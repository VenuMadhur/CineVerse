# CineVerse — Premium Streaming Catalog (Demo Feature)

## What this is

A frontend-only addition to the existing CineVerse Billing Platform that demonstrates how a customer's real subscription plan would unlock premium content, if CineVerse were a real streaming service. **CineVerse's actual purpose remains subscription billing, payments, invoices, refunds, and customer management** — this feature exists purely to make that billing relationship tangible with a familiar "movies and shows" UI, not to add real streaming.

## What it is not

- Not a real content catalog or streaming service.
- Not connected to any backend API, database table, or new endpoint. Every title, genre, cast member, and description is static, local data in `src/data/catalogData.js`.
- No real trailer or video content is embedded, linked, or referenced anywhere. "Preview" and "Watch Now" both open in-app placeholder pages explaining that streaming is out of scope for this project.
- No real poster artwork is fetched or displayed. Every card and detail page uses an original, brand-styled gradient placeholder (`PosterPlaceholder.jsx`) instead.

## How subscription access works

Access is entirely derived from the customer's **real, existing subscription** — reusing the same `subscriptionService` and `planService` calls already used elsewhere in the app (see `useAccessTier.js`). No new entitlement system, no duplicated billing logic. A customer's current plan is ranked by price against all active plans and bucketed into Starter / Professional / Premium; a higher tier unlocks everything a lower tier does. If a customer has no active or trial subscription, they see no access anywhere in the catalog — the check fails closed, not open.

Access is checked in two places independently — once for the UI (showing "Watch Now" vs. "Upgrade Plan" on the detail page) and again on the `/watch/:id` page itself — so navigating directly to a watch URL can't bypass the plan requirement.

## Pages & Routes

| Route | Purpose |
|---|---|
| `/movies` | Trending Movies grid |
| `/movies/:id` | Movie detail page |
| `/series` | Popular Web Series grid |
| `/series/:id` | Series detail page (same component as movies, by design) |
| `/preview/:id` | In-app placeholder — no external link, no video |
| `/watch/:id` | In-app placeholder for entitled customers — re-checks access independently |

All customer-only, added inside the existing `ProtectedRoute` / `AppLayout` block. Nothing was added to admin routing or the admin sidebar.

## Catalog content

6 movies, 7 web series — titles, genres, cast, and release years are factual, publicly-known information (the same category of data any listings site references); descriptions are original text, not copied synopses. The Starter / Professional / Premium mapping matches the specification exactly.

## Files

See the accompanying delivery report for the full modified/new file list.
