"""
Authentication endpoints: register, login, refresh token.

Two login endpoints are provided:
    POST /auth/login  - JSON body (email, password) for frontend/API clients.
    POST /auth/token   - application/x-www-form-urlencoded (username, password)
                          per OAuth2 Password Flow, used by Swagger UI's
                          "Authorize" button and other OAuth2-compliant tooling.

Both issue the same JWT access/refresh token pair via AuthService.authenticate.

Rate limiting: all four endpoints below are the most common target for
credential-stuffing/brute-force attempts, so each is limited to
RATE_LIMIT_AUTH_MAX_ATTEMPTS requests per RATE_LIMIT_AUTH_WINDOW_SECONDS
per client (see app/core/rate_limiter.py). Registration and login are
rate-limited independently, so exhausting one doesn't block the other.
"""
from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.settings import settings
from app.core.database import get_db
from app.core.rate_limiter import get_client_ip, rate_limit
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

_auth_rate_limit_kwargs = dict(
    max_attempts=settings.RATE_LIMIT_AUTH_MAX_ATTEMPTS,
    window_seconds=settings.RATE_LIMIT_AUTH_WINDOW_SECONDS,
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new API user",
    dependencies=[Depends(rate_limit(**_auth_rate_limit_kwargs, scope="register"))],
)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    return AuthService(db).register(payload, ip_address=get_client_ip(request))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with a JSON body and receive access + refresh tokens",
    dependencies=[Depends(rate_limit(**_auth_rate_limit_kwargs, scope="login"))],
)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    return AuthService(db).login(payload, ip_address=get_client_ip(request))


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="OAuth2 Password Flow token endpoint (used by Swagger's Authorize button)",
    dependencies=[Depends(rate_limit(**_auth_rate_limit_kwargs, scope="login"))],
)
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # OAuth2PasswordRequestForm uses the field name `username`; our users
    # authenticate by email, so we simply treat `username` as the email.
    # Shares the "login" rate-limit scope with POST /login above -- both
    # are the same underlying action (a password guess), just two
    # different request shapes for the same endpoint's worth of risk.
    return AuthService(db).authenticate(
        form_data.username, form_data.password, ip_address=get_client_ip(request)
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair",
    dependencies=[Depends(rate_limit(**_auth_rate_limit_kwargs, scope="refresh"))],
)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    return AuthService(db).refresh(payload.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated user's account details, including admin status",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record a logout event for the Activity Timeline",
)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    JWT authentication is stateless -- there is no server-side session
    for this endpoint to invalidate, and the frontend clears its
    stored tokens regardless of whether this call succeeds. This
    endpoint's only purpose is recording a USER_LOGGED_OUT audit event
    so it appears in the account-wide Activity Timeline.
    """
    AuthService(db).logout(current_user, ip_address=get_client_ip(request))
    return None
