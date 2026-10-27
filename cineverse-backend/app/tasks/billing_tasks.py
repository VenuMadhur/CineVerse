"""
Celery tasks for billing automation.

`run_billing_cycle_scheduler` is invoked by Celery Beat on the
interval configured in app.tasks.celery_app.beat_schedule.
"""
from celery.utils.log import get_task_logger

from app.core.database import SessionLocal
from app.scheduler.billing_scheduler_service import BillingSchedulerService
from app.tasks.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.tasks.billing_tasks.run_billing_cycle_scheduler",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_billing_cycle_scheduler(self):
    """
    Scans all billing cycles due for renewal, generates draft
    invoices, advances billing cycles, and finalizes any pending
    end-of-cycle cancellations.
    """
    db = SessionLocal()
    try:
        scheduler = BillingSchedulerService(db)
        summary = scheduler.run()
        return summary
    except Exception as exc:  # noqa: BLE001
        logger.exception("Billing cycle scheduler run failed")
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
