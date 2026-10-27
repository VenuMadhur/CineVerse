"""
Payment Webhook Sender (Module 2).

Builds the webhook payload for a payment event and delivers it:

  * If `settings.PAYMENT_WEBHOOK_URL` is configured, POSTs the
    HMAC-signed payload there (with retries), exactly as a real
    payment gateway would call back into the billing system.
  * Otherwise (the default, for local/dev/test use so the platform
    works out of the box without extra infrastructure), it invokes
    the webhook handler directly, in-process, within the same DB
    session — simulating an instantaneous webhook round-trip.
"""
import hashlib
import hmac
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

import httpx
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.schemas.webhook import PaymentWebhookPayload

logger = get_logger(__name__)


def sign_payload(raw_body: bytes) -> str:
    return hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()


class WebhookSenderService:
    def __init__(self, db: Session):
        self.db = db

    def send_payment_event(
        self,
        event_type: Literal["paid", "failed", "refunded"],
        invoice_id: uuid.UUID,
        customer_id: uuid.UUID,
        transaction_id: str,
        amount: Decimal,
        event_time: datetime,
        message: Optional[str] = None,
    ) -> None:
        payload = PaymentWebhookPayload(
            invoice_id=invoice_id,
            customer_id=customer_id,
            transaction_id=transaction_id,
            status=event_type,
            amount=amount,
            event_time=event_time,
            message=message,
        )

        if settings.PAYMENT_WEBHOOK_URL:
            self._send_over_http(payload)
        else:
            self._send_in_process(payload)

    # ------------------------------------------------------------------
    # Delivery strategies
    # ------------------------------------------------------------------
    def _send_in_process(self, payload: PaymentWebhookPayload) -> None:
        # Import locally to avoid a circular import at module load time
        # (the handler module does not depend on the sender).
        from app.services.payment_webhook_handler_service import (
            PaymentWebhookHandlerService,
        )

        logger.info(
            "Delivering payment webhook in-process: event=%s invoice=%s",
            payload.status, payload.invoice_id,
        )
        PaymentWebhookHandlerService(self.db).handle_event(payload)

    @retry(
        stop=stop_after_attempt(settings.WEBHOOK_MAX_RETRIES),
        wait=wait_fixed(1),
        reraise=False,
    )
    def _post_webhook(self, url: str, raw_body: bytes, signature: str) -> httpx.Response:
        response = httpx.post(
            url,
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response

    def _send_over_http(self, payload: PaymentWebhookPayload) -> None:
        raw_body = payload.model_dump_json().encode("utf-8")
        signature = sign_payload(raw_body)
        try:
            self._post_webhook(settings.PAYMENT_WEBHOOK_URL, raw_body, signature)
            logger.info(
                "Payment webhook delivered to %s (event=%s)",
                settings.PAYMENT_WEBHOOK_URL, payload.status,
            )
        except Exception:  # noqa: BLE001
            # Webhook delivery failures must never break payment
            # processing itself; log and move on. A production system
            # would persist an outbox record here for later replay.
            logger.exception(
                "Failed to deliver payment webhook to %s after %d attempts",
                settings.PAYMENT_WEBHOOK_URL, settings.WEBHOOK_MAX_RETRIES,
            )
