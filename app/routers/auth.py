"""Autenticação de usuários: cadastro, login (senha e Google) e sessão.

Indicação (fase Stripe): ?ref=codigo no cadastro grava referred_by; o crédito
de meses só acontece quando o indicado vira assinante pago.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.security import (
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _new_referral_code(db: Session) -> str:
    while True:
        code = secrets.token_hex(5)  # 10 chars
        if not db.query(User).filter_by(referral_code=code).first():
            return code


def _resolve_referrer(db: Session, ref: str | None):
    if not ref:
        return None
    referrer = db.query(User).filter_by(referral_code=ref.strip().lower()).first()
    return referrer.id if referrer else None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=200)
    ref: str | None = Field(default=None, max_length=20)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleIn(BaseModel):
    credential: str  # ID token do Google Identity Services
    ref: str | None = Field(default=None, max_length=20)


class SetPasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    name: str | None
    plan: str
    referral_code: str | None
    has_password: bool = False


class TokenOut(BaseModel):
    token: str
    me: MeOut


def _me(user: User) -> MeOut:
    return MeOut(
        email=user.email,
        name=user.name,
        plan=user.plan,
        referral_code=user.referral_code,
        has_password=bool(user.password_hash),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Já existe uma conta com este e-mail — faça login")
    user = User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        referral_code=_new_referral_code(db),
        referred_by=_resolve_referrer(db, payload.ref),
    )
    db.add(user)
    db.commit()
    return TokenOut(token=create_token(user.id), me=_me(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email.lower().strip()).first()
    # Mensagem única para e-mail e senha errados (não revelar quais e-mails existem)
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "E-mail ou senha incorretos")
    if not user.is_active:
        raise HTTPException(403, "Conta desativada")
    return TokenOut(token=create_token(user.id), me=_me(user))


@router.post("/google", response_model=TokenOut)
def login_google(payload: GoogleIn, db: Session = Depends(get_db)):
    s = get_settings()
    if not s.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Login com Google não está configurado no servidor")

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        info = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), s.GOOGLE_CLIENT_ID
        )
    except Exception:  # noqa: BLE001 — token inválido/expirado/audience errada
        raise HTTPException(401, "Credencial do Google inválida")

    sub = info["sub"]
    email = (info.get("email") or "").lower().strip()
    if not email or not info.get("email_verified", False):
        raise HTTPException(401, "Conta Google sem e-mail verificado")

    user = db.query(User).filter_by(google_sub=sub).first()
    if not user:
        # Vincula por e-mail verificado (padrão de mercado) ou cria conta nova
        user = db.query(User).filter_by(email=email).first()
        if user:
            user.google_sub = sub
        else:
            user = User(
                email=email,
                name=info.get("name"),
                google_sub=sub,
                referral_code=_new_referral_code(db),
                referred_by=_resolve_referrer(db, payload.ref),
            )
            db.add(user)
        db.commit()
    if not user.is_active:
        raise HTTPException(403, "Conta desativada")
    return TokenOut(token=create_token(user.id), me=_me(user))


@router.post("/set-password", response_model=MeOut)
def set_password(
    payload: SetPasswordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Define/atualiza a senha do usuário logado (migração do X-API-Key legado
    ou troca de senha de quem entrou via Google)."""
    user.password_hash = hash_password(payload.password)
    if not user.referral_code:
        user.referral_code = _new_referral_code(db)
    db.commit()
    return _me(user)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return _me(user)
