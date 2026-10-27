"""
Aggregates all v1 routers into a single APIRouter mounted by
app.main under the configured API_V1_PREFIX.
"""
from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    audit_logs,
    auth,
    customers,
    health,
    invoices,
    payments,
    plans,
    refunds,
    reports,
    retry,
    subscriptions,
    tax,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(plans.router)
api_router.include_router(customers.router)
api_router.include_router(subscriptions.router)
api_router.include_router(invoices.router)
api_router.include_router(payments.router)
api_router.include_router(webhooks.router)
api_router.include_router(refunds.router)
api_router.include_router(audit_logs.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(retry.router)
api_router.include_router(tax.router)
