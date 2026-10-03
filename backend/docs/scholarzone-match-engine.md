# ScholarZone Match 2.0

ScholarZone Match calculates how closely a student's supplied profile matches a
scholarship's **published, verified requirements**.

It is not an admissions predictor, not a probability of winning, and not a
language-model opinion. Every number it returns is arithmetic over stored facts.
There is no model in the scoring path, and no language model anywhere in the
service.

---

## 1. Architecture

```
MatchProfileRequest (POST body, never stored)
        |
        v
normalize.py      grading scales, country codes, Academic Profile Index
        |
        v
requirements.py   conservative readers for explicitly published conditions
        |
        v
eligibility.py    HARD GATE -> ELIGIBLE | NEEDS_VERIFICATION | INELIGIBLE
        |
        v
academic.py       comparison that refuses cross-scale conversion
components.py     field, funding, language, preference, timing, requirement
        |
        v
metrics.py        weighted fit, coverage, effective weights, sensitivity bracket
engine.py         orchestration + the public fit disclosure state model
readiness.py      application readiness, a third independent layer
confidence.py     record trust, computed independently of the profile
gaps.py           what could not be established, and why
actions.py        grounded next steps, derived from the gaps
profile_strength.py  how complete the student's own input is
summaries.py      every count and facet, with its reconciliation asserted
explain.py        deterministic reason codes -> fixed templates
nlp.py            optional deterministic free-text profile parser
        |
        v
MatchResponse
```

The engine is **pure**. It takes a normalised profile, a list of facts, the
engine version and an `as_of` date, and returns results. It contains no clock, no
randomness, no session and no network access. `service.py` is the only place a
database session and a calendar date enter, and both are injected.

Consequence: the same profile, the same catalogue and the same `as_of` produce a
byte-identical response.

### Module map

| Module | Responsibility |
|---|---|
| `config.py` | Every weight, band, matrix and version, validated at import. The single source of configuration truth. |
| `constants.py` | Backwards-compatible re-export of `config.py`. `validate_weight_constants()` still works. |
| `types.py` | Typed request/response contract (Pydantic v2). |
| `repository.py` | One bounded, explicit-column candidate query. SQL-side country filtering. |
| `normalize.py` | Profile normalisation, Academic Profile Index, country resolution. |
| `taxonomy.py` | Controlled programme/field taxonomy. |
| `requirements.py` | Readers for published requirements. |
| `academic.py` | Academic comparison and fit. |
| `components.py` | The remaining six dimensions. |
| `eligibility.py` | Hard gate and deadline resolution. |
| `metrics.py` | Fit arithmetic and the public fit disclosure state model. |
| `confidence.py` | Confidence score and evidence status. |
| `readiness.py` | Application readiness. |
| `profile_strength.py` | Profile completeness. |
| `gaps.py` | Gap classification. |
| `actions.py` | Grounded next steps. |
| `summaries.py` | Counting, reconciliation and facets. |
| `explain.py` | Reason codes and templates. |
| `nlp.py` | Deterministic free-text profile parser. |
| `engine.py` | The pipeline and ranking. |
| `service.py` | The impure boundary: database session and `as_of`. |

### Versioning

| Component | Version | Meaning |
|---|---|---|
| Fit engine | `2.0.0` | The pipeline and its arithmetic. |
| Scoring configuration | `2.0.0` | Weights, bands and matrices. |
| Field taxonomy | `1.0.0` | Curated programme fields and their relationships. |
| Requirement reader | `2.0.0` | The published-rule readers. |
| Deadline semantics | `1.0.0` | Inherited from the existing `deadline_semantics.py`, unmodified. |

Every response carries all five, under `explanation`. A response can be
reproduced months later because the versions that produced it are published with
it.

---

## 2. The pure engine boundary

`service.py` is the only module allowed to touch the database or the wall clock.
It resolves an `as_of` date once, loads candidates with one bounded query, and
hands both to `engine.score_record`.

Everything downstream is a function of its arguments. This is enforced by test
rather than by convention: the pure modules are source-scanned for
`date.today()`, `datetime.now()`, `time.time()`, and for any HTTP client.

---

## 3. Profile normalisation

A profile arrives in whatever shape a student could express it and is normalised
once, before scoring:

- **Academic marks** are rescaled inside their own scale. A 3.9 on a 4.0 scale
  becomes 97.5. A value outside its own scale is not interpreted; it becomes
  absent. A cross-scale reading is never attempted.
- **Letter grades** become a documented band, never a number.
- **Countries** resolve to ISO codes case-insensitively with surrounding
  whitespace ignored. A phrase like "Nordic" or "developing countries" is not a
  country and resolves to nothing.
- **Degrees** resolve against the curated list.
- **The Academic Profile Index** summarises the academic evidence the student
  supplied. It is not a measure of ability, and it is not an admission
  prediction.

---

## 4. Eligibility

The gate runs **before any scoring function** and is never passed a fit score.
That is structural: `evaluate()` and `evaluate_deadline()` accept no score
argument at all, so no sequence of edits can make the gate depend on fit.

Three verdicts:

| Verdict | Meaning |
|---|---|
| `ELIGIBLE` | Every published mandatory condition was evaluated and satisfied. |
| `NEEDS_VERIFICATION` | A published mandatory condition could not be checked against the profile. |
| `INELIGIBLE` | At least one published mandatory condition is confirmed not met. |

**Silence is not a rule.** A record that publishes nothing produces no
conditions, no blockers and no unverified items. A missing national field against
a published citizenship rule is unverified, never a failure.

Conditions are checked in a fixed, published order:

1. application window
2. academic minimum
3. language minimum
4. nationality
5. age
6. degree level
7. programme restriction
8. study mode

Every outcome preserves the awarding body's own wording: the `raw_quote` and the
`provenance_url` travel with the verdict.

### The three states and the fit disclosure

The fit arithmetic and the fit *disclosure* are one explicit state model in
`metrics.resolve_public_fit`. There are exactly three states:

| Eligibility | `fit_score` | `fit_label` |
|---|---|---|
| `INELIGIBLE` | `null` | `INELIGIBLE` |
| `NEEDS_VERIFICATION` | the score, if any | the band, if any |
| `ELIGIBLE` | the score, if any | the band, if any |

An ineligible record publishes **no** fit score and **no** fit band. A high
number there would read as a recommendation the gate has already refused.

A `NEEDS_VERIFICATION` record keeps its deterministic score and its band, because
that verdict is a statement about our evidence, not about the student's fit.
Withholding a real measurement would hide it, and composing the label into a
second key would break fit-band and facet lookup. Eligibility is reported
separately on every result and stays visible.

The raw arithmetic behind an ineligible result stays internal to
`PublicFit.internal_fit_score`. It is **not** on `MatchResult` and never appears
in a response, because a raw number beside a refused result invites a client to
keep ranking on it.

`fit_label` is always one of the five configured band keys, `INELIGIBLE` or
`NOT_EVALUATED`. Never a composed string.

---

## 5. Fit mathematics

### Weights

| Component | Weight |
|---|---|
| Academic | 25% |
| Field / programme | 20% |
| Funding | 20% |
| Requirements | 15% |
| Language | 10% |
| Preference | 5% |
| Timing | 5% |
| **Total** | **100%** |

A weight table that does not total exactly 1.0 raises at import time. It is never
silently rescaled, because rescaling would change every score in the product
without changing a line of the configuration.

### The formula

```
fit = SUM(weight x score) / SUM(weight)      over EVALUATED components only
```

An unevaluated component is excluded from **both** halves of the fraction.
Including it in the denominator would inflate the score; treating it as zero
would deflate it. Neither is right, because "we could not measure this" and
"this measured zero" are different facts.

If no component can be evaluated, `fit_score` is `null`. Never 0.

### Coverage

```
coverage = SUM(weight of evaluated components) x 100
```

Coverage is how much of the configured model was measurable. It is reported
separately from the score, because a score of 90 measured on 45% of the model is
a different statement from a score of 90 measured on all of it.

### Effective weights and contributions

When anything is excluded, the configured weight is not what the arithmetic
actually applied:

```
effective_weight = configured_weight / SUM(weights of evaluated components)
contribution     = effective_weight x score
```

Contributions sum to the published score. Reporting "Academic is 25%" next to
"Academic scored 96" would otherwise imply 24 points the average never contained.

Only the final presentation is rounded, to one decimal. Nothing is rounded
intermediately.

### Fit bands

| Score | Band |
|---|---|
| 90–100 | Exceptional Fit |
| 80–89.9 | Very Strong Fit |
| 70–79.9 | Strong Fit |
| 55–69.9 | Possible Fit |
| 0–54.9 | Low Fit |

### Sensitivity range

When anything is unevaluated, the engine publishes the bracket that the
unevaluated weight implies:

```
lower = (N + 0   x U) / SUM(configured weights)
upper = (N + 100 x U) / SUM(configured weights)
```

with `N` the weighted numerator over evaluated components and `U` the
unevaluated weight. Both bounds are on the same 0–100 scale as the score, and the
range always carries its caveat: *mathematical sensitivity range, not a
prediction*. It is never used for ranking.

---

## 6. Academic comparison

Only a like-for-like comparison is attempted.

- Same scale → compared directly.
- Different scales → `INCOMPARABLE`. No conversion, no score. A published GPA
  minimum is never compared with a percentage result, or with a 5-point scale.
- A minimum without a declared scale is not interpretable, and is refused.
- A missing student mark is `STUDENT_MARK_UNKNOWN`, not a failure.

**Two published anchors.** When a record publishes both a minimum and a
preferred value:

```
score = 100 x (student - minimum) / (preferred - minimum), clamped 0–100
```

**One anchor.** When only a minimum is published, meeting it earns the documented
**85**. No second anchor is invented, so meeting the minimum and exceeding it
cannot both score 85 with no published way to tell them apart.

Cross-scale letter-grade conversion is refused for the same reason: no official
conversion exists.

---

## 7. Field taxonomy

A controlled, versioned taxonomy with curated relationships:

| Relationship | Score |
|---|---|
| `EXACT` | 100 |
| `CLOSE_SPECIALIZATION` | 85 |
| `RELATED_FIELD` | 65 |
| `BROAD_FIELD` | 40 |
| `UNRELATED` | 0 |

Aliases are matched longest-first, so `informatics science` resolves to
`information_science` and `informatics` to `computer_science`. Short aliases
match on word boundaries only, so `cs` matches but `scholarship` does not.

A scholarship's field is read from `program_type` first, then `official_details`,
then `degree`. The structured column outranks the free-form JSON blob, because
`program_type` is what the research pipeline writes the programme into.

**Prose is never used to invent a field.** The title and eligibility text are not
consulted, and a degree word is not a subject: `Master` and `PhD` do not resolve
to a field.

A record whose programme the taxonomy cannot resolve is simply not scored on
that dimension, and is absent from the field facet rather than filed under an
invented subject.

---

## 8. Funding matrix

Funding states are derived from evidence, in this order:

1. Explicit tuition and living-cost coverage columns.
2. An explicit published statement of no funding.
3. A monetary award with no coverage detail → `PARTIAL`.
4. Anything else → `UNKNOWN`.

`fully_funded` is never the evidence. It is a `NOT NULL` column with a false
default, so a false value is an unknown, not a "no". When a record has no
coverage detail, the flag can corroborate a derived state but cannot establish
one on its own, and the response records that distinction.

**`UNKNOWN` is never `NONE`.** An unestablished funding structure is not scored at
all, and is reported as unknown. The student is not penalised for a gap in our
catalogue.

Compatibility is a configured matrix, not a decision tree in the code:

| Student's need | FULL | TUITION_PLUS_LIVING | TUITION_ONLY | PARTIAL | NONE |
|---|---|---|---|---|---|
| Full funding | 100 | high | partial | low | 0 |
| Tuition covered | 100 | 100 | 100 | lower | 0 |
| Partial acceptable | 100 | 100 | 100 | 100 | 0 |
| No stated need | full | full | full | partial | reduced |

Funding **state** is never an eligibility rule. It only affects the funding fit
dimension.

---

## 9. Language

Only the same test is ever compared. Cross-test equivalency is not supported and
is not attempted: a TOEFL score never satisfies an IELTS requirement.

```
score = 100 x clamp((student - published minimum) / configured surplus range, 0, 1)
```

The surplus range is the documented headroom for that test, not a target:

| Test | Surplus range |
|---|---|
| IELTS | 2.0 |
| TOEFL | 15.0 |
| PTE | 10.0 |

So IELTS 6.5 against a 6.5 minimum scores 0, IELTS 7.5 scores 50, and IELTS 8.5
or above scores 100.

Meeting the minimum exactly is **not** full marks. The requirement is a floor,
not a target, and the floor earns nothing above itself.

A score below the minimum is a real, evaluated zero. A missing student credential,
a test with no documented range, and a missing published requirement are all
reported as not evaluated or as a stated exemption, and are never treated as a
failure.

---

## 10. Requirements

The requirement dimension scores the applicant's burden of satisfying published
conditions: documented document lists and other conditions the record publishes.

**Hard eligibility rules are not counted here.** Nationality, academic minimum,
language minimum, degree level, programme restriction, study mode and the
application window belong to the gate. Counting them again would double-count a
rule that has already been decided.

**Prose never becomes a requirement.** A reader only extracts a condition from an
explicit marker. A comparative phrase like "preference will be given to" is not a
mandatory gate. "Applicants must be" on its own is not a study-mode condition.

A condition the reader cannot classify is counted as an unknown condition: it
lowers measured precision, and it never fails the student.

---

## 11. Preference

Preferring a country is not an eligibility rule. A student who did not ask for a
country still gets a scored result, and a preference only changes the preference
dimension.

Preference is a configured lookup, not a similarity function. An unresolvable
country on either side is reported as not evaluated rather than as a mismatch,
because guessing a relationship ScholarZone does not publish would be inventing
data.

---

## 12. Timing

Timing reuses the existing `deadline_semantics.py`, unmodified. That module
resolves what a deadline means; Match consumes its resolution rather than
reinterpreting the text.

| Days remaining | Score | Bucket |
|---|---|---|
| 60+ | 100 | Comfortable |
| 30–59 | 90 | Approaching |
| 14–29 | 75 | Approach soon |
| 7–13 | 55 | Closing soon |
| 1–6 | 30 | Urgent |

A closed round, a rolling or annual deadline, and an unpublished deadline are all
**not evaluated**. None of them is zero, and none of them is treated as an
absence of urgency.

Month-precision deadlines are measured to the end of the month and flagged as
approximate.

---

## 13. Confidence

Confidence describes the **scholarship record**, not the applicant. It is
computed with no reference to the profile, so no profile can raise or lower it.

```
confidence = 35% data completeness
           + 25% provenance quality
           + 25% requirement explicitness
           + 15% verification freshness
```

| Days since verified | Freshness |
|---|---|
| ≤ 90 | 1.00 |
| ≤ 180 | 0.75 |
| ≤ 365 | 0.50 |
| ≤ 730 | 0.25 |
| beyond, or unknown | 0.00 |

There is no floor for an ancient record. Unbounded credit for evidence nobody
refreshed is not credit at all.

Bands: `HIGH` ≥ 85, `MEDIUM` ≥ 65, `LOW` below.

Confidence is **not** multiplied by fit, and fit is not multiplied by confidence.
They are independent measurements, and a product of them would say something
neither one supports.

---

## 14. Readiness

Readiness answers a third, separate question: how much of this application can
you act on today?

| Component | Weight |
|---|---|
| Eligibility certainty | 30% |
| Requirement completeness | 20% |
| Language readiness | 15% |
| Application readiness | 15% |
| Deadline readiness | 20% |

An unevaluated dimension is excluded and the remaining weights are renormalised.
If nothing can be evaluated, readiness is `null`, not 0.

An ineligible record has no application to be ready for, so its eligibility
certainty is a real zero and the copy says so.

---

## 15. Profile strength

Profile strength describes how complete the **student's own input** is. It is
explicitly neither fit nor confidence.

| Group | Weight |
|---|---|
| Academic | 25% |
| Study goal | 25% |
| Language | 20% |
| Funding | 20% |
| Identity | 10% |

Two students with an identical profile strength can have completely different
matches, and a strong profile does not make any particular scholarship a better
match.

Missing groups produce concrete, non-punitive suggestions. Nothing is ever marked
complete without evidence.

---

## 16. Reason codes, gaps and actions

### Reason codes

Every explanation is a stable code rendered through a fixed template. No text is
generated by a language model, so the same inputs always produce the same
sentences.

### Gap categories

| Category | Meaning |
|---|---|
| `KNOWN_GAP` | A published rule exists and cannot be checked. |
| `UNVERIFIED` | A published rule nobody has checked yet. |
| `MISSING_USER_INFORMATION` | The student has not supplied something. |
| `MISSING_SCHOLARSHIP_DATA` | A gap in our catalogue. No student action changes it. |

Separating these is what stops missing data being written up as a failure.
"Language requirement not evaluated" is a statement about measurement; "you are
not eligible" is a statement about the student, and only the gate is allowed to
make that one.

An unknown gap code still renders, with the code as its text. A gap the engine
has no template for is visible rather than silently dropped.

### Actions

Actions are derived from the gaps that actually occurred and are ordered by
consequence. A blocking condition comes first; "visit the official source" comes
last, and only when a URL was actually published.

**A document is never named unless the record names it**, and a task is never
marked complete without evidence.

---

## 17. Counting

Two candidate sets exist in a response, and every count names which one it
describes.

**The analysed universe.** Every candidate scored and gated, before the response
was truncated. `total_candidates` is its size, and every summary count reconciles
against it:

```
eligible + needs_verification + ineligible == total_candidates
scored     + not_scored                == total_candidates
sum(fit tiers) + unclassified           == scored_count
sum(confidence buckets)                == total_candidates
sum(coverage buckets)                  == total_candidates
sum(deadline buckets)                  == total_candidates
sum(funding buckets)                   == total_candidates
```

`visible_candidate_count` names the page separately, so the interface never
implies the reader is looking at the whole analysis when they are not.

**The returned page.** The ranked subset actually returned. Facet counts are
built from this set, because a filter's count must never be stale relative to the
list it filters: offering "Germany (27)" has to mean twenty-seven cards are one
click away. `MatchFacets.count_basis` records this explicitly.

`assert_reconciled` raises on any violation rather than returning a dashboard that
disagrees with itself. A count that does not reconcile is a bug, and the correct
response to a bug is to fail loudly.

`include_ineligible: false` removes records from the analysed universe rather
than scoring and hiding them, so the three states still sum to the total.

Facet values are never truncated, and a label is the published string verbatim.
Country names and degree strings are already written for a reader; restyling them
would restyle text ScholarZone did not author.

---

## 18. Ranking

The order is total, so the same profile always produces the same sequence:

1. eligibility state, `ELIGIBLE` → `NEEDS_VERIFICATION` → `INELIGIBLE`
2. fit score, descending
3. confidence, descending
4. coverage, descending
5. deadline relevance
6. `scholarship_id`, ascending

An ineligible record cannot outrank a valid one because its raw arithmetic is not
in the public contract at all.

---

## 19. Determinism

Identical inputs produce identical output. This is a design constraint with teeth:

- no clock inside the engine; `as_of` is injected
- no randomness
- no network access in the scoring path
- no model-generated text anywhere
- no language model in the natural-language parser, which is a curated table
  lookup
- ranking has a final tiebreak on a stable key

---

## 20. Privacy

The profile is sent in the POST body, so a student's nationality, age and academic
record never reach an access log or a `Referer` header. It is not stored
server-side, no account is required, and the response never echoes the applicant
age. The optional free-text parser keeps nothing: it returns an interpretation
for the student to confirm, and it writes no records.

---

## 21. API

| Endpoint | Purpose |
|---|---|
| `POST /api/scholarships/match` | Score a profile. Resolves under `/scholarships/match` too. |
| `GET /api/scholarships/match/profile-options` | Curated options for the form. |
| `POST /api/scholarships/match/parse-profile` | Optional deterministic free-text interpretation. |

Requests are strictly validated: unknown properties are rejected rather than
ignored, and an out-of-range value is a 422 rather than a silently clamped one.

### The free-text parser

Optional, deterministic, and local to ScholarZone. It matches the text against
approved lists and reports back both what it understood, with the exact phrase it
matched, and what it could **not** resolve. It never calculates anything: the
interface fills in the form and the student confirms or edits before a score is
requested.

Uncertain values are not silently turned into facts. A country that is not in
ScholarZone's list is reported as unresolvable rather than guessed.

---

## 22. Performance

- One bounded query with explicit columns. No N+1, no lazy loading.
- SQL-side country filtering.
- `public_visibility_conditions()` is reused, so Match can never surface a record
  the directory hides.
- Scoring is O(n) over candidates.
- No cache, no Redis, no new external service.

---

## 23. Known limitations

These are real and deliberately not "improved" by guessing:

- `program_type` is missing on many records, so field alignment is honestly
  unevaluated for them.
- Structured funding columns are sparse, so funding coverage is unknown more
  often than not.
- Missing data reduces coverage. It never becomes a zero.
- A record that publishes no rule cannot be verified against one.
- Country filters and facets are English-only.

The response reports what it does not know on every result. That is the point.

---

## 24. Tests

| Suite | Covers |
|---|---|
| `test_matching_engine.py` | Pipeline behaviour and invariants. |
| `test_matching_taxonomy.py` | Aliases, collisions and field relationships. |
| `test_matching_api.py` | HTTP contract, visibility, CORS, parsing, counting. |
| `test_matching_v2.py` | The Match 2.0 contract: arithmetic, bands, every dimension, the disclosure state model, counting, facets, ranking, the parser and the request contract. |