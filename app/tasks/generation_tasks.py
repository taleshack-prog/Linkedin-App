"""Task de geração: pauta -> pesquisa -> N posts em draft (aguardando revisão)."""
import logging

from app.database import SessionLocal
from app.models import BrandProfile, ContentBrief, LinkedInAccount, Post, PostStatus, User
from app.services.plans import max_posts_for
from app.services.usage import posts_used_this_month
from app.services.content_generator import generate_posts
from app.tasks.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_from_brief(self, brief_id: str, linkedin_account_id: str):
    db = SessionLocal()
    try:
        brief = db.get(ContentBrief, brief_id)
        account = db.get(LinkedInAccount, linkedin_account_id)
        if not brief or not account:
            log.error("Brief ou conta inexistente: %s / %s", brief_id, linkedin_account_id)
            return

        brief.status = "generating"
        db.commit()

        # Teto de geração do plano (mês-calendário). -1 = ilimitado.
        requested = brief.posts_per_week
        user = db.get(User, brief.user_id)
        cap = max_posts_for(user) if user else -1
        if cap >= 0:
            remaining = cap - posts_used_this_month(db, brief.user_id)
            if remaining <= 0:
                brief.status = "failed"
                brief.error = (
                    f"Limite de {cap} posts gerados neste mes atingido. "
                    "Faca upgrade de plano para gerar mais."
                )
                db.commit()
                return
            requested = min(requested, remaining)

        profile = None
        if brief.use_profile:
            profile = db.query(BrandProfile).filter_by(user_id=brief.user_id).first()
        posts = generate_posts(
            theme=brief.theme,
            instructions=brief.instructions,
            count=requested,
            language=brief.language,
            profile=profile.to_context_dict() if profile else None,
            source_text=brief.source_text,
        )
        for p in posts:
            db.add(
                Post(
                    user_id=brief.user_id,
                    brief_id=brief.id,
                    linkedin_account_id=account.id,
                    commentary=p["commentary"],
                    hashtags=p["hashtags"],
                    sources=p["sources"],
                    status=PostStatus.draft,
                )
            )
        brief.status = "generated"
        db.commit()
    except Exception as exc:
        db.rollback()
        brief = db.get(ContentBrief, brief_id)
        if brief:
            brief.status = "failed"
            brief.error = str(exc)[:2000]
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()
