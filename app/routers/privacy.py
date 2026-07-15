"""Direitos do titular (LGPD, art. 18): portabilidade e exclusão de dados.

- GET  /privacy/export  -> todos os dados do usuário em JSON (art. 18, V)
- DELETE /privacy/account -> exclusão definitiva (art. 18, VI)

A exclusão faz, nesta ordem:
1. Cancela a assinatura no Stripe (não se pode cobrar quem excluiu a conta);
2. Revoga os tokens no LinkedIn (não manter acesso à conta de terceiro);
3. Apaga o usuário — o schema cascateia contas, pautas, posts, imagens,
   logs e perfil de marca (ON DELETE CASCADE).

Os passos 1 e 2 são best-effort: falha em provedor externo não pode impedir
o titular de exercer o direito de exclusão.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import BrandProfile, ContentBrief, LinkedInAccount, Post, PublishLog, User
from app.security import decrypt, get_current_user
from app.services import linkedin_client as li

log = logging.getLogger(__name__)

router = APIRouter(prefix="/privacy", tags=["privacy"])


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


@router.get("/export")
def export_data(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Portabilidade (LGPD art. 18, V): todos os dados do titular em JSON.

    Tokens do LinkedIn NÃO são exportados: são credenciais de acesso, não dado
    pessoal do titular, e exportá-los criaria um risco de segurança.
    """
    accounts = db.query(LinkedInAccount).filter_by(user_id=user.id).all()
    briefs = db.query(ContentBrief).filter_by(user_id=user.id).all()
    posts = db.query(Post).filter_by(user_id=user.id).all()
    profile = db.query(BrandProfile).filter_by(user_id=user.id).first()

    return {
        "exportado_em": _iso(datetime.now()),
        "conta": {
            "email": user.email,
            "nome": user.name,
            "plano": user.plan,
            "plano_valido_ate": _iso(user.plan_until),
            "codigo_de_indicacao": user.referral_code,
            "criada_em": _iso(user.created_at),
        },
        "contas_linkedin": [
            {
                "nome_exibicao": a.display_name,
                "person_urn": a.person_urn,
                "status": a.status,
                "conectada_em": _iso(a.created_at),
            }
            for a in accounts
        ],
        "perfil_de_marca": profile.to_context_dict() if profile else None,
        "pautas": [
            {
                "tema": b.theme,
                "instrucoes": b.instructions,
                "posts_por_semana": b.posts_per_week,
                "idioma": b.language,
                "status": b.status,
                "arquivo_de_referencia": b.source_filename,
                "texto_de_referencia": b.source_text,
                "criada_em": _iso(b.created_at),
            }
            for b in briefs
        ],
        "posts": [
            {
                "texto": p.commentary,
                "hashtags": p.hashtags,
                "fontes": p.sources,
                "status": p.status.value if p.status else None,
                "tem_imagem": p.has_image,
                "agendado_para": _iso(p.publish_at),
                "publicado_em": _iso(p.published_at),
                "urn_linkedin": p.linkedin_post_urn,
                "criado_em": _iso(p.created_at),
            }
            for p in posts
        ],
    }


class DeleteAccountIn(BaseModel):
    confirmacao: str  # o usuário digita EXCLUIR


@router.delete("/account", status_code=204)
def delete_account(
    payload: DeleteAccountIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Exclusão definitiva da conta e de todos os dados (LGPD art. 18, VI)."""
    if payload.confirmacao.strip().upper() != "EXCLUIR":
        raise HTTPException(400, 'Digite EXCLUIR para confirmar')

    email = user.email

    # 1) Cancelar assinatura ativa (best-effort)
    if user.stripe_customer_id and get_settings().STRIPE_SECRET_KEY:
        try:
            import stripe

            stripe.api_key = get_settings().STRIPE_SECRET_KEY
            subs = stripe.Subscription.list(customer=user.stripe_customer_id, status="active")
            for sub in subs.auto_paging_iter():
                stripe.Subscription.cancel(sub.id)
            log.info("Assinaturas canceladas na exclusão: %s", email)
        except Exception:  # noqa: BLE001
            log.exception("Falha ao cancelar assinatura de %s (exclusão prossegue)", email)

    # 2) Revogar tokens do LinkedIn (best-effort)
    for account in db.query(LinkedInAccount).filter_by(user_id=user.id).all():
        try:
            li.revoke_token(decrypt(account.access_token_enc))
        except Exception:  # noqa: BLE001
            log.warning("Falha ao revogar token da conta %s (exclusão prossegue)", account.id)

    # 3) Apagar tudo (cascade cuida de contas, pautas, posts, imagens, logs, perfil)
    post_ids = [p.id for p in db.query(Post.id).filter_by(user_id=user.id).all()]
    if post_ids:
        db.query(PublishLog).filter(PublishLog.post_id.in_(post_ids)).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    log.info("Conta excluída definitivamente: %s", email)
