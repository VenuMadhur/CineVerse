"""
Shared ownership-enforcement helpers (Phase 1D).

Phase 1C added ownership enforcement for the `Customer` resource
itself. This module extends the same rule -- a non-admin may only
access resources belonging to their own linked Customer -- to every
resource that belongs to one: Subscriptions, Invoices, Payments, and
Refunds.

Two helpers cover the two shapes of endpoint in this codebase:
  * `assert_owns_customer` -- for single-resource GET/POST-by-ID
    endpoints: load the resource, then assert the caller owns the
    Customer it belongs to (or is an admin).
  * `effective_customer_filter` -- for list endpoints: a non-admin's
    results are always scoped to their own Customer, regardless of
    what `customer_id` they passed (or omitted). Admins get whatever
    filter they asked for, including none (= everyone).

A `requesting_user=None` means "no enforcement context" -- used by
internal service-to-service calls (invoice generation, the billing
scheduler, notifications) that aren't acting on behalf of a specific
API request and must remain unaffected by this module entirely.
"""
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions.custom_exceptions import ForbiddenException
from app.models.user import User
from app.repositories.customer_repository import CustomerRepository


def resolve_own_customer_id(db: Session, user: User) -> Optional[uuid.UUID]:
    """The Customer.id linked to this User, or None if unlinked."""
    customer = CustomerRepository(db).get_by_user_id(user.id)
    return customer.id if customer else None


def assert_owns_customer(
    resource_customer_id: uuid.UUID,
    requesting_user: Optional[User],
    db: Session,
) -> None:
    """
    Raises ForbiddenException unless `requesting_user` is a superuser
    or `resource_customer_id` matches their own linked Customer.
    """
    if requesting_user is None or requesting_user.is_superuser:
        return
    own_customer_id = resolve_own_customer_id(db, requesting_user)
    if own_customer_id is None or resource_customer_id != own_customer_id:
        raise ForbiddenException("You do not have access to this resource")


def effective_customer_filter(
    requested_customer_id: Optional[uuid.UUID],
    requesting_user: Optional[User],
    db: Session,
) -> Optional[uuid.UUID]:
    """
    For list endpoints. Superusers (or internal calls with no
    requesting_user) get whatever filter they asked for -- including
    None, meaning "everyone". Non-admins are always forced to their
    own linked Customer, regardless of what they passed.

    If a non-admin has no linked Customer yet, returns a random UUID
    that can never match any real row -- so the list is correctly
    empty rather than needing special-case "no customer" handling in
    every caller.
    """
    if requesting_user is None or requesting_user.is_superuser:
        return requested_customer_id
    own_id = resolve_own_customer_id(db, requesting_user)
    return own_id if own_id is not None else uuid.uuid4()


def assert_owns_audit_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    requesting_user: Optional[User],
    db: Session,
) -> None:
    """
    Final production review: GET /audit-logs/{entity_type}/{entity_id}
    predates Phase 1D and was never covered by it -- confirmed live
    that any authenticated non-admin could pass any other customer's
    subscription/invoice/payment/refund ID and see their private audit
    trail. This resolves the owning customer_id for whichever entity
    type was requested, then reuses assert_owns_customer exactly as
    every other resource does.

    `entity_type` values with no per-customer ownership concept (e.g.
    "plan", which is a global/shared resource, or anything unrecognized)
    fail closed -- admin only -- rather than guessing.
    """
    if requesting_user is None or requesting_user.is_superuser:
        return

    if entity_type == "plan":
        # Plans are public data -- GET /plans and GET /plans/{id} need
        # no authentication at all -- so their audit trail (e.g. "when
        # was the price last changed") isn't customer-sensitive either.
        # Any authenticated user may view it; only entity types that
        # carry real per-customer data need ownership resolution below.
        return

    # Imported locally to avoid a circular import (these repositories
    # don't need to depend on this module at all).
    from app.repositories.invoice_repository import InvoiceRepository
    from app.repositories.payment_repository import PaymentRepository
    from app.repositories.refund_repository import RefundRepository
    from app.repositories.subscription_repository import SubscriptionRepository

    customer_id: Optional[uuid.UUID] = None

    if entity_type == "customer":
        customer_id = entity_id
    elif entity_type == "subscription":
        subscription = SubscriptionRepository(db).get_by_id(entity_id)
        customer_id = subscription.customer_id if subscription else None
    elif entity_type == "invoice":
        invoice = InvoiceRepository(db).get_by_id(entity_id)
        customer_id = invoice.customer_id if invoice else None
    elif entity_type == "payment":
        payment = PaymentRepository(db).get_by_id(entity_id)
        if payment is not None:
            invoice = InvoiceRepository(db).get_by_id(payment.invoice_id)
            customer_id = invoice.customer_id if invoice else None
    elif entity_type == "refund":
        refund = RefundRepository(db).get_by_id(entity_id)
        customer_id = refund.customer_id if refund else None
    else:
        raise ForbiddenException("You do not have access to this resource")

    if customer_id is None:
        raise ForbiddenException("You do not have access to this resource")
    assert_owns_customer(customer_id, requesting_user, db)
