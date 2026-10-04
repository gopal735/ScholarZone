# GROUNDed AI MENTOR 1.0 — Phase 0 Architecture Audit

Revision audited: `c405b49` (deployed production; `/api/health` → `c405b49bb8b9`)
Worktree: `C:\Users\GopaL\AppData\Local\Temp\kilo\mentor-wt`, branch `grounded-mentor`

Every conclusion below is labelled:

- **OBSERVED FACT** — read directly from the repository or queried from the platform.
- **PROVEN** — demonstrated by a test or an executed command.
- **DISPROVEN** — a plausible belief that the repository contradicts.
- **PLAUSIBLE BUT UNPROVEN** — likely, not demonstrated.
- **UNKNOWN** — not determinable from what is available.

---

## 0. Two blocking discoveries made before any code was written

### 0.1 The local `master` branch is 75 commits stale

**OBSERVED FACT.** `git merge-base master origin/master` = `8ac1c9a` = local `master` HEAD.
`git log origin/master..master` is empty.

**DISPROVEN.** The starting assumption that `master` and `origin/master` had diverged. They
have not. Local `master` is a strict ancestor — the repository is 75 commits behind, fast-forward
only, with zero local-only commits and nothing at risk.

**Why it matters.** An isolated worktree was first created from local `master`. On that base
`backend/app/routers/applications.py`, `backend/app/services/application_workspace.py`,
`backend/app/services/dashboard.py`, `backend/app/routers/dashboard.py` and every frontend test
file were **absent**, and `frontend/package.json` had **no** `test` script — which would have
produced a completely false audit conclusion ("this project has no frontend test framework").
The worktree was discarded while still empty (no commits) and rebuilt from `origin/master`, which
is the deployed line.

**Action for all contributors:** `git fetch origin`, then branch from `origin/master`.

### 0.2 There is no LLM provider, and two tests forbid adding one

**OBSERVED FACT — production credentials.** `vercel env ls production --project prj_NLC71y3rKRIOduTla785AzEOEFL5`:

| name | type | environments |
| --- | --- | --- |
| `DATABASE_URL` | Secret | Production |
| `SCHOLARZONE_DATABASE_URL` | Secret | Production |
| `SCHOLARZONE_ENVIRONMENT` | Secret | Production |
| `RESEND_API_KEY` | Secret | Production, Preview |
| `NOTIFICATION_EMAIL` | Secret | Production, Preview |
| `SCHOLARZONE_VERIFICATION_SECRET` | Secret | Production, Preview |

No `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `NVIDIA_API_KEY`, NIM/NGC key, Groq, or any other model
credential exists in production or in any local env file. `backend/requirements.txt` contains no
LLM SDK. No provider integration, prompt-building module, or chat-completion code exists anywhere
in `backend/`.

**OBSERVED FACT — house rules encoded as tests.** Four existing tests assert the absence of paid
AI dependencies:

| test | scope | forbidden |
| --- | --- | --- |
| `test_final_hardening.py::test_no_paid_dependency_was_added` | `backend/requirements.txt` | `openai`, `anthropic`, `google-genai`, `replicate`, `cohere` |
| `test_autonomous_maintenance.py::test_no_paid_dependency_was_introduced` | `backend/requirements.txt` | same five |
| `test_activated_features.py::test_no_snapdeploy_and_no_paid_dependency` | maintenance worker source (tokenised, comments/strings stripped) | `snapdeploy`, `openai`, `anthropic`, `api/public/wake` |
| `test_matching_v2.py::test_the_parser_needs_no_external_ai_service` | `app/services/matching/nlp.py` source only | `openai`, `anthropic`, `requests.`, `httpx`, `urllib`, `http://` |

The third and fourth are scoped to single modules and do not constrain new modules. The first two
scan `requirements.txt` wholesale: **adding a paid AI SDK would turn two currently-green tests
red.** The brief forbids weakening existing tests and altering tests to manufacture green CI.

**Conclusion.** The mentor ships with a **deterministic composer as its default and only
production path**, plus a **provider adapter that stays disabled until a credential is
configured**. No new dependency, no secret in the repository, no existing test altered. Enabling a
real provider later requires a credential *and* an explicit decision by the maintainers about
those two guard tests. That decision is not mine to make silently.

**Note on the prompt header.** `MODEL: NVIDIA Nemotron 3 Ultra` designates the coding agent
writing this code. It is not a credential available to the ScholarZone application, and no NVIDIA
endpoint is configured anywhere in the project.

---

## 1. What canonical data already exists?

**OBSERVED FACT.** Every system the mentor must ground itself in is live and reachable as a Python
service function.

| Domain | Canonical entry point | Location |
| --- | --- | --- |
| Session auth | `require_user` (FastAPI dependency) | `backend/app/dependencies.py` |
| Student profile | `load_stored_profile`, `get_profile_record`, `profile_is_empty`, `build_profile_strength` | `backend/app/services/dashboard.py` |
| Profile gaps | `build_gaps(match_response, strength) -> list[GapItem]` | `backend/app/services/dashboard.py` |
| Match 2.0 | `match_scholarships`, `MATCH_COLUMNS`, `CandidateRow`, `to_facts`, `select_matches`, `_recommendation` | `backend/app/services/matching/` |
| Readiness / eligibility | Match result fields `fit`, `coverage`, `eligibility`, `readiness`, `confidence`, `reasons`, `gaps`, `unverified_requirements` | `backend/app/services/matching/types.py` |
| Count Intelligence | `count_intelligence` | `backend/app/services/counting/service.py` |
| Deadline semantics | `evaluate_deadline(facts, as_of) -> DeadlineEvaluation`; `classify_deadline_text`; `coerce_deadline_precision` | `backend/app/services/matching/eligibility.py`, `backend/app/services/deadline_semantics.py` |
| Application Workspace | `application_workspace` service + `/applications` routes | `backend/app/services/application_workspace.py`, `backend/app/routers/applications.py` |
| Public visibility | `public_visibility_conditions()` | `backend/app/repositories/scholarships.py` |
| Verification | authoritative `verification_status` + label map | `backend/app/verification_contract.py` |
| Saved scholarships | `SavedScholarship` model, `count_saved` | `backend/app/models.py`, `backend/app/services/dashboard.py` |
| **Next actions (deterministic)** | **`build_next_actions(...) -> list[NextAction]`** | **`backend/app/services/dashboard.py:473`** |
| **Whole-user context assembly** | **`build_dashboard(db, user, as_of=None) -> DashboardResponse`** | **`backend/app/services/dashboard.py:687`** |

**The two most important findings.**

1. **A deterministic next-action engine already exists and must be reused.**
   `build_next_actions` uses a fixed priority-band table, documented in the source as deliberate:

   ```python
   #: Fixed priority bands. Ordering is a property of this table, not a score, a
   #: model or a clock reading: two identical states produce an identical list in
   #: an identical order. No fake urgency.
   _PRIORITY_PROFILE = 10
   _PRIORITY_IN_PROGRESS = 20
   _PRIORITY_SAVED_NOT_STARTED = 30
   _PRIORITY_UNVERIFIED_REQUIREMENT = 40
   _PRIORITY_CLOSING_SOON = 50
   _PRIORITY_COMPARE = 60
   _PRIORITY_EXPLORE = 90
   ```

   It returns `sorted(actions, key=lambda action: (action.priority, action.code))`. The brief
   says: *"Do not create an independent competing task engine if an existing deterministic
   next_actions system already exists. Reuse it."* It exists. The mentor therefore introduces **no
   new priority bands and no new scoring**; it renders this engine's output with evidence.

   Its deadline branch is already UNKNOWN-safe and is the pattern to copy:
   ```python
   days = recommendation.days_to_deadline
   if days is None or days > 30:
       continue
   ```
   `None` is skipped, never treated as `0` and never called overdue.

2. **`build_dashboard(db, user, as_of)` is already a single bounded context-assembly operation.**
   It already assembles profile, profile strength, gaps, match summary, Count Intelligence
   figures, deadlines, saved items, application items and next actions for one authenticated user
   in one call. The brief asks for *"one bounded server-side context assembly operation"* and
   *"do not duplicate entire database rows unnecessarily."* Reusing it satisfies both and avoids
   N+1 reads entirely.

**DISPROVEN.** That ScholarZone would need a new grounded-context builder. One exists, at user
scope, and it is already the dashboard.

## 2. What can be reused directly?

**OBSERVED FACT.** Directly reusable with no modification:

- `build_dashboard`, `build_next_actions`, `build_gaps`, `build_profile_strength`,
  `load_stored_profile`, `get_profile_record`, `profile_is_empty`, `select_matches`,
  `load_facts_for_ids`, `deadline_facts`, `count_saved`.
- `evaluate_deadline` and the deadline-precision helpers.
- `public_visibility_conditions()` and the verification contract.
- The Application Workspace service for state, outcome, progress, checklist and next action.
- `require_user` for ownership.
- `WorkspaceError` → HTTP status mapping already registered in `main.py`.
- Frontend: `GlassSurface`, `GlassButton`, `GlassBadge`, `GlassSkeleton`, the `theme.css` token
  set, `authContext`/`useAuth`, the per-domain service idiom, and the vitest setup.

## 3. What must NOT be duplicated?

**OBSERVED FACT.** The following would each create a second source of truth and are therefore
out of bounds: scholarship facts; deadline arithmetic; match/readiness/coverage scoring;
verification status; public-visibility rules; the application state machine; the checklist model;
catalogue counts; and **a second next-action priority table**.

**Specific traps found in the audit.**

- `main.py` CORS `allow_methods=["GET","POST","PUT","DELETE"]` does **not** include `PATCH`, yet
  the Application Workspace uses `PATCH`. Harmless today because the SPA and API are same-origin
  on Vercel, so no preflight occurs. **PLAUSIBLE BUT UNPROVEN** that this breaks if the frontend
  is ever hosted cross-origin. Pre-existing; not introduced here and not in scope.
- `schemas_dashboard.py` carries a snapshot fallback for hidden/archived scholarships, so a
  mentor that re-queried `Scholarship` directly would *regress* against the dashboard's behaviour.
- `deadline_semantics.py` and `matching/eligibility.py` both concern deadlines; the canonical
  entry point is `evaluate_deadline`, and both dashboard and application workspace already route
  through it.

## 4. Where should mentor logic live?

**Decision.** A new package `backend/app/services/mentor/`, with private schemas in
`backend/app/schemas_mentor.py` and one router in `backend/app/routers/mentor.py` registered
**last** in `main.py`, behind `require_user`, exactly like the dashboard and application
workspace.

```
backend/app/services/mentor/
    context.py     MentorContext assembly from canonical services (deterministic)
    intents.py     intent classification + unsupported-intent handling
    next_actions.py thin adapter over dashboard.build_next_actions (no new bands)
    evidence.py    evidence chips from canonical fields only
    compose.py     deterministic WHY / KNOWN / UNKNOWN / NEXT composer
    provider.py    provider Protocol + DisabledProvider (default) + injectable fake
    guards.py      input bounds, prompt-injection sanitisation, UNKNOWN-safe wording
```

**Rationale for a package rather than one module.** The grounding contract, the composer, the
provider seam and the guards have genuinely different failure modes and different test
requirements. Splitting them keeps the deterministic core provable without touching the provider
seam.

## 5. Provider/model integration actually available

**PROVEN: none.** See §0.2. Consequences:

- The production answer is produced **deterministically** from canonical facts. This is not a
  degraded mode; it is the most trustworthy configuration available and it satisfies every
  product requirement (grounded, deterministic, uncertainty-explicit, unable to fabricate).
- `provider.py` defines an abstract `MentorProvider` with a single `generate(request) -> ProviderResult`
  seam, and `resolve_provider()` returns `DisabledProvider` unless a credential is configured.
- `DisabledProvider` is not an error path: the composer simply does not call a provider and
  returns the deterministic answer. Tests inject a deterministic fake to exercise the seam.
- `httpx` (already a declared dependency, `>=0.27,<0.29`) is the only outbound HTTP client
  available, so a future provider adapter needs **no new dependency**. It is deliberately unused
  by default so that no mentor code path can make a network call unless explicitly enabled.
- Timeouts, failure and circuit-breaker behaviour are implemented and tested against the seam.

## 6. Secrets management

**OBSERVED FACT.** Secrets live only in Vercel project env vars and local untracked `.env` files.
`SCHOLARZONE_VERIFICATION_SECRET` is documented in-repo as also being the admin credential
(`df79a2f docs: record that the verification secret is also the admin credential`). No secret is
committed. `.env.local`/`.env.production.local` hold only `VERCEL_OIDC_TOKEN`.

**Decision.** The mentor reads at most one optional credential through the existing settings
object and never logs it, never returns it, and never places it in any response field. With no
credential configured, nothing about the provider is exposed to the client beyond the boolean
"assistance mode available".

## 7. Streaming vs non-streaming

**OBSERVED FACT.** The frontend has no `EventSource`, `ReadableStream`, `getReader`, or
`text/event-stream` usage anywhere, and Vercel serverless functions are not a good fit for
long-lived streaming responses.

**Decision.** Non-streaming `POST /api/mentor/message` returning one complete grounded answer.
Consistent with every other ScholarZone endpoint, testable deterministically, and it avoids
half-rendered "facts" arriving before their evidence. Streaming is a future improvement and is
listed as such.

## 8. Does a server-side grounded context builder already exist?

**PROVEN: yes, at user scope** — `build_dashboard(db, user, as_of)`. See §1. The mentor builds
`MentorContext` *from* it plus bounded extra lookups, never from raw table scans.

## 9. CSRF behaviour

**OBSERVED FACT.** There is no CSRF token anywhere. The posture is:

- `SameSite=lax` session cookie.
- CORS with an explicit origin allow-list and `allow_credentials=True`, methods
  `GET/POST/PUT/DELETE`.
- A per-router **Origin guard** on state-changing requests, used by the Application Workspace.

**Decision.** The mentor is a state-changing, cookie-authenticated `POST`, so it carries the same
Origin guard as the application workspace. The mentor performs **no writes at all** — it reads and
composes — so its blast radius is already minimal. A separate, minimal global CSRF hardening
change is *not* introduced here: the brief permits it only if it can be done without destabilising
production, and altering the auth posture for every existing endpoint in the same change as a new
feature is exactly the kind of destabilisation the brief warns against. It is recorded as a
recommended separate change, not silently ignored.

## 10. Rate limiting and observability

**OBSERVED FACT — rate limiting.** None exists anywhere: no `slowapi`, throttle, semaphore or
concurrency cap. **PROVEN** by search.

**Decision.** Because a mentor request can be expensive if a provider is ever enabled, the mentor
adds its own bounded, in-process, per-user limiter: a small fixed-window counter plus a bounded
in-flight cap, returning `429` with a `Retry-After`. It is deliberately scoped to the mentor
router rather than introduced globally, so it cannot change the behaviour of any existing
endpoint. Documented in the final report as in-process (per-instance), which is honest about its
limits on a serverless fleet.

**OBSERVED FACT — observability.** `main.py` calls `logging.basicConfig(level=SCHOLARZONE_LOG_LEVEL,
stream=sys.stdout)` and each module holds `logging.getLogger(__name__)`. Validation errors return
422, `WorkspaceError` returns its own status, and a catch-all returns a generic 500 with
`logger.exception`. **There is no request-id or correlation-id middleware.**

**Decision.** The mentor emits structured, privacy-safe log lines: a generated request id, latency,
intent, grounded/ungrounded outcome, provider mode, and bounded counts. It never logs message
text, notes, profile values, credentials, or the assembled context.

## 11. Migrations

**OBSERVED FACT.** Production does **not** run `create_all` on boot — `_run_init` only verifies
connectivity in production, because `create_all` plus `ALTER TABLE` took `ACCESS EXCLUSIVE` locks
on a serverless cold start and hung. Schema is owned by the GitHub Actions pipeline.
`migrate_schema.py` plans with no transaction open, then applies one statement per transaction
(after the Neon `IdleInTransactionSessionTimeout` incident).

**Decision — no migration at all.** The brief asks whether persistent conversation history is
actually required, and prefers minimal architecture. For 1.0 it is not required: the mentor answers
from bounded, current, canonical state. So **the mentor adds no table and no column**, which
removes the entire class of Neon migration risk from this feature. No `create_all`, no
`ALTER TABLE`, no new index, nothing to validate. Conversation history is listed as a future
improvement with the conditions it would have to satisfy.

---

## Architecture decision summary

| Question | Answer | Confidence |
| --- | --- | --- |
| Provider available? | **No.** No credential, no SDK, two tests forbid one | PROVEN |
| What produces the production answer? | Deterministic composer over canonical services | PROVEN |
| Second source of truth? | None created; no new priority bands, no new scoring | PROVEN |
| Second application state machine? | None; Application Workspace reused | PROVEN |
| Second deadline model? | None; `evaluate_deadline` only | PROVEN |
| Database change? | **None.** No tables, no columns | PROVEN (by construction) |
| Context assembly | One bounded `build_dashboard` call | PROVEN |
| Streaming? | No; single non-streaming POST | Decision |
| Conversation storage? | None for 1.0 | Decision |
| Global CSRF hardening? | Deferred to a separate minimal change | Decision, documented not ignored |
| Rate limiting? | Mentor-scoped in-process limiter, `429` + `Retry-After` | Decision |

**Unknowns that remain genuinely unknown and are labelled as such in the final report:** whether a
provider will ever be enabled; whether the mentor's in-process limiter is sufficient under a
serverless fleet (it is per-instance by construction); whether the pre-existing missing-`PATCH`
CORS entry ever matters (same-origin today).