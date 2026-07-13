"""Billing (Stripe) e indicação.

Fluxo: GET /billing/plans (público) -> POST /billing/checkout (cria sessão) ->
Stripe hospeda o pagamento -> webhook provisiona/revoga. O webhook é a fonte da
verdade da assinatura (nunca confiar no redirect de sucesso do cliente).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.services import referrals
from app.services.plans import PLANS, REFERRAL_TIERS, plan_of
from app.services.referrals import count_active_referrals

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


# ---------- Planos (público, para a página de preços) ----------
@router.get("/plans")
def list_plans():
    return {
        "plans": [
            {
                "key": p.key, "name": p.name, "price_brl": p.price_brl,
                "linkedin_accounts": p.linkedin_accounts, "ai_images": p.ai_images,
                "doc_upload": p.doc_upload, "brand_profile": p.brand_profile,
            }
            for p in PLANS.values() if p.key != "free"
        ],
        "referral_tiers": [{"referrals": t, "months": m} for t, m in REFERRAL_TIERS],
        "trial_days": get_settings().TRIAL_DAYS,
    }


# ---------- Status da conta ----------
class BillingStatus(BaseModel):
    plan: str
    plan_name: str
    plan_until: datetime | None
    referral_code: str | None
    active_referrals: int
    months_earned: int


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

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
        user.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=user.stripe_customer_id,
        line_items=[{"price": price, "quantity": 1}],
        subscription_data={
            "trial_period_days": s.TRIAL_DAYS,
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
def customer_portal(user: User = Depends(get_current_user)):
    if not user.stripe_customer_id:
        raise HTTPException(400, "Sem assinatura para gerenciar")
    stripe = _stripe()
    s = get_settings()
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=f"{s.FRONTEND_APP_URL}/",
    )
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
    finally:
        db.close()
    return {"received": True}


def _user_by_customer(db: Session, customer_id: str) -> User | None:
    return db.query(User).filter_by(stripe_customer_id=customer_id).first()


def _handle_event(db, stripe, event) -> None:
    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        user = _user_by_customer(db, obj.get("customer"))
        plan = (obj.get("metadata") or {}).get("plan")
        if user and plan and obj.get("subscription"):
            sub = stripe.Subscription.retrieve(obj["subscription"])
            until = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
            _grant(db, user, plan, until)

    elif etype in ("customer.subscription.updated", "invoice.paid"):
        # Renovação/mudança: reflete período e plano vigentes
        sub = obj if etype == "customer.subscription.updated" else stripe.Subscription.retrieve(obj["subscription"])
        user = _user_by_customer(db, sub.get("customer"))
        if user and sub.get("status") in ("active", "trialing"):
            plan = (sub.get("metadata") or {}).get("plan") or user.plan
            until = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
            _grant(db, user, plan, until)

    elif etype in ("customer.subscription.deleted", "invoice.payment_failed"):
        cust = obj.get("customer")
        user = _user_by_customer(db, cust)
        if user:
            # Não zera na hora do fail (Stripe re-tenta); expira no fim do período pago.
            if etype == "customer.subscription.deleted":
                user.plan = "free"
                user.plan_until = None
                db.commit()
