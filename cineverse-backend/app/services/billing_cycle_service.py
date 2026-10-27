"""
Billing Cycle Engine.

Responsible for computing billing period boundaries and renewal
dates for monthly and annual plans, and for creating/advancing
BillingCycle records for a subscription.
"""
import calendar
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.billing_cycle import BillingCycle
from app.models.enums import AuditEventType, BillingInterval
from app.repositories.billing_cycle_repository import BillingCycleRepository
from app.services.audit_log_service import AuditLogService


def add_interval(start: datetime, interval: BillingInterval) -> datetime:
    """
    Add one billing interval to `start`, correctly handling month-end
    edge cases (e.g. Jan 31 + 1 month -> Feb 28/29).
    """
    if interval == BillingInterval.MONTHLY:
        month = start.month + 1
        year = start.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(start.day, last_day)
        return start.replace(year=year, month=month, day=day)

    if interval == BillingInterval.ANNUAL:
        year = start.year + 1
        last_day = calendar.monthrange(year, start.month)[1]
        day = min(start.day, last_day)
        return start.replace(year=year, day=day)

    raise ValueError(f"Unsupported billing interval: {interval}")


class BillingCycleService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BillingCycleRepository(db)
        self.audit_service = AuditLogService(db)

    def create_initial_cycle(
        self,
        subscription_id: uuid.UUID,
        billing_interval: BillingInterval,
        start_date: Optional[datetime] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> BillingCycle:
        """Creates the first billing cycle for a new subscription."""
        cycle_start = start_date or datetime.now(timezone.utc)
        cycle_end = add_interval(cycle_start, billing_interval)

        cycle = BillingCycle(
            subscription_id=subscription_id,
            cycle_start_date=cycle_start,
            cycle_end_date=cycle_end,
            renewal_date=cycle_end,
            # Bill in advance, at the start of the period being paid
            # for -- not cycle_end. A subscription is only ever
            # invoiced by the billing scheduler picking up a due
            # cycle (see BillingSchedulerService), so if this were
            # cycle_end, a brand-new subscriber would get a full,
            # silent extra billing period free (on top of any trial)
            # before ever being charged: exactly the "no invoice after
            # activation" symptom this was fixed for. cycle_end
            # remains the invoice's due_date (see
            # InvoiceService.generate_billing_invoice) -- the customer
            # is billed at the start of the period and has until its
            # end to pay, not billed only after the period is already
            # over.
            next_billing_date=cycle_start,
            is_billed=False,
        )
        cycle = self.repository.add(cycle)

        self.audit_service.record(
            event_type=AuditEventType.BILLING_CYCLE_CREATED,
            entity_type="subscription",
            entity_id=subscription_id,
            description="Initial billing cycle created",
            actor_id=actor_id,
            metadata={
                "cycle_start_date": cycle_start.isoformat(),
                "cycle_end_date": cycle_end.isoformat(),
                "billing_interval": billing_interval.value,
            },
        )
        return cycle

    def advance_cycle(
        self,
        subscription_id: uuid.UUID,
        billing_interval: BillingInterval,
        actor_id: Optional[uuid.UUID] = None,
    ) -> BillingCycle:
        """
        Marks the current cycle as billed and creates the next one,
        used by the Celery Beat renewal job after a successful charge.
        """
        current_cycle = self.repository.get_current_for_subscription(subscription_id)
        if current_cycle is not None:
            current_cycle.is_billed = True
            self.db.flush()
            new_start = current_cycle.cycle_end_date
        else:
            new_start = datetime.now(timezone.utc)

        new_end = add_interval(new_start, billing_interval)
        next_cycle = BillingCycle(
            subscription_id=subscription_id,
            cycle_start_date=new_start,
            cycle_end_date=new_end,
            renewal_date=new_end,
            # Same "bill in advance" fix as create_initial_cycle above
            # -- the next period is invoiced as soon as it starts, not
            # only once it's already over.
            next_billing_date=new_start,
            is_billed=False,
        )
        next_cycle = self.repository.add(next_cycle)

        self.audit_service.record(
            event_type=AuditEventType.BILLING_CYCLE_CREATED,
            entity_type="subscription",
            entity_id=subscription_id,
            description="Billing cycle advanced to next period",
            actor_id=actor_id,
            metadata={
                "cycle_start_date": new_start.isoformat(),
                "cycle_end_date": new_end.isoformat(),
            },
        )
        return next_cycle

    def get_current_cycle(self, subscription_id: uuid.UUID) -> Optional[BillingCycle]:
        return self.repository.get_current_for_subscription(subscription_id)

    def list_for_subscription(self, subscription_id: uuid.UUID) -> list[BillingCycle]:
        return self.repository.list_for_subscription(subscription_id)
