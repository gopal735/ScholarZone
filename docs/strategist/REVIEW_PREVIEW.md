# Reviewing the Study Abroad Planner on a PR preview

Both gates are **off by default**, so a preview built from this branch as-is shows
no planner: the route returns the not-found page and no navigation entry or
homepage call to action exists. That is deliberate — the feature ships inert.

To review it, one of two paths. Both require the **frontend** flag; only the
live-API path needs the backend flag as well.

---

## Path A — review the interface without any backend (fixture data)

Enough to see the planner end to end, including the Bangla toggle, the
insufficient-data cells and the BDT conversions, because the interface reads a
captured fixture instead of the network.

**Vercel preview for this PR**

1. Open the PR's Vercel preview deployment (the "Preview" check on PR #49).
2. Add the build variable and redeploy the preview:
   `VITE_STRATEGIST_ENABLED=true`.
   - Vercel dashboard → the preview deployment → **Redeploy** → copy the
     variable, **uncheck "use existing Build Cache"**, then deploy.
   - Vite inlines `VITE_*` at build time, so a cached rebuild would not contain it.
3. Visit `/strategist?fixture=1`. The `?fixture=1` query is read at runtime, so
   no rebuild is needed and the same preview can be shown with and without it.

`VITE_STRATEGIST_FIXTURE=true` is the build-time equivalent, for a preview that
should always open on fixture data.

**Locally**

```
cd frontend
VITE_STRATEGIST_ENABLED=true npm run build
npx vite preview
# then http://127.0.0.1:4173/ScholarZone/strategist?fixture=1
```

**Committed E2E (no backend, no Vercel)**

```
cd frontend
npx playwright install chromium   # not pre-installed in this project's CI
npm run test:e2e:strategist
```

`frontend/e2e/preview-server.mjs` builds with the frontend flag on, serves the
production build on port 4173 and the spec drives `/strategist?fixture=1` on a
mobile (Pixel 5) and a desktop (1280×900) viewport — 4 tests covering the happy
path and the insufficient-data path. Screenshots from such a run are committed
under `docs/strategist/screenshots/`.

---

## Path B — review the planner against the real API

Requires both flags, because the backend refuses the planner's routes while its
own switch is off (`/v2/strategist/*` returns 404 — an absence, not a disabled
feature).

| where | variable | notes |
| --- | --- | --- |
| frontend (build time) | `VITE_STRATEGIST_ENABLED=true` | Vite inlines it; redeploy the preview with the build cache bypassed |
| API (runtime) | `SCHOLARZONE_STRATEGIST_ENABLED=true` | set on the API deployment the frontend calls, then restart that service |

The frontend calls the API at `VITE_API_BASE_URL` (default `/api`), so a preview
whose `/api` is not rewired to the running API will fall back to the fixture path
above — the interface does not pretend the data is live.

> Do not set either variable in any shared environment to try this. A preview
> deployment is disposable; production is where the flag would become a public
> release decision, and that is not what a review needs.

---

## What to look at while reviewing

| promise | where to see it |
| --- | --- |
| every sourced cell links its official source | the source line under each cell |
| BDT shown beside the original currency, with the rate dates | cells with a converted figure |
| "Insufficient data" with a reason, never a number | cells where the source is missing |
| gross salary, never take-home | the `gross, not take-home` label on salary cells |
| no single "best country" | the ranking rule panel and the disclaimer |
| nothing invented | a country with a missing essential criterion is listed as not ranked, with the reason |

`frontend/src/features/strategist/StrategistPage.test.jsx` pins each of these in
unit tests, so a regression in any of them fails CI rather than the review.

## Test evidence for the entry points

`frontend/src/features/strategist/discoverability.test.jsx` asserts the nav link
and the homepage call to action in **both** directions (present with the flag on,
absent with it off), that they point at `/strategist`, that the route is gated
the same way, and that fixture mode answers from the bundle without the network.
