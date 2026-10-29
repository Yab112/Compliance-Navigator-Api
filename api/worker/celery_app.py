from celery import Celery

from config.config import settings

celery_app = Celery(
    "compliance_navigator",
    broker=settings.broker_url,
    backend=settings.result_backend_url,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Addis_Ababa",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 30,
    worker_prefetch_multiplier=1,
)

# Nightly MESOB refresh and stale check (run `celery -A worker.celery_app beat` alongside the worker)
celery_app.conf.beat_schedule = {
    "mesob-nightly": {
        "task": "worker.tasks.scrape_government_source",
        "schedule": 60 * 60 * 24,
        "args": ("mesob",),
    },
    "stale-check-daily": {
        "task": "worker.tasks.flag_stale_graph_nodes",
        "schedule": 60 * 60 * 24,
    },
}
