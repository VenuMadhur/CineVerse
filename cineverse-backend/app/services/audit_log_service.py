"""
Reusable audit logging service.

Every service that mutates billing-relevant state should call
`AuditLogService.record(...)` within the same DB transaction so the
audit trail is always consistent with the actual data change.
"""
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config.logging_config import get_logger
from app.models.audit_log import AuditLog
from app.models.enums import AuditEventType
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.refund_repository import RefundRepository
from app.repositories.subscription_repository import SubscriptionRepository

logger = get_logger(__name__)

# Pragmatic ceiling on how many of each entity type contribute to one
# account's Activity Timeline -- reasonable for this project's scale,
# same philosophy as ReportService's _ROW_LIMIT.
_ACCOUNT_ENTITY_LIMIT = 1000


class AuditLogService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AuditLogRepository(db)
        self.customer_repository = CustomerRepository(db)
        self.subscription_repository = SubscriptionRepository(db)
        self.invoice_repository = InvoiceRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.refund_repository = RefundRepository(db)

    def record(
        self,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: Optional[uuid.UUID],
        description: str,
        actor_id: Optional[uuid.UUID] = None,
        actor_type: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        actor_role: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            actor_type=actor_type,
            description=description,
            metadata_json=metadata or {},
            ip_address=ip_address,
            actor_role=actor_role,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
        self.repository.add(entry)
        logger.info(
            "Audit event recorded: %s on %s:%s - %s",
            event_type.value, entity_type, entity_id, description,
        )
        return entry

    def list_for_entity(self, entity_type: str, entity_id: uuid.UUID, skip=0, limit=100):
        return self.repository.list_for_entity(entity_type, entity_id, skip, limit)

    def list_all(self, entity_type: Optional[str] = None, skip=0, limit=100):
        return self.repository.list_all(entity_type, skip, limit)

    def count_all(self, entity_type: Optional[str] = None) -> int:
        return self.repository.count_all(entity_type)

    def has_event(self, entity_type: str, entity_id: uuid.UUID, event_type: AuditEventType) -> bool:
        return self.repository.has_event(entity_type, entity_id, event_type)

    # ------------------------------------------------------------------
    # Account-wide Activity Timeline
    # ------------------------------------------------------------------
    def _account_entity_pairs(self, user: User) -> List[tuple]:
        """
        Every (entity_type, entity_id) that belongs to one account:
        the user itself, their linked customer (if any), and every
        subscription/invoice/payment/refund that customer owns.
        Reuses the exact same repositories every other service already
        uses -- no new queries beyond what GET /subscriptions,
        /invoices, /payments, /refunds already run for that customer.
        """
        pairs: List[tuple] = [("user", user.id)]

        customer = self.customer_repository.get_by_user_id(user.id)
        if customer is None:
            return pairs
        pairs.append(("customer", customer.id))

        subscriptions = self.subscription_repository.list_all(
            customer_id=customer.id, limit=_ACCOUNT_ENTITY_LIMIT
        )
        pairs += [("subscription", s.id) for s in subscriptions]

        invoices = self.invoice_repository.list_all(
            customer_id=customer.id, limit=_ACCOUNT_ENTITY_LIMIT
        )
        pairs += [("invoice", i.id) for i in invoices]

        payments = self.payment_repository.list_all(
            customer_id=customer.id, limit=_ACCOUNT_ENTITY_LIMIT
        )
        pairs += [("payment", p.id) for p in payments]

        refunds = self.refund_repository.list_all(
            customer_id=customer.id, limit=_ACCOUNT_ENTITY_LIMIT
        )
        pairs += [("refund", r.id) for r in refunds]

        return pairs

    def list_for_account(self, user: User, skip: int = 0, limit: int = 50) -> List[AuditLog]:
        pairs = self._account_entity_pairs(user)
        return self.repository.list_for_account(pairs, skip, limit)

    def count_for_account(self, user: User) -> int:
        pairs = self._account_entity_pairs(user)
        return self.repository.count_for_account(pairs)
