from celery import Celery

import app.db.base  # noqa: F401 — registers all models so relationship() string refs resolve in this process
from app.core.config import settings

celery_app = Celery(
    "vulnscan",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
)

# Make sure task modules are registered with this app.
celery_app.autodiscover_tasks(["app.worker"])
