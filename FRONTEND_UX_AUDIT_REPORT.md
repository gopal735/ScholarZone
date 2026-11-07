# ScholarZone — Frontend & Product UX Audit Report

**Date:** 2026-11-07  
**Branch:** feature/global-catalogue-expansion-2026-11-07  
**Scope:** Complete feature inventory, navigation parity, UX quality, accessibility, responsive behavior, route verification

---

## 1. COMPLETE FEATURE INVENTORY

### 1.1 Routes & Pages (from `App.jsx`)

| Route | Page Component | Auth Required | Lazy Loaded | Works? | Notes |
|-------|----------------|---------------|-------------|--------|-------|
| `/` | HomePage | No | No | ✅ | Hero + natural language goal + lifecycle-grouped catalogue |
| `/scholarships` | ScholarshipsPage | No | Yes | ✅ | Full filter/search/sort + pagination + lifecycle tabs |
| `/scholarships/:id` | ScholarshipDetailsPage | No | Yes | ✅ | Rich detail with verification, funding, eligibility, sources |
| `/match` | MatchPage | No | Yes | ✅ | Quick/Deep profile → eligibility-gated results + analytics |
| `/assistant` | UnifiedAIPage | No* | Yes | ✅ | Grounded search + Mentor (auth) + Remote/Local AI modes |
| `/mentor` | → `/assistant` redirect | - | - | ✅ | Legacy alias, permanent redirect |
| `/countries` | CountryPage | No | No | ✅ | Editorial country grid with live counts |
| `/dashboard` | DashboardPage | Yes | Yes | ✅ | Personal workspace: matches, apps, deadlines, gaps |
| `/applications` | ApplicationsPage | Yes | Yes | ✅ | List + detail workspace (stage tracker, tasks, SOP) |
| `/applications/:id` | ApplicationsPage | Yes | Yes | ✅ | Deep link to workspace for one application |
| `/saved` | SavedScholarshipsPage | No | Yes | ✅ | LocalStorage-based shortlist |
| `/compare` | ComparePage | No | Yes | ✅ | Side-by-side table (max 4) with funding breakdown |
| `/login` | LoginPage | No | Yes | ✅ | AuthForm (login mode) |
| `/register` | RegisterPage | No | Yes | ✅ | AuthForm (register mode) |
| `*` | NotFoundPage | No | Yes | ✅ | 404 page |

> *UnifiedAIPage: Mentor features require auth; grounded search works without.

### 1.2 Navigation Items (from `Navigation.jsx`)

| Label | Route | Badge | Count | Auth-Aware | Desktop | Mobile |
|-------|-------|-------|-------|------------|---------|--------|
| Scholarships | `/scholarships` | — | — | No | ✅ | ✅ |
| Smart Match | `/match` | ✨ | — | No | ✅ | ✅ |
| Countries | `/countries` | — | — | No | ✅ | ✅ |
| Applications | `/applications` | — | — | No | ✅ | ✅ |
| AI Guide | `/assistant` | 🤖 | — | No | ✅ | ✅ |
| Compare | `/compare` | — | compareIds.length | No | ✅ | ✅ |
| Saved | `/saved` | — | savedIds.length | No | ✅ | ✅ |
| **Sign in** | `/login` | — | — | **Signed-out only** | ✅ | ✅ |
| **Dashboard** | `/dashboard` | — | — | **Signed-in only** | ✅ | ✅ |
| Theme Toggle | — | — | — | No | ✅ | ✅ (in drawer) |

### 1.3 Feature Aliases / Duplicates / Broken

| Feature | Status | Details |
|---------|--------|---------|
| `/mentor` | **Alias** | Permanent redirect to `/assistant` (line 52 App.jsx) |
| Smart Match vs Match | **Alias** | Nav says "Smart Match", route is `/match` |
| AI Guide vs Unified AI | **Alias** | Nav says "AI Guide", route is `/assistant`, page title "ScholarZone AI Assistant" |
| Plan | **Missing from nav** | Home has "My plan" drawer but no `/plan` route |
| Statement | **Missing** | Referenced in Home glossary/quiz but no dedicated page |
| BD Journey | **Missing** | Not found in routes or nav |
| Dark Mode | **Present** | ThemeToggle in nav (desktop) + in mobile drawer |

---

## 2. PAGES & COMPONENTS AUDIT

### 2.1 Core Pages

| Page | File | Lines | Key Features | State Handling |
|------|------|-------|--------------|----------------|
| **HomePage** | `HomePage.jsx` | ~1400+ | Hero, natural language goal parser, filter chips, lifecycle sections, plan drawer, learn sections (funding matrix, glossary, statement guide, quiz, prep checklist) | Loading (staticMode notice), empty, error toast |
| **ScholarshipsPage** | `ScholarshipsPage.jsx` | 136 | SEO meta, trust banner, ScholarshipList | Loading, fallback (snapshot), staticMode notice |
| **ScholarshipDetailsPage** | `ScholarshipDetailsPage.jsx` | 1065 | Hero image, badges, quick facts, funding breakdown (track-level), benefits/coverage, eligibility, academic scope, requirements, documents, English req, application method, selection notes, official sources, verification record, related scholarships | Loading skeleton, missing (404), error with retry, fallback (local) |
| **DashboardPage** | `DashboardPage.jsx` | 315 | OpportunitySummary, NextActions, ProfileSnapshot, MatchList, ApplicationProgress, DeadlineWatch, SavedScholarships, ProfileGaps | Checking/Loading/Ready/Error/Unauthenticated |
| **ApplicationsPage** | `ApplicationsPage.jsx` | 233 | List + Workspace (stage tracker, task checklist, SOP, referee, deadline) | Loading/Ready/Error/Unauthenticated |
| **SavedScholarshipsPage** | `SavedScholarshipsPage.jsx` | 47 | LocalStorage shortlist + ScholarshipList | Loading, empty, populated |
| **ComparePage** | `ComparePage.jsx` | 264 | Side-by-side table (max 4), funding coverage breakdown, official links | Loading, empty with suggestions, populated |
| **MatchPage** | `MatchPage.jsx` | 290 | ProfileTextParser, MatchProfileForm (Quick/Deep), MatchResults, ProfileStrengthPanel, CountAnalytics, HowThisIsCalculated | Calculating/Success/Empty/Error |
| **UnifiedAIPage** | `UnifiedAIPage.jsx` | 514 | Welcome screen, chat, settings panel (Local AI, Remote AI, Grounded, Mentor), disclaimer, footer links | Loading, error with retry/fallback |
| **CountryPage** | `CountryPage.jsx` | 259 | Editorial grid (tiered cards), live counts via bounded concurrency, SEO + structured data | Loading (skeletons), populated |
| **LoginPage** | `LoginPage.jsx` | 5 | AuthForm (login) | — |
| **RegisterPage** | `RegisterPage.jsx` | 5 | AuthForm (register) | — |
| **NotFoundPage** | `NotFoundPage.jsx` | ~30 | 404 message + link home | — |

### 2.2 Key Components

| Component | File | Purpose | Notable Features |
|-----------|------|---------|------------------|
| **Navigation** | `Navigation.jsx` | Primary nav + mobile drawer | Auth-aware, badges, counts, theme toggle, ARIA |
| **Layout** | `Layout.jsx` | App shell + scroll progress | Suspense boundary, premium pointer, SVG symbol library |
| **ScholarshipCard** | `ScholarshipCard.jsx` | 677 lines | Expandable, official logo/monogram, lifecycle badge, deadline countdown, academic scope preview, funding fit meter, supervisor CTA, actions, view details |
| **ScholarshipList** | `ScholarshipList.jsx` | 671 lines | Search, filters (country, degree, funding, deadline month, status, lifecycle tabs), quick pills, sort, pagination, snapshot/fallback notices |
| **PremiumScholarshipCard** | `PremiumScholarshipCard.jsx` | 28942 bytes | Multi-level expand (L2 Quick Decision, L3 Planning, L4 Evidence) |
| **LifecycleBadge** | `LifecycleBadge.jsx` | Status pill | Opening/Upcoming/Open/Closing Soon/Closed/Unknown |
| **ScholarshipImage** | `ScholarshipImage.jsx` | Responsive image with fallback | — |
| **DashboardSections** | `DashboardSections.jsx` | 20848 bytes | NextActions, ProfileGaps, SavedScholarships |
| **Match Components** | `match/*.jsx` | 9 components | CountAnalytics, HowThisIsCalculated, MatchCard, MatchCompare, MatchFilters, MatchProfileForm, MatchReadiness, MatchResults, MatchResultSummary, ProfileStrengthPanel, ProfileTextParser |
| **Mentor Components** | `mentor/*.jsx` | 2 components | MentorAnswer, MentorComposer |
| **UI Primitives** | `ui/*.jsx` | 5 components | AmbientOrbs, GlassBadge, GlassButton, GlassSkeleton, GlassSurface |
| **AuthForm** | `AuthForm.jsx` | Login/Register | — |
| **ApplicationWorkspace** | `ApplicationWorkspace.jsx` | 21419 bytes | Stage tracker, tasks, SOP, referees, deadlines |

---

## 3. NAVIGATION & DISCOVERABILITY

### 3.1 Desktop Navigation (Navigation.jsx + Navigation.css)

**Structure:**
- Logo (Home link) — left
- Primary nav links (7 items) — center
- Controls: Theme toggle + Auth button (Sign in / Dashboard) — right
- Mobile menu toggle (hidden ≥960px)

**Issues Found:**
1. **No "More" dropdown** — All 7 primary links show inline. At ≤1040px they shrink; at ≤960px desktop nav hides entirely. No overflow menu for intermediate widths.
2. **Home accessibility** — Only via logo (no "Home" label in nav). Acceptable but not explicit.
3. **Auth-aware button** — Correctly shows "Sign in" (signed-out) or "Dashboard" (signed-in).
4. **Theme control** — Distinct, accessible (ARIA label, keyboard focusable).
5. **NEW badges** — "✨" on Smart Match, "🤖" on AI Guide. No "NEW" text badge.
6. **Duplicate links** — None in primary nav. However:
   - "Applications" in nav → `/applications` (auth not required but page shows signed-out state)
   - "Dashboard" only appears when authenticated
   - "Saved" and "Compare" show counts but work without auth (localStorage)

### 3.2 Mobile Navigation (Drawer)

**Structure:**
- Header: Logo + Close button
- Quick Auth: Dashboard card (signed-in) OR Sign in / Create Account buttons (signed-out)
- Links: All 7 nav items with descriptions + badges + counts
- Footer: Tagline

**Issues Found:**
1. **All features discoverable** — Yes, all 7 nav items + auth actions present.
2. **Home accessible** — Only via logo in drawer header (links to `/`).
3. **Theme control** — **MISSING** from mobile drawer. Only in desktop header.
4. **Active state** — Shows `is-active` class on current route.
5. **Escape key** — Closes drawer.
6. **Backdrop click** — Closes drawer.
7. **Body scroll lock** — Applied when open.

### 3.3 Navigation Parity Summary

| Feature | Desktop | Mobile | Gap |
|---------|---------|--------|-----|
| All 7 primary links | ✅ | ✅ | — |
| Auth-aware button | ✅ | ✅ | — |
| Theme toggle | ✅ | ❌ | **Missing in mobile drawer** |
| Home via logo | ✅ | ✅ | — |
| Badges (✨, 🤖) | ✅ | ✅ | — |
| Counts (Saved, Compare) | ✅ | ✅ | — |
| Active route highlight | ✅ | ✅ | — |
| Keyboard accessible | ✅ | ✅ | — |
| ARIA labels | ✅ | ✅ | — |

---

## 4. UX QUALITY AUDIT

### 4.1 Scholarship Card Accuracy (ScholarshipCard.jsx)

| Field | Source | Evidence-Backed? | Notes |
|-------|--------|------------------|-------|
| Title | `scholarship.title` | ✅ | Direct from record |
| Provider | `scholarship.provider` | ✅ | Shown in card header |
| Country | `scholarship.country` | ✅ | With flag emoji |
| Degree | `scholarship.degree` | ✅ | e.g., "Master's, PhD" |
| Funding Indicator | `scholarship.funding` | ⚠️ | Tag shows "Fully Funded"/"Partial"/"Stipend" — **no evidence link on card** |
| Lifecycle State | `classifyLifecycle(scholarship)` | ✅ | Opening/Upcoming/Open/Closing Soon/Closed + countdown |
| Deadline | `getDeadlineLabel()` + countdown | ✅ | Shows "X days left" or "Opens in X days" |
| Source/Verification | `verification_status` + `last_verified_at` | ✅ | "Verified official source" / "Confirm with provider" + date |
| Official Logo | `getConfirmedOfficialLogo()` | ✅ | Shows logo or monogram; provenance rule (hollow/filled) |
| Academic Scope | departments/fields/programmes | ✅ | Preview in collapsed card (max 2 each) |
| Fit Meter | Custom 4-criteria | ⚠️ | **Heuristic** (fully funded, exact deadline, bachelor, verified) — not personalized |

**Severity: MEDIUM** — Funding tag lacks "verified" provenance link on card (only in expanded section).

### 4.2 Scholarship Detail Page Completeness (ScholarshipDetailsPage.jsx)

| Section | Present? | Evidence/Provenance | Unknown Markers |
|---------|----------|---------------------|-----------------|
| Hero (image, title, country, degree, provider) | ✅ | Image sourceType shown | — |
| Status badges (deadline, verification, verificationState) | ✅ | `verification_status === 'active'` | "Confirm with provider" for unverified |
| Quick Facts (KeyValueGrid) | ✅ | Auto-wide for long values | — |
| Funding & Coverage (top-level + track-level) | ✅ | `funding_details` array with per-track provenance | "Not confirmed" for missing |
| Benefits & Coverage | ✅ | From `benefits`/`coverage` arrays | — |
| About / Description | ✅ | `description` field | — |
| Eligibility (summary + list) | ✅ | `eligibility_summary` + `eligibility` | — |
| Academic Eligibility (departments, fields, programmes) | ✅ | **Provenance flags** (`inferred` → muted note) | "Confirm with awarding body" |
| Requirements & Documents | ✅ | `requirements` + `documents`/`required_documents` | — |
| English Requirement | ✅ | `english_requirement` | — |
| Application Method (ordered list) | ✅ | `application_method` | — |
| Selection Notes / General Notes | ✅ | `selection_notes` + `notes` | — |
| Official Sources (links with host) | ✅ | `official_source_url`, `catalogue_url`, `official_updates_url`, `application_link` | Host shown, external link icon |
| Verification Record | ✅ | `buildVerificationRecord()` → entries + image provenance | — |
| Related Scholarships | ✅ | By country/degree match | — |
| Final CTA (apply or confirm) | ✅ | Context-aware | — |

**Strength:** Exceptional provenance handling — "inferred" fields explicitly marked, hollow provenance rule for missing logos, verification status from `verification_status` not legacy `verified` boolean.

**Severity: LOW** — Only minor: funding "Not confirmed" could be more prominent.

### 4.3 Design System Consistency

**Tokens (theme.css):** Comprehensive — colors, typography scale (4 tiers), spacing (4px base), radius, motion, glass system (4 levels), depth, shadows, focus rings.

**Visual Direction:** Editorial — off-white (#FBFAF6) / navy (#14130F) / steel blue accent (#1B3A5C) / restrained gold (#C4A44A). Dark mode: near-black (#08090B) / charcoal surfaces / steel blue (#5E93D6).

**Consistency Issues:**

| Issue | Location | Severity |
|-------|----------|----------|
| **Two nav implementations** | `Navigation.jsx` (new) vs `site-header` styles in `App.css` (legacy) | MEDIUM |
| **Inconsistent button classes** | `.btn` (Navigation.css) vs `.sz-btn` (theme.css) vs `.sz-glass-button` | MEDIUM |
| **Card variants** | `ScholarshipCard` (p-card, p-rise) vs `PremiumScholarshipCard` (own system) | LOW |
| **Form styles** | Inline in MatchPage.css vs theme.css `.sz-input` | LOW |
| **Focus rings** | `--focus-ring` token defined but Navigation uses custom focus | LOW |

### 4.4 Responsive Behavior

| Breakpoint | Home | Scholarships | Details | Dashboard | Match | AI Assistant | Countries |
|------------|------|--------------|---------|-----------|-------|--------------|-----------|
| **Phone (≤640px)** | Stack hero, panel full-width, grid 1-col | Filters stack, pills wrap, table → cards | Hero stacks, facts 1-col, sections stack | Sections stack, cards 1-col | Form stacks, results cards | Chat full-width, welcome stacks | Grid 1-col (tier cards) |
| **Tablet (640-960px)** | Hero 2-col, grid 2-col | Filters 2-3 col, grid 2-col | Hero 2-col, facts 2-col | 2-col sections | Form 2-col, results 2-col | 2-col layout | Grid 2-3 col |
| **Laptop (960-1280px)** | Hero 2-col, grid 3-col | Full filters, grid 3-col | Full layout, 2-col blocks | Full dashboard | Full form + sidebar | Full layout | Grid 3-4 col |
| **Wide (≥1280px)** | Max 1680px container | Max 1180px (list) | Max 1120px (details) | Max 1180px | Max 1180px | Max container | Grid 4-6 col |

**Issues:**
1. **ScholarshipsPage** uses `max-width: 1180px` while Home uses `1680px` — inconsistent content width.
2. **Navigation** hides desktop nav at 960px — no intermediate "More" dropdown.
3. **CountryPage** tier system (tier1/tier2/tier3) creates visual hierarchy but tier3 cards are very small on mobile.

### 4.5 Loading / Error / Empty / Offline States

| Page | Loading | Error | Empty | Offline/Fallback |
|------|---------|-------|-------|------------------|
| Home | ❌ (no skeleton, uses staticMode notice) | Toast only | "Nothing fits" message | ✅ StaticMode banner |
| Scholarships | ✅ Skeleton cards | ❌ (relies on List fallback) | ✅ "No matching" + reset | ✅ Snapshot notice + Retry |
| Details | ✅ Skeleton (hero + lines) | ✅ "Try again" button | ✅ 404 page message | ✅ Local fallback + notice |
| Dashboard | ✅ Skeleton bars | ✅ "Try again" | ✅ Signed-out CTA | — |
| Applications | ✅ Skeleton | ✅ "Try again" | ✅ Empty + preview features | — |
| Saved | ✅ "Loading..." | ❌ | ✅ Empty + CTA | — |
| Compare | ✅ "Loading..." | ❌ | ✅ Empty + suggestions | — |
| Match | ✅ Stepper bar | ✅ "Try again" | ✅ Empty results + alternatives | — |
| AI Assistant | ✅ Dots + context text | ✅ Retry / fallback to grounded | ✅ Welcome screen | — |
| Countries | ✅ Skeleton cards | ❌ | — (always has data) | — |

**Gap:** Several pages lack explicit error boundaries (only Dashboard, Applications, Match have structured error states). Home relies on toast; Scholarships/List relies on fallback notice.

---

## 5. ACCESSIBILITY AUDIT

### 5.1 Semantic HTML & Structure

| Check | Status | Evidence |
|-------|--------|----------|
| Heading hierarchy (h1→h2→h3) | ✅ | Home: h1 in hero, h2 in sections; Details: h1 hero, h2 blocks; Match: h1 page, h2 sections |
| Landmarks (header, main, nav, aside, footer) | ✅ | Layout: header (Navigation), main, footer; Mobile drawer: aside |
| Lists (ul/ol) | ✅ | ScholarshipList grid uses article; Compare uses table; Details uses dl/ul/ol |
| Button vs Link semantics | ✅ | NavLink for navigation, button for actions (theme toggle, save, expand) |

### 5.2 Keyboard Navigation

| Feature | Status | Notes |
|---------|--------|-------|
| Focus visible | ✅ | `--focus-ring` token; `.sz-btn:focus-visible`, `.sz-glass:focus-visible`, Navigation buttons |
| Skip links | ❌ | **Missing** — no "Skip to main content" link |
| Tab order logical | ✅ | Natural DOM order |
| Escape to close | ✅ | Mobile drawer, detail sheets (Home), modals |
| Arrow keys in menus | ❌ | Mobile drawer links not arrow-navigable |
| Focus trap in drawers/sheets | ✅ | Home detail sheet traps focus; mobile drawer uses `inert` |

### 5.3 ARIA & Screen Reader

| Feature | Status | Evidence |
|---------|--------|----------|
| ARIA labels on icon buttons | ✅ | Theme toggle, mobile toggle, save button, expand button |
| ARIA live regions | ✅ | `aria-live="polite"` on results counts (Home, Scholarships, Match), dashboard notice |
| ARIA expanded/controls | ✅ | ScholarshipCard expand button, mobile drawer, plan drawer |
| ARIA hidden decorative | ✅ | SVG icons `aria-hidden="true"`, atmosphere elements |
| Role=status on loading | ✅ | LoadingState components, skeleton `aria-busy="true"` |
| Role=dialog on modals | ⚠️ | Settings panel in AI Assistant has `role="dialog"` but no `aria-modal` |

### 5.4 Contrast & Color

| Check | Status | Notes |
|-------|--------|-------|
| Text contrast (4.5:1) | ✅ | Tokens define `--sz-success-text`, `--sz-accent-text`, `--sz-warning-text` for on-tint text |
| Focus indicator contrast | ✅ | `--focus-ring: rgba(27,58,92,0.5)` on light; `rgba(94,147,214,0.5)` on dark |
| Color-only info | ⚠️ | Lifecycle badges use color + text; funding tags use color + text; but **fit meter** is visual-only (bar + number) — number provides text equivalent |
| Reduced motion | ✅ | `useReducedMotion` hook; `@media (prefers-reduced-motion: reduce)` disables animations, transitions, scroll-linked motion |

### 5.5 Accessibility Defects

| Defect | Location | Severity |
|--------|----------|----------|
| **No skip link** | Global (Layout) | HIGH |
| **Mobile drawer links not arrow-navigable** | Navigation.jsx | MEDIUM |
| **Settings panel missing `aria-modal`** | UnifiedAIPage.jsx | LOW |
| **Theme toggle missing from mobile drawer** | Navigation.jsx | MEDIUM (accessibility + parity) |
| **Home detail sheet focus restore** | HomePage.jsx | ✅ Implemented correctly |
| **ScholarshipCard expand focus management** | ScholarshipCard.jsx | ❌ No focus management on expand/collapse |
| **Compare table keyboard scroll** | ComparePage.jsx | ⚠️ `tabIndex="0"` on wrapper but no scroll hint |

---

## 6. STATE HANDLING VERIFICATION

### 6.1 Route-by-Route State Matrix

| Route | Loading | Error | Empty | Auth-Gated | Fallback/Offline |
|-------|---------|-------|-------|------------|------------------|
| `/` | StaticMode notice | Toast | "Nothing fits" | No | ✅ Static catalogue |
| `/scholarships` | Skeleton | Via List fallback | "No matching" + reset | No | ✅ Snapshot + Retry |
| `/scholarships/:id` | Skeleton | "Try again" | 404 message | No | ✅ Local fallback |
| `/match` | Stepper bar | "Try again" | Empty + alternatives | No | — |
| `/assistant` | Dots + text | Retry + fallback | Welcome screen | Mentor only | — |
| `/countries` | Skeletons | — | — | No | — |
| `/dashboard` | Skeleton | "Try again" | Signed-out CTA | **Yes** | — |
| `/applications` | Skeleton | "Try again" | Empty + preview | **Yes** | — |
| `/applications/:id` | (Workspace) | — | — | **Yes** | — |
| `/saved` | "Loading..." | — | Empty + CTA | No (localStorage) | — |
| `/compare` | "Loading..." | — | Empty + suggestions | No (localStorage) | — |
| `/login` | — | AuthForm handles | — | No | — |
| `/register` | — | AuthForm handles | — | No | — |

### 6.2 Search/Filter/Detail Navigation

| Flow | Works? | Notes |
|------|--------|-------|
| Home: type goal → filter chips → cards update | ✅ | Real-time, debounced |
| Home: manual filters (level, funding, country) → cards update | ✅ | Override parsed criteria |
| Home: click "Details" → sheet opens | ✅ | Focus trap, Escape close, restore focus |
| Home: click "View details" → `/scholarships/:id` | ✅ | Link navigation |
| Scholarships: search/filter/sort → results update | ✅ | Debounced, pagination resets |
| Scholarships: lifecycle tabs → filter by status | ✅ | Client + server (snapshot) |
| Scholarships: click card → `/scholarships/:id` | ✅ | |
| Details: "Related" links → other details | ✅ | |
| Dashboard: "View all matches" → `/match` | ✅ | |
| Dashboard: "View application" → `/applications/:id` | ✅ | |
| Applications: list → click → `/applications/:id` | ✅ | URL-addressable workspace |
| Saved: click card → details | ✅ | |
| Compare: add/remove → table updates | ✅ | Max 4, localStorage |
| Match: submit profile → results | ✅ | Eligibility gate + scoring |
| Match: filter results → counts update | ✅ | `useCountIntelligence` shared state |
| AI Assistant: ask → response with sources | ✅ | Grounded + fallback chain |

### 6.3 Broken Routes / Dead Ends

| Route | Issue | Severity |
|-------|-------|----------|
| `/plan` | Referenced in Home ("My plan") but no route exists | MEDIUM |
| `/statement` | Referenced in Home glossary/quiz but no route | LOW |
| `/bd-journey` | Not found anywhere | LOW |
| `/mentor` | Redirects to `/assistant` — works but legacy | LOW (intentional) |

---

## 7. SEVERITY-CLASSIFIED DEFECT LIST

### CRITICAL (0)
None found.

### HIGH (2)
1. **No skip-to-main-content link** — Global accessibility failure (WCAG 2.4.1)
2. **Theme toggle missing from mobile drawer** — Parity + accessibility; users on mobile cannot switch theme

### MEDIUM (8)
1. **No "More" dropdown in desktop nav** — At 960-1040px, nav items shrink but don't collapse; at ≤960px they disappear entirely with no alternative access except mobile drawer
2. **Two navigation implementations** — `Navigation.jsx` (new) vs legacy `site-header` styles in `App.css` — maintenance burden, potential conflicts
3. **Inconsistent button systems** — `.btn` (Navigation), `.sz-btn` (theme), `.sz-glass-button` (theme), `.p-btn` (HomePage) — 4+ button variants
4. **ScholarshipCard expand lacks focus management** — Keyboard users lose context when expanding/collapsing
5. **Several pages lack structured error states** — Home (toast only), Scholarships/List (fallback notice only), Saved, Compare
6. **Content width inconsistency** — Home: 1680px, Scholarships: 1180px, Details: 1120px
7. **Mobile drawer links not arrow-key navigable** — Only Tab navigation
8. **`/plan` route referenced but missing** — Home shows "My plan" drawer with no persistent URL

### LOW (6)
1. **Funding tag on card lacks provenance link** — Only in expanded section
2. **Settings panel missing `aria-modal`** — Minor ARIA gap
3. **Compare table keyboard scroll lacks hint** — `tabIndex="0"` but no visible indicator
4. **Legacy `site-header` styles in App.css unused** — Dead code
5. **Tier3 country cards very small on mobile** — UX compromise
6. **`/mentor` redirect** — Works but adds redirect hop

---

## 8. RESPONSIVE BEHAVIOR SUMMARY

| Viewport | Navigation | Home Hero | Scholarship Grid | Detail Page | Dashboard | Match Form | AI Chat |
|----------|------------|-----------|------------------|-------------|-----------|------------|---------|
| **320px** | Drawer only | Stacked, panel full | 1-col | Stacked, 1-col facts | Stacked sections | Stacked fields | Full-width |
| **480px** | Drawer only | Stacked | 1-col | Stacked | Stacked | Stacked | Full-width |
| **768px** | Drawer only | 2-col | 2-col | 2-col facts | 2-col sections | 2-col fields | 2-col |
| **960px** | **Nav hides** | 2-col | 3-col | Full | Full | Full | Full |
| **1024px** | Drawer only | 2-col | 3-col | Full | Full | Full | Full |
| **1280px** | Full nav | 2-col | 3-4 col | Full | Full | Full | Full |
| **1680px** | Full nav | 2-col | 4-col | Full (max 1120) | Full (max 1180) | Full (max 1180) | Full |

**Key Breakpoint Issues:**
- **960px cliff**: Desktop nav disappears completely; mobile drawer is only access
- **No intermediate "More" menu** for 960-1040px where items are cramped
- **Container max-widths differ** across pages (1680/1180/1120)

---

## 9. ROUTE-BY-ROUTE VERIFICATION

| Route | Loads | Auth Check | Content Renders | Navigation Works | No Console Errors |
|-------|-------|------------|-----------------|------------------|-------------------|
| `/` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/scholarships` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/scholarships?country=Germany` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/scholarships/1002` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/scholarships/999999` | ✅ | N/A | 404 state | ✅ | ✅ |
| `/match` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/assistant` | ✅ | N/A (Mentor gated) | ✅ | ✅ | ✅ |
| `/mentor` | ✅ | N/A | Redirect | ✅ | ✅ |
| `/countries` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/dashboard` | ✅ | **Server-session** | ✅/Unauth | ✅ | ✅ |
| `/applications` | ✅ | **Server-session** | ✅/Unauth | ✅ | ✅ |
| `/applications/123` | ✅ | **Server-session** | ✅/Unauth | ✅ | ✅ |
| `/saved` | ✅ | N/A (localStorage) | ✅ | ✅ | ✅ |
| `/compare` | ✅ | N/A (localStorage) | ✅ | ✅ | ✅ |
| `/login` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/register` | ✅ | N/A | ✅ | ✅ | ✅ |
| `/plan` | ❌ | — | 404 | — | — |
| `/statement` | ❌ | — | 404 | — | — |

---

## 10. RECOMMENDATIONS PRIORITY ORDER

### Immediate (Before Release)
1. Add skip-to-main-content link in `Layout.jsx`
2. Add theme toggle to mobile drawer in `Navigation.jsx`
3. Implement "More" dropdown for desktop nav at 960-1040px
4. Consolidate button systems (pick one: `.sz-btn` + `.sz-glass-button`)
5. Add focus management to `ScholarshipCard` expand/collapse
6. Create `/plan` route or remove "My plan" references from Home

### Short Term (Next Sprint)
1. Remove legacy `site-header` styles from `App.css`
2. Standardize container max-widths (recommend 1120px for content, 1680px for full-bleed hero)
3. Add structured error states to Home, Scholarships/List, Saved, Compare
4. Make mobile drawer links arrow-key navigable
5. Add `aria-modal` to AI Assistant settings panel
6. Add visible scroll hint to Compare table wrapper

### Medium Term
1. Unify card variants (ScholarshipCard vs PremiumScholarshipCard)
2. Add keyboard shortcut legend (?) for power users
3. Consider adding "Home" label next to logo in nav for clarity
4. Audit all focus-visible styles for consistency
5. Add offline detection banner (service worker + navigator.onLine)

---

## 11. STRENGTHS SUMMARY

1. **Exceptional provenance/verification system** — Hollow/fill provenance rule, inferred field markers, verification_status authoritative source
2. **Comprehensive detail page** — Funding breakdown (track-level), academic scope with provenance, official sources with host, verification record
3. **Robust state machines** — Explicit load states (CHECKING/LOADING/READY/ERROR/UNAUTHENTICATED) on Dashboard, Applications, Match
4. **Static-first architecture** — Snapshot fallback works seamlessly; `fromSnapshot`/`staticMode` flags propagate to UI
5. **Accessibility foundations strong** — ARIA live regions, focus management in sheets/drawers, reduced motion, semantic HTML
6. **Editorial visual design** — Cohesive token system, dark mode parity, liquid atmosphere, glass system
7. **Smart Match architecture** — Eligibility gate → scoring → analytics → explanation transparency
8. **AI Assistant multi-mode** — Grounded (deterministic) + Mentor (personalized) + Remote/Local AI with fallback chain
9. **URL-addressable workspaces** — `/applications/:id` deep links work on refresh/share
10. **Performance considerations** — Request deduplication, bounded concurrency (CountryPage), lazy routes, Suspense boundaries

---

*End of Audit Report*