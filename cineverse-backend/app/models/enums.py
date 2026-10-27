"""
Enum types shared across models, schemas, and services.

Each Python enum backs a native PostgreSQL ENUM type via
SQLAlchemy's Enum construct (see individual model columns).
"""
import enum


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class BillingInterval(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class PlanStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    FAILED = "failed"
    VOID = "void"
    REFUNDED = "refunded"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class CancellationType(str, enum.Enum):
    IMMEDIATE = "immediate"
    END_OF_CYCLE = "end_of_cycle"


class InvoiceLineItemType(str, enum.Enum):
    PLAN_FEE = "plan_fee"
    PRORATION_CREDIT = "proration_credit"
    PRORATION_DEBIT = "proration_debit"
    USAGE_CHARGE = "usage_charge"
    TAX = "tax"
    DISCOUNT = "discount"
    REFUND = "refund"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class RetryStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditEventType(str, enum.Enum):
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    PLAN_ARCHIVED = "plan_archived"
    PLAN_UNARCHIVED = "plan_unarchived"
    PLAN_DELETED = "plan_deleted"
    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_UPDATED = "customer_updated"
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    SUBSCRIPTION_PAUSED = "subscription_paused"
    SUBSCRIPTION_RESUMED = "subscription_resumed"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    SUBSCRIPTION_CANCELLATION_UNDONE = "subscription_cancellation_undone"
    SUBSCRIPTION_PLAN_CHANGED = "subscription_plan_changed"
    STATUS_CHANGED = "status_changed"
    BILLING_CYCLE_CREATED = "billing_cycle_created"
    INVOICE_GENERATED = "invoice_generated"
    INVOICE_PAID = "invoice_paid"
    INVOICE_FAILED = "invoice_failed"
    PRORATION_APPLIED = "proration_applied"
    PAYMENT_PROCESSED = "payment_processed"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REFUNDED = "payment_refunded"
    WEBHOOK_RECEIVED = "webhook_received"
    REFUND_CREATED = "refund_created"
    TRIAL_ENDING_REMINDER_SENT = "trial_ending_reminder_sent"
    RENEWAL_REMINDER_SENT = "renewal_reminder_sent"
    USER_REGISTERED = "user_registered"
    USER_LOGGED_IN = "user_logged_in"
    USER_LOGGED_OUT = "user_logged_out"
    RETRY_CONFIGURATION_CREATED = "retry_configuration_created"
    RETRY_CONFIGURATION_UPDATED = "retry_configuration_updated"
    RETRY_SCHEDULED = "retry_scheduled"
    RETRY_ATTEMPTED = "retry_attempted"
    RETRY_SUCCEEDED = "retry_succeeded"
    RETRY_FAILED = "retry_failed"
    RETRY_CANCELLED = "retry_cancelled"
    TAX_RATE_CREATED = "tax_rate_created"
    TAX_RATE_UPDATED = "tax_rate_updated"
    TRIAL_STARTED = "trial_started"
    TRIAL_ENDED = "trial_ended"
    INVOICE_UPDATED = "invoice_updated"
    PDF_GENERATED = "pdf_generated"
    INVOICE_DOWNLOADED = "invoice_downloaded"
