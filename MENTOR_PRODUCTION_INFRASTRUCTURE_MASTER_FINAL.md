# MENTOR — PRODUCTION INFRASTRUCTURE MASTER FINAL

**No deployment. No merge. No production data change. No Neon write. Master unmoved.**

---

## 1. Executive Verdict

The three release blockers were treated as one system and **two are now closed in code**; the third is
external. Immutable build provenance and an exact deployment gate are implemented, tested and awaiting
review in **PR #3**. The Mentor dedup fix is included and verified. The release identity gate and the
anonymous-probe safeguard exist because release verification has twice been contaminated by a stale
server and once mis-read an authenticated response as an anonymous one.

Two things prevent declaring READY_FOR_FINAL_DEPLOY, and neither is a code defect:

- the **Vercel build rate limit is still active** (single fresh check, both projects);
- the **canonical user-facing production host is still UNKNOWN** — there are three public surfaces, and
  the sitemap names a fourth-party one.

**FINAL CLASSIFICATION: READY_FOR_PR**

## 2. Current Master — PROVEN

`573a983b004ab08578497272659123323ab489b7` — `docs: the wording fix is deployed and verified in production`

Re-read at Phase 0 and again at Phase 14. **It did not advance.** Unmoved; no rewrite; no amend.

## 3. Mentor Candidate — VALIDATED, PRESERVED, PORTED

`a4d5833b4c3e16f41f11fc7b777751c9aff4ee38` (parent `573a983`). Re-derived rather than trusted:
cherry-picked `-n` onto current master, applied cleanly, and the resulting blobs are **byte-identical**
to the proven candidate (`8e957c0e…`, `bfcefaf9…`). Ported into the release branch as
`48b8201`.

**Coordination finding — PROVEN.** A peer branch `rc/mentor-hardening` (`00bc39d`) already contains a
**semantically identical** dedup fix (`(entry.scholarship_id, …)`, student chips scoped with `None`
instead of a sentinel). It also bundles unrelated compose + documentation churn.
`rc/revision-provenance` (`00bc39d`, same SHA) is **misnamed**: it contains no provenance work at all.
**Open PR #1** also touches `evidence.py`. Someone should reconcile these three; this branch deliberately
carries the narrowest variant (2 files, no doc churn).

## 4. Root Cause of Revision Mismatch — PROVEN

`build_revision()` resolved, **at import, from the environment**, and truncated:

1. `VERCEL_GIT_COMMIT_SHA` → `raw[:12]`
2. `VERCEL_GIT_COMMIT_REF` → `raw[:12]`
3. `SCHOLARZONE_BUILD_REVISION` → `raw[:12]` — operator-settable
4. `dev` / `unknown`

Three defects in one function: the value was **mutable per deployment**, it was **not a commit id**, and
`SCHOLARZONE_BUILD_REVISION` let a build be *told* what to claim — which the code's own docstring
concedes is exactly the failure the endpoint exists to detect.

## 5. Immutable Build Provenance — IMPLEMENTED

```
VERCEL build → scripts/write_build_provenance.py → validates exactly 40 hex
             → writes app/build_provenance.json into the deployed package
             → app/provenance.py reads it → /api/health reports the full SHA
```

- Accepts **only** `[0-9a-f]{40}`. A 12-char prefix, a branch, a tag, a URL, `unknown`, `latest` → **build
  failure** (exit 1).
- Missing SHA → **build failure**. No "unknown production build" exists any more.
- Wired as `backend/vercel.json` `buildCommand`, additive after the existing `installCommand`.
- Artefact is **gitignored**, so a committed copy cannot reintroduce a falsifiable label.
- `VERCEL_GIT_COMMIT_REF` is now explicitly refused **with a reason**, instead of silently falling
  through to "no SHA provided".
- Runtime reads **only** the artefact. Proven by test: neither `VERCEL_GIT_COMMIT_SHA` nor
  `SCHOLARZONE_BUILD_REVISION` nor spoofed request headers change the reported value.

## 6. Health Endpoint Contract — IMPLEMENTED, TESTED

`revision` is now the exact 40-character SHA. Existing fields preserved. A production build with no
artefact reports **`unproven-build`**, deliberately *not* `unknown`, so the gate can distinguish "wrong
commit" from "no provenance record". 32 tests pin the contract, including a real subprocess run of the
generator and an end-to-end *supplied SHA == artefact == runtime* chain.

## 7. Deployment Gate — HARDENED, NOT WEAKENED

`deploy.yml` now:
- validates its own expected revision is a full 40-char id before polling;
- compares the **full** id for equality;
- **explicitly refuses a prefix** of the expected commit;
- accepts only `^[0-9a-f]{40}$` as a trustworthy identity.

`EXPECTED_SHORT` and the `{7,40}` range are **gone**. Verified 0 occurrences remain. HTTP 200 alone is
still insufficient — the revision match is mandatory.

## 8. Vercel Project A — `scholarzone-fwzj` — PROVEN

Live `4edd154a3037`. This is the **CI-verified production target**: `gh variable list` shows
`SCHOLARZONE_API_URL = https://scholarzone-fwzj.vercel.app/api`, which `deploy.yml` polls, and
`admin-auth-check.yml` uses it. Last successful deployment 09:18:43Z; since then every promotion has
been rate-limited.

## 9. Vercel Project B — `scholarzone` — STALE

Live `3ee434c01f53` — **four commits behind**, missing `27047de` ("stop the mentor asserting a claim it
never checked"). Serves the **same database** (identical 358/358/358). **Nothing verifies it**: no
workflow, variable or check targets it. Not deleted, not altered.

## 10. Canonical Production Host Evidence — **UNKNOWN**

| surface | evidence |
|---|---|
| `scholarzone-fwzj.vercel.app` | **PROVEN** canonical for CI/deployment verification (`SCHOLARZONE_API_URL`) |
| `scholarzone.vercel.app` | also in `allowed_origins`, so the app accepts browser requests from it |
| `gopal735.github.io/ScholarZone/` | **`sitemap.xml` canonical `<loc>`**, and `robots.txt` allows `/ScholarZone/*` |

Tracked references: `scholarzone-fwzj` in 4 files (`admin-auth-check.yml`, `core/config.py`, and two
tests); `scholarzone` in 3 (config + tests). Local `.vercel` linkage: **absent**, and per the rules it
would not be proof anyway.

**`canonical_user_host = UNKNOWN`.** The application's own public canonical points at GitHub Pages,
while its deployment pipeline verifies a Vercel host that sitemap does not name. This cannot be resolved
from the repository or from public metadata, and I will not invent a hostname.

## 11. Stale Host Risk — PROVEN

`scholarzone.vercel.app` is reachable, serves the full app, shares the production database, is an allowed
origin, and is three Mentor fix commits behind master + `4edd154`. A user landing there gets a Mentor with
a defect that is fixed everywhere else. **Behavioural divergence is unresolved.**

## 12. Rate Limit Status — ACTIVE (single check, no retries)

Both `scholarzone` and `scholarzone-fwzj`: *"Deployment rate limited — retry in 24 hours."* Not bypassed,
not retried, no alternate project or account used. Deployment is **BLOCKED** until it clears.

## 13. Release Identity Gate — IMPLEMENTED, PROVEN WITH A NEGATIVE CONTROL

`backend/scripts/release_identity_gate.py` refuses to proceed unless it can prove: the backend answers;
`/health` reports the **exact** expected revision; a sentinel record exists; and that sentinel carries
**this run's unique marker**.

**It earned its place immediately.** On first run it **passed against a stale uvicorn** left over from my
previous phase, because I had reused a fixture title. That is the exact contamination it exists to catch,
so I hardened it (per-run marker) and added a **negative control**: a wrong marker now correctly fails.
With nothing running it exits 2 and refuses to assert anything.

Two further defects in the gate were found and fixed by testing: a `Accept: application/json` header made
a dev server 404 its HTML root, and a bare origin needed normalising.

## 14. Test Ordering / Isolation — FIXED

The earlier false result ("auth guard missing") was **my test ordering**: I registered, creating a cookie,
before asserting anonymity. `frontend/src/services/anonymousProbe.js` now pins `credentials: "omit"` for
every anonymous probe, with 4 tests. In this run all anonymous checks were performed with cookies
omitted and returned **401** as they should.

## 15. Mentor Verification — VALIDATED

| gate | result |
|---|---|
| mentor regression | **10 passed**; **5 failed / 5 passed** with the fix reverted (non-vacuous) |
| mentor + provenance + contract | **132 passed** |
| relevant backend suites | **1046 passed, 1 skipped** |
| frontend | **167 passed**, lint **0 errors**, build clean |
| browser E2E behind a passing identity gate | **19/19** |

Browser: twins both retain `[Application state, Deadline]`; focused application leads; deadline precision
truthful; unknown deadline unknown; funding `UNKNOWN` unmeasured; per-record dedup max 1; budget 10;
logout → unauthenticated; anonymous protected endpoint → 401; no private data leaked. Console: **4 errors,
all my own deliberate 401 probes** — zero from the changed code.

## 16. Exact Git Diff — PROVEN

`48b8201` on `573a983` — 14 files, +1290 / −75:

```
M .github/workflows/deploy.yml                    M backend/vercel.json
M .gitignore                                      M frontend/src/services/anonymousProbe.test.js
M backend/app/main.py                              A frontend/src/services/anonymousProbe.js
A backend/app/provenance.py                        A backend/scripts/release_identity_gate.py
M backend/app/services/mentor/evidence.py          A backend/scripts/write_build_provenance.py
A backend/tests/test_build_provenance.py           A backend/tests/test_evidence_record_identity.py
M backend/tests/test_final_hardening.py
M backend/tests/test_vercel_migration.py
```

No image, ingestion, Match, Count, Supervisor, verification-contract, Wave 1–3 or scheduler change. The
local fixture harness `backend/rel_seed.py` was **verified absent** from the commit.

## 17. PR — OPEN, NOT MERGED

**https://github.com/gopal735/ScholarZone/pull/3** — base `master`, head
`release/final-mentor-production-reconciliation`. Not merged. Not deployed.

## 18. Post-Reset Deployment Procedure — FOR THE OWNER

Once the rate limit clears, and **only** after PR #3 is reviewed and merged:

1. `git fetch origin && git rev-parse origin/master` — record the merge commit.
2. Re-check the rate limit: both Vercel commit statuses must not say "rate limited".
3. Confirm the merge commit's Vercel deployment is `Production`, not Preview.
4. `curl -s https://scholarzone-fwzj.vercel.app/api/health | jq -r .revision` — must equal the **full 40-char**
   merge SHA. A 12-char value means the build hook did not run: **stop**.
5. Run the identity gate against production:
   `python backend/scripts/release_identity_gate.py --base-url https://scholarzone-fwzj.vercel.app/api --expect-revision <sha> --expect-host scholarzone-fwzj.vercel.app`
6. Confirm the frontend points at the canonical backend.
7. Authenticated Mentor E2E on production; anonymous probes with credentials omitted; verify public
   scholarship visibility unchanged (358 / 358 / 358).
8. Decide the `scholarzone` project's fate so no stale public host survives indefinitely.

**HTTP 200 alone is never proof.**

## 19. Remaining Unknowns — UNKNOWN / BLOCKED

1. **Canonical user-facing production host** — UNKNOWN (three public surfaces; sitemap names GitHub Pages).
2. **Vercel account/project configuration** — UNKNOWN (no API credentials; no proxying of limits).
3. **Whether the new `buildCommand` behaves on Vercel** — UNKNOWN until a real deployment; deliberately
   additive, but it is the one change not provable locally.
4. **Vercel project settings**: production branch per project, aliases, deployment protection — UNKNOWN.
5. Reconciliation of PR #1, `rc/mentor-hardening` and this PR's overlapping `evidence.py` work.
6. `maintenance_runs` id 250 still stale `status='running'` — activity UNKNOWN.

## 20. Final Release Decision

# READY_FOR_PR

Not `READY_FOR_FINAL_DEPLOY`, because readiness requires the rate limit to be inactive (**it is not**) and
the canonical production host to be proven (**it is not**). Not `NEEDS_CONFIGURATION_FIX`, because the code
and configuration work that *can* be done is done, tested, and in review. Not `BLOCKED`, because the
release path is open and unblocked by anything I can fix.

**What was achieved:** immutable build provenance and an exact deployment gate replace a revision field
that was mutable per deployment and not a commit id; the Mentor dedup regression is fixed with a
provably non-vacuous test; and release verification can no longer be fooled by a stale server or an
authenticated session.

**What remains, in order:** (1) review and merge PR #3; (2) wait out the rate limit; (3) establish the
canonical user-facing host and resolve the stale `scholarzone` project; (4) run the post-reset procedure
above.