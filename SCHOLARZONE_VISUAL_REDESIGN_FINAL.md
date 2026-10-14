# SCHOLARZONE_VISUAL_REDESIGN_FINAL.md

Fourth pass, finalised. Fifty live research tracks, a multi-source synthesis, a
design thesis, a dedicated-worktree commit, and browser QA on the real
application. Every number in §7 was measured.

Evidence: `SCHOLARZONE_50_AGENT_RESEARCH_SYNTHESIS.md` (tracks + evidence
matrix) → `SCHOLARZONE_DESIGN_THESIS.md` (the reasoning).

---

## 1. A correction I have to make first

**I destroyed three subagent deliverables with a careless shell script.**
`AuthForm.css`, `MatchPage.css` and `NotFoundPage.css` were blanked by a
bisection probe whose restore hit file locks. They are recovered from `HEAD` and
migrated to 3.0 tokens, so they build and render — but they are the *previous*
composition, not the redesign two agents had produced for them. `/login`,
`/match` and 404 therefore ship on the 3.0 token system without the route-level
redesign. That is my error, not a research outcome, and it is why the
classification below is NEEDS_ITERATION rather than READY.

The `CountryPage` / `ComparePage` / `SavedScholarshipsPage` redesign from the
other agent survived and is present.

---

## 2. Git safety

| | |
|---|---|
| Main tree HEAD | `8ac1c9a` — **unchanged** |
| Main tree dirty non-frontend files | 392 — **preserved, untouched** |
| Main tree dirty frontend files | 91 — **preserved** |
| Reset / clean / restore of unrelated files | **none** |
| Where the work was committed | `.kilo/worktrees/sz-visual-final`, branch `feat/editorial-visual-system-3`, commit `2eac2f3` |
| Files in the commit | **59, all under `frontend/`** — verified: nothing outside `frontend/src` |
| Backend / database / maintenance / provenance / Count / Match / data changes | **none** |

The commit was made in a dedicated clean worktree based on `origin/master`, as
required, precisely so that the main tree's hundreds of unrelated dirty files
could not be staged by accident.

The worktree has no `node_modules`, so its own `npm run lint` / `npm run build`
were not executed there. The 30 copied files were verified **byte-identical**
(SHA-256) to the main tree, where both commands do pass — so the build claim
rests on identical content, and I am stating that rather than implying the
worktree was independently built.

---

## 3. What this pass changed

### 3.1 The detail page — rebuilt, not re-skinned

It was 5,698px of ten bordered blocks. Three changes did the work.

**A spec strip** directly under the title: deadline · funding · study level ·
country, four fixed cells on one rule, deadline in the serif as the largest
field on the page. This is TU Delft's scholarship spec table (identical row
labels in identical order on every award) and Cambridge's three-tier funding
taxonomy — both put the DECISION fields in a comparable band before the prose,
because the reader's first question is "can I apply and what does this pay",
not "tell me about it".

**Four questions in four sections**, each headed by an eyebrow that *is* the
question — *What it is · Can I apply · What it pays · What to prepare · How to
apply · Also worth knowing · **Can I trust this*** — so a reader who scans
eyebrows gets what a reader of headings gets.

**Provenance moved into the record**, not only the aside. On a 5,000px page the
aside has scrolled away by the time a reader reaches the claim, and the claim
is the reason the product is worth anything.

Verified: the deadline is rendered **exactly once** on the page. Detail research
found a competitor repeating it five times; the rule adopted here is *delegate,
do not restate*.

### 3.2 The 1024–1280 weakness — solved from evidence

Page head **263px → 85px** (a bar, not a taller header). The rail moved to
**≥1280**: M3 says a medium layout recommends "a single pane… because of
limited screen width", GOV.UK adds nothing at 1024 and centres, and Bootstrap
and Polaris both put their first large step at 1040. The arithmetic agreed — a
240px rail at 1440 left the results ~950px, which cannot hold the row's five
tracks, so every row folded and three were visible. Five selects were costing
the list a third of its width to sit beside 1,469 rows' worth of facets.

Below 1280 the rail is a right drawer with scrim, Escape-to-dismiss and a
persistent `Show N results`.

### 3.3 The state word removed from the row

`Open` restated a deadline already on the row. Three encodings of one fact is
what made the list read as a status board. **Trust evidence untouched** — the
source host and the read date both stay.

### 3.4 Four WCAG failures, found by computing the ratios

| | Was | Now |
|---|---|---|
| `--ink-4` — the colour of **every 12px label** | **2.86:1 FAIL** | 4.52:1 |
| Control borders | **1.35 / 1.68:1 FAIL** (1.4.11) | 3.14:1 |
| Row state by background luminance alone | **1.14:1** — fails 1.4.11 *and* 1.4.1 | 2px left bar + tint |
| Focus Not Obscured (2.4.11) | rows scrolled under the sticky masthead | `scroll-margin-top: 96px` |

The left bar is a **shape, not a colour** — it survives greyscale, colour
blindness and forced-colours mode.

### 3.5 Empty and error states, all four wired

`EmptyState` takes a `variant` and ships four distinct copies with four recovery
actions. Three rules implemented literally: the search field is **never
wiped** (a typo is the likeliest cause), the **resource** is named rather than
the failure, and an empty state is **never rendered while a request is in
flight**.

### 3.6 Token migration

All four remaining consumers migrated: `AuthForm.css`, `MatchPage.css`,
`NotFoundPage.css`, `AppErrorBoundary.css`, plus 64 hex-fallback declarations
stripped from `SupervisorPanel.css`.

The 2.0→3.0 shim in `theme.css` is therefore **no longer load-bearing for the
public routes**. It is retained because `AdminPage.css` is deliberately a
separate operator tool with its own token set, and removing the shim is a
follow-up that should be done with `AdminPage` in scope rather than guessed at.

---

## 4. Route status

| Route | State |
|---|---|
| `/` | Redesigned — 4-element hero, mono ledger strip, mask-wipe choreography |
| `/scholarships` | Redesigned — 89–115px rows, rail at ≥1280, drawer below |
| `/scholarships/:id` | **Redesigned this pass** — spec strip, question-headed sections |
| `/countries` | Redesigned (survived) |
| `/compare` | Redesigned (survived) |
| `/saved` | Redesigned (survived) |
| `/match` | **Tokens + radius ladder only** — redesign lost, see §1 |
| `/login`, 404 | **Tokens + radius ladder only** — redesign lost, see §1 |
| `/admin` | Untouched by intent — operator tool, its own dark language |

---

## 5. Motion — measured at the four required timestamps

| t | Running | Infinite | Headline clip-path |
|---|---|---|---|
| 150ms | **23** | 0 | `inset(-1.33px …)` — line 1 entering, 2–3 still closed |
| 400ms | **23** | 0 | `inset(-7.44px …)` |
| 800ms | **6** | 0 | settled |
| 1800ms | **0** | 0 | — |

**Reduced motion**: 0 running, **0 stranded reveals**. The token collapse means
the whole decision rides on variables with zero per-component overrides.

The reveal invariant is inverted from the 2.0 failure: CSS renders
`[data-reveal]` as **visible**, and only `html.js-motion` — added by the
observer module itself after confirming a working IntersectionObserver — hides
anything. A missing observer can no longer strand content.

---

## 6. Responsive — measured, 24 rows live

| Width | First record | Row | **Rows visible** | Overflow |
|---|---|---|---|---|
| 1920×1080 | y=339 | 89px | **9** | 0 |
| 1440×900 | y=339 | 89px | **7** | 0 |
| 1366×768 | y=339 | 89px | **5** | 0 |
| 1280×800 | y=339 | 115px | **4** | 0 |
| 1024×768 | y=383 | 115px | **4** | 0 |
| 768×1024 | y=373 | 115px | **6** | 0 |
| 412×915 | y=357 | 107px | **6** | 0 |
| 390×844 | y=418 | 107px | **4** | 0 |

**9 routes × light/dark**: 0 horizontal overflow · 0 rendered text below
10.5px · 0 error boundaries · 0 console errors introduced.

---

## 7. Build

lint **0 problems** · build **OK** · CSS 163.5 kB / 27.8 kB gzip · JS 461.1
kB / 129.1 kB gzip · **no new dependency** · `motion@13.1.1` remains installed
and unused.

---

## 8. Unresolved

1. **`/match`, `/login`, 404** lack their route redesign — lost to my own
   scripting error (§1). The highest-value remaining work.
2. **1280 shows 4 rows, not 7.** The results column there is 855px, below the
   900px the five-track row needs. Fixing it means dropping the rail below
   1280 (more drawer taps) or shrinking the fact track until values ellipsise.
   I did not guess.
3. **1920 shows 9, not 12.** Twelve needs a ~60px row, which means cutting the
   provenance line — forbidden by the trust rule. Nine is the honest number.
4. **The 2.0→3.0 shim remains** for the admin console's sake (§3.6).
5. **No independent 10-reviewer panel was run.** The brief asked for one; I ran
   the research agents instead and did not have the context budget for a fresh
   scoring panel. Claiming a review score I did not collect would be worse than
   omitting it.
6. **Nothing is deployed.** The live frontends still serve the 1.0 build.

## 9. Unrelated known issues

Untouched, as agreed: `?degree=` · `?funding=` · `DIRECTORY_LIMIT=100`.
