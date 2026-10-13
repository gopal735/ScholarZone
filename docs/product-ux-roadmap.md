# Product UX roadmap

> Status: **wave 1 complete and under review** (PR against `master`).
> Scope: the Tutorials & Help Center foundation plus the contextual help entries
> across the product. Remaining feature upgrades are scheduled as waves 2+ below.
>
> Nothing in this document describes an intention as though it shipped. Each
> claim is either implemented and covered by a test, or explicitly listed under
> "Remaining work" with its acceptance criteria.

---

## 1. What this repo actually ships

The route table below is the audit's source of truth. It is derived from
`frontend/src/App.jsx` and cross-checked against the tutorial registry's
`ROUTES` map (`frontend/src/features/tutorials/lib/routeMap.js`), which is the
same data the Help Center filters on. A route with no tutorial is not an
oversight; section 3 lists every deliberate exclusion and why.

| Route | Page | Audience | Tutorial | Notes |
|---|---|---|---|---|
| `/` | HomePage | public | `home` | |
| `/countries` | CountryPage | public | `countries` | |
| `/scholarships` | ScholarshipsPage | public | `scholarships` | |
| `/match` | MatchPage | public | `match` | Deterministic, no AI |
| `/scholarships/:id` | ScholarshipDetailsPage | public | `scholarship-details` | |
| `/login` | LoginPage | public | `account` | Shares one form with `/register` |
| `/register` | RegisterPage | public | `account` | |
| `/saved` | SavedScholarshipsPage | public | `saved` | Signed-in: server shortlist |
| `/plan` | PlanPage | public | `plan` | Browser-local workspace |
| `/statement` | SopBuilderPage | public | `statement` | Browser-local workspace |
| `/dashboard` | DashboardPage | auth | `dashboard` | Server-resolved access |
| `/applications` | ApplicationsPage | auth | `applications` | |
| `/applications/:applicationId` | ApplicationsPage | auth | `applications` | |
| `/mentor` | MentorPage | auth | `mentor` | |
| `/compare` | ComparePage | public | `compare` | Device-local selection |
| `/bangladesh-journey` | JourneyPage | public | `bangladesh-journey` | Has its own i18n |
| `/bangladesh-journey/:stepId` | JourneyPage | public | `bangladesh-journey` | Deep-linked step |
| `/help` | HelpCenterPage | public | — | **new in this wave** |
| `/admin` | AdminPage | **admin** | `admin` | Gated by `X-Admin-Secret` |
| `/admin/verification` | AdminVerificationPage | **admin** | `admin` | |
| `/admin/scholarships` | AdminScholarshipPage | **admin** | `admin` | |
| `/consistency-review` | ConsistencyAuditorPage | public | **none** | `enabled` is committed `false` |

### Feature inventory, by the tasks a student actually arrives with

| Goal | Feature | Route(s) |
|---|---|---|
| Find scholarships that fit me | Catalogue, Match | `/scholarships`, `/match` |
| Understand one scholarship properly | Scholarship details | `/scholarships/:id` |
| Compare two or more | Compare | `/compare` |
| Keep track of deadlines | Plan, Journey timeline | `/plan`, `/bangladesh-journey` |
| Work out what it will cost me | Countries, Journey costs | `/countries`, `/bangladesh-journey` |
| Write my statement of purpose | Statement builder | `/statement` |
| Know what an application needs | Applications workspace | `/applications` |
| Get my documents ready | Journey documents step | `/bangladesh-journey` |
| Find the steps for applying from Bangladesh | Applicant journey | `/bangladesh-journey` |
| See what I have done so far | Dashboard, Saved | `/dashboard`, `/saved` |
| Manage the catalogue | Admin tools | `/admin/*` |

---

## 2. What wave 1 delivered

### 2.1 Tutorials & Help Center (`/help`)

A single directory for every user-facing feature, searchable across the whole
guide rather than just its title, with category filters and a goal index.

**Files**
- `frontend/src/features/tutorials/lib/registry.js` — the 15 tutorials, in `{en, bn}`
- `frontend/src/features/tutorials/lib/routeMap.js` — route → tutorial id, no prose
- `frontend/src/features/tutorials/lib/tutorialSchema.js` — storage shape
- `frontend/src/features/tutorials/lib/tutorialStorage.js` — storage adapter
- `frontend/src/features/tutorials/i18n/strings.js` — UI chrome, `en`/`bn`
- `frontend/src/features/tutorials/i18n/useTutorialsI18n.js` — `t`, `both`, `prose`
- `frontend/src/features/tutorials/state/` — shared language + dismissals
- `frontend/src/features/tutorials/hooks/useHelpCenter.js` — search/filter state
- `frontend/src/features/tutorials/components/` — `TutorialDetail`, `HowToUse`
- `frontend/src/features/tutorials/HelpCenterPage.jsx`
- `frontend/src/features/tutorials/tutorials.css`

**Each tutorial carries:** purpose, when to use it, ordered steps, what to type
into each box (with a worked example), how to read the result, common mistakes
with fixes, where the data is kept, and what the feature does **not** guarantee.

**Design decisions worth knowing**

- **Prose is lazy-loaded.** The registry is 138 kB of two-language text. Because
  `HowToUse` is mounted on seven pages, importing it eagerly put all of it in the
  initial bundle for every reader. `routeMap.js` is a tiny separate module that
  answers "does this route have a tutorial?" without the prose; the prose loads
  only when a guide is opened. Build now emits `registry-*.js` as its own chunk
  and the main chunk is ~165 kB smaller.
- **Search, category and the open tutorial live in the URL**, so a filtered view
  is shareable and survives reload — the same reason the catalogue's filters are
  URL-bound.
- **Shared language and dismissals live in one provider.** The first version had
  each component hold its own copy, so a choice made on `/help` did not reach the
  panel on a feature page, and dismissing a guide in the panel updated state the
  trigger could not see. Both were real bugs caught by tests, not assumptions.
- **Dismissal is the reader's to undo.** The trigger does not auto-reopen a
  dismissed guide; the guide's own control does. The first version overrode the
  reader's choice and wrote to storage on every open.
- **The admin group is opt-in visibility, not authorisation.** The auth context
  carries no role — admin access is enforced by an `X-Admin-Secret` header
  resolved server-side — so the directory shows a labelled opt-in rather than
  pretending to derive staff status from a session. Showing a guide grants
  nothing.

### 2.2 Contextual "কীভাবে ব্যবহার করবেন?" on feature pages

`HowToUse` renders above the primary heading on the seven pages that have a
tutorial: Scholarships, Match, Countries, Saved, Compare, Plan, Statement.

- It renders **nothing** on a route with no tutorial, so `/consistency-review`
  gets no button whose panel would say the guide is missing.
- The panel is a `region` in flow, not a dialog, so it cannot cover a primary
  action or trap a keyboard user.
- Open does not move focus; Escape closes and returns focus to the trigger.
- `Help` was added to the navigation's utility row.

### 2.3 Guardrails preserved

Every existing safeguard is intact and covered: the Match engine is still
deterministic, Plan and Statement are still browser-local with accurate privacy
copy, the journey still carries its own Bangla/English i18n, and the consistency
auditor is still disabled. Tutorials never assert an outcome; a test asserts the
whole registry is free of outcome-promising phrases.

---

## 3. Known exclusions, and why each is deliberate

| Route | Why no tutorial |
|---|---|
| `/consistency-review` | The feature's own `enabled` flag is committed `false`; the route renders the not-found page. A guide would send a reader somewhere that 404s. Listed on `/help` as a deliberate exclusion, and `registry.test.js` asserts the exclusion list, so enabling the flag fails a test instead of leaving a stale guide. |
| `/help` itself | Self-referential; the intro text covers it. |

**Unverified, and not claimed:** no browser-based verification was run in this
wave — no Playwright, no Lighthouse, no device check. Responsive behaviour is
implemented (mobile-first single column, `900px` breakpoint for the split,
44px touch targets) but is asserted by the stylesheet's own rules rather than by
a measured viewport. Accessibility is implemented through semantics (`region`,
`aria-expanded`, `aria-controls`, labelled controls) but was not run through
axe or a screen reader.

---

## 4. Remaining work, as reviewable waves

Each wave is scoped to be reviewed on its own. Acceptance criteria are written so
a reviewer can tell done from nearly-done.

### Wave 2 — Accessibility verification and responsive confirmation
- **Why next:** the UI is built to be accessible but nothing has *verified* it.
- **Work:** add Playwright (or the repo's existing e2e harness if it can support
  it) to check `/help` at 320/360/390/768/1280/1440, keyboard traversal, and
  axe on the Help Center plus one tutorial's detail. Fix what it finds.
- **Acceptance:** measured results recorded in the PR description; no horizontal
  overflow at 320px; every interactive control reachable by keyboard with visible
  focus; axe clean or a documented, justified exception.

### Wave 3 — Tutorial content depth
- **Why:** current tutorials are accurate but brief; "common mistakes" is the
  section that pays for itself and it is the thinnest.
- **Work:** expand each tutorial's mistakes/recovery with the real support
  cases; add worked examples for Match's profile fields and the statement
  builder's word-limit source.
- **Acceptance:** each tutorial names at least three recoverable mistakes; every
  example uses a value that actually exists in the catalogue.

### Wave 4 — First-use discovery without an onboarding modal
- **Why:** a first-time visitor has no signal that _Help_ exists.
- **Work:** a single, dismissible pointer from the home page to the Help Center,
  persisted through the tutorials store — with no multi-step tour and no
  focus theft.
- **Acceptance:** a reader who dismisses it never sees it again; the pointer is
  keyboard-reachable and announced; no modal.

### Wave 5 — Error and empty-state review across the catalogue
- **Why:** the audit found inconsistency in how empty, loading and failure states
  read across the catalogue, saved, compare and match.
- **Work:** a shared empty/loading/error pattern, applied per page.
- **Acceptance:** each of those pages has a recovery action, not just a message;
  no page silently shows a blank list.

### Wave 6 — Bangla coverage for the wider app
- **Why:** only the journey and the tutorial system are bilingual; the rest of
  the app's own chrome is English.
- **Work:** decide scope with the maintainer — the tutorials are bilingual today,
  and extending the product's own UI is a larger decision than a content one.
- **Acceptance:** a written scope decision in this document before any UI work.

---

## 5. Evidence

| Check | Command | Result |
|---|---|---|
| Tutorial tests | `npx vitest run src/features/tutorials` | 102 passed |
| Full frontend suite | `npm test` | 43 files / 1102 passed |
| Lint | `npm run lint` | clean |
| Production build | `npm run build` | 640 modules, `registry-*.js` emitted separately |

Not run in this wave: browser/e2e checks, Lighthouse, device testing, axe.
