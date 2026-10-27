"""
Celery application instance, configured with Redis as broker and
result backend, plus the Celery Beat schedule for the billing cycle
scheduler.
"""
from celery import Celery
from celery.schedules import crontab

from app.config.settings import settings

celery_app = Celery(
    "billing_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.billing_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.reminder_tasks",
        "app.tasks.retry_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 10,
    task_soft_time_limit=60 * 8,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
    # If the broker is briefly unreachable when a task is dispatched
    # synchronously from request-handling code (e.g. the notification
    # task fired from the payment webhook handler / refund service),
    # fail fast instead of retrying publish with backoff for several
    # seconds -- callers already treat dispatch failures as non-fatal
    # and log them, so a quick failure is preferable to blocking.
    task_publish_retry_policy={
        "max_retries": 1,
        "interval_start": 0,
        "interval_step": 0,
        "interval_max": 0,
    },
)

# ---------------------------------------------------------------------
# Celery Beat schedule
# ---------------------------------------------------------------------
celery_app.conf.beat_schedule = {
    "run-billing-cycle-scheduler": {
        "task": "app.tasks.billing_tasks.run_billing_cycle_scheduler",
        "schedule": settings.BILLING_SCHEDULER_INTERVAL_SECONDS,
    },
    "run-billing-cycle-scheduler-nightly": {
        "task": "app.tasks.billing_tasks.run_billing_cycle_scheduler",
        "schedule": crontab(hour=1, minute=0),
    },
    # Phase 6B: trial-ending / renewal reminders. Runs once daily --
    # unlike billing itself, reminders don't need to be checked every
    # few minutes, and the audit-log-based dedup means running it more
    # than once a day would just be wasted work, not a correctness risk.
    "run-reminder-scheduler": {
        "task": "app.tasks.reminder_tasks.run_reminder_scheduler",
        "schedule": crontab(hour=9, minute=0),
    },
    # Module 3, Phase 1b: processes due retry queue entries. Purely
    # event-driven -- only acts on RetryQueue rows that already exist
    # (created by PaymentWebhookHandlerService when a payment fails),
    # never scans Invoice/Payment tables for new failures.
    "run-retry-scheduler": {
        "task": "app.tasks.retry_tasks.run_retry_scheduler",
        "schedule": settings.RETRY_SCHEDULER_INTERVAL_SECONDS,
    },
}
