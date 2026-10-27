"""
Business logic for Plan management: create, update, archive, and
retrieve subscription plans.
"""
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.exceptions.custom_exceptions import ConflictException, NotFoundException
from app.models.enums import AuditEventType, PlanStatus
from app.models.plan import Plan
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanCreate, PlanUpdate
from app.services.audit_log_service import AuditLogService


class PlanService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PlanRepository(db)
        self.audit_service = AuditLogService(db)

    def create_plan(self, payload: PlanCreate, actor_id: Optional[uuid.UUID] = None) -> Plan:
        existing = self.repository.get_by_name(payload.name)
        if existing is not None:
            raise ConflictException(f"A plan named '{payload.name}' already exists")

        plan = Plan(
            name=payload.name,
            description=payload.description,
            price=payload.price,
            currency=payload.currency,
            billing_interval=payload.billing_interval,
            trial_period_days=payload.trial_period_days,
            feature_entitlements=payload.feature_entitlements,
            status=PlanStatus.ACTIVE,
        )
        plan = self.repository.add(plan)

        self.audit_service.record(
            event_type=AuditEventType.PLAN_CREATED,
            entity_type="plan",
            entity_id=plan.id,
            description=f"Plan '{plan.name}' created",
            actor_id=actor_id,
            metadata={"price": str(plan.price), "billing_interval": plan.billing_interval.value},
        )
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update_plan(
        self, plan_id: uuid.UUID, payload: PlanUpdate, actor_id: Optional[uuid.UUID] = None
    ) -> Plan:
        plan = self._get_plan_or_404(plan_id)

        update_data = payload.model_dump(exclude_unset=True)
        changed_fields = {}
        old_values = {}
        for field, value in update_data.items():
            current = getattr(plan, field)
            if current != value:
                changed_fields[field] = value
                old_values[field] = current
                setattr(plan, field, value)

        if changed_fields:
            self.db.flush()
            self.audit_service.record(
                event_type=AuditEventType.PLAN_UPDATED,
                entity_type="plan",
                entity_id=plan.id,
                description=f"Plan '{plan.name}' updated",
                actor_id=actor_id,
                metadata={"changed_fields": list(changed_fields.keys())},
                old_value=str(old_values),
                new_value=str(changed_fields),
            )
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def archive_plan(self, plan_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> Plan:
        plan = self._get_plan_or_404(plan_id)
        if plan.status == PlanStatus.ARCHIVED:
            raise ConflictException("Plan is already archived")

        plan.status = PlanStatus.ARCHIVED
        self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.PLAN_ARCHIVED,
            entity_type="plan",
            entity_id=plan.id,
            description=f"Plan '{plan.name}' archived",
            actor_id=actor_id,
        )
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def unarchive_plan(self, plan_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> Plan:
        """
        Restores an archived plan so it's offered to new customers
        again (GET /plans?status=active, already used by the customer
        Plans page, picks it back up automatically -- no other change
        needed). All historical data is untouched; this only ever
        flips `status`.
        """
        plan = self._get_plan_or_404(plan_id)
        if plan.status == PlanStatus.ACTIVE:
            raise ConflictException("Plan is already active")

        plan.status = PlanStatus.ACTIVE
        self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.PLAN_UNARCHIVED,
            entity_type="plan",
            entity_id=plan.id,
            description=f"Plan '{plan.name}' unarchived",
            actor_id=actor_id,
        )
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete_plan(self, plan_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None) -> None:
        """
        Permanently deletes a plan. Only allowed when genuinely safe:
        zero subscriptions -- of any status, not just active -- have
        ever been created against it. Since every invoice, payment,
        and refund is tied to a subscription (never directly to a
        plan), this single check transitively guarantees none of that
        historical data exists either. Subscription.plan_id also has
        an ondelete="RESTRICT" foreign key as a database-level backstop;
        this check exists so the admin gets a clear, actionable message
        instead of a raw integrity error.
        """
        plan = self._get_plan_or_404(plan_id)
        subscription_count = self.repository.count_subscriptions_for_plan(plan_id)
        if subscription_count > 0:
            raise ConflictException(
                f"Cannot delete plan '{plan.name}': {subscription_count} subscription(s) "
                "have used it. Archive it instead to hide it from new customers."
            )

        plan_name = plan.name
        self.audit_service.record(
            event_type=AuditEventType.PLAN_DELETED,
            entity_type="plan",
            entity_id=plan.id,
            description=f"Plan '{plan_name}' deleted",
            actor_id=actor_id,
        )
        self.repository.delete(plan)
        self.db.commit()

    def get_plan(self, plan_id: uuid.UUID) -> Plan:
        return self._get_plan_or_404(plan_id)

    def list_plans(
        self, status: Optional[PlanStatus] = None, skip: int = 0, limit: int = 100
    ) -> List[Plan]:
        return self.repository.list_by_status(status, skip, limit)

    def count_plans(self, status: Optional[PlanStatus] = None) -> int:
        return self.repository.count_by_status(status)

    def _get_plan_or_404(self, plan_id: uuid.UUID) -> Plan:
        plan = self.repository.get_by_id(plan_id)
        if plan is None:
            raise NotFoundException(f"Plan {plan_id} not found")
        return plan
