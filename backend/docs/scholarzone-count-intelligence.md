# ScholarZone Count Intelligence 2.0

The canonical source of truth for every business-facing number in ScholarZone.

This layer **counts**. It never scores. The Match engine decides whether a student
is eligible and how well a scholarship fits; this layer measures the results and
publishes them so they can be checked.

The governing rule, and everything else follows from it:

> **Exact when possible. Approximate only when necessary. Predictive only when the
> evidence supports it. Never invent a number.**

---

## 1. Architecture

### 1.1 The dividing line

| | Match engine | Count intelligence |
|---|---|---|
| Decides | eligibility, fit, confidence, coverage, readiness, ranking | partitions, counts, facets, reconciliation, provenance |
| Input | profile + published record facts | the engine's finished results, or stored rows |
| Output | a verdict and a score, with evidence | counts of those verdicts, with provenance |

The counting layer has no opinion about a student's fit. It cannot acquire one: its
predicates come from a declarative contract, and it reads the engine's published
fields rather than re-deriving them.

### 1.2 One contract, two consumers

`app/services/counting/contract.py` is the single authoritative definition of every
count. Every metric declares nine things:

```
name                the stable identifier
universe            which population it counts
predicate           a deterministic function of one record
partition_type      COMPLETE / PARTIAL / NOT_A_PARTITION
null_policy         what happens when a value is absent
unknown_policy      how a known-unknown is handled
as_of_dependency    can this change purely because the date moved?
engine_dependency   which engines it depends on
version_dependency  which versions invalidate a stored copy
```

**The Match engine builds its summary from this contract.**
`app/services/matching/summaries.py` maps bucket keys onto the published
`MatchSummary` field names, and takes its predicates from here. A bucket with no
response field, or a field the contract does not declare, raises at import rather
than silently dropping a number. That is what stops the Match response and the
intelligence response from drifting apart, and it is asserted by test.

### 1.3 Module map

```
backend/app/services/counting/
  types.py           The typed contract: universes, partitions, provenance, integrity
  contract.py        The declarative definitions everything else reads
  core.py            The counting engine: count, partition, reconcile, aggregate
  facets.py          Facets, filter semantics, self-exclusion, reset identity
  counterfactual.py  One controlled change at a time; zero-result intelligence
  catalogue.py       Catalogue-universe counts, in one query
  temporal.py        Snapshot and trend support on existing stored history
  anomalies.py       Evidence-based anomaly detection; the integrity monitor
  relationships.py   Counts over verified and published relationships
  incremental.py     Change classification, with a full-recompute fallback
  provenance.py      Reproduction metadata and count explanation
  service.py         The impure boundary: session, as_of, one assembled response

backend/app/routers/counts.py   POST /v2/counts/intelligence, GET /v2/counts/contract
```

### 1.4 Pipeline

```
Canonical candidate set
    ↓
Predicate evaluation        (from the contract, never re-declared)
    ↓
Partition / bucket counting (single pass)
    ↓
Facet aggregation           (self-exclusion, one set per facet)
    ↓
Reconciliation              (asserted, and published)
    ↓
One API response
```

The counting engine knows nothing about HTTP, SQL or presentation.

---

## 2. The three universes

Never merged. Every count names the set it describes, because a catalogue total
presented where a Match total was expected is how a dashboard starts lying.

| Universe | What it is | Produced by |
|---|---|---|
| `CATALOGUE` | The canonical public catalogue | `catalogue.catalogue_counts`, over the directory's `public_visibility_conditions` |
| `SEARCH_FILTER` | The catalogue after the directory's search and filter predicates | `repositories.scholarships.list_scholarships` |
| `MATCH_ANALYSED` | Candidates Match 2.0 loaded, scored and gated for one profile | `core.count_all_partitions` over the engine's results |
| `MATCH_RETURNED_PAGE` | The truncated page — the basis facets describe | `facets.build_facets` |

`UNIVERSE_PRODUCERS` in `contract.py` binds each universe to the module that
produces it. An unreferenced universe would be a naming convention; this is a
binding.

**Summary counts describe the analysed universe. Facet counts describe the returned
page.** Both are named in every response via `count_basis`.

---

## 3. The count contract

Published in full at `GET /v2/counts/contract`, so any consumer can check a number
against the definition it claims to satisfy without reading the source.

`COUNT_CONTRACT_VERSION = "2.0.0"`, bumped whenever any metric definition,
predicate or partition changes. A count that moves under an unchanged contract
version is the failure the version exists to prevent.

Eleven partitions, 54 metrics. Validated at import: a duplicate metric name, a
repeated bucket key, a COMPLETE partition with no buckets, or a bucket with no
metric all raise at startup rather than producing a number nobody can reconcile.

### 3.1 Partitions

| Partition | Universe | Type | Reconciles against |
|---|---|---|---|
| `eligibility` | MATCH_ANALYSED | COMPLETE | universe |
| `scored` | MATCH_ANALYSED | COMPLETE | universe |
| `fit_tier` | MATCH_ANALYSED | COMPLETE | **scored** |
| `confidence` | MATCH_ANALYSED | COMPLETE | universe |
| `coverage` | MATCH_ANALYSED | COMPLETE | universe |
| `readiness` | MATCH_ANALYSED | COMPLETE | universe |
| `funding` | MATCH_ANALYSED | COMPLETE | universe |
| `deadline` | MATCH_ANALYSED | COMPLETE | universe |
| `deadline_precision` | MATCH_ANALYSED | COMPLETE | universe |
| `lifecycle_status` | CATALOGUE | COMPLETE | public total |
| `catalogue_evidence` | CATALOGUE | **NOT_A_PARTITION** | nothing, by design |

**Why the fit tiers reconcile against `scored_count` and not `total_candidates`.**
An unscored record has no tier by definition — it was refused by the gate, or
nothing could be evaluated for it. Reconciling tiers against the total would require
inventing a "no tier" bucket for every unscored record and would misdescribe what a
tier is. The contract records this as `reconciles_against="SCORED"` and the counting
engine reads it from there rather than hardcoding it.

**Why `catalogue_evidence` is not a partition.** A record can be verified *and* have
no image. Both claims are true, so the sum means nothing and no identity is asserted
for it.

### 3.2 Null and unknown policy

Every metric publishes both, and the default is `EXCLUDED_AND_REPORTED`: an absent
value is an absence, never silently counted as the lowest bucket, and the number of
absences is itself published.

`unknown` is a separate question from `null`, and conflating them is the most
common way a counting layer starts lying:

| | Meaning | Published as |
|---|---|---|
| `null` | no value exists | excluded, and the exclusion counted |
| `unknown` | a known-unknown: evidence exists and it is inconclusive | its own bucket |

Concretely: `funding_state == UNKNOWN` means no verified coverage detail was found.
`NONE` means the record states no funding is offered. Collapsing them would report a
finding ScholarZone never made. The test suite asserts the two stay distinct.

---

## 4. Catalogue counts

Computed in **one query**, not one per figure. The previous implementation of
`GET /scholarships/stats` issued nine separate `COUNT` queries, each re-deriving the
visibility predicate, and the homepage ran all nine on every load. It now delegates
to `catalogue.catalogue_counts`; the response contract is unchanged.

The visibility predicate is **not reimplemented** — `public_visibility_conditions`
is the directory's own definition and is reused verbatim.

Two bases are counted on purpose:

- `CATALOGUE` — what a visitor can see. Excludes quarantined and archived rows.
- Row totals — what exists in storage, including archived and quarantined. An
  archived count *cannot* come from the public predicate, because that predicate is
  exactly what hides archived rows.

Only states the schema can express are reported. `other` is a published lifecycle
bucket rather than a silent drop, so an unexpected status stays visible.

---

## 5. Match counts and the mandatory invariants

```
eligible_count + needs_verification_count + ineligible_count = total_candidates
scored_count   + not_scored_count                            = total_candidates
fit tiers + unclassified                                       = scored_count
```

These are not comments. `core.reconcile` builds them as data, `core.integrity` grades
them, and `core.assert_integrity` raises on a contradiction. A partial universe is
never produced silently: `include_ineligible=false` names the universe it produced.

---

## 6. Facets

Eleven families: `countries`, `regions`, `degree_levels`, `fields`,
`funding_states`, `eligibility_states`, `fit_bands`, `confidence_bands`,
`coverage_bands`, `readiness_bands`, `deadline_buckets`.

Every bucket is `key`, `label`, `count`.

### 6.1 Self-exclusion

> Each facet counts records matching every active filter **except its own
> dimension**. A facet therefore still offers alternative values while one of its own
> values is selected. `count_basis` names the set each count describes.

Without this, committing to "Germany" makes every other country invisible — exactly
when the reader needs them. Published verbatim in every facet response as
`SELF_EXCLUSION_SEMANTICS`, because the semantics are part of the contract rather
than an implementation detail.

Self-exclusion is **surgical**. Selecting country *and* degree means the country
facet still respects the degree filter; only the country's own predicate is removed.
Under self-exclusion each family describes a different candidate set, so
reconciliation is checked per family against the set that family actually used.

### 6.2 Labels are never derived from keys

A country and a degree are already written for a reader. Echoing them exactly is both
more correct and more honest about where the wording came from. Title-casing a
published string turns `"Bachelor's, Master's"` into `"Bachelor'S, Master'S"` and
`"PhD"` into `"Phd"`. The field facet's label comes from the taxonomy's own label.

### 6.3 No truncation, no invention

A country present in the catalogue is always offerable. A **region** appears only
where the curated mapping places the country in *exactly one* region — Mexico is in
both North America and Latin America, so it is absent rather than assigned to
either. A **field** appears only where the taxonomy resolved one; a programme the
taxonomy cannot resolve is absent, never filed under a subject ScholarZone chose.

### 6.4 Reset integrity

`FilterState.fingerprint()` is an order-independent identity for a filter state.
Selecting Germany then France, and France then Germany, constrain exactly the same
records and therefore share a fingerprint. A reset restores the same candidate ids,
counts, facets, ordering and `as_of` context as the initial request.

---

## 7. Zero-result intelligence

When the active filters produce nothing, the response offers deterministic one-change
alternatives:

```
Remove "Country"  → 5 results
```

Three rules:

1. **Exactly one dimension changes.** Every other active predicate is retained, so
   the alternative's count is attributable.
2. **Nothing is invented.** An alternative is published only if applying the change
   actually produces results. A state where every change leads to zero returns an
   empty list rather than a list of dead ends.
3. **The reader's state is never mutated.** Every counterfactual is computed on a
   copy.

**This replaced a client-side implementation.** The frontend used to count
alternatives in the browser by dropping one filter at a time and counting the
surviving rows. That was wrong twice over: it counted the *rendered page* rather than
the analysed universe, so a truncated response offered counts the API never
confirmed; and it could only ever relax a filter, so it could never offer the change
that actually helps — adding a related field, or widening a country preference.

---

## 8. Counterfactual counting

`baseline_count`, `counterfactual_count`, `delta`, `changed_dimension`,
`baseline_state`, `counterfactual_state`, `value_kind="SIMULATED"`.

One intervention at a time, over the same candidate universe, recomputed with the
same logic. The caller's filter state is untouched and asserted by test.

**This is deterministic recomputation, not causal inference.** The delta is the
difference between two counts of one universe under two stated conditions. It is
never a causal effect, a treatment effect, a probability, or an expected admission
increase. The disclaimer travels in the payload rather than relying on every caller
to remember it.

---

## 9. Incremental counting

The abstraction is a **classification step**, not an optimisation.

```
plan_increments(changes, partitions) -> strategy, updated, recomputed, increments
```

A change is only applied incrementally when it is *provably* local: one record, one
dimension, no other partition affected. Full recomputation is the default, and it is
published as `FULL_RECOMPUTE` — a success state naming what it did, not an admission
of failure.

`INTERACTING_CHANGES` are the kinds that force a recomputation, and the reasons are
structural rather than cautious. A deadline change moves the timing bucket *and* how
many days remain, which moves eligibility at the gate. Funding, eligibility-evidence
and field changes move the gate itself, which moves three partitions at once. A batch
of more than one change is recomputed because ruling out interactions between them
costs more than recomputing.

`apply_plan` refuses to publish a recomputation without its figures.

**No persistent counters.** No table, no migration, no state that can survive a
restart and disagree with the data it describes. No Redis.

---

## 10. Time, snapshots and trends

**No schema change was needed.** `scholarship_snapshots` already carries
`valid_from`, `valid_to`, `is_current` and `version_id`, and
`temporal_versioning` owns the read and write paths. Point-in-time counting reads
what is there; reconstruction is delegated to the existing `get_state_at` so there is
one answer to "what did this record look like then".

### 10.1 History is never fabricated

> If the historical state does not exist, the answer is `NOT_AVAILABLE`.

This is not caution for its own sake. A snapshot table only has rows for records
*changed* after the feature existed. Asking for the catalogue as it stood in 2024 and
finding nothing yields two indistinguishable truths — "the catalogue was empty" and
"we were not recording". Publishing a trend across them would be a straight line of
invented history presented with the authority of a measurement.

### 10.2 A trend needs three points

One point is a measurement; two are a change. Neither is a trend, and drawing a line
through them reads as a direction the evidence does not establish. Fewer than three
distinct observations returns `NOT_AVAILABLE`.

Snapshots are written *on change*, so several can share a day. Points on the same day
collapse to one, because a burst of edits is one moment in time — otherwise a busy
afternoon renders as a month of trend.

Every point is labelled `is_historical`. Nothing is interpolated, smoothed or
modelled.

---

## 11. Anomaly detection and integrity monitoring

### 11.1 Integrity is a first-class result

| Status | Meaning |
|---|---|
| `PASS` | every asserted identity holds |
| `WARNING` | counts are internally sound, but some declared evidence was unavailable |
| `FAIL` | the counts contradict each other and must not be displayed as coherent |

`WARNING` and `FAIL` are kept distinct on purpose: a reader is never told a number is
trustworthy when the honest answer is "true, but I could not see part of the
catalogue". `assert_integrity` lets `WARNING` through — refusing to publish honest
incomplete counts would be the wrong trade — and raises only on `FAIL`.

### 11.2 Detection order

`RECONCILIATION` → `IMPOSSIBLE_VALUE` → `ROLLING_BASELINE` → `FACET_IMBALANCE`. A
set of counts that do not add up needs no further investigation to be untrustworthy.

### 11.3 The thresholds are two floors, not one rate

```python
min_absolute_delta   = 5      # ignore a change this small, whatever the rate
min_relative_delta   = 0.25   # ignore a change this small, whatever the size
min_baseline_points  = 3
spike_deviations     = 3.0
facet_imbalance_ratio    = 0.95
degenerate_facet_ratio   = 0.99
negligible_bucket_ratio  = 0.01
```

A percentage rule alone flags 2 → 6 as a 200% rise in a small catalogue, every time,
which trains everyone to ignore the detector. An absolute floor alone misses a
catalogue losing four records. Both must hold.

### 11.4 No machine learning

With a catalogue this size, a z-score over three observations is a mathematical
artefact wearing a lab coat. Not because ML is bad, but because it would produce
confident output about a problem the data cannot describe.

`is_baseline_available=False` means "not enough evidence to say", which is published
differently from "no anomaly".

Anomaly *severity* reuses the existing `app.services.anomaly_detection.AnomalySeverity`
vocabulary rather than introducing a second scale.

---

## 12. Relationship counting

Built on the existing relational data. **No graph database.** Two evidence classes,
never merged:

| Class | Source | `is_verified` |
|---|---|---|
| `VERIFIED_EDGE` | a row in `knowledge_edges` with a verified status | `true` |
| `PUBLISHED_FIELD_MATCH` | two records sharing an identical value in a structured column | `false` |

The distinction is about provenance, not capability. Two records sharing a funding
*string* is evidence they describe funding the same way; it is **not** evidence they
share a legal funder, and `is_verified=false` says exactly that. A relationship is
never inferred from name similarity.

Related-programme suggestions read the taxonomy's curated `close` / `related` tuples,
so a proposed field is one ScholarZone has a documented opinion about.

**No centrality or community detection.** The relationship graph is sparse, and a
centrality score over three verified edges is a number that looks like insight and is
not. `graph_density` is published so a reader can see how thin the graph is.

Singletons are not published: a "cluster" of one tells a reader nothing.

---

## 13. Provenance and explanation

Every response carries `count_basis`, `universe`, `filter_state`, `as_of`,
`as_of_dependency`, `count_contract_version`, `engine_version`,
`scoring_config_version`, `field_taxonomy_version`, `deadline_semantics_version`,
`depends_on` and `value_kinds`.

`as_of` is only populated where the count genuinely depends on the date. A catalogue
count is not a function of today, and stamping today's date on it would imply a
history it does not have.

**Value kinds are never summed across.** `OBSERVED`, `DERIVED`, `SIMULATED`,
`HISTORICAL`, `UNAVAILABLE`. A catalogue count read from stored rows and a
counterfactual recomputed under a hypothetical change are both integers, and adding
them would produce a number meaning nothing.

### 13.1 Explanation

Both forms, assembled from the same clause list so they cannot disagree:

```
213 = analysed scholarships AND eligibility = "ELIGIBLE"
      as_of = 2026-10-03   engine = 2.0.0   count contract = 2.0.0
```

`clauses` is the machine-readable form — ordered `(dimension, operator, value)`
triples — so the count can be recomputed rather than believed.

---

## 14. The API

### `POST /v2/counts/intelligence`

One endpoint, not a dozen narrow ones. A reader asking "how many, and where did that
number come from" should not need eight requests and have to reconcile the answers.
Results, summary, facets, integrity, provenance, counterfactuals and relationships
come back in one response, computed in one pass over one candidate set.

```jsonc
{
  "profile": { /* the same body POST /scholarships/match accepts, optional */ },
  "filters": { "countries": ["Germany"], "funding": ["FULL"] },
  "capabilities": ["summary", "facets", "integrity", "explain",
                   "zero_result", "counterfactual", "catalogue", "snapshot",
                   "trends", "relationships", "incremental", "distributions"]
}
```

`extra="forbid"` on both nested models, and capabilities are validated by a
`field_validator`, so an unknown field or capability is a **422** — a malformed
request — rather than a 500 implying the server broke.

`as_of` is a query parameter, so a count can be reproduced exactly.

### `GET /v2/counts/contract`

The complete contract: every partition, bucket, universe, producer, note and
dependency, plus the self-exclusion semantics and the filter vocabulary.

---

## 15. Frontend semantics

### 15.1 The authority rule

**Business counts come from the API.** There is no `results.filter(...).length` for
any number a reader sees.

The frontend may filter a list to decide which cards to render — that is rendering.
Deciding how many scholarships exist in a country is the counting engine's job, and
reimplementing it in the browser is how a facet badge and a result count drift apart
by one.

`matchFilterConfig.alternativesFor` no longer computes anything. It maps the API's
answer into the shape the empty state renders.

### 15.2 No stale counts

`useCountIntelligence` tags every response with the id of the request that produced
it and discards any response for a superseded filter state. Without that guard, a
slow response lands after the reader has moved on and paints "Germany (5)" above a
list of forty cards.

The inactive and loading states are **derived**, not stored. Storing them means
calling `setState` inside the effect body, forcing a second render pass on every
reset, to produce state that was a function of the props anyway.

With nothing filtered the hook makes **no request at all** — the Match response
already carries authoritative counts, so there is nothing to ask for.

### 15.3 A failed count is not a zero

An error is reported as an error, in both the hook and `CountAnalytics`. Falling
back to counting the rendered list would produce a confident number nobody can audit.

### 15.4 UX layering

- **Default screen:** plain language. "36 of 71 analysed scholarships meet the
  published conditions for this profile."
- **Collapsed:** distributions with their sample sizes and caveats.
- **Expanded:** why the number is what it is; where it came from; the integrity
  verdict and its issues; every version.

Technical complexity is never forced onto the first screen.

---

## 16. Accessibility

- Every count is a readable number, with literal `N/A` or "Not measured" rather
  than an icon. An average over no records reads "Not measured", never `0`.
- No information is colour-only; the integrity verdict is a word.
- `<details>`/`<summary>` for every disclosure — keyboard accessible natively.
- `role="status" aria-live="polite"` on the count update line.
- The distributions table has a `<caption>` and `scope` attributes.
- Reduced motion respected; the panel adds no animation of its own.

---

## 17. Performance

| Rule | How it is met |
|---|---|
| One bounded query | `catalogue_counts` is one `SELECT` with conditional aggregates |
| No N+1 | one candidate set held in memory; every facet derived from it |
| O(n) aggregation | single pass per partition |
| No per-facet query explosion | 11 facets, one candidate set, zero extra queries |
| One response | results + summary + facets + integrity + provenance together |

Predicate lists are resolved from the contract once and cached per partition name.

No cache was added. No Redis. No memoization of user-specific data. Nothing here is
worth a cache until a benchmark says so.

---

## 18. Tests

| File | Covers |
|---|---|
| `backend/tests/test_counting_core.py` | the contract, partitions, reconciliation, distributions |
| `backend/tests/test_counting_facets.py` | facets, self-exclusion, filter composition, reset, region mapping |
| `backend/tests/test_counting_intelligence.py` | counterfactuals, zero-result, anomalies, time, incremental, relationships, provenance |
| `backend/tests/test_counting_api.py` | the HTTP surface, plus Match 2.0 regression |

They reuse `make_facts` / `strong_profile` from `test_matching_v2` rather than
declaring a second database fixture, so a counting bug cannot be papered over by
testing against a shape the engine never produces.

Invariants tested directly: zero candidates, one candidate, nulls, unknown vs none,
duplicate IDs, filtered universes, archived and quarantined exclusion, hidden
records, all filters, reset, threshold boundaries, insufficient baselines, and
same-input-same-output.

`test_counting_api.py` asserts the Match response and the counting response report
the **same numbers**, which is what keeps the contract binding real rather than
aspirational.

### 18.1 Two existing regression tests were updated

`test_final_hardening.py::test_stats_and_directory_use_one_predicate` and
`test_router_name_resolution.py::test_stats_endpoint_can_resolve_its_visibility_helper`
guarded against "a second copy of the public visibility rule". They asserted the
*router module* called `public_visibility_conditions()` directly, because that
module used to compute the counts itself.

The counts now live in `counting.catalogue` and the router delegates. **The property
is unchanged and is now checked where the call actually is** — including that the
router has *not* started calling the predicate again, which would mean a second
counting implementation. The guards were relocated, not relaxed.

---

## 19. Limitations

Accepted rather than guessed away:

- `deadline_precision` has eight published buckets, several of which the catalogue
  rarely populates. The buckets are declared because the vocabulary allows them;
  an empty one is visible, which is honest.
- Relationship grouping by published string is not entity resolution. Two funders can
  publish the same string. `is_verified=false` is the disclosure.
- The knowledge graph is sparse, so relationship counts come mostly from published
  field matches. No centrality, no communities.
- No durable historical count series exists, so trends over past counts are
  `NOT_AVAILABLE` until snapshots accumulate. Coverage is published so a reader can
  see why.
- Anomaly detection needs three real observations before it will say anything.
- `as_of` reconstructs record state, not counts: a full historical count would need
  a stored count series. See §20.
- The developer's local `backend/scholarzone.db` predates `is_archived` and fails its
  own startup seed. Pre-existing, unrelated, and why tests use isolated databases.

---

## 20. Future / research — not in the production core

Deliberately not implemented, and not justified by current data or scale:

HyperLogLog, blockchain/Merkle audit infrastructure, quantum-inspired counting, causal
inference, treatment-effect estimation, admission probability, applicant percentile
benchmarking, competitive density without authoritative data, Redis-backed
distributed caching, mandatory WebSocket infrastructure, full OLAP warehouse,
external paid analytics.

Two specific items need an architectural decision **before** code, not after:

1. **Durable historical count series.** Snapshot-as-of reconstructs *record* state.
   A stored *count* series would need a new table — or a defined reuse of
   `MaintenanceRun.counts`. That is a migration, and migrations are not created
   silently. The requirement is recorded here instead.

2. **Event-driven updates.** The contracts are designed so future data events can
   invalidate affected counts without rewriting the engine. The current model is
   `request → deterministic computation → authoritative response`, which is correct
   for this scale.

---

## 21. Configuration reference

| Version | Value | Source |
|---|---|---|
| `count_contract_version` | `2.0.0` | `counting/contract.py` |
| `anomaly_detection_version` | `1.0.0` | `counting/anomalies.py` |
| `engine_version` | Match 2.0 | `matching/config.py` |
| `scoring_config_version` | Match 2.0 | `matching/config.py` |
| `field_taxonomy_version` | taxonomy version | `matching/config.py` |
| `deadline_semantics_version` | semantics version | `deadline_semantics.py` |

All published at `GET /v2/counts/contract` and in every intelligence response.