# Phase F — Design Synthesis

## Research Sources

### 1. Linear (March 2026 UI Refresh)
- **Calm, consistent interface** — headers, navigation, and view controls unified across workflows
- **Dimmed navigation** — sidebar recedes so main content stands out
- **Compact tabs** — smaller icon-only tabs with rounded corners
- **Reduced icon usage** — scaled down, removed colored team icon backgrounds
- **Structure felt not seen** — softer borders, rounded edges, reduced visual noise
- **Warmer gray palette** — less saturated, crisper feel

### 2. Stripe Dashboard
- **Information hierarchy** — surface key metrics without burying them
- **Job-based navigation** — label by what users do, not what data is called
- **Color discipline** — reserve color for status signals only (green=succeeded, red=failed, yellow=pending)
- **Specific microcopy** — every status answers "what happened" and "what do I do next"
- **Opinionated home screen** — curated, not configurable
- **Type scale** — 6 distinct sizes/weights for clear hierarchy

### 3. Vercel
- **Dark-mode-first** — maximum contrast for readability
- **Status everywhere** — tab icons, page titles reflect state
- **Optimistic UI** — show expected state immediately
- **Functional empty states** — show commands, not illustrations
- **Performance IS design** — no animation compensates for slow load

### 4. Notion
- **Sidebar tabs** — organized into Pages, AI, Meetings, Notifications
- **Standardized spacing** — predictable rhythm, flexible for web display
- **Adjacency rules** — lists compact, paragraphs breathe
- **Focus on scannability** — good tools get out of your way

### 5. Card UI Best Practices (2026)
- **Cards for browsing, lists for scanning, tables for comparing**
- **One card, one concept, one primary action**
- **2-second sniff test** — image and first words of title are all that matter
- **Progressive disclosure** — secondary info on detail page
- **3-4 metadata attributes** that drive the decision

## What ScholarZone Should Adopt

1. **Calm navigation hierarchy** — dim secondary nav, let content breathe
2. **Restrained color system** — gold accent only for key actions and positive status
3. **Strong typographic hierarchy** — editorial feel through size/weight/spacing
4. **Card discipline** — image → title → provider → 3 key metadata → action
5. **Status discipline** — green (verified/open), amber (closing soon), red (closed)
6. **Filter clarity** — show active filters as removable chips
7. **Trust signals as design** — verification badges, last-verified dates, source provenance
8. **Restrained motion** — hover lift only, no continuous animation
9. **Responsive transformation** — not just shrinking desktop

## What ScholarZone Should Explicitly Avoid

1. Purple gradients, blue SaaS template aesthetics
2. Excessive glassmorphism, neon effects, giant blobs
3. Meaningless animation or visual clutter
4. Cards crammed with every database field
5. Multiple primary actions per card
6. Color used decoratively rather than semantically
7. Generic "Get started" illustrations in empty states

## Proposed Visual Direction

- **Foundation**: Existing cream/paper (#F7F5F0) and deep navy/ink (#1B2A4A)
- **Accent**: Restrained gold (#C4A44A) for CTAs, verified badges, active states
- **Typography**: Instrument Serif for display, Inter for body — strong size contrast
- **Spacing**: 4px base grid, generous whitespace, clear section rhythm
- **Cards**: Subtle shadow, refined border, single top accent line on hover
- **Motion**: 180ms micro transitions, hover translateY(-2px), no continuous animation
- **Trust language**: Verified shield badge, last-verified date, status indicators, funding clarity

## Proposed Information Architecture

### Home
- Hero: ScholarZone value proposition with stats
- Trust bar: API-driven metrics
- Featured: Curated collections (recently added, closing soon, fully funded)
- Browse: Country, degree, funding categories
- Why ScholarZone: 4 trust pillars
- Process: 4-step verification flow
- Stats: API-driven numbers
- CTA: Browse scholarships

### Scholarships (Discovery)
- Page heading with trust indicator
- Filter section: Search + structured filters with active chips
- Results summary: count + context
- Card grid: 3 columns desktop, 2 tablet, 1 mobile
- Pagination

### Scholarship Card (Priority Hierarchy)
1. Program image (PROGRAM_IMAGE → OFFICIAL_BANNER → OFFICIAL_LOGO → fallback)
2. Status badge (Open / Closing soon / Closed)
3. Funding badge
4. Scholarship title
5. Provider / institution
6. Verification signal (verified + last verified date)
7. Key metadata (Deadline, Location, Level)
8. Primary action (View details)

### Scholarship Detail
- Hero: Image + title + provider
- Meta bar: Status, funding, deadline, verification
- Facts panel: Country, degree, field, eligibility highlights
- Next steps: Visit official source CTA
- Back link

## Implementation Plan

### Phase F.1 — Design Tokens & Primitives
- Polish `theme.css` tokens
- Standardize button, badge, input, card primitives
- Add filter chip component
- Add skeleton loading states

### Phase F.2 — Scholarship Card
- Redesign card with premium hierarchy
- Image system with graceful fallbacks
- Status badges with semantic color
- Verification trust signals
- Single primary CTA

### Phase F.3 — Scholarship Listing
- Refined filter section with chip display
- Results summary
- Card grid with responsive behavior
- Pagination
- Empty state

### Phase F.4 — Homepage Polish
- Hero refinement
- Trust bar
- Featured collections
- Browse categories
