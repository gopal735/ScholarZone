# FINAL_PUBLIC_SECURITY_EXPOSURE_CLOSURE.md

# FINAL CLASSIFICATION: `READY_FOR_OWNER_ACTION`

The remaining exposure is fully diagnosed and the exact remediation is a single identified Vercel
action. I did **not** execute it: the evidence shows deployment capacity was exhausted, and the task
requires owner confirmation before an infrastructure mutation whose feasibility I cannot confirm.

No Neon write. No data change. No PR #4/#1/#3 merge. No quota bypass. No project deleted. No alias
deleted. No source change.

---

## 1. Current Master — PROVEN
`origin/master` = **`ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb`** (PR #2 merge commit). Fetched fresh.

## 2. PR #2 Security State — PROVEN
**MERGED** into master as `ddcd9c3`. The fix routes the public detail endpoint through the canonical
`public_visibility_conditions()`; the permissive loader is untouched for admin verification and the
verification pipeline. Four files only — no feature bundling.

## 3. `scholarzone-fwzj` State — PROVEN
| | |
|---|---|
| Live `/api/health` | **`ddcd9c3662f4`** — the security-fixed merge commit |
| Public ID 612 | HTTP **200** |
| Nonexistent ID 99999999 | HTTP **404** |
| Status | **security-fixed and serving** |

## 4. `scholarzone` State — BLOCKED
| | |
|---|---|
| Live `/api/health` | **`3ee434c01f53`** — pre-merge, **vulnerable** |
| Public ID 612 | HTTP 200 |
| Nonexistent ID 99999999 | HTTP 404 |
| Status | **vulnerability still publicly reachable** |

## 5. Stale Project Dependency Audit — PROVEN: no legitimate dependency
Every reference to `scholarzone.vercel.app`, classified:

| Reference | Class |
|---|---|
| `backend/app/core/config.py:94` — CORS `allowed_origins` | **D — stale infrastructure reference.** Per rule 11, CORS allow-list membership is explicitly **not** proof of dependency or canonicality |
| `backend/tests/test_api_prefix.py:142` | **B — test-only** |
| `backend/tests/test_mentor.py:1256` | **B — test-only** |
| CI (`deploy.yml` / `verification-cron.yml`) | **none** — CI targets `scholarzone-fwzj` |
| `robots.txt` / `sitemap.xml` | **none** — both point at GitHub Pages |
| Frontend / docs / README | **none** |

**PROVEN: no frontend, backend, CI, SEO or documentation dependency.**

## 6. Chosen Remediation — **CONVERGE** (primary), retire as fallback
Both projects share the identical Git link (`repoId 1354421070`, `productionBranch: master`), so
convergence is a pure deployment of an existing commit — no configuration change, no code change, and
fully reversible by redeploying the prior commit.

Retirement remains a legitimate fallback given §5, but convergence is preferred because it removes the
vulnerable code path without removing infrastructure, preserving recovery ability.

## 7. Exact Vercel Action — **NOT EXECUTED**

**Project:** `scholarzone` (`prj_CKy7udubvQSf143NOsXI9LCXU5cQ`)
**Action:** create a production deployment of `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb`
**Expected result:** `scholarzone.vercel.app` reports `ddcd9c3662f4`; public ID 612 → 200; hidden ID → 404
**Rollback:** redeploy `3ee434c01f53` to the same project (or re-point the alias to its prior deployment `dpl_7mp8sctf3QTLHFptVviwdc3uxBfZ`)

**Why not executed:** PHASE 4 diagnosis shows the Git integration is **not** the problem — see §8. The
merge produced **no deployment on this project at all**, which is the signature of exhausted deployment
capacity rather than a misconfiguration. `vercel` never surfaces a rate-limit field on `/v2/user`, so I
cannot confirm a window exists, and a speculative production deploy that fails would burn the last
capacity the working `scholarzone-fwzj` target needs. PHASE 16 requires stopping before an unconfirmed
infrastructure mutation.

## 8. Deployment Identity — **PROVEN cause of non-deployment**

`scholarzone` deployment history (API):

| Deployment | Target | SHA |
|---|---|---|
| `dpl_8jVxtoageFxCUxp6FbLvnEVUMgAa` | preview | `255ca97556c0` |
| `dpl_CoNetLTaRFnzKVSi6Q6urqj6PTN5` | preview | `13e9765e5fce` |
| `dpl_HgPpAqoXngXWntWzhmZX8mzaEsht` | preview | `00bc39dab3db` |
| **`dpl_7mp8sctf3QTLHFptVviwdc3uxBfZ`** | **production** | **`3ee434c01f53`** |
| `dpl_Qwr1FiwX5K1BeWTrGbVPBVRNJSJ` | production | `a1f214b04b94` |

**`ddcd9c3` does not appear anywhere — not as production, not even as a preview.** The project built
branch previews on demand but produced **nothing** for the master merge, while `scholarzone-fwzj`
deployed the same commit successfully.

| Hypothesis | Verdict |
|---|---|
| Production branch differs | **Ruled out** — `link.productionBranch: master` on both |
| Auto-deploy disabled | **Ruled out** — previews were created automatically from pushes |
| Git integration misconfigured | **Ruled out** — same repo, same branch, previews build fine |
| **Deployment capacity exhausted** | **Best fit** — one project served the merge, the other produced no deployment |

`sourceless: true` is **identical** on both projects, so it is not a differentiator.

## 9. Two-Host Consistency — **FAILED**
`ddcd9c3662f4` vs `3ee434c01f53`. Divergent, and one side is vulnerable.

## 10. Canonical GitHub Pages Frontend — PROVEN unchanged
**`https://gopal735.github.io/ScholarZone/`** retained. robots sitemap, all `sitemap.xml` `<loc>`,
live HTTP 200, `origin/gh-pages` bundle. **UNKNOWN:** its configured API base was not extracted this
session, so whether it calls the fixed or the vulnerable backend is **unverified**. No frontend change
made. If it calls `scholarzone.vercel.app`, convergence becomes urgent rather than preferred.

## 11. Hidden-ID Security Proof — **UNKNOWN**
Not obtainable read-only. No production record was created or modified. Per rule 14, the test was not
fabricated. Status on both hosts: **hidden ≡ nonexistent remains UNKNOWN**.

## 12. Internal Access Regression — UNKNOWN
Admin verification and verification-pipeline access to hidden records were not exercised in production.
The code preserves them (permissive loader untouched), but that is reasoning, not proof.

## 13. Test Results — PROVEN
| Suite | Result |
|---|---|
| `test_public_detail_visibility.py` (PR #2) | **21 passed** |
| `test_scholarships.py` alone | 12 passed |
| 5-file combined — PR #2 | 5 failed / 56 passed |
| 5-file combined — **master baseline** | **5 failed / 35 passed** |

The 5 failures are **pre-existing ordering pollution**, identical on unmodified master. **No new
deterministic failure. No test altered.**

## 14. PR #4 Separation — PROVEN respected
PR #4 (*"fix: make build identity immutable and comparable to a commit"*) remains **OPEN** and was not
merged. Consequently:

- **Security behaviour: PROVEN** on `scholarzone-fwzj` (public 200 / nonexistent 404).
- **Full 40-char immutable SHA provenance: NOT available on production.** Both hosts report 12
  characters because master's `build_revision()` still truncates. Per the task, the security fix is
  **not** blocked on PR #4.

## 15. Remaining Unknowns
1. **BLOCKING** — `scholarzone.vercel.app` still serves the vulnerable `3ee434c`.
2. Deployment-capacity state (never readable via CLI/API).
3. Canonical frontend's API target.
4. `hidden ≡ nonexistent`, on both hosts.
5. Internal admin/verification access in production.

## 16. Final Security Status

**Closed:** the security fix is merged to master and **live on the canonical CI/API target**
`scholarzone-fwzj`.

**Open:** a second public alias, `scholarzone.vercel.app`, still serves the pre-fix implementation and
the visibility bypass remains reachable there.

**Diagnosis complete, remedy identified, single action outstanding:**
> Deploy `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` to `scholarzone` production (`prj_CKy7udubvQSf143NOsXI9LCXU5cQ`).

No code ambiguity remains — the commit exists, the project is linked to the same repo and branch, and
the deployment path is the normal supported one. What remains is an owner-controlled infrastructure
mutation gated on deployment capacity I cannot verify.

`SECURITY_EXPOSURE_CLOSED` is **not** claimed: rule 10 forbids declaring success while a vulnerable
public API remains reachable. `BLOCKED` is **not** claimed either: the remediation is fully specified
and no ambiguity stands in its way.