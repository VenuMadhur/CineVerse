"""
Business logic for Customer management.
"""
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.exceptions.custom_exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.customer import Customer
from app.models.enums import AuditEventType
from app.models.user import User
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.audit_log_service import AuditLogService
from app.services.notification_dispatch import notify


class CustomerService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CustomerRepository(db)
        self.audit_service = AuditLogService(db)

    def _create_customer_record(
        self, payload: CustomerCreate, actor_id: Optional[uuid.UUID] = None
    ) -> Customer:
        existing = self.repository.get_by_email(payload.email)
        if existing is not None:
            raise ConflictException(
                f"A customer with email '{payload.email}' already exists"
            )
        if actor_id is not None and self.repository.get_by_user_id(actor_id) is not None:
            raise ConflictException("This account already has a linked customer record")

        # `actor_id` is always the currently authenticated User's own id
        # (see app/api/v1/customers.py) -- linking it here is what keeps
        # Customer.user_id populated for every customer created from
        # this point forward, which GET /customers/me depends on. This
        # is not ownership *enforcement* (no access is restricted here)
        # -- it's the same internal field Phase 1A's migration added,
        # now actually being set; the request/response contract is
        # unchanged.
        customer = Customer(
            name=payload.name,
            email=payload.email,
            phone_number=payload.phone_number,
            country=payload.country,
            address=payload.address,
            state=payload.state,
            user_id=actor_id,
        )
        customer = self.repository.add(customer)

        self.audit_service.record(
            event_type=AuditEventType.CUSTOMER_CREATED,
            entity_type="customer",
            entity_id=customer.id,
            description=f"Customer '{customer.name}' created",
            actor_id=actor_id,
        )
        return customer

    def create_customer(
        self, payload: CustomerCreate, actor_id: Optional[uuid.UUID] = None
    ) -> Customer:
        customer = self._create_customer_record(payload, actor_id)
        self.db.commit()
        self.db.refresh(customer)
        notify("welcome", customer.id)
        return customer

    def update_customer(
        self,
        customer_id: uuid.UUID,
        payload: CustomerUpdate,
        actor_id: Optional[uuid.UUID] = None,
        requesting_user: Optional[User] = None,
    ) -> Customer:
        customer = self.get_customer(customer_id, requesting_user=requesting_user)
        update_data = payload.model_dump(exclude_unset=True)
        changed_fields = {}
        old_values = {}
        for field, value in update_data.items():
            current = getattr(customer, field)
            if current != value:
                changed_fields[field] = value
                old_values[field] = current
                setattr(customer, field, value)

        if changed_fields:
            self.db.flush()
            self.audit_service.record(
                event_type=AuditEventType.CUSTOMER_UPDATED,
                entity_type="customer",
                entity_id=customer.id,
                description=f"Customer '{customer.name}' updated",
                actor_id=actor_id,
                metadata={"changed_fields": list(changed_fields.keys())},
                old_value=str(old_values),
                new_value=str(changed_fields),
            )
        self.db.commit()
        self.db.refresh(customer)
        if changed_fields:
            notify("profile_updated", customer.id)
        return customer

    def get_customer(
        self, customer_id: uuid.UUID, requesting_user: Optional[User] = None
    ) -> Customer:
        """
        Ownership enforcement (Phase 1C): when `requesting_user` is
        provided (i.e. this is being called on behalf of an API
        request, not an internal service-to-service lookup), a
        non-superuser may only fetch the Customer linked to their own
        account. Internal callers that need a Customer by ID for
        business logic unrelated to a specific request (invoice
        generation, the billing scheduler, notifications, etc.) go
        through `CustomerRepository` directly and are unaffected by
        this check.
        """
        customer = self.repository.get_by_id(customer_id)
        if customer is None:
            raise NotFoundException(f"Customer {customer_id} not found")

        if requesting_user is not None and not requesting_user.is_superuser:
            if customer.user_id != requesting_user.id:
                raise ForbiddenException(
                    "You do not have access to this customer record"
                )
        return customer

    def get_my_customer(self, user_id: uuid.UUID) -> Customer:
        """
        Returns the Customer record linked (via Customer.user_id) to the
        given User. Raises NotFoundException if this User has no linked
        Customer yet -- the caller (frontend) is expected to prompt for
        billing profile setup in that case.
        """
        customer = self.repository.get_by_user_id(user_id)
        if customer is None:
            raise NotFoundException("No customer record is linked to this account")
        return customer

    def list_customers(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Customer]:
        return self.repository.list_all(skip, limit, search=search)

    def count_customers(self, search: Optional[str] = None) -> int:
        return self.repository.count_search(search=search)
