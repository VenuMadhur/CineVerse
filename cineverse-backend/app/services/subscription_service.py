"""
Business logic for Subscription lifecycle management: create, change
plan, pause, resume, cancel. Orchestrates the state machine, billing
cycle engine, and audit logging within a single DB transaction per
operation.

Module 2 additions: `change_plan` now applies mid-cycle proration
(via ProrationService + InvoiceService) when the subscription is
active, and `preview_proration` lets a caller calculate the effect of
a plan change without applying it. Immediate cancellation of an
active, already-paid subscription now automatically refunds the
unused portion of the current billing cycle (via RefundService).

Phase 1D: every public method accepts an optional `requesting_user`
and enforces that a non-admin may only act on subscriptions belonging
to their own linked Customer (see app/services/ownership.py). A
`requesting_user=None` (the default) means "no enforcement context" --
used by internal callers, none of which currently call into this
service that way, but kept consistent with the rest of the codebase's
ownership-enforcement pattern.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions.custom_exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.enums import (
    AuditEventType,
    CancellationType,
    PlanStatus,
    SubscriptionStatus,
)
from app.models.subscription import Subscription, SubscriptionStatusHistory
from app.models.user import User
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionCancel, SubscriptionCreate
from app.services.audit_log_service import AuditLogService
from app.services.billing_cycle_service import BillingCycleService
from app.services.invoice_service import InvoiceService
from app.services.notification_dispatch import notify
from app.services.ownership import assert_owns_customer, effective_customer_filter, resolve_own_customer_id
from app.services.proration_service import ProrationCalculation, ProrationService
from app.services.refund_service import RefundService
from app.services.subscription_state_machine import SubscriptionStateMachine


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SubscriptionRepository(db)
        self.plan_repository = PlanRepository(db)
        self.customer_repository = CustomerRepository(db)
        self.audit_service = AuditLogService(db)
        self.billing_cycle_service = BillingCycleService(db)
        self.invoice_service = InvoiceService(db)
        self.refund_service = RefundService(db)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _transition(
        self,
        subscription: Subscription,
        target_status: SubscriptionStatus,
        reason: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> None:
        SubscriptionStateMachine.assert_valid_transition(
            subscription.status, target_status
        )
        previous_status = subscription.status
        subscription.status = target_status

        now = datetime.now(timezone.utc)
        if target_status == SubscriptionStatus.ACTIVE and subscription.activated_at is None:
            subscription.activated_at = now
        elif target_status == SubscriptionStatus.ACTIVE:
            # Re-activation from past_due or paused also stamps activated_at
            subscription.activated_at = now
        elif target_status == SubscriptionStatus.PAST_DUE:
            subscription.past_due_at = now
        elif target_status == SubscriptionStatus.PAUSED:
            subscription.paused_at = now
        elif target_status == SubscriptionStatus.CANCELLED:
            subscription.cancelled_at = now

        self.db.flush()

        history = SubscriptionStatusHistory(
            subscription_id=subscription.id,
            from_status=previous_status,
            to_status=target_status,
            reason=reason,
        )
        self.repository.add_status_history(history)

        # Module 3, Phase 4: reuses this single central transition
        # point (every subscription status change already passes
        # through here) rather than duplicating this check in every
        # public method that could move a subscription out of trial
        # (activate, cancel-during-trial, the billing scheduler's
        # auto-activation).
        if previous_status == SubscriptionStatus.TRIAL and target_status != SubscriptionStatus.TRIAL:
            self.audit_service.record(
                event_type=AuditEventType.TRIAL_ENDED,
                entity_type="subscription",
                entity_id=subscription.id,
                description=f"Trial ended (transitioned to {target_status.value})",
                actor_id=actor_id,
                old_value=previous_status.value,
                new_value=target_status.value,
            )

        self.audit_service.record(
            event_type=AuditEventType.STATUS_CHANGED,
            entity_type="subscription",
            entity_id=subscription.id,
            description=(
                f"Subscription status changed from {previous_status.value} "
                f"to {target_status.value}"
            ),
            actor_id=actor_id,
            metadata={"reason": reason} if reason else None,
        )

    def _get_subscription_or_404(
        self, subscription_id: uuid.UUID, requesting_user: Optional[User] = None, for_update: bool = False
    ) -> Subscription:
        subscription = (
            self.repository.get_by_id_for_update(subscription_id)
            if for_update
            else self.repository.get_by_id(subscription_id)
        )
        if subscription is None:
            raise NotFoundException(f"Subscription {subscription_id} not found")
        assert_owns_customer(subscription.customer_id, requesting_user, self.db)
        return subscription

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------
    def create_subscription(
        self,
        payload: SubscriptionCreate,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Subscription:
        if requesting_user is not None and not requesting_user.is_superuser:
            own_customer_id = resolve_own_customer_id(self.db, requesting_user)
            if own_customer_id is None or payload.customer_id != own_customer_id:
                raise ForbiddenException(
                    "You can only create a subscription for your own customer record"
                )

        plan = self.plan_repository.get_by_id(payload.plan_id)
        if plan is None:
            raise NotFoundException(f"Plan {payload.plan_id} not found")
        if plan.status == PlanStatus.ARCHIVED:
            raise ConflictException("Cannot subscribe to an archived plan")

        now = datetime.now(timezone.utc)
        # Issue 2 fix: a plan with no trial period should never pass
        # through TRIAL status at all -- previously every subscription
        # started in TRIAL unconditionally, even with
        # trial_period_days=0, which only ever produced a zero-length
        # trial rather than genuinely skipping it. trial_started_at/
        # trial_ends_at are still populated the same way as before (see
        # the comment on create_initial_cycle for why cycle_start
        # depends on trial_ends_at) -- only the subscription's actual
        # status, and activated_at, change.
        skips_trial = plan.trial_period_days <= 0
        initial_status = SubscriptionStatus.ACTIVE if skips_trial else SubscriptionStatus.TRIAL

        subscription = Subscription(
            customer_id=payload.customer_id,
            plan_id=payload.plan_id,
            status=initial_status,
            trial_started_at=now,
            trial_ends_at=(
                now + timedelta(days=plan.trial_period_days)
                if plan.trial_period_days > 0
                else now
            ),
            activated_at=now if skips_trial else None,
        )
        subscription = self.repository.add(subscription)

        history = SubscriptionStatusHistory(
            subscription_id=subscription.id,
            from_status=None,
            to_status=initial_status,
            reason="Subscription created" if skips_trial else "Subscription created (trial)",
        )
        self.repository.add_status_history(history)

        # Initial billing cycle starts at the end of the trial (or now,
        # if there is no trial period).
        cycle_start = subscription.trial_ends_at or now
        self.billing_cycle_service.create_initial_cycle(
            subscription_id=subscription.id,
            billing_interval=plan.billing_interval,
            start_date=cycle_start,
            actor_id=actor_id,
        )

        self.audit_service.record(
            event_type=AuditEventType.SUBSCRIPTION_CREATED,
            entity_type="subscription",
            entity_id=subscription.id,
            description="Subscription created",
            actor_id=actor_id,
            metadata={
                "customer_id": str(payload.customer_id),
                "plan_id": str(payload.plan_id),
                "trial_period_days": plan.trial_period_days,
            },
        )
        # Module 3, Phase 4: fires alongside (not instead of) the
        # existing SUBSCRIPTION_CREATED above -- distinguishes "a
        # subscription record was created" from "a trial period
        # actually began," only when the plan has a genuine trial
        # period. This condition doesn't need to change alongside the
        # Issue 2 fix above (subscriptions with trial_period_days=0 now
        # start ACTIVE, not TRIAL) -- it already correctly keyed off the
        # plan's configured trial length rather than subscription.status,
        # so it continues to fire only for genuine trials.
        if plan.trial_period_days > 0:
            self.audit_service.record(
                event_type=AuditEventType.TRIAL_STARTED,
                entity_type="subscription",
                entity_id=subscription.id,
                description=f"Trial started, ending {subscription.trial_ends_at.strftime('%Y-%m-%d')}",
                actor_id=actor_id,
            )

        self.db.commit()
        self.db.refresh(subscription)
        # Issue 2 fix: a plan with no trial period genuinely has no
        # trial to announce -- "subscription_started" always claims
        # "your free trial is active" (see notification_service.py),
        # which would now directly contradict the subscription's real
        # (ACTIVE, not TRIAL) status. Reuses the existing
        # "subscription_activated" event/template instead, exactly as
        # already used elsewhere for a genuine activation.
        if skips_trial:
            notify(
                "subscription_activated",
                payload.customer_id,
                {"plan_name": plan.name},
            )
        else:
            notify(
                "subscription_started",
                payload.customer_id,
                {
                    "plan_name": plan.name,
                    "trial_ends_at": subscription.trial_ends_at.strftime("%Y-%m-%d")
                    if subscription.trial_ends_at
                    else None,
                },
            )
        return subscription

    def activate_subscription(
        self,
        subscription_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Subscription:

        subscription = self._get_subscription_or_404(
            subscription_id,
            requesting_user,
        )

        self._transition(
            subscription,
            SubscriptionStatus.ACTIVE,
            "Manually activated",
            actor_id,
        )

        plan = self.plan_repository.get_by_id(subscription.plan_id)
        customer = self.customer_repository.get_by_id(subscription.customer_id)
        cycle = self.billing_cycle_service.get_current_cycle(subscription.id)

        if plan and customer and cycle and not cycle.is_billed:
            self.invoice_service.generate_billing_invoice(
                subscription=subscription,
                plan=plan,
                customer=customer,
                cycle=cycle,
            )

        self.db.commit()
        self.db.refresh(subscription)

        notify(
            "subscription_activated",
            subscription.customer_id,
            {
                "plan_name": plan.name if plan else None
            },
        )

        return subscription

    def preview_proration(
        self,
        subscription_id: uuid.UUID,
        new_plan_id: uuid.UUID,
        requesting_user: Optional[User] = None,
    ) -> ProrationCalculation:
        """
        Calculates (without applying) the proration effect of moving
        `subscription_id` to `new_plan_id` right now. Read-only.
        """
        subscription = self._get_subscription_or_404(subscription_id, requesting_user)
        new_plan = self.plan_repository.get_by_id(new_plan_id)
        if new_plan is None:
            raise NotFoundException(f"Plan {new_plan_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE:
            return ProrationCalculation(
                applicable=False,
                reason=(
                    "Proration only applies to active subscriptions "
                    f"(subscription is '{subscription.status.value}')"
                ),
            )

        old_plan = self.plan_repository.get_by_id(subscription.plan_id)
        cycle = self.billing_cycle_service.get_current_cycle(subscription.id)
        if cycle is None or cycle.is_billed:
            return ProrationCalculation(
                applicable=False,
                reason="No in-progress billing cycle to prorate against",
            )

        return ProrationService.calculate(
            old_plan_price=old_plan.price,
            new_plan_price=new_plan.price,
            cycle_start=cycle.cycle_start_date,
            cycle_end=cycle.cycle_end_date,
            as_of=datetime.now(timezone.utc),
        )

    def change_plan(
        self,
        subscription_id: uuid.UUID,
        new_plan_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Tuple[Subscription, Optional[ProrationCalculation]]:
        subscription = self._get_subscription_or_404(subscription_id, requesting_user)
        if subscription.status == SubscriptionStatus.CANCELLED:
            raise ConflictException("Cannot change the plan of a cancelled subscription")

        old_plan = self.plan_repository.get_by_id(subscription.plan_id)
        new_plan = self.plan_repository.get_by_id(new_plan_id)
        if new_plan is None:
            raise NotFoundException(f"Plan {new_plan_id} not found")
        if new_plan.status == PlanStatus.ARCHIVED:
            raise ConflictException("Cannot move a subscription to an archived plan")

        # Apply proration only for mid-cycle plan changes on an active
        # (already billing) subscription with an in-progress, unbilled
        # cycle. Trial/paused/past_due changes simply swap the plan;
        # the next invoice will use the new plan's price.
        proration_calc: Optional[ProrationCalculation] = None
        if subscription.status == SubscriptionStatus.ACTIVE:
            cycle = self.billing_cycle_service.get_current_cycle(subscription.id)
            if cycle is not None and not cycle.is_billed:
                calc = ProrationService.calculate(
                    old_plan_price=old_plan.price,
                    new_plan_price=new_plan.price,
                    cycle_start=cycle.cycle_start_date,
                    cycle_end=cycle.cycle_end_date,
                    as_of=datetime.now(timezone.utc),
                )
                if calc.applicable:
                    customer = self.customer_repository.get_by_id(subscription.customer_id)
                    self.invoice_service.generate_proration_invoice(
                        subscription=subscription,
                        customer=customer,
                        old_plan=old_plan,
                        new_plan=new_plan,
                        cycle=cycle,
                        calculation=calc,
                    )
                proration_calc = calc

        old_plan_id = subscription.plan_id
        subscription.plan_id = new_plan_id
        self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.SUBSCRIPTION_PLAN_CHANGED,
            entity_type="subscription",
            entity_id=subscription.id,
            description="Subscription plan changed",
            actor_id=actor_id,
            metadata={
                "old_plan_id": str(old_plan_id),
                "new_plan_id": str(new_plan_id),
            },
        )
        self.db.commit()
        self.db.refresh(subscription)
        notify(
            "plan_changed",
            subscription.customer_id,
            {
                "direction": "upgraded" if new_plan.price > old_plan.price else "downgraded",
                "old_plan_name": old_plan.name,
                "new_plan_name": new_plan.name,
            },
        )
        return subscription, proration_calc

    def pause_subscription(
        self,
        subscription_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Subscription:
        subscription = self._get_subscription_or_404(subscription_id, requesting_user)
        self._transition(
            subscription, SubscriptionStatus.PAUSED, "Subscription paused", actor_id
        )
        self.audit_service.record(
            event_type=AuditEventType.SUBSCRIPTION_PAUSED,
            entity_type="subscription",
            entity_id=subscription.id,
            description="Subscription paused",
            actor_id=actor_id,
        )
        self.db.commit()
        self.db.refresh(subscription)
        plan = self.plan_repository.get_by_id(subscription.plan_id)
        notify(
            "subscription_paused",
            subscription.customer_id,
            {"plan_name": plan.name if plan else None},
        )
        return subscription

    def undo_scheduled_cancellation(
        self,
        subscription_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Subscription:
        """
        QA-confirmed fix (Finding #8): reverses a not-yet-executed
        "cancel at end of billing cycle" request. Only ever touches
        `cancel_at_period_end`/`cancellation_type` -- the subscription's
        `status` never actually changed for this cancellation type (it
        stays active/trial/paused until the billing scheduler acts on
        the flag), so this is a flag reset, not a state-machine
        transition, and reuses none of resume_subscription's
        pause-reversal logic (which is unrelated and must stay exactly
        as already verified).
        """
        subscription = self._get_subscription_or_404(subscription_id, requesting_user)

        if not subscription.cancel_at_period_end:
            raise ConflictException("This subscription has no scheduled cancellation to undo")

        subscription.cancel_at_period_end = False
        subscription.cancellation_type = None
        self.audit_service.record(
            event_type=AuditEventType.SUBSCRIPTION_CANCELLATION_UNDONE,
            entity_type="subscription",
            entity_id=subscription.id,
            description="Scheduled end-of-cycle cancellation undone",
            actor_id=actor_id,
        )
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def resume_subscription(
        self,
        subscription_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Subscription:
        subscription = self._get_subscription_or_404(subscription_id, requesting_user)
        self._transition(
            subscription, SubscriptionStatus.ACTIVE, "Subscription resumed", actor_id
        )
        subscription.paused_at = None
        self.audit_service.record(
            event_type=AuditEventType.SUBSCRIPTION_RESUMED,
            entity_type="subscription",
            entity_id=subscription.id,
            description="Subscription resumed",
            actor_id=actor_id,
        )
        self.db.commit()
        self.db.refresh(subscription)
        plan = self.plan_repository.get_by_id(subscription.plan_id)
        notify(
            "subscription_resumed",
            subscription.customer_id,
            {"plan_name": plan.name if plan else None},
        )
        return subscription

    def cancel_subscription(
        self,
        subscription_id: uuid.UUID,
        payload: SubscriptionCancel,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Subscription:
        subscription = self._get_subscription_or_404(subscription_id, requesting_user, for_update=True)
        previous_status = subscription.status

        if payload.cancellation_type == CancellationType.IMMEDIATE:
            plan = self.plan_repository.get_by_id(subscription.plan_id)

            self._transition(
                subscription,
                SubscriptionStatus.CANCELLED,
                payload.reason or "Immediate cancellation",
                actor_id,
            )
            subscription.cancellation_type = CancellationType.IMMEDIATE

            # If the subscription had already been paying (active, not
            # trial), refund the unused portion of the current cycle.
            # No-op if there's no paid invoice to refund against (e.g.
            # cancelling during trial, before any charge occurred).
            if previous_status == SubscriptionStatus.ACTIVE:
                self.refund_service.refund_unused_period_on_cancellation(
                    subscription=subscription, plan=plan, actor_id=actor_id
                )
        else:
            # End-of-cycle cancellation: subscription stays in its current
            # status but is flagged so the billing scheduler cancels it
            # once the current billing cycle completes instead of renewing.
            if subscription.status == SubscriptionStatus.CANCELLED:
                raise ConflictException("Subscription is already cancelled")
            subscription.cancel_at_period_end = True
            subscription.cancellation_type = CancellationType.END_OF_CYCLE
            self.db.flush()

        self.audit_service.record(
            event_type=AuditEventType.SUBSCRIPTION_CANCELLED,
            entity_type="subscription",
            entity_id=subscription.id,
            description=f"Subscription cancellation requested ({payload.cancellation_type.value})",
            actor_id=actor_id,
            metadata={"reason": payload.reason} if payload.reason else None,
        )
        self.db.commit()
        self.db.refresh(subscription)
        plan = self.plan_repository.get_by_id(subscription.plan_id)
        notify(
            "subscription_cancelled",
            subscription.customer_id,
            {"plan_name": plan.name if plan else None},
        )
        return subscription

    def get_subscription(
        self, subscription_id: uuid.UUID, requesting_user: Optional[User] = None
    ) -> Subscription:
        return self._get_subscription_or_404(subscription_id, requesting_user)

    def list_subscriptions(
        self,
        status: Optional[SubscriptionStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
        requesting_user: Optional[User] = None,
    ) -> List[Subscription]:
        effective_customer_id = effective_customer_filter(customer_id, requesting_user, self.db)
        return self.repository.list_all(status, effective_customer_id, skip, limit)

    def count_subscriptions(
        self,
        status: Optional[SubscriptionStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> int:
        effective_customer_id = effective_customer_filter(customer_id, requesting_user, self.db)
        return self.repository.count_all(status, effective_customer_id)
