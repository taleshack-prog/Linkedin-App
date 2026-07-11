import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ContentBrief, LinkedInAccount, User
from app.security import get_current_user
from app.services.text_extractor import ExtractionError, extract_text
from app.tasks.generation_tasks import generate_from_brief

router = APIRouter(prefix="/briefs", tags=["briefs"])

MAX_SOURCE_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    theme: str
    instructions: str | None
    posts_per_week: int
    language: str
    status: str
    error: str | None
    source_filename: str | None
    created_at: datetime


@router.get("", response_model=list[BriefOut])
def list_briefs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(ContentBrief)
        .filter_by(user_id=user.id)
        .order_by(ContentBrief.created_at.desc())
        .limit(100)
        .all()
    )


@router.post("", status_code=202)
async def create_brief(
    theme: str = Form(min_length=3, max_length=500),
    linkedin_account_id: uuid.UUID = Form(...),
    instructions: str | None = Form(default=None, max_length=2000),
    posts_per_week: int = Form(default=3, ge=1, le=7),
    language: str = Form(default="pt-BR"),
    source_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cria a pauta. Com arquivo de referência (PDF/DOCX/TXT/MD/CSV), a IA baseia
    os posts naquele conteúdo e usa a web apenas para complementar."""
    account = (
        db.query(LinkedInAccount)
        .filter_by(id=linkedin_account_id, user_id=user.id)
        .first()
    )
    if not account:
        raise HTTPException(404, "Conta LinkedIn não encontrada para este usuário")

    source_text = None
    source_filename = None
    if source_file is not None and source_file.filename:
        data = await source_file.read()
        if len(data) > MAX_SOURCE_FILE_BYTES:
            raise HTTPException(413, "Arquivo acima de 10 MB")
        try:
            source_text = extract_text(source_file.filename, data)
        except ExtractionError as exc:
            raise HTTPException(422, str(exc))
        source_filename = source_file.filename

    brief = ContentBrief(
        user_id=user.id,
        theme=theme,
        instructions=instructions or None,
        posts_per_week=posts_per_week,
        language=language,
        source_text=source_text,
        source_filename=source_filename,
    )
    db.add(brief)
    db.commit()

    generate_from_brief.delay(str(brief.id), str(account.id))
    return {"brief_id": str(brief.id), "status": "generating"}
