"""Painel de saúde (admin). Métricas de geração e publicação computadas das
tabelas existentes — sem tabela nova. Acesso só para e-mails em ADMIN_EMAILS.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ContentBrief, Post, PostStatus, PublishLog
from app.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


def _redis_ok():
    try:
        import redis
        redis.from_url(get_settings().REDIS_URL, socket_connect_timeout=2).ping()
        return True
    except Exception:
        return False


@router.get("/health")
def health(db: Session = Depends(get_db), _=Depends(require_admin)):
    now = datetime.now(timezone.utc)
    day = now - timedelta(hours=24)
    week = now - timedelta(days=7)

    def cposts(*f): return db.query(func.count(Post.id)).filter(*f).scalar() or 0
    def cbriefs(*f): return db.query(func.count(ContentBrief.id)).filter(*f).scalar() or 0
    def clogs(*f): return db.query(func.count(PublishLog.id)).filter(*f).scalar() or 0

    stuck = cposts(Post.status == PostStatus.publishing)
    overdue = cposts(Post.status == PostStatus.approved, Post.publish_at.isnot(None), Post.publish_at < now)
    gen_failed_24h = cbriefs(ContentBrief.status == "failed", ContentBrief.created_at >= day)
    gen_ok_24h = cbriefs(ContentBrief.status == "generated", ContentBrief.created_at >= day)
    publish_failed_24h = clogs(PublishLog.success.is_(False), PublishLog.created_at >= day)
    credit_alert = cbriefs(ContentBrief.status == "failed", ContentBrief.error.ilike("%credit%"),
                           ContentBrief.created_at >= day)

    published_24h = cposts(Post.status == PostStatus.published, Post.published_at.isnot(None), Post.published_at >= day)
    published_7d = cposts(Post.status == PostStatus.published, Post.published_at.isnot(None), Post.published_at >= week)

    rows = db.query(Post.status, func.count(Post.id)).group_by(Post.status).all()
    queue = {(s.value if hasattr(s, "value") else str(s)): n for s, n in rows}

    gen_total = gen_ok_24h + gen_failed_24h
    gen_rate = round(gen_ok_24h / gen_total * 100) if gen_total else None

    recent_gen = [
        {"when": b.created_at.isoformat(), "theme": (b.theme or "")[:80], "error": (b.error or "")[:200]}
        for b in db.query(ContentBrief).filter(ContentBrief.status == "failed")
        .order_by(ContentBrief.created_at.desc()).limit(8).all()
    ]
    recent_pub = []
    for lg in (db.query(PublishLog).filter(PublishLog.success.is_(False))
               .order_by(PublishLog.created_at.desc()).limit(8).all()):
        body = ""
        if isinstance(lg.response, dict):
            body = str(lg.response.get("body") or lg.response)[:200]
        recent_pub.append({"when": lg.created_at.isoformat(), "http_status": lg.http_status, "error": body})

    alerts = []
    if stuck:
        alerts.append({"level": "high", "msg": f"{stuck} post(s) preso(s) em publicação — worker pode estar travado"})
    if overdue:
        alerts.append({"level": "high", "msg": f"{overdue} post(s) agendado(s) vencido(s) sem publicar"})
    if credit_alert:
        alerts.append({"level": "high", "msg": "Geração falhou por saldo baixo da Anthropic — recarregue os créditos"})
    if gen_failed_24h:
        alerts.append({"level": "medium", "msg": f"{gen_failed_24h} geração(ões) falharam nas últimas 24h"})
    if publish_failed_24h:
        alerts.append({"level": "medium", "msg": f"{publish_failed_24h} publicação(ões) falharam nas últimas 24h"})

    return {
        "generated_at": now.isoformat(),
        "alerts": alerts,
        "signals": {
            "stuck_publishing": stuck,
            "overdue_scheduled": overdue,
            "gen_failed_24h": gen_failed_24h,
            "publish_failed_24h": publish_failed_24h,
            "anthropic_credit_alert": bool(credit_alert),
        },
        "volume": {
            "published_24h": published_24h,
            "published_7d": published_7d,
            "gen_ok_24h": gen_ok_24h,
            "gen_failed_24h": gen_failed_24h,
            "gen_success_rate_pct": gen_rate,
        },
        "queue": queue,
        "services": {"postgres": True, "redis": _redis_ok()},
        "recent_failures": {"generation": recent_gen, "publishing": recent_pub},
    }
