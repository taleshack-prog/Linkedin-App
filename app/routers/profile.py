"""Perfil de marca do usuário — contexto injetado em toda geração de posts.

Um perfil por usuário (upsert via PUT). Todos os campos são opcionais:
quanto mais preenchido, mais direcionada a geração.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BrandProfile, User
from app.security import get_current_user

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
