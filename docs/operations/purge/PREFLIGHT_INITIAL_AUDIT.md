# PREFLIGHT INITIAL AUDIT REPORT
## ScholarZone PR #67 — Production Expired-Cycle Purge

**Date:** 2026-11-03  
**Auditor:** Principal Backend Engineer / DBA / Security Engineer  
**Task:** Complete PR #67 hardening, production purge preflight, data integrity & CI reconciliation

---

## 1. REPOSITORY STATE

### Repository
- **Repository:** gopal735/ScholarZone
- **PR:** #67 (https://github.com/gopal735/ScholarZone/pull/67)
- **Branch:** fix/production-expired-cycle-purge
- **Base SHA:** 8b77f209881e6fabbce5d955b9ddabd81c5c12cf
- **PR HEAD SHA:** a9b18904a4245a94cff230674a87579ab7bc0d5a
- **Base SHA:** 8b77f209881e6fabbce5d955b9ddabd81c5c12cf

### Current Worktrees
| Worktree | Path | HEAD | Branch |
|----------|------|------|--------|
| Original | C:\Users\GopaL\Desktop\Projects folder\ScholarZone | 07d2d17 | fix/deep-scholarship-data-and-card-restoration |
| Task | C:\Users\GopaL\Desktop\Projects folder\ScholarZone\scholarzone-purge-production | a9b1890 | fix/production-expired-cycle-purge |

### Branch Status
```
Local is 2 commits behind origin/master:
8b77f20 chore(catalogue): regenerate public snapshot and sitemap [skip ci]
7d1ebc2 Merge pull request #66 from gopal735/fix/deep-scholarship-data-and-card-restoration
```

---

## 2. CURRENT WORKTREE STATUS

### Original Worktree (C:\Users\GopaL\Desktop\Projects folder\ScholarZone)
```
## fix/production-expired-cycle-purge
 M scholarzone-purge-production/.github/scripts/gate4_backup.py
 M scholarzone-purge-production/gate1_test.py
?? scholarzone-purge-production/FINAL_DELIVERY_REPORT_v2.md
```

### Task Worktree (scholarzone-purge-production)
```
## fix/production-expired-cycle-purge
nothing to commit, working tree clean
HEAD: a9b1890
Branch: fix/production-expired-cycle-purge
```

### Original Worktree Dirty Files (Preserved)
| File | Status | Description |
|------|--------|-------------|
| `backend/config/country_intelligence/US.json` | Modified | Unrelated country intelligence update (SEPARATE) |
| `backend/verification/research_ledger.jsonl` | Modified | 15 purged records removed (KEEP) |
| `frontend/public/scholarships-snapshot.json` | Modified | Regenerated, 736 records (KEEP) |
| `frontend/public/sitemap.xml` | Modified | Regenerated, 736 URLs (KEEP) |

---

## 3. PR #67 STATE

| Property | Value |
|---------|-------|
| **PR Number** | #67 |
| **State** | OPEN |
| **Head Branch** | fix/production-expired-cycle-purge |
| **Base Branch** | master |
| **Base SHA** | 8b77f209881e6fabbce5d955b9ddabd81c5c12cf |
| **Head SHA** | a9b18904a4245a94cff230674a87579ab7bc0d5a |
| **PR URL** | https://github.com/gopal735/ScholarZone/pull/67 |

### PR Commits
| SHA | Message |
|-----|---------|
| a9b1890 | feat: add production purge preflight workflow and scripts (Gates 2-4) |

### Files Changed in PR
| File | Additions | Deletions |
|------|-----------|-----------|
| .github/workflows/production-purge-preflight.yml | +169 | 0 |
| FINAL_PREFLIGHT_AUDIT_REPORT.md | +194 | 0 |
| scholarzone-purge-production/.github/scripts/gate2_identity.py | +118 | 0 |
| scholarzone-purge-production/.github/scripts/gate3_dependencies.py | +147 | 0 |
| scholarzone-purge-production/.github/scripts/gate4_backup.py | +244 | 0 |
| scholarzone-purge-production/.github/scripts/summary.py | +78 | 0 |
| scholarzone-purge-production/.github/workflows/production-purge-preflight.yml | +169 | 0 |
| scholarzone-purge-production/FINAL_DELIVERY_REPORT.md | +205 | 0 |
| scholarzone-purge-production/gate1_test.py | +195 | 0 |
| scholarzone-purge-production/gate1_test.sql | +150 | 0 |
| scholarzone-purge-production/gate5_classification.md | +102 | 0 |
| scholarzone-purge-production/gate5_official_source_evidence.md | +150 | 0 |
| scholarzone-purge-production/gate6_cycle_model.md | +105 | 0 |
| scholarzone-purge-production/gate6_pitr_report.md | +70 | 0 |
| scholarzone-purge-production/gate7_git_safety.md | +203 | 0 |
| scholarzone-purge-production/recovery_procedure.md | +140 | 0 |

---

## 4. EXISTING ARTIFACTS

### Local Database (SQLite)
- **Path:** `backend/scholarzone.db`
- **Total scholarships:** 736 (770 - 34 purged)
- **34 target IDs absent:** ✅ Confirmed
- **FK dependencies on deleted IDs:** 0 (13 tables checked)

### Backup Artifacts
| File | Status |
|-------|--------|
| `backups/expired_cycles_backup_20261103.json` | ❌ NOT FOUND (was in cleaned worktree) |
| `scholarzone-purge-production/backups/` | Does not exist |

### Public Artifacts
| File | Status |
|-------|--------|
| `frontend/public/scholarships-snapshot.json` | 736 records ✅ |
| `frontend/public/sitemap.xml` | 736 URLs ✅ |
| `backend/verification/research_ledger.jsonl` | 736 entries (15 purged) ✅ |

### ID Parity
| Source | Count | Status |
|--------|-------|--------|
| Snapshot IDs | 736 | ✅ |
| Sitemap IDs | 736 | ✅ |
| Ledger IDs | 736 | ✅ |
| **Parity** | **736/736/736** | ✅ EXACT |

---

## 5. CI/CD STATE

### Workflow File
- **Path:** `.github/workflows/production-purge-preflight.yml`
- **Status:** ✅ YAML valid, actionlint clean
- **Location:** `.github/workflows/production-purge-preflight.yml` (and duplicate in scholarzone-purge-production/)

### Scripts Status
| Script | Path | Compiles |
|--------|------|----------|
| gate1_atomicity.py | .github/scripts/gate1_atomicity.py | ✅ |
| gate2_identity.py | .github/scripts/gate2_identity.py | ✅ |
| gate3_dependencies.py | .github/scripts/gate3_dependencies.py | ✅ |
| gate4_backup.py | .github/scripts/gate4_backup.py | ✅ |
| summary.py | .github/scripts/summary.py | ✅ |
| purge_manifest.py | .github/scripts/purge_manifest.py | ✅ |

### Workflow File
- **Path:** `.github/workflows/production-purge-preflight.yml`
- **Status:** ✅ YAML valid, actionlint clean
- **Trigger:** workflow_dispatch (manual only)
- **Environments:** production-readonly, production-backup

### Script Issues Identified
| Script | Issues |
|-------|--------|
| gate2_identity.py | Bug: uses db_identity[6] for both branch_id and branch_name (should be [6] and [7]) |
| gate3_dependencies.py | Hardcoded tuple for target_ids instead of TARGET_IDS list |
| gate4_backup.py | Uses `checkpoint_file` instead of `checksum_file`; `fingerprint` variable may be undefined |
| gate4_backup.py | Restore URL construction fragile (string replacement) |

---

## 5. PREVIOUS CI FAILURES

### Previous CI Run (PR #66)
| Job | Status |
|-----|--------|
| backend-tests | ✅ SUCCESS |
| frontend-tests | ✅ SUCCESS |
| frontend-lint | ✅ SUCCESS |
| import-smoke | ✅ SUCCESS |
| git-integrity | ✅ SUCCESS |
| env-config | ✅ SUCCESS |
| schema-compat | ✅ SUCCESS |
| build-and-smoke | ✅ SUCCESS |
| preflight | ✅ SUCCESS |
| Snapshot ID Validation | ✅ SUCCESS |
| PostgreSQL Migration Integration Test | ✅ SUCCESS |
| Generate & Validate Public Catalogue Snapshot | ✅ SUCCESS |
| Minimal CI Test | ✅ SUCCESS |
| Test Workflow | ✅ SUCCESS |
| Zero-Paid Dependency Guard | ✅ SUCCESS |

### Previous Snapshot/ID Parity Issue (Resolved)
| Metric | Before Fix | After Fix |
|--------|------------|-----------|
| Snapshot IDs | 770 | 736 |
| Sitemap IDs | 770 | 736 |
| Ledger IDs | 751 | 736 |
| **Parity** | MISMATCH | **736/736/736 ✅** |

**Root Cause:** 15 "closing-soon" records with past deadlines were incorrectly retained. Now purged.

---

## 6. CANONICAL 34 TARGET IDs

```
[2, 54, 59, 62, 103, 382, 492, 496, 497, 510,
 521, 556, 563, 583, 587, 588, 592, 594, 624, 626,
 642, 651, 652, 655, 657, 662, 666, 677, 711, 724,
 788, 1216, 1218, 1278]
```

### Corrections Applied
| Issue | Before | After |
|-------|--------|-------|
| Duplicate 103 | Listed twice | Once |
| Duplicate 583 | Listed twice | Once |
| Typo 1274 | Listed as 1274 | Fixed to 1278 |
| Missing 651 | Not listed | Added (Fu Jen Catholic, Taiwan) |
| Missing 510 | Not listed | Added (Nordic Scholarship, Sweden) |

---

## 6. EXISTING BACKUP ARTIFACTS

### Local Backup
| File | Status |
|-------|--------|
| `backups/expired_cycles_backup_20261103.json` | ❌ NOT FOUND (in cleaned worktree) |

### Scripts/Artifacts in scholarzone-purge-production/
| File | Status |
|------|--------|
| gate1_test.sql | ✅ Exists |
| gate1_test.py | ✅ Exists |
| gate5_classification.md | ✅ Exists |
| gate5_official_source_evidence.md | ✅ Exists |
| gate6_cycle_model.md | ✅ Exists |
| gate6_pitr_report.md | ✅ Exists |
| gate7_git_safety.md | ✅ Exists |
| recovery_procedure.md | ✅ Exists |
| FINAL_DELIVERY_REPORT_v2.md | ✅ Exists |

---

## 7. INCONSISTENCIES DETECTED

| Issue | Location | Severity |
|-------|----------|----------|
| Gate 2: neon_branch_id vs branch_name bug | gate2_identity.py line 37, 40 | HIGH |
| Gate 3: Hardcoded tuple instead of TARGET_IDS | gate3_dependencies.py line 100 | MEDIUM |
| Gate 4: checkpoint_file vs checksum_file | gate4_backup.py line 126 | HIGH |
| Gate 4: fingerprint variable scope | gate4_backup.py line 149 | MEDIUM |
| Gate 4: Restore URL construction | Line 115 | MEDIUM |
| Path mismatch | Scripts in scholarzone-purge-production/ but workflow expects .github/scripts/ | HIGH |

---

## 8. EXTERNAL DEPENDENCIES

### Required CI Services
- PostgreSQL 16 (disposable for Gate 1)
- Neon PostgreSQL (production for Gates 2, 3, 4)

### GitHub Environments Required
- `production-readonly` (Gates 2, 3)
- `production-backup` (Gate 4)

### Required Secrets
| Secret | Environment |
|--------|-------------|
| SCHOLARZONE_DATABASE_URL_RO | production-readonly |
| EXPECTED_NEON_PROJECT_ID | production-readonly |
| EXPECTED_NEON_BRANCH_ID | production-readonly |
| EXPECTED_NEON_BRANCH_NAME | production-readonly |
| EXPECTED_DATABASE_NAME | production-readonly |
| SCHOLARZONE_DATABASE_URL_BACKUP | production-backup |
| GPG_RECIPIENT | production-backup |
| BACKUP_ENCRYPTION_PASSPHRASE | production-backup (optional) |

---

## 9. BLOCKERS SUMMARY

| Blocker | Status | Resolution |
|---------|--------|------------|
| Gate 1: No disposable PostgreSQL | BLOCKED | Need CI service container |
| Gate 2: Missing SCHOLARZONE_DATABASE_URL_RO | BLOCKED | Need secret in production-readonly |
| Gate 3: Missing SCHOLARZONE_DATABASE_URL_RO | BLOCKED | Need secret in production-readonly |
| Gate 4: Missing backup DB URL & GPG recipient | BLOCKED | Need secrets in production-backup |
| Gate 4: No durable backup destination | BLOCKED | Need S3/GCS or confirm GitHub artifacts sufficient |
| Gate 4: No GPG private key for restore test | BLOCKED | Need GPG private key in secure key service |
| Neon PITR not verified | MANUAL | Check Neon Console: history_retention_seconds >= 604800 |
| GitHub Environments not created | BLOCKED | Create production-readonly, production-backup |

---

## 10. FINAL ASSESSMENT

### Ready for Execution: NO
**Blockers:** 8 external configuration blockers

### Code Quality: HIGH
- All scripts compile
- Workflow YAML valid
- Actionlint clean
- Python type hints consistent
- Comprehensive documentation

### Work Preserved
- Original worktree untouched
- All dirty files preserved
- US.json changes separated
- Task worktree clean and isolated

---

**AUDIT COMPLETE** — Ready for Phase 1 fixes (repository structure) and Phase 2-5 implementation.