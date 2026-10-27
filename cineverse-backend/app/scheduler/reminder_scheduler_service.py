"""
Trial-Ending & Renewal Reminder Scheduler (Phase 6B).

Executed periodically by Celery Beat, alongside (but separately from)
the existing billing scheduler. Finds subscriptions whose trial is
about to end, or whose next billing cycle is about to renew, and
sends a reminder email for each -- deduped via the audit log (an
audit entry is recorded the moment a reminder is sent, and checked
before sending another) rather than a new "last_reminded_at" column,
so no schema change beyond the two new AuditEventType values was
needed.

Kept as a plain service (not a Celery task itself), matching
BillingSchedulerService, so it can be unit tested without a running
Celery worker.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.models.enums import AuditEventType
from app.repositories.billing_cycle_repository import BillingCycleRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.audit_log_service import AuditLogService
from app.services.notification_dispatch import notify

logger = get_logger(__name__)


class ReminderSchedulerService:
    def __init__(self, db: Session):
        self.db = db
        self.subscription_repository = SubscriptionRepository(db)
        self.billing_cycle_repository = BillingCycleRepository(db)
        self.plan_repository = PlanRepository(db)
        self.audit_service = AuditLogService(db)

    def run(self, as_of: datetime | None = None) -> dict:
        """Executes one full reminder pass. Returns a summary dict."""
        as_of = as_of or datetime.now(timezone.utc)
        trial_reminders_sent = self._send_trial_ending_reminders(as_of)
        renewal_reminders_sent = self._send_renewal_reminders(as_of)

        summary = {
            "as_of": as_of.isoformat(),
            "trial_reminders_sent": trial_reminders_sent,
            "renewal_reminders_sent": renewal_reminders_sent,
        }
        logger.info("Reminder scheduler run complete: %s", summary)
        return summary

    def _send_trial_ending_reminders(self, as_of: datetime) -> int:
        window_end = as_of + timedelta(days=settings.TRIAL_ENDING_REMINDER_DAYS)
        candidates = self.subscription_repository.list_trial_ending_within(as_of, window_end)

        sent = 0
        for subscription in candidates:
            if self.audit_service.has_event(
                "subscription", subscription.id, AuditEventType.TRIAL_ENDING_REMINDER_SENT
            ):
                continue

            plan = self.plan_repository.get_by_id(subscription.plan_id)
            notify(
                "trial_ending_reminder",
                subscription.customer_id,
                {
                    "plan_name": plan.name if plan else None,
                    "trial_ends_at": subscription.trial_ends_at.strftime("%Y-%m-%d")
                    if subscription.trial_ends_at
                    else None,
                },
            )
            self.audit_service.record(
                event_type=AuditEventType.TRIAL_ENDING_REMINDER_SENT,
                entity_type="subscription",
                entity_id=subscription.id,
                description="Trial-ending reminder email sent",
            )
            sent += 1

        if sent:
            self.db.commit()
        return sent

    def _send_renewal_reminders(self, as_of: datetime) -> int:
        window_end = as_of + timedelta(days=settings.RENEWAL_REMINDER_DAYS)
        candidates = self.billing_cycle_repository.list_upcoming_within(as_of, window_end)

        sent = 0
        for cycle in candidates:
            subscription = self.subscription_repository.get_by_id(cycle.subscription_id)
            if subscription is None:
                continue
            if self.audit_service.has_event(
                "subscription", subscription.id, AuditEventType.RENEWAL_REMINDER_SENT
            ):
                continue

            plan = self.plan_repository.get_by_id(subscription.plan_id)
            notify(
                "renewal_reminder",
                subscription.customer_id,
                {
                    "plan_name": plan.name if plan else None,
                    "renewal_date": cycle.next_billing_date.strftime("%Y-%m-%d"),
                    "amount": str(plan.price) if plan else None,
                    "currency": plan.currency if plan else None,
                },
            )
            self.audit_service.record(
                event_type=AuditEventType.RENEWAL_REMINDER_SENT,
                entity_type="subscription",
                entity_id=subscription.id,
                description="Renewal reminder email sent",
            )
            sent += 1

        if sent:
            self.db.commit()
        return sent
