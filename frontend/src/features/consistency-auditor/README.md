# Application Consistency Auditor V1

A browser-only review aid for a student's own application documents. It
compares the text of the SOP / motivation letter, the CV / resume text, and
any additional answers, and lists places where the documents **may** state
different things.

It is not an admission predictor, not a plagiarism or AI-writing detector,
not a truthfulness or fraud engine, and it never writes anything for the
student. Every output is a question to check, phrased with "may conflict" or
"differs", never "wrong", "false" or "fraudulent".

## Architecture

Four layers, each dependent only on the one above it:

| Layer | Files | Rule |
|---|---|---|
| Engine (pure) | `engine/` | No DOM, no network, no storage, no React. Deterministic: same input ⇒ same findings, same order, same IDs. |
| Review state | `state/` | Session decisions (dismiss / reviewed), and the opt-in storage adapter. |
| UI | `components/`, `pages/` | Rendering and events only. Never normalises or rewrites text. |
| Public surface | `index.js` | The `enabled` flag and the module's exports. |

```
engine/normalize.js      numerals, dates, names — always returns new values
engine/findings.js       categories, confidence labels, stable IDs
engine/validator.js      size limits and input refusal
engine/rules/dates.js    DATE-01..05
engine/rules/entities.js NAME-01..04
engine/rules/claims.js   CLAIM-01..03
engine/index.js          review() — validation, rule run, deterministic sort
state/storage.js         the only module touching browser storage
state/reviewState.js     decisions, invalidation, opt-in persistence
```

The engine never mutates its input. Normalisation works on internal copies;
each finding carries `start`/`end` offsets into the *original* string so
excerpts are displayed exactly as written (asserted in the test suite).

### Finding ID and determinism

An ID is `ruleId-<digest>`, where the digest is over the comparison's
content (normalised excerpts, or fact values for date/number rules) — never
over document text, so an ID never leaks content and never changes when a
sentence is reworded around the same fact. Ordering is category, then
document, then position, then rule and ID.

## Rule catalogue

### A. Dates and timelines

| ID | Name | What it flags | Limits |
|---|---|---|---|
| DATE-01 | Graduation dates differ | Two documents name the same degree with different completion years → *Possible factual inconsistency* | Keyed on degree + field, not wording; does not know whether the years are the same programme |
| DATE-02 | Range ends before it starts | "2019 – 2015" → *Possible factual inconsistency* | Year-granularity only; a month/day typo inside one year is not detected |
| DATE-03 | Periods overlap | Two study/work periods overlap → *Needs human review*, never an inconsistency | One period per line; concurrent study and work is explicitly legitimate |
| DATE-04 | Unsupported date format | Bengali calendar months (বৈশাখ…), and lines too long to scan → *Needs human review* | Never converted, never guessed, never silently skipped |
| DATE-05 | Same institution, different start years | Reserved: currently folded into DATE-01's degree keying | — |

Supported English formats: `Jan 2023`, `January 2023`, `Sept 2022`,
`01/2023`, `2023-01`, `2023-01-15`, `15 January 2023`, `January 15, 2023`,
`2021–2023`, `2021 - present`, `since 2022`, `since January 2023`,
`Present`/`Current`/`Currently`/`Ongoing`.

Supported Bengali: numerals ০–৯ (২০২৩ = 2023), Gregorian month names
(জানুয়ারি…ডিসেম্বর), full Bengali dates (`১৫ জানুয়ারি ২০২৩`), and mixed
Bengali/English text.

**Not** converted: Bengali calendar months. The Bengali year begins in
mid-April, so a Bengali month + year cannot be mapped to a Gregorian date
without knowing which Gregorian year is meant; those become DATE-04
"Needs human review". A word that merely looks like a month ("completed
2021") is correctly read as a year.

### B. Entity and wording differences

| ID | Name | What it flags | Limits |
|---|---|---|---|
| NAME-01 | Same institution, different formatting | Names that normalise to the same thing, or differ only by an abbreviation → *Formatting or naming variation* | Thresholds below; will not merge names whose differing words identify the institution |
| NAME-02 | Same project, different title | Project titles ≥ threshold similarity → *Possible factual inconsistency* (weak/moderate) | Similarity is not identity; a shortened title is offered, not asserted |
| NAME-03 | Comparable numbers differ | CGPA/GPA, publication count, years of experience, team size → *inconsistency* (or *Needs human review* for CGPA/GPA) | Reads the raw text, so decimal points survive; requires a labelled number in each document |
| NAME-04 | Same number, possibly different scales | A stated scale differs, e.g. `/4.0` vs `out of 5.0` → *Needs human review* | Only when a scale is stated; a bare number produces NAME-03 |

Similarity thresholds (documented so they can be argued with):

- `exactOrNear 0.94` — at or above this names are treated as one entity for
  formatting checks, **provided** every differing word is in a small
  structural list (`of`, `the`, `university`, `college`, `institute`, …).
- `variation 0.78` — at or above this a differing project title is offered
  as a naming variation.
- `floor 0.72` — below this nothing is compared.

Consequence: `University of Dhaka` vs `National Taiwan University` are
**not** merged despite high similarity, because the differing words
(`Dhaka`, `National`, `Taiwan`) are not structural.

### C. Claims to substantiate

| ID | Name | What it flags | Limits |
|---|---|---|---|
| CLAIM-01 | Broad claim without nearby support | Phrases such as "extensive research experience", "significant leadership experience", "proven track record", "numerous publications", "led multiple projects" → *Claim to substantiate*, as a question | Requires the phrase from a small table; a rhetorical sentence is not a factual claim |
| CLAIM-02 | Broad claim with support nearby | Same phrase with a role/project/publication on the same line or within two lines → downgraded, with the support shown | Support is a word, not a judgement about it |
| CLAIM-03 | Superlative without a number | Folded into CLAIM-01's phrase table | — |

Claims are questions ("What project, role, or outcome supports this?"),
never statements that a claim is false. Evidence is never invented.

## Privacy

- **Memory only by default.** Documents live in React state. Nothing is
  persisted and nothing is sent anywhere; analysis runs entirely in the
  browser.
- **Opt-in saving.** "Save on this device" is a separate control, explained
  before the choice (mechanism: `localStorage`, stays in this browser,
  readable by anyone using this browser profile). Opting in stores review
  decisions (dismissed/reviewed finding IDs) only — **never document text**,
  which the test suite asserts.
- **Namespaced keys.** Every key this feature writes starts with
  `sz.consistencyAuditor.v1.`: `…review` and `…consent`.
- **Clear all data** removes only keys under that prefix, confirmed through
  an aria-live message, and leaves unrelated storage untouched.
- **No network.** The feature issues no fetch, XHR, sendBeacon, WebSocket or
  image request. A full user flow runs with all five channels recorded and
  asserting none of them carries document text.
- **No logging of content.** The error boundary catches, shows a safe
  message, and deliberately does not call `console.error`, a reporting
  client, or rethrow — its message contains no error text and no excerpt.
- **Plain-text rendering.** All excerpts and user text are text nodes; no
  `dangerouslySetInnerHTML`, no `eval`, no inline scripts.

### Telemetry audit (commands a reviewer should run)

```
git grep -n "sentry\|gtag\|analytics\|posthog\|logrocket" frontend/src
git grep -n "console\." frontend/src/features/consistency-auditor
git grep -n "window.onerror\|unhandledrejection\|sendBeacon" frontend/src
git grep -n "dangerouslySetInnerHTML\|eval(" frontend/src/features/consistency-auditor
```

`frontend/src` contains no telemetry or error-reporting client (the only
"analytics" matches are catalogue data fields and a CSS class name), so
there is nothing that could receive document content.

## Storage keys

| Key | Written | Contains | Removed by "Clear all data" |
|---|---|---|---|
| `sz.consistencyAuditor.v1.review` | Only after opt-in | `{dismissed: [id…], reviewed: [id…]}` | yes |
| `sz.consistencyAuditor.v1.consent` | Only after opt-in | The consent flags | yes |

Nothing else is written, and no key anywhere else is read or removed.

## Feature flag and rollback

`frontend/src/features/consistency-auditor/index.js` exports
`enabled = false` — the committed default. With it false:

- `/consistency-review` is **not registered**, so the route falls through
  to the catch-all (404);
- the "Review" navigation link is not rendered.

To disable after enabling: set `enabled = false`, or remove the single
conditional block in `App.jsx` and the block in `components/Navigation.jsx`.
There are no migrations, no database changes and no stored data to revert —
clear any namespaced keys with the "Clear all data" control.

## Adding a rule

1. Put the comparison in the right `engine/rules/*.js` (pure functions
   only, importing from `engine/normalize.js` and `engine/findings.js`).
2. Emit findings with a stable ID built from the comparison's content via
   `makeFindingId(ruleId, parts)`, one of the four categories, and a
   confidence label that describes the **text comparison**, never the truth
   of a claim.
3. Reference original offsets so excerpts are exact.
4. Document it in the table above, including its limits.
5. Add a fixture test to `engine.test.js` — including the case where the
   rule must stay silent.

## Known limitations

- **Similarity is not identity.** NAME-01/NAME-02 compare text patterns;
  two clearly different programmes with similar names can be offered as a
  variation, and the finding says so.
- **Year granularity.** Most date reasoning is at year precision; a missing
  month or day is never invented.
- **One period per line** for the overlap check (DATE-03).
- **English and Bengali only.** Other scripts' dates are not parsed; their
  text still works as plain content.
- **No external verification.** Nothing is checked against a transcript, a
  portal or the internet — the feature cannot determine whether a statement
  is true.
- **Lines longer than 8,000 characters** are not scanned for entities
  (documented in DATE-04's behaviour).
- The false-positive rate is the main cost; every finding is a prompt, not
  a verdict, and the "How this works and its limits" panel says so in the
  page.

## Tests

```
npx vitest run src/features/consistency-auditor/   # 61 tests
npx vitest run                                    # full frontend suite
npm run lint
npm run build
```

Categories covered: equivalent formats, conflicting years, precision
equality, Bengali numerals/months/calendar, naming variation vs clearly
different names, ongoing vs completed, overlap-as-question, fully matching
facts, claims as questions (with and without support), empty/whitespace/
over-limit, determinism and stable IDs, adversarial input within a time
bound, no input mutation, numeric mismatches and scales, dismiss
persistence, edit invalidation, opt-in storage, scoped clear, network
isolation, error-boundary silence, plain-text rendering, the flag being
off, and accessibility (labels, roles, aria-live, focus).

The network and logging assertions (cases 20–21) prove the behaviour of the
code paths they exercise. They are not an absolute guarantee: a future
change adding a network call or a console statement is not caught by them,
which is why the grep commands above are documented.
