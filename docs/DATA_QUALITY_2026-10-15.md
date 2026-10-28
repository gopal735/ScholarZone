# ScholarZone — Data quality findings from the live_upcoming package verification

Observed 2026-10-15 while verifying the data package against the live built app.
These are recorded, not fixed: they are catalogue data defects, and changing them
would require a write to the source database, which this task must not perform.

## 1. Mojibake in five scholarship titles (REAL, confirmed)

The following records contain UTF-8 text that was decoded as cp1252 and stored
double-encoded, so they render as `Ã¢â‚¬Â¦` / `â€` in the UI:

- `75` Global Futures Scholarship (South Asia) — University of Manchester
- `76` GREAT Scholarship for Bangladesh — University of Manchester
- `78` GREAT Scholarships 2026 — University of Edinburgh
- `544`, `545` (same pattern; titles not individually confirmed)

Confirmed two ways:
- Read directly from the committed `frontend/public/scholarships-snapshot.json`
  with a programmatic scan for `Ã` and `â€`.
- Rendered in the browser: the Manchester and Edinburgh headings displayed the
  mojibake inside `<h2>` elements.

Impact: user-visible garbled text on the homepage, catalogue cards, and the
detail pages of those five records. It does not affect visibility, and these
records remain public and indexable.

Recommended fix (data work, not done here): re-encode the stored title with
`title.encode("cp1252").decode("utf-8")` in a transaction, after confirming the
row's current value, and regenerate the snapshot.

## 2. The `live_upcoming` package is internally consistent (VERIFIED)

- `patch/new_records.json` holds 15 researched records; their titles match the
  15 database rows with `id >= 730` exactly (no orphans, no missing).
- All 15 are `status` `upcoming` or `open`, none archived or quarantined, so all
  are public.
- All 15 appear in the public snapshot and in the sitemap.
- `patch/logo_updates.json` holds 141 entries; all 141 rows exist in the
  database.
- The manifest records its own source hashes, including the research artifact
  `03aa36635f2d1728…` and the database hash at patch time.

The patch therefore looks like a genuine, traceable research package, but it has
been applied to the local database directly. It is not yet a version-controlled
artifact with an idempotent apply script, which is what this task's Phase 4 asks
for.

## 3. Snapshot privacy check

The snapshot exposes 35 keys per record: title/name, country, region, degree,
program type, funding, deadlines, eligibility, benefits, requirements, duration,
links, status, verification metadata and image provenance.

No user, applicant, email, saved/compare, admin or internal-note field is
present. `selection_notes` is the awarding body's published selection process,
not private data.
