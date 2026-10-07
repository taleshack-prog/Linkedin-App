"""Task de geração: pauta -> pesquisa -> N posts em draft (aguardando revisão)."""
import logging

from app.database import SessionLocal
from app.models import BrandProfile, ContentBrief, LinkedInAccount, Post, PostStatus, ProfileAudit, User
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
        orientacao = None
        if brief.use_profile:
            profile = db.query(BrandProfile).filter_by(user_id=brief.user_id).first()
            # As diretrizes vêm da auditoria mais recente. Ficam aqui, e não no
            # BrandProfile, porque `angulo` e `evitar` não têm campo lá — e
            # `evitar` é justamente o que impede a geração de repetir o vício
            # que a auditoria apontou.
            ultima = (
                db.query(ProfileAudit)
                .filter_by(user_id=brief.user_id)
                .order_by(ProfileAudit.created_at.desc())
                .first()
            )
            if ultima and isinstance(ultima.resultado, dict):
                orientacao = ultima.resultado.get("para_geracao")
        posts = generate_posts(
            theme=brief.theme,
            instructions=brief.instructions,
            count=requested,
            language=brief.language,
            profile=profile.to_context_dict() if profile else None,
            source_text=brief.source_text,
            audit_guidance=orientacao,
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
        # A task tenta 3 vezes (1 + max_retries), com 60s entre elas. Marcar
        # "falhou" já na primeira fazia o usuário ver o erro — e ser instruído a
        # tentar de novo — enquanto duas tentativas ainda estavam a caminho. Pior:
        # quando ele finalmente via a falha, a mensagem sugeria instabilidade
        # temporária, sem dizer que o temporário já tinha sido descartado 3x.
        ultima = self.request.retries >= self.max_retries
        brief = db.get(ContentBrief, brief_id)
        if brief:
            if ultima:
                brief.status = "failed"
                tentativas = self.max_retries + 1
                brief.error = f"{exc} (tentado {tentativas}x, com 1 min entre as tentativas)"[:2000]
            else:
                brief.status = "generating"  # ainda há tentativa pela frente
                brief.error = None
            db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()
