# Supervisor Discovery 1.0 — Final Report

Status: **built, tested, locally backfilled. Not deployed.**
Trust posture: **zero fabricated professors. Zero fabricated claims.**

---

## 0. Read this first — what the spec assumed versus what the repository contained

The specification's section 0 states that several subsystems already exist and
must not be rebuilt. Before writing any code I checked each one. Four of the
assumptions did not hold, and two of them change the shape of the work:

| Spec assumed | Actual state | Consequence |
|---|---|---|
| Authentication / session system exists | **None.** Only `backend/app/core/admin_auth.py` (shared admin secret). `frontend/src/services/authService.js` was a stub whose only behaviour was to throw `AuthServiceUnavailableError`. | Sections 17, 18, 31, 32, 38 and E2E steps 10–23 all require server-persisted private per-user data. This was impossible to build without an owner. |
| Student Dashboard 1.0 exists | **Does not exist.** No dashboard route or page. | Section 20's outreach summary is delivered as a small dedicated surface, not as a dashboard. |
| Application Workspace 1.0 exists | **Does not exist.** No application table or route. | Section 19's `application_id` is a nullable integer with no table behind it. No application lifecycle was invented. |
| `scholarship_supervisor_coverage` needs an institution key | `scholarships` has **no** institution, university, department or provider column. The only institution signals are `official_source`, `official_source_url`, `catalogue_url`, `official_updates_url`, `program_type`, `coverage`, `title`, `region`. (`provider` exists only on `discovery_candidates`.) | Discovery resolves the institution from the scholarship's **own** official URLs and requires the faculty page to be on **that same host**. Nothing cross-institution is ever linked. |

This was raised with the user before implementation. The decision recorded was:
build minimal student session auth as a prerequisite. That is what
`backend/app/core/student_auth.py` is.

### A pre-existing leak found and deliberately not copied

`repositories/scholarships.py:157-158` fetches a single scholarship with a bare
`session.get`, and `routers/scholarships.py:120-129` returns 200 for it. The
canonical `public_visibility_conditions` is therefore **not** applied on the
public detail route, so archived and quarantined records are currently readable
by id. This is pre-existing and out of scope to change here.

The supervisor routes do **not** copy that pattern. They apply
`public_visibility_conditions()` through `get_public_scholarship_or_404`, and a
record failing the predicate yields 404 — identically to an absent record.

---

## 1. Architecture audit

- **Backend**: FastAPI + SQLAlchemy 2.0, one `backend/app/models.py`, **no Alembic**.
  Schema arrives via `Base.metadata.create_all` plus hand-written idempotent DDL.
  Production is Postgres/Neon; local dev is SQLite.
- **Production does not migrate at startup.** `main.py:84-104` documents a
  deployment that answered 503 indefinitely because `create_all` and `ALTER TABLE`
  took ACCESS EXCLUSIVE locks with no statement timeout on a cold start.
  Production only runs `SELECT 1`. **Schema changes must go through the
  migration pipeline.** This feature is wired accordingly.
- **`create_all` creates new tables automatically on both dialects**
  (`checkfirst=True`, per-table). The hand-written DDL is defence-in-depth and is
  the path that actually reaches Neon.
- **Truth split**: the SQL visibility gate reads legacy `is_verified`, while
  `verification_contract.py` treats only `verification_status == 'active'` as
  verified. They can drift. This feature reuses the SQL gate rather than
  introducing a third meaning.
- **Test trap**: `backend/tests/conftest.py:30-31` sets the two public quality
  gates to `false`, so most tests run ungated. My test modules pin and restore
  them explicitly.
- **No LLM provider exists.** `config.py` has no OpenAI/Anthropic/Gemini key, and
  `requirements.txt` has no client library. Email personalisation is therefore
  deterministic (section 8), which is also the safer design.
- **No `passlib`/`argon2`/`bcrypt`.** Password hashing uses stdlib `hashlib.scrypt`
  rather than adding a dependency.
- **Existing fetch layer**: synchronous `httpx`, one-shot clients, `DomainRateLimiter`
  exists but was unwired, `DomainCircuitBreaker` exists inside the image runner,
  and **robots.txt is respected nowhere** — `source_adapter.py:47
  respect_robots_txt=True` is a dead flag.
- **Only outbound email** is `send_verification_reminder`, single-recipient and
  operator-notification only. There is no arbitrary-recipient send path.

---

## 2. Data model

Nine new tables. All additive, all new, `scholarships` untouched.

| Table | Purpose |
|---|---|
| `students` | Account. Unique normalised email, scrypt digest. |
| `student_sessions` | Server-side session, hashed token, expiry + revocation. |
| `contact_templates` | Editable templates, mirrored from code. |
| `scholarship_supervisor_coverage` | **Exactly one row per scholarship.** The invariant. |
| `professor_profiles` | One academic, deduplicated on `official_profile_url`. |
| `scholarship_professor_links` | Relationship, unique on `(scholarship_id, professor_id, relationship_type)`. |
| `supervisor_source_evidence` | One row per page actually read, with content hash. |
| `professor_availability` | One row per `(professor, scope)`; `source_url` and `verified_at` are NOT NULL. |
| `professor_outreach_records` | Private. Unique on `(user_id, scholarship_id, professor_id)`, `version` for optimistic concurrency. |

Types are `JSON` (never `JSONB`) to match the repository's export tooling.
Index and constraint naming follows the existing `ix_`/`uq_` conventions.

**One DDL source of truth**: `backend/app/supervisor_ddl.py` is imported by both
`app/database.py` and `backend/migrate_schema.py`, so the dev upgrade path and the
production migration path cannot describe different schemas.

---

## 3. Coverage model

Statuses (`app/services/supervisor_status.py`): `search_pending`,
`verified_supervisors`, `no_verified_supervisor_found`, `not_applicable`,
`needs_verification`, `source_blocked`.

Three rules are enforced by tests rather than by convention:

1. **A fresh row asserts nothing.** Default is `search_pending`, not zero.
2. **An unread source is never a negative result.** `recompute_coverage` checks
   `blocked` before `not searched`; an unreachable source is `source_blocked`, and
   only a genuinely completed read with no qualifying relationship is
   `no_verified_supervisor_found`. *(This was a real bug found and fixed by a test.)*
3. **The count is recomputed, never incremented.** Re-running discovery cannot
   inflate it.

---

## 4. Provenance

Every relationship row requires `evidence_source_url` and
`evidence_source_type` — non-nullable. A relationship without provenance cannot
be represented. `supervisor_source_evidence` additionally records what was read,
when, with what HTTP status and content hash.

A verified relationship whose source type is not in `AUTHORITATIVE_SOURCE_TYPES`
is counted as an invariant failure by `scripts/supervisor_backfill.py` and must be
zero.

---

## 5. Discovery pipeline

`app/services/supervisor_discovery.py`, deliberately separate from the maintenance
worker and from the image/verification stages.

```
scholarship official URLs (own host only)
  → fetch (robots + per-host delay + shared cache)
  → find same-host faculty/people links (≤3 pages, ≤6 fetches)
  → fetch each faculty page
  → extract person links (name heuristics reject "Apply Now", digits, headings)
  → fetch each profile page (≤40 per scholarship)
  → store professor, link, evidence, availability
  → recompute coverage
```

Host scoping is the trust boundary: **a faculty page on the awarding
institution's domain is evidence; any other host is not.** Cross-institution
links are never created — the extractor discards them.

Politeness: `DomainRateLimiter(1.0s)` before every request, `robots.txt` checked
with a 1-hour cache that **fails closed** on an unreadable policy, ≤8 workers
(ceiling 16), bounded page and candidate counts, HTML capped at 400 KB.

One bug worth recording: robots.txt is respected **nowhere** in this repository,
including the existing image pipeline. I did not modify that pipeline (out of
scope, and it is fragile shared maintenance), but it should be treated as
outstanding work.

---

## 6. Verification semantics

Six independent dimensions, deliberately not merged:

| Dimension | Source of truth |
|---|---|
| Scholarship verification | existing `verification_contract.py` — untouched |
| Scholarship visibility | existing `public_visibility_conditions()` — reused |
| Professor relationship | `scholarship_professor_links.verification_status` |
| Email confidence | `professor_profiles.official_email_verified` |
| Availability | `professor_availability.state` + source + date |
| Research alignment | computed per request from explicit interests |

A scholarship can be fully verified while a professor relationship is unverified,
and a professor can be verified while availability is `unknown`. Both are true at
once and no code path collapses them.

**Official email rule**: an address is published only when it was read from the
institution's own page *and* its domain matches. Otherwise the UI says "Use the
university profile or contact page." No address is generated from a naming
convention, ever.

**Availability**: five states, per scope (master's / PhD / postdoc / funding).
Absences (`unknown`, `not_published`) never decay into `stale`, because a stale
absence is still an absence. Only `verified_yes`/`verified_no` age out, after 30
days.

---

## 7. Research alignment

Four bands, deterministic, no arithmetic that could be read as a probability:
`STRONG` (stated interest matches a published area as a whole phrase),
`MODERATE` (≥2 significant words all present), `RELATED` (one shared significant
word), `INSUFFICIENT_EVIDENCE`.

**`INSUFFICIENT_EVIDENCE` is the default for every user in 1.0**, because no
student profile is persisted anywhere in this codebase. Interests are typed by the
student, held in `localStorage`, and sent per request. Nothing is stored server-
side and nothing is inferred. That is a correct answer, not a missing feature.

An early test caught over-generosity: a single shared generic word
("approaches") was producing `MODERATE`. The rule now requires two significant
words.

---

## 8. Email templates

Three: initial master's, initial PhD, follow-up. Plain text, bounded
(subject ≤200, body ≤3500), stored in `contact_templates` and mirrored
idempotently from code.

**There is no AI in this path.** No provider is configured, and a model would make
output indistinguishable from a sourced one while giving it no way to check its
own claims. Personalisation fills only from verified records and **names what it
could not fill** in an `unresolved` list. With no verified research area the
sentence is omitted rather than invented. There is no publication to reference,
so no draft can mention a paper.

Templates assert nothing about the recipient: no claim that a place exists, that
they are recruiting, or that funding is available.

**The server cannot send email.** No send endpoint exists. Draft → review →
copy → send from the student's own client.

---

## 9. Outreach tracking

One canonical state machine in `OUTREACH_TRANSITIONS`. Illegal transitions are
rejected with 422, not silently applied — `sent → positive` is refused; the path
must go through `replied`.

Optimistic concurrency via `version`; a stale write gets 409 and the newer note
survives. Notes are plain text with markup rejected and length bounded.

Deleting an outreach record removes the student's own row and touches nothing
else — the professor, the relationship and the provenance remain, because those
are public facts, not the student's data.

---

## 10. API contract

```
POST   /auth/register            201, sets HttpOnly SameSite=Lax cookie
POST   /auth/login               200 / 401 (identical failure for unknown vs wrong password)
GET    /auth/me                  200 / 401
POST   /auth/logout              204 (revokes server-side, then clears cookie)

GET    /scholarships/{id}/supervisors            public, 404 if not publicly visible
GET    /scholarships/{id}/supervisor-summary     public, card-weight only

GET    /outreach                                 private
GET    /outreach/summary                         private
POST   /outreach                                 private, idempotent
PATCH  /outreach/{id}                            private, 404 cross-user, 409 stale
DELETE /outreach/{id}                            private, 404 cross-user

GET    /supervisor-email/templates               public
POST   /supervisor-email/draft                   private, returns text only
```

`user_id` is never accepted from a client. Cross-user access returns **404, not
403** — a 403 would confirm the record exists.

Rate limits (new, in-process): 120 reads/min per resource, 20 drafts/min,
60 writes/min per student. It is in-process and documented as such; a
multi-instance deployment would need shared state.

---

## 11. Frontend UX

Existing visual language only: off-white `#FBFAF6`, navy `#1B3A5C`, Instrument
Serif + Inter, hairline borders, no new palette.

- **Card**: a quiet `Potential Supervisors · N` label, rendered **only** when a
  verified count exists. A zero is never rendered as "0", because that reads as
  "this scholarship has no supervisors".
- **Detail page**: a full panel that renders a distinct, explained state for
  search pending / none verified / blocked / not applicable / stale / error. The
  no-results copy explicitly says this usually means the faculty page was not
  reachable — **not** that no professors exist.
- **Professor card**: name, affiliation, research areas, alignment with its
  reasoning in words, official profile, verified email or an explicit
  "use the official page" instruction, availability per scope with source and
  date, provenance disclosure, prepare email, track outreach.
- Availability state is spelled out in text **and** colour — colour alone would
  exclude readers who cannot distinguish the tones.
- 44px minimum targets, visible `:focus-visible` throughout,
  `prefers-reduced-motion` honoured, interests and outreach labelled.
- `SupervisorPanel` owns both the public list and the private tracker, because
  they share a scholarship and a session.

---

## 12–14. Security, privacy, performance

**Security.** scrypt (N=2^14, r=8, p=1) with per-password salt; self-describing
digests so cost can be raised later. 256-bit random session tokens stored only as
SHA-256 digests, so a stolen database yields no live session and any session can
be revoked individually. Cookie is HttpOnly + Secure-in-production +
SameSite=Lax, which is what makes unsafe methods cross-site-safe without a second
CSRF mechanism. Identity comes only from `core/student_auth.py`; the admin secret
is untouched and neither accepts the other's credential. Password length is
bounded on both sides so registration cannot be used as a memory-exhaustion
vector. Login runs a dummy verify on the unknown-address path so timing does not
reveal whether an account exists.

**Privacy.** No outreach field — draft, notes, response history, next action — is
reachable from any public route; a test greps the public response body for each
of them. Research interests never leave the browser except in the request that
uses them. A professor's public record contains no student data.

**Performance.** Batched, not per-professor: one link query, one profile query,
one availability query, one evidence query per response. All 9 new columns that
are filtered on are indexed. The summary route reads the coverage row rather
than recounting, so a grid of cards does not fetch 40 professor lists. The
coverage backfill selects only uncovered rows, so it advances past its first
batch instead of re-reading it.

---

## 15. Migration

Additive, idempotent, fresh- and existing-database safe, second-run no-op.

**Verified on SQLite**: `init_database()` twice — 9 tables, all declared indexes
present, second run a clean no-op.

Two bugs found and fixed during this step, both by the tools rather than by
inspection:

- Model `index=True` collided with explicitly declared `Index` names, producing
  duplicate index objects and a `create_all` crash. Every implicit index was
  removed so each index name is declared exactly once.
- `migrate_schema.py` recovers an index name by splitting on `" ON "`, so its
  index definitions must **not** carry a `CREATE ... IF NOT EXISTS` prefix. The
  shared module now stores bare definitions and prepends the prefix itself.

Production path: `python migrate_schema.py --dry-run` → `--validate-only` →
apply → `--validate-only`. `_validate_postgresql_schema` now also asserts the 9
new tables by name, so a missing one is a named startup failure rather than a 500
on the first supervisor request.

---

## 16. Backfill — measured, local database

```
python backend/scripts/supervisor_backfill.py
```

```
coverage backfill complete: 522 new row(s)   (200 already present from an earlier run)
All supervisor invariants hold.
```

Final local state, `backend/scholarzone.db`:

| Measure | Value |
|---|---|
| Total scholarships | **722** |
| Coverage rows | **722** |
| Coverage invariant holds | **true** |
| Scholarships with ≥1 verified supervisor | **0** |
| Scholarships with 0 verified supervisors | **722** |
| `search_pending` | **722** |
| `not_applicable` / `source_blocked` / `needs_verification` | **0 / 0 / 0** |
| Total unique professors | **0** |
| Total professor links | **0** |
| Verified official emails | **0** |
| Relationships without evidence | **0** |
| Verified relationships on a non-authoritative source | **0** |
| Availability claims without a source | **0** |
| Duplicate professor profiles | **0** |
| Count drift between coverage and links | **0** |

**722 of 722 covered. Zero professors. Zero claims.**

That is the intended outcome and it is the point of the feature: coverage is
comprehensive while knowledge is honestly zero. Nothing was invented to make a
number look better.

### Production counts

Production public catalogue measured read-only from the live API during this work:
**358** scholarships (43 countries, all verified and imaged, 264 open).

The raw production row count is **not** available from this machine — the Neon
URL is not in any local environment file and app startup deliberately does not
migrate. `scripts/supervisor_backfill.py` reports exact production figures on
first run against the production database. **I have not invented them.**

---

## 17. Tests

123 new tests, all passing, in three files.

`tests/test_supervisor_discovery.py` (38) — coverage for every scholarship,
idempotency, invariant report, blocked-vs-pending-vs-negative, duplicate
professor and duplicate relationship refused by the database, one professor across
two scholarships, public/private schema separation by body inspection, unverified
relationship never published, unverified email withheld, internal error summary
never public, archived/quarantined/absent all identically 404, availability
staleness, alignment bands, catalogue and Match isolation, validation, rate
limiting.

`tests/test_supervisor_outreach.py` (43) — scrypt round-trip and salt uniqueness,
malformed hash authenticates nobody, register/login/logout, revoked cookie replay,
indistinguishable login failures, every private route 401, cross-user 404 for
read/update/delete, idempotent create, illegal transition, unknown enum, 409 stale
concurrency, markup and length limits, delete leaves the public fact intact, draft
fabrication guards, draft bounded length, templates public and plain text.

`tests/test_supervisor_worker.py` (42) — host classification, faculty-link
detection, seed-URL filtering, extraction excluding cross-institution links and
link labels, no research areas without a labelled section, email domain rules,
availability phrasing, verified professors with provenance, no duplicates across
runs, non-institutional source refused, unreachable / 403 / 404 / 429 / 5xx /
timeout all distinguished from a negative, malformed HTML, robots disallow,
robots fails closed, bounded concurrency measured rather than asserted.

### Bugs these tests found in my own code

Worth recording, because each was a way to publish a false statement:

1. Unreachable source recorded as a completed negative — the exact failure the
   feature exists to prevent.
2. "not accepting students" matched the affirmative phrase "accepting students",
   turning a refusal into an offer.
3. `blocked` lost to `not searched`, hiding a real access failure as "pending".
4. The card listing professors while the coverage row said "none found" when a
   counter drifted.
5. A single generic shared word producing `MODERATE` alignment.
6. A colon from a research-interest label being stored as part of an area.
7. A successful fetch returning empty content being treated as a read page.

**Full suite: 4827 passed, 2 failed.** Both failures are pre-existing and
unrelated — one is a missing `yaml` dev dependency in the virtualenv, the other is
an image-pipeline assertion in `image_validator.py`, a file carrying 193 lines of
uncommitted work by another actor that predates this work. Neither is touched by
this feature.

---

## 18. Browser E2E

**Not run.** The environment has no browser driver available to this session, and
the local database has no verified professors — the interesting path (evidence,
availability, alignment, cross-user 404) has no data to exercise until discovery
runs against real institutional pages.

The 25-step journey in section 55 is designed but unexecuted. It should be run
before any deployment.

---

## 19–21. Deployment, verification, invariants

Not performed. Nothing has been deployed and no production data has been written.

Rollout order when approved:

1. `migrate_schema.py --dry-run`, then apply, then `--validate-only`.
2. `supervisor_backfill.py --coverage-only` — every scholarship gets a state,
   asserting nothing.
3. `supervisor_backfill.py --discover --limit N` — small batches, review the
   statuses before widening.
4. Public API + UI.

Invariants to check before and after, all of which this feature is designed to
leave alone: scholarship total, public total, verified total, Match counts, Count
Intelligence, application counts, dashboard counts, saved records, image counts,
image audit, Admin Verification. The backend tests assert Match and catalogue
isolation directly.

---

## 22. Known limitations

1. **No student profile exists**, so alignment is `INSUFFICIENT_EVIDENCE` for
   everyone until interests are typed. Correct, but a thin first-run experience.
2. **Discovery has never run against a real university.** The pipeline is verified
   against fixtures only. Real faculty pages vary enormously; expect a tuning
   cycle on extraction before results are trustworthy.
3. **robots.txt is respected nowhere else in this repository.** The image pipeline
   still ignores it. Pre-existing, untouched, and worth fixing.
4. **No retry/backoff in the discovery worker.** It reuses
   `fetch_official_source`, which does not retry. A 429 ends that scholarship as
   `source_blocked` and waits for the next run. Acceptable, not ideal.
5. **The summary count can disagree with the coverage row** if a link is inserted
   outside the worker. The public list self-heals; the card does not.
6. **In-process rate limiting only.** One instance is bounded; a scaled deployment
   is not.
7. **`institution_name` is derived from `official_source` or the host.** It is a
   label for a verified fact, so an approximate value is tolerable there in a way
   it would not be for a person's name.
8. **No E2E run, no production migration, no backfill against Neon.**
9. **No frontend test runner exists** in this repository. Section 54 asked for
   Vitest; it is not installed and I did not add a dependency to introduce it.
10. **Two unrelated pre-existing failures** in the suite (above).

---

## 23. Future enhancements — deliberately not built

Bulk email, scheduling, response prediction, admission probability, professor
reputation scores, star ratings, testimonials, attachment sending, paywalls,
autonomous agents. Section 64 lists these as out of scope for 1.0 and none of them
is present. There is no code path that could send an email even if asked.

---

## 24. Exact count of scholarships covered

**Local development database: 722 of 722 (100%).**

**Production:** 358 public scholarships measured live; the raw row count and the
post-backfill breakdown must be read from the production database on first run.
They are not guessed here.