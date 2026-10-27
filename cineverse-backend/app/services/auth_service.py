"""
Business logic for authentication: registration, login, and token
refresh.

Records USER_REGISTERED / USER_LOGGED_IN audit events (Activity
Timeline) -- reusing the existing AuditLogService exactly like every
other service already does, not a new logging mechanism. USER_LOGGED_IN
is recorded once, in authenticate(), since both /auth/login (via
login()) and /auth/token route through it -- no duplicate call sites
needed for the two login request shapes.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_subject_from_token,
    hash_password,
    verify_password,
)
from app.exceptions.custom_exceptions import ConflictException, UnauthorizedException
from app.models.enums import AuditEventType
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserLogin, UserRegister
from app.schemas.customer import CustomerCreate
from app.services.audit_log_service import AuditLogService
from app.services.customer_service import CustomerService
from app.services.notification_dispatch import notify


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)
        self.audit_service = AuditLogService(db)

    def register(self, payload: UserRegister, ip_address: Optional[str] = None, is_superuser: bool = False) -> User:
        existing = self.repository.get_by_email(payload.email)
        if existing is not None:
            raise ConflictException(f"A user with email '{payload.email}' already exists")

        try:
            user = User(
                email=payload.email,
                full_name=payload.full_name,
                hashed_password=hash_password(payload.password),
                is_superuser=is_superuser,
            )
            user = self.repository.add(user)
            self.audit_service.record(
                event_type=AuditEventType.USER_REGISTERED,
                entity_type="user",
                entity_id=user.id,
                description=f"User {user.email} registered",
                actor_id=user.id,
                actor_role="admin" if user.is_superuser else "customer",
                ip_address=ip_address,
            )

            if not user.is_superuser:
                customer_service = CustomerService(self.db)
                customer_payload = CustomerCreate(
                    name=payload.full_name,
                    email=payload.email,
                    country=payload.country
                )
                customer = customer_service._create_customer_record(customer_payload, actor_id=user.id)
            else:
                customer = None

            self.db.commit()
            self.db.refresh(user)

            if customer:
                notify("welcome", customer.id)
            
            return user
        except Exception:
            self.db.rollback()
            raise

    def authenticate(
        self, email: str, password: str, ip_address: Optional[str] = None
    ) -> TokenResponse:
        user = self.repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException("User account is inactive")

        self.audit_service.record(
            event_type=AuditEventType.USER_LOGGED_IN,
            entity_type="user",
            entity_id=user.id,
            description=f"User {user.email} logged in",
            actor_id=user.id,
            actor_role="admin" if user.is_superuser else "customer",
            ip_address=ip_address,
        )
        self.db.commit()

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    def login(self, payload: UserLogin, ip_address: Optional[str] = None) -> TokenResponse:
        return self.authenticate(payload.email, payload.password, ip_address=ip_address)

    def refresh(self, refresh_token: str) -> TokenResponse:
        subject = get_subject_from_token(refresh_token, expected_type="refresh")
        return TokenResponse(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
        )

    def logout(self, user: User, ip_address: Optional[str] = None) -> None:
        """
        JWT auth is stateless -- there is no server-side session to
        invalidate -- so this method's only job is to record the
        USER_LOGGED_OUT audit event for the Activity Timeline. Called
        by POST /auth/logout, a new endpoint whose sole purpose is
        this recording.
        """
        self.audit_service.record(
            event_type=AuditEventType.USER_LOGGED_OUT,
            entity_type="user",
            entity_id=user.id,
            description=f"User {user.email} logged out",
            actor_id=user.id,
            actor_role="admin" if user.is_superuser else "customer",
            ip_address=ip_address,
        )
        self.db.commit()
