"""
Centralized logging configuration for the whole application.

Every module obtains its logger via `get_logger(__name__)` so log
formatting, level, and handlers stay consistent across API requests,
Celery tasks, and database operations.
"""
import logging
import sys

from app.config.settings import settings

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)


def configure_logging() -> None:
    """Configure root logging handlers exactly once."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Already configured (e.g. re-imported module)
        return

    root_logger.setLevel(settings.LOG_LEVEL)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(stream_handler)

    # Quiet down noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.APP_DEBUG else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
