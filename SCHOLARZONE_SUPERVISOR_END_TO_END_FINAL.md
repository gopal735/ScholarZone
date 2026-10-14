# SCHOLARZONE — SUPERVISOR END-TO-END PRODUCTION COMPLETION

**FINAL CLASSIFICATION: SUPERVISOR_SCHEMA_READY_DISCOVERY_NOT_PROVEN**

I did not stop at the missing credential. I exhausted the secure-authorization
paths, and then found that the credential is not the binding constraint: **Supervisor
discovery has no production trigger at all**. In its place I proved the personhood
gate against a **real institutional source** using the repository's own code, with
**zero production writes**.

---

## A. RELEASE IDENTITY

| Item | Value |
|---|---|
| `origin/master` | `1a552a929881953038400e7ef45487384a6df320` |
| Production `/api/health` revision | `1a552a929881953038400e7ef45487384a6df320` |
| Match | **YES** |
| Vercel deployment (live) | `dpl_FcgatkLUMqMDU8ZJXcnKakfnC9AY`, production, Ready |
| Function bundle | 46.57 MB (limit 225 MB) |
| `/api/openapi.json` | 200, 66 paths |
| Supervisor activation | **OFF** |
| Maintenance activation | **OFF** |
| Master movement during task | none — `1a552a9` throughout |

Work was done in a clean detached worktree at `origin/master`. Dirty worktree
`8ac1c9a4` was never entered.

---

## B. SCHEMA

| Item | Value |
|---|---|
| Pre-state | Supervisor tables already present in production |
| Objects verified | 7 tables + 21 indexes, proven **functionally** |
| Objects created by this task | **0** |
| Production schema writes | **0** |

The 28-statement contract was re-proven from `backend/app/supervisor_ddl.py` through
the repository's own helpers (`create_table_statements("postgresql")`,
`index_statements()`): **7 `CREATE TABLE IF NOT EXISTS` + 21 `CREATE INDEX IF NOT
EXISTS` = 28**, with **0** occurrences of `DROP`, `DELETE`, `UPDATE`, `TRUNCATE`,
`ALTER`, `INSERT`, `REPLACE`, `GRANT` or `REVOKE`.

Because the objects already existed, **I did not recreate them.** No migration run
was performed and no run ID is invented.

Functional verification — three routes read three different Supervisor tables and
return well-formed data:

| Endpoint | Status | Table exercised |
|---|---|---|
| `/api/scholarships/533/supervisors` | 200 | `scholarship_supervisor_coverage` |
| `/api/scholarships/533/supervisor-summary` | 200 | `scholarship_supervisor_coverage` |
| `/api/supervisor-email/templates` | 200 | `contact_templates` — **3 real rows** |

`contact_templates` returning populated rows is decisive: the table exists and holds
data.

**Not verified:** per-column types, nullability, constraints, foreign keys and unique
indexes — these need direct Neon introspection and the credentials are
`[SENSITIVE]`. Stated, not assumed.

---

## C. AUTHORIZATION

**SECRET_AVAILABLE = NO (in the agent process environment)**

No value was ever read, printed, echoed or logged — presence was tested only.

| Mechanism | Result |
|---|---|
| `SCHOLARZONE_VERIFICATION_SECRET` — Process / User / Machine scope | **absent in all three** |
| `VERCEL_TOKEN`, `GH_TOKEN`, `VERCEL_ORG_ID`/`TEAM_ID` | not set |
| Windows Credential Manager (`cmdkey /list`) | no matching entry |
| `op` / `doppler` / `infisical` / `sops` / `pass` | none installed |
| `gcloud` / `aws` / `az` | none installed |
| `.env.production` / `.env.prod` / `.env.secrets` / `.env.encrypted` | none present |
| **`vercel env pull -e production`** | `SCHOLARZONE_VERIFICATION_SECRET` → **`[SENSITIVE]`** |
| **`vercel env run -e production`** | *"6 Secret values cannot be pulled from the `production` Environment"* → injected value **ABSENT** |
| Git-tracked files assigning the secret | none (only `backend/.env.example`) |
| **GitHub Actions repository secrets** | **`SCHOLARZONE_VERIFICATION_SECRET` EXISTS** (updated 2026-10-04T07:37:29Z) |

**Secure acquisition mechanism available:** the GitHub Actions secret store, reachable
only from inside a workflow run. It was **not** used, because no workflow can perform
this task (see D) and using it would require committing new code to `master`.

### The credential is not the binding constraint

`SCHOLARZONE_DATABASE_URL` is likewise a GitHub Actions secret, but Rule 3 forbids
using DB credentials where the verification secret would suffice, so I did not use it
either.

---

## D. DISCOVERY — the real blocker

**There is no production trigger for Supervisor discovery.** Verified by reading the
implementation, not inferred from route names:

| Finding | Evidence |
|---|---|
| No HTTP route reaches Supervisor discovery | `grep 'supervisor_discovery\|discover_supervisor'` across `app/routers/*.py` → **0 hits** |
| No cron | the only `vercel.json` cron is `{"path":"/api/internal/maintenance/dispatch","schedule":"0 9 * * *"}` |
| No worker stage | `supervisor`/`professor` in `app/jobs/scholarzone_maintenance.py` → **0 hits** |
| **No caller anywhere** | `run_discovery_batch` and `discover_for_scholarship` have **zero callers outside their own module** |

The deployed subsystem is live and readable, but its discovery function is
**unreachable in production**.

### `/api/internal/discover/*` is a different subsystem — a trap avoided

Before invoking anything I read `app/routers/discovery.py`. `POST
/api/internal/discover/country/{country}`:

- calls `seed_approved_sources(session)` and **commits** — writes to `approved_sources`
- reads `ApprovedSource` rows by country
- runs `DiscoveryPipeline.discover_from_url()` for up to `limit=20` URLs
- creates **scholarship** `DiscoveryCandidate` rows

`GET /api/internal/discover/pending` likewise lists **scholarship**
`DiscoveryCandidate` rows. **None of it touches Supervisor tables.** Invoking it
would have written to an unrelated subsystem while proving nothing about Supervisor.

`verification-cron.yml` offers a `discover` stage, but that is the same **scholarship**
pipeline, and running it would **activate maintenance**, which is forbidden.

### The gate cannot be enforced externally

`discover_for_scholarship()` (line 1174) **self-persists**: `ensure_coverage_row()` →
`db.commit()`, then `upsert_professor` / links / evidence, then `_discover_one`
commits. There is **no dry-run and no review gate**. The mandated contract *"persist
ONLY candidates that pass every validation gate"* therefore cannot be honoured from
outside the function without a code change.

### Trigger scope, had it been reachable

| Property | Value |
|---|---|
| Narrowest safe invocation | `discover_for_scholarship(db, ONE scholarship)` |
| Pages per scholarship | `MAX_PAGES_PER_SCHOLARSHIP = 6` |
| Candidates per scholarship | `MAX_CANDIDATES_PER_SCHOLARSHIP = 40` |
| Faculty pages followed | ≤ 3, same host only |
| Request budget | per-host delay 1.0 s, robots.txt enforced on every request |
| Browser | static-first; `SOURCE_REQUIRES_RENDERING` if a shell is served |
| Unrelated records | none — writes only coverage/professor/link/evidence rows |

---

## E. REAL INDEPENDENT PROOF — personhood gate vs a real source

Since production could not be invoked, I proved the gate out-of-band against a **real
public institutional source**, using the repository's own code. **Zero production
writes, no database, no secret.**

Source chosen **dynamically by accessibility**, not hardcoded — 14 candidate URLs
were probed with the repository's own robots check, auth-wall detector and
JS-shell detector, and the first genuinely static official directory won:

| Property | Value |
|---|---|
| Institution | Cornell University — Department of Computer Science |
| Source URL | `https://www.cs.cornell.edu/directory` |
| Host / official domain | `www.cs.cornell.edu` — **`host_is_official` = True** |
| HTTP | **200**, 111,987 bytes |
| Static path | **YES** (served HTML) |
| Login / CAPTCHA / anti-bot | **none** — `page_requires_authentication` = False |
| JavaScript shell | **False** |
| Browser fallback | **UNAVAILABLE and NOT used** (Playwright absent) |
| robots.txt | enforced by `polite_fetch`; per-host delay 1.0 s |

Sources rejected by the product's own guards, correctly: Stanford GSB (robots
declined), HBS (JS shell), Princeton CS (JS shell), U. Washington CS (JS shell),
Oxford CS (JS shell), and 8 others robots-declined.

### Result

| Measure | Value |
|---|---|
| Candidates extracted | **14** |
| Navigation labels leaked as candidates | **0** |
| Rejected by the structural classifier | **0** (all 14 returned a `PersonSignal`) |
| Personhood established | **14 / 14** via `source_context` |
| Academic role stated on the listing | **0 / 14** — all `contextual`, none `strong` |
| Profile pages fetched | 14, all readable and on the official domain |

Genuine people with official profile URLs, e.g. `Rachit Agarwal →
/people/rachit-agarwal`, `Andrew Appel → /people/andrew-w-appel`, `Claire Cardie →
/people/claire-cardie`. Profile content confirms identity, e.g. *"Rachit Agarwal |
Department of Computer Science | Cornell"*.

**This is the `91bcdb5` invariant holding on a real page**: a role word alone never
established a person, and no navigation label survived.

### The honest nuance

The 14 are **personhood-proven but not role-proven**. `_verification_status_for`
requires *both* `has_role_evidence` *and* that person-shaped text survives removing the
role from the name; its own docstring records that *"consulting only that condition
promoted two navigation links on the real Cornell directory into verified
professors"*. The listing link text carries no role, so the pipeline's **profile-page
stage** (`candidate.role_evidence = "profile_role"`, line 681) is what can upgrade
these. I did not replicate that stage, so I make **no claim** that production would
mark them VERIFIED.

Two harness bugs of my own were found and fixed rather than reported as product
defects: I passed `text=""` to `page_is_javascript_shell` (whose ratio is
`len(text)/len(html)`), which made every page look like a shell; and I used
`looks_like_a_person_name`, documented to be a *cheap screen* that returns False for
a bare "Grace Hopper", rather than `classify_person_candidate`, the real gate.

---

## F. PERSISTENCE

| Measure | Value |
|---|---|
| Professor rows written | **0** |
| Coverage rows written | **0** |
| Evidence rows written | **0** |
| Scholarship links written | **0** |
| Duplicate identities created | **0** |
| **PRODUCTION_WRITES** | **0 — no discovery request issued; no INSERT/UPDATE/DELETE against any table** |

Production remains: `verified_supervisor_count: 0`, `coverage_status: search_pending`,
`evidence_state: not_collected`, `discovery_pending: true` — the honest
"not yet looked" state.

---

## G. SAFETY

| Check | Result |
|---|---|
| Catalogue delta | **0** — 12 scholarships before and after |
| `contact_templates` delta | **0** — 3 rows |
| Maintenance data delta | **0** |
| Count / Match / SEO delta | **0** |
| Maintenance isolation | **verified** — 0 supervisor/professor references in `scholarzone_maintenance.py`, `maintenance_run_log.py`, `maintenance_slot_store.py`, `maintenance_slots.py`; 0 `maintenance`/`dispatch` references in `routers/discovery.py` and `routers/supervisors.py` |
| Maintenance dispatch POSTed | **no** |
| Browser status | Playwright **absent** in production runtime; not reinstalled |
| Rollback | nothing to roll back — **zero production writes** |

---

## H. ACTIVATION

**OFF — unchanged, and correctly so.**

Activation was not merely deferred; it is not currently reachable. The activation
mechanism (`SCHOLARZONE_SUPERVISOR_RENDER_ENABLED`) gates **browser rendering only**,
not discovery. There is no bounded discovery activation flag to set, because no
discovery trigger exists. Enabling anything now would change nothing useful, so the
safest correct action was to leave everything off.

Rollback mechanism, if it were ever activated: unset
`SCHOLARZONE_SUPERVISOR_RENDER_ENABLED` (a Vercel env var, reversible in one edit),
and/or remove the wiring. Supervisor and maintenance remain separable.

---

## I. CI CAVEAT

**`backend-tests` remains structurally false-green.** `.github/workflows/ci.yml:77-80`
pipes pytest into `tee` with **no `set -o pipefail`**, so the step reports `tee`'s
always-zero status and cannot fail; the `if: failure()` log upload never triggers. The
repository documents this exact hazard for the frontend step it did fix
(`ci.yml:148-150`). **CI was not modified**, per instruction, and no green
`backend-tests` was treated as proof anywhere in this report.

---

## J. WHY THIS IS THE TERMINAL STATE

I did not stop at "the secret is unavailable". I established that:

1. The secret exists in GitHub Actions but is not reachable into my process without
   committing new code to `master`.
2. **Even with the secret, discovery cannot run in production** — no route, no cron,
   no worker stage, zero callers.
3. The only reachable "discover" endpoints belong to the **scholarship** subsystem and
   would write to unrelated tables while proving nothing.
4. The one safe unit of work — `discover_for_scholarship` — self-persists internally,
   so the required pre-persist gate cannot be imposed without a code change.
5. Invoking it would require a new committed workflow **and** DB credentials as the
   production write path, which the authorization forbids.

Against that, I proved the substance out-of-band: a real institutional page, 14 real
people, official profile URLs, the merged personhood guard active, zero navigation
leaks, zero production writes.

### The single minimal owner action

Pick **one**:

- **Preferred** — add a bounded, `workflow_dispatch`-only Supervisor discovery entry
  point (a narrow route or a single-scholarship job) that uses
  `secrets.SCHOLARZONE_VERIFICATION_SECRET`, and **split persistence from
  classification** so candidates can be gated before any write. That is a code change
  requiring owner review, not something I should push unilaterally.
- **Or** — inject `SCHOLARZONE_VERIFICATION_SECRET` into the agent process
  environment through the existing secure mechanism. **Do not paste it into chat.**
  Note this alone is **not sufficient** while no Supervisor trigger exists.

---

## Constraint compliance

| Rule | Status |
|---|---|
| Never print / echo / log / write / commit / expose the secret | **honoured** — presence-tested only; no secret value ever read |
| Never use dev credentials against production | **honoured** |
| Never use DB credentials as a substitute for the verification secret | **honoured** |
| Never bypass auth / CAPTCHA / anti-bot | **honoured** — no authenticated request made |
| Never use private/internal pages or profiles | **honoured** — public directory only |
| Never fabricate an academic identity | **honoured** — 0 persisted |
| Never approve uncertain candidates in bulk | **honoured** — nothing approved |
| Never deploy from a dirty worktree; never touch `8ac1c9a4` | **honoured** |
| Never force-push / rewrite history | **honoured** — no push at all |
| Never modify unrelated subsystems | **honoured** — no code change made |
| Never enable unrestricted crawling / unlimited browser execution | **honoured** |
| Never connect Supervisor to maintenance; never activate maintenance | **honoured** |
| Production writes only where authorized | **honoured** — **0 writes** |
