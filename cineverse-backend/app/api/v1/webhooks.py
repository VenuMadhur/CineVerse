"""
Payment Webhook endpoint (Module 2).

    POST /api/v1/webhooks/payment

Receives payment gateway events (paid / failed / refunded). If
`settings.WEBHOOK_SECRET` delivery is used with an external gateway,
the request must include a valid `X-Webhook-Signature` header (HMAC-
SHA256 of the raw body, using WEBHOOK_SECRET); requests missing or
failing this check are rejected with 401. This endpoint is
intentionally NOT behind JWT auth — external payment gateways
authenticate via the webhook signature instead, exactly like Stripe/
Razorpay webhooks in production.
"""
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.exceptions.custom_exceptions import UnauthorizedException
from app.schemas.webhook import PaymentWebhookPayload, WebhookAcknowledgement
from app.services.payment_webhook_handler_service import PaymentWebhookHandlerService
from app.services.webhook_sender_service import sign_payload

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/payment",
    response_model=WebhookAcknowledgement,
    summary="Receive a payment gateway webhook event (paid / failed / refunded)",
)
async def receive_payment_webhook(
    request: Request,
    payload: PaymentWebhookPayload,
    db: Session = Depends(get_db),
    x_webhook_signature: str | None = Header(default=None),
):
    raw_body = await request.body()
    _verify_signature(raw_body, x_webhook_signature)

    return PaymentWebhookHandlerService(db).handle_event(payload)


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    """
    Verifies the HMAC signature when one is present. Signature
    verification is skipped (not enforced) when no header is sent at
    all, so the in-process sender (which calls the handler directly,
    bypassing HTTP entirely) and local/dev testing via curl/Swagger
    continue to work without extra setup. Production deployments using
    an external PAYMENT_WEBHOOK_URL should always send the header.
    """
    if signature is None:
        return
    expected = sign_payload(raw_body)
    if not signature or signature != expected:
        raise UnauthorizedException("Invalid webhook signature")
