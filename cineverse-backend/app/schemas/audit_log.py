"""
Pydantic v2 schemas for the AuditLog resource.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.models.enums import AuditEventType
from app.schemas.common import ORMBaseModel


class AuditLogResponse(ORMBaseModel):
    id: uuid.UUID
    event_type: AuditEventType
    entity_type: str
    entity_id: Optional[uuid.UUID]
    actor_id: Optional[uuid.UUID]
    actor_type: str
    description: str
    metadata_json: Dict[str, Any]
    created_at: datetime
    # Module 3, Phase 4: all optional/nullable -- existing rows (and
    # any client still expecting the pre-Phase-4 shape) are unaffected;
    # these are simply absent/null until populated.
    ip_address: Optional[str] = None
    actor_role: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    remarks: Optional[str] = None
