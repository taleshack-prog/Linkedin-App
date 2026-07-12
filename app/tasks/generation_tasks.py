"""Task de geração: pauta -> pesquisa -> N posts em draft (aguardando revisão)."""
import logging

from app.database import SessionLocal
from app.models import BrandProfile, ContentBrief, LinkedInAccount, Post, PostStatus
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

        profile = None
        if brief.use_profile:
            profile = db.query(BrandProfile).filter_by(user_id=brief.user_id).first()
        posts = generate_posts(
            theme=brief.theme,
            instructions=brief.instructions,
            count=brief.posts_per_week,
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
