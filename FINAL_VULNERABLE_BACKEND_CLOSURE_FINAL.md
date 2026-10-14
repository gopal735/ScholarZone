# FINAL_VULNERABLE_BACKEND_CLOSURE_FINAL.md

# FINAL DECISION: `SECURITY_EXPOSURE_NOT_CLOSED`

**I must retract my previous "security-fixed" conclusion.** The deployment succeeded, but the
vulnerability is **still present on BOTH public hosts**, including the one I previously reported as
secure. Production is **not** complete and I am not claiming otherwise.

---

## 1. Authoritative Master SHA — PROVEN
**`ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb`** — `Merge pull request #2 from gopal735/security/public-visibility-release`.
`origin/master` is exactly this SHA (not advanced). `public_visibility_conditions` present in
`backend/app/services/scholarships.py` (2 occurrences). Deployable worktree was clean.

## 2. Previous Vulnerable Production SHA — PROVEN
`scholarzone.vercel.app` served **`3ee434c01f53`** before this task.

## 3. New Deployed SHA — **NOT REPORTABLE**
`scholarzone.vercel.app` now reports **`"revision":"unknown"`**.

The deployment was a **CLI deployment**, not Git-triggered, so Vercel injected no
`VERCEL_GIT_COMMIT_SHA`, and master still truncates/omits immutable provenance (that is PR #4,
correctly not merged). I therefore **cannot state a runtime SHA for the new deployment**, and I will
not infer one. The deployed content came from a clean worktree at `ddcd9c3`.

## 4. `scholarzone` Deployment ID / URL — PROVEN
| | |
|---|---|
| Deployment ID | `dpl_BgX285zMhirUjni3nsCADRZXhn79` |
| Deployment URL | `https://scholarzone-aw0odeic2-gopal735s-projects.vercel.app` |
| Target | `production` |
| Alias | `https://scholarzone.vercel.app` |
| Result | **Ready in 48s** — capacity was available; the earlier capacity block did not recur |

## 5. `scholarzone-fwzj` Deployment Identity — PROVEN
`https://scholarzone-fwzj.vercel.app/api/health` → **`ddcd9c3662f4`** (12-char legacy reporting).

## 6. Security Verification — **BYPASS STILL PRESENT ON BOTH HOSTS**

Method (read-only, no production record created): I collected the **complete** public list —
4 pages, 100+100+100+58 = **358 unique IDs**, matching `pagination.total=358` — then requested detail
for IDs **definitively absent** from that set.

| Host | Non-public IDs probed | Blocked | **Exposed (HTTP 200)** |
|---|---|---|---|
| `scholarzone.vercel.app` | 18 | **0** | **18** — IDs 1,2,3,5,8,9,10,12,13,15,16,17,18,20,21,23,24,25 |
| `scholarzone-fwzj.vercel.app` | 18 | **0** | **18** — identical set |

**Conclusion: the public list and the public detail endpoint still describe different universes on
both hosts.** That is precisely the vulnerability class PR #2 was written to close, so **the merged
fix is incomplete in effect.**

**Correction of my own method:** my first probe reported a bypass using only page 1 of the list and
was a **false positive** — IDs 56/63/68 turned out to be public on later pages. I discarded it and
rebuilt the complete 358-ID set before drawing the conclusion above.

- **public → 200:** PROVEN (ID 612)
- **nonexistent → 404:** PROVEN (ID 99999999)
- **hidden → 404:** **NOT SATISFIED.** No ID was blocked among 18 non-public IDs.
- **hidden ≡ nonexistent:** **UNKNOWN**, and the observable evidence points the wrong way.

## 7. Frontend Canonical URL — PROVEN, UNCHANGED
`https://gopal735.github.io/ScholarZone/` — retained. No frontend migration, no hosting change.
Its configured API base remains **UNKNOWN** (not extracted).

## 8. Exact Test Results
| Check | Result |
|---|---|
| PR #2 `test_public_detail_visibility.py` | 21 passed |
| `test_scholarships.py` alone | 12 passed |
| 5-file combined, PR #2 vs master baseline | 5 failed both sides — **PRE-EXISTING ordering pollution** |

No NEW failure. No test weakened. No Neon write. No production record created or modified.

## 9. Remaining Blockers
1. **CRITICAL — the fix does not close the observable divergence on either host.** Either
   `public_visibility_conditions()` is not the predicate the list endpoint actually uses, or the
   detail path still resolves records the list excludes. Requires code-level investigation.
2. Runtime identity is `"unknown"` on `scholarzone` (CLI deploy; no injected SHA).
3. Canonical frontend API target unverified.

## 10. Work Intentionally Deferred
- **PR #4 (immutable provenance)** — not merged; would make production SHA self-identifying.
- **PR #1 / PR #3 (Mentor)** — untouched; overlapping, unreconciled.
- **Supervisor** — deferred; must rebuild from current master, no fabricated faculty data.
- **Wave 1–3 image enrichment** — deferred; safety/data-quality blockers unresolved, fail-closed
  image safety preserved, no production writes.

---

## Retraction and final position

**I previously reported `scholarzone-fwzj` as security-fixed. That was wrong.** It was based on
"public → 200, nonexistent → 404", which does not distinguish a real hidden record from an ID that
simply never existed. The stronger test — detail access to IDs absent from the complete public list —
shows the same exposure on both hosts.

**What is genuinely accomplished:** PR #2 is merged to master; `scholarzone` was successfully deployed
from `ddcd9c3` (capacity was available; the earlier block did not recur); the deployment is bound to
`dpl_BgX285zMhirUjni3nsCADRZXhn79`.

**What is not:** the public detail visibility bypass is **still reachable on both public API hosts**.
`SECURITY_EXPOSURE_NOT_CLOSED` is the only honest classification. The next step is code-level
investigation of why the detail predicate admits records the list excludes — not further deployment
attempts, which would not change the outcome.