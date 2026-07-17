"""Tasks de publicação e manutenção de tokens.

Fluxo:
  beat (60s) -> scan_due_posts: pega posts approved com publish_at vencido,
  usando SELECT ... FOR UPDATE SKIP LOCKED (seguro com múltiplos workers),
  marca como publishing e despacha publish_post por post.

Robustez:
  - Posts presos em 'publishing' (worker morreu no meio) voltam para
    'approved' após STALE_PUBLISHING_MINUTES e são reprocessados.
  - 401/403 => needs_reauth, sem retry (problema de credencial).
  - Outros erros => retry com backoff linear até MAX_PUBLISH_ATTEMPTS.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import LinkedInAccount, Post, PostStatus, PublishLog, User
from app.security import decrypt, encrypt
from app.services import linkedin_client as li
from app.tasks.celery_app import celery

log = logging.getLogger(__name__)


@celery.task
def scan_due_posts():
    s = get_settings()
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1) Resgate: posts presos em 'publishing' (worker caiu) voltam à fila.
        stale_limit = now - timedelta(minutes=s.STALE_PUBLISHING_MINUTES)
        stale = (
            db.execute(
                select(Post)
                .where(Post.status == PostStatus.publishing, Post.updated_at <= stale_limit)
                .with_for_update(skip_locked=True)
            )
            .scalars()
            .all()
        )
        for post in stale:
            log.warning("Post %s preso em publishing — devolvendo para approved", post.id)
            post.status = PostStatus.approved
        if stale:
            db.commit()

        # 2) Fila normal: approved com publish_at vencido.
        stmt = (
            select(Post)
            .where(Post.status == PostStatus.approved, Post.publish_at <= now)
            .with_for_update(skip_locked=True)
            .limit(50)
        )
        due = db.execute(stmt).scalars().all()
        ids = []
        for post in due:
            # Assinatura cancelada/expirada: não publicamos. O post fica em
            # 'approved' e volta a ser publicável quando o plano for reativado —
            # nada é destruído, mas não há serviço sem assinatura.
            from app.services.plans import has_active_subscription

            owner = db.get(User, post.user_id)
            if not owner or not has_active_subscription(owner):
                log.info("Post %s adiado: assinatura inativa (%s)", post.id,
                         owner.email if owner else "usuário removido")
                continue
            post.status = PostStatus.publishing
            ids.append(str(post.id))
        db.commit()
        for pid in ids:
            publish_post.delay(pid)
        if ids:
            log.info("Despachados %d posts para publicação", len(ids))
    finally:
        db.close()


def _ensure_fresh_token(db, account: LinkedInAccount) -> str:
    """Retorna access token válido, renovando via refresh_token se preciso."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    margin = timedelta(days=s.TOKEN_REFRESH_MARGIN_DAYS)

    if account.access_expires_at > now + margin:
        return decrypt(account.access_token_enc)

    if not account.refresh_token_enc or (
        account.refresh_expires_at and account.refresh_expires_at <= now
    ):
        account.status = "needs_reauth"
        db.commit()
        raise li.LinkedInError(401, "Token expirado e sem refresh válido — reautenticação necessária")

    data = li.refresh_access_token(decrypt(account.refresh_token_enc))
    access_exp, refresh_exp = li.tokens_to_expiry(data)
    account.access_token_enc = encrypt(data["access_token"])
    account.access_expires_at = access_exp
    if data.get("refresh_token"):
        account.refresh_token_enc = encrypt(data["refresh_token"])
        account.refresh_expires_at = refresh_exp
    db.commit()
    return data["access_token"]


def _full_commentary(post: Post) -> str:
    commentary = post.commentary
    if post.hashtags:
        commentary += "\n\n" + " ".join(
            h if h.startswith("#") else f"#{h}" for h in post.hashtags
        )
    return commentary


@celery.task(bind=True, max_retries=0)
def publish_post(self, post_id: str):
    s = get_settings()
    db = SessionLocal()
    try:
        post = db.get(Post, post_id)
        if not post or post.status != PostStatus.publishing:
            return

        account = db.get(LinkedInAccount, post.linkedin_account_id)
        post.attempts += 1

        try:
            commentary = _full_commentary(post)
            if len(commentary) > s.LINKEDIN_COMMENTARY_MAX_CHARS:
                raise li.LinkedInError(
                    422,
                    f"commentary + hashtags com {len(commentary)} chars excede o limite "
                    f"de {s.LINKEDIN_COMMENTARY_MAX_CHARS} do LinkedIn — edite o post",
                )

            token = _ensure_fresh_token(db, account)

            # Imagem opcional: sobe para o LinkedIn antes do post (Images API, 2 etapas)
            image_urn = None
            if post.image_mime:
                upload_url, image_urn = li.initialize_image_upload(token, account.person_urn)
                li.upload_image_binary(upload_url, token, post.image_data)

            urn, status_code, meta = li.publish_text_post(
                token, account.person_urn, commentary, image_urn=image_urn
            )

            post.status = PostStatus.published
            post.published_at = datetime.now(timezone.utc)
            post.linkedin_post_urn = urn
            post.last_error = None
            db.add(PublishLog(post_id=post.id, attempt=post.attempts, success=True,
                              http_status=status_code, response=meta))
            db.commit()
            log.info("Post %s publicado: %s", post_id, urn)

        except li.LinkedInError as exc:
            db.add(PublishLog(post_id=post.id, attempt=post.attempts, success=False,
                              http_status=exc.status, response={"body": exc.body[:2000]}))
            post.last_error = str(exc)[:2000]
            # 401/403: credencial; 422: conteúdo inválido — retry não resolve.
            if exc.status in (401, 403, 422) or post.attempts >= s.MAX_PUBLISH_ATTEMPTS:
                post.status = PostStatus.failed
            else:
                post.status = PostStatus.approved
                post.publish_at = datetime.now(timezone.utc) + timedelta(minutes=5 * post.attempts)
            db.commit()
    finally:
        db.close()


@celery.task
def refresh_expiring_tokens():
    """Renova proativamente tokens perto de expirar (evita falha na hora do post)."""
    s = get_settings()
    db = SessionLocal()
    try:
        limit = datetime.now(timezone.utc) + timedelta(days=s.TOKEN_REFRESH_MARGIN_DAYS)
        accounts = (
            db.query(LinkedInAccount)
            .filter(LinkedInAccount.status == "active", LinkedInAccount.access_expires_at <= limit)
            .all()
        )
        for acc in accounts:
            try:
                _ensure_fresh_token(db, acc)
            except Exception as exc:  # noqa: BLE001
                log.warning("Falha ao renovar token da conta %s: %s", acc.id, exc)
    finally:
        db.close()
