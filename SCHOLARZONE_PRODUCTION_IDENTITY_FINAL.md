# SCHOLARZONE — PRODUCTION IDENTITY FINAL

| | |
| --- | --- |
| Gate | Post-merge production identity proof |
| Result | **RELEASE_IDENTITY_BLOCKED** |
| Reason | **PR #5 is not merged.** The gate stopped at the precondition. |

Labels: **PROVEN**, **UNPROVEN**, **BLOCKED**.

---

## 1. Preconditions — FAILED, gate stopped

| Check | Expected | Observed | Result |
| --- | --- | --- | --- |
| PR #5 state | MERGED | **OPEN** (`mergedAt` empty, `mergeCommit` empty) | **FAIL** |
| Master contains PR #5 | yes | head `01f128c` is **not** an ancestor of master | **FAIL** |
| Current master SHA | — | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` | recorded |
| Merge commit SHA | — | **none — no merge occurred** | — |
| Provenance implementation in master | present | **absent**: no `build_provenance.py`, `embed_build_revision.py`, `release_identity_gate.py` | **FAIL** |
| No later commit reverted it | — | **N/A — it was never merged** | — |

**PROVEN.** Master's `backend/app/main.py` still contains the pre-provenance
implementation: it iterates `("VERCEL_GIT_COMMIT_SHA", "VERCEL_GIT_COMMIT_REF")`
and its own comment still says *"falsified by hand"*. There is no packaged build
artefact in master, so **value C cannot exist**.

Per the brief: *"If PR #5 is NOT actually merged: STOP. FINAL CLASSIFICATION:
RELEASE_IDENTITY_BLOCKED."* The gate stopped here. No deployment was triggered.

## 2. Deployment capacity — read once

**PROVEN.** Read once, read-only. No deploy, no retry, no dummy commit, no
throwaway project, no quota bypass.

| Project | Check result |
| --- | --- |
| `scholarzone` | **pass** — "Deployment has completed" |
| `rc-revprov` | **pass** — "Deployment has completed" |
| `scholarzone-fwzj` | **fail** — "Deployment rate limited — retry in 24 hours" |

**Capacity is therefore partially available, and quota is NOT the blocker for this
gate.** Two of three projects deployed successfully. The blockers are the
unmerged PR and Deployment Protection (§4). Reporting quota as the blocker would
be inaccurate.

## 3. Canonical host — `scholarzone-fwzj.vercel.app`

Deployment identity (stable across **two** observations, no redeploy between them):

| Field | Expected | Observed | Result |
| --- | --- | --- | --- |
| master SHA (A) | 40-char lowercase hex | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` | **PROVEN** valid |
| deployment ID | — | `dpl_Fnk6fnJFbqYcFKriqwDhDr3Jbn7e` | **PROVEN** |
| project | `scholarzone-fwzj` | `scholarzone-fwzj` | **PROVEN** |
| target | production | `production` | **PROVEN** |
| gitSource.ref | `master` | `master` | **PROVEN** |
| gitSource.sha (B) | 40-char lowercase hex | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` | **PROVEN** valid |
| artifact SHA (C) | 40-char lowercase hex | **UNAVAILABLE** — no artefact exists in master | **FAIL** |
| runtime SHA (D) | 40-char lowercase hex | `ddcd9c3662f4` (**12 chars**) | **FAIL** |

**Four-way equality: FAIL.**
- `A == B` → **PASS** (both 40-char, identical)
- `B == C` → **FAIL** (C does not exist)
- `C == D` → **FAIL** (C does not exist)

D is a **truncated 12-character value**. Regex `^[0-9a-f]{40}$` → **INVALID**.
Per the failure matrix this is never a warning.

## 4. Deployment binding — exact URL is protected

**PROVEN.** Health was queried against the **exact deployment URL** returned by
the platform, not the alias:
`https://scholarzone-fwzj-qor3eneld-gopal735s-projects.vercel.app/api/health`

Result: the request returns Vercel's **"Protected Deployment"** interstitial (an
authentication login page, HTTP 404 for the API path), not the application's
`/health` payload.

**PROVEN.** This project has Vercel **Deployment Protection** enabled, so a
per-deployment URL cannot be read anonymously. Protection was **not** disabled —
doing so is explicitly forbidden, and would also invalidate the proof.

**Consequence (BLOCKED):** even with PR #5 merged, value **D cannot be obtained
from the exact deployment URL** without either bypassing protection or substituting
the alias. The brief forbids both as identity proof. This is a second, independent
blocker to the four-way proof as specified.

Alias-derived health was recorded for context only and is **not** offered as
identity proof: `scholarzone-fwzj.vercel.app/api/health` → `{"status":"ok","revision":"ddcd9c3662f4"}`.

## 5. Secondary host — `scholarzone.vercel.app`

Determined **independently**; not assumed to mirror the canonical host.

| Field | Expected | Observed | Result |
| --- | --- | --- | --- |
| deployment ID | — | `dpl_BgX285zMhirUjni3nsCADRZXhn79` | **PROVEN** |
| project | — | `scholarzone` | **PROVEN** |
| target | production | `production` | **PROVEN** |
| gitSource.ref | `master` | **empty** | **FAIL** |
| gitSource.sha (B) | 40-char | **empty** | **FAIL** |
| artifact SHA (C) | 40-char | **UNAVAILABLE** | **FAIL** |
| runtime SHA (D) | 40-char | `unknown` | **FAIL** |

**Classification: RELEASE_IDENTITY_UNPROVEN.** This deployment has **no git source
at all**, so per the brief it is rejected as production identity proof
(`gitSource == null` / `gitSource.sha` absent). Its runtime reports the literal
string `unknown`, which fails `^[0-9a-f]{40}$`.

Its exact deployment URL is likewise behind Deployment Protection.

**Stated explicitly:** this host is publicly reachable and carries no verifiable
build identity. Whether it is intentionally part of the release topology is
**UNKNOWN** and is an owner decision, not something this gate can settle.

## 6. Artifact proof

**UNPROVEN — impossible in the current state.** The runtime in master resolves its
revision from the **Vercel environment variable** at request time, not from a
packaged artefact:

```
for variable in ("VERCEL_GIT_COMMIT_SHA", "VERCEL_GIT_COMMIT_REF"):
```

There is no `app/build_revision.txt`, no build generator, and no runtime reader in
master. So the required property — *"Runtime must read provenance from packaged
build artifact, NOT Vercel environment variable"* — is **not satisfied by the
deployed code**, and cannot be until PR #5 is merged and deployed.

## 7. Security regression

**No public visibility predicate was modified. No regression check was run against
production data**, because the gate stopped at the precondition and the brief
restricts this task to identity verification.

**Preserved as UNKNOWN, exactly as instructed:** `hidden-vs-nonexistent production`.
The previously disputed ID set was **not** re-examined and **not** restated as a
finding.

**PROVEN — no production data mutation occurred:** no purge, no ingestion repair,
no image restoration, no record deletion, no maintenance data change, no image
record change, no Neon write.

## 8. Failure matrix

| Condition | Present? |
| --- | --- |
| `A != B` | no — equal |
| `B != C` | **YES** — C unavailable |
| `C != D` | **YES** — C unavailable |
| SHA truncated | **YES** — D is 12 chars on the canonical host |
| gitSource missing | **YES** — secondary host |
| gitSource.sha missing | **YES** — secondary host |
| artifact missing | **YES** — no artefact in master |
| wrong project | no |
| wrong deployment ID | no |
| target mismatch | no |
| runtime mismatch | **YES** — D is not 40 chars |

None of these are warnings. Any one of them is disqualifying.

## 9. Final output

```
FINAL CLASSIFICATION:
RELEASE_IDENTITY_BLOCKED

MASTER SHA:
ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb

CANONICAL HOST:
RELEASE_IDENTITY_BLOCKED
(scholarzone-fwzj.vercel.app - deployment dpl_Fnk6fnJFbqYcFKriqwDhDr3Jbn7e, gitSource.sha matches master exactly, but no packaged artefact exists and runtime reports a 12-character truncation)

SECONDARY HOST:
RELEASE_IDENTITY_UNPROVEN
(scholarzone.vercel.app - deployment dpl_BgX285zMhirUjni3nsCADRZXhn79, no gitSource.ref and no gitSource.sha, runtime reports "unknown")

FOUR-WAY EQUALITY:
FAIL

PROJECT BINDING:
PASS

DEPLOYMENT BINDING:
FAIL
(deployment IDs, targets and gitSource.ref resolve correctly, but the exact deployment URL is behind Vercel Deployment Protection and cannot be read without bypassing it)

PRODUCTION WRITES:
NONE

EXACT OWNER ACTION:
Merge pull request #5 (release/build-provenance-only -> master), then re-run this gate once a Git-integrated production deployment has completed.

REMAINING BLOCKERS:
1. PR #5 is OPEN, not merged - master contains no provenance implementation, so the packaged build artefact (C) cannot exist.
2. Vercel Deployment Protection prevents reading /health from an exact per-deployment URL, so the runtime identity (D) cannot be bound to a specific deployment without bypassing protection.
3. scholarzone.vercel.app has no gitSource and reports "unknown" - it is publicly reachable with no verifiable build identity, and whether it belongs in the release topology is undecided.
4. Deployment capacity is only partially available: scholarzone-fwzj still reports "Deployment rate limited - retry in 24 hours".
```