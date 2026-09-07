# ScholarZone — Premium SaaS Redesign Direction

## 1. Research Synthesis

### Current 2026 SaaS Patterns Observed
- **Product-first heroes**: Real UI screenshots above the fold, not illustrations or abstract artwork
- **Typography-led design**: Single display family, tight scale, weight as hierarchy, negative letter-spacing on headlines
- **Restrained color**: Monochrome base, one accent, no gradient clutter. Gradients used once at most, as brand punctuation
- **Density that scrolls**: Long-form pages with modular sections, not sparse minimalism. Vertical rhythm 64–96px between sections
- **Trust through specificity**: Named metrics, real product evidence, dates, counts — not generic logo walls
- **Interaction completeness**: Every element has default, hover, focus, active, disabled, loading, empty, error states
- **Engineer-voice copy**: Short, direct, outcome-oriented. Sentence-case headings. No hedge words.
- **Motion as feedback**: 120–180ms micro-transitions, 250ms smooth reveals. Motion signals state, never decorates.
- **Command palette**: Cmd/Ctrl+K is table stakes for power users in 2026 (Linear, Notion, Stripe docs)
- **Sidebar navigation**: Default for products with 6+ sections. Top bar reserved for 3–6 primary areas or content-first products
- **Strategic minimalism**: Every element must earn its place. Remove before decorating.

### Reference Brands Studied
- **Linear**: Dark-mode-first, Inter, single tuned accent, keyboard-speed motion, density rhythm, "calm design", warm gray neutrals (not cool blue), structure felt not seen
- **Stripe**: White canvas, deep navy ink, single violet accent, Söhne at weight 300 (light display type), animated gradient hero used once, real product screenshots, bento grid, trust through specificity, radius discipline (6–16px)
- **Vercel**: True black/white, Geist typography, negative letter-spacing, sharp edges (0–4px), single blue accent as punctuation, borders at 8% opacity, aggressive whitespace (96–128px), no gradients on core UI, "restraint as feature"
- **Scholar-specific**: stem·spark (editorial serif + mono metadata), ScholarshipMatcher (clean filters), Aplyra (Netflix-style discovery carousel)

## 2. Final Visual Direction

### Brand Character
ScholarZone is **intelligent infrastructure for scholarship discovery** — not a student project, not a generic directory, not a flashy AI landing page. The design communicates: verified, autonomous, globally scaled, calm under pressure, editorial precision.

### Palette Strategy
- **Light mode**: Editorial cream (`#F7F5F0`) + deep navy ink (`#1B2A4A`) + warm gold accent (`#C4A44A`). This is distinctive and SaaS-credible.
- **Dark mode**: Deep navy/ink (`#0f1729`) + warm gold accent (`#d4b85a`). Consistent warm gold in both modes strengthens brand.
- **Restraint**: No gradient-everything. Gradients only as brand punctuation (hero top-edge line, stat accent card). No decorative orbs on public pages.
- **Surfaces**: Use elevation through subtle shadow and border, not heavy glassmorphism. Admin retains spatial glass aesthetic but aligns to gold/navy tokens.

### Typography System
- **Display**: `Instrument Serif` for hero headlines and major section titles. Weight 400 only. Size does the work.
- **Body**: `Inter` for everything else. Weights: 400 (body), 500 (labels), 600 (buttons/emphasis). No heavier weights.
- **Mono**: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace` for technical metadata only (source URLs, IDs, timestamps)
- **Scale**: Explicit tokenized scale. Negative letter-spacing on display sizes (-0.02em to -0.03em).
- **Rule**: One display weight (400), two body weights (400, 500, 600). Hierarchy through size and spacing, not boldness.

### Spacing System
- 4px base unit with micro-adjustments
- `--space-1` (4px) through `--space-16` (128px)
- Sections use `--space-12` to `--space-16` vertical rhythm
- Within components, use `--space-2` to `--space-6`
- Every gap has one owner; children must not add competing margins

### Component Primitives
Reusable classes with consistent behavior:
- `.sz-btn` — primary (navy), secondary (outline), ghost (minimal)
- `.sz-badge` — status, funding, verified chips with semantic colors
- `.sz-card` — base card with subtle hover lift (-2px)
- `.sz-input` — search, select, text inputs with focus ring
- `.sz-table` — comparison table primitive
- `.sz-empty` — empty/no-results state
- `.sz-skeleton` — loading shimmer

### Motion
- **Micro**: 180ms cubic-bezier(0.4, 0, 0.2, 1) — hover states, focus rings, button feedback
- **Smooth**: 250ms cubic-bezier(0.25, 0.46, 0.45, 0.94) — page reveals, panel transitions
- **Reveal**: 700ms cubic-bezier(0.16, 1, 0.3, 1) — staggered scroll reveals
- Hover lifts: `translateY(-2px)` only, never `-5px`
- No continuous animation, no decorative motion, no parallax on public pages
- Respect `prefers-reduced-motion` — all animations become instant

### Anti-Patterns (Explicitly Forbidden)
- Excessive glassmorphism on public pages (admin keeps spatial glass, aligned to tokens)
- Neon gradients or gradient-everything
- Generic purple AI-dashboard aesthetic
- Rounded cards over 14px radius on public pages
- Visual clutter / decorative elements that reduce usability
- Decorative typography that competes with content
- More than one accent color per viewport
- Blue gradients on public pages (brand is navy + gold)
- -5px hover lifts
- Continuous floating animations

## 3. Information Architecture

### Public Pages
- **Home**: Product-first hero with real scholarship discovery UI. Trust bar with live stats. Feature sections built from actual components. Long-form editorial sections with consistent vertical rhythm.
- **Scholarships**: Persistent search, filter controls, active filter visibility, sort, result count. Cards optimized for 5-second scanning.
- **Details**: Structured hero → metadata → panels → related. Long-form content made scannable. Sticky deadline and source actions.
- **Auth**: Clean two-column layout, form card, trust badge.

### Admin
- Keep existing spatial glass aesthetic (already premium)
- Align all color tokens to public theme (gold/navy, not purple/blue)
- Data-dense but premium. Operational feel, not marketing feel.
- Metric cards, activity feed, queues, tables

## 4. Implementation Priority

1. **Tokens** — Align and scale (theme.css)
2. **Navigation** — Brand alignment, mobile improvements
3. **Homepage** — Product-first hero, trust signals, modular sections
4. **Discovery** — Filter UX, card hierarchy, scanning optimization
5. **Details** — Panel architecture, metadata hierarchy
6. **Admin** — Token alignment, remove purple/blue
7. **Primitives** — Extract Button, Badge, Card, Input
8. **QA** — Responsive, accessibility, build, lint

## 5. What Is Intentionally Preserved

- Existing editorial cream + navy + gold palette (light mode)
- `Instrument Serif` display + `Inter` body pairing
- Admin spatial glass aesthetic (refined, not removed)
- All existing functionality (filters, verification, discovery, image pipeline, auth, compare, saved)
- Context-based state management
- Accessibility patterns (aria labels, reduced motion, focus rings)
- `motion` library usage (reduced on public pages, kept where meaningful)
- Scholarship data and API contracts

## 6. Page-Level Design Specifications

### Homepage Hero
- **Background**: Editorial cream (`#F7F5F0`), not dark. Subtle top-edge gold line (1px, 40% opacity) as brand punctuation.
- **Layout**: 12-column grid. Text in columns 1–5, product preview in columns 7–12.
- **Headline**: `Instrument Serif`, `clamp(2.75rem, 6vw, 5rem)`, weight 400, letter-spacing -0.03em. "Find the right scholarship with confidence."
- **Subhead**: Inter, 1.0625rem, line-height 1.75, color `--text-secondary`
- **CTAs**: Primary (navy background, white text), Secondary (outline). Both with subtle hover lift.
- **Product preview**: 3 real scholarship cards stacked with slight offset, showing actual data (title, provider, deadline, status, verification). Not abstract.
- **Live indicator**: Small pill with gold dot + "Live directory" text + 4 live stats.
- **Motion**: Staggered fade-up on mount only. No parallax, no continuous animation.

### Scholarship Discovery Page
- **Header**: Clean, high-contrast. Search bar prominent. Result count and sort visible.
- **Filters**: Horizontal on desktop, stacked on mobile. Active filters shown as pills with clear reset. No mesh layer background.
- **Cards**: 3-column grid on desktop, 2 on tablet, 1 on mobile. Compact but premium.
- **Card hierarchy**: Status badge → Title → Provider → Deadline (high-contrast, scannable) → Country/Degree → Verification signal. Progressive disclosure for secondary info.

### Scholarship Detail Page
- **Hero**: Clean surface with subtle border. Image on left, content on right (desktop). Sticky deadline panel on desktop.
- **Metadata**: Country, degree, funding, status, deadline as labeled rows. Verification state as factual badge.
- **Panels**: Overview, Funding, Eligibility, Requirements, Timeline, Official Source, Related. Consistent panel styling.
- **Actions**: Sticky "Apply via official source" CTA on desktop. Save/Compare in card footer.

### Admin Dashboard
- **Background**: Deep navy/ink. Gold accent for actions and highlights.
- **Cards**: Spatial glass with gold specular highlights, not purple/blue.
- **Metric tiles**: Compact, data-dense, gold accent for values.
- **Tables**: Clean, high-density, alternating row opacity.
- **Review queue**: Fast-scan cards with approve/reject as primary actions.

## 7. Mobile Specifications

- **Navigation**: Bottom tab bar (max 5 items) for primary destinations. Slide-over drawer for full menu.
- **Search**: Full-width, sticky on scholarship discovery.
- **Filters**: Collapsible filter sheet on mobile.
- **Cards**: Single column, full-width.
- **Touch targets**: Minimum 44px for all interactive elements.
- **Typography**: Slightly larger base size (16px), comfortable line height (1.6+).

## 8. Accessibility

- Semantic HTML (`nav`, `main`, `article`, `section`, `header`, `footer`)
- Keyboard navigation throughout
- Visible focus rings (gold, 2px + 2px offset)
- ARIA labels on icon-only buttons
- `prefers-reduced-motion` — all animations become instant
- Sufficient color contrast (WCAG AA minimum)
- 44px minimum touch targets on mobile
- Screen reader announcements for dynamic content (`aria-live`)

## 9. Performance

- No unnecessary dependencies
- No heavy animation libraries on public pages
- CSS-first animations where possible
- Tokenized CSS avoids duplication
- Existing React/Vite architecture preserved
- Lazy load images
- Skeleton loading for async content
- Target: Build < 300ms, Lint clean
