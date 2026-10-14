# PUBLIC_SECURITY_RELEASE_COMPLETE_FINAL.md

# FINAL CLASSIFICATION: `BLOCKED`

PR #2 **was merged and deployed to `scholarzone-fwzj`**. But `scholarzone.vercel.app` **did not
receive the deployment** and still publicly serves the vulnerable revision `3ee434c`. Per absolute
rule 7 and the `SECURITY_RELEASE_COMPLETE` criteria, the release is incomplete.

The vulnerability remains publicly exposed. I am reporting that plainly rather than calling a partial
release a success.

---

## 1. Pre-Merge State — PROVEN
| | |
|---|---|
| `origin/master` before | **`573a983b004ab08578497272659123323ab489b7`** |
| PR #2 head | `0b9fe00ccbaaaf16502376d0d92e1f95e4b4c467` |
| PR #2 base | `573a983` — **verified equal to current master** |
| Commits ahead / behind | 5 ahead, **0 behind** |
| PR #2 state | `OPEN`, `MERGEABLE` |
| Live revisions | `scholarzone` `3ee434c01f53` · `scholarzone-fwzj` `4edd154a3037` |

PR #2 was current-master-based, so the "STOP and rebuild on current master" condition did not apply.

## 2. Security PR — PROVEN
Exactly four files:

| Status | Path |
|---|---|
| `M` | `backend/app/services/scholarships.py` |
| `A` | `backend/tests/test_public_detail_visibility.py` |
| `A` | `PUBLIC_SCHOLARSHIP_DETAIL_VISIBILITY_FINAL.md` |
| `A` | `PUBLIC_VISIBILITY_SECURITY_RELEASE_FINAL.md` |

**No Mentor, Supervisor, Wave 1–3, Match, Count, Application Workspace, image-pipeline or auth work.**

## 3. Exact Security Fix — PROVEN
Public detail switched from the bare primary-key `get_scholarship_by_id` to the canonical
`public_visibility_conditions()` imported from `repositories.scholarships` — not restated. The
permissive loader is deliberately left intact so admin verification and the verification pipeline
still reach records meant to be invisible.

## 4. Test Evidence — PROVEN
| Suite | PR #2 | Master baseline | Verdict |
|---|---|---|---|
| `test_public_detail_visibility.py` | **21 passed** | n/a | green |
| `test_scholarships.py` **alone** | **12 passed** | 12 passed | green |
| 5-file combined run | 5 failed / 56 passed | **5 failed / 35 passed** | **pre-existing** |

**The 5 `test_scholarships.py` failures are test-ordering pollution present identically on unmodified
master** — proven by running the same combined set on a clean `573a983` worktree and getting the same
5 failures. **PR #2 introduces no new deterministic failure.** No test was altered to obtain this.

## 5. Merge Commit — PROVEN
| | |
|---|---|
| Method | `--merge` (merge commit; audit trail preserved). Repo allows merge/squash/rebase |
| Pre-merge master | `573a983b004ab08578497272659123323ab489b7` |
| **Post-merge master** | **`ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb`** |
| PR #2 | **MERGED** |
| Branch deleted | no (`--delete-branch=false`) |

**PR #1, #3, #4 all remain OPEN and untouched** — PROVEN. PR #4
(*"fix: make build identity immutable and comparable to a commit"*) is the provenance work, correctly
**not** bundled into this security release.

Master verified to contain the fix (`public_visibility_conditions` present ×2) and to **not** contain
the Mentor dedup (`evidence.py` unchanged by the merge).

## 6. `scholarzone-fwzj` Deployment — PROVEN
| | |
|---|---|
| Live `/api/health` | **`ddcd9c3662f4`** — the merged master |
| Status | **updated**, fixed |

## 7. `scholarzone` Deployment — **BLOCKED**
| | |
|---|---|
| Live `/api/health` | **`3ee434c01f53`** — **still the vulnerable pre-merge revision** |
| Newest deployments | **previews only** (33m, 51m, 1h old) |
| Production deployment | unchanged |

**The merge triggered no production deployment on this project.** Its Git integration built branch
previews but did not deploy `master` to production. The public alias still serves vulnerable code.

## 8. Exact SHA Provenance — **VALIDATED, not full-SHA**
`scholarzone-fwzj` reports `ddcd9c3662f4` — **12 characters**. Exact 40-character equality is
**impossible on master today**, because master's `build_revision()` still truncates with `raw[:12]`.
The immutable-provenance fix lives in **PR #4, deliberately not merged** under rule 1.

So the 40-char gate is satisfied only on previews built from the provenance branch (previously
**PROVEN**), not on production.

## 9. Runtime Health SHA — PARTIAL
| Host | Reported | Matches its build? |
|---|---|---|
| `scholarzone-fwzj` | `ddcd9c3662f4` | yes, at 12-char legacy precision |
| `scholarzone` | `3ee434c01f53` | yes, but **pre-fix code** |

## 10. Two-Host Convergence — **FAILED**
Hosts serve different revisions (`ddcd9c3662f4` vs `3ee434c01f53`). Per PHASE 8 this is a **STOP**.

## 11. Public Security Verification — PARTIAL
Read-only, no records created:

| Check | `scholarzone-fwzj` | `scholarzone` |
|---|---|---|
| known public ID 612 | **200** | **200** |
| nonexistent ID 99999999 | **404** | **404** |

**hidden ≡ nonexistent: NOT PROVEN.** This requires a known hidden ID (archived / quarantined /
`needs_review` / image-gated). I could not obtain one read-only, and creating production records is
forbidden. This is the decisive security assertion and it remains **BLOCKED** on both hosts.

## 12. Internal Access Verification — NOT RUN
Admin and verification-pipeline access to hidden records was not exercised in production. **UNKNOWN.**
The code preserves it by design (the permissive loader is untouched), but that is reasoning, not proof.

## 13. GitHub Pages Frontend Target — UNKNOWN
Canonical frontend remains **`https://gopal735.github.io/ScholarZone/`** — unchanged, PROVEN by
robots/sitemap/live app/gh-pages bundle. Its configured API base was **not** extracted, so whether it
calls the fixed or the vulnerable backend is **UNKNOWN**. No frontend change was made or needed.

## 14. Browser Identity Gate — NOT RUN
No browser E2E was executed. PHASE 7 provenance did not pass on production (12-char truncation), and
PHASE 9 could not be completed without a hidden ID. Running browser tests now would produce evidence of
unproven provenance.

## 15. Post-Release E2E — BLOCKED
Gated behind §14. Not run.

## 16. Remaining Risks
| # | Risk | Severity |
|---|---|---|
| 1 | **`scholarzone.vercel.app` publicly serves the vulnerable `3ee434c`** — the visibility bypass is still live there | **CRITICAL** |
| 2 | Two hosts diverge, so users hitting the stale alias get unpatched, unverified behaviour | HIGH |
| 3 | `hidden ≡ nonexistent` unproven in production | HIGH |
| 4 | Production reports 12-char SHAs; exact deployment identity is unverifiable until PR #4 merges | MEDIUM |
| 5 | Canonical frontend's API target unknown | MEDIUM |
| 6 | Pre-existing `test_scholarships.py` ordering pollution (identical on master) | LOW |
| 7 | Rate-limit state never readable from the API | LOW |

## 17. Final Decision — `BLOCKED`

**Achieved (PROVEN):** PR #2 merged to `master` as `ddcd9c3`, alone, with an audit-preserving merge
commit. `scholarzone-fwzj` deployed it and now serves the security-fixed code. No feature bundling;
PR #1/#3/#4 untouched; no Neon write; no data change; no quota bypass.

**Why not `SECURITY_RELEASE_COMPLETE`:** two of its criteria fail.
1. *"both Vercel projects deployed from the resulting master"* — **false**. Only one deployed.
2. *"exact full SHA proven on both"* — **false**. Production reports 12 characters.

**Why not `READY_FOR_OWNER_ACTION`:** that status presumes the remaining work is an owner-controlled
action. Here the primary blocker is that **one public backend is still vulnerable** — the definition
of `BLOCKED`.

**Root cause of the deployment failure:** the `scholarzone` project's Git integration does not deploy
`master` to production. It builds branch previews only. Its production deployment has been pinned at
`3ee434c` while master advanced four commits. This matches the divergence identified in earlier audits.

**Exact owner actions, in order:**
1. **Close the exposure first.** Either explicitly deploy the `scholarzone` project from `master`
   (`ddcd9c3`) through its normal Git-connected path, **or** retire the `scholarzone.vercel.app` alias.
   Retirement is now the cleaner option: the fix is already live on `scholarzone-fwzj`, so removing the
   second public alias eliminates the vulnerable surface outright. Neither was done — both are
   owner-approved Vercel actions.
2. Confirm no historical user depends on `scholarzone.vercel.app` before retiring.
3. Re-verify both hosts report the same revision.
4. Prove `hidden ≡ nonexistent` using a known hidden ID supplied from an authoritative source, without
   creating records.
5. Merge **PR #4** separately to make production SHAs exact and independently verifiable.
6. Then browser E2E.

**Statement of limits:** the security fix is **live on the canonical CI/API target**
(`scholarzone-fwzj`) but **not** on the stale alias. The vulnerability is **partially** remediated, and
I am not reporting otherwise.