# CineVerse — Frontend

A premium, Netflix-inspired OTT streaming platform UI that is, under the hood,
a complete customer-facing frontend for the **Subscription Billing Automation
Platform** backend (FastAPI). Movies/content are static design placeholders —
every account, plan, subscription, invoice, payment, and refund shown is real
data from the backend.

**This project never modifies the backend.** No new endpoints, no schema
changes, no altered request/response formats. Every API call below maps to an
endpoint that already exists.

---

## 1. Stack

React (Vite) · Tailwind CSS v4 · React Router · Axios · React Hook Form ·
Framer Motion · React Icons · React Hot Toast · Context API

## 2. Setup

```bash
cp .env.example .env
# edit .env if your backend isn't on http://localhost:8000

npm install
npm run dev
```

Requires the backend running (see the backend's own README) with CORS
allowing the frontend's origin — the backend's default `CORS_ORIGINS=["*"]`
already covers this out of the box.

## 3. Important architectural note: User vs. Customer

The backend has **two separate entities**:

- **`User`** — the JWT auth account (`/auth/register`, `/auth/login`). It has
  no profile fields beyond email/name and no update endpoint at all.
- **`Customer`** — the actual billing subscriber that every subscription,
  invoice, payment, and refund belongs to (`/customers`).

**As of the backend's Phase 1A/1B work, these are linked server-side**
(`Customer.user_id`, with `GET /customers/me` as the lookup endpoint) — so
`src/context/CustomerContext.jsx` is now simple:

1. **On registration** (`RegisterPage.jsx`): after creating the `User` and
   logging in, it calls `POST /customers`. The backend automatically sets
   `Customer.user_id` from the authenticated request — no client-side
   bookkeeping needed.
2. **On any login, any device**: `CustomerContext` calls `GET /customers/me`.
   `200` → that's the linked customer. `404` → no customer exists yet.
3. **Genuine edge case** (`404`, e.g. an account that predates the backend's
   ownership link and wasn't matched by its one-time email backfill):
   `CustomerSetupGate.jsx` renders a one-time "complete your billing
   profile" form that calls the same `POST /customers` endpoint.

Everything past this point (Dashboard, Subscriptions, Invoices, Payments,
Refunds, Profile) operates on the resolved `Customer` record, not the `User`.

> **Prior architecture (removed):** before the backend added this link,
> `CustomerContext` bridged the two client-side — caching `customer.id` in
> `localStorage` (`src/utils/customerMap.js`) and, failing that, paginating
> through every customer searching for an email match. Both were removed
> once `GET /customers/me` made them unnecessary; `customerMap.js` no
> longer exists.

## 4. Folder structure

```
src/
├── assets/        static images/placeholder movie data (design-only)
├── components/
│   ├── common/    Modal, Spinner, StatusBadge, Table, Pagination, etc.
│   ├── layout/     Sidebar, Topbar, AdminSidebar, AdminTopbar, Navbar, Footer, CustomerSetupGate
│   ├── landing/    Hero, MovieRow, WhyChoose, FAQ
│   ├── subscription/  PlanCard, ProrationModal, CancelSubscriptionModal
│   ├── invoices/   InvoiceDetailModal
│   ├── payments/   ProcessPaymentModal
│   ├── refunds/    RequestRefundModal
│   └── admin/      PlanFormModal (create/edit)
├── pages/          one file per customer-facing route
│   └── admin/      one file per admin route (Phase 3 + Reports, Phase 5)
├── layouts/        PublicLayout, AppLayout (customer shell), AdminLayout (admin shell)
├── routes/         AppRoutes.jsx, ProtectedRoute.jsx, AdminRoute.jsx
├── services/       one thin module per backend domain + apiClient.js
├── hooks/          useAuth, useCustomer, useApi
├── context/        AuthContext, CustomerContext
└── utils/          constants, jwt decode, formatters, download.js (blob downloads)
```

**Rule of thumb:** every `services/*.js` file's functions map 1:1 onto real
backend endpoints — check there first if you're wondering "does the backend
support X?"

## 5. Backend endpoint coverage

| Feature | Backend endpoint(s) used |
|---|---|
| Register / Login / Token refresh | `POST /auth/register`, `/auth/login`, `/auth/refresh` |
| Resolve my customer record | `GET /customers/me` |
| Browse plans | `GET /plans` |
| Subscribe / Activate / Pause / Resume / Cancel | `POST /subscriptions`, `/{id}/activate`, `/{id}/pause`, `/{id}/resume`, `/{id}/cancel` |
| Upgrade / Downgrade with proration | `POST /subscriptions/{id}/proration-preview` then `/{id}/change-plan` |
| Invoices | `GET /invoices`, `GET /invoices/{id}` |
| Download invoice PDF | `GET /invoices/{id}/pdf` (Phase 4) |
| Email invoice PDF to customer | `POST /invoices/{id}/email` (Phase 6C) |
| Pay an invoice | `POST /payments/process` |
| Payment history | `GET /invoices/{id}/payments` (aggregated per-invoice client-side for the Payments page, since the backend has no "list my payments" endpoint) |
| Refunds | `POST /refunds`, `GET /refunds` (supports `customer_id` directly) |
| Recent activity | `GET /audit-logs/{entity_type}/{entity_id}` |
| Account-wide Activity Timeline | `GET /audit-logs/me` |
| Logout (records the event; token is cleared client-side regardless) | `POST /auth/logout` |
| **Admin:** platform-wide audit log | `GET /audit-logs` (admin only, except `entity_type=plan`) |
| Profile | `GET`/`PATCH /customers/{id}` (name, phone, country, address — email is read-only, matching the backend's `CustomerUpdate` schema exactly) |
| **Admin:** who am I / role | `GET /auth/me` |
| **Admin:** dashboard summary | `GET /analytics/dashboard` |
| **Admin:** revenue/subscription/payment/refund analytics | `GET /analytics/revenue`, `/subscriptions`, `/payments`, `/refunds` |
| **Admin:** all customers, edit any customer | `GET /customers`, `PATCH /customers/{id}` (admin-only since Phase 1C; edit UI added in Final Polish) |
| **Admin:** plan create/edit/archive | `POST /plans`, `PATCH /plans/{id}`, `POST /plans/{id}/archive` |
| **Admin:** all subscriptions/payments/refunds | `GET /subscriptions`, `/payments`, `/refunds` (unfiltered — the backend serves everyone's data to an admin, scoping only non-admins) |
| **Admin:** reports & export | `GET /reports/{revenue|customers|subscriptions|payments|refunds}?format=csv\|xlsx\|pdf` (Phase 5) |

Nothing here was invented — every row above is a real, pre-existing endpoint.

## 6. Auth & token refresh

`src/services/apiClient.js` attaches the JWT to every request and
transparently refreshes an expired access token via the existing
`POST /auth/refresh` on a 401, queuing any concurrent requests until the new
token is ready. If refresh itself fails, it dispatches a `cv:session-expired`
window event that logs the user out everywhere.

`AuthContext` also loads the account's role via `GET /auth/me` whenever the
authenticated user changes, exposing `isSuperuser` / `roleLoading` /
`accountInfo` (email + name, captured from the same response — nothing else
needs a second call to `/auth/me`). `LoginPage` additionally calls
`authService.getMe()` directly right after a successful login (not via
context state, to avoid a timing race with the effect above) to decide
whether to land the user on `/dashboard` or `/admin/dashboard`.
`src/routes/AdminRoute.jsx` gates the whole `/admin/*` section on
`isSuperuser`, redirecting a logged-in non-admin to `/dashboard` — they are
never shown any admin content and no admin-only API call is ever attempted
on their behalf.

## 7. What's intentionally *not* here

Per the backend's own documented scope: no failed-payment retry UI
(Module 3), no usage-based billing UI (no service populates it), no
emailing generated reports, no background report generation (every
report/export request in this app is synchronous — you wait for the
download, there's no job queue or "check back later"), and no
charts/graphs on the Admin Dashboard (no charting library was
introduced — the analytics endpoints' numbers are shown as stat cards,
matching the existing `StatCard` component already used on the customer
dashboard, since charts weren't explicitly requested and adding a new
dependency for them wasn't in scope for that phase).

## 8. Admin Dashboard (Phase 3)

A second, parallel app shell (`AdminLayout` / `AdminSidebar` / `AdminTopbar`)
alongside the customer-facing one, gated entirely by `AdminRoute`
(`isSuperuser`). Six pages:

- **`/admin/dashboard`** — stat cards from `GET /analytics/dashboard` (+ 
  refund total from `/analytics/refunds`): total/active customers, total
  plans, active/cancelled subscriptions, total revenue, successful/failed
  payments, total refunds.
- **`/admin/customers`** — every customer on the platform (`GET /customers`,
  admin-only since Phase 1C), with client-side search by name/email and
  pagination.
- **`/admin/plans`** — list + status filter (existing `GET /plans`), plus
  **new** create/edit/archive UI (`PlanFormModal`) wired to the existing
  `POST/PATCH /plans` and `POST /plans/{id}/archive` endpoints, which had
  no frontend UI at all before this phase.
- **`/admin/subscriptions`**, **`/admin/payments`**, **`/admin/refunds`** —
  the same `GET /subscriptions` / `/payments` / `/refunds` the
  customer-facing pages already call, just without a customer filter
  (which the backend now serves in full to an admin, per Phase 1D's
  ownership enforcement scoping only non-admins).

**Reuse, not duplication:** every page reuses the existing service modules
(`customerService`, `planService`, `subscriptionService`, `paymentService`,
`refundService`) and the existing UI components (`Table`, `Pagination`,
`Skeleton*`, `EmptyState`, `ErrorState`, `StatusBadge`, `StatCard`,
`PageHeader`, `Modal`). Only two things are genuinely new:
`src/services/analyticsService.js` (wraps the five Phase 2 endpoints) and
three new methods on `planService.js` (`create`/`update`/`archive` — the
backend has supported these since Module 1/Phase 1C, but no frontend caller
existed until now).

Discoverable from the customer app via a conditional "Admin Panel" link in
the regular `Sidebar` (visible only when `isSuperuser`), and admins are
routed straight to `/admin/dashboard` on login instead of the customer
`/dashboard`.

## 9. Invoice PDF Download (Phase 4)

`src/components/invoices/InvoiceDetailModal.jsx` (the customer-facing
invoice detail view — the only place a full invoice is actually
*displayed*, as opposed to just summarized in a list row) gained a
"Download PDF" button wired to the new `GET /invoices/{id}/pdf`.

- **`invoiceService.downloadPdf(invoiceId)`** (new) fetches the PDF as a
  blob (`responseType: 'blob'`) and reads the suggested filename straight
  off the backend's `Content-Disposition` header, so the frontend doesn't
  need to know or duplicate the backend's invoice-number naming
  convention.
- **`src/utils/download.js`** (new) — a small, generic
  `downloadBlob(blob, filename)` helper (temporary anchor element +
  `URL.createObjectURL`/`revokeObjectURL`) that any future blob download
  elsewhere in the app can reuse, rather than being invoice-specific.
- The button shows a spinner and "Downloading…" while the request is in
  flight, and surfaces a toast on failure — it doesn't silently do
  nothing if the download fails.
- **Not added to the `InvoicesPage.jsx` list rows.** The list only shows
  a summary line (amount/tax/status) with a click-to-open-detail
  interaction; adding a second per-row action there would have meant
  reworking that interaction (stopping click-propagation, adding an
  actions column), which felt like exactly the kind of "redesign an
  existing invoice page" this phase was asked to avoid. The detail modal
  — where the invoice is actually shown in full — was the more
  conservative, correct place for this.

## 10. Reports & Export (Phase 5)

**`/admin/reports`** — a new Admin Dashboard page (`AdminReportsPage.jsx`)
letting an admin pick a report type (Revenue / Customer / Subscription /
Payment / Refund), an export format (CSV / Excel / PDF), an optional date
range (only enabled for Revenue and Payment — the two report types the
backend actually supports date filtering for), and download.

- **`src/services/reportService.js`** (new) — thin wrapper around the 5
  `GET /reports/*` endpoints (Phase 5), following the exact same blob +
  `Content-Disposition`-filename pattern already established by
  `invoiceService.downloadPdf` (Phase 4) — no new download mechanism was
  invented, the existing `downloadBlob` utility is reused as-is.
- The date-range inputs are conditionally rendered/enabled based on
  `REPORT_TYPES_WITH_DATE_RANGE` (exported from `reportService.js`), so
  the UI can never even attempt to send a date range the backend doesn't
  support for a given report type.
- Shows a spinner + "Generating…" while the request is in flight, and a
  toast on failure — mirroring the invoice PDF button's error handling.

## 11. Design

Dark theme, brand red `#E50914`, background `#0F172A`, glassmorphism cards,
Framer Motion micro-animations — see `src/index.css` for the full token set
(Tailwind v4 `@theme`).

**Accessibility:** every button variant, nav link, and modal close button
has a visible `:focus-visible` ring (`.focus-ring` utility class, or built
into `.btn-primary`/`.btn-secondary`/`.btn-ghost`) — added in the Final
UI/UX Polish pass, since none of them had one before. Icon-only action
buttons carry both a `title` (mouse hover) and `aria-label` (screen
readers).

**Performance:** every authenticated/admin page is `React.lazy()`-loaded
behind a `Suspense` boundary (`src/routes/AppRoutes.jsx`) — only the
public landing/login/register pages are in the initial bundle. This
measurably shrank the main JS bundle (572 kB → 432 kB) and eliminated the
"chunks larger than 500 kB" build warning that had appeared throughout
this project's history.

**Confirmation dialogs:** destructive/irreversible actions (like archiving
a plan) use a themed `ConfirmDialog` component (`src/components/common/`),
not a native `window.confirm()` — matches the rest of the design system
and supports a loading state.

## Catalog Artwork

Catalog artwork is loaded from The Movie Database (TMDB) image CDN for the demo catalog. The frontend keeps all existing card/container dimensions unchanged and selects poster artwork for portrait cards and landscape artwork for wide hero areas where available. If an image fails to load, the existing CineVerse gradient treatment is used as a graceful fallback.

TMDB attribution notice: This product uses the TMDB API but is not endorsed or certified by TMDB. Artwork is served from TMDB's image CDN; verify TMDB's current terms and attribution requirements before using the project commercially.
