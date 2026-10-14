# FINAL_SCOPE_ATTRIBUTION

Scope attribution of all current frontend changes for PR decisions.
Working directory: `C:\Users\GopaL\Desktop\Projects folder\ScholarZone`
Current HEAD: `bac50bf55816bfdea02df1b78c219f7df7be1771`

---

## GIT INVENTORY

### Modified tracked files (26)

| File | Status | Session | Reason |
|---|---|---|---|
| frontend/index.html | M | CURRENT | Google Fonts URL switched to Newsreader + Inter variable |
| frontend/package.json | M | CURRENT | `motion` removed; no new dependency added |
| frontend/src/App.css | M | CURRENT | Atmosphere gradient token-ised; `z-index: 20` → `--z-header` |
| frontend/src/components/AppErrorBoundary.jsx | M | CURRENT | Inline light-mode styles replaced with class + token-driven; Reload/Home actions |
| frontend/src/components/Layout.jsx | M | CURRENT | `ResizeObserver` publishes real header height to `--header-h` |
| frontend/src/components/Navigation.css | M | CURRENT | iOS lozenge → warm token-driven mark; mobile tab-bar/drawer CSS |
| frontend/src/components/Navigation.jsx | M | CURRENT | Native `<dialog>` drawer + bottom tab-bar; `motion` import removed; `useCallback` close; `aria-expanded` |
| frontend/src/components/ScholarshipCard.css | M | PRE_EXISTING | Last modified 10/6 7:20:15 PM. Rich card UI levels 2-4. No edits in this session. |
| frontend/src/components/ScholarshipCard.jsx | M | PRE_EXISTING | Last modified 10/6 7:21:58 PM. No edits in this session. |
| frontend/src/components/ScholarshipList.css | M | MIXED | Filter-sheet scrim, toggle, is-open class, 48px floor: CURRENT. Pre-existing PremiumScholarshipCard styles preserved. |
| frontend/src/components/ScholarshipList.jsx | M | MIXED | `useCallback` import, `activeFilterCount`, `filtersOpen`, scrim, toggle: CURRENT. Pre-existing `usePremiumCard` toggle, premium card import, loading effect: PRE_EXISTING. |
| frontend/src/components/SupervisorPanel.css | M | CURRENT | Instrument Serif stack → `var(--font-display)` |
| frontend/src/components/dashboard/DeadlineWatch.jsx | M | CURRENT | `div` wrapper → `.sz-table-scroll` + `role="region"` + aria-labelledby |
| frontend/src/components/match/MatchCompare.jsx | M | CURRENT | Same `.sz-table-scroll` treatment |
| frontend/src/index.css | M | CURRENT | `* { font-weight: calc(var(--weight,400) * var(--weight-multiplier,1)) }`; optical-size reset on display tiers; `tabular-nums lining-nums` on figures; `light-dark` scheme |
| frontend/src/main.jsx | M | CURRENT | `tokens.css` imported last so it wins every cascade tie |
| frontend/src/pages/AdminPage.css | M | CURRENT | purple removed; iOS reds/greens/oranges → semantic tokens; `10px/11px` font floor lifted to `12px`; steel-blue mesh → `--accent-soft`; cream-glass bg → `--sz-glass-tint-3` |
| frontend/src/pages/AdminPage.jsx | M | CURRENT | `StatOrb`/`MetricCard` hardcoded iOS palettes (`#0a84ff/#ff9f0a/#30d158`) replaced with `var(--info/--warning/--success)` |
| frontend/src/pages/ComparePage.css | M | CURRENT | `min-width: 680px` removed; sticky first column added; selected-chip list CSS; touch floor 48px |
| frontend/src/pages/ComparePage.jsx | M | CURRENT | `.sz-table-scroll` wrapper + region role + reachable Selected list with Remove buttons |
| frontend/src/pages/CountryPage.css | M | CURRENT | Cormorant Garamond stack → `var(--font-display)` |
| frontend/src/pages/HomePage.css | M | CURRENT | `.sz-reveal` gated behind `html.js-reveal`; motion token aliases aligned |
| frontend/src/pages/ScholarshipDetailsPage.jsx | M | PRE_EXISTING | Last modified 10/6 7:25:41 PM. Adds `PremiumScholarshipCard` import + `<Reveal className="sz-detail__premium">`. No edits this session. |
| frontend/src/styles/adminVerification.css | M | CURRENT | `--avc-*` tokens re-declared from canonical tokens; Georgia stack → `--font-body`; min target 44 → `--touch-min`; radius `6px` → `--radius-sm` |
| frontend/src/styles/glass.css | M | CURRENT | `--glass-tint/--glass-specular/--glass-radius-*/--status-*/--admin-bg/--mesh-*` now resolve to canonical tokens and semantic colours; `--spring/--smooth/--ease-out` now canonical easings |
| frontend/src/styles/responsive.css | M | CURRENT | `--sz-touch-min` 44→48px; gutter centralised to `--gutter` token; sticky header offset via `--header-h` |
| frontend/src/theme.css | M | CURRENT | Old two `:root` blocks (479 lines) replaced; primitives ported onto canonical tokens, focus ring standard, 48px touch; `sz-toast/--z-*` layered stack; `sz-table-scroll/sz-table` primitives added; `sz-hero__error`/`sz-hero__fallback-notice`/`match-counts__*`/loading spinner/skeleton styles added |

### Deleted tracked files (5)

| File | Status | Session |
|---|---|---|
| frontend/src/components/ui/AmbientOrbs.jsx | D | CURRENT |
| frontend/src/components/ui/GlassBadge.jsx | D | CURRENT |
| frontend/src/components/ui/GlassButton.jsx | D | CURRENT |
| frontend/src/components/ui/GlassSkeleton.jsx | D | CURRENT |
| frontend/src/components/ui/GlassSurface.jsx | D | CURRENT |

### New untracked files related to this pass (3)

| File | Status | Size | Notes |
|---|---|---|---|
| frontend/src/styles/tokens.css | untracked | 735 lines | Canonical token source of truth. Imported last in main.jsx. |
| frontend/src/components/AppErrorBoundary.css | untracked | 87 lines | Token-driven crash screen styles. Imported by AppErrorBoundary.jsx. |
| frontend/src/hooks/useScrollRegion.js | untracked | 40 lines | Measures overflow + focusable + data-overflowing; used by DeadlineWatch / MatchCompare / ComparePage. |

### Unrelated untracked files (NOT a result of this session)

- frontend/src/components/PremiumScholarshipCard.css / .jsx — `git status` lists them but their timestamps (pre-9:45 PM) indicate they predate this session
- frontend/src/components/card/ — same provenance
- frontend/src/hooks/useCountUp.js, useReveal.js, services/premiumCardResearch.js, utils/cardPresentation.js — same provenance
- frontend/public/research/ — same provenance
- frontend/src/components/ui/index.jsx, frontend/src/components/ui/primitives.css, frontend/src/styles/motion.css — were never tracked; deletion removed untracked files from disk, no tracked-file impact

---

## DELETED UI/ FILE ANALYSIS

### frontend/src/components/ui/AmbientOrbs.jsx
- Path: `frontend/src/components/ui/AmbientOrbs.jsx`
- Imported anywhere: NO (grep shows no `from '../components/ui/AmbientOrbs'` or `<AmbientOrbs`)
- Reachable from app: NO
- Deletion safe: YES
- Part of this visual pass: YES (tracked file, modified/deleted)

### frontend/src/components/ui/GlassBadge.jsx
- Path: `frontend/src/components/ui/GlassBadge.jsx`
- Imported anywhere: NO
- Reachable from app: NO
- Deletion safe: YES
- Part of this visual pass: YES

### frontend/src/components/ui/GlassButton.jsx
- Path: `frontend/src/components/ui/GlassButton.jsx`
- Imported anywhere: NO
- Reachable from app: NO
- Deletion safe: YES
- Part of this visual pass: YES

### frontend/src/components/ui/GlassSkeleton.jsx
- Path: `frontend/src/components/ui/GlassSkeleton.jsx`
- Imported anywhere: NO
- Reachable from app: NO
- Deletion safe: YES
- Part of this visual pass: YES

### frontend/src/components/ui/GlassSurface.jsx
- Path: `frontend/src/components/ui/GlassSurface.jsx`
- Imported anywhere: NO
- Reachable from app: NO
- Deletion safe: YES
- Part of this visual pass: YES

(Also deleted from disk but never tracked: `frontend/src/components/ui/index.jsx` 434 lines, `frontend/src/components/ui/primitives.css` 903 lines, `frontend/src/styles/motion.css` 357 lines. All three were never imported. No `git diff` impact.)

---

## LOGICAL CHANGE CLASSIFICATION

### VISUAL_SYSTEM
- tokens.css (new canonical file)
- theme.css — token section rewrite, primitive ports, contract pieces
- App.css — warm gradient tokenize, z-index
- AppErrorBoundary.css (new), AppErrorBoundary.jsx
- index.css — weight-multiplier, optical-sizing, tabular-nums
- adminVerification.css — avc-* tokens collapse to canonical
- glass.css — glass recipe + status colours collapse to canonical
- Navigation.css — warm mark + drawer/tab-bar styling
- SupervisorPanel.css, CountryPage.css — font-display token swap
- HomePage.css — js-reveal gating + motion token alignment
- ComparePage.css / AdminPage.css — tokenisation, sticky columns, touch floor

### RESPONSIVE
- responsive.css — touch floor 44→48px, gutter token, sticky header offset
- Navigation.jsx / Navigation.css — drawer + 4-item tab bar
- ComparePage.css — `min-width: 680px` removed, sticky first column
- ScholarshipList.css — filter sheet (scrim, is-open, slide-up)
- theme.css — `sz-table-scroll/sz-table` primitive added
- ComparePage.jsx / DeadlineWatch.jsx / MatchCompare.jsx — region wrapper

### ACCESSIBILITY
- theme.css — focus-ring standard, `sr-only` class, `prefers-contrast` block
- Navigation.jsx — `aria-expanded`, `aria-controls`, `role="region"`, labelled drawer
- DeadlineWatch.jsx / MatchCompare.jsx / ComparePage.jsx — `role="region"` + measured `tabIndex`
- ScholarshipList.jsx — toggle `aria-expanded`, scrim `aria-label`
- All transitions already wrapped in `prefers-reduced-motion`

### BUG_FIX
- ComparePage.css `min-width: 680px` removal — Remove chip was unreachable
- `--sz-paper` duplicate definitions collapsing — one had been winning by accident
- Two `:root` blocks with `--sz-ease` conflict (Ledger.css winning silently)
- `--line` split-brain in `index.css` vs `theme.css`
- `--surface` duplicate definition
- Nav header stacking to 208px on mobile (no hamburger/drawer existed)
- `.admin-nav` painting over `.site-header` (z-index 50 vs 20)
- AdminPage.css hardcoded orange/green/red iOS palette + purple gradient
- `--glass-radius-*` 8/12/16/20/28px contradicting public 4/6/8/12/16px scale

### BEHAVIOR_CHANGE
- Filter sheet opens/closes on mobile (≤640px) — user toggles via "Filters" button + scrim/Escape
- Bottom tab bar replaces the 11 stacked utility links below ≤640px
- `motion` package removed — count-badge spring in nav-utility no longer happens; CSS trace shows zero `motion` imports remain (verified)
- Compare page: selected scholarship chips always visible on every width
- `--sz-reveal` rule is inverted: now gated behind `html.js-reveal` so content is visible by default (was: opacity 0 + failsafe)

### PRE_EXISTING (no edits this session, only noted in audit)
- ScholarshipCard.jsx, ScholarshipCard.css, ScholarshipDetailsPage.jsx

### PRE_EXISTING INSIDE MIXED hunks
- ScholarshipList.jsx / ScholarshipList.css — `PremiumScholarshipCard` import / toggle / loading / `premiumItems` state were pre-existing; my filter-sheet edits are layered on top

### UNRELATED
- All untracked files under `backend/` and at repo root (experimental / research outputs)
- Deleted untracked `ui/index.jsx`, `ui/primitives.css`, `styles/motion.css` — these were never imported and removing them does not change app behaviour

---

## BEHAVIOR CHANGES THAT ARE NOT PURELY PRESENTATIONAL

1. Filter sheet opens/closes on mobile. The list of controls is identical; only the trigger is a toggle button on small viewports.
2. Bottom tab bar appears below 640px (4 items: Home, Scholarships, Match, Countries). On desktop all 11 destinations remain in the top bar.
3. `motion` package removed. Nav-utility count badges no longer spring in; they appear instantly.
4. Compare page: the scholarship name + Remove link list is always visible at every width.
5. Scroll reveal rule is inverted: sections render visible unless `js-reveal` is on `<html>`. Before, `.sz-reveal` was `opacity: 0` with a JS failsafe; now it is visible by default.

All other changes are tokenisation, palette alignment, type scale, radius scale, touch floor, sticky table primitives, focus ring, contrast fix, and dead-code removal.

---

## RECOMMENDED PR SCOPE

**PR_SCOPE_REQUIRES_SEPARATION**

The current working tree contains two disjoint concerns:

1. **Current visual pass** — token system, dark mode re-derivation, mobile nav + filter sheet, table scroll primitives, admin palette collapse, focus ring standard, motion press-scale semantics, touch floor 48px.
2. **Pre-existing premium-card work** — `ScholarshipCard.jsx/.css`, `ScholarshipDetailsPage.jsx`, `PremiumScholarshipCard.jsx/.css`, `premiumCardResearch.js`, `cardPresentation.js`, `useCountUp.js`, `useReveal.js`, plus the `usePremiumCard` toggle inside `ScholarshipList.jsx/.css`.

These are interleaved in `ScholarshipList.jsx` (mixed hunks) and in the working tree generally. The pre-existing work is untracked and unrelated to the visual restyling pass; the visual pass is tracked and self-contained except for the ScholarshipList pair.

### To produce a clean PR:

1. Stage the current-session files (table above). Stage ScholarshipList.jsx/css selectively with `git add --patch` — keep the filter-sheet hunks, drop the premium-card import/toggle hunks (revert those two files to the mixed state with only filter-sheet edits before staging).
2. Decide separately on the premium-card work. Either ship it as its own PR, or leave it uncommitted in the working tree.
3. The 4 PRE_EXISTING tracked files (ScholarshipCard.jsx/.css, ScholarshipDetailsPage.jsx) stay as-is in the working tree and are NOT included in the visual pass PR.

### Confirmation:

- BACKEND CHANGED = NO
- DATABASE CHANGED = NO
- RESEARCH DATA CHANGED = NO

Final: **PR_SCOPE_REQUIRES_SEPARATION**