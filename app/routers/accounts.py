"""Contas LinkedIn conectadas do usuário (leitura).

O frontend precisa listar as contas para: (1) escolher a conta ao criar uma
pauta e (2) mostrar status do token (active / needs_reauth) e expiração.
Nunca expor tokens — nem criptografados.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LinkedInAccount, User
from app.security import get_current_user

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str | None
    person_urn: str
    status: str
    access_expires_at: datetime


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(LinkedInAccount)
        .filter_by(user_id=user.id)
        .order_by(LinkedInAccount.created_at.desc())
        .all()
    )
