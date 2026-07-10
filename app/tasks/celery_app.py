from celery import Celery

from app.config import get_settings

s = get_settings()

celery = Celery("linkpost", broker=s.REDIS_URL, backend=s.REDIS_URL)
celery.conf.update(
    timezone="America/Sao_Paulo",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scan-due-posts": {
            "task": "app.tasks.publish_tasks.scan_due_posts",
            "schedule": s.PUBLISH_SCAN_INTERVAL_SECONDS,
        },
        "refresh-expiring-tokens": {
            "task": "app.tasks.publish_tasks.refresh_expiring_tokens",
            "schedule": 6 * 60 * 60,  # a cada 6h
        },
    },
)
celery.autodiscover_tasks(["app.tasks"])

# Garante registro das tasks quando o worker sobe
from app.tasks import publish_tasks, generation_tasks  # noqa: E402,F401
