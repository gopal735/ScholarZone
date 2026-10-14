# Phase 3B — Concurrent Writer Forensic Audit

Generated: 2026-10-06 (read-only audit). No DB writes, no git mutations, no frontend/backup/report modifications.

## Task 1 — Row count
- `scholarships` rows now: **691** (matches Phase 3 post-repair count and PRE-PHASE3 snapshot: 691).
- `scholarship_verification_history` rows now: **723** (was 662 pre-Phase-3 → +61).

## Task 2 — Non-target scholarship changes
- **131 non-target scholarship rows** differ from the PRE-PHASE3 snapshot (Phase 3's incident note reported 67 — understated).
- Changed columns (excluding `updated_at`): `official_details` (131), `applicant_utility` (131), `programme_verification` (131), `verification_notes` (22), `verification_status` (20), `status` (16), `deadline_precision` (1), `official_source_url` (1).
- All 131 had `official_details` overwritten with a thin marker `{"depth": "full_deep_8"}` and `programme_verification` replaced with `{"depth": "full_deep_agent_8", "schema_version": "scholarzone-card-3.0", "checked_at": "2026-10-06"}` — i.e. the concurrent job **replaced curated JSON** on those fields.
- All 61 new verification-history rows map 1:1 onto 61 of these 131 rows.
- Updated-at clusters: 40 rows at `2026-10-06T15:39`, 2 at `16:01`, plus a spread through `15:39..16:06`; note 62 of the 131 rows changed content **without** an `updated_at` bump.
- Status transitions observed: 16 rows mostly `open/upcoming → closed` (ids 16, 50, 230, 317–321, …).
- `deadline_precision`: id 21 month→day. `official_source_url`: id 230 (DAAD) detail URL changed.
- Attribution: plausible for the same concurrent `bulk_official_fetch` + `full_deep_agent_8` agent pass; **not** attributable to Phase 3 (targets untouched, strings absent from tracked source, no test module builds the frontend).

## Task 3 — 61 verification history rows
- IDs **714–774** (61 rows), all `created_at = 2026-10-06 15:39:03` (identical timestamp).
- `field_name = bulk_official_fetch`, `change_type = updated`, `old_value = ""`, `new_value`: 44× `fetched_ok`, 17× `fetch_fail_code_None`, `verification_status = pending`, `confidence = medium`.
- `evidence_text` like `bulk fetch fetched_ok audit=no_DB_deadline_must_extract_official_only_no_fake`.
- Each carries a per-row `source_url` (e.g. MIT, JASSO, DAAD, MSCA).
- **No repo job writes these literals** (`bulk_official_fetch`, `fetched_ok`, `no_DB_deadline_must_extract_official_only_no_fake` absent from all tracked source). Matches a single external concurrent agent job, not Phase 3 pytest.

## Task 4 — Attribute exposure
- Affected: `status` (16), `verification_status` (20), `verification_notes` (22), `deadline_precision` (1), `official_source_url` (1), plus thin-overwrite of `official_details`/`applicant_utility`/`programme_verification` on 131 rows.
- **NOT** affected: `archived`, `deadline_date`, `funding_period`, funding amount fields, image fields, public-visibility flags.

## Task 5 — Phase 3 targets (162, 271, 272, 273, 285, 299, 356)
- All 7 rows intact; `updated_at` unchanged at `2026-10-05T14:39:34.*` (none touched after 2026-10-06T14:47).
- `299.deadline_date = 2026-03-31` preserved.
- Coimbra/uc.pt contamination: **0** rows. Prose in `deadline_date`: **0**. `funding_period='unknown'`: **0**.
- `english_requirement` NULL for 285 and 299. ✔
- Repaired fields (deadline/funding nulls from Phase 3) remain null.

## Task 6 — Stability
- Phase 3 repairs intact: YES.
- All concurrent changes fully attributable: NO (61 history rows + 15:39 batch attributable to one bulk-fetch agent; the 131-row curated-JSON overwrite and the 67→131 count discrepancy are not fully explained).
- Active writer: **codex PID 19540** (started 20:53:26 local) plus node PIDs 11948/21980 (20:53:30/32) were running before Phase 3 and are still running; DB mtime advanced to 22:08:28 local.
- No new rows/deletes/writes by this audit (0 mutations).

**FINAL STATUS: DB_STATE_UNCERTAIN**

## End-state accounting
- DATABASE WRITES: 0
- ROWS CREATED: 0
- ROWS DELETED: 0
- ROWS MODIFIED: 0
- PHASE3 TARGETS INTACT: YES
- ACTIVE WRITERS DETECTED: YES
- FINAL STATUS: DB_STATE_UNCERTAIN
