"""Perfil de marca do usuário — contexto injetado em toda geração de posts.

Um perfil por usuário (upsert via PUT). Todos os campos são opcionais:
quanto mais preenchido, mais direcionada a geração.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BrandProfile, ProfileAudit, User
from app.security import get_current_user, require_subscription
from app.services.audit_ingest import rodar_auditoria
from app.services.linkedin_export import ExportError, parse_analytics_xlsx
from app.services.plans import require_feature
from app.services.text_extractor import ExtractionError, extract_text, limpar_contato_do_perfil

router = APIRouter(prefix="/profile", tags=["profile"])

ENTITY_TYPES = {"autonomo", "colaborador", "empresa"}
GOALS = {"autoridade", "leads", "networking", "recrutamento", "marca_empregadora"}


class ProfileIn(BaseModel):
    entity_type: str | None = Field(default=None, max_length=30)
    role: str | None = Field(default=None, max_length=300)
    company: str | None = Field(default=None, max_length=300)
    industry: str | None = Field(default=None, max_length=300)
    audience: str | None = Field(default=None, max_length=500)
    goal: str | None = Field(default=None, max_length=30)
    tone: str | None = Field(default=None, max_length=500)
    pillars: str | None = Field(default=None, max_length=1000)
    positioning: str | None = Field(default=None, max_length=2000)


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime | None = None


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = db.query(BrandProfile).filter_by(user_id=user.id).first()
    return profile or ProfileOut()


@router.put("", response_model=ProfileOut)
def upsert_profile(
    payload: ProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = db.query(BrandProfile).filter_by(user_id=user.id).first()
    if not profile:
        profile = BrandProfile(user_id=user.id)
        db.add(profile)
    data = payload.model_dump()
    # normaliza os campos de escolha; valores fora da lista viram None
    if data.get("entity_type") not in ENTITY_TYPES:
        data["entity_type"] = None
    if data.get("goal") not in GOALS:
        data["goal"] = None
    for field, value in data.items():
        setattr(profile, field, value.strip() if isinstance(value, str) and value.strip() else None)
    db.commit()
    db.refresh(profile)
    return profile


# ===========================================================================
# Auditoria de marca
#
# Alimentada por upload, não por API: os escopos self-serve do LinkedIn não
# entregam headline, "sobre" nem métrica. O usuário baixa dois arquivos da
# própria conta (PDF do perfil e .xlsx de análises) e sobe aqui.
#
# Roda de forma síncrona: é UMA chamada ao modelo, sem busca na web. Se o
# tempo de resposta virar problema com material grande, o caminho é mover
# para o Celery, como a geração de posts.
# ===========================================================================
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_XLSX_BYTES = 10 * 1024 * 1024
MAX_IMG_BYTES = 4 * 1024 * 1024
MAX_IMAGENS = 4


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    score_total: int | None
    score_perfil: int | None
    score_conteudo: int | None
    score_consistencia: int | None
    fontes: list[str]
    resultado: dict
    created_at: datetime


@router.get("/audit", response_model=AuditOut | None)
def ultima_auditoria(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(ProfileAudit)
        .filter_by(user_id=user.id)
        .order_by(ProfileAudit.created_at.desc())
        .first()
    )


@router.get("/audit/historico", response_model=list[AuditOut])
def historico_auditorias(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(ProfileAudit)
        .filter_by(user_id=user.id)
        .order_by(ProfileAudit.created_at.desc())
        .limit(12)
        .all()
    )


@router.post("/audit", response_model=AuditOut)
async def criar_auditoria(
    perfil_pdf: UploadFile | None = File(default=None),
    analytics_xlsx: UploadFile | None = File(default=None),
    posts_texto: str | None = Form(default=None),
    imagens: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = Depends(require_subscription),
):
    if not require_feature(user, "audit"):
        raise HTTPException(402, "A auditoria de marca está disponível a partir do plano Pro")

    perfil_texto = None
    if perfil_pdf is not None and perfil_pdf.filename:
        dados = await perfil_pdf.read()
        if len(dados) > MAX_PDF_BYTES:
            raise HTTPException(413, "PDF do perfil acima de 10 MB")
        try:
            bruto = extract_text(perfil_pdf.filename, dados)
        except ExtractionError as exc:
            raise HTTPException(422, str(exc))
        # endereço, telefone e e-mail não servem para auditar posicionamento
        # e não precisam trafegar até a IA (ver text_extractor)
        perfil_texto = limpar_contato_do_perfil(bruto)

    metricas = None
    if analytics_xlsx is not None and analytics_xlsx.filename:
        dados = await analytics_xlsx.read()
        if len(dados) > MAX_XLSX_BYTES:
            raise HTTPException(413, "Planilha acima de 10 MB")
        try:
            metricas = parse_analytics_xlsx(dados, analytics_xlsx.filename)
        except ExportError as exc:
            raise HTTPException(422, str(exc))

    imgs: list[tuple[str, bytes]] = []
    for arquivo in (imagens or [])[:MAX_IMAGENS]:
        if not arquivo or not arquivo.filename:
            continue
        conteudo = await arquivo.read()
        if not conteudo or len(conteudo) > MAX_IMG_BYTES:
            continue
        mime = arquivo.content_type or "image/png"
        if mime not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            continue
        imgs.append((mime, conteudo))

    colados = [t for t in (posts_texto or "").split("\n---\n") if t.strip()]

    if not (perfil_texto or metricas or colados or imgs):
        raise HTTPException(
            422,
            "Envie ao menos o PDF do seu perfil ou a planilha de análises do LinkedIn.",
        )

    try:
        return rodar_auditoria(
            db, user,
            perfil_texto=perfil_texto,
            metricas=metricas,
            posts_colados=colados,
            imagens=imgs or None,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(502, f"A auditoria falhou: {exc}")
