# Verified scholarship ingestion

The only catalogue for verified scholarship records is
`backend/app/data/verified_scholarships.py`. Add one
`ScholarshipIngestionRecord` there for each scholarship whose information has
been reviewed against an official source.

## Required fields

- `name`
- `country`
- `degree_levels`
- `official_source_url` — a non-empty HTTPS URL and the unique identity

`funding_type` is required when adding a new record because the current public
API requires a funding label; it may be omitted for an update when the official
data supplied does not change the existing value. `is_verified` defaults to `True`. The ingestion service always sets
`last_verified_date` (and the API-compatible `last_verified_at`) to the day it
runs; do not supply a guessed verification date.

## Optional fields

Use only official, confirmed information for `region`, `duration`, `deadline`,
`application_period`, `eligibility_summary`, `coverage`,
`required_documents`, `catalogue_url`, `official_updates_url`, `notes`, and
the additional provider-detail fields supported by the record model. Omit an
unknown optional field; it remains empty in a new database row and is not
overwritten in an existing one.

The existing public API uses compatible names: `name` is returned as `title`,
`degree_levels` as `degree`, `funding_type` as `funding`,
`required_documents` as `documents`, and `deadline` as the display deadline.
Do not rename those API fields without a frontend migration.

## Example

```python
ScholarshipIngestionRecord(
    name="Global Korea Scholarship (GKS)",
    country="South Korea",
    degree_levels="UG (Bachelor's/Associate)",
    funding_type="Fully Funded",
    official_source_url="https://www.studyinkorea.go.kr",
    eligibility_summary="Use the current official yearly announcement.",
    coverage=["Only include official confirmed coverage here."],
    required_documents=["Only include official confirmed documents here."],
)
```

## Upsert and safety rules

The ingestion service validates the complete catalogue before writing. It then
uses `official_source_url` to find a record:

- a matching URL updates the existing row in place and preserves its ID;
- a missing URL creates one new row;
- duplicate URLs in the catalogue are rejected before writes, and the database
  unique constraint/index blocks duplicate stored URLs.

Only the EMJM and legacy KGSP aliases have migration metadata to attach their
already-existing pre-URL rows to their official URLs. Do not use name matching
for ordinary future records.

ICCR and DAAD currently have no official source URL in this project. They are
preserved by the bootstrap seed and must not be added to the verified catalogue
until their official data is supplied.

## Run and verify

From `backend/` with the project virtual environment active:

```powershell
python scripts/seed_real_scholarships.py
```

Expected repeat behavior is `Created 0 scholarship record(s); updated N
record(s).` Confirm the result through `GET /scholarships` and the individual
detail endpoints. For a direct SQLite check, query the `scholarships` table by
`official_source_url`; there must be at most one row per URL.
