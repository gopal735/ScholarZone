# SCHOLARZONE — DEPLOYMENT-PROTECTION-COMPATIBLE GATE PATCH

| | |
| --- | --- |
| Scope | **2 files** — `backend/scripts/release_identity_gate.py`, its tests |
| Branch | `release/build-provenance-only` @ `fa95f5f` (merged with concurrent work) |
| `origin/master` | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` — **never moved** |
| Provenance redesign | **none** · SHA semantics changed: **none** · application changed: **none** |
| Deployment Protection | **PRESERVED — never disabled, no exception, no public URL** |
| Production writes | **NONE** |
| Deployments triggered | **NONE** |

---

## 1. The blocker, and what changed

A per-deployment Vercel URL sits behind Deployment Protection. An anonymous read
returns the platform's interstitial — and unhelpfully it returns **HTTP 200 with
an HTML page carrying a different `data-dpl-id`**, which is more dangerous than
an error because it looks like a successful response. The gate could therefore
never bind a runtime revision to a specific deployment.

**PROVEN — the mechanism now works.** `vercel curl` performs an authenticated
read using credentials the CLI already holds. Verified live against the exact
canonical deployment URL:

```
{"status":"ok","revision":"ddcd9c3662f4"}
```

**PROVEN — protection was not weakened.** The same URL read anonymously in the
same session returned `content-type: text/html`, `isAppJson=False` — the
interstitial, not the application. Only the authenticated path returns the real
payload. No credential is read, passed or logged; the CLI authenticates with its
own stored session, and a failed read reports only an exit code rather than
echoing stderr, which can carry a session trace.

**PROVEN — no bypass mechanism is exposed to the application.** Nothing was added
to the app: no header, no query token, no shared secret, no exception. The
authenticated path lives entirely in the verifier script.

**PROVEN — fails closed.** If the CLI is unavailable or the read fails, the gate
refuses and says protection remains enabled. It does not fall back to an alias,
because an alias would let a healthy production domain stand in for a specific
deployment — the exact substitution this gate exists to prevent.

## 2. Three defects found while implementing it

Recorded because each would have produced a *plausible wrong answer* rather than
an error.

**2.1 `vercel inspect --format json` omits `gitSource`.** It resolves a URL *or*
an id, but its summary has no commit provenance, so on its own the gate reported a
deployment as having no git source at all — indistinguishable from a deployment
that genuinely has none. The REST API returns the full record but resolves **only
by id**; both URL forms 404. Resolution is therefore two steps: resolve to an id,
then fetch the authoritative record by id.

**2.2 The platform returns a deployment `url` without a scheme.** Comparing it
against a caller's `https://…` reported a false "deployment url mismatch" on the
*correct* deployment. URL comparison now normalises scheme and case.

**2.3 Windows `CreateProcess` searches neither `PATH` nor `PATHEXT`.** Passing a
bare `"vercel"` failed with file-not-found even though the command works from a
shell, and `shutil.which` would have picked the PowerShell `.ps1` shim, which a
direct process launch cannot execute. The resolved absolute path is used instead.

## 3. Tests

**PROVEN — 90 pass** across the gate and provenance suites
(`test_release_identity_gate.py` + `test_build_provenance.py`), up from 46 for the
gate alone. New coverage, per the required matrix:

| Case | Test |
| --- | --- |
| protected exact deployment URL | `test_the_authenticated_read_parses_the_health_payload` |
| authenticated exact deployment request | same, plus `--deployment` asserted |
| missing authentication | `test_it_fails_closed_when_the_cli_is_unavailable` |
| authentication failure | `test_it_fails_closed_when_authentication_fails` |
| wrong deployment URL / alias | existing `test_a_wrong_backend_cannot_pass`, `test_a_git_master_alias_is_rejected…` |
| malformed runtime SHA | `test_a_malformed_health_revision_is_refused[…]` |
| truncated runtime SHA | `test_a_truncated_health_revision_is_refused[12/7/8]` |
| stderr not echoed | `test_it_never_echoes_cli_stderr_which_may_carry_a_trace` |
| interstitial not mistaken for health | `test_the_interstitial_is_never_mistaken_for_a_health_payload` |
| artefact/runtime agreement | `TestArtefactAgreement` (5 tests) |

Also asserted: the read is **read-only and `shell=False`**, with no `-X` and no
`--prod`, so it cannot mutate anything or be redirected by a crafted URL.

**PROVEN — one test assertion was updated, not weakened.** It asserted the command
began with the literal `"vercel"`; it now asserts the *resolved* executable path,
which is the corrected behaviour. The boundary is unchanged.

**PROVEN — full backend suite, merged tree:** `5080 passed / 8 failed / 10 skipped
/ 13 warnings / 1 error` against a baseline of `4988 / 8 / 11 / 13 / 1`. The 8
failures are the known pre-existing `test_neon_migration.py` set.

**VALIDATED — the one-skip difference is not mine.** It is
`test_it_measures_against_the_real_catalogue`, which reads the **gitignored**
local `backend/scholarzone.db` and therefore skips or runs depending on local
state. It skips in the baseline worktree and runs here. Previously reported; not
fixed, since changing it would alter what the discovery gate proves.

## 4. Concurrent-work reconciliation

The release branch was **rewritten by another actor** mid-patch, so the two lines
of work arrived as five add/add conflicts. Resolved by merge — **no force push,
no rebase, no history rewrite** — toward the versions verified here, which are a
superset: the other actor independently implemented the gitignore rule and the
strict uppercase rejection, and both are kept here; the **project binding** and
the **authenticated observation** exist only on this side. The gitignore rule is
identical on both sides and only the explanatory comment differs. Pushed as a
fast-forward (`ffc73f6..fa95f5f`).

## 5. Live gate result — and what still blocks it

Run against the **exact deployment URLs**, authenticated, twice, on the same
deployment identity with no switch between observations:

| Host | Result |
| --- | --- |
| `scholarzone-fwzj.vercel.app` | deployment URL, project, target, `gitSource.ref`, `gitSource.sha` all resolve and match master. **One** failure remains: `health revision 'ddcd9c3662f4' is not a full 40-character … SHA` |
| `scholarzone.vercel.app` | fails on missing `gitSource` **and** `unknown` revision |

**Four-way equality: FAIL — and correctly so.** `A == B` passes. `C` does not
exist and `D` is a 12-character truncation, because **PR #5 is still unmerged**
and master therefore still resolves its revision from the environment variable.
The gate is now capable of proving identity; it is reporting truthfully that the
deployed code cannot yet supply it.

## 6. Required output

```
Deployment Protection:
    PRESERVED

Exact deployment URL:
    USED

Authenticated runtime observation:
    PROVEN

Four-way equality:
    FAIL

Production writes:
    NONE

Remaining blocker (unchanged by this patch):
    PR #5 is unmerged, so master has no packaged build artefact and its runtime
    still reports a 12-character environment-variable prefix. This patch removed
    the observation blocker; it cannot supply a commit identity the deployed code
    does not yet carry.
```