"""Uso/quota de geração: quantos posts o usuário gerou no mês-calendário atual.

O teto é por plano (plans.max_posts). Contamos os posts pelo created_at no mês
corrente — reset automático na virada do mês, sem contador nem rotina de reset.
"""
from datetime import datetime, timezone

from sqlalchemy import func

from app.models import Post
from app.services.plans import max_posts_for


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def posts_used_this_month(db, user_id) -> int:
    """Nº de posts gerados pelo usuário no mês-calendário atual."""
    return (
        db.query(func.count(Post.id))
        .filter(Post.user_id == user_id, Post.created_at >= _month_start())
        .scalar()
        or 0
    )


def generation_quota(db, user) -> tuple[int, int, int]:
    """Retorna (usados, teto, restantes). teto e restantes = -1 quando ilimitado."""
    cap = max_posts_for(user)
    used = posts_used_this_month(db, user.id)
    if cap < 0:
        return used, -1, -1
    return used, cap, max(0, cap - used)
