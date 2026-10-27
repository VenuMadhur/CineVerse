"""
Business logic for Tax Master administration (Module 3, Phase 2a).

Distinct from TaxService (app/services/tax_service.py), which is the
calculation engine InvoiceService uses internally to look up a rate
and compute tax on an amount. This service is the admin-facing CRUD
for managing TaxRate records themselves, following the exact same
pattern as PlanService/RetryService.
"""
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.exceptions.custom_exceptions import NotFoundException
from app.models.enums import AuditEventType
from app.models.tax_rate import TaxRate
from app.repositories.tax_rate_repository import TaxRateRepository
from app.schemas.tax import TaxRateCreate, TaxRateUpdate
from app.services.audit_log_service import AuditLogService


class TaxRateService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TaxRateRepository(db)
        self.audit_service = AuditLogService(db)

    def create_tax_rate(
        self, payload: TaxRateCreate, actor_id: Optional[uuid.UUID] = None
    ) -> TaxRate:
        tax_rate = TaxRate(
            country=payload.country,
            state=payload.state,
            tax_name=payload.tax_name,
            tax_percentage=payload.tax_percentage,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_active=payload.is_active,
        )
        tax_rate = self.repository.add(tax_rate)

        self.audit_service.record(
            event_type=AuditEventType.TAX_RATE_CREATED,
            entity_type="tax_rate",
            entity_id=tax_rate.id,
            description=(
                f"Tax rate created: {tax_rate.tax_name} {tax_rate.tax_percentage}% "
                f"for {tax_rate.country}"
            ),
            actor_id=actor_id,
            metadata={"country": tax_rate.country, "tax_percentage": str(tax_rate.tax_percentage)},
        )
        self.db.commit()
        self.db.refresh(tax_rate)
        return tax_rate

    def update_tax_rate(
        self, tax_rate_id: uuid.UUID, payload: TaxRateUpdate, actor_id: Optional[uuid.UUID] = None
    ) -> TaxRate:
        tax_rate = self._get_tax_rate_or_404(tax_rate_id)

        update_data = payload.model_dump(exclude_unset=True)
        changed_fields = {}
        old_values = {}
        for field, value in update_data.items():
            current = getattr(tax_rate, field)
            if current != value:
                changed_fields[field] = value
                old_values[field] = current
                setattr(tax_rate, field, value)

        if changed_fields:
            self.db.flush()
            self.audit_service.record(
                event_type=AuditEventType.TAX_RATE_UPDATED,
                entity_type="tax_rate",
                entity_id=tax_rate.id,
                description=f"Tax rate for {tax_rate.country} updated",
                actor_id=actor_id,
                metadata={"changed_fields": list(changed_fields.keys())},
                old_value=str(old_values),
                new_value=str(changed_fields),
            )
        self.db.commit()
        self.db.refresh(tax_rate)
        return tax_rate

    def get_tax_rate(self, tax_rate_id: uuid.UUID) -> TaxRate:
        return self._get_tax_rate_or_404(tax_rate_id)

    def list_tax_rates(
        self, country: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[TaxRate]:
        return self.repository.list_all(country, skip, limit)

    def count_tax_rates(self, country: Optional[str] = None) -> int:
        return self.repository.count_all(country)

    def _get_tax_rate_or_404(self, tax_rate_id: uuid.UUID) -> TaxRate:
        tax_rate = self.repository.get_by_id(tax_rate_id)
        if tax_rate is None:
            raise NotFoundException(f"Tax rate {tax_rate_id} not found")
        return tax_rate
