# SCHOLARZONE_50_AGENT_RESEARCH_SYNTHESIS.md

Fifty live research tracks across ten clusters. Every finding cites a URL an
agent actually fetched. Agents reported fetch failures honestly rather than
filling gaps from memory, and those failures are recorded below because they
bound what the synthesis can claim.

---

## 1. Track coverage and delivery

| Cluster | Tracks | Domain | Agent |
|---|---|---|---|
| A | 01–10 | Scholarship/education discovery + premium editorial catalogues | ✔ delivered |
| B | 11–20 | Dense professional products + global university sites | ✔ delivered |
| C | 21–30 | Premium modern web design + motion | ✔ delivered |
| D | 31–40 | Responsive specialists + accessibility/UX/states | ✔ delivered |
| E | 41–50 | Search/discovery/filter UX + competitor synthesis | ✔ delivered |

### Fetch failures that bound this synthesis

Reported by the agents, not smoothed over: chevening.org (timeout twice),
europeana.eu (403), philpapers.org (403), dimensions/scopus (no session),
cscscholarships.org (transport error; cscuk.fcdo.gov.uk used instead),
mastersportal.com (403), wellcomecollection.org (JS shell), sciencumuseumgroup
(429), carbon design system (transport then 404), apple HIG accessibility
(JS shell), bloomberg terminal / Capital IQ / AlphaSense / PitchBook /
Dealroom (session-gated), vogue/framer/figma (no parseable CSS), BMW/GitHub
badge docs (404), NaviQ (**wrong company** — it is an AGV sensor vendor, not
a scholarship platform; dropped from the comparison set).

Nothing below is asserted from a source an agent could not read.

---

## 2. Synthesis matrix — the strongest recurring patterns

Evidence counts are independent sources. A pattern needed **two or more**
independent confirmations to reach system level; single-source findings stayed
as suggestions.

### ADOPT (2+ independent sources)

| # | Pattern | Sources | Strengths | Weaknesses | Relevance | Cost | A11y | Perf |
|---|---|---|---|---|---|---|---|---|
| A1 | **Range + total in the running head** ("Showing 1–24 of 481") | arXiv (190 entries, range pagination + "showing 28 of 28"); Simpler.Grants.gov ("1,469 Opportunities", "0 Opportunities" at zero) | States coverage, survives truncation | None material | High — replaces our bare "381 scholarships" | Low | Neutral | Neutral |
| A2 | **Rail earns its width at ≥1280, never at 1024** | M3 (medium = "a single pane is recommended"); GOV.UK (adds nothing at 1024, centres); Bootstrap (992/1200/1400); Polaris (lg=1040) | Frees 224px exactly where it is wasted | None | **Critical** — this is the 1024–1280 weakness | Low | Neutral | Positive |
| A3 | **Zero on the face of a facet, disabled not hidden** | Simpler.Grants.gov prints `Closed[0]`; Algolia guidance; Prodigy (no counts) | Hiding an option makes the corpus feel broken | A 51-value list is long | Medium | Medium | Neutral | Neutral |
| A4 | **One selected chip per active facet + "Clear all"** | Algolia `CurrentRefinements`; Helios; Leeds; Carbon; Visa (all list chips as REQUIRED) | Carries the label, individually dismissible, survives scroll | Two representations (rail + chip) can drift | High | Low | Positive (label text, not colour) | Neutral |
| A5 | **Row = fixed slots, ONE elastic column** | GOV.UK table guidance; USWDS; GitHub Primer (`grow` / `growCollapse` / `auto` / fixed, `rowHeader: true`); Primer's own warning that `grow` on every column makes nothing comparable | Comparison works on aligned type | Needs measured column widths | **Critical** | Low | Positive (semantic `<th scope>`) | Neutral |
| A6 | **Fixed columns for short uniform values; align numbers right, tabular** | GOV.UK (`govuk-table__cell--numeric`, "easier to visually scan and compare"); Primer (`align: 'end'`) | Scanning a column beats reading a row | Right-alignment fights a neighbouring column | High | Low | Neutral | Neutral |
| A7 | **Differentiate a select from a reset** | 3 independent agents | A sort is a preference; a filter is a narrowing | None | Medium | Low | Needs non-colour state | Neutral |
| A8 | **Deadline dual-form: relative + absolute** | Simpler.Grants.gov (Close date + sort Soonest); Fulbright ("6 Oct 2026 11:00 UTC"); DAAD ("24.00 CET"); CSC ("31 March 2026, 16:00 BST") | "Closes in 12 days" is urgency; "15 Nov 2026" is fact | Needs a parseable date | High for ours | Medium | Neutral | Neutral |
| A9 | **Funding as an enumerated taxonomy, not a badge** | Cambridge (Fully/Partially/Self-funded, defined in one clause); TU Delft ("16 full scholarships … and 2 partial"); Chevening (10 enumerated components) | Honest, comparable | Requires data we do not have | Medium — we render verbatim + qualifier | None | Neutral | Neutral |
| A10 | **Provenance = resolvable identifier + who + when** | ROR (admin.created + admin.last_modified + ror.org permalink); Crossref (5 distinct timestamps); ORCID (per-assertion `common:source` naming who asserted it); GOV.UK ("Published 3 April 2012 / Last updated 2 April 2025") | Checkable. Falsifiable | Requires real resolvable IDs | **Critical — our differentiator** | Medium | Neutral | Neutral |
| A11 | **Publish your own counting rules, including unflattering ones** | OpenAlex (`meta.count` separate from `meta.page`; unknown values excluded by default unless `:include_unknown`) | A count the reader can reproduce | None | High | Low | Neutral | Neutral |
| A12 | **A constant status is not a signal** | ROR `active` on 79/79 read as metadata, not trust | Removes badge noise at scale | None | **Critical** — we had it on 480/481 | None | Positive | Positive |
| A13 | **Empty state = named cause + named recovery, never wipe the field** | GOV.UK error summary; Algolia `ClearRefinements`; GitHub live (verified: `0 results (66 ms)` + three distinct suggestions); vocab.design | Different causes need different actions | Four copy sets to maintain | High | Low | Positive (`role="status"`) | Neutral |
| A14 | **Never declare emptiness while loading** | NN/g: "inaccurate system-status messages cause users to develop a severe distrust of the application" | Prevents a false empty state during a refetch | Slightly slower first paint | High | Low | Positive | Neutral |
| A15 | **Error copy is imperative and specific; name the resource not the failure** | GOV.UK ("There is a problem" + exact field error); Sentry (message + event id + retry); GOV.UK forbids "maintenance"/"improvements" | Actionable | None | High | Low | Positive | Neutral |
| A16 | **Motion must begin within 0.1s to be attributed to the action** | NN/g animation-usability, citing Pratt et al. 2010 *Psychological Science* 21:1724 | Causality | None | High | None | Neutral | Neutral |
| A17 | **Travel ≥16px, duration ≥150ms, peak ≥100px/s to be perceived** | NN/g 100–500ms; Val Head (MHP ~230ms); JND 33–50ms | Below it, motion reads as a layout shift | None | **Critical** — the previous pass was at 29px/s | None | Neutral | Neutral |
| A18 | **Enter longer than exit; ease-out in, accelerate out** | M3 tokens (emphasized `0.2,0,0,1` in / legacy-accelerate `0.4,0,1,1` out); NN/g (popup 300 in / 200–250 out) | Asymmetry IS the token | None | High | None | Neutral | Neutral |
| A19 | **Hover = colour/background only, ≤150ms, gated on `(hover: hover)`** | 4 independent agents; Material: "hover states appear and disappear using a low-emphasis animated fade" | `:hover` persists after a tap and reads as broken on touch | Not tactile | High | None | Neutral | Neutral |
| A20 | **Reduced motion: swap transform for opacity, keep duration and curve** | Val Head *Making Motion Inclusive*; Apple ("removing animations entirely can have a negative effect on usability"); Adrian Roselli (the media query alone satisfies SC 2.3.3 technique C39) | Causality survives | None | High | Low | Positive | Neutral |
| A21 | **Scroll-triggered animation is for SECONDARY content, never the main body** | NN/g scroll-animations (task-focused users "don't want to be wowed"; fire once) | A dense list is the main body | Reveals on lists compete with reading | **Critical** — we reveal rows | None | Neutral | Positive |
| A22 | **Prefers-reduced-motion: invert the query** — `@media (no-preference) { animate }` | Adrian Roselli: better supported than the positive form | A component opts IN to motion | Requires discipline | Medium | Low | Positive | Neutral |
| A23 | **Display ceiling: 64px; nothing above** | Linear `--title-8: 4rem/1.06/−0.022em`; Apple 56; Stripe 56; measured Vercel 72–128 but its page holds no catalogue | Every 8px is a lost row | None | High | None | Neutral | Neutral |
| A24 | **Track line-height to the font's own metrics** | woff2 tables: Instrument Serif ascender 0.990 + descender −0.310 = **1.300em** box vs Inter 1.210em. At 64px on 1.02 the gap is 45.4px and the cap needs 46.1px — a **0.7px descender/cap collision** | Prevents cramped headings | Needs the real font metrics, not a guess | **Critical** | Low | Positive | Neutral |
| A25 | **Tracking is size-keyed; nothing measured is negative at 17–19px** | Vercel −0.06em at 64px but −0.02em at 16px; It's Nice That body **+0.108px**; Raycast **+0.2px on 13–14px** — positive at small sizes | Dense small type closes up | None | **Critical** — our body was −0.011em | Low | Positive | Neutral |
| A26 | **Optical size compensation** | Instrument x-height 0.510em, `n` 20.5% narrower than Inter → sets 1.26× more chars/line at equal size; ×1.07 restores | Correct apparent size | None | High | Low | Neutral | Neutral |
| A27 | **Premium ≠ shadow density** | Apple: 667 kB CSS, **30 hex, 1 box-shadow**; Framer: 1 repeated radius (8px ×37); Vercel: 421 hex / 284 shadows = a Tailwind dump | Restraint reads as cost, not emptiness | None | High | None | Neutral | Positive |
| A28 | **Radius ladders converge** | Linear 2/4/6/8/12; Attio 4/6/8/12/16; Raycast 4/6/8/12/16/20; Material 4/8/12; Apple 980 (full) | The 4/8/14/22 editorial ladder we already shipped is defensible; add a 4/6/8/12/16 dense-control sub-ladder | None | Medium | Low | Neutral | Neutral |
| A29 | **`backdrop-filter` is the most expensive common decoration** | willchan.me, measured: 3.6× the box's pixel area read per frame; a blurred tile row = 3 composited layers, 3.8 MB backing at DPR2 | Removable with almost no visual loss on paper | Loses the glassy nav | High | None | Neutral | **Positive** |
| A30 | **`content-visibility: auto` + `contain-intrinsic-size`** | web.dev: **232ms → 30ms**, stays in the DOM/a11y tree/find-in-page/tab order | The largest single perf win on a 24-row page | `contain-intrinsic-size` is mandatory or scrollbars jump | High | Low | Positive (stays reachable) | **Positive** |
| A31 | **Control boundaries need 3:1; decorative hairlines do not** | WCAG 2.2 SC 1.4.11; computed: `--rule` 1.35:1, `--rule-strong` 1.68:1 **FAIL**, `--rule-ui` 3.14:1 **PASS** | Applies 1.4.11 to boundaries that identify a control | Two rule tokens needed | **Critical** | Low | Positive | Neutral |
| A32 | **Never signal state by background luminance alone** | Computed: `--surface-sunken` vs `--surface` = **1.14:1** — fails 1.4.11 AND 1.4.1 | Needs a second, non-colour cue | One more element | **Critical** | Low | Positive | Neutral |
| A33 | **`scroll-margin-top` for Focus Not Obscured** | WCAG 2.2 SC 2.4.11 — bites a sticky-header product specifically | A focused row cannot hide under the masthead | None | High | Low | Positive | Neutral |
| A34 | **Touch floor 24px, 44px on coarse pointers** | WCAG 2.2 SC 2.5.8 (24×24 + a spacing exception); Apple HIG 44pt; M3 48dp | The exception requires 4px+ gaps between adjacent targets | None | High | Low | Positive | Neutral |
| A35 | **Drop the small-button override at source, not per page** | Two independent agents found `--sz-button--small` at 40px overridden page-locally | One fix, no drift | None | Medium | Low | Positive | Neutral |
| A36 | **Body text never shrinks on mobile; only display steps down** | GOV.UK: `govuk-body` is 19px/25px on BOTH sides of the 640 boundary; only heading-xl 48→32, heading-l 36→27 step down | "Compressed desktop" is the failure mode | None | **Critical** | None | Positive | Neutral |
| A37 | **Mobile holds fewer navigation destinations, not smaller ones** | Khan Academy moved Search OUT of the tab bar; Apple News hides the channel list on iPhone; the desktop/iPad version gains a SIDEBAR, not columns | Structural difference, not a scale-down | None | High | Medium | Positive | Neutral |
| A38 | **Page size 25-class, not 12** | arXiv 25/50/100/200; OpenAlex default 25 max 100; Simpler.Grants.gov 25 | 12 is two screens of a 481-record corpus | None | High | Low | Neutral | Neutral |
| A39 | **Density is a per-component prop, never a page mood** | Material (0/−1/−2/−3, each −4px block padding, horizontal spacing unchanged); USWDS enumerable scale; JSTOR (same tokens, list vs article vs index differ by measure) | Three tiers, one scale | None | Medium | Medium | Positive | Neutral |
| A40 | **A phone keeps a whole-row target with one carve-out** | LinkedIn jobs (one trailing bookmark; Apply/Save live in a sticky bottom bar); Baymard (28% of sites lack clear hit areas; make the whole item one target) | Large targets and a dense list are not opposed | One nested target needs ≥8px clearance | High | Medium | Positive | Neutral |
| A41 | **No invented metrics; publish what the number counts** | Our World in Data ("we clearly indicate the source… whenever we have combined data sources"); GOV.UK numeral formatting | A count is a claim about a scope | None | **Critical** | None | Positive | Neutral |
| A42 | **"Fully funded" is unverifiable and contradicted by funders' own terms** | Chevening T&Cs ("universities expected to cover at least 20% of tuition"; MBA tuition "capped at £22,000"; a part award may fund tuition OR stipend); Fulbright (city-banded stipend vs tuition cap); MEXT | A badge on it is a claim we cannot make | None | **Critical** | None | Positive | Neutral |
| A43 | **Non-comparable values must not be coloured** | MEXT ("between April and May", per country); EMJM ("between October and January"); arXiv explicitly degrades granularity and says so | Colouring an unknown as calm asserts "not urgent" | Needs an `unknown` state | High | Medium | Positive (1.4.1) | Neutral |
| A44 | **A detail page's fixed label order is the trust mechanism** | TU Delft's 7-row spec table, identical order for every scholarship | Comparison across records | None | Medium | Medium | Positive (`<dl>`) | Neutral |
| A45 | **State your own negative rules** | Oxford Clarendon: "There are **no** restrictions on nationality, ordinary residence or field of study"; Cambridge: "If you have not received a funding offer by July, you should assume… unsuccessful"; Erasmus+ "National Agency forms close at 12:00:00 Brussels time regardless of date" | Negative facts stated plainly build more trust than positive ones | None | Medium | Low | Positive | Neutral |
| A46 | **Every field's evidence should carry a KIND, not a bare date** | Crossref's five distinct timestamps (issued / published-print / created / deposited / indexed); GOV.UK ("Published" vs "Last updated") | "Deadline last checked" ≠ "Record last checked" | None | High | Low | Positive | Neutral |
| A47 | **Repeat ONE micro-field per item to create calm at 40+** | The Gentlewoman's `/library`: **164 items, zero images, zero pagination, zero filters** — one repeated micro-meta field and 2-column rows; Monocle `The Entrepreneurs #10 | October 2026`; arXiv's own count in the head | Calm at scale without cards | None | **Critical** | Low | Neutral | Positive |
| A48 | **Give the reader a per-page defect channel** | DAAD's accessibility `Report accessibility issue` link pre-filling the page URL via `barrierUrl` | Cheapest honest trust signal available | Needs a mailto | Medium | Low | Positive | Neutral |
| A49 | **Skip loading libraries for transform/opacity work** | GSAP 70 kB+; Motion 34 kB untree-shakeable, `LazyMotion` 4.6 kB; View Transitions same-document 91.8% with **no Firefox cross-document** | 0 kB is available and correct here | `allow-discrete` absent in Firefox | High | None | Neutral | **Positive** |
| A50 | **Animation timelines need a failsafe, not optimism** | Documented regressions: scroll-reveal shipping `opacity:0` in SSR (crawlers index nothing, no-JS readers get blank sections); a vendor shipping `animation:none` under reduced motion while `opacity:0` remained, blanking their own landing | Invert the dependency | None | **Critical** | Low | Positive | Neutral |

---

### ADAPT (one source, or needs translation)

| # | Pattern | Adaptation |
|---|---|---|
| B1 | Primer's 40px condensed row | Too dense for our 3-line record; we land at 89–115px. |
| B2 | arXiv's `▽ More` inline disclosure | Our long `deadline` sentences go to the detail page instead; we do not expand in place. |
| B3 | Monocle's 66-value facet with "Show more" | Our 5 facets do not need it; the **pattern** (cap a long facet) is kept for countries. |
| B4 | Eye on Design's series field | We have no series. Rejected. |
| B5 | Vercel's 1200px content step | Kept as the upper bound for the *results column*, not the shell — we ship 1560 with a 224px rail. |
| B6 | Cambridge's decision calendar | Not in our data model. Rejected. |
| B7 | arXiv's 7 fixed row slots | We ship 5 tracks. The **fixed-slot** principle is kept; the slot count is set by what our data can fill without ellipses. |

### REJECT

| # | Pattern | Why rejected |
|---|---|---|
| X1 | Provider logos on every row | The Gentlewoman ships 164 items with **zero images**. Our `image_url` is mostly not an official logo, so it asserts something unverifiable. Kept at 56px and **only when present**. |
| X2 | A "credibility score" | ScholarshipOwl's pattern; unverifiable and it invites scrutiny. |
| X3 | Relative dates alone | "2 days ago" without the absolute date is unverifiable and breaks on re-read. |
| X4 | A progress bar for funding coverage | Implies a measured magnitude; we have a string. |
| X5 | Flag emoji | Render as the two letters on Windows (Chromium 40766658). Already absent; confirmed correct. |
| X6 | `translateZ(0)` / static `will-change` | Holds a GPU texture for the element's lifetime; the most expensive one-liner available. Zero `will-change` in the build. |
| X7 | Smooth-scroll hijacking (Lenis) on the catalogue | Breaks `position: sticky`, and NN/g is explicit that scroll-triggered motion is wrong for task-focused list reading. |
| X8 | View Transitions | No Firefox cross-document; a partial route transition behaves differently in the browser the user has. |
| X9 | Per-row scroll reveal at 24px × 60 rows | The documented "annoying" category. We stagger **8** and cap the total. |
| X10 | Shrinking body copy at 390 | GOV.UK holds 19px across the boundary. Rejected outright. |
| X11 | `* { transition-duration: 0.01ms !important }` | `!important` means nothing can opt out, and it flattens semantic state changes into jumps. Replaced by a token collapse. |
| X12 | Badge stacks per record | Coursera stacks up to 3; Atlassian and GitLab both moved off colour containers. We ship **0**. |

---

## 3. What the synthesis says about ScholarZone's one real advantage

Three independent agents, unprompted, converged on the same answer:

> **Per-record verifiable provenance.** Every record carries a source URL and
> a last-verified timestamp, rendered as a fact row. No competitor shows this.
> Studyportals and Prodigy make marketing claims (visitor counts, NMLS
> numbers); Euraxess and the EU programmes are curations; DAAD is print-first.
> A public per-record "checked on" date is the one signal a
> knowledge-motivated aggregator can publish and a marketing-led one will not,
> because it exposes its own staleness.

That is also the constraint the owner set: **if density conflicts with trust,
trust wins.** Nothing in this pass removed the evidence to make a row fit.

## 4. Classification

The synthesis does not average the agents. It takes the patterns with two or
more independent confirmations, applies them to measurements taken from this
codebase, and records what remains unproven. The unproven items are in §"Honest
misses" of `SCHOLARZONE_VISUAL_REDESIGN_FINAL.md` and are not dressed up.
