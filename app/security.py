"""Criptografia de tokens LinkedIn em repouso + auth simples da API.

Tokens NUNCA são persistidos em texto puro (requisito de ToS do LinkedIn e LGPD).
"""
import hashlib

from cryptography.fernet import Fernet
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Instancia o Fernet apenas no primeiro uso (lazy).

    Evita que um simples `import app.security` exija todas as variáveis de
    ambiente — importante para testes e para ferramentas de introspecção.
    """
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


def get_current_user(x_api_key: str = Header(...), db: Session = Depends(get_db)):
    """Auth mínima por API key (suficiente para uso próprio).

    Para o SaaS: substituir por JWT/Clerk/Auth0 — o restante do código
    só depende de `user.id`, então a troca é isolada aqui.
    """
    from app.models import User

    user = (
        db.query(User)
        .filter(User.api_key_hash == hash_api_key(x_api_key), User.is_active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="API key inválida")
    return user
