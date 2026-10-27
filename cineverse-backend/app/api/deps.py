"""
Reusable FastAPI dependencies: current authenticated user, current
superuser (admin), and common query-param helpers (pagination).
"""
import uuid

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_subject_from_token
from app.exceptions.custom_exceptions import ForbiddenException, UnauthorizedException
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if token is None:
        raise UnauthorizedException("Missing bearer token")

    subject = get_subject_from_token(token, expected_type="access")
    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise UnauthorizedException("Invalid token subject") from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedException("User not found or inactive")
    return user


def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    Layers on top of get_current_user: requires a valid, active session
    (401 otherwise) AND that the account is flagged is_superuser (403
    otherwise). Use for admin-only endpoints -- see Plan mutation
    routes and the customer list endpoint for examples.
    """
    if not current_user.is_superuser:
        raise ForbiddenException("This action requires administrator privileges")
    return current_user


class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.skip = (page - 1) * page_size
        self.limit = page_size
