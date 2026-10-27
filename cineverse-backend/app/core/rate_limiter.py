"""
Fixed-window rate limiter, backed by the existing Redis instance --
no new infrastructure or third-party rate-limiting library needed.

Applied as a FastAPI dependency to the endpoints most exposed to
abuse: authentication (register/login/token/refresh), which are the
common target for credential-stuffing and brute-force attempts.

Fails open (allows the request through) if Redis itself is
unreachable, logging a warning instead of raising -- consistent with
this project's existing philosophy of never letting an auxiliary
system (notifications, webhooks) become a single point of failure for
core functionality. A rate limiter that itself takes down login when
Redis hiccups would be worse than no rate limiter at all.
"""
import redis
from fastapi import Request

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.exceptions.custom_exceptions import RateLimitExceededException

logger = get_logger(__name__)

_redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    socket_connect_timeout=2,
    socket_timeout=2,
    decode_responses=True,
)


def get_client_ip(request: Request) -> str:
    """
    Prefers the first hop of X-Forwarded-For (set by a reverse proxy/
    load balancer in front of this API in any real deployment) over
    the raw connection address. Used both for rate-limiting keys here
    and for audit log ip_address capture (Module 3, Phase 4).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(max_attempts: int, window_seconds: int, scope: str):
    """
    Returns a FastAPI dependency enforcing `max_attempts` requests per
    `window_seconds` per client, scoped independently per `scope` --
    e.g. "login" and "register" each get their own counter, even for
    the same client, so hitting one limit doesn't spuriously affect
    the other.
    """

    def _dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        key = f"ratelimit:{scope}:{get_client_ip(request)}"
        try:
            current = _redis_client.incr(key)
            if current == 1:
                _redis_client.expire(key, window_seconds)
            if current > max_attempts:
                ttl = _redis_client.ttl(key)
                raise RateLimitExceededException(
                    message=f"Too many {scope} attempts. Please try again in a moment.",
                    retry_after=ttl if ttl and ttl > 0 else window_seconds,
                )
        except RateLimitExceededException:
            raise
        except Exception:  # noqa: BLE001
            logger.warning(
                "Rate limiter unavailable (Redis unreachable?), failing open for scope=%s",
                scope,
                exc_info=True,
            )
            return

    return _dependency
