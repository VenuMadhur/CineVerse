"""
Data access layer for the TaxRate entity.
"""
import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tax_rate import TaxRate
from app.repositories.base_repository import BaseRepository


class TaxRateRepository(BaseRepository[TaxRate]):
    def __init__(self, db: Session):
        super().__init__(TaxRate, db)

    def get_by_id(self, tax_rate_id: uuid.UUID) -> Optional[TaxRate]:
        return super().get_by_id(tax_rate_id)

    def list_all(
        self, country: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[TaxRate]:
        stmt = select(TaxRate)
        if country is not None:
            stmt = stmt.where(TaxRate.country == country.upper())
        stmt = (
            stmt.order_by(TaxRate.country.asc(), TaxRate.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_all(self, country: Optional[str] = None) -> int:
        stmt = select(func.count()).select_from(TaxRate)
        if country is not None:
            stmt = stmt.where(TaxRate.country == country.upper())
        return self.db.execute(stmt).scalar_one()

    def get_effective_rate(self, country: str, as_of: date) -> Optional[TaxRate]:
        """
        The single active tax rate for `country` whose effective date
        range covers `as_of`. If more than one row matches (e.g. an
        old rate whose effective_to wasn't set before a new one
        started), the most recently effective one wins.
        """
        stmt = (
            select(TaxRate)
            .where(
                TaxRate.country == country.upper(),
                TaxRate.is_active.is_(True),
                TaxRate.effective_from <= as_of,
                (TaxRate.effective_to.is_(None)) | (TaxRate.effective_to >= as_of),
            )
            .order_by(TaxRate.effective_from.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()
