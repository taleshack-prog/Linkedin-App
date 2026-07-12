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

MAX_SOURCE_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    theme: str
    instructions: str | None
    posts_per_week: int
    language: str
    status: str
    error: str | None
    use_profile: bool = True
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
    use_profile: bool = Form(default=True),
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
            raise HTTPException(413, "Arquivo acima de 25 MB")
        try:
            source_text = extract_text(source_file.filename, data)
        except ExtractionError as exc:
            raise HTTPException(422, str(exc))
        source_filename = source_file.filename

    brief = ContentBrief(
        user_id=user.id,
        linkedin_account_id=account.id,
        theme=theme,
        instructions=instructions or None,
        posts_per_week=posts_per_week,
        language=language,
        use_profile=use_profile,
        source_text=source_text,
        source_filename=source_filename,
    )
    db.add(brief)
    db.commit()

    generate_from_brief.delay(str(brief.id), str(account.id))
    return {"brief_id": str(brief.id), "status": "generating"}


def _own_brief(brief_id: uuid.UUID, db: Session, user: User) -> ContentBrief:
    brief = db.query(ContentBrief).filter_by(id=brief_id, user_id=user.id).first()
    if not brief:
        raise HTTPException(404, "Pauta não encontrada")
    return brief


class BriefUpdate(BaseModel):
    theme: str | None = None
    instructions: str | None = None
    posts_per_week: int | None = None
    language: str | None = None
    use_profile: bool | None = None


@router.patch("/{brief_id}", response_model=BriefOut)
def edit_brief(
    brief_id: uuid.UUID,
    payload: BriefUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Refina/corrige a pauta. Depois, use 'regenerate' para gerar com o texto novo."""
    brief = _own_brief(brief_id, db, user)
    if brief.status == "generating":
        raise HTTPException(409, "Pauta em geração — aguarde concluir para editar")
    if payload.theme is not None:
        theme = payload.theme.strip()
        if not (3 <= len(theme) <= 500):
            raise HTTPException(422, "Tema deve ter entre 3 e 500 caracteres")
        brief.theme = theme
    if payload.instructions is not None:
        brief.instructions = payload.instructions.strip()[:2000] or None
    if payload.posts_per_week is not None:
        if not (1 <= payload.posts_per_week <= 7):
            raise HTTPException(422, "posts_per_week deve estar entre 1 e 7")
        brief.posts_per_week = payload.posts_per_week
    if payload.language is not None:
        brief.language = payload.language
    if payload.use_profile is not None:
        brief.use_profile = payload.use_profile
    db.commit()
    return brief


@router.post("/{brief_id}/regenerate", status_code=202)
def regenerate_brief(
    brief_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Gera novamente (retry de falha ou nova rodada após editar).

    Rascunhos existentes não são tocados — duplicatas podem ser canceladas na fila.
    """
    brief = _own_brief(brief_id, db, user)
    if brief.status == "generating":
        raise HTTPException(409, "Pauta já está em geração")

    account = None
    if brief.linkedin_account_id:
        account = (
            db.query(LinkedInAccount)
            .filter_by(id=brief.linkedin_account_id, user_id=user.id)
            .first()
        )
    if not account:  # pautas antigas (sem conta persistida) ou conta removida
        account = (
            db.query(LinkedInAccount)
            .filter_by(user_id=user.id, status="active")
            .order_by(LinkedInAccount.created_at.desc())
            .first()
        )
    if not account:
        raise HTTPException(409, "Nenhuma conta LinkedIn conectada para gerar")

    brief.linkedin_account_id = account.id
    brief.status = "pending"
    brief.error = None
    db.commit()
    generate_from_brief.delay(str(brief.id), str(account.id))
    return {"brief_id": str(brief.id), "status": "generating"}


@router.delete("/{brief_id}", status_code=204)
def delete_brief(
    brief_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Exclui a pauta. Posts já gerados por ela são preservados (vínculo vira nulo)."""
    brief = _own_brief(brief_id, db, user)
    if brief.status == "generating":
        raise HTTPException(409, "Pauta em geração — aguarde concluir para excluir")
    db.delete(brief)
    db.commit()
