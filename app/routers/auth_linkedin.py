"""Fluxo OAuth 3-legged do LinkedIn.

GET /auth/linkedin/login    -> redireciona para o consent screen
GET /auth/linkedin/callback -> troca code por tokens, resolve person URN e persiste

`state` carrega o user_id assinado (evita CSRF e vincula o callback ao tenant).
"""
import hashlib
import hmac
import uuid as uuidlib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import LinkedInAccount, User
from app.security import encrypt, get_current_user
from app.services import linkedin_client as li

router = APIRouter(prefix="/auth/linkedin", tags=["oauth"])


def _sign(value: str) -> str:
    key = get_settings().SECRET_KEY.encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:32]


@router.get("/login")
def login(user: User = Depends(get_current_user)):
    state = f"{user.id}.{_sign(str(user.id))}"
    return {"authorize_url": li.build_authorize_url(state)}


@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    try:
        user_id, sig = state.rsplit(".", 1)
    except ValueError:
        raise HTTPException(400, "state malformado")
    if not hmac.compare_digest(sig, _sign(user_id)):
        raise HTTPException(400, "state inválido")

    data = li.exchange_code(code)
    info = li.get_userinfo(data["access_token"])
    access_exp, refresh_exp = li.tokens_to_expiry(data)

    person_urn = f"urn:li:person:{info['sub']}"
    account = (
        db.query(LinkedInAccount)
        .filter_by(user_id=uuidlib.UUID(user_id), person_urn=person_urn)
        .first()
    )
    if not account:
        account = LinkedInAccount(user_id=uuidlib.UUID(user_id), person_urn=person_urn)
        db.add(account)

    account.display_name = info.get("name")
    account.access_token_enc = encrypt(data["access_token"])
    account.access_expires_at = access_exp
    if data.get("refresh_token"):
        account.refresh_token_enc = encrypt(data["refresh_token"])
        account.refresh_expires_at = refresh_exp
    account.status = "active"
    db.commit()

    # Volta para o frontend (primeira origem configurada) com flag de sucesso
    frontend = get_settings().FRONTEND_ORIGINS.split(",")[0].strip()
    return RedirectResponse(url=f"{frontend}/?linkedin=connected")
