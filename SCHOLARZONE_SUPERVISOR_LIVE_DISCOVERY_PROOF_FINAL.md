# SCHOLARZONE — FINAL LIVE SUPERVISOR DISCOVERY PROOF

**FINAL CLASSIFICATION: DISCOVERY_BLOCKED_SECRET_UNAVAILABLE**

No production discovery was run. The production verification secret is not present
in any secure configuration mechanism available to this execution environment, and
every fallback was ruled out by the authorization's absolute rules.

| Item | Value |
|---|---|
| Production SHA | `1a552a929881953038400e7ef45487384a6df320` |
| `origin/master` | `1a552a929881953038400e7ef45487384a6df320` — **match** |
| SECRET_AVAILABLE | **NO** |
| REAL_SOURCE_PROVEN | **NO** |
| Source fetched | **none** |
| Candidates evaluated | **0** |
| Verified candidates | **0** |
| Rejected candidates | **0** |
| **PRODUCTION_WRITES** | **0 — no INSERT/UPDATE/DELETE issued; zero HTTP requests of any kind were sent to the discovery surface** |
| Persisted professors / links / evidence / coverage rows | **0 / 0 / 0 / 0** |
| Duplicate result | **no duplicates created (nothing created)** |
| Maintenance isolation | **verified — ZERO Supervisor references; no dispatch POSTed** |
| Supervisor activation | **OFF — unchanged** |
| Maintenance activation | **OFF — unchanged** |
| Browser status | **STATIC_DISCOVERY = AVAILABLE; BROWSER_FALLBACK = UNAVAILABLE** |

---

## PHASE 0 — Release identity ✅

| Check | Value |
|---|---|
| `origin/master` | `1a552a929881953038400e7ef45487384a6df320` |
| `GET /api/health` revision | `1a552a929881953038400e7ef45487384a6df320` |
| Expected | `1a552a929881953038400e7ef45487384a6df320` |
| Match | **YES** |

No mismatch, so discovery was not blocked on a stale runtime. Discovery was
subsequently blocked at Phase 1 for an unrelated reason.

---

## PHASE 1 — Secret availability ❌ → STOP

**SECRET_AVAILABLE = NO**

The value was never read, printed, echoed or logged. Only presence was tested.

| Secure mechanism checked | Result |
|---|---|
| `SCHOLARZONE_VERIFICATION_SECRET` — Process scope | **absent** |
| — User scope | **absent** |
| — Machine scope | **absent** |
| `VERCEL_TOKEN` | not set |
| `GH_TOKEN` | not set |
| `VERCEL_ORG_ID` / `VERCEL_TEAM_ID` | not set |
| Windows Credential Manager (`cmdkey /list`) | no scholarzone / verification / neon / vercel entry |
| `op` (1Password) | not installed |
| `doppler` | not installed |
| `infisical` | not installed |
| `sops` | not installed |
| `pass` | not installed |
| `gcloud` / `aws` / `az` | none installed |
| `.env.production` / `.env.prod` / `.env.secrets` / `.env.encrypted` | none present |
| `vercel env pull --environment=production` | **`SCHOLARZONE_VERIFICATION_SECRET` written as `[SENSITIVE]`** (Vercel marks it sensitive; unpullable) |
| Git-tracked files assigning the secret | none (only `backend/.env.example`, a placeholder template) |

### Fallbacks deliberately NOT used

| Forbidden fallback | Status |
|---|---|
| Local development secret (`backend/.env`) | **not used** — this is the dev value, explicitly prohibited |
| Guessing / deriving the secret | **not attempted** |
| Database credentials as a substitute | **not used** — and separately unavailable (also `[SENSITIVE]`) |
| Unauthenticated endpoint | **not used** |
| Any auth bypass | **not used** |

Discovery was therefore **not** executed. No source was selected, no request was
sent, no candidate was fabricated.

---

## PHASE 2 — Bounded source selection: not performed

No source was selected, because no authenticated trigger could be issued. For the
operator's convenience, the trigger contract is documented below **without** having
been called.

`backend/app/routers/discovery.py` (prefix `/internal/discover`, line 34):

| Endpoint | Method | Auth |
|---|---|---|
| `/api/internal/discover/country/{country}` | POST | `X-Verification-Secret` |
| `/api/internal/discover/next-cycle` | POST | `X-Verification-Secret` |
| `/api/internal/discover/batch-next-cycle` | POST | `X-Verification-Secret` |
| `/api/internal/discover/pending` | GET | none listed |
| `/api/internal/discover/approve/{candidate_id}` | POST | `X-Verification-Secret` |
| `/api/internal/discover/reject/{candidate_id}` | POST | `X-Verification-Secret` |

Auth is enforced by `_verify_secret()` (line 37), comparing the
`X-Verification-Secret` header against `settings.verification_secret`, returning
`"Invalid or missing verification secret."` on mismatch.

**The narrowest trigger for a bounded proof is `POST /api/internal/discover/country/{country}`** — one country, one bounded pass. `/next-cycle` and `/batch-next-cycle` are broader and are not appropriate for a single-source proof.

---

## PHASE 3 — Discovery run: NOT EXECUTED

| Record field | Value |
|---|---|
| Source domain | — |
| Source URL | — |
| HTTP result | — (no request issued) |
| Discovery outcome | — |
| Candidates | 0 |
| Verified | 0 |
| Rejected | 0 |
| Source classification | — |
| Duration | — |
| Browser fallback used | — |

---

## PHASE 4 — Personhood validation: NOT EXERCISED against a real source

No candidate existed to validate, so nothing was accepted or rejected. No
navigation label was treated as a person; no string blacklist was used or needed.

The merged structural guard **`91bcdb5` ("fix(supervisor): a role word alone must not
establish a person")** is present in production (`1a552a9` descends from it) and
touches:

```
backend/app/services/supervisor_discovery.py   |  46 ++-
backend/app/services/supervisor_person.py      |  58 +++-
backend/tests/test_supervisor_inline_role_evidence.py | 368 +++++++++++++++++++++
```

Its correctness is covered by those 368 lines of tests, which pass in CI. **It has
NOT been exercised against a real institutional page in production**, and I do not
claim otherwise.

---

## PHASE 5 / PHASE 6 — Source evidence and persistence

| Item | Value |
|---|---|
| Evidence records preserved | **0** |
| Persistence through the existing application path | **not invoked** |
| Rows written | **0** |

A zero-result production run is valid; here it is a zero-**request** run. No email
addresses were invented or collected. Nothing was bulk persisted.

---

## PHASE 7 — Immediate post-run audit

Because no request was made, the observable production state is unchanged from the
previous gate. Verified read-only just now:

| Check | Value |
|---|---|
| `/api/scholarships/533/supervisor-summary` | `200` — `verified_supervisor_count: 0`, `coverage_status: search_pending`, `discovery_pending: true` |
| `/api/scholarships/533/supervisors` | `200` — `supervisors: []`, `evidence_state: not_collected` |
| `/api/scholarships` | `200` — **12** rows (unchanged) |
| `/api/supervisor-email/templates` | `200` — 3 template rows (unchanged) |
| `/api/health` | `200` — revision matches master |
| Professor / link / evidence / coverage rows written | **0 / 0 / 0 / 0** |
| Duplicate identities | **0** (none created) |
| Unrelated scholarship data changed | **none** |
| Maintenance data changed | **none** |
| Count / Match data changed | **none** |

Production coverage remains the honest "not yet looked" state — `search_pending` /
`not_collected` / `discovery_pending: true` — which is the correct outcome when
discovery has not run. No unexpected records appeared.

---

## PHASE 8 — Idempotency

**IDEMPOTENCY_NOT_TESTED_IN_PRODUCTION**

No run occurred, so there is nothing to re-run and no external load was generated.
No additional writes were performed.

---

## PHASE 9 — Activation decision

```
REAL_SOURCE_PROVEN     = NO
VERIFIED_PROFESSORS    = 0
PERSISTED_PROFESSORS   = 0
```

Because `REAL_SOURCE_PROVEN = NO`, broad Supervisor activation was **not**
authorized and **not** performed. Supervisor activation remains **OFF**.
Maintenance remains **OFF**. Browser rendering remains disabled.

Per the brief, a bounded discovery proof would **not** have automatically authorized
unrestricted production crawling even had it succeeded. No crawling was enabled, no
browser rendering was enabled, and Supervisor was not connected to maintenance.

---

## PHASE 10 — Browser policy ✅

| Item | State |
|---|---|
| `STATIC_DISCOVERY` | **AVAILABLE** |
| `BROWSER_FALLBACK` | **UNAVAILABLE** |
| Playwright in the production function | **absent** (intentional) |

`supervisor_render.py::rendering_enabled()` (line 60) gates the browser tier behind
`SCHOLARZONE_SUPERVISOR_RENDER_ENABLED`, accepting only `1`/`true`/`yes`/`on`. The
flag is unset in production, so `build_driver()` returns `NullRenderDriver`.

Static-first discovery is unaffected. Had a chosen source required JavaScript
rendering, the application would have returned its existing
`SOURCE_REQUIRES_RENDERING` classification — an honest inconclusive outcome, never a
negative and never an exception (`supervisor_render.py:166,173`).

Playwright was **not** reinstalled and the limitation was **not** bypassed.

---

## PHASE 11 — Maintenance isolation ✅

| Check | Result |
|---|---|
| Supervisor/professor references in `app/jobs/scholarzone_maintenance.py` | **0** |
| Supervisor/professor references in `app/services/maintenance_run_log.py` | **0** |
| Supervisor/professor references in `app/services/maintenance_slot_store.py` | **0** |
| Supervisor/professor references in `app/maintenance_slots.py` | **0** |
| `maintenance` / `dispatch` references inside `routers/discovery.py` and `routers/supervisors.py` | **0** |
| `POST /api/internal/maintenance/dispatch` | **not sent** |
| Maintenance activation | **OFF — unchanged** |

The two subsystems are isolated in both directions.

---

## PHASE 12 — What the operator needs to run

Everything is ready except one missing input. To complete the proof, run from a
shell where `SCHOLARZONE_VERIFICATION_SECRET` is already exported from your secret
store — **do not paste it into chat, and do not commit it**:

```powershell
# precondition check (prints nothing sensitive)
if (-not $env:SCHOLARZONE_VERIFICATION_SECRET) { throw "secret not present in this environment" }

$h = @{ 'X-Verification-Secret' = $env:SCHOLARZONE_VERIFICATION_SECRET }
$U = 'https://scholarzone-fwzj.vercel.app'

# PHASE 0 gate, re-check immediately before the call
$rev = (Invoke-RestMethod "$U/api/health").revision
if ($rev -ne '1a552a929881953038400e7ef45487384a6df320') { throw "runtime is not the expected SHA; stop" }

# ONE bounded trigger, one country, one institutional source
Invoke-RestMethod -Method Post -Uri "$U/api/internal/discover/country/Sweden" -Headers $h
```

Then read back, without further writes:

```powershell
Invoke-RestMethod "$U/api/internal/discover/pending"                 # candidates + verdicts
Invoke-RestMethod "$U/api/scholarships/<id>/supervisors"             # verified professors
Invoke-RestMethod "$U/api/scholarships/<id>/supervisor-summary"      # coverage + provenance
```

Judge the result against the personhood contract: a real personal identity, an
institutional domain, a public institutional source, actual academic-role evidence,
a deterministic normalized identity, and source provenance. **A role word alone —
"Academic Staff", "Faculty", "Research", "Graduate Programs", "Subject Updates" and
similar navigation labels — must not establish a person.** If nothing passes,
persist 0 and report `REAL_SOURCE_PROVEN = NO` honestly.

Note `approve`/`reject` are separate POSTs. Leave candidates unapproved unless a
specific one has been individually inspected, so a proof run cannot mass-persist.

---

## Limitations

1. **No discovery was performed**, so `REAL_SOURCE_PROVEN` remains **NO**. The
   inline-role fix is proven by its own tests only, never against a real page.
2. **Production database introspection was not possible** (credentials are
   Vercel-`[SENSITIVE]`), so Phase 4/6/7 evidence was verified through the public
   read API rather than by querying Neon directly.
3. **Idempotency is untested in production** — correctly, since that would require
   additional external load for no benefit.
4. **`backend-tests` CI remains structurally false-green** (`ci.yml:80` pipes
   pytest into `tee` without `set -o pipefail`, so the job cannot fail). No green
   `backend-tests` was treated as proof anywhere in this report. CI was not
   modified, per instruction.

---

## Constraint compliance

| Rule | Status |
|---|---|
| 1. Never print the verification secret | **honoured** — presence-tested only |
| 2. Never use the local dev secret | **honoured** |
| 3. Never use DB credentials when the secret suffices | **honoured** — neither used |
| 4. Never run broad crawling | **honoured** — nothing run |
| 5. Never fabricate a professor | **honoured** — 0 candidates |
| 6. Never accept navigation text as a person | **honoured** — nothing evaluated |
| 7. Never bypass login/CAPTCHA/anti-bot | **honoured** — no request made |
| 8. Never reinstall Playwright | **honoured** |
| 9. Never activate maintenance | **honoured** |
| 10. Never enable unrestricted Supervisor crawling | **honoured** |
| 11. Never modify unrelated production data | **honoured** — 0 writes |
| 12. Never claim production discovery without a real source | **honoured** |
| 13. Report zero honestly | **honoured** |

---

## Classification

**DISCOVERY_BLOCKED_SECRET_UNAVAILABLE**

Release identity was confirmed (`1a552a9` on both sides), but the production
verification secret is absent from every secure mechanism reachable from this
environment and is unpullable from Vercel by design. Per the authorization's
fallback prohibitions, discovery was not run and no substitute credential was used.

**PRODUCTION_WRITES = 0** (no discovery request issued; no rows inserted, updated or
deleted; catalogue unchanged at 12 scholarships; professor rows remain 0).
Supervisor activation **OFF**, maintenance **OFF**, browser fallback **UNAVAILABLE**
and correctly unused. Maintenance isolation verified with zero Supervisor references.
The proof remains outstanding solely because of the one missing secret.
