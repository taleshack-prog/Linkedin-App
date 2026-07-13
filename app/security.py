"""Autenticação: JWT (e-mail/senha e Google) com transição do X-API-Key legado.

- Senhas: bcrypt (hash irreversível; nem o operador conhece a senha do usuário).
- Sessão: JWT HS256 assinado com SECRET_KEY, expira em JWT_EXPIRE_DAYS.
- Transição: get_current_user aceita `Authorization: Bearer <jwt>` OU o header
  legado `X-API-Key` — usuários antigos migram definindo senha em /auth/set-password.
- Tokens LinkedIn seguem criptografados (Fernet) em repouso.
"""
import hashlib
import uuid as uuidlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_settings().SECRET_KEY.encode())
    return _fernet


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ---------- Senha (bcrypt) ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# ---------- JWT ----------
def create_token(user_id) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=s.JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, s.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> str:
    """Retorna o user_id do token. Levanta HTTPException 401 se inválido/expirado."""
    try:
        payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sessão expirada — entre novamente")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")


# ---------- Dependência de auth (JWT ou API key legada) ----------
def get_current_user(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    from app.models import User

    user = None
    if authorization and authorization.lower().startswith("bearer "):
        user_id = decode_token(authorization.split(" ", 1)[1].strip())
        try:
            user = db.get(User, uuidlib.UUID(user_id))
        except ValueError:
            raise HTTPException(401, "Token inválido")
    elif x_api_key:
        user = (
            db.query(User)
            .filter(User.api_key_hash == hash_api_key(x_api_key), User.is_active.is_(True))
            .first()
        )

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return user
