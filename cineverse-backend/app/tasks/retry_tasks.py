"""
Celery task for the failed payment retry scheduler (Module 3, Phase 1b).

`run_retry_scheduler` is invoked by Celery Beat on its own periodic
schedule, separate from (but alongside) the billing and reminder
schedulers.
"""
from celery.utils.log import get_task_logger

from app.core.database import SessionLocal
from app.scheduler.retry_scheduler_service import RetrySchedulerService
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.tasks.retry_tasks.run_retry_scheduler",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_retry_scheduler(self):
    """
    Processes every RetryQueue entry whose scheduled_retry_date has
    arrived -- purely event-driven, never scans Invoice/Payment
    tables for new failures (those are enqueued elsewhere, by
    PaymentWebhookHandlerService right after a payment fails).
    """
    db = SessionLocal()
    try:
        scheduler = RetrySchedulerService(db)
        summary = scheduler.run()
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.exception("Retry scheduler run failed")
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
