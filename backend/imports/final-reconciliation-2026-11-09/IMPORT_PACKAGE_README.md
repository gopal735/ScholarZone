# IMPORT PACKAGE README
**ScholarZone — Global Scholarship Audit Import Package**  
**Generated:** 2026-11-09 (Asia/Dhaka)  
**Audit:** GLOBAL_SCHOLARSHIP_FINAL_AUDIT_REPORT.md  

---

## PACKAGE OVERVIEW

This import package contains the complete, validated output of the independent audit of ScholarZone's scholarship catalogue against the research_ledger.jsonl (825 entries) and the live database (790 active records).

**Decision:** `RESEARCH_COMPLETE_WITH_MANUAL_REVIEW` — Import approved for verified corrections only; pending records blocked.

---

## FILE INVENTORY

| File | Purpose | Records | Import Ready |
|------|---------|---------|--------------|
| `verified_programmes.json` | All independently verified programmes (completed + pending matches) | 87 | Reference only |
| `import_ready_scholarships.json` | **Approved new programme inserts** | 6 | ✅ YES |
| `existing_cycle_updates.json` | **Approved cycle updates for existing records** | 19 | ✅ YES |
| `funding_corrections.json` | **Approved funding classification corrections** | 5 | ✅ YES |
| `discontinued_programmes.json` | **Approved lifecycle corrections (archive/discontinue)** | 2 | ✅ YES |
| `verification_pending.json` | Records requiring official verification | 46 | ❌ NO |
| `source_evidence.json` | Structured evidence for every claim | 666 | Reference only |
| `reconciliation_manifest.json` | Complete operation map for every record | 141 | Reference only |
| `import_validation_report.json` | Machine-readable validation results | 1 | Reference only |
| `GLOBAL_SCHOLARSHIP_FINAL_AUDIT_REPORT.md` | Human-readable complete audit report | 1 | Reference only |

---

## SCHEMA DEFINITION

All import records conform to the **ScholarZone Canonical Catalogue Contract** as defined in `backend/app/models.py` (`Scholarship` class) and `backend/app/schemas.py` (`ScholarshipResponse`).

### Key Fields (per model)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `title` | String(255) | YES | Canonical programme name |
| `country` | String(120) | YES | Host country (ISO-style) |
| `degree` | String(255) | YES | Study level(s) |
| `funding` | String(120) | YES | Funding label (e.g., "Fully Funded", "Partial") |
| `fully_funded` | Boolean \| Null | YES | Tri-state: true/false/null (UNKNOWN) |
| `funding_amount` | Numeric(12,2) | NO | Amount if known |
| `funding_currency` | String(8) | NO | ISO 4217 currency code |
| `funding_period` | String(64) | NO | e.g., "monthly", "annual", "total" |
| `tuition_coverage` | Boolean \| Null | NO | Explicit tuition coverage |
| `living_cost_coverage` | Boolean \| Null | NO | Explicit living cost coverage |
| `travel_coverage` | Boolean \| Null | NO | Explicit travel coverage |
| `official_source_url` | String(2048) | YES | Authoritative source (unique constraint) |
| `application_link` | String(2048) | NO | Direct application URL |
| `status` | String(20) | YES | open/upcoming/closing-soon/closed |
| `is_archived` | Boolean | YES | One-way archive flag |
| `deadline_date` | Date | NO | ISO 8601 deadline |
| `deadline_display` | Text | NO | Human-readable deadline |
| `deadline_precision` | String(16) | YES | exact/month/year/unknown |
| `region` | Text | NO | Geographical region |
| `eligibility` | JSON (list[str]) | NO | Eligibility criteria |
| `benefits` | JSON (list[str]) | NO | Benefits list |
| `funding_details` | JSON (list[dict]) | NO | Structured per-track funding |
| `official_details` | JSON (dict) | NO | What awarding body published |
| `applicant_utility` | JSON (dict) | NO | Derived guidance |
| `programme_verification` | JSON (dict) | NO | What was checked/confirmed |

### Import Record Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `operation` | String | NEW_INSERT / EXISTING_CYCLE_UPDATE / FUNDING_CORRECTION / LIFECYCLE_CORRECTION |
| `change_classification` | String | NEW_PROGRAMME_CANDIDATE / EXISTING_RECORD_CYCLE_UPDATE / FUNDING_CHANGE / LIFECYCLE_CHANGE |
| `catalogue_match` | String | EXACT_MATCH / HIGH_CONFIDENCE_DUPLICATE / NO_MATCH_FOUND_IN_INSPECTED_DATA |
| `existing_record_ids` | List[int] | Matched catalogue IDs |
| `verification_gaps` | List[str] | Fields not established |
| `evidence_notes` | List[str] | Source evidence summary |
| `date_checked` | String | ISO 8601 audit date |

---

## NULL / UNKNOWN HANDLING

| Field | Null Means | Example |
|-------|------------|---------|
| `fully_funded` | Funding scope not confirmed by official source | DAAD Scholarship → `false` (confirmed partial), ARES → `null` (unknown) |
| `deadline_date` | No specific deadline published | Rolling deadlines |
| `funding_amount` | Amount not published | Many government scholarships |
| `tuition_coverage` | Not confirmed | `null` = unknown, `false` = confirmed no coverage |
| `application_link` | No direct application URL | University-nominated only |

**Rule:** Never infer. Use `null` for UNKNOWN. Use `false` only when official source confirms absence.

---

## OPERATION TYPES

| Operation | Description | Trigger |
|-----------|-------------|---------|
| `NEW_INSERT` | Brand new programme not in catalogue | `catalogue_match = NO_MATCH_FOUND_IN_INSPECTED_DATA` |
| `EXISTING_CYCLE_UPDATE` | Update cycle dates/deadlines for existing record | `catalogue_match = EXACT_MATCH` + cycle changes |
| `FUNDING_CORRECTION` | Correct `fully_funded` or funding fields | Evidence contradicts current value |
| `LIFECYCLE_CORRECTION` | Change status to `discontinued` / `archived` | Official discontinuation confirmed |

---

## IMPORT ORDER (Critical)

**Execute in this exact sequence:**

1. **`LIFECYCLE_CORRECTION`** (`discontinued_programmes.json`) — Archive/discontinue records first
   - Vanier CGS (ID 729) → `discontinued`
   - NFP/OTS (ID 31) → `discontinued`

2. **`FUNDING_CORRECTION`** (`funding_corrections.json`) — Fix funding classifications
   - DAAD Scholarship (ID 3) → `fully_funded = false`
   - ARES Scholarships (ID 40) → `fully_funded = null`
   - NFP/OTS (ID 31) → `fully_funded = null`
   - Vanier CGS (ID 729) → `fully_funded = null`
   - Erasmus Mundus (ID 1) → `fully_funded = true`

3. **`EXISTING_CYCLE_UPDATE`** (`existing_cycle_updates.json`) — Update cycle info
   - 19 records with new 2027/28 cycle dates

4. **`NEW_INSERT`** (`import_ready_scholarships.json`) — Add new programmes
   - 6 records approved for insert

5. **Post-Import Deduplication** — Merge 5 duplicate pairs
   - Lund University (IDs 183, 753)
   - CBS Danish Gov (IDs 270, 1244)
   - UCPH Danish Gov (IDs 271, 760)
   - Stipendium Hungaricum (IDs 285, 1277)
   - Fulbright Foreign Student (IDs 1217, 1309)

---

## VALIDATION COMMANDS

```bash
# 1. Validate JSON syntax
python -m json.tool verified_programmes.json > /dev/null && echo "OK"
python -m json.tool import_ready_scholarships.json > /dev/null && echo "OK"
python -m json.tool existing_cycle_updates.json > /dev/null && echo "OK"
python -m json.tool funding_corrections.json > /dev/null && echo "OK"
python -m json.tool discontinued_programmes.json > /dev/null && echo "OK"

# 2. Schema validation (requires backend environment)
cd backend && python -c "
from app.models import Scholarship
from app.database import engine
from sqlalchemy.orm import Session
# Validate each import record against model
"

# 3. Duplicate check
python -c "
import json
for f in ['import_ready_scholarships.json', 'existing_cycle_updates.json']:
    data = json.load(open(f))
    urls = [r.get('official_programme_url') or r.get('official_source_url') for r in data]
    dupes = set([u for u in urls if urls.count(u) > 1])
    print(f'{f}: {len(dupes)} duplicate URLs')
"

# 4. Required fields check
python -c "
import json
required = ['canonical_programme_name', 'official_provider', 'destination_country', 'official_programme_url']
for f in ['import_ready_scholarships.json']:
    data = json.load(open(f))
    for i, r in enumerate(data):
        missing = [k for k in required if not r.get(k)]
        if missing:
            print(f'Record {i} missing: {missing}')
"

# 5. Date format check
python -c "
import json, re
date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
for f in ['import_ready_scholarships.json', 'existing_cycle_updates.json', 'funding_corrections.json']:
    data = json.load(open(f))
    for r in data:
        for k in ['deadline', 'opening_date', 'date_checked']:
            v = r.get(k)
            if v and not date_pattern.match(str(v)):
                print(f'Invalid date {k}={v} in {f}')
"
```

---

## REMAINING MANUAL REVIEWS

| File | Count | Action Required |
|------|-------|-----------------|
| `verification_pending.json` | 46 | Official Tier 1 verification required before import |
| `reconciliation_manifest.json` | 141 | Review all `MANUAL_REVIEW` operations |
| `source_evidence.json` | 666 | Cross-check evidence claims |

### Excluded from Import (Mission Scope)

The following pending new candidates are from **excluded regions** (Latin America, Middle East, Caribbean) and are NOT in `import_ready_scholarships.json`:

- OAS / CONICET / Chile / Brazil / Argentina / Colombia / Mexico programmes
- Middle East regional programmes

These require separate regional audit if scope expands.

---

## DRY-RUN RESULTS SUMMARY

| Metric | Value |
|--------|-------|
| Records Evaluated | 173 (6 insert + 19 cycle + 5 funding + 2 lifecycle + 141 reconciliation) |
| New Records Accepted | 6 |
| Existing Records Matched | 87 |
| Cycle Updates Proposed | 19 |
| Funding Corrections Proposed | 5 |
| Lifecycle Corrections Proposed | 2 |
| Duplicate Records Rejected | 5 pairs (10→5) |
| Pending Records Excluded | 734 |
| Final Projected Active Count | 789 |

---

## CONTACT / ESCALATION

**Audit Lead:** Principal Scholarship-Data Researcher / Data-Quality Engineer / PostgreSQL Architect / Backend Engineer / Release Auditor  
**Repository:** gopal735/ScholarZone  
**Branch:** feat/bd-journey-functional-repair  
**Date:** 2026-11-09  

**Do not import `verification_pending.json` records.**  
**Do not merge to production without manual review gate.**