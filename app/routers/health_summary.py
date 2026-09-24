"""GET /health/summary — saúde interna do Posthink para o painel Hack Tech Farm.

Protegida por MONITOR_TOKEN (Bearer, comparação em tempo constante). Roda os
checks em paralelo (timeout individual 2s), agrega o pior status, e responde
sempre 200 com o JSON — 5xx só se a própria rota quebrar. Sem segredos no corpo.
"""
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, Response
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LinkedInAccount, Post, PostStatus

router = APIRouter(prefix="/health", tags=["health"])

_s = get_settings()
# Engine dedicado, com timeout de conexão curto — para um banco fora não travar.
_check_engine = create_engine(
    _s.DATABASE_URL, connect_args={"connect_timeout": 2},
    pool_pre_ping=False, pool_size=2, max_overflow=2,
)

STUCK_MINUTES = 5
_REQUIRED_VARS = ["SECRET_KEY", "DATABASE_URL", "REDIS_URL",
                  "LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "ANTHROPIC_API_KEY"]

_cache = {"ts": 0.0, "data": None}
_lock = threading.Lock()


def _ck(name, status, detail=""):
    return {"name": name, "status": status, "detail": detail}


def check_banco():
    try:
        with _check_engine.connect() as c:
            c.execute(text("SELECT 1"))
        return _ck("banco", "ok", "responde")
    except Exception:
        return _ck("banco", "down", "SELECT 1 falhou")


def check_migracoes():
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    try:
        root = Path(__file__).resolve().parents[2]
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        heads = set(script.get_heads())
        total = len(list(script.walk_revisions()))
        with _check_engine.connect() as c:
            current = set(MigrationContext.configure(c).get_current_heads())
        if current == heads:
            return _ck("migracoes", "ok", f"{total}/{total} migrações")
        pending = list(script.iterate_revisions(tuple(heads), tuple(current)))
        first = pending[-1].revision if pending else "?"
        return _ck("migracoes", "down", f"{len(pending)} pendente(s), a partir de {first}")
    except Exception:
        return _ck("migracoes", "degraded", "não foi possível verificar migrações")


def check_redis():
    try:
        import redis
        redis.from_url(_s.REDIS_URL, socket_connect_timeout=2, socket_timeout=2).ping()
        return _ck("redis", "ok", "PING ok")
    except Exception:
        return _ck("redis", "down", "PING falhou")


def check_worker():
    try:
        from app.tasks.celery_app import celery
        pong = celery.control.ping(timeout=1.5) or []
        if pong:
            return _ck("worker", "ok", f"{len(pong)} worker(s)")
        return _ck("worker", "down", "nenhum worker respondeu")
    except Exception:
        return _ck("worker", "degraded", "não foi possível pingar o worker")


def check_beat():
    try:
        import redis
        raw = redis.from_url(_s.REDIS_URL, socket_connect_timeout=2, socket_timeout=2).get("posthink:hb:scan")
        if not raw:
            return _ck("beat", "down", "sem sinal do agendador")
        last = datetime.fromisoformat(raw.decode() if isinstance(raw, bytes) else raw)
        age = int((datetime.now(timezone.utc) - last).total_seconds())
        interval = getattr(_s, "PUBLISH_SCAN_INTERVAL_SECONDS", 60)
        if age <= interval * 3 + 30:
            return _ck("beat", "ok", f"último ciclo há {age}s")
        if age <= 600:
            return _ck("beat", "degraded", f"agendador atrasado ({age}s)")
        return _ck("beat", "down", f"agendador parado ({age}s)")
    except Exception:
        return _ck("beat", "degraded", "não foi possível verificar o agendador")


def check_fila():
    try:
        limit = datetime.now(timezone.utc) - timedelta(minutes=STUCK_MINUTES)
        with Session(bind=_check_engine) as db:
            n = db.query(func.count(Post.id)).filter(
                Post.status == PostStatus.publishing, Post.updated_at <= limit).scalar() or 0
        if n == 0:
            return _ck("fila", "ok", "nenhum post preso")
        return _ck("fila", "degraded", f"{n} post(s) preso(s) há +{STUCK_MINUTES}min")
    except Exception:
        return _ck("fila", "degraded", "não foi possível verificar a fila")


def check_linkedin():
    try:
        soon = datetime.now(timezone.utc) + timedelta(days=3)
        with Session(bind=_check_engine) as db:
            n = db.query(func.count(LinkedInAccount.id)).filter(
                (LinkedInAccount.status != "active") | (LinkedInAccount.access_expires_at <= soon)).scalar() or 0
        if n == 0:
            return _ck("linkedin", "ok", "credenciais ok")
        return _ck("linkedin", "degraded", f"{n} conta(s) p/ reautenticar ou expirando")
    except Exception:
        return _ck("linkedin", "degraded", "não foi possível verificar o LinkedIn")


def check_config():
    missing = [k for k in _REQUIRED_VARS if not getattr(_s, k, "")]
    if not missing:
        return _ck("config", "ok", f"{len(_REQUIRED_VARS)}/{len(_REQUIRED_VARS)} variáveis")
    return _ck("config", "down", "faltando: " + ", ".join(missing))


CHECKS = [
    ("banco", check_banco),
    ("migracoes", check_migracoes),
    ("redis", check_redis),
    ("worker", check_worker),
    ("beat", check_beat),
    ("fila", check_fila),
    ("linkedin", check_linkedin),
    ("config", check_config),
]


def _run_checks():
    ex = ThreadPoolExecutor(max_workers=len(CHECKS))
    futs = {name: ex.submit(fn) for name, fn in CHECKS}
    out = {}
    for name, fut in futs.items():
        try:
            out[name] = fut.result(timeout=2)
        except FuturesTimeout:
            out[name] = _ck(name, "degraded", "não respondeu em 2s")
        except Exception:
            out[name] = _ck(name, "down", "erro no check")
    ex.shutdown(wait=False)  # não bloqueia: respeita o orçamento de tempo do painel
    return [out[name] for name, _ in CHECKS]


def _compute():
    checks = _run_checks()
    worst = "ok"
    if any(c["status"] == "down" for c in checks):
        worst = "down"
    elif any(c["status"] == "degraded" for c in checks):
        worst = "degraded"
    detail = "; ".join(f'{c["name"]}: {c["detail"]}' for c in checks if c["status"] != "ok" and c["detail"])
    return {
        "app": "Posthink",
        "status": worst,
        "detail": detail,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": checks,
    }


def _cached():
    now = time.time()
    with _lock:
        if _cache["data"] is not None and now - _cache["ts"] < 30:
            return _cache["data"]
    data = _compute()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data


@router.get("/summary")
def summary(authorization: str | None = Header(default=None)):
    token = get_settings().MONITOR_TOKEN
    if not token:
        return Response(status_code=503)          # nunca liberar por omissão
    if not authorization or not authorization.startswith("Bearer "):
        return Response(status_code=401)          # sem corpo explicativo
    presented = authorization.split(" ", 1)[1]
    if not secrets.compare_digest(presented, token):
        return Response(status_code=401)
    return JSONResponse(_cached())
