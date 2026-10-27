"""
Pydantic v2 schemas for authentication (register/login/tokens).
"""
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMBaseModel


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=128)
    country: str = Field(..., min_length=2, max_length=2, examples=["US"])

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, v: str) -> str:
        return v.upper()


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(ORMBaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str
