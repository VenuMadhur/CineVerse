"""
Pydantic v2 schemas for the Retry Configuration resource (Module 3,
Phase 1a). Retry Queue schemas will be added in Phase 1b, once an
endpoint actually needs to return them.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBaseModel


class RetryConfigurationBase(BaseModel):
    retry_attempt: int = Field(
        ..., ge=1, examples=[1], description="1st, 2nd, 3rd... retry attempt number"
    )
    retry_after_days: int = Field(
        ..., ge=1, examples=[1], description="Days after the payment first failed to retry"
    )
    is_active: bool = Field(True, examples=[True])


class RetryConfigurationCreate(RetryConfigurationBase):
    pass


class RetryConfigurationUpdate(BaseModel):
    """All fields optional -- only supplied fields are updated."""
    retry_after_days: int | None = Field(None, ge=1)
    is_active: bool | None = None


class RetryConfigurationResponse(ORMBaseModel):
    id: uuid.UUID
    retry_attempt: int
    retry_after_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
