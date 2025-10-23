import logging

from celery import Celery
from celery.schedules import crontab

from config import settings

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "x_list_worker",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    include=["tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    result_expires=3600,  # 1 hour
    # Async support
    task_routes={
        "tasks.*": {"queue": "default"},
    },
    task_always_eager=False,
    task_eager_propagates=True,
)

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    "process-user-queue": {
        "task": "tasks.process_user_queue",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    "cleanup-expired-jobs": {
        "task": "tasks.cleanup_expired_jobs",
        "schedule": crontab(minute="0", hour="*/6"),  # Every 6 hours
    },
}

# Auto-discover tasks
celery_app.autodiscover_tasks()
