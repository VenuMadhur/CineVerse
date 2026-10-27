"""
Centralized application configuration.

All environment-driven configuration is defined here as a single
Pydantic Settings class so the rest of the codebase never touches
`os.environ` directly.
"""
from functools import lru_cache
from typing import Dict, List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- Application ----
    APP_NAME: str = "Billing Automation Platform"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ---- Database ----
    POSTGRES_USER: str = "billing_user"
    POSTGRES_PASSWORD: str = "billing_pass"
    POSTGRES_DB: str = "billing_db"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = (
        "postgresql+psycopg2://billing_user:billing_pass@db:5432/billing_db"
    )

    # ---- Security / JWT ----
    SECRET_KEY: str = "change_this_to_a_long_random_secret_key_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080

    # ---- Redis / Celery ----
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ---- Rate Limiting ----
    # Reuses the existing Redis instance (no new infrastructure) to
    # apply a fixed-window request limit to the authentication
    # endpoints, which are the most common target for credential-
    # stuffing / brute-force attempts. Off entirely via
    # RATE_LIMIT_ENABLED=false if ever needed (e.g. local dev without
    # Redis running).
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_MAX_ATTEMPTS: int = 10
    RATE_LIMIT_AUTH_WINDOW_SECONDS: int = 60
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # ---- Billing Scheduler ----
    BILLING_SCHEDULER_INTERVAL_SECONDS: int = 3600
    # Module 3, Phase 1b: how often the retry scheduler checks for due
    # queue entries. More frequent than the daily reminder schedule,
    # since a retry configured for "1 day after failure" should
    # actually run close to that mark, not just once a day at a fixed
    # hour -- but this is still purely event-driven (it only processes
    # already-queued entries whose scheduled_retry_date has arrived,
    # never scans for new failures).
    RETRY_SCHEDULER_INTERVAL_SECONDS: int = 3600
    # Phase 6B: how many days before a trial ends / a cycle renews to
    # send a reminder email. Each subscription only ever gets one
    # reminder per trial/cycle regardless of how often the scheduler
    # runs (deduped via the audit log, see ReminderSchedulerService).
    TRIAL_ENDING_REMINDER_DAYS: int = 3
    RENEWAL_REMINDER_DAYS: int = 3

    # ---- Tax Calculation (Module 2) ----
    # Per-country tax rate as a decimal fraction (e.g. 0.08 = 8%), keyed by
    # ISO 3166-1 alpha-2 country code. Falls back to DEFAULT_TAX_RATE for
    # any country not listed here. Configurable via the TAX_RATES env var
    # as a JSON object string, e.g. {"US": 0.08, "IN": 0.18, "GB": 0.20}
    TAX_RATES: Dict[str, float] = {
        "US": 0.08,
        "IN": 0.18,
        "GB": 0.20,
        "DE": 0.19,
        "FR": 0.20,
        "CA": 0.05,
        "AU": 0.10,
    }
    DEFAULT_TAX_RATE: float = 0.0

    # ---- Mock Payment Gateway (Module 2) ----
    PAYMENT_GATEWAY_SUCCESS_RATE: float = 0.9  # 90% simulated success rate

    # ---- Payment Webhooks (Module 2) ----
    # If set, the webhook sender POSTs (HMAC-signed) to this URL instead of
    # invoking the webhook handler in-process. Leave unset for local/dev/
    # test use, where the "webhook" is delivered in-process for simplicity.
    PAYMENT_WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: str = "change_this_webhook_secret_in_production"
    WEBHOOK_MAX_RETRIES: int = 3

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"

    # ---- Email Notifications (Module 2 + Phase 6B lifecycle emails) ----
    # If SMTP_HOST is unset (the default), notifications are logged
    # instead of actually sent -- so this feature works out of the box
    # for local/dev/demo use without requiring a real mail provider.
    #
    # Provider-agnostic by design: SMTP is not "just SMTP" here -- every
    # major transactional provider (SendGrid, Amazon SES, Resend,
    # Mailgun, Postmark, etc.) exposes a standard SMTP relay endpoint,
    # so pointing these settings at any of them works without any
    # provider-specific SDK/code branch. For example:
    #   SendGrid:  SMTP_HOST=smtp.sendgrid.net       SMTP_USERNAME=apikey            SMTP_PASSWORD=<API key>
    #   Amazon SES: SMTP_HOST=email-smtp.<region>.amazonaws.com  SMTP_USERNAME=<SMTP user>  SMTP_PASSWORD=<SMTP password>
    #   Resend:    SMTP_HOST=smtp.resend.com         SMTP_USERNAME=resend             SMTP_PASSWORD=<API key>
    NOTIFICATIONS_ENABLED: bool = True
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    NOTIFICATION_FROM_EMAIL: str = "billing@cineverse.example.com"
    # Used by the HTML email template (Phase 6B) -- company name/logo in
    # the header, support contact in the footer of every email.
    COMPANY_NAME: str = "CineVerse"
    COMPANY_LOGO_URL: str = "https://cineverse.example.com/logo.png"
    SUPPORT_EMAIL: str = "support@cineverse.example.com"

    # ---- Company details for Invoice PDF (Module 3, Phase 5a) ----
    # Distinct from COMPANY_LOGO_URL above (used by HTML email
    # templates, which a mail client fetches itself): PDF generation
    # must never depend on a network request, so this is a *local*
    # file path instead. Left empty by default -- no logo file
    # shipped with this project -- in which case the PDF gracefully
    # falls back to a styled text header using COMPANY_NAME.
    COMPANY_LOGO_PATH: str = ""
    COMPANY_ADDRESS: str = "123 Market Street, Suite 400, San Francisco, CA 94105, USA"
    COMPANY_PHONE: str = "+1 (415) 555-0100"
    COMPANY_EMAIL: str = "billing@cineverse.example.com"
    COMPANY_WEBSITE: str = "https://cineverse.example.com"
    # Module 3, Phase 5b: the customer-facing SPA's base URL, used only
    # to build optional CTA links in emails (e.g. "View Invoice" ->
    # {FRONTEND_BASE_URL}/invoices). Distinct from COMPANY_WEBSITE
    # above (the public marketing site) -- no such app-URL setting
    # existed before this phase.
    FRONTEND_BASE_URL: str = "https://app.cineverse.example.com"
    COMPANY_TAX_ID: str = "TAX-ID-0000000"
    SUPPORT_PHONE: str = "+1 (415) 555-0199"
    PAYMENT_TERMS: str = "Payment is due within the invoice's stated due date. Late payments may result in service suspension."
    REFUND_POLICY: str = "Refunds are issued at our discretion in accordance with our published refund policy. Contact support for assistance."

    # ---- CORS ----
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()


settings = get_settings()
