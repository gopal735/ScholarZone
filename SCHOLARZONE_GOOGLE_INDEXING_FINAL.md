# SCHOLARZONE_GOOGLE_INDEXING_FINAL.md

**Google Search visibility / indexing: audit, release, live verification, and Search Console verification**
· 2026-10-04 19:16Z–20:45Z
**Audited baseline:** `fc4096f7a2aac8530f4e14495a7f21b9a97419be`
**Canonical public site:** `https://scholarzone-fwzj.vercel.app`
**Production writes:** NONE (no database writes, no production data mutation, no configuration change)
**Production deployments created manually by this task:** 0 (every deployment came from the Git integration)

> **Note on this document.** An earlier revision was corrupted by a shell encoding mistake during
> editing (non-ASCII punctuation was destroyed across 163 lines). This revision is a clean
> reconstruction. **No factual content was lost** — every measurement, finding and classification
> below is reproduced from the verified evidence. Decorative dash and arrow glyphs were normalised to
> plain equivalents.

---

# PART 1 — STATUS

## 1.1 SEO release: shipped

| | |
|---|---|
| PR | **#8** — https://github.com/gopal735/ScholarZone/pull/8 |
| SEO commit | `16151af362a5916331f8e379cc8e46c6c17b2f1f` |
| Merge commit on master | `cfb2b54d03341316985e66c7963a4c73976d33ef` |
| Merged | 2026-10-04T20:18:18Z |
| CI | **9/9 jobs green** on head `16151af` |
| Deployment | `dpl_6CvxptL5NBwibWHEmHJySkN8VTRo` |
| Provenance | `source=git`, `target=production`, `gitSource.ref=master`, `gitSource.sha=cfb2b54…` |
| Deployed by | the Vercel GitHub App on the master push. **No manual or CLI deployment was used.** |
| Vercel status | `Vercel – scholarzone-fwzj` = **success**, "Deployment has completed" (20:18:57Z) |
| Live verified | 2026-10-04T20:22Z–20:28Z (Part 5) |

Live runtime identity on the canonical host, confirming the deployed build:

```
GET https://scholarzone-fwzj.vercel.app/api/health
  {"status":"ok","revision":"cfb2b54d03341316985e66c7963a4c73976d33ef"}
  length = 40, lowercase hex = true
```

Equal to the merged master and to the deployment's `gitSource.sha` — the same four-way identity
standard this project already applies to releases.

## 1.2 Search Console ownership verification: blocked

```
GOOGLE_VERIFICATION_BLOCKED
```

**This is a final classification of this task, not an interim status.** See Part 4 for the full
reasoning. In short, two independent blockers:

1. **The Google HTML verification file was never provided.** The mission brief contains a literal
   placeholder where the file belongs. Nothing was invented to fill it.
2. **Even with the file, nothing would publish**, because the Vercel GitHub App is currently refusing
   deployments on this project with "Deployment rate limited - retry in 24 hours". A manual CLI
   deployment would bypass that and is forbidden.

Critically, blocker 2 also explains the original failure, and **clears the tag approach of blame** —
see Part 4.2.

**No claim is made that Google ownership verification succeeded.**

## 1.3 What is *not* claimed anywhere in this document

- Not claimed: that Google has indexed ScholarZone, or any page of it.
  `site:scholarzone-fwzj.vercel.app` returns **0 results**, and a brand search for "ScholarZone"
  returns only unrelated third-party sites.
- Not claimed: that Google will index anything, rank the site, or show any rich result.
  Submitting a sitemap and requesting indexing **do not guarantee inclusion**.
- Not claimed: that ownership verification passed. Only the owner can complete that, and the file
  was never supplied.

What *is* claimed, and was proven: the intended canonical pages are publicly discoverable and
crawlable, the deployed site has no known technical blocker preventing indexing, and the complete
indexable URL universe is published in a valid sitemap.

---

# PART 2 — WHAT WAS ALREADY THERE (PRESERVED)

The repository already contained a substantial, deliberate SEO implementation. It was audited before
anything was changed, and most of it was preserved. Rewriting it would have been the wrong move.

| Artefact | What it does | Verdict |
|---|---|---|
| `frontend/src/services/canonicalOrigin.js` | One `CANONICAL_ORIGIN` consumed by HomePage, ScholarshipsPage, ScholarshipDetailsPage, CountryPage | **Architecture correct, value wrong.** Fixed the value only |
| `frontend/public/robots.txt` | Hand-written crawl policy with stated reasons, including a deliberate `Disallow: /*?*` for filter URLs | **Intent correct, paths inert.** Fixed the paths |
| `backend/app/data/generate_sitemap.py` | DB-backed generator writing `frontend/public/sitemap.xml`, with per-record `lastmod` | **Good design, wrong host, weaker filter.** Fixed both |
| `frontend/scripts/generate-sitemap.js` | A second Node generator for the same output | **Orphaned, non-functional.** Removed |
| `frontend/public/sitemap.xml` | Committed generated artefact, 490 URLs | **Wrong host, wrong membership.** Regenerated |
| `frontend/index.html` | Minimal SPA shell | **No metadata.** Fixed |
| Runtime SEO effects in 4 pages | description, OG, Twitter, canonical, JSON-LD, `noindex` on failed detail load | **Working and good** — preserved as the architecture |
| `data-sz-seo` convention | Every runtime-injected head node is marked so effects can clean up | **Good** — preserved and reused |
| `vercel.json` (root) | Two-service routing; all non-`/api` paths to the SPA | **One origin for app and API** |
| `frontend/vercel.json` | SPA fallback rewrite so `/scholarships/12` resolves | **Deep links work** |

Specifically preserved, with reasons:

1. **The centralised origin module.** Right shape; only the value was wrong.
2. **The `Disallow: /*?*` policy.** Chosen deliberately to stop filter combinations exploding into
   thin duplicates. Kept exactly.
3. **`noindex` on a failed detail load.** Kept.
4. **`ScholarArticle` + `BreadcrumbList` on detail pages**, and the deliberate removal of
   `Scholarship` as a JSON-LD type, with a comment explaining schema.org defines no such listing
   type. Kept — this is exactly the "no made-up schema" discipline required.
5. **Real crawlable anchors** on cards (`<Link to={/scholarships/${id}}>`), not click handlers.
6. **Catalogue copy that refuses to assert "every listing has a verified official source"**, because
   the catalogue deliberately publishes some records as "Confirm with provider". Left intact.
7. **`/match` and `/mentor` left crawlable.** They are real public pages.
8. **SPA fallback and deploy-target-derived Vite base.**
9. **No fabricated social image.** The repo ships no `og-image.png`, yet the homepage pointed
   `og:image` at one. Fixed by removing the claim, not by inventing an asset.

Relevant history, so prior work is neither undone nor resurrected:

- `1d792f2 fix: the sitemap advertised URLs that do not exist`
- `d812cdb fix: give the frontend service an SPA fallback so deep links resolve`
- `56f0c75 fix: derive the router basename from the deploy target and add an error boundary`
- `8436d31 Deploy ScholarZone frontend to GitHub Pages` (2026-09-08) — the legacy Pages build

---

# PART 3 — WHAT WAS WRONG, AND WHAT CHANGED

## 3.1 Defects confirmed against live production (pre-release)

### 3.1.1 The canonical host was a stale legacy deployment — CRITICAL

`canonicalOrigin.js` defaulted to `https://gopal735.github.io/ScholarZone`.
`VITE_CANONICAL_ORIGIN` is **not set** on the canonical Vercel project, so the default was live.
Every canonical link, `og:url`, BreadcrumbList item and the SearchAction template therefore named a
host that is not the production site, instructing a crawler to consolidate onto it.

Evidence that host is legacy, not canonical:

- `gopal735.github.io/ScholarZone/` returns HTTP 200, but it is a **different, older build**
- `gopal735.github.io/ScholarZone/scholarships` returns **HTTP 404** (no SPA fallback there)
- its branch `gh-pages` was last built **2026-09-08**, roughly four weeks behind master
- it is a separate project, not the Git-integrated production deployment

### 3.1.2 The served HTML had no metadata at all

Production returned a **byte-identical 788-byte document** for `/`, `/scholarships` and
`/scholarships/1`: one static `<title>`, an empty `<div id="root">`, and no description, canonical,
Open Graph, Twitter, robots directive or JSON-LD. All real metadata was injected later by JavaScript,
after two client-side fetches.

### 3.1.3 robots.txt rules matched nothing

Every rule carried the GitHub Pages project-page prefix. On the canonical host the app is served from
`/`, so `Disallow: /ScholarZone/admin` **did not match `/admin`** — the private surface was never
actually blocked while the file claimed it was. Its `Sitemap:` line pointed at the legacy host.

### 3.1.4 The sitemap was wrong in both directions — CRITICAL

Valid XML, HTTP 200, no duplicates, but:

- **all 490 URLs** on `gopal735.github.io`, with a `/ScholarZone/` prefix that does not exist on
  production
- **207 of its 487 scholarship IDs are not public** (they would 404 or render `noindex`)
- **87 genuinely public scholarship IDs missing** entirely, mostly IDs 492+

Root cause: the generator carried its own weaker membership rule
(`verification_status != "quarantined"`) instead of calling the repository's own
`public_visibility_conditions()`, which also excludes archived records and applies the verification
and image gates.

### 3.1.5 Two sitemap generators existed, and one could never have worked

`frontend/scripts/generate-sitemap.js` requested `limit=500`, but the API schema caps `limit` at 100
(`Field(default=12, ge=1, le=100)`), so it would have been rejected. Referenced by no npm script and
by nothing else in the repository. Dead code that would mislead the next person.

### 3.1.6 Every page shared one title

No public page set `document.title`. Only the private pages (Dashboard, Applications, Match, Mentor)
did. So `/`, `/scholarships`, `/scholarships/1` and `/countries` all presented the same `<title>`.

### 3.1.7 Filter URLs contradicted robots.txt

The catalogue emitted `robots: index, follow` on `?country=`, `?degree=` and `?funding=` variants while
robots.txt disallowed every query URL. The two files disagreed about the same URLs.

### 3.1.8 Empty `ItemList` structured data

`CountryPage` emitted `mainEntity: { '@type': 'ItemList', itemListElement: [] }` on mount and never
updated it — advertising a list that described nothing.

### 3.1.9 `og:image` pointed at a file that does not exist

HomePage set `og:image` to `${baseUrl}/og-image.png`. The project ships no such asset.

## 3.2 Changes made — 11 files

### `frontend/src/services/canonicalOrigin.js` (modified)
Default changed to `https://scholarzone-fwzj.vercel.app`; env override retained. The comment records
why the legacy host was wrong and why the project alias is preferred over a per-deployment URL: the
alias survives every future build.

### `frontend/index.html` (modified)
Added real, accurate head metadata for the homepage, served to every crawler **before** any script
runs: title, meta description, `robots: index, follow`, canonical, Open Graph, Twitter, and
`WebSite` + `SearchAction` JSON-LD.

Every tag carries `data-sz-seo="true"`. That reuses the repository's existing ownership convention:
HomePage's effect removes all `[data-sz-seo]` nodes before writing its own, so the static tags are
**replaced by identical values, not duplicated by them**. No counts, deadlines or funding claims were
written in — the catalogue size and country count are live values the page fills in later, and a
hardcoded number would be a claim the page cannot guarantee.

### `frontend/public/robots.txt` (rewritten)
- Rules written for the deployed base `/`; the inert `/ScholarZone/` prefix removed.
- Blocks `/admin`, `/dashboard`, `/applications`, `/login`, `/register`, `/saved`, `/compare`, `/api/`.
- Keeps `Disallow: /*?*` for filter, search, sort and pagination variants.
- `Sitemap: https://scholarzone-fwzj.vercel.app/sitemap.xml`.
- `/match` and `/mentor` deliberately still allowed.

### `backend/app/data/generate_sitemap.py` (modified)
- `BASE_URL` defaults to the canonical origin, overridable via `SCHOLARZONE_CANONICAL_ORIGIN`.
- Membership now calls `public_visibility_conditions()`, the repository's single definition of "may be
  shown publicly". The sitemap can no longer disagree with the directory.

### `frontend/public/sitemap.xml` (regenerated)
370 URLs on the canonical host. Full result in 4.4.

### `frontend/scripts/generate-sitemap.js` (deleted)
Orphaned and non-functional. Deleted so exactly **one** sitemap generator exists. This removes
duplication rather than adding any.

### `frontend/src/pages/HomePage.jsx` (modified)
Sets and restores `document.title`. Removed the `og:image` reference to a non-existent asset;
`twitter:card` changed from `summary_large_image` to `summary`, because there is no image to show.

### `frontend/src/pages/ScholarshipsPage.jsx` (modified)
- Sets and restores `document.title`.
- Any query variant now emits `noindex, follow` and canonicalises to the clean `/scholarships`.
  `follow` is retained so a crawler reaching a filtered URL still walks the links beneath it. The
  clean catalogue stays `index, follow` and self-canonical.
- `twitter:card` changed to `summary`.

### `frontend/src/pages/ScholarshipDetailsPage.jsx` (modified)
- Sets and restores `document.title` from the record's own title. No count, deadline or funding claim
  is added, because those change and a stale one in a snippet is a claim the site cannot stand behind.
- `og:title` / `twitter:title` use the same per-record title.
- `twitter:card` follows the record: `summary_large_image` when an official image exists, `summary`
  when it does not.
- The existing `noindex` on a failed load, the canonical, the description, the `ScholarArticle` graph
  and the `BreadcrumbList` are unchanged.

### `frontend/src/pages/CountryPage.jsx` (modified)
- Sets and restores `document.title`.
- The `ItemList` is built from the same list the page renders, in the same order, and only from
  countries with at least one public scholarship. Emitted **once the counts settle**. If nothing
  qualifies it is omitted entirely rather than emitted empty, leaving an honest `CollectionPage`.

### `frontend/src/seoContract.test.js` (added — 21 tests)
A regression guard for exactly these defects. Each assertion corresponds to a failure that was
actually live:

- canonical origin is the production host, and is not the legacy host; no trailing slash
- robots.txt points at the sitemap on the canonical host; contains no legacy project-page prefix
- every private surface blocked; filter variants blocked
- robots.txt does **not** block the pages that are the product, nor the render-blocking assets
- sitemap well formed, non-empty, entirely on the canonical host, no query strings, no duplicates, no
  private/admin/API URLs, covers the three indexable routes, and covers **more than 100** detail URLs
- the served document carries a canonical, a description, an indexing directive and `WebSite`
  JSON-LD before any script runs
- every shipped head tag is `data-sz-seo`-marked, so the runtime replaces rather than duplicates it
- no reference to an asset the build does not produce
- no file names the legacy host

## 3.3 What was deliberately NOT done

- **No SSR, no framework migration, no static regeneration of 367 records.** The architecture is a
  client-rendered SPA. The question was whether it made important pages effectively empty *before*
  JavaScript — it did — and the fix was to make the **document** correct, which is far smaller than a
  rendering stack.
- **`DIRECTORY_LIMIT = 100` left alone.** Investigated; see 4.6.
- **No custom domain.** Owner decision, see 4.11.
- **No `ItemList` on the catalogue.** It paginates 12 per page across 31 pages; an `ItemList` naming
  12 of 367 would misrepresent the page.
- **No change to `vercel.json`.** Not required.

---

# PART 4 — VERIFICATION RESULTS

## 4.1 Canonical public URL

```
CANONICAL_SITE_URL = https://scholarzone-fwzj.vercel.app
```

Determined from deployed configuration, not assumption:

| Evidence | Finding |
|---|---|
| `.vercel/repo.json` | linked project `scholarzone-fwzj` / `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| Vercel project record | `link.type=github`, repo `ScholarZone`, `link.productionBranch=master` |
| Project `domains` | **no custom domain**; only the three stable `*.vercel.app` aliases |
| Production deployment | `dpl_6CvxptL…`, `gitSource.ref=master`, holds all three aliases |
| Root `vercel.json` | SPA and API share one origin |
| `vite.config.js` | `base: isVercel ? '/' : '/ScholarZone/'` — production served from `/` |
| Live `/api/health` | revision matches the deployed merge commit |

The project-scoped alias was chosen over the org-scoped alias and over per-deployment URLs, because it
is the conventional canonical and it survives every redeploy. Both serve the same deployment.

**Mixture check — the defining defect, now consistent.** Before: canonical to GitHub Pages, sitemap to
GitHub Pages, robots `Sitemap:` to GitHub Pages, sitemap URLs to GitHub Pages. After: all four name
`https://scholarzone-fwzj.vercel.app`, asserted by test and confirmed live.

## 4.2 robots.txt — live, post-release

HTTP 200, 1,710 bytes, anonymously reachable, LF line endings.

```
User-agent: *
Allow: /
Disallow: /admin
Disallow: /dashboard
Disallow: /applications
Disallow: /login
Disallow: /register
Disallow: /saved
Disallow: /compare
Disallow: /api/
Disallow: /*?*
Sitemap: https://scholarzone-fwzj.vercel.app/sitemap.xml
```

| Path class | Directive | Classification |
|---|---|---|
| `/`, `/scholarships`, `/scholarships/<id>`, `/countries` | `Allow: /` | **INTENTIONALLY_ALLOWED** |
| `/match`, `/mentor` | `Allow: /` | **INTENTIONALLY_ALLOWED** — real public pages |
| `/assets/*.css`, `/assets/*.js` | `Allow: /` | **INTENTIONALLY_ALLOWED** — render-blocking |
| `?country=` `?degree=` `?funding=` `?search=` `?sort=` `?page=` | `Disallow: /*?*` | **INTENTIONALLY_BLOCKED** — thin duplicates |
| `/admin`, `/admin/verification` | blocked | **INTENTIONALLY_BLOCKED** |
| `/dashboard`, `/applications`, `/login`, `/register`, `/saved`, `/compare` | blocked | **INTENTIONALLY_BLOCKED** — per-user or near-duplicate |
| `/api/` | blocked | **INTENTIONALLY_BLOCKED** — internal API |

Live verification of the exact questions asked:

| Check | Result |
|---|---|
| literal legacy path prefix `/ScholarZone` present | **false** |
| legacy `github.io` host present | **false** |
| blocks `/admin` | **true** |
| blocks `/api/` | **true** |
| blocks query variants | **true** |
| blocks `/scholarships` | **false** — correctly allowed |
| blocks `.css` / `.js` assets | **false** — correctly allowed |

The pre-release state was **ACCIDENTALLY_BLOCKED** in one specific sense: its private-surface rules
matched nothing while appearing to block. There was never a whole-site block.

## 4.3 Indexable URL classes

| Class | Count | Canonical form | Indexable |
|---|---|---|---|
| Homepage | 1 | `/` | yes |
| Catalogue | 1 | `/scholarships` | yes |
| Destinations | 1 | `/countries` | yes |
| Scholarship detail | **367** | `/scholarships/<id>` | yes |
| Filter / search / sort / page variants | unbounded | — | **no** — `Disallow: /*?*` + `noindex, follow` |
| Private, admin, per-user, API | 13 route prefixes | — | **no** |
| **Total indexable** | **370** | | |

The 367 is not a guess: `/api/scholarships/stats` returns `total: 367`, and paged enumeration
(`limit=100&page=1..4`, `total_pages: 4`) returned exactly 367 distinct public records across 47
countries.

## 4.4 Sitemap — live, post-release

Regenerated from the live public catalogue (read-only, through the same endpoint the site renders
from, which applies `public_visibility_conditions()` internally).

| Property | Before | After (live) |
|---|---|---|
| HTTP status | 200 | **200** |
| Valid XML | yes | **VALID** (`urlset`) |
| Bytes | 91,502 | **67,994** |
| URL count | 490 | **370** |
| Distinct hosts | `gopal735.github.io` | **`scholarzone-fwzj.vercel.app` only** |
| Non-public IDs advertised | **207** | **0** |
| Public IDs missing | **87** | **0** |
| Duplicate URLs | 0 | **0** |
| Query-string URLs | 0 | **0** |
| Private / admin / API URLs | 0 | **0** |
| `lastmod` present | 487, stale from a September build | **367**, from each record's own `updated_at` / `last_verified_at` |
| Referenced by robots.txt | no (named the legacy host) | **yes, host agrees** |

370 URLs is well under the 50,000-URL and 50 MB guidelines, so **no sitemap index is needed** and none
was added. Line endings are LF-only, matching the repository convention.

## 4.5 Rendered pages — live, post-release

Each URL measured in a **fresh browser context**, so no route state carried between measurements.

| URL | HTTP | Title | Canonical | robots | JSON-LD | Content |
|---|---|---|---|---|---|---|
| `/` | 200 | `ScholarZone · Verified Scholarship Directory` | `…/` | `index, follow` | `WebSite` | 12,628 chars |
| `/scholarships` | 200 | `All Scholarships \| ScholarZone` | `…/scholarships` | `index, follow` | — | 6,665 chars |
| `/scholarships/1` | 200 | `Erasmus Mundus Joint Masters (EMJM) \| ScholarZone` | `…/scholarships/1` | `index, follow` | `ScholarArticle` + `BreadcrumbList` | 5,019 chars |
| `/scholarships/488` | 200 | `JWU Global Full Tuition Scholarship \| ScholarZone` | `…/scholarships/488` | `index, follow` | `ScholarArticle` + `BreadcrumbList` | 3,848 chars |
| `/countries` | 200 | `Explore Destinations \| ScholarZone` | `…/countries` | `index, follow` | `CollectionPage` (**ItemList, 19 items**) | 806 chars |
| `/scholarships?degree=Undergraduate` | 200 | `All Scholarships \| ScholarZone` | `…/scholarships` | **`noindex, follow`** | — | 6,665 chars |
| `/scholarships?country=Japan` | 200 | `Japan Scholarships \| ScholarZone` | `…/scholarships` | **`noindex, follow`** | — | 6,754 chars |
| `/scholarships?funding=Fully Funded` | 200 | `All Scholarships \| ScholarZone` | `…/scholarships` | **`noindex, follow`** | — | 6,665 chars |
| `/scholarships/999999` | 200 | `Scholarship · ScholarZone` | **none** | **`noindex, follow`** | none | "Scholarship not found" |
| `/no-such-route` | 200 | `ScholarZone · Verified Scholarship Directory` | **none** | **`noindex, nofollow`** | none | "We could not find that page." |

- **No JSON-LD parse errors** on any page.
- **No accidental `noindex`** on any intended indexable page.
- **No accidental crawler block.** All public paths return 200 anonymously.
- The only console entries anywhere were two expected `404`s on `/scholarships/999999` — the API
  correctly reporting that the record does not exist.

### A measurement note, recorded because it would otherwise look like a defect

An earlier pass that reused a single browser page reported `/` rendering the catalogue and
`/scholarships/1` rendering record 533. That was SPA route-state bleed between sequential `page.goto`
calls, not a site fault. Re-measured in isolated contexts, both render correctly as shown above.

## 4.6 `DIRECTORY_LIMIT=100` impact

`DIRECTORY_LIMIT = 100` lives in `frontend/src/hooks/useScholarshipDirectory.js:5`. Investigated as
instructed.

- It does **not** truncate the sitemap: the sitemap is generated from the database, not from that
  hook, and now carries all 367 records.
- It does **not** break direct detail URLs: verified for IDs 1, 488 and 623-range records.
- It **does** limit homepage link coverage to the first 100.

Assessment: it controls a UI/API page size for the homepage directory hook and the per-page load, and
the discovery layer (sitemap) is now complete. **Left alone**, per the instruction not to raise limits
blindly. No performance regression results from leaving it, and raising it would increase homepage
payload without improving discoverability, because the sitemap already closes the gap.

## 4.7 Internal linking

| From | To | Mechanism | Count |
|---|---|---|---|
| Homepage | `/scholarships/<id>` | `<Link>` anchors (`FeaturedStory`) | **17** |
| Homepage | `/scholarships?…` filters | anchors, now `noindex` | 25 |
| Catalogue | `/scholarships/<id>` | `<Link>` anchors (`ScholarshipCard`) | 12 per page |
| Detail | `/scholarships/<id>` related | `<Link>` anchors | present |
| Detail to catalogue | `/scholarships` | `<Link>` "All scholarships" | present |

**Honest limitation.** Catalogue pagination (31 pages) is `<button onClick>`, not anchors, so the
**link graph** covers roughly the first 100 records while the **sitemap** covers all 367. Making
pagination crawlable would require `?page=N` links, which robots.txt disallows and would therefore be
self-contradictory, or a path-based pagination scheme, which is a routing and UX change the brief does
not call for. The complete URL universe is reachable through the sitemap, the accepted mechanism for a
paginated catalogue. Recorded rather than silently left.

Anchor text is the real scholarship title, not keyword-stuffed.

## 4.8 404 and redirect behaviour

| Case | Result |
|---|---|
| Nonexistent ID (`/scholarships/999999`) | 200 + `noindex, follow`, no canonical, no JSON-LD, "Scholarship not found" |
| Unknown route (`/no-such-route`) | 200 + `noindex, nofollow`, "We could not find that page." |
| Deleted / retired ID (ID 42) | API 404; excluded from the sitemap |
| Non-public IDs (207 of them) | removed from the sitemap, so never advertised |
| Redirects | none added; no existing redirect or canonical destroyed |

**Known limitation, stated plainly.** The SPA fallback returns HTTP **200** for every path, so a
nonexistent scholarship is a soft-404 at the HTTP layer. A real 404 would require the frontend to know
the valid ID set at request time, which a static SPA rewrite cannot do. The mitigation is the
`noindex` directive plus explicit not-found content, the honest signal available in this architecture.
Nothing redirects a bad URL to the homepage.

## 4.9 Structured data

Audited before adding anything. No fabricated dates, ratings, reviews, awards or popularity figures.

| Page | Type | Status |
|---|---|---|
| Homepage | `WebSite` + `SearchAction` | **newly server-delivered**, still runtime-owned. Valid JSON |
| Detail | `ScholarArticle` + `BreadcrumbList` | preserved unchanged; every field copied from visible content |
| Destinations | `CollectionPage` (+ `ItemList` when populated) | `ItemList` fixed from empty to **19 real countries** |
| Catalogue | none | **deliberate** — it paginates 12 of 367, so an `ItemList` would misrepresent it |

All emitted JSON-LD parsed successfully in-browser on every page tested; no parse errors.

## 4.10 Tests

### Before commit

| Suite | Result |
|---|---|
| `npm run lint` | **0 errors**, 1 warning (`react-hooks/exhaustive-deps` on `HomePage.jsx:259`, **pre-existing**) |
| `npm run build` | **pass**, `dist/index.html` 4.30 kB |
| `npm test` (frontend) | **184 / 184**, 10 files — 163 pre-existing all still passing, plus 21 new |
| SEO / indexability suite | **21 / 21** |
| Routing suites (`ApplicationsPage`, `DashboardPage`, `MentorPage`) | **61 / 61** |
| `generate_sitemap.py` | imports cleanly; `BASE_URL` and `OUTPUT` resolve correctly |
| Backend visibility / Count tests | 60 passed, 1 failed — pre-existing, see below |
| Browser QA (local build) | 10 page loads, **0** page errors |

### CI on PR #8, head `16151af` — 9/9 green

```
import-smoke      success        git-integrity   success
backend-tests     success        frontend-tests  success
preflight         success        frontend-lint   success
env-config        success        build-and-smoke success
schema-compat     success        run conclusion: success
```

The merge was performed only after this run reported `success` and the PR head was re-confirmed as
`16151af362a5916331f8e379cc8e46c6c17b2f1f` (`MERGEABLE / CLEAN`, base `master`, not a draft).

**`backend-tests` passed on CI.** The local failure did not reproduce there, confirming it is a local
test-isolation artefact rather than anything introduced by this change.

### The one local backend failure — pre-existing, proven, not skipped

`tests/test_stats_universe_scope.py::test_public_review_count_is_derived_not_hardcoded` fails
(`assert 5 == 6`) **only when run alongside** the three visibility test files, and **passes when run
alone**. The identical four-file combination was run against a **pristine `fc4096f` worktree** and
produced the identical failure:

```
pristine fc4097f worktree : 1 failed, 60 passed   (same test, same assertion)
this branch               : 1 failed, 60 passed
either, run alone         : 1 passed
this branch on CI         : passed
```

It is a **test-isolation defect in the repository**, unrelated to SEO, and not caused by any change
here. Deliberately **not** fixed: it sits in Count/visibility logic, which this mission explicitly
excludes. Classified **ENVIRONMENTAL / PRE-EXISTING**.

## 4.11 Changed files and scope safety

Work performed in a clean worktree at `fc4096f`, because the primary checkout is 95 commits behind
master with 483 dirty entries — including a working tree with **no** `build_provenance.py`, so it could
not have been a valid basis for this work. **All 483 unrelated entries were left untouched and none
entered the commit.**

| Status | File | Change |
|---|---|---|
| M | `backend/app/data/generate_sitemap.py` | canonical base + shared visibility predicate |
| M | `frontend/index.html` | server-delivered head metadata + JSON-LD |
| M | `frontend/public/robots.txt` | base-path rules + canonical sitemap reference |
| M | `frontend/public/sitemap.xml` | regenerated, 370 URLs, canonical host |
| D | `frontend/scripts/generate-sitemap.js` | orphaned non-functional duplicate generator removed |
| M | `frontend/src/pages/CountryPage.jsx` | title + real `ItemList` |
| M | `frontend/src/pages/HomePage.jsx` | title, removed non-existent `og:image` |
| M | `frontend/src/pages/ScholarshipDetailsPage.jsx` | per-record title, conditional card type |
| M | `frontend/src/pages/ScholarshipsPage.jsx` | title, filter-variant noindex + canonical |
| M | `frontend/src/services/canonicalOrigin.js` | canonical production host |
| A | `frontend/src/seoContract.test.js` | 21-test regression guard |

```
11 files changed, 1254 insertions(+), 1714 deletions(-)
```

Staged by explicit path, so nothing could be picked up incidentally. PR #8's file list was then diffed
against the expected list: **11 expected, 11 actual, 0 unexpected, 0 missing.**

**Scope confirmation.** No Mentor, Match, Count, maintenance, verification, image, provenance,
release-identity or visual-redesign file appears in the diff, and `vercel.json` was **not** modified. No
secret was added to any file. Deployment Protection was not disabled or weakened. Nothing was
force-pushed and no history rewritten.

*(Note: `CountryPage.jsx` contains the substring "count" inside "Country". That is a false positive in
any naive `count` grep, not a change to Count Intelligence.)*

## 4.12 Search Console status

**Not connected.** Searching the entire repository for `google-site-verification`,
`searchconsole`, `search console`, `webmasters`, `bing-site-verification` and `msvalidate` yields one
hit: `README.md:676`, which states *"Search Console is not connected, so indexing status is
unverified."*

No verification was configured at audit time, no sitemap had been submitted, and no URL inspection had
been run. Part 5 covers what happened next.

---

# PART 5 — SEARCH CONSOLE OWNERSHIP VERIFICATION

## 5.1 Final classification of this task

```
GOOGLE_VERIFICATION_BLOCKED
```

**`GOOGLE_VERIFICATION_FILE_LIVE` is not reported, because no verification file was ever provided, and
`GOOGLE_OWNERSHIP_VERIFIED` is not reported, because verification was never attempted or completed.**

## 5.2 Root cause of the original failure: the tag was never deployed

The reported error was *"We couldn't find your verification meta tag."* **That was not a defect in the
tag.** It was a deployment problem, and it is now proven.

PR **#9** (`chore(seo): add Google Search Console verification`, head `ee6c601`, merged
`cfd0acaf00dc6bd2ec9ce30c6dbc2a128eae032b` at 2026-10-04T20:32:18Z) added:

```html
<meta name="google-site-verification" content="mzaQ_MW4nVgMwHhbSOxxTsr46gaV7sanks7vbnE7aaE" />
```

to `frontend/index.html`. It deliberately did **not** mark it `data-sz-seo`, so the per-page effect
that strips `[data-sz-seo]` nodes on every route cannot delete it. That reasoning is correct and the
placement is right.

**The Vercel GitHub App then refused to deploy it:**

```
Vercel - scholarzone-fwzj   failure   Deployment rate limited - retry in 24 hours.   (20:32:21Z)
Vercel - rc-revprov         failure   Deployment rate limited - retry in 24 hours.   (20:32:21Z)
Vercel - sz_god_wt          failure   Deployment rate limited - retry in 24 hours.   (20:32:21Z)
```

| | |
|---|---|
| master tip | `cfd0acaf…` — **contains** the verification tag |
| live production deployment | `dpl_6CvxptL5NBwibWHEmHJySkN8VTRo` = `cfb2b54…` — the previous merge |
| deployed == master | **false** |
| `google-site-verification` in `master:frontend/index.html` | **true** |
| `google-site-verification` in the live served `/` | **false** |

Google fetched a build that predates the tag. The error it reported was accurate about what it
received, and says nothing about whether the tag works.

## 5.3 Blocker 1: the Google file was never provided

The mission brief for this pass contains a literal placeholder where the file belongs:

```
GOOGLE PROVIDED FILE:
<PLACE THE EXACT DOWNLOADED GOOGLE HTML VERIFICATION FILE IN THE REPOSITORY>
```

That is the placeholder text itself, not a file. A search came back empty everywhere:

| Searched | Result |
|---|---|
| `google*.html` in the primary working tree | none |
| `google*.html` in the SEO worktree | none |
| `google*.html` added anywhere in git history, all branches | none |
| `google-site-verification` token in any file | none, outside PR #9, which landed after this search |

**No filename or token was invented.** A fabricated `google<random>.html` would never satisfy Google,
would put untrue content on a public website, and would make the next person waste a verification
attempt on it. That is worse than doing nothing.

## 5.4 Blocker 2: the same rate limit blocks the file method too

Publishing a verification file has the same dependency: **nothing reaches the canonical host until a
Git-integrated deployment succeeds.** The rate limit was hit at 20:32:21Z and the provider asks for a
24-hour wait. A CLI or manual deployment would bypass it and is forbidden by rule.

So a file committed now would sit in master, undeployed — exactly as the tag is doing now.

## 5.5 Discovery complete: the publishing path is proven, not assumed

Everything except the file itself is settled and verified.

**Which directory becomes the deployed public root:**

| Step | Finding |
|---|---|
| `frontend/vite.config.js` | sets only `base`; **no `publicDir` override**, so Vite's default `public/` applies |
| Build command | `npm run build` -> `vite build`, output `dist` (`frontend/vercel.json`: `outputDirectory: dist`) |
| `frontend/public/` currently ships | `404.html`, `favicon.svg`, `icons.svg`, `robots.txt`, `sitemap.xml` |
| `dist/` root after build | all five appear at the root, alongside `index.html` and `assets/` |

So **`frontend/public/` is the correct and only location.** A file placed there is copied verbatim to
`dist/` root by the build, and is therefore published at
`https://scholarzone-fwzj.vercel.app/<filename>`.

**The SPA-fallback rewrite will not swallow it — proven by a natural experiment.** The frontend service
rewrites `/((?!api/).*)` -> `/index.html`, so the real question is whether that intercepts a `.html`
file that exists in the output. The repo already ships `public/404.html`, which makes this directly
testable against production without adding anything:

| Request | HTTP | Bytes | Served as |
|---|---|---|---|
| `/404.html` — **exists** in `public/` | **200** | **1,092** | **its own content**, `text/html`, `spaShell=false` |
| `/favicon.svg` — exists | 200 | 9,522 | its own content, `image/svg+xml` |
| `/robots.txt` — exists | 200 | 1,710 | its own content, `text/plain` |
| `/sitemap.xml` — exists | 200 | 67,994 | its own content, `application/xml` |
| `/definitely-missing-file.html` — **absent** | 200 | **4,299** | **the SPA shell** — fallback substituted |

The contrast is conclusive: a file that exists in `public/` is served verbatim at the root, and only an
absent one falls through to the SPA shell. Static output takes precedence over the rewrite.

**Therefore, once the file exists and a deployment succeeds, all of these will hold** (each proven by
the experiment above or by the open-access check in 4.2):

- HTTP 200
- exact filename and exact content
- no redirect to another domain
- no authentication — the public alias is already confirmed open
- not an HTML shell
- not a Vercel 404
- no SPA-fallback substitution

## 5.6 To finish, two things are needed

**Option A — zero code work, and the fastest route.** The verification tag is already in master. Wait
for the Vercel build-rate-limit window to clear, confirm the tag is present on the live site, then
click **Verify** in Search Console again. The previous failure was a deployment timing artefact, not a
defect in the tag.

**Option B — the HTML file method, as requested.** Requires the exact filename and exact file content
that Google downloaded. For this method that is a single-line file, shaped like:

```
google-site-verification: google<token>.html
```

with the filename `google<token>.html`. **Both the filename and the content must come from Google** —
they are a matched pair and neither can be derived. Once supplied, the remaining work is mechanical and
already validated:

1. write the file to `frontend/public/<filename>`, byte-for-byte, unwrapped, not generated;
2. `npm run lint` and `npm run build`, then confirm `dist/<filename>` exists at the root;
3. commit **only that one file**, push, PR, merge — no force-push, no CLI deployment;
4. let the Git-integrated deployment run;
5. fetch `https://scholarzone-fwzj.vercel.app/<filename>` anonymously and verify it;
6. confirm the Part 4 SEO checks still hold;
7. the owner clicks **Verify** in Search Console.

The file must then be left in place — Google requires it to remain available for verification to stay
valid. It will not be removed.

## 5.7 Owner actions, consolidated

1. Wait out the Vercel build-rate-limit window that began **2026-10-04T20:32:21Z**.
2. Confirm the verification tag is live: `https://scholarzone-fwzj.vercel.app/` should contain
   `<meta name="google-site-verification" content="mzaQ_MW4nVgMwHhbSOxxTsr46gaV7sanks7vbnE7aaE">`.
3. Click **Verify** in Search Console. Then, once verified, submit
   `https://scholarzone-fwzj.vercel.app/sitemap.xml`.
4. Run **URL Inspection** on the homepage and on at least one detail URL, e.g.
   `https://scholarzone-fwzj.vercel.app/scholarships/1`.
5. Request indexing for the homepage and a small set of priority detail pages.
6. Monitor the **Sitemaps** and **Page Indexing** reports.
7. Optional: consider a custom domain. It would make the canonical host durable and brand-owned, and is
   the single highest-value change for long-term Search Console continuity.
8. Optional maintenance: the sitemap is a committed artefact, not build-generated. Re-run
   `backend/app/data/generate_sitemap.py` whenever the catalogue changes, or it will drift. The
   generator is now correct and uses the same visibility predicate as the public API, so re-running it
   is safe.

## 5.8 Nothing else was touched in the verification pass

No backend behaviour, scholarship data, Count, Match, Mentor, maintenance, verification logic, image
handling, provenance or release identity was modified. `robots.txt` and `sitemap.xml` were **not**
changed — the verification file needs no crawl-policy change, because it is a static asset rather than
an indexable page, and it is not linked from any page or sitemap. The canonical origin was not changed.
No existing SEO metadata was removed. No manual or CLI deployment was made. No branch was force-pushed
and no history rewritten. No unrelated dirty work was reset or cleaned. No commit was created in the
verification pass.

---

# PART 6 — CHAIN, ACCEPTANCE, AND LIMITS

## 6.1 The chain, as proven against the live deployment

```
PUBLIC CANONICAL URL   https://scholarzone-fwzj.vercel.app      PROVEN - canonical project, holds prod aliases
-> DEPLOYED             GitHub App, source=git, ref=master       PROVEN - dpl_6CvxptL, gitSource.sha = cfb2b54
-> CRAWLABLE            200 anonymously, no auth wall          PROVEN - Googlebot UA, every path 200
-> DISCOVERABLE         robots.txt advertises the sitemap      PROVEN - Sitemap: line, HTTP 200, host agrees
-> INDEXABLE            index,follow on all intended pages    PROVEN - rendered live in a real browser
-> CANONICAL            one origin, self-canonical             PROVEN - 370/370 sitemap + every canonical
-> MEANINGFUL CONTENT   real scholarship text, real h1        PROVEN - 3,848 to 12,628 chars per page
-> SITEMAP              370 valid URLs, complete set          PROVEN - live XML, 367 detail = stats.total
-> OWNERSHIP VERIFIED   NOT CONFIGURED                        PROVEN - tag undeployed, file never provided
                        BLOCKED - rate limited + file missing
```

## 6.2 Release chain

```
fc4096f   audited baseline, the defects live
  +-- 16151af   fix(seo), 11 files                    (PR #8, CI 9/9 green)
      +-- cfb2b54   merge commit on master, 20:18:18Z
          +-- dpl_6CvxptL   source=git, target=production, gitSource.sha=cfb2b54
              +-- live /api/health revision = cfb2b54d03341316985e66c7963a4c73976d33ef
                  +-- cfd0aca   verification tag (PR #9)  UNDEPLOYED - rate limited
```

## 6.3 Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| A | canonical public frontend identified | **PASS** | `https://scholarzone-fwzj.vercel.app`, from deployed config; no custom domain exists |
| B | robots.txt correct and publicly reachable | **PASS** | HTTP 200 anonymously; base-path rules; no accidental block |
| C | sitemap exists and is valid | **PASS** | HTTP 200, valid XML, 370 URLs, LF endings |
| D | sitemap contains the intended indexable URL universe | **PASS** | 3 routes + all **367** public records, matching `stats.total` and 4-page enumeration |
| E | sitemap uses canonical hostname | **PASS** | 370/370 on the canonical host |
| F | homepage indexability verified | **PASS** | metadata server-delivered and correct after render |
| G | scholarship detail indexability verified | **PASS** | two independent records, unique titles, own canonical, structured data |
| H | direct detail URLs work | **PASS** | deep link and refresh verified, no prior interaction |
| I | title / meta / canonical verified | **PASS** | unique per page; canonical deterministic |
| J | filter / query duplicate policy verified | **PASS** | `/*?*` + `noindex, follow` + canonical to clean catalogue |
| K | JSON-LD valid where used | **PASS** | all blocks parsed in-browser; empty `ItemList` fixed to 19 real items |
| L | no accidental noindex | **PASS** | `index, follow` on every intended page |
| M | no accidental robots block | **PASS** | assets and public pages allowed |
| N | no soft-404 behaviour discovered | **PASS WITH KNOWN LIMITATION** | `noindex` + not-found content; HTTP 200 from the SPA fallback is inherent |
| O | internal discoverability works | **PASS** | homepage 17 detail anchors, catalogue 12/page; sitemap closes the pagination gap |
| P | frontend build passes | **PASS** | `built in 458ms`; `build-and-smoke` green on CI |
| Q | browser QA passes | **PASS** | 10 page loads, 0 errors, re-verified live post-deployment |
| R | no unrelated changes | **PASS** | 11 files, all SEO/indexability; `vercel.json` untouched; 483 unrelated dirty entries left alone |
| S | production writes = NONE | **PASS** | read-only throughout; no manual deployment created |

## 6.4 Honest limitations

1. **No indexing claim.** `site:scholarzone-fwzj.vercel.app` returns **0 results**. Without Search
   Console, **NOT DISCOVERED YET** and **NOT INDEXED** cannot be told apart, and that is stated rather
   than guessed. It is explicitly **not** "blocked from indexing": after this release no robots,
   canonical or auth blocker remains.
2. **Per-record metadata is still client-side.** The homepage's metadata is now server-delivered, but
   per-record titles, descriptions and JSON-LD still require JavaScript. Google renders JavaScript;
   other crawlers may not. Deliberate: the brief forbids a framework migration for SEO, and
   build-time prerendering of 367 records is a separate architectural decision, not a bug fix.
3. **Pagination is button-based**, so link-graph coverage (~100) is narrower than sitemap coverage
   (367). Reasoned in 4.7.
4. **HTTP 200 for unknown detail URLs** is inherent to a static SPA fallback. Reasoned in 4.8.
5. **The sitemap is a committed artefact**, not build-generated. It will drift as records change. See
   5.7 item 8.
6. **One pre-existing local backend test failure**, unrelated, left unfixed, proven pre-existing in
   4.10 and passing on CI.
7. **The canonical host is a `*.vercel.app` alias.** Stable and correct today, but a custom domain
   would be more durable. Owner action, 5.7 item 7.
8. **Ownership verification is not done**, and cannot be completed from here. See Part 5.

## 6.5 WARNING: the primary checkout has pre-staged work that would revert the SEO release

Found while verifying that nothing leaked into unrelated work. **This needs action.**

The primary checkout (`C:\Users\GopaL\Desktop\Projects folder\ScholarZone`) has **40 files already
staged** that predate and are unrelated to this task: maintenance jobs, auto-delete policy and
collector, `models.py`, `database.py`, supervisor services, and a broad set of frontend CSS plus
`ScholarshipList.jsx`, `main.jsx`, and four of the page components this SEO work also touched.

**Those staged copies are the pre-SEO versions.** Verified directly from the index:

| Staged file | Still contains the bug this release fixed |
|---|---|
| `frontend/src/pages/CountryPage.jsx` | `itemListElement: []` — the empty `ItemList` |
| `frontend/src/pages/HomePage.jsx` | `og-image.png` — reference to a non-existent asset |
| `HomePage`, `CountryPage`, `ScholarshipsPage`, `ScholarshipDetailsPage` | no `document.title` handling at all |

**Consequence: committing from the primary checkout would revert the live SEO fixes.** That is how the
local checkout is 95 commits behind master — it predates the whole release.

The SEO work itself is **safe**, because it was done in a separate clean worktree with explicit-path
staging, and it is committed on `origin/master`:

```
origin/master = cfd0acaf…  contains cfb2b54…  contains 16151af…
master canonicalOrigin default = https://scholarzone-fwzj.vercel.app
master contains frontend/src/seoContract.test.js = true
```

**Recommendation.** Do not commit from the primary checkout as it stands. Either reconcile it against
`origin/master` first, or keep releasing from a clean worktree as was done here. That pre-staged set
should be reviewed on its own merits before anyone commits it, and it is unrelated work that this
audit deliberately left untouched.

## 6.6 Final classifications

**SEO / indexability work:**

```
GOOGLE_INDEXING_READY_OWNER_ACTION_REQUIRED
```

Ready, deployed, and live-verified. Not indexed, and not claimed to be. Search Console remains
unconnected, which is the only outstanding item.

**Search Console ownership verification:**

```
GOOGLE_VERIFICATION_BLOCKED
```

The Google HTML verification file was never provided, and the Git-integrated deployment path is
rate-limited. No verification file was invented, nothing was committed in that pass, and no success is
claimed.

```
PRODUCTION WRITES = NONE
```

---

# PART 7 — DEPLOYMENT PIPELINE DIAGNOSIS (2026-10-05 05:25Z–05:30Z)

## 7.1 Classification

```
DEPLOYMENT_PIPELINE_BLOCKED
```

**The Git integration is not broken.** There was no configuration fault to repair, and no
configuration change was made. The pipeline is healthy and demonstrably so; it was stopped by a
provider-side deployment quota, and the only remaining ways to deploy `cfd0aca` are manual, which is
out of scope by instruction.

## 7.2 STEP 1 — Git connection inspection: everything healthy

| Check | Result |
|---|---|
| project | `scholarzone-fwzj` / `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| `link.type` | `github` |
| connected repository | `ScholarZone`, `repoId=1354421070`, `org=gopal735`, `repoOwnerId=211871430` |
| GitHub App access | **present** — `gitCredentialId` is set, and the App answered pushes (7.4) |
| `link.productionBranch` | **`master`** |
| `link.sourceless` | `true` — vestigial flag from CLI project creation; Git builds still occur |
| `link.deployHooks` | `[]` |
| `vercel.json` on `origin/master` | **no** `git` block, **no** `deploymentEnabled`, **no** `ignoreCommand` |
| production environment | accepts master deployments; 6 production-scoped env vars present |

No repository-side rule disables Git deployment. The two-service `vercel.json` contains only service
routing and the SPA rewrite.

## 7.3 STEP 2 — root cause

```
provider rate limit  (Vercel build/deployment quota)
NOT: disconnected repository
NOT: GitHub App permission
NOT: production branch mismatch
NOT: automatic deployment disabled
NOT: deployment check / promotion block
```

The provider's own commit status on `cfd0aca`, posted **3 seconds** after the push:

```
Vercel - scholarzone-fwzj   failure   Deployment rate limited - retry in 24 hours.   (20:32:21Z)
Vercel - rc-revprov         failure   Deployment rate limited - retry in 24 hours.   (20:32:21Z)
Vercel - sz_god_wt          failure   Deployment rate limited - retry in 24 hours.   (20:32:21Z)
```

The status URL Vercel attached points at `vercel.com/gopal735s-projects?upgradeToPro=build-rate-limit`,
i.e. a **plan quota**, not a project setting. That cannot be changed by configuration; it resets with
time or by upgrading the plan.

## 7.4 Proof the pipeline itself is healthy

The Vercel GitHub App answered **both** pushes within 3 seconds, and handled the first one correctly:

| Push | Response | Outcome |
|---|---|---|
| `cfb2b54` at 20:18:18Z | deployment created 20:18:21Z | **succeeded**, `source=git`, `target=production` |
| `cfd0aca` at 20:32:18Z | status posted 20:32:21Z | refused, quota |

A disconnected repository, missing App permission, wrong production branch, or disabled auto-deploy
would all produce **no response at all** or a permanent misconfiguration error. Vercel answered both in
3 seconds and built one of them. The integration is connected, authorised, correctly branched and
enabled.

The refusal was also **one-shot**. Across all four Git-connected projects there have been **zero
deployments** in the 8 h 56 m since the refusal, and the commit status has not been touched since
20:32:21Z. Vercel does not re-process a push event it has already refused.

Quota context for 2026-10-04, account-wide:

| project | deployments on Oct-04 |
|---|---|
| scholarzone-fwzj | 60 |
| rc-revprov | 8 |
| sz_god_wt | 3 |
| **total** | **71** |

The successful `cfb2b54` deployment was **#71 of the day**. The `cfd0aca` request was the next one and
was refused — so the effective ceiling was reached at that point.

## 7.5 STEP 3 — no fix applied, because nothing is misconfigured

| Candidate fix | Why not applied |
|---|---|
| Reconnect / re-authorise the GitHub App | App is authorised and responding |
| Change production branch | already `master` |
| Re-enable automatic Git deployments | already enabled; it built `cfb2b54` three hours earlier |
| Edit `vercel.json` to force Git deploys | no `git` rule exists to change, and editing it would be an application-config change with no effect on a quota |
| Clear the rate limit | not a configuration knob; it is a plan quota that resets with time or a paid upgrade |

**No provider-side or repository-side configuration was changed.** A change would have been
cosmetic at best, and billing or plan changes are not mine to make.

## 7.6 STEP 4 — why `cfd0aca` cannot be deployed by the Git integration

Every remaining path was evaluated against the constraints:

| Path | Verdict |
|---|---|
| Wait for the provider to retry the refused push | **Will not happen.** The status is terminal and has not moved in 8 h 56 m. Verified, not assumed. |
| Push a new commit to trigger a new event | **Forbidden.** "Do NOT manufacture a new application commit merely to trigger deployment" — and it would move master off `cfd0aca`, breaking the required `gitSource.sha = cfd0aca…` |
| Re-run a GitHub workflow | **Impossible.** No workflow in this repository creates a Vercel deployment. Verified across all 11 workflow files on `origin/master`. The `deploy` check run on `cfd0aca` belongs to `deploy.yml`, which is the *deployment verification* workflow — its `verify-native-github-deployment` job is what fails when no deployment exists. |
| Vercel dashboard "Redeploy" / "Deploy" | Manual, and owner-only (no browser session for vercel.com) |
| `vercel deploy` / Vercel REST deployment | **Forbidden explicitly** |

## 7.7 STEP 5 — what is live right now

| | |
|---|---|
| master | `cfd0acaf00dc6bd2ec9ce30c6dbc2a128eae032b` |
| production serving | `cfb2b54d03341316985e66c7963a4c73976d33ef` (`dpl_6CvxptL5NBwibWHEmHJySkN8VTRo`) |
| deployed == master | **false** |
| deployments of `cfd0aca` | **0** |
| live `/api/health` revision | `cfb2b54d03341316985e66c7963a4c73976d33ef` (40 lowercase hex) |
| live homepage | 4,299 bytes, canonical `https://scholarzone-fwzj.vercel.app/` |
| **Google verification tag live** | **false** — absent, because `cfd0aca` was never built |
| live SEO otherwise | intact and unchanged |

`GOOGLE_VERIFICATION_READY_OWNER_ACTION_REQUIRED` is **not** claimed, because the live build does not
contain the tag.

## 7.8 Owner actions to unblock

In order of preference, all owner-side:

1. **Wait for the daily quota to reset**, then trigger the Git build from the Vercel dashboard for the
   connected repository on branch `master`. That builds the existing `cfd0aca` from Git — no new commit,
   no SHA change, no CLI. This is the smallest reversible action and is the Git-connected path.
2. **Alternatively, upgrade the plan** if daily deployment volume is genuinely exceeded. 71
   deployments in one day across four connected projects is what triggered this, and the volume is
   worth reviewing on its own merits.
3. **Reduce deployment volume.** Four Vercel projects are Git-connected to the same repository and all
   build on every push. That multiplies the quota cost of every merge by roughly four. Reviewing
   whether all four need automatic deployments would be the highest-leverage permanent fix.
4. Once the deployment exists, confirm the live tag at
   `https://scholarzone-fwzj.vercel.app/` contains
   `<meta name="google-site-verification" content="mzaQ_MW4nVgMwHhbSOxxTsr46gaV7sanks7vbnE7aaE">`,
   then click **Verify** in Search Console.

**No claim is made that Google ownership verification succeeded.**