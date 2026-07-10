from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ContentBrief, LinkedInAccount, User
from app.schemas import BriefCreate
from app.security import get_current_user
from app.tasks.generation_tasks import generate_from_brief

router = APIRouter(prefix="/briefs", tags=["briefs"])


@router.post("", status_code=202)
def create_brief(
    payload: BriefCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    account = (
        db.query(LinkedInAccount)
        .filter_by(id=payload.linkedin_account_id, user_id=user.id)
        .first()
    )
    if not account:
        raise HTTPException(404, "Conta LinkedIn não encontrada para este usuário")

    brief = ContentBrief(
        user_id=user.id,
        theme=payload.theme,
        instructions=payload.instructions,
        posts_per_week=payload.posts_per_week,
        language=payload.language,
    )
    db.add(brief)
    db.commit()

    generate_from_brief.delay(str(brief.id), str(account.id))
    return {"brief_id": str(brief.id), "status": "generating"}
