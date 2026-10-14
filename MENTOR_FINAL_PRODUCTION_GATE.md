# MENTOR — FINAL PRE-DEPLOYMENT GATE

**No deployment, no push, no Vercel setting altered.** Read-only gate plus local verification.

---

## Current Master SHA

`573a983b004ab08578497272659123323ab489b7` — `docs: the wording fix is deployed and verified in production`

Re-read at the start of this gate. **It has not advanced** during this task.

- Candidate `a4d5833` reachable from master? **No** (`exit=1`) — it is not merged.
- Master is an ancestor of the candidate? **Yes** (`exit=0`).
- Commits master → candidate: **1**. Commits candidate → master: **0**.

**No Mentor file changed on master since the candidate was prepared.** The single Mentor file that
differs between the two is `evidence.py` — the candidate's own change seen in reverse. Master was not
overwritten; nothing was lost.

## Mentor Candidate SHA

`a4d5833b4c3e16f41f11fc7b777751c9aff4ee38` — `fix(mentor): scope the evidence fingerprint to the record that owns the chip`

- Parent: `573a983` (exactly current master) → a clean fast-forward.
- **Verified absent from the remote** — not pushed, not deployed.

## Provenance Status — **NOT IMPLEMENTED AS REQUIRED** (BLOCKING)

`backend/app/main.py::build_revision()` resolves the reported revision in this order:

1. `VERCEL_GIT_COMMIT_SHA` — accepted if it matches `[0-9a-fA-F]{7,64}`, then **truncated to 12 chars**
2. `VERCEL_GIT_COMMIT_REF` — same rule
3. `SCHOLARZONE_BUILD_REVISION` — same rule
4. `dev` if not production, else `unknown`

Against the required chain **build-time Git SHA → immutable build artifact → runtime health revision**:

| requirement | status |
|---|---|
| build-time SHA baked into an immutable artifact | **PROVEN ABSENT** — `git grep SCHOLARZONE_BUILD_REVISION` finds it only in `main.py` (read) and in tests. **No build script, `vercel.json`, or workflow ever writes it.** |
| runtime value cannot be a branch name | **HOLDS** — branch names fail the hex regex |
| runtime value cannot be a truncated SHA | **FAILS THE REQUIREMENT** — a 7–12 char hex prefix is accepted and returned, so a truncated SHA **is** accepted. Live reports `4edd154a3037` (12 chars) |
| runtime value cannot be manually supplied | **FAILS THE REQUIREMENT** — `SCHOLARZONE_BUILD_REVISION` is an operator-settable env var. The docstring itself concedes a build "told what revision to claim will happily claim it while serving older code" |
| HTTP 200 alone is insufficient | **HOLDS** — `unknown` in production is treated as failure by the verifier |
| a fresh preview can be required to report the exact commit Vercel built | **CANNOT BE DONE** — I cannot create a preview without deploying, which is not authorised, and the mechanism would not prove it anyway |

**Conclusion: revision provenance is NOT trustworthy.** It is a truncated runtime environment read with a
falsifiable fallback, not an immutable build artefact. Deployment status cannot be established to the
standard this gate requires.

## Canonical Production Target — **PROVEN for CI; AMBIGUOUS for users**

| host | `/api/health` revision | `stats.total` | `/api/mentor/overview` |
|---|---|---|---|
| `scholarzone-fwzj.vercel.app` | **`4edd154a3037`** | 358 | 200 |
| `scholarzone.vercel.app` | **`3ee434c01f53`** | 358 | 200 |

**The deployment-verification target is provable:** `gh variable list` returns
`SCHOLARZONE_API_URL = https://scholarzone-fwzj.vercel.app/api`, which is the variable `deploy.yml`
polls; `admin-auth-check.yml` also uses `scholarzone-fwzj.vercel.app`.

**But the two-project ambiguity is real and unresolved:**

- Both hosts serve the **same database** (identical 358 / 358 / 358), so they are two deployments of one
  app — not two products.
- Both are listed in `backend/app/core/config.py::allowed_origins`, so the application accepts browser
  requests from **both**.
- **`scholarzone.vercel.app` is four commits behind** at `3ee434c01f53` — it predates `27047de`
  ("stop the mentor asserting a claim it never checked"), so a user landing there gets a Mentor with a
  defect that is fixed everywhere else.
- **Nothing verifies that host.** No workflow, variable or check covers it.

So: canonical target for CI = `scholarzone-fwzj` (**proven**). Canonical target for *users* =
**not proven**, because a second unmonitored user-facing alias exists and is stale. Per the gate's own
rule, that half of Step 3 is **BLOCKED**.

## Two-Project Status

| project | live revision | commits behind master | monitored by CI |
|---|---|---|---|
| `scholarzone-fwzj` | `4edd154a3037` | 1 (docs only) | **yes** — `SCHOLARZONE_API_URL` |
| `scholarzone` | `3ee434c01f53` | 3 (`27047de`, `84d9d7e`, `573a983`) | **no** |

Both currently report Vercel **rate-limited** failures.

## Final Test Results

| gate | result |
|---|---|
| Mentor regression (candidate) | **10 passed** |
| **non-vacuity** — `evidence.py` reverted to master's version | **5 failed / 5 passed** |
| restored from the proven blob (identity re-verified) | **10 passed** |
| relevant backend suite (15 files) | **1046 passed, 1 skipped** |
| frontend `npm test` | **163 passed** (9 files) |
| `npm run lint` | **0 errors**, 1 pre-existing `HomePage.jsx` warning |
| `npm run build` (production build) | **success** |

## Browser Identity-Gate Result — **PASSED**

Two stale servers from earlier phases were holding ports 8000/8002/5173. **My first gate attempt was
invalid because of it and was discarded**, exactly as in the previous phase. Before accepting any result I
asserted the identity gate:

```
GATE: health reachable            -> 200
GATE: backend is the seeded GATE db -> 200 "GATE Twin Alpha"
```

All results below come from a run where that gate passed first.

| required assertion | result |
|---|---|
| supporting records retain **both** chips | **PASS** — A `[Application state, Deadline]`, B `[Application state, Deadline]` |
| focused application record leads | **PASS** — first application chip `application-1-state`, focused app id 1 |
| logout changes authenticated state correctly | **PASS** — session present before (user id 1), logout 204, `{"user":null}` after, private surface 401 |
| private data not exposed | **PASS** — with `credentials:'omit'`: `/api/mentor/message` **401** "Sign in to continue.", `/api/dashboard` 401, `/api/applications` 401. Public overview returns only the 5 static keys, no `email`/`token`/`user_id`/`scholarship_id` |
| 0 unexpected console errors | **PASS** — 8 total: 3 × `ERR_CONNECTION_TIMED_OUT` on `www.daad.de/...scholarship-banner-students-campus.jpg` (third-party image on a **seeded demo record**, unreachable from this sandbox) and 5 × 401 on my own deliberate anonymous/post-logout probes. **Zero from the candidate's code.** |

Unchanged behaviours re-verified live: deadline precision truthful, unknown deadline stays unknown,
funding `UNKNOWN` unmeasured, same-record duplicates collapse (`max=1`), chip budget respected (`items=10`).
Responsive at 320 px: `wrap=wrap`, `right=277`, **no horizontal scroll**, **0 interactive overflow**.

**One self-correction:** my first gate run reported "anon mentor refused → 200" as a failure. That was a
**test-ordering bug** — I registered (creating a session cookie) before the anonymous assertion, so the
call was authenticated. Re-tested with `credentials:'omit'` it returns **401**. No product defect.

## Deployment Eligibility — **NOT ELIGIBLE**

| requirement | met? |
|---|---|
| A. current master verified | **YES** — `573a983`, unchanged, candidate is a clean fast-forward |
| B. Mentor candidate preserved | **YES** — `a4d5833`, not pushed, not deployed, still reachable locally |
| C. revision provenance trustworthy | **NO** — no immutable build artefact; truncated runtime env with a falsifiable fallback |
| D. canonical production target proven | **PARTIAL** — proven for CI (`scholarzone-fwzj`); **not proven for users** (stale unmonitored alias `scholarzone`) |
| E. final tests pass | **YES** — 10 regression (5 failing without the fix), 1046 backend, 163 frontend, lint/build clean, 17/17 E2E behind an identity gate |
| F. Vercel rate limit no longer active | **NO** — still active |

## Exact Remaining Blockers

1. **Vercel build rate limit is ACTIVE.** Fresh read-only check at 12:51Z: both `scholarzone` and
   `scholarzone-fwzj` returned *"Deployment rate limited — retry in 24 hours."* at **11:51:45Z**, ~1 h
   before this gate. Stated reset **2026-10-05 10:21:57Z — 21.5 hours away**. No deployment may be
   attempted while this holds.
2. **Revision provenance is not implemented as required.** No build-time SHA is baked into any artefact;
   `SCHOLARZONE_BUILD_REVISION` has no producer; a truncated SHA is accepted; the operator fallback is
   falsifiable by the app's own admission. Deployment correctness cannot be *proven* after promotion —
   only asserted.
3. **A second user-facing alias is stale and unmonitored.** `scholarzone.vercel.app` serves
   `3ee434c01f53`, four commits behind, missing `27047de`, with no CI coverage and no defined canonical
   status. Merging the Mentor fix does not reach it.

None of the three is a code defect in this candidate. All three are deployment/ops conditions.

## Release Decision

# BLOCKED

The Mentor fix itself is **GREEN** and fully verified — but the gate requires A–F simultaneously, and
**C, D (user-facing half) and F all fail**. Two are configuration/ops (provenance chain, stale alias) and
one is an active third-party rate limit with ~21.5 h to run.

`NEEDS_CONFIGURATION_FIX` would understate it: even with provenance and alias resolved, the rate limit
independently forbids deployment today. The code is ready; the **release path is not**.

**Recommended sequence, in order:**
1. Wait for the rate limit to reset (2026-10-05 ~10:22Z), or have the owner upgrade the Vercel plan.
2. Resolve the canonical user-facing target: decide whether `scholarzone.vercel.app` is retired or must be
   kept current, and put it under verification if kept.
3. Implement build-time SHA provenance — bake the full commit into an artefact at build and report that
   immutable value, dropping or clearly marking the operator-supplied fallback.
4. Re-run this gate; then push `a4d5833` to master and let the existing CI→deploy path promote it.

**No deployment was attempted, and no Vercel setting was altered.**