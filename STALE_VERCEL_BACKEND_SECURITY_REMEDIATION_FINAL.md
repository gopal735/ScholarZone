# STALE_VERCEL_BACKEND_SECURITY_REMEDIATION_FINAL.md

# FINAL CLASSIFICATION: `READY_FOR_OWNER_ACTION`

**The vulnerability is on BOTH public backends, not just the "stale" one.** PR #2 (`0b9fe00`) is
unmerged, so the canonical visibility predicate exists on **neither** host. Merging PR #2 to master
converges *and* fixes both in a single normal Git-connected deployment, because both projects are
git-connected to `master`.

I did not merge or deploy: the rate-limit state could not be read, and merging to master triggers an
unreviewed production deployment of both projects. That is an owner decision.

No project deleted. No alias deleted. No setting changed. No Neon write. No quota bypass.

---

## 1. Current Master — PROVEN
`origin/master` = **`573a983`** (`docs: the wording fix is deployed and verified in production`).
Fetched fresh; unmodified. Security PR #2 head = **`0b9fe00`**, parent `1b259b9`, **not on master**.

## 2. Stale Project Identity — PROVEN
| | |
|---|---|
| Project | `scholarzone` · `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` |
| Repository | `gopal735/ScholarZone` (`1354421070`) — **same repo as the canonical project** |
| Production branch | `master` (git-connected, `…-git-master-…` alias) |
| Production deployment | `scholarzone-bvl7g26in-…` |
| Served SHA (live) | **`3ee434c01f53`** |
| Aliases | `scholarzone.vercel.app`, `scholarzone-gopal735s-projects.vercel.app`, `scholarzone-git-master-…` |
| Custom domains | **none** |
| Tracking master | **no** — pinned at `3ee434c` |

## 3. Public Exposure — PROVEN
| Host | Live `/api/health` | Status |
|---|---|---|
| `scholarzone.vercel.app` | `3ee434c01f53` | **vulnerable** — predates the fix |
| `scholarzone-fwzj.vercel.app` | `4edd154a3037` | **also vulnerable** — predates the fix |

Live routes confirmed read-only on the stale host: `/api/health` 200, `/api/scholarships` 200,
`/api/mentor/overview` 200, `/api/dashboard/` 401, `/api/applications/` 401.

**Correction to the framing I was given:** the exposure is not confined to the stale host. `4edd154`
on the canonical project is a **later** commit than `3ee434c`, but the security fix is only on PR #2
and is on **neither**. Both public API targets are vulnerable until the fix reaches master.

## 4. User-Facing Dependency Analysis — PROVEN
| Reference | Verdict |
|---|---|
| `backend/app/core/config.py:94` — in `allowed_origins` (CORS) | **PROVEN reference** — the API accepts this origin. An allowlist entry, **not** evidence of user traffic or canonicality |
| `backend/tests/test_api_prefix.py:142` — asserts that origin | test lock-in, not usage |
| `backend/tests/test_mentor.py:1256` — URL in a test fixture | test fixture, not usage |
| CI / deploy config | **not referenced** — CI targets `scholarzone-fwzj` |
| robots.txt / sitemap | **not referenced** — both point at GitHub Pages |
| Repository docs | **not referenced** |

**PROVEN: no legitimate independent role.** The only repository references are a CORS allowlist entry
and two test fixtures. There is no CI, SEO, or documentation dependency.

## 5. Canonical Frontend — PROVEN (unchanged)
**`https://gopal735.github.io/ScholarZone/`** — robots sitemap directive, all `sitemap.xml` `<loc>`
values, live HTTP 200, `origin/gh-pages` bundle. **Not moved. Not changed.**

## 6. Canonical Backend — VALIDATED as `scholarzone-fwzj`
CI target (`https://scholarzone-fwzj.vercel.app/api`), and it alone tracks master (4 master commits
ahead). **UNKNOWN:** the live gh-pages bundle's configured API base was not extracted this session, so
canonicality rests on CI + operational evidence rather than direct frontend configuration.

## 7. Convergence Analysis — **VIABLE and RECOMMENDED**
Requirements all satisfiable:

| Requirement | Status |
|---|---|
| Same Git repository | **PROVEN** — both `repoId 1354421070` |
| Same intended production branch | **PROVEN** — both `master` |
| Same security-fixed code | achievable via master, **not yet** — PR #2 unmerged |
| Exact deployment provenance | **PROVEN available** — `verify_release_identity.py` PASSES |

**Convergence is automatic once master carries the fix.** Both projects are git-connected to master,
so a master deployment updates **both**. No per-project action, no manual artefact, no stale-branch
deploy is needed.

## 8. Retirement Analysis — **NOT RECOMMENDED now**
Retiring the alias would remove one exposure but leave `scholarzone-fwzj` serving the *same*
vulnerable code, and would discard a project whose only defect is being behind. Phase 5's default —
prefer convergence when role is uncertain — applies. Retirement remains a reasonable *follow-up*
once both hosts are fixed and owner confirms no historical users.

## 9. Chosen Remediation — **CONVERGE VIA MASTER**
Merge **PR #2 alone** to `master`. Both projects then receive the same security-fixed revision through
the normal Git-connected path. Vulnerable code on `scholarzone.vercel.app` stops being served, and the
two hosts become consistent.

Not bundled: Mentor, Supervisor, Wave 1–3, Count, Match, UI redesign, or any data change.

## 10. Vercel Deployment — **NOT PERFORMED**
No deployment was attempted. Two independent reasons:

1. **Rate limit UNKNOWN** — `/v2/user` returned no rate-limit fields, so the state could not be read.
   Phase 6 forbids deploying while it may be active. **No quota bypass, alternate account, alternate
   project, or undocumented route was used.**
2. Merging to master triggers an **unreviewed production deployment of both projects**, which is an
   owner decision, not an agent one.

## 11. Exact SHA Proof — **PROVEN (capability), PENDING (post-merge)**
The mechanism is proven end to end on a real preview:

```
gitSource.sha / build-time / artifact / runtime / /api/health
  = 255ca97556c0d3ad74a93d5644ea17e7d79e2d7f   (exact 40-char equality)
```
`verify_release_identity.py` → **PASS**, with negative tests proving it rejects a wrong or truncated
SHA. Post-convergence proof requires only re-running it against the new production deployment.

## 12. Security Verification — **BLOCKED** (pending deploy)
Cannot verify `hidden ≡ nonexistent` on either host because neither carries the fix. Planned
read-only checks on the canonical host post-merge: public → 200; hidden (archived, quarantined,
`needs_review`, image-gated) → 404; nonexistent → 404; hidden and nonexistent identical in status and
body; admin and verification paths still reach hidden records.

## 13. Both-Host Consistency — **BLOCKED** (pending deploy)
Currently divergent (`3ee434c` vs `4edd154`, and the latter alone carries `27047de`). Convergence via
master resolves this. Must be re-verified after deploy.

## 14. Rate Limit — **UNKNOWN**
Checked once; `/v2/user` returned empty rate-limit fields. Not confirmed active, not confirmed
cleared. **No conclusion in this report depends on it**, because no deployment was attempted.

## 15. Remaining Unknowns
1. Rate-limit state.
2. Canonical frontend's configured API base (backend canonicality rests on CI + operational evidence).
3. Whether GitHub Pages rewrites `/api` to that backend or serves a static snapshot.
4. Post-convergence security E2E and both-host consistency — not yet performed.

## 16. Final Release Status

**What is settled:**
- Both public backends are vulnerable; the stale one is not uniquely at fault.
- The stale project has **no legitimate independent role** — only a CORS allowlist entry and two test
  fixtures.
- Convergence requires **no per-project action**: merging PR #2 to master updates both.
- Exact deployment provenance is **proven and reusable** via a gate that has passed on a real preview
  and rejects wrong or truncated SHAs.

**Exact owner actions, in order:**
1. Confirm the Vercel quota window.
2. **Merge PR #2 alone to `master`.** Do not bundle anything.
3. Let the normal master Git deployment run — it updates **both** projects.
4. Verify the canonical backend:
   `python backend/scripts/verify_release_identity.py --sha <master-sha> --url <production-deployment-id>`
   → must PASS with exact 40-char equality.
5. Read-only security E2E on the canonical host: public 200; hidden 404; nonexistent 404; hidden ≡
   nonexistent; admin and verification paths still reach hidden records.
6. Confirm both hosts now report the identical revision.
7. *Optional follow-up:* with both hosts fixed and no historical users, retire the
   `scholarzone.vercel.app` alias.

**Status: `READY_FOR_OWNER_ACTION`.** The remediation is fully specified and every mechanism it
depends on is proven. What remains is a platform action — merging to master and letting Vercel deploy —
that I will not take unattended, because it publishes to production and the quota window is unconfirmed.

`RESOLVED` cannot be claimed: the vulnerable public backend is still exposed. `BLOCKED` would imply
the work cannot proceed; it can, the moment the owner merges.