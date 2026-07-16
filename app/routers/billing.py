"""Billing (Stripe) e indicação.

Fluxo: GET /billing/plans (público) -> POST /billing/checkout (cria sessão) ->
Stripe hospeda o pagamento -> webhook provisiona/revoga. O webhook é a fonte da
verdade da assinatura (nunca confiar no redirect de sucesso do cliente).
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.services import referrals
from app.services.plans import PLANS, REFERRAL_TIERS, REFERRED_BONUS_DAYS, plan_of
from app.services.referrals import count_active_referrals

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _stripe():
    import stripe

    s = get_settings()
    if not s.STRIPE_SECRET_KEY:
        raise HTTPException(503, "Pagamentos não configurados no servidor")
    stripe.api_key = s.STRIPE_SECRET_KEY
    return stripe


def _price_id(plan_key: str) -> str | None:
    s = get_settings()
    return {
        "starter": s.STRIPE_PRICE_STARTER,
        "pro": s.STRIPE_PRICE_PRO,
        "agency": s.STRIPE_PRICE_AGENCY,
    }.get(plan_key)



def _ensure_customer(stripe, db: Session, user: User) -> str:
    """Devolve um customer válido no modo ATUAL do Stripe (test ou live).

    Um customer criado no modo teste não existe no modo ativo (e vice-versa).
    Na virada test->live, o ID gravado vira órfão e o Stripe responde
    "No such customer". Aqui detectamos e recriamos — sem isso, o primeiro
    checkout em produção falharia para todo usuário que já testou.
    """
    if user.stripe_customer_id:
        try:
            cust = stripe.Customer.retrieve(user.stripe_customer_id)
            if not getattr(cust, "deleted", False):
                return user.stripe_customer_id
            log.warning("Customer %s excluído no Stripe — recriando", user.stripe_customer_id)
        except Exception:  # noqa: BLE001 — inclui "No such customer" (troca test<->live)
            log.warning(
                "Customer %s inválido no modo atual (virada test/live?) — recriando",
                user.stripe_customer_id,
            )
    customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


# ---------- Planos (público, para a página de preços) ----------
@router.get("/plans")
def list_plans():
    return {
        "plans": [
            {
                "key": p.key, "name": p.name, "price_cents": p.price_cents,
                "linkedin_accounts": p.linkedin_accounts, "ai_images": p.ai_images,
                "doc_upload": p.doc_upload, "brand_profile": p.brand_profile,
                "text_formatting": p.text_formatting,
            }
            for p in PLANS.values() if p.key != "free"
        ],
        "referral_tiers": [{"referrals": t, "months": m} for t, m in REFERRAL_TIERS],
        "referred_bonus_days": REFERRED_BONUS_DAYS,
        "guarantee_days": get_settings().GUARANTEE_DAYS,
    }


# ---------- Status da conta ----------
class BillingStatus(BaseModel):
    plan: str
    plan_name: str
    plan_until: datetime | None
    referral_code: str | None
    active_referrals: int
    months_earned: int
    text_formatting: bool = False
    ai_images: bool = False
    doc_upload: bool = False


@router.get("/status", response_model=BillingStatus)
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = plan_of(user)
    return BillingStatus(
        plan=p.key,
        plan_name=p.name,
        plan_until=user.plan_until,
        referral_code=user.referral_code,
        active_referrals=count_active_referrals(db, user.id),
        months_earned=user.referral_months_granted or 0,
        text_formatting=p.text_formatting,
        ai_images=p.ai_images,
        doc_upload=p.doc_upload,
    )


# ---------- Checkout ----------
class CheckoutIn(BaseModel):
    plan: str  # starter | pro | agency


@router.post("/checkout")
def create_checkout(
    payload: CheckoutIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.plan not in ("starter", "pro", "agency"):
        raise HTTPException(400, "Plano inválido")
    price = _price_id(payload.plan)
    if not price:
        raise HTTPException(503, f"Preço do plano {payload.plan} não configurado")

    stripe = _stripe()
    s = get_settings()

    customer_id = _ensure_customer(stripe, db, user)

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price, "quantity": 1}],
        subscription_data={
            "metadata": {"user_id": str(user.id), "plan": payload.plan},
        },
        metadata={"user_id": str(user.id), "plan": payload.plan},
        success_url=f"{s.FRONTEND_APP_URL}/?billing=success",
        cancel_url=f"{s.FRONTEND_APP_URL}/?billing=cancel",
        allow_promotion_codes=True,
    )
    return {"url": session.url}


# ---------- Portal (gerenciar/cancelar assinatura) ----------
@router.post("/portal")
def customer_portal(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.stripe_customer_id:
        raise HTTPException(400, "Sem assinatura para gerenciar")
    stripe = _stripe()
    s = get_settings()
    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id, return_url=f"{s.FRONTEND_APP_URL}/",
        )
    except Exception:  # noqa: BLE001 — customer de outro modo (test/live)
        log.warning("Portal indisponível p/ customer %s (modo trocado?)", user.stripe_customer_id)
        raise HTTPException(409, "Assinatura não encontrada — assine novamente para gerenciar")
    return {"url": session.url}


# ---------- Webhook (fonte da verdade) ----------
def _grant(db: Session, user: User, plan: str, until: datetime | None):
    user.plan = plan
    user.plan_until = until
    db.commit()
    referrals.on_referred_user_subscribed(db, user)


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(default=None)):
    stripe = _stripe()
    s = get_settings()
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, s.STRIPE_WEBHOOK_SECRET)
    except Exception:  # noqa: BLE001 — assinatura inválida/payload adulterado
        raise HTTPException(400, "Assinatura do webhook inválida")

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        _handle_event(db, stripe, event)
    except Exception:
        # Log completo p/ diagnóstico; erro 500 faz o Stripe reenviar o evento
        log.exception("Falha ao processar webhook %s", _g(event, "type"))
        raise
    finally:
        db.close()
    return {"received": True}


def _g(obj, key, default=None):
    """Acesso seguro a campos do Stripe.

    A lib entrega StripeObject, que NÃO herda de dict e NÃO tem .get() (v15+).
    Este acessor funciona com StripeObject (via getattr) e com dict puro
    (usado nos testes) — a divergência entre os dois foi o que deixou o bug
    'AttributeError: get' passar dos testes para a produção.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _period_end(sub) -> datetime | None:
    """Fim do período vigente da assinatura.

    A API "Basil" (2025-03-31) REMOVEU current_period_end da Subscription e o
    moveu para os items (items.data[].current_period_end). Lemos dos dois lugares
    para funcionar em qualquer versão de API configurada na webhook.
    """
    ts = _g(sub, "current_period_end")
    if not ts:
        items = _g(_g(sub, "items"), "data") or []
        ts = next((_g(i, "current_period_end") for i in items if _g(i, "current_period_end")), None)
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


def _subscription_id_from_invoice(inv) -> str | None:
    """ID da assinatura numa invoice. Basil moveu invoice.subscription para
    invoice.parent.subscription_details.subscription."""
    sub = _g(inv, "subscription")
    if sub:
        return sub if isinstance(sub, str) else _g(sub, "id")
    details = _g(_g(inv, "parent"), "subscription_details")
    sub = _g(details, "subscription")
    return sub if isinstance(sub, str) else _g(sub, "id")


def _user_by_customer(db: Session, customer_id: str) -> User | None:
    if not customer_id:
        return None
    return db.query(User).filter_by(stripe_customer_id=customer_id).first()


def _handle_event(db, stripe, event) -> None:
    etype = _g(event, "type")
    obj = _g(_g(event, "data"), "object")

    if etype == "checkout.session.completed":
        customer = _g(obj, "customer")
        user = _user_by_customer(db, customer)
        plan = _g(_g(obj, "metadata"), "plan")
        if not user:
            log.warning("Webhook %s: cliente %s sem usuário local", etype, customer)
            return
        sub_id = _g(obj, "subscription")
        if plan and sub_id:
            sub = stripe.Subscription.retrieve(sub_id)
            _grant(db, user, plan, _period_end(sub))
            log.info("Assinatura provisionada: user=%s plano=%s", user.email, plan)

    elif etype in ("customer.subscription.updated", "invoice.paid"):
        # Renovação/mudança: reflete período e plano vigentes
        if etype == "customer.subscription.updated":
            sub = obj
        else:
            sub_id = _subscription_id_from_invoice(obj)
            if not sub_id:
                return  # invoice avulsa, sem assinatura
            sub = stripe.Subscription.retrieve(sub_id)
        user = _user_by_customer(db, _g(sub, "customer"))
        if user and _g(sub, "status") in ("active", "trialing"):
            plan = _g(_g(sub, "metadata"), "plan") or user.plan
            _grant(db, user, plan, _period_end(sub))
            log.info("Assinatura atualizada: user=%s plano=%s", user.email, plan)

    elif etype in ("customer.subscription.deleted", "invoice.payment_failed"):
        cust = _g(obj, "customer")
        user = _user_by_customer(db, cust)
        if user:
            # Não zera na hora do fail (Stripe re-tenta); expira no fim do período pago.
            if etype == "customer.subscription.deleted":
                user.plan = "free"
                user.plan_until = None
                db.commit()
