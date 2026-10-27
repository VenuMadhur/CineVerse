"""
AuditLog model: append-only log of all significant billing events
for financial compliance.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import UUIDPrimaryKeyMixin, utcnow
from app.core.database import Base
from app.models.enums import AuditEventType


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType, name="audit_event_type_enum"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="system"
    )
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Module 3, Phase 4: all nullable/additive -- every existing
    # record() call site across the codebase continues to work
    # unmodified, producing rows with these fields left NULL.
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6-safe length
    actor_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} entity={self.entity_type}:{self.entity_id}>"
