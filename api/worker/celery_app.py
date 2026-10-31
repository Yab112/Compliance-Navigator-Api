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

# Nightly MESOB refresh, daily maintenance and due staff-added sources (run `celery -A worker.celery_app beat` alongside the worker)
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
    # Payouts approved and sent to Chapa, until Chapa says they landed or failed
    "payouts-processing-15min": {
        "task": "worker.tasks.check_processing_payouts",
        "schedule": 60 * 15,
    },
    # Paid transfers of the last 30 days that a bank sent back after Chapa said "success"
    "payouts-paid-daily": {
        "task": "worker.tasks.check_paid_payouts",
        "schedule": 60 * 60 * 24,
    },
    # Refunds whose gateway answer was lost, and checkouts whose webhook was lost
    "refunds-sending-15min": {
        "task": "worker.tasks.check_sending_refunds",
        "schedule": 60 * 15,
    },
    "payments-pending-15min": {
        "task": "worker.tasks.check_pending_payments",
        "schedule": 60 * 15,
    },
    # Staff-added sources with a daily or weekly schedule; each one runs only when it is due
    "custom-sources-hourly": {
        "task": "worker.tasks.run_scheduled_custom_sources",
        "schedule": 60 * 60,
    },
}
