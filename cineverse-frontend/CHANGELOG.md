# Changelog

## Original Scope Completion: Paid Date, Rate Limiting, Activity Timeline (unreleased)

The final three items from the original planned scope.

### 1. Paid Date display

`InvoiceDetailModal.jsx` now shows a "Paid" date (in emerald, next to
"Due"), shown only when `invoice.paid_at` is actually set — matching the
existing conditional pattern already used for Discount and Payment
Method. The backend field existed since Phase 6C; this was the missing
display.

### 2. Rate Limiting (429)

No frontend changes required — the existing `extractErrorMessage`
(Phase 6A) already handles a `429` response with a clear, friendly
message ("You're doing that too quickly..."), and this is now genuinely
reachable for the first time, since the backend previously never
returned one.

### 3. Account-wide Activity Timeline

- **New `/activity` page** (`ActivityPage.jsx`) — the full, paginated,
  account-wide timeline via the backend's new `GET /audit-logs/me`.
  Reuses the *exact same* `RecentActivity` component the Dashboard's
  smaller preview card already used (given an optional `limit` prop,
  default `8`, so the existing Dashboard usage is completely
  unaffected) — no new timeline-item UI built from scratch.
- **`auditLogService.listForMe()`** (new) wraps the endpoint.
- Added to the customer sidebar nav (between Profile and Logout) and a
  "View All" link on the Dashboard's Recent Activity card.
- **`AuthContext.logout()`** now calls the backend's new
  `POST /auth/logout` (via a new `authService.logout()`) before clearing
  stored tokens — best-effort, never awaited, and any failure is
  swallowed, so a slow network or a dead backend never prevents someone
  from actually logging out.

### Verified

- `npm run build` — clean (`ActivityPage` got its own lazy-loaded chunk;
  main bundle size essentially unchanged).
- `npm run lint` — clean (81 files, up from 80, same 2 pre-existing
  warnings).
- Verified the exact request/response shapes live against the real
  backend: `POST /auth/logout` returns `204`, `GET /audit-logs/me`
  returns the expected paginated shape with real recorded events.

---

## Final Production Readiness Review (unreleased)

A systematic cross-check: for every backend endpoint, confirmed there's
an actual frontend UI calling it. Found exactly one gap.

### Added

- **`AdminAuditLogPage`** (`/admin/audit-log`) — `auditLogService.list()`
  (wrapping `GET /audit-logs`) already existed but had no page using it.
  Follows the exact same list + pagination + entity-type-filter pattern
  as every other admin page (`AdminRefundsPage`, `AdminPlansPage`, etc.).
  Registered in the admin sidebar and routes, lazy-loaded like every
  other authenticated page.

### Backend authorization fix (see the backend's own CHANGELOG)

The backend endpoint this new page calls was found to have no ownership
enforcement at all — any authenticated user could see any other
customer's audit trail. Fixed backend-side; this page correctly requires
admin as a result (matching every other admin-only page in this app).

### Verified

- Full backend↔frontend cross-check: every other backend endpoint
  already has a corresponding frontend caller — no other gaps found.
- `npm run build` — clean (main bundle 432.71 kB, essentially unchanged;
  the new page got its own lazy chunk).
- `npm run lint` — clean (80 files, up from 79, same 2 pre-existing
  warnings).

---

## Final UI/UX Polish (unreleased)

Audit-first pass, frontend only -- no backend file was touched. Every
change below is a genuine, verified gap or improvement, not a redesign;
most of the app (branding, theme, subscription CRUD, invoice actions)
was already solid and is documented as such in the Final Report rather
than being needlessly reworked.

### Fixed (real bugs found during audit)

- **Favicon was never actually linked** — `index.html` still pointed to
  Vite's default `/vite.svg` despite a real `favicon.svg` existing in
  `public/`. That file's colors (purple) also didn't match the
  established brand red, so it was replaced with a small on-brand SVG
  mark (dark rounded square, red ring, red play triangle) and properly
  linked.
- **No keyboard focus indicator anywhere** — every button variant
  (`.btn-primary`, `.btn-secondary`, `.btn-ghost`), the `Modal` close
  button, and every nav link (`Sidebar`, `AdminSidebar`, `Navbar`) had
  no visible `:focus-visible` state at all. Added a consistent focus
  ring system (new `.focus-ring` utility class plus ring styles built
  into each button variant) across all of them.
- **Native `window.confirm()`** for archiving a plan — replaced with a
  new reusable `ConfirmDialog` component matching the app's actual
  design system, supports a loading state during the request (a native
  browser dialog can't).
- **`AdminCustomersPage` had zero edit capability** — list-only, no way
  to update a customer's details from the admin side at all, despite
  the backend's `PATCH /customers/{id}` already supporting it (and
  already being admin-accessible since Phase 1D). Added a new
  `CustomerEditModal`, reusing the exact same field set/validation as
  the customer-facing `ProfilePage`.

### Improved

- **Route-based code splitting** — every authenticated/admin page is
  now `React.lazy()`-loaded behind a `Suspense` boundary (landing/login/
  register/404 stay eager, since they're small and on the critical
  first-paint path). Measured, real result: the main JS bundle dropped
  from **572.73 kB to 432.34 kB**, and the "chunks larger than 500 kB"
  build warning that had appeared in every single build across this
  entire project is now gone entirely.
- Added `aria-label`s to icon-only action buttons that only had a
  `title` attribute before (Plans edit/archive, Customers edit).

### Verified already correct (audited, not changed)

- **Branding** — "CineVerse" is already a well-suited, movie-themed name
  (not generic SaaS), already consistent across logo, browser title,
  login/register, dashboard, navbar, sidebar, and footer. Kept as-is.
- **Theme** — the dark navy + brand-red glassmorphism design system
  (`index.css`) already has consistent border radius, shadows,
  transitions, and disabled states across buttons/cards/forms. Not a
  Netflix/Disney+/Prime clone; kept as-is.
- **Subscription CRUD** — pause/resume/cancel already exist and already
  use a proper themed `CancelSubscriptionModal`, not a native dialog.
- **Plans CRUD** — add/edit/archive already fully exist (Phase 3).
- **Invoice actions** — view/download PDF/email invoice already exist
  (Phases 4, 6C).
- **Payment retry** — already fully functional via the existing
  `POST /payments/process` (confirmed working in Phase 6C); the button
  label was already fixed to say "Retry Payment" for a failed invoice.
- **Tables** — `Table.jsx` already wraps in `overflow-x-auto` with a
  `min-w-[640px]` inner table, so narrow viewports already get a
  horizontal scroll rather than broken/overflowing layout.
- **Menu buttons** — mobile hamburger menus (`Topbar`, `AdminTopbar`,
  `Navbar`) already had proper `aria-label`s.
- No orphaned/unused component files found in a full repo scan.

### Explicitly not done

- No rebranding (CineVerse is good, per the request's own instruction to
  keep it if so).
- No architecture rewrite — code-splitting was added without touching
  routing structure, state management, or component boundaries.
- No backend changes of any kind — authentication, billing, payments,
  analytics, reports, scheduler, email automation, database schema, and
  every backend API were left completely untouched, per the explicit
  scope of this phase.

### Verified

- `npm run build` — clean, and the persistent bundle-size warning is
  gone.
- `npm run lint` — clean (79 files, same 2 pre-existing, unrelated
  warnings).

---

## Phase 6C: Invoice & Payment Improvements (unreleased)

Extends the invoice detail view with the backend's new denormalized
fields and two new actions — no existing page was redesigned.

### Added

- **`invoiceService.emailInvoice(invoiceId)`** (new) — wraps the
  backend's new `POST /invoices/{id}/email`.
- **`src/utils/download.js`** — added `printBlob(blob)`: opens a fetched
  PDF blob in a new tab so the browser's own native PDF viewer (with its
  own print button) handles printing — no custom print layout needed.
  Falls back to a plain download if the popup is blocked, rather than
  silently doing nothing.
- **`InvoiceDetailModal.jsx`**:
  - New "Bill To" block showing customer name/email/billing address/
    country (from the backend's new denormalized fields).
  - Payment method now shown once a payment exists.
  - A discount line appears in the summary grid only when
    `discount_amount > 0` (currently always 0 — no discount feature
    exists yet — so this is dormant until the backend ever populates it,
    not visible today).
  - A "Partially Refunded" / "Fully Refunded" badge next to the invoice
    status badge, driven by the backend's new `refund_status` field.
  - New "Print" button (via `printBlob`) and "Email Invoice" button
    (via the new service method), both with loading states and error
    toasts, matching the existing "Download PDF" button's pattern
    exactly.
  - The existing "Pay Now" button now reads "Retry Payment" specifically
    when the invoice status is `failed` — the underlying action was
    already identical (same modal, same endpoint); this is a label-only
    clarity fix, not a new capability.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean (77 files, same 2 pre-existing warnings).
- Verified the exact request/response shapes this page relies on live
  against the real backend (the enriched `GET /invoices/{id}` fields, and
  `POST /invoices/{id}/email` returning `202`).

---

## Phase 6A (Runtime Verification): Full Stack E2E Testing (unreleased)

### Fixed

- **Real bug found via live error-response testing**: `extractErrorMessage`
  checked the generic top-level `message` *before* the field-level
  `details` array, meaning the more specific, actionable validation
  message (e.g. "Field required" for a specific field) could never
  actually surface — the backend's structured error responses always
  include a top-level message too, so that branch was dead code. Fixed
  to check `details` first and include which field failed (e.g.
  `"email: Field required"` instead of the generic "One or more fields
  failed validation"). Verified against the exact real 422 response
  bodies captured live from the backend.

### Verified live (no code changes needed)

- Confirmed the frontend's error-message logic (network/timeout/429/500/
  structured backend errors) produces a correct, clear message for every
  real error shape observed from the live backend during this session's
  testing (401, 403, 404, 422, 409).
- Regenerated all 15 report combinations after the backend's Phase 6A
  analytics changes — still all valid.

### Known limitation of this verification pass

- **No browser automation tool is available in this environment.** Visual
  claims (clicking through the rendered UI, viewport/responsive behavior
  at specific breakpoints, browser back/forward navigation) could not be
  tested by literally driving a browser. Substituted with: (1) live
  verification of every underlying API call and response the UI depends
  on, (2) code-level confirmation of the Tailwind responsive classes and
  React Router `<Link>`/`<NavLink>` usage already in place (React
  Router's history-based navigation correctly supports back/forward by
  default; nothing in this codebase uses `window.location` in a way that
  would break it). This is a real gap in *how* it was verified, not a
  claim that it works — flagging clearly rather than asserting confidence
  I don't have.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean (77 files, same 2 pre-existing warnings).

---

## Phase 6A: QA Audit & Confirmed Fixes (unreleased)

### Fixed

- **CineVerse logo wasn't clickable** — was a plain `<span>` in both
  `Sidebar.jsx` and `AdminSidebar.jsx`. Now a `Link` to `/dashboard`
  (customer) or `/admin/dashboard` (admin), closing mobile nav on click.
- **Missing `.gitignore`** — the project had none at all. Without it,
  `node_modules/`, build output, and `.env` (secrets) would all be
  committable by accident. Added the standard Vite/React pattern. This
  also fixed a real, surprising side effect discovered during this pass:
  a newer `oxlint` version uses `.gitignore` to decide what to skip, so
  without one it was linting all of `node_modules` (2718 files, 145
  false "errors") instead of just this project's 77 source files.
- **Error messages for network failures/timeouts/5xx/429** —
  `extractErrorMessage` previously fell through to axios's raw message
  ("Network Error", "timeout of 10000ms exceeded") for anything without a
  structured backend error body. Now gives a clear, actionable message for
  each case.

### Added

- `AdminDashboardPage.jsx` now displays MRR, ARR, Trial Customers, and
  Cancelled Customers (backend added these in Phase 6A) — additive stat
  cards on the existing grid, not a redesign.

### Investigated and confirmed already working (not bugs)

- All 7 customer sidebar nav items correctly map to their routes —
  diffed against `AppRoutes.jsx` line by line, no mismatch found.
- The Profile module already validates, shows loading states, toasts on
  success/error, and persists after reload.
- Duplicate-request prevention (buttons disabled during in-flight
  requests) and active-page highlighting were already correctly
  implemented across the app.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean, and now correctly scoped to 77 files (see the
  `.gitignore` fix above).

---

## Phase 5: Reports & Export (unreleased)

Adds a Reports page to the Admin Dashboard, wired to the backend's 5 new
`GET /reports/*` endpoints (Phase 5). No existing page was redesigned.

### Added

- **`src/services/reportService.js`** (new) — thin wrapper around
  `GET /reports/{revenue|customers|subscriptions|payments|refunds}`,
  reusing the exact same blob + `Content-Disposition`-filename download
  pattern already established by `invoiceService.downloadPdf` (Phase 4).
  Exports `REPORT_TYPES_WITH_DATE_RANGE` (`revenue`, `payments`) so the UI
  can gate the date-range inputs to only the report types the backend
  actually supports date filtering for.
- **`src/pages/admin/AdminReportsPage.jsx`** (new) — report type, export
  format (CSV/Excel/PDF), and optional date-range selection, with a
  "Download Report" button showing a spinner + "Generating…" while in
  flight and a toast on failure.
- **`src/components/layout/AdminSidebar.jsx`** — added a "Reports" nav
  item.
- **`src/routes/AppRoutes.jsx`** — registered `/admin/reports`, wrapped in
  the existing `AdminRoute` + `AdminLayout` (Phase 3), no new routing
  infrastructure needed.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean (same 2 pre-existing, unrelated warnings; file
  count 77, up from 75).
- Verified the exact request shapes this page sends (format + optional
  date params) live against the real backend for both a date-range-
  supporting report (revenue) and a non-date-range report (customers),
  confirming correct `Content-Type` and `Content-Disposition` for each.

---

## Phase 4: Invoice PDF Download (unreleased)

Adds a "Download PDF" button to the invoice detail view, wired to the
backend's new `GET /invoices/{id}/pdf` (Phase 4). No existing invoice
page was redesigned.

### Added

- **`src/services/invoiceService.js`** — added `downloadPdf(invoiceId)`,
  fetching the PDF as a blob and reading the filename straight from the
  backend's `Content-Disposition` header (no hardcoded naming
  convention).
- **`src/utils/download.js`** (new) — a small, generic
  `downloadBlob(blob, filename)` helper, reusable for any future blob
  download in the app, not invoice-specific.
- **`src/components/invoices/InvoiceDetailModal.jsx`** — new "Download
  PDF" button with a loading state ("Downloading…" + spinner) and a
  toast on failure.

### Deliberately not added to `InvoicesPage.jsx`'s list rows

The list only shows a summary line with a click-to-open-detail
interaction; adding a second per-row action there would have required
reworking that interaction (stopping click-propagation, adding an
actions column) — which felt like exactly the "redesign an existing
invoice page" this phase was asked to avoid. The detail modal, where an
invoice's full contents are actually shown, was the correct, more
conservative place for this.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean (same 2 pre-existing, unrelated warnings; file
  count 75, up from 74).
- Verified the filename-extraction regex against the exact
  `Content-Disposition` header format the backend actually sends
  (`attachment; filename="INV-202607-....pdf"`), confirmed correct
  extraction.
- Every request/response shape this button relies on was verified live
  against the real backend — see the backend's own CHANGELOG for the
  live PDF-generation and authorization verification.

---

## Phase 3: Admin Dashboard (unreleased)

Builds the Admin Dashboard on top of Phase 1C's `AdminRoute`/`isSuperuser`
and Phase 2's analytics endpoints. A second, parallel app shell alongside
the existing customer-facing one — no existing customer page, route, or
flow was touched beyond one small addition (see below).

### Added

- **`src/services/analyticsService.js`** (new) — wraps the 5 Phase 2
  `/analytics/*` endpoints.
- **`src/services/planService.js`** — added `create`/`update`/`archive`,
  wrapping `POST/PATCH /plans` and `POST /plans/{id}/archive`. The backend
  has supported these since Module 1 (admin-only since Phase 1C), but no
  frontend caller existed until this phase.
- **6 admin pages** (`src/pages/admin/`): `AdminDashboardPage`,
  `AdminCustomersPage`, `AdminPlansPage`, `AdminSubscriptionsPage`,
  `AdminPaymentsPage`, `AdminRefundsPage`.
- **`src/components/admin/PlanFormModal.jsx`** (new) — create/edit form
  used by the Plans page.
- **`src/layouts/AdminLayout.jsx`**, **`src/components/layout/AdminSidebar.jsx`**,
  **`src/components/layout/AdminTopbar.jsx`** (all new) — a second app
  shell, structurally mirroring `AppLayout`/`Sidebar`/`Topbar` but with no
  `CustomerSetupGate` (an admin account has no billing profile to set up).
- **`src/routes/AppRoutes.jsx`** — registered `/admin/dashboard`,
  `/admin/customers`, `/admin/plans`, `/admin/subscriptions`,
  `/admin/payments`, `/admin/refunds`, all wrapped in the existing
  `AdminRoute` (Phase 1C) + the new `AdminLayout`.
- **`src/context/AuthContext.jsx`** — the existing `GET /auth/me` call (made
  for role-loading since Phase 1C) now also captures `email`/`full_name`
  into a new `accountInfo` field, so `AdminTopbar` can show the admin's own
  identity without a second API call.
- **`src/pages/LoginPage.jsx`** — after a successful login, calls
  `authService.getMe()` directly (not via context state, to avoid a race
  with the async role-loading effect) to decide whether to land on
  `/dashboard` or `/admin/dashboard`. Verified live that a regular
  customer's `is_superuser: false` leaves this behavior unchanged.
- **`src/components/layout/Sidebar.jsx`** (customer-facing) — one small,
  conditional addition: an "Admin Panel" link, visible only when
  `isSuperuser`, so an admin account can actually discover and reach the
  new section from within the app (otherwise `/admin/dashboard` would only
  be reachable by typing the URL directly).

### No new dependencies

No charting library was added. The Dashboard's revenue/subscription/
payment/refund numbers are shown as stat cards (reusing the existing
`StatCard` component from the customer dashboard), not graphs — charts
weren't explicitly requested, and this phase's brief also excluded report
export and PDF generation, so no new dependency was introduced for
visualization either.

### Security

- Every admin page is only reachable through `AdminRoute`, unchanged from
  Phase 1C: a logged-in non-admin is redirected to `/dashboard` before any
  admin page component ever mounts, so no admin-only API call is ever
  attempted on their behalf.
- Verified live against the real backend that every genuinely new request
  shape this phase introduces (plan create/update/archive) succeeds for an
  admin token and correctly receives `403` for a regular customer token.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean (same 2 pre-existing, unrelated fast-refresh
  warnings; file count 74, up from 63).
- Live verification against the real backend: admin login → `GET
  /auth/me` confirms `is_superuser: true`; plan create → update (including
  changing `billing_interval`) → archive all succeed for the admin token
  and correctly `403` for a regular customer token; confirmed a regular
  customer's `GET /auth/me` still returns `is_superuser: false`, so the
  new login-redirect logic leaves their destination (`/dashboard`)
  unchanged.

---

## Phase 1C: Role Loading & AdminRoute (unreleased)

The backend added `GET /auth/me` and real ownership enforcement (Phase
1C). This adds the frontend pieces needed to know about admin status,
without building any admin UI yet.

### Added

- **`src/services/authService.js`** — `getMe()`, wrapping `GET /auth/me`.
- **`src/context/AuthContext.jsx`** — loads the account's role via
  `getMe()` whenever the authenticated user changes (login, register,
  logout, or session restore on mount); exposes `isSuperuser` and
  `roleLoading`. Fails closed on any error (network, expired token) —
  never silently grants admin access.
- **`src/routes/AdminRoute.jsx`** (new) — mirrors `ProtectedRoute`'s auth
  check, additionally requiring `isSuperuser`; redirects a logged-in
  non-admin to `/dashboard` rather than showing a dedicated "forbidden"
  page (out of scope to build one yet). Not wired into `AppRoutes.jsx`
  yet — there's no Admin Dashboard for it to protect until a later phase.

### Unchanged (verified, not assumed)

- Every existing customer-facing page, route, and flow — Login,
  Register, Dashboard, Plans, Subscriptions, Invoices, Payments, Refunds,
  Profile — required zero changes. `AuthContext`'s new role-loading
  effect only fires an extra API call for a logged-in user; unauthenticated
  visitors (landing page, login, register) trigger nothing new.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean (same 2 pre-existing, unrelated fast-refresh
  warnings as before; file count 63, up from 62 for the new
  `AdminRoute.jsx`).
- The backend's live security tests (two customers, cross-access
  attempts, admin bypass) prove the API contracts this frontend relies on
  behave correctly; see the backend's own CHANGELOG for details.

---

## Phase 1B: CustomerContext simplified via GET /customers/me (unreleased)

The backend added a real ownership link between `User` and `Customer`
(`Customer.user_id`, Phase 1A) and exposed it via `GET /customers/me`
(Phase 1B). This lets `CustomerContext` drop the client-side workaround
that existed only because that link didn't exist yet.

### Changed

- **`src/context/CustomerContext.jsx`** — completely rewritten. Now just
  calls `GET /customers/me` on auth state change: `200` → resolved,
  `404` → `needsSetup: true`. The entire previous multi-strategy
  resolution (localStorage cache lookup → paginated email search →
  generation-ref race guard to protect against the auto-resolve effect
  racing a fresh `provisionCustomer` call) is gone — there's nothing left
  to race, since the backend is now the single source of truth.
- **`src/services/customerService.js`** — added `getMe()`, removed
  `findByEmail()` (no longer has any caller).
- **`src/pages/RegisterPage.jsx`** — simplified: `provisionCustomer` no
  longer needs a `userId` passed through explicitly (that was working
  around a stale-closure timing issue in the old cache-based approach);
  the backend now derives ownership from the authenticated request itself.

### Removed

- **`src/utils/customerMap.js`** — deleted. Its entire purpose (caching
  `{ userId: customerId }` in `localStorage`) is now handled correctly and
  authoritatively by the backend.
- `STORAGE_KEYS.CUSTOMER_MAP` in `src/utils/constants.js` — the key that
  utility used, now unused.

### Unchanged (verified, not assumed)

- `src/components/layout/CustomerSetupGate.jsx` — needed no changes; it
  already only depended on `needsSetup` / `loadingCustomer` /
  `provisionCustomer` from `useCustomer()`, all of which kept the same
  shape.
- Every downstream page (Dashboard, Plans, Subscriptions, Invoices,
  Payments, Refunds, Profile) — zero changes; they only ever consume
  `customer` from context, never how it was resolved.

### Verified

- `npm run build` — clean.
- `npm run lint` — clean (same 2 pre-existing, unrelated fast-refresh
  warnings as before).
- Live end-to-end against the real backend: register → login →
  `/customers/me` (404, correctly empty) → create customer →
  `/customers/me` (200, matching) → subscribe → activate → plan-change →
  pay → refund → profile update → login again → `/customers/me` still
  resolves correctly.
