"""
Celery task for the trial-ending / renewal reminder scheduler
(Phase 6B).

`run_reminder_scheduler` is invoked by Celery Beat on its own periodic
schedule, separate from (but alongside) the billing cycle scheduler.
"""
from celery.utils.log import get_task_logger

from app.core.database import SessionLocal
from app.scheduler.reminder_scheduler_service import ReminderSchedulerService
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.tasks.reminder_tasks.run_reminder_scheduler",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_reminder_scheduler(self):
    """
    Scans for subscriptions whose trial is ending soon or whose next
    billing cycle is renewing soon, and sends a reminder email for
    each -- deduped via the audit log so a subscription is never
    reminded twice for the same trial/cycle.
    """
    db = SessionLocal()
    try:
        scheduler = ReminderSchedulerService(db)
        summary = scheduler.run()
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.exception("Reminder scheduler run failed")
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
