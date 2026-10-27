"""
Data access layer for the RetryConfiguration entity.
"""
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.retry_configuration import RetryConfiguration
from app.repositories.base_repository import BaseRepository


class RetryConfigurationRepository(BaseRepository[RetryConfiguration]):
    def __init__(self, db: Session):
        super().__init__(RetryConfiguration, db)

    def get_by_id(self, config_id: uuid.UUID) -> Optional[RetryConfiguration]:
        return super().get_by_id(config_id)

    def get_by_retry_attempt(self, retry_attempt: int) -> Optional[RetryConfiguration]:
        stmt = select(RetryConfiguration).where(
            RetryConfiguration.retry_attempt == retry_attempt
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, skip: int = 0, limit: int = 100) -> List[RetryConfiguration]:
        stmt = (
            select(RetryConfiguration)
            .order_by(RetryConfiguration.retry_attempt.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_active(self) -> List[RetryConfiguration]:
        """
        Used by the retry scheduler to determine the currently-active
        retry schedule, in attempt order.
        """
        stmt = (
            select(RetryConfiguration)
            .where(RetryConfiguration.is_active.is_(True))
            .order_by(RetryConfiguration.retry_attempt.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_first_active(self) -> Optional[RetryConfiguration]:
        """
        The retry configuration to use for a newly-failed payment's
        first retry -- the lowest active attempt number. None if no
        active retry configuration exists at all (retries not
        configured yet), in which case the caller should no-op rather
        than fail.
        """
        stmt = (
            select(RetryConfiguration)
            .where(RetryConfiguration.is_active.is_(True))
            .order_by(RetryConfiguration.retry_attempt.asc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_next_active(self, current_attempt: int) -> Optional[RetryConfiguration]:
        """
        The next active retry configuration after `current_attempt`.
        None means the retry sequence is exhausted -- the caller
        should cancel the subscription rather than schedule another
        attempt.
        """
        stmt = (
            select(RetryConfiguration)
            .where(
                RetryConfiguration.is_active.is_(True),
                RetryConfiguration.retry_attempt > current_attempt,
            )
            .order_by(RetryConfiguration.retry_attempt.asc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()
