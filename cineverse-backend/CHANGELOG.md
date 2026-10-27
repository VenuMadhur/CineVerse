# Changelog

## Original Scope Completion: Paid Date, Rate Limiting, Activity Timeline (unreleased)

The final three items from the original planned scope, implemented in order.

### 1. Paid Date display

`InvoiceDetailResponse.paid_at` already existed on the backend since Phase
6C but was never shown on the frontend. No backend change needed —
covered under the frontend changelog.

### 2. Rate Limiting (429) for authentication endpoints

- **`app/core/rate_limiter.py`** (new) — a Redis-backed fixed-window rate
  limiter, reusing the existing Redis instance (no new infrastructure,
  no new third-party library). Fails open (allows the request through,
  logging a warning) if Redis is unreachable, so an outage of this
  auxiliary system never blocks real logins — same philosophy already
  used for notifications and webhooks in this codebase.
- Applied to `POST /auth/register`, `/login`, `/token`, and `/refresh`,
  each with an independent counter per client IP (via `X-Forwarded-For`,
  falling back to the raw connection address) — exhausting one endpoint's
  limit doesn't affect the others.
- New `RateLimitExceededException` (429, with a `Retry-After` header).
  `AppException` gained an optional `retry_after` attribute (`None` for
  every other exception, so nothing else's behavior changed) and the
  generic exception handler now surfaces it as a response header when set.
- New settings: `RATE_LIMIT_ENABLED` (default `true`),
  `RATE_LIMIT_AUTH_MAX_ATTEMPTS` (default `10`),
  `RATE_LIMIT_AUTH_WINDOW_SECONDS` (default `60`) — documented in
  `.env.example`.
- Disabled for the test suite (`tests/conftest.py` sets
  `RATE_LIMIT_ENABLED=false` by default, matching the existing
  `DATABASE_URL`/`SECRET_KEY` override pattern) — the suite legitimately
  makes far more auth requests per minute than any real client would.
  5 dedicated tests explicitly re-enable it to verify real enforcement.
- **Verified live** against the real running server: exactly 10 requests
  allowed, the 11th correctly returns `429` with `Retry-After: 60`.

### 3. Account-wide Activity Timeline

- Three new `AuditEventType` values (`USER_REGISTERED`, `USER_LOGGED_IN`,
  `USER_LOGGED_OUT`) via a new migration, same `ALTER TYPE ... ADD VALUE`
  pattern as every previous audit-event addition.
- `AuthService` now records `USER_REGISTERED` on registration and
  `USER_LOGGED_IN` on successful authentication (one call site,
  `authenticate()`, covers both `/auth/login` and `/auth/token` — no
  duplicated recording logic for the two login request shapes). Failed
  login attempts are correctly never recorded as a login.
- **New `POST /auth/logout`** — JWT auth is stateless, so there's no
  server-side session to invalidate; this endpoint's only job is
  recording the `USER_LOGGED_OUT` event.
- **New `GET /audit-logs/me`** — the account-wide timeline itself.
  Always scoped to the caller's own account (no customer_id parameter,
  unlike every other list endpoint — there's no admin/"see everyone"
  mode here at all). Implemented via new
  `AuditLogRepository.list_for_account()` /`count_for_account()`
  (matches audit entries across multiple `(entity_type, entity_id)`
  pairs via `OR`) and a new `AuditLogService` orchestration method that
  reuses the *existing* Customer/Subscription/Invoice/Payment/Refund
  repositories to resolve every entity that belongs to the caller's
  account — no new queries beyond what those resources' own list
  endpoints already run.
- 8 new tests: registration/login/logout recording (including that a
  *failed* login is never recorded), the timeline spanning every
  resource type an account touched (not just one subscription — the
  gap this feature was built to close), correct chronological
  ordering, and strict account-to-account isolation (verified that one
  account's timeline never contains another account's events).
- **Verified live**: register → login → logout against the real running
  server, confirmed all three appear in `GET /audit-logs/me` in the
  correct chronological order.

### Verified

- Full suite: 261/261 passing (253 existing + 8 new for the Activity
  Timeline; rate limiting's 5 tests were already included in that 253).
- OpenAPI schema: 48 paths (46 + `POST /auth/logout` + `GET /audit-logs/me`).
- `pyflakes` clean across `app/` (same 20 pre-existing, intentional
  model-registration imports).

---

## Critical Fix: Billing Cycle Timing — "Bill in Advance," Not "in Arrears" (unreleased)

**Root cause of "no invoice/payment after activation."** Confirmed live,
before fixing anything: `activate_subscription()` was never supposed to
generate an invoice (invoice generation is intentionally centralized in
the Celery Beat billing scheduler — this part of the architecture is
correct and was NOT changed). The actual bug: `BillingCycleService.
create_initial_cycle()` and `.advance_cycle()` both set
`next_billing_date = cycle_end_date` instead of `cycle_start_date` —
meaning every subscription (first cycle *and* every renewal) was only
ever invoiced a full billing period *after* that period had already
started, not when it began. A brand-new subscriber therefore got a
silent, unintended free period (on top of any trial) before ever being
billed — exactly reproducing "subscribe → activate → Invoices/Payments
stay empty."

### Fixed

- `app/services/billing_cycle_service.py` — `next_billing_date` now set
  to `cycle_start_date` in both `create_initial_cycle()` and
  `advance_cycle()`. Invoices are now generated at the *start* of the
  period being paid for ("bill in advance," standard for flat-rate
  subscriptions) and remain due by `cycle_end_date` (unchanged) — the
  customer is billed immediately and has the full period to pay, rather
  than being billed only after the period is already over.
- No schema change, no change to invoice/tax/proration math, no change
  to the scheduler's own due-cycle query — the fix is entirely in *when*
  a cycle becomes eligible for the scheduler to pick up.
- 4 new tests (`tests/test_billing_cycle_timing.py`): unit-level
  confirmation of the corrected timing for both methods, plus two full
  end-to-end reproductions of the reported scenario — a no-trial
  subscription is invoiced by a single, immediate scheduler run (no
  backdating needed), and a trial subscription is invoiced exactly at
  `trial_ends_at`, not a further full cycle later.

### Explicitly not changed (by design, confirmed correct)

- Invoice generation stays exclusively in the billing scheduler —
  `activate_subscription()` was **not** given its own invoicing logic,
  since that would create a second, competing code path and risk
  double-invoicing once the scheduler later processes the same cycle.
- Payment collection remains manual (the customer/frontend calls
  `POST /payments/process`) — there is no saved payment method or
  auto-charge capability anywhere in this system, consistent with every
  prior phase; this was not a gap introduced or fixed here.
- Refunds, reports, analytics, and every other module — untouched.

### Verified

- Full suite: 248/248 passing (244 existing + 4 new).
- Live, real-server proof (not just pytest): ran the *actual* FastAPI +
  Redis + Celery Worker + Celery Beat stack together, registered a
  customer, subscribed (no trial), activated — confirmed `0` invoices
  immediately after (matching the reported symptom exactly) — then, with
  **no backdating or manual triggering**, waited 15 real seconds for
  Celery Beat's own periodic schedule to fire on its own, and confirmed
  an invoice (`INV-202607-A6FEE1B1`, $32.39) was generated automatically,
  with its `invoice_generated` notification email logged through the
  same real worker, immediately after `subscription_started` and
  `subscription_activated`.

### Proactive lifecycle review (see chat for full writeup)

Reviewed every other lifecycle stage explicitly for the same class of
bug (missing/mistimed automation): trial expiration, renewals, invoice
generation, payment/refund processing, invoice/payment/refund emails,
reminder emails, and both Celery Beat schedules. All confirmed correct
except the one fixed here. One pre-existing, unrelated limitation is
worth flagging for a future decision, not fixed here: there is no
automatic dunning/cancellation for a customer who simply never pays an
open invoice — the subscription stays `active` and the scheduler will
keep generating new invoices each period regardless of payment status.
This is consistent with the "manual payment, no saved card" model this
whole system already uses, not a regression from this fix.

---

## Final Production Readiness Review (unreleased)

A complete backend↔frontend cross-check: for every implemented backend
endpoint, does the frontend actually have a UI for it? This surfaced one
real, pre-existing authorization gap that had never been covered by any
prior ownership-enforcement pass.

### Fixed (real security gap, confirmed live before and after)

- **`GET /audit-logs` and `GET /audit-logs/{entity_type}/{entity_id}` had
  no ownership enforcement at all** — this router predates Phase 1D and
  was never included in it. Confirmed live: a completely unrelated,
  non-admin user could pass any other customer's subscription/invoice/
  payment/refund ID and see their private audit trail, or call the
  unfiltered list endpoint and see the entire platform's history (58
  entries across every customer, in one unauthenticated-from-privacy'
  s-perspective call). Fixed:
  - New `assert_owns_audit_entity()` in `app/services/ownership.py` —
    resolves the owning `customer_id` per `entity_type` (customer
    directly; subscription/invoice via their own `customer_id`; payment
    via its invoice; refund directly) and reuses the existing
    `assert_owns_customer()` exactly as every other resource does.
  - **`plan` is deliberately exempt** — plans are already public data
    (`GET /plans` needs no authentication at all), so gating their audit
    trail more strictly than the resource itself would be inconsistent,
    not more secure. Any authenticated user may view a plan's trail;
    everything else requires ownership or admin.
  - `GET /audit-logs` (list-all) now requires admin unless filtered to
    `entity_type=plan` — this endpoint has no per-row scoping mechanism
    (unlike every other list endpoint), so even a `customer`- or
    `subscription`-filtered call would still mix every customer's rows
    together; only the plan exception is genuinely safe for a non-admin.
  - 9 new tests in `tests/test_audit_log_api.py`: cross-customer 403 on
    both the entity-trail and list-all endpoints, admin bypass, the
    plan-type public exception, and an unrecognized `entity_type` failing
    closed.
  - Two pre-existing tests (`test_list_all_audit_logs_filtered_by_entity_type`,
    which used the plan exception, and the plan-trail test) were checked
    against the new behavior and needed no changes — they already only
    exercised exactly the case that remains open.

### Verified

- Full suite: 244/244 passing (236 existing + 8 net new).
- OpenAPI schema: still 46 paths — pure authorization change, no new/
  removed/renamed endpoints.
- Live, real-server re-verification: repeated the exact cross-customer
  request that proved the gap before the fix, confirmed it now returns
  `403`, and confirmed the legitimate owner and an admin both still get
  `200`.

---

## Phase 6C: Invoice & Payment Improvements (unreleased)

Extends the invoice detail view with denormalized fields for a self-
contained display, adds "Email Invoice" (PDF as an attachment), and
confirms/documents two capabilities that already existed without any
backend change needed.

### Added

- **`InvoiceDetailResponse`** gained `customer_name`, `customer_email`,
  `customer_country`, `billing_address`, `payment_method` (from the most
  recent payment attempt), `discount_amount` (0 unless a future discount/
  coupon feature populates `DISCOUNT`-type line items — no such feature
  exists yet, this just exposes the field), and `refund_status`
  (`none`/`partial`/`full`) — genuinely new information: a partial refund
  leaves `status` as `paid` with a reduced `total_amount`, so there was
  previously no way to tell "partially refunded" from "never refunded"
  without this. All computed in a new `InvoiceService.get_invoice_with_details()`,
  reusing `CustomerRepository`/`PaymentRepository`/`RefundRepository`
  exactly as-is — no new queries beyond what `/payments` and `/refunds`
  sub-resources already run.
- **`POST /invoices/{invoice_id}/email`** — "Email Invoice." Regenerates
  the PDF via the existing `InvoicePdfService` (Phase 4) inside a new
  Celery task (`send_invoice_email`) and emails it as an attachment via
  a new `NotificationService.send_invoice_attachment()` method. Returns
  `202 Accepted` (delivery is asynchronous, same fire-and-forget
  guarantee as every other notification — a broker outage never breaks
  the request). Same ownership enforcement as every other invoice
  endpoint (Phase 1D): your own invoice, or any if you're an admin.
- **`NotificationService._send()`** extended to optionally accept a
  `(filename, bytes, mime_type)` attachment (`MIMEMultipart("mixed")`
  wrapping the existing text+HTML alternative part) — the one piece of
  real new plumbing this phase needed; every other notification is
  unaffected and still sends exactly as before.
- 10 new tests in `tests/test_invoice_api.py`: denormalized customer
  fields, `refund_status` transitions through none → partial → full
  (verified against real partial and full refunds, not just unit-level
  logic), payment method appears after a real payment, and the email
  endpoint's dispatch/auth/ownership/not-found/failure-resilience.

### Confirmed already working (no backend change needed)

- **"Retry Failed Payment"** — `PaymentGatewayService.process_payment`
  only ever blocked `PAID`/`VOID` invoices, never `FAILED` — a failed
  invoice could already be re-processed via the exact same
  `POST /payments/process`. Verified live: forced a guaranteed failure
  (`PAYMENT_GATEWAY_SUCCESS_RATE=0.0`), retried the identical request,
  confirmed it's accepted (not blocked) and the resulting payment record
  correctly shows `attempt_number: 2`.
- **"Payment Status History"** — already fully covered by the existing
  audit log (`payment_succeeded`/`payment_failed`/`payment_refunded`
  events, each timestamped) — no new history table needed.

### Explicitly not done (deferred, consistent with earlier phases)

- **Multiple payment gateways** (Stripe/Razorpay-ready abstraction) —
  flagged as its own, much larger architectural decision back in Phase
  6A/6B planning; not attempted here.
- **A discount/coupon-code system** — `discount_amount` is exposed on the
  response for when such a feature might exist, but no code path
  currently creates a `DISCOUNT` line item; building that system is a
  distinct feature request, not an invoice/payment "improvement."

### Verified

- Full suite: 236/236 passing (226 existing + 10 new).
- OpenAPI schema: 46 paths (45 + 1 new); every pre-existing path's shape
  unchanged except the additive `InvoiceDetailResponse` fields.
- Live, real-server verification: the enriched invoice detail fields
  return real, correct values against a real invoice; `POST .../email`
  dispatched to a real running Celery worker, which correctly
  regenerated a real PDF (2969 bytes) and logged the simulated send with
  the attachment noted; the retry-failed-payment live test described
  above.

---

## Phase 6B: Email Automation (unreleased)

### Important context for this entry

A substantially complete email-automation implementation was already
present in the codebase when this phase began (`notification_dispatch.py`,
`email_templates.py`, an expanded `NotificationService` covering 12 event
types with HTML templates, and real trigger wiring across 5 services --
Customer, Subscription, Invoice, PaymentWebhookHandler, Refund). This was
not built from scratch in this phase; it was **thoroughly verified**
line-by-line, one real regression was found and fixed, and the one
genuinely missing piece (trial-ending/renewal reminders) was added.

### Fixed (real regression, found via actually running the test suite)

- **`tests/test_notification_service.py` was completely stale** and
  failing (10 of 10 tests) -- it tested the pre-refactor 3-event, no-HTML
  architecture: wrong `_build_message()` signature, and it patched
  `app.tasks.notification_tasks.send_payment_notification`, a function
  that had been renamed to `send_notification_email` and no longer
  existed. The unpatched calls were falling through to real (unreachable)
  Redis connection attempts. Completely rewritten: 30 tests now, covering
  all 12 event types' message building, the shared `notify()` helper,
  and integration tests hitting all 14 real trigger points through the
  actual API (register→create customer→welcome email; profile update
  fires `profile_updated` only when something actually changed; the full
  subscription lifecycle fires the right event at each step; payment/
  refund notifications). All 30 pass.

### Added

- **Trial-ending & renewal reminder scheduler** (`app/scheduler/reminder_scheduler_service.py`,
  `app/tasks/reminder_tasks.py`) -- the one event type from the original
  request with no existing trigger point. Runs daily via a new Celery
  Beat entry (`run-reminder-scheduler`), separate from the billing
  scheduler. Deduped via the audit log (`AuditLogRepository.has_event()`,
  new) rather than a new "last_reminded_at" column -- a subscription is
  never reminded twice for the same trial/cycle regardless of how often
  the scheduler runs.
- Two new `AuditEventType` values (`TRIAL_ENDING_REMINDER_SENT`,
  `RENEWAL_REMINDER_SENT`) via a proper Alembic migration (`ALTER TYPE
  ... ADD VALUE`, following the exact pattern of the Module 2 audit-event
  migration), applied to both databases.
- `SubscriptionRepository.list_trial_ending_within()`,
  `BillingCycleRepository.list_upcoming_within()` -- new, narrowly-scoped
  query methods (upcoming, not-yet-due, distinct from the existing
  `list_due()` used by the actual billing scheduler).
- `TRIAL_ENDING_REMINDER_DAYS` / `RENEWAL_REMINDER_DAYS` settings
  (default 3 days), documented in `.env.example`.
- 8 new tests (`tests/test_reminder_scheduler.py`): sends within the
  window, doesn't send outside it, doesn't double-send on a second run,
  doesn't confuse an already-due cycle (billing scheduler's job) with an
  upcoming one, both reminder types correctly fire in a single pass.

### Explicitly not done (by design, scoped down from the original ask)

- **Email verification, password reset** -- no such auth flows exist in
  this system at all; adding email automation for features that don't
  exist would mean building the features first, which is well outside
  "email automation."
- **Subscription reactivation email** -- confirmed in Phase 6A that
  reactivating a cancelled subscription isn't supported (`CANCELLED` is a
  terminal state); no email for a capability that doesn't exist.
- **Multi-provider abstraction** (Resend/SendGrid/SES SDKs) -- the
  existing single configurable SMTP setup already works with all of
  these (they each expose an SMTP relay), without needing
  provider-specific code.
- **Admin Actions email** -- marked optional in the original request.

### Verified

- Full suite: 226/226 passing (198 existing, minus 10 broken-then-fixed,
  plus 30 rewritten + 8 new).
- Live, real-server verification (not just pytest): dispatched the actual
  `run_reminder_scheduler` Celery task to a real running worker, confirmed
  it correctly identified a real subscription (trial ending in 2 days,
  backdated via direct SQL) and returned `trial_reminders_sent: 1`,
  confirmed the audit log entry exists in the real database, then
  re-triggered the task a second time and confirmed `trial_reminders_sent:
  0` -- the dedup genuinely works against a real database, not just in an
  isolated unit test.
- `pyflakes` clean across `app/` (same 20 pre-existing, intentional model-
  registration imports, unrelated to this phase).

### No frontend changes

Every notification is a backend-only, async side effect of an action the
frontend already performs (register, subscribe, pause, pay, etc.) --
there's no UI surface for "an email was sent" to display, matching
exactly how the original 3-event notification system (Module 2) also
required zero frontend changes.

---

## Phase 6A (Runtime Verification): Full Stack E2E Testing (unreleased)

Real, live verification of the running application — not just static code
reading. FastAPI + Redis + Celery Worker + Celery Beat all run together;
every claim below is backed by an actual HTTP response, an actual database
row, or an actual generated file — see the conversation transcript for full
command-by-command output.

### Verified live (no application code changes needed — all correct)

- Full subscription lifecycle end-to-end against a running stack: create →
  trial → activate → (scheduler-generated invoice) → pay → upgrade
  (proration invoice generated correctly) → downgrade (net credit,
  correctly generates no invoice) → pause → resume → cancel. Every step's
  audit-log entry confirmed present and accurate.
- **The Celery Beat scheduler genuinely works**: backdated a real billing
  cycle's `next_billing_date`, waited for the actual periodic task to
  fire (not simulated), confirmed the worker log shows
  `run_billing_cycle_scheduler` executing and returning
  `invoices_created: ['INV-...']`, then confirmed via the API that the
  invoice really exists. **Documented requirement: Celery Beat + a worker
  must both be running continuously for scheduled billing to ever
  happen** — `uvicorn` alone is not sufficient.
- Every dashboard analytics figure (total/active/trial/cancelled
  customers, total plans, active/cancelled subscriptions, total revenue,
  MRR, ARR, successful/failed payments, total refunds) cross-checked
  against raw SQL run directly against the same database — every single
  number matched exactly.
- All 15 report combinations (5 types × csv/xlsx/pdf) regenerated and
  re-validated after the Phase 6A analytics changes — still all valid.
- Full error-handling matrix tested live: 401 (missing token, garbage
  token), 403 (role-gated), 404, 422 (missing field, malformed UUID path
  param — confirmed this degrades to 422, not a 500 crash), 409 (double
  payment).
- JWT lifecycle: forced immediate access-token expiry
  (`ACCESS_TOKEN_EXPIRE_MINUTES=0`), confirmed a genuinely-expired token
  is rejected with 401, then confirmed the refresh endpoint issues a
  valid new token pair.

### Confirmed gap (not fixed — needs a design decision, not silent implementation)

- **No rate limiting (429) exists anywhere in this codebase.** Confirmed
  via exhaustive search — no middleware, no library, nothing. If this
  matters for production, it needs its own scoped decision (which
  endpoints, what limits, per-IP vs per-user, sliding window vs token
  bucket) rather than being bolted on silently.

### Verified

- Full suite: 198/198 passing, re-run after this session's changes.

---

## Phase 6A: QA Audit & Confirmed Fixes (unreleased)

A rigorous QA pass against a large list of claimed issues -- each one verified
against the actual code before anything was changed. Two genuine gaps were
found and fixed; several claimed issues were investigated and found to
already be correct (documented below so they aren't "fixed" twice).

### Added

- **MRR / ARR** on `GET /analytics/dashboard` — `mrr` (sum of active
  subscriptions' plan prices, annual plans normalized to a monthly figure)
  and `arr` (`mrr x 12`). New `SubscriptionRepository.monthly_recurring_revenue()`.
- **`trial_customers` / `cancelled_customers`** on the same endpoint —
  distinct-customer counts (not subscription counts), generalizing the
  existing `count_active()` pattern via new
  `CustomerRepository.count_by_subscription_status(status)` (kept
  `count_active()` as a thin backward-compatible wrapper around it).
- 4 new tests in `tests/test_analytics_api.py`: MRR/ARR reflect a real
  active subscription's price, annual-plan MRR normalization is correct,
  cancelled-customer and trial-customer counts are correct.

### Investigated and confirmed already correct (not bugs)

- Revenue/payment analytics query logic — re-read `sum_paid_amount()` and
  the payment status counts; both correct, matching the extensive live
  verification already done in Phase 2.
- "Subscribe → Invoices/Payments empty" — this is the intended, by-design
  trial-first billing workflow (`create_subscription` never generates an
  invoice; only the Celery Beat scheduler or a mid-cycle plan change does).
  Flagged as an operational point, not a code bug: this requires Celery
  Beat + a worker actually running continuously to ever fire.
- "Reactivate a cancelled subscription" — `CANCELLED` is a deliberate
  terminal state in the state machine (zero valid outgoing transitions).
  Not implemented without an explicit decision, since un-cancelling has
  real business/audit-trail implications.

### Verified

- Full suite: 198/198 passing (195 existing + 3 net new).
- No existing endpoint's shape changed except the additive fields above.

---

## Phase 5: Reports & Export Module (unreleased)

Five admin-only report endpoints (revenue, customers, subscriptions,
payments, refunds), each exportable as CSV, Excel, or a summary PDF. No
schema change. Reports are synchronous (no background job queue —
explicitly out of scope for this phase).

### Added

- **`GET /reports/{revenue|customers|subscriptions|payments|refunds}`** —
  `format=csv|xlsx|pdf` (default `csv`, validated at the query-param layer
  itself via a regex pattern, so an invalid value never reaches
  application code). `date_from`/`date_to` supported only on revenue and
  payments, matching exactly what Phase 2's analytics already supported.
- **`app/services/report_service.py`** (new) — gathers report data by
  reusing `AnalyticsService` (Phase 2) for every summary number and
  existing repository `list_all` methods for every detail row. Zero
  aggregation logic of its own.
- **`app/services/report_export_service.py`** (new) — renders a report as
  CSV (stdlib), Excel (`openpyxl`, `Summary` + `Detail` sheets), or PDF
  (ReportLab, visually consistent with the Phase 4 invoice PDF). Never
  touches the database.
- **`PaymentRepository`** — added optional `date_from`/`date_to` params
  (new trailing, backward-compatible). Needed because the Payment
  Report's detail rows would otherwise silently ignore the date range
  that its summary (via `AnalyticsService`) already respected — a real
  inconsistency caught and fixed during this phase's own testing.
- `openpyxl==3.1.5` added to `requirements.txt` (real, non-test
  dependency).
- 13 new tests (`tests/test_reports_api.py`, new file): authorization (all
  5 endpoints × admin-succeeds/non-admin-403/unauthenticated-401), every
  report × every format returns valid, correctly-typed content, invalid
  format → `422`, per-report-type content correctness (each report's
  detail rows genuinely contain the seeded record), and date-range
  filtering genuinely excludes out-of-range data for both revenue and
  payments.

### Explicitly not done (by design, per phased plan)

- No deployment changes, no email scheduling, no background report
  generation, no Admin Dashboard redesign.

### Verified

- Full suite: 195/195 passing (182 existing + 13 new).
- OpenAPI schema: 45 paths (40 + 5 new); no existing path's shape changed.
- Live, real-server verification of all 15 report×format combinations —
  every CSV parses correctly, every XLSX opens correctly with the right
  sheets/headers, every PDF is a genuine, correctly-rendered document.
  Confirmed live: `422` for an invalid format, `403` for a regular
  customer, `401` unauthenticated, and that a date range genuinely
  excludes out-of-range data.

---

## Phase 4: Invoice PDF Generation (unreleased)

Adds `GET /invoices/{invoice_id}/pdf` — a professional, single-page PDF
of an invoice, generated entirely in-memory via ReportLab (already a
dependency, never used until now). No schema change, no file persisted
to disk.

### Added

- **`app/services/invoice_pdf_service.py`** (new) — the only new backend
  code this phase. Builds the PDF layout (header, customer block, summary
  table, line items, footer) from data pulled entirely through the
  existing repository layer — zero new query logic.
- **`GET /invoices/{invoice_id}/pdf`** in `app/api/v1/invoices.py` — reuses
  `InvoiceService.get_invoice(invoice_id, requesting_user=current_user)`,
  the exact same ownership check (Phase 1D) already used by
  `GET /invoices/{id}` and its sub-resources: `403` for another customer's
  invoice, `404` if it doesn't exist, full access for admins.
- PDF contents: company name, invoice number/date, customer name/email,
  subscription plan, billing interval, amount/currency, invoice status,
  payment status (from the invoice's most recent `Payment`, "No payment
  yet" if none), payment date, due date, the full line-item breakdown
  (reusing Module 2's existing invoice line items as-is), and a footer
  with the generation timestamp.
- `pdfminer.six` added as a **test-only** dependency (`requirements.txt`)
  so the test suite can extract and assert on real PDF text content
  instead of only checking "it's *a* PDF."
- 7 new tests (`tests/test_invoice_pdf.py`, new file): successful
  generation, real content verification via text extraction, missing-auth
  `401`, cross-customer `403`, admin `200`, invalid invoice ID `404`, and
  an unpaid invoice (no `Payment` record) rendering gracefully instead of
  crashing.

### Explicitly not done (by design, per phased plan)

- No report/CSV/Excel export, no emailing PDFs, no deployment changes, no
  UI redesigns.

### Verified

- Full suite: 182/182 passing (175 existing + 7 new).
- OpenAPI schema: 40 paths (39 + 1 new); no existing path's shape changed.
- Live, real-server verification (not just pytest): generated a real PDF
  for a real paid invoice with proration line items, confirmed via `file`
  it's a genuine PDF 1.4 document, and via `pdftotext` that every required
  field renders correctly, including the full subtotal/tax/total
  breakdown. Confirmed live: `401` unauthenticated, `403` cross-customer,
  `200` for admin, `404` for a nonexistent invoice ID.

---

## Phase 2: Analytics Module (unreleased)

Read-only, admin-only aggregation endpoints for the future Admin
Dashboard. No new database tables, no schema migration — every metric
is computed on demand from the existing schema, reusing the existing
repository layer wherever a method already did what was needed.

### Added

- **`GET /analytics/dashboard`** — total/active customers, total plans,
  active/cancelled subscriptions, total revenue, successful/failed
  payments, total refunds.
- **`GET /analytics/revenue`** — total revenue, revenue by month, revenue
  by plan; optional `date_from`/`date_to` query params (inclusive,
  `YYYY-MM-DD`, filtered on `Invoice.paid_at`).
- **`GET /analytics/subscriptions`** — full status breakdown (active,
  trial, paused, past_due, cancelled). `expired_subscriptions` is always
  `0` and documented as such — `SubscriptionStatus` has no "expired"
  state in this schema.
- **`GET /analytics/payments`** — successful/failed/pending counts plus a
  monthly trend; optional `date_from`/`date_to`.
- **`GET /analytics/refunds`** — status breakdown plus total refunded
  amount. `completed_refunds`/`failed_refunds` are documented as the
  closest equivalents to "approved"/"rejected" — `RefundStatus` has no
  such states, so the real enum vocabulary is used and mapped in the docs
  rather than inventing mismatched field names.
- All five endpoints require `get_current_superuser` — non-admins get
  `403`, matching the Phase 1C pattern exactly.
- `app/services/analytics_service.py`, `app/schemas/analytics.py`,
  `app/api/v1/analytics.py` (all new).
- Extended (not duplicated) three repositories with new, backward-
  compatible capabilities:
  - `PaymentRepository` / `RefundRepository`: new optional trailing
    `status` filter parameter on `_filtered_query`/`list_all`/`count_all`
    — verified via grep that every existing positional caller is
    unaffected before making the change, confirmed by the full
    pre-existing suite passing unmodified afterward.
  - `InvoiceRepository`: new `sum_paid_amount`, `revenue_by_month`,
    `revenue_by_plan`.
  - `CustomerRepository`: new `count_active`.
  - Everything else reuses methods that already existed (e.g.
    `SubscriptionRepository.count_all(status=...)`, `PlanRepository.count()`
    via the inherited `BaseRepository.count()`) — zero duplicated query
    logic.
- 16 new tests (`tests/test_analytics_api.py`, new file): authorization
  (all 5 endpoints × admin-succeeds / non-admin-403 / unauthenticated-401)
  and correctness (dashboard reflects created data, revenue totals match
  a real paid invoice, revenue-by-plan attribution, date-range filtering
  genuinely excludes out-of-range data, subscription breakdown sums to
  the total, payment counts are internally consistent, a forced payment
  failure is counted, refund counts and total amount are correct).

### Explicitly not done (by design, per phased plan)

- No Admin Dashboard frontend, charts, reports, invoice PDF generation,
  export functionality, or deployment changes.

### Verified

- Full suite: 175/175 passing (159 existing + 16 new).
- OpenAPI schema: 39 paths (34 + 5 new); every pre-existing path's shape
  unchanged.
- Live, real-server verification (not just pytest) of all 5 endpoints
  against real accumulated data, cross-checked by hand: revenue-by-plan
  entries sum to the same total as `total_revenue`; subscription/payment/
  refund breakdowns sum to their respective totals; date-range filtering
  on `/revenue` confirmed to change the result; 403 confirmed for a
  regular customer on all 5 endpoints, 200 confirmed for an admin.

---

## Phase 1D: Ownership Enforcement for Subscriptions, Invoices, Payments & Refunds (unreleased)

Closes the gap explicitly flagged at the end of Phase 1C: extends the
same ownership-enforcement rule from `Customer` to every resource that
belongs to one. No database migration needed — pure service/router
logic reusing the `Customer.user_id` link from Phase 1A.

### Added

- **`app/services/ownership.py`** (new) — `assert_owns_customer` (single-
  resource enforcement) and `effective_customer_filter` (list-endpoint
  scoping: non-admins are always forced to their own customer, silently
  overriding whatever `customer_id` they passed or omitted, rather than
  validating-and-rejecting).
- **Subscriptions**: ownership enforced on every method in
  `SubscriptionService` that loads a subscription by ID
  (get/activate/pause/resume/cancel/change_plan/preview_proration),
  `create_subscription` verifies the target `customer_id` belongs to the
  caller, `list/count_subscriptions` scoped for non-admins.
  `GET /subscriptions/{id}` and `GET /subscriptions/{id}/billing-cycles`
  now require authentication (previously public).
- **Invoices**: ownership enforced in `InvoiceService.get_invoice` /
  `list_invoices` / `count_invoices`; the `/payments` and `/refunds`
  sub-resource endpoints check the parent invoice's ownership first.
- **Payments**: ownership enforced in
  `PaymentGatewayService.process_payment` and in the `GET /payments`
  list/detail endpoints (the detail endpoint resolves the payment's
  invoice to determine its owning customer, since `Payment` has no
  `customer_id` column of its own).
- **Refunds**: ownership enforced in `RefundService.create_refund` /
  `get_refund` / `list_refunds` / `count_refunds`.
- 25 new tests (`tests/test_ownership_enforcement.py`, new file) — a
  shared fixture builds two fully independent customers (each with an
  activated subscription and a paid invoice), then exercises
  cross-customer 403s, list-scoping, own-access-still-works, and
  admin-bypass across all four resource types.

### Fixed (test-only, no application behavior change)

- 8 pre-existing tests broke from the new auth requirements — 7 were
  simply missing an `Authorization` header on a call to an endpoint that
  used to be public (`GET /subscriptions/{id}`,
  `GET /subscriptions/{id}/billing-cycles`); fixed by adding the header.
  The 8th (`test_payments_list_supports_customer_id_filter`) had an
  assertion describing exactly the weaker pre-Phase-1D behavior ("pass
  someone else's customer_id, expect empty results") — rewritten to
  verify the new, stronger guarantee (a non-admin's filter is always
  silently overridden to their own scope, so the correct check is from
  the *other* user's perspective, not by trying to trick the filter).

### Explicitly not done (by design, per phased plan)

- No Admin Dashboard, analytics, reports, or invoice PDF generation.

### Verified

- Full suite: 159/159 passing (134 existing + 25 new).
- OpenAPI schema: 34 paths, unchanged from Phase 1C — pure enforcement
  addition, no new/removed/renamed endpoints.
- Live, real-server security tests (not pytest) across all four resource
  types: two independent customers, confirmed genuine `403`s on every
  cross-customer access attempt (view/pause/create-for subscription,
  view invoice/its payment history, refund an invoice, view a refund by
  ID), confirmed legitimate own-access and the admin bypass both continue
  working, all over real HTTP against the real database.

---

## Phase 1C: Ownership Enforcement & Role-Based Authentication (unreleased)

Adds real security enforcement on top of Phase 1A/1B's ownership link,
plus a minimal admin role. Scoped tightly per plan: only the `Customer`
resource gained ownership enforcement, and only Plan mutations + the
customer list became admin-only. No database migration needed (reuses
`User.is_superuser`, already present since Module 1 but never checked
anywhere until now).

### Added

- **`GET /auth/me`** — returns the authenticated user's own account,
  including `is_superuser`.
- **`get_current_superuser`** dependency (`app/api/deps.py`) — 401 if
  unauthenticated, 403 if authenticated but not an admin.
- **Customer ownership enforcement**: `CustomerService.get_customer()`
  accepts an optional `requesting_user`; when provided, a non-admin may
  only access the `Customer` linked to their own account. Threaded
  through `GET`/`PATCH /customers/{id}` (the latter via
  `update_customer`). `GET /customers/{id}` now requires authentication
  (previously public) — verified this doesn't affect the frontend, since
  every authenticated session already sends a bearer token on every
  request regardless of whether the endpoint required one.
- **Admin-only endpoints**: `POST /plans`, `PATCH /plans/{id}`,
  `POST /plans/{id}/archive`, `GET /customers` (list) now require
  `get_current_superuser`. `GET /plans`, `GET /plans/{id}` remain public.
- 15 new tests across `tests/test_auth_me.py` (new file) and
  `tests/test_customer_api.py`/`tests/test_plan_api.py` (expanded):
  `/auth/me` behavior, cross-user 403s on `GET`/`PATCH /customers/{id}`,
  admin-bypass 200s, plan-mutation 403s for non-admins, list-customers
  403 for non-admins.
- `admin_auth_headers` test fixture (`tests/conftest.py`) — registers a
  user then flips `is_superuser` directly in the DB (there's no API to
  do this, by design), mirroring how a real deployment would bootstrap
  its first admin.

### Fixed (test-only, no application behavior change)

- ~57 existing tests across 8 files created a `Plan` as setup using a
  regular (non-admin) auth token, which now correctly returns 403. Fixed
  by routing plan creation through the new `admin_auth_headers` fixture
  in every affected test/fixture (`active_subscription_with_invoice` in
  `conftest.py`, plus `test_subscription_api.py`,
  `test_subscription_proration.py`, `test_pagination_regression.py`,
  `test_audit_log_api.py`, `test_refund_api.py`) — the tests' actual
  *subject matter* (proration, pagination, refunds, audit logs, etc.) is
  unchanged; only how their plan-creation setup step authenticates.

### Explicitly not done (by design, per phased plan)

- Subscriptions/invoices/payments/refunds are **not** ownership-scoped —
  only the `Customer` resource itself. See README section 13 for why
  this is a known, deliberate limitation rather than an oversight.
- No Admin Dashboard, analytics, reports, invoice PDF, or other new
  business features.

### Verified

- Full suite: 134/134 passing (119 existing + 15 new).
- OpenAPI schema: 34 paths (33 + `/auth/me`); `CustomerResponse` shape
  unchanged.
- Live, real-server security tests (not just pytest): two independently
  registered customers, confirmed Customer B gets 403 viewing/editing
  Customer A's record via raw HTTP, confirmed Customer A gets 403 on
  `GET /customers` and `POST /plans`, confirmed an admin (promoted via
  direct DB update, matching the fixture's bootstrap pattern) can view
  any customer, list all customers, and create a plan.
- Live end-to-end legitimate customer flow re-verified post-enforcement:
  register → login → create own customer → `/customers/me` → subscribe
  → activate → plan-change → pay → refund → update own profile — all
  succeed exactly as before, now with real ownership checks in place
  rather than an open door.

---

## Phase 1B: Customer Ownership Lookup Layer (unreleased)

Adds the read/write endpoint that makes Phase 1A's `Customer.user_id`
link actually usable, without adding any authorization/enforcement yet.
No existing API's request/response format changed.

### Added

- **`GET /customers/me`** — returns the authenticated user's linked
  `Customer`, `404` if none exists. Declared before `/{customer_id}` in
  the router (required — otherwise FastAPI would try to parse `"me"` as a
  UUID path parameter).
- `CustomerRepository.get_by_user_id`, `CustomerService.get_my_customer`.
- `POST /customers` now sets `Customer.user_id` from the authenticated
  caller automatically (`actor_id`, already threaded through for audit
  logging — no new parameter). This is what keeps the ownership link
  populated for every customer created from this point forward; without
  it, `GET /customers/me` would only ever work for the small number of
  records Phase 1A's one-time backfill could match by email.
  - Also rejects (`409`) creating a second customer for an account that
    already has one — mirrors the existing email-uniqueness check's
    style, prevents an unhandled `IntegrityError` from the new unique
    constraint on `user_id`.
- 5 new tests (`tests/test_customer_api.py`): 404-when-unlinked,
  200-with-correct-record, auth-required, cross-user scoping (one user's
  `/me` never returns another's customer), and the duplicate-customer
  409.

### Fixed (test-only, no application behavior change)

- `tests/test_pagination_regression.py::test_payments_list_supports_customer_id_filter`
  previously created a "different customer" reusing the same
  `auth_headers` token as a fixture that already had a linked customer —
  now correctly rejected by the new one-per-user constraint. Fixed by
  registering a genuinely separate user for that assertion, which is what
  the test actually intended to exercise.

### Explicitly not done (by design, per phased plan)

- No ownership *enforcement* — `GET/PATCH /customers/{id}` still has no
  access check; any authenticated user can view/edit any customer by ID,
  exactly as before this phase.
- No admin auth, admin dashboard, reports, analytics, or invoice PDF.

### Verified

- Full suite: 119/119 passing (114 existing + 5 new).
- Live end-to-end: register → login → `/customers/me` (404) → create
  customer → `/customers/me` (200, matching) → subscribe → activate →
  plan-change → pay → refund → profile update → login again →
  `/customers/me` still resolves correctly.
- OpenAPI schema: 33 paths (32 + exactly the one new route); no existing
  path's shape changed.

---

## Phase 1A: Customer Ownership Foundation (unreleased)

Adds the database-level ownership link between a `User` (auth account)
and its `Customer` (billing record) — schema only, no application code
reads this column yet (that's Phase 1B, above). No existing API changed.

### Added

- `customers.user_id` — nullable, unique, FK to `users.id`,
  `ON DELETE SET NULL`. Migration:
  `alembic/versions/bd0578485c27_phase_1a_add_customer_user_id_ownership_.py`.
- One-time backfill matching `Customer.email` to `User.email` (safe as a
  backfill specifically because both columns are independently unique,
  so the join can never fan out to more than one match either way).
- `Customer.user` / `User.customer` ORM relationship, lazy (`"select"`)
  loading only — no eager join added to any existing query.

### Verified

- Migration is fully reversible: `downgrade -1` → `upgrade head` round-trip
  tested, backfilled data came back identically.
- Unique constraint actually rejects duplicates (tested with an
  intentional duplicate assignment in a throwaway transaction, rolled
  back).
- Lazy loading confirmed by instrumented query counting, not assumed:
  fetching customers issues the same 1 query regardless of the new
  relationship; accessing `.user` on a linked customer fires exactly one
  additional on-demand query.
- Full suite: 114/114 passing, unmodified. OpenAPI schema: 32 paths,
  unchanged (`user_id` does not appear in any request/response schema at
  this stage).

### Migration report (dev database, at time of migration)

| Metric | Count |
|---|---|
| Total Customers | 5 |
| Successfully Linked | 1 |
| Unlinked Customers | 4 |
| Duplicate matches | 0 |
| Case-mismatch emails | 0 |

Unlinked customers were all test/demo records created directly via API
calls with a different email than the associated login, not through the
real registration UI (which always uses matching emails) — expected, not
a defect.

---

## Module 2 Gap-Fill: Email Notifications (unreleased)

A gap analysis against the official Module 1 and Module 2 written
requirements found exactly one missing piece: Module 2's "Payment Webhook
Handler → Notifications" subsection (trigger notifications for Payment
Successful, Payment Failed, Refund Successful) was never implemented. This
pass adds only that feature — no existing API, schema, or business logic
was changed. No database migration was required.

### Added

- **Email notifications** for payment succeeded, payment failed, and
  refund completed, dispatched asynchronously via the existing Celery +
  Redis infrastructure (`app/tasks/notification_tasks.py`,
  `app/services/notification_service.py`).
  - Wired into `PaymentWebhookHandlerService` (payment succeeded/failed)
    and, since this app's refund flow doesn't route through the payment
    webhook handler, directly into `RefundService._apply_refund` (the
    actual code path every refund — manual and auto-refund-on-cancellation
    — goes through) for refund completed.
  - Defaults to logging the notification instead of sending it
    (`SMTP_HOST` unset) so the feature works out of the box without a mail
    provider — same "simulate by default" philosophy as the mock payment
    gateway. Set `SMTP_HOST`/`SMTP_USERNAME`/`SMTP_PASSWORD` to send real
    email. Set `NOTIFICATIONS_ENABLED=false` to disable entirely.
  - Dispatch failures (e.g. broker unreachable) are logged and swallowed,
    never propagated — verified with a live test that a Redis outage
    cannot break payment or refund processing.
  - Tuned `task_publish_retry_policy` on the Celery app so a broker outage
    fails in ~1s instead of ~20s when a task is dispatched synchronously
    from request-handling code.
- 10 new tests (`tests/test_notification_service.py`) covering message
  building for all 3 event types, log-only default behavior, the
  disabled/missing-record no-op paths, dispatch integration from both the
  webhook handler and refund service, and the non-blocking guarantee.

### Verified

- Full suite: 114/114 passing (104 existing + 10 new).
- Live end-to-end test with a real Redis instance and a real Celery
  worker consuming actual queued tasks against the real database,
  confirming both `payment_succeeded` and `refund_completed` notifications
  fire with correct recipient/subject/body content.

---

## Module 1 & 2 Review Pass

A full review of Module 1 and Module 2 against the internship requirements,
covering database schema, services, routers, schemas, Celery tasks, and
tests. No new features were added — this pass only fixes bugs found during
review. All existing APIs, request/response formats, authentication, and
Docker configuration are unchanged. No database migration was required.

### Fixed

- **Pagination `total` was incorrect on 5 list endpoints.** `GET
  /subscriptions`, `GET /invoices`, `GET /payments`, `GET /refunds`, and
  `GET /audit-logs` computed `total` as the count of items on the *current
  page* rather than the true count of all matching rows. With more rows
  than one page, this capped `total` at `page_size`, causing any paginated
  client to conclude there was only one page and never surface rows beyond
  it.
  - Added `count_all(...)` to `SubscriptionRepository`, `InvoiceRepository`,
    `PaymentRepository`, `RefundRepository`, and `AuditLogRepository`,
    mirroring the filters already used by each `list_all(...)`.
  - Added matching `count_*` methods to `SubscriptionService`,
    `InvoiceService`, `RefundService`, and `AuditLogService`.
  - Updated the five routers to use the real count instead of `len(items)`.
  - No response shape change — `total` now simply holds the correct value.

- **`PaymentRepository.count_for_invoice` loaded every row into memory to
  count them** (`len(list(...))`) instead of issuing a `SELECT COUNT(*)`.
  Replaced with a proper aggregate query. No behavior change, pure
  performance fix (this runs on every mock payment attempt to compute the
  next `attempt_number`).

### Added

- **`GET /payments` now supports a `customer_id` filter**, in addition to
  the existing `invoice_id` filter — bringing Payment History to parity
  with Invoices and Refunds, which already supported filtering by
  customer. Implemented via a join through `Invoice` (Payment has no
  `customer_id` column of its own); no schema change. Purely additive —
  the existing `invoice_id` filter is unchanged.

- **5 new regression tests** (`tests/test_pagination_regression.py`)
  proving `total` reflects the full matching row count (not just the
  current page) for subscriptions, invoices, refunds, and audit logs, plus
  a test for the new `customer_id` filter on payments.

### Removed

- Two unused imports (`json` in `webhook_sender_service.py`, `Customer` in
  `refund_service.py`) — dead code, no behavior change.

### Test suite

104/104 tests passing (99 pre-existing + 5 new regression tests), plus a
live verification against a running instance with real Postgres data
confirming the fix (not just the isolated test database).
