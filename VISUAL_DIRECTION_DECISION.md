# VISUAL_DIRECTION_DECISION.md

The binding art-direction contract for ScholarZone. Supersedes
`EDITORIAL_SYSTEM.md`. Every value below is either measured from a published
design system or measured from this codebase — none is invented taste.

---

## 1. What should ScholarZone look like?

**A live research desk.** A full-bleed instrument in warm paper and ink, dense
with real figures, softly lit, quietly in motion — a Bloomberg terminal that a
magazine art director signed.

The previous direction ("restrained editorial minimalism") was a correct instinct
applied past its useful life. Its diagnosis of the problem — too many boxes, too
much animation, no hierarchy — was right. Its cure was wrong on three counts that
the rendered result proved: **restraint without density reads as emptiness**,
**a 1320px column on a 1440px screen reads as a prototype**, and **a scale where
four of six radius tokens equal `2px` reads as cheap, not severe.**

---

## 2. Ten non-negotiable principles

1. **Full-bleed by default.** `--sz-container` becomes a **prose measure**, never
   a page frame. Bands and shells reach the viewport edge; only running text is
   capped.
2. **No `100vw` bleed, ever.** `margin-inline: calc(50% - 50vw)` overshoots by the
   scrollbar and `scrollbar-gutter` only fixes Chrome. Full-bleed = a `width:100%`
   band that is a direct child of the shell, with an inner
   `width: min(100% - var(--gutter)*2, var(--sz-shell))`.
3. **Widen by adding a zone, never by stretching.** Past 1560px the third column
   appears (filter rail · results · insight rail). A 1760px-wide result row stops
   being a row.
4. **Density is the product.** **12 result rows visible in a 900px viewport.** The
   hero must not consume a full viewport before the first record.
5. **Motion is a system or it is nothing.** Five duration tokens, three easings,
   four motifs. No ad-hoc duration anywhere. Under `prefers-reduced-motion` the
   tokens go to `0ms` so the whole product changes behaviour with zero
   per-component overrides.
6. **One radius ladder, six real steps.** No token may lie about its own name.
   Nesting law: `r_child ≤ r_parent − 4px`.
7. **Softness comes from luminance, not from shadow.** Elevation is a lighter
   surface. The product carries **zero** decorative `box-shadow`.
8. **Instrument Serif is display-only, with a hard floor of 24px.** It ships one
   weight, so hierarchy can never come from weight, and below ~20px its condensed
   width turns to mush on 1x DPR. Any card title in the serif is a bug.
9. **Every band states a true number.** 481 records · 51 countries · 157 fully
   funded · 480 verified — staged as a live instrument, not a footnote. Numbers
   come from `GET /scholarships/stats` and nowhere else.
10. **Trust is demonstrated, not decorated.** A glyph that asserts provenance the
    product cannot prove is worse than nothing. The official source host and the
    date it was read are shown in full on every record.

---

## 3. Discarded decisions

| Discarded | Why | Measured |
|---|---|---|
| 1320px centred column as the page frame | "giant blank side gutters" | **361px dead per side at 1920 — 19% of the screen** |
| Radius `1px / 2px / 2px / 2px / 3px / pill=2px` | six tokens, four identical values, `pill` is square | below 4px nothing reads as soft |
| Zero animation | signalled nothing shipped | 9 duration tokens already defined and unused |
| 929px hero on the home page | "oversized hero occupying space without information" | first result row at **y=1400px** |
| ~300px result rows | "wastes viewport" | **2 rows per 900px screen** |
| 240px rail at `min-width: 1024px` | a 240px rail at 1024 leaves ~700px of results | 1024–1279 gets the worst of both |
| 6×2px filled/hollow square as the *primary* trust signal | decorative glyph asserting unverifiable provenance | demoted to a secondary mark; evidence promoted |
| Verification state as a bare sentence | correct logic, wrong register | reads as a caption, not a verdict |
| Gold on four things at once | an accent on everything is on nothing | gold is now a **state** |

**Reusable unchanged:** Instrument Serif + Inter pairing · mono citations ·
paper/ink/navy/gold hues · `.sz-button--primary` · `.sz-field__*` · `.sz-table` ·
`Badge` · `Skeleton` · `EmptyState` · `Figure` · every verification and
comparison rule · all data contracts.

---

## 4. Shape language

```
--r-0       0      full-bleed bands, table cells, hairline dividers
--r-1       4px    chips, inline facts, inputs, small controls
--r-2       8px    result rows, panels, selects      (was 2px)
--r-3       14px   media frames, aside cards, hero tiles
--r-4       22px   feature and marketing surfaces
--r-pill    999px  badges, status chips, logo plates (was 2px)
```

`--radius-xs` and `--radius-md` are **deleted**, not aliased. Nesting law from
Cloudfour / Apple's concentric rule: a child's radius never exceeds its parent's
minus the gap between them, or the inner corner visibly pinches.

Pills are for **status** only — a badge, a state chip, a logo plate. A pill on a
nav link or a primary button reads consumer-bubble and undercuts an academic
register.

---

## 5. Motion language

### Durations (five steps, from Material 3 / Fluent 2 ramps)

| token | value | used for |
|---|---|---|
| `--sz-dur-press` | 90ms | press feedback |
| `--sz-dur-fast` | 140ms | hover, chips, toggles, colour |
| `--sz-dur-base` | 220ms | row lift, tab underline, accordion |
| `--sz-dur-enter` | 420ms | section + row reveal |
| `--sz-dur-route` | 380ms | route content in (200ms out) |

### Easings (Material 3)

```
--sz-ease-out      cubic-bezier(0.2, 0, 0, 1)       entrances, hover-in
--sz-ease-standard cubic-bezier(0.4, 0, 0.2, 1)     small state, press
--sz-ease-in       cubic-bezier(0.3, 0, 1, 1)       exits only
```

Enter 420ms / exit 200ms — never symmetric. **No springs, no bounce.** This is a
reference desk.

### Four motifs — that is the whole vocabulary

1. **Instrument sweep** — a 1px gold rule draws left→right on load, 520ms, once.
2. **Ledger reveal** — rows and sections stagger in: `translateY(12px)` +
   opacity, 45ms apart, **clamped to 6 items** (`min(45ms, 260ms / n)`) so the
   total never exceeds 300ms regardless of item count.
3. **Ledger count-up** — stat-band figures count up once on mount, 700ms,
   tabular numerals so nothing reflows.
4. **Hover lift** — row background shifts one luminance step and the rule extends;
   **no translate, no shadow**. Media inside a frame scales to `1.03` from
   `620ms` with `overflow:hidden` on the frame and `transform` on the child.

Plus: press `scale(0.98)`, chips `scale(0.96)`, tab underline `scaleX()` from the
left. Hover and press are gated behind `@media (hover: hover)` — `:hover` persists
after a tap on touch and reads as broken.

**Route transition**: fade + 8px rise keyed on `location.pathname`. **No View
Transitions API** — support is incomplete in Safari/Firefox as of 2026 and a
partial implementation is worse than none.

**Reveal robustness** — the previous pass removed scroll reveal because it left
blank pages. That regression must not recur, so:
- CSS default state is **visible**. Only a `js-motion` class on `<html>`, set by
  the observer module itself, hides anything.
- `IntersectionObserver` with `threshold: 0.15`, unobserved after first fire.
- Everything above the fold gets `data-motion="now"` and never waits.
- A 1200ms failsafe reveals anything still hidden.

**Reduced motion**: all five duration tokens → `0ms`, all delay tokens → `0s`,
entrance `transform` → `none` so a reveal collapses to a pure fade. One block in
`index.css`, zero per-component overrides.

---

## 6. Spacing and density

4px base: `4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64 · 96 · 128`.

Leading snapped to the 4px grid (Bringhurst 2.2.2): 14→20, 13→18, 12→16,
16→24, 18→24. Prose may run off-grid (17→28). Two incompatible leading systems
in one product is a documented cause of "feels rigid".

Section rhythm: 96px between sections desktop / 64px to the opening rule;
80 / 48 on mobile. Reduced from 112/72 — the previous rhythm spent more space on
gaps than the catalogue spent on records.

**Catalogue row grid** (desktop, ≥1280):

```
--r-2  64px  logo / media
1fr            name + institution + provenance
216px          funding · degree · country
150px          deadline (tabular, emphasised)
104px          verification state
44px           action
```

Row height **132–144px**, title clamped to 2 lines, facts on one line.
Mobile 390px: rows 112–124px, logo 52px, deadline the only emphasised value.

---

## 7. Full-screen strategy

```
--gutter        clamp(16px, 3vw, 40px)
--sz-shell      min(100% - 2*gutter, 1560px)
--sz-prose      min(100% - 2*gutter, 68ch)
--sz-shell-xl   min(100% - 2*gutter, 1800px)
```

- `.app-shell` — `overflow-x: clip`, never `hidden` (that breaks the sticky rail
  and the detail aside).
- Full-bleed bands: `width: 100%` as a **direct child of the shell**, inner
  wrapper `width: var(--sz-shell-xl)`. No viewport math anywhere.
- **1440** — three-zone catalogue: rail 248px · results `1fr` · insight 300px.
- **1280–1439** — two zones: rail 224px · results `1fr`.
- **1024–1279** — rail becomes a right drawer; sticky 52px toolbar with Sort +
  `Filters (n)` + a scrollable chip rail.
- **<1024** — single column, filters in a bottom sheet at `max-height: 85dvh`
  with a `Show N results` primary.
- 1680+ adds the insight rail; 1920+ widens the shell to 1800px. Past that the
  results column caps — a row wider than 1760px stops being scannable.

Use **container queries** on the catalogue so the zone decision follows the
column, not the window. The codebase currently has zero `@container` rules; that
is the missing tool, not a missing hack.

---

## 8. Highest-leverage changes, in implementation order

1. **Radius ladder + full-bleed shell.** Every surface downstream depends on these.
2. **Catalogue density.** Three-zone shell, 132px rows, 12 visible. The single
   biggest perceived upgrade.
3. **Motion system.** Ship the tokens; purge the residual animation from the
   admin console in the same pass so motion is one system, not an admin privilege.
4. **Real evidence instead of a decorative glyph.** Official-source host and read
   date shown in full on every record; the square demoted to a secondary mark.
5. **Instrument the stat band.** 481 / 51 / 157 / 480 as a full-bleed count-up
   band that doubles as the hero's credibility argument.

---

## 9. Out of scope

Match 2.0 · Count Intelligence · verification contracts · scholarship data ·
public visibility rules · routing · API calls · auth. The known issues `?degree=`,
`?funding=` and `DIRECTORY_LIMIT = 100` remain tickets. No new dependencies —
the entire motion system is CSS plus one `IntersectionObserver`.
