import re

with open('backend/app/database.py', 'r') as f:
    content = f.read()

# Find the first additions dict (PostgreSQL) - it's the one with image_url, is_archived, etc.
# We need to add legacy_id to it
old_additions = '''additions = {
            "image_url": "VARCHAR(2048)",
            "image_source_url": "VARCHAR(2048)",
            "image_source_type": "VARCHAR(32)",
            "image_kind": "VARCHAR(32)",
            "image_verified_at": "TIMESTAMPTZ",
            "image_alt_text": "VARCHAR(512)",
            "image_evaluation_status": "VARCHAR(32)",
            "image_evaluated_at": "TIMESTAMPTZ",
            # Archiving. NOT NULL with a default, so existing rows are
            # immediately, correctly un-archived rather than NULL, which would
            # make ``is_archived.is_(False)`` exclude the whole table.
            "is_archived": "BOOLEAN NOT NULL DEFAULT FALSE",
            "archived_at": "TIMESTAMPTZ",
            "archived_reason": "VARCHAR(120)",
            # Award economics, separated from the short ``funding`` label. See
            # the model for why a stipend must not read as full funding.
            "funding_amount": "NUMERIC(12, 2)",
            "funding_currency": "VARCHAR(8)",
            "funding_period": "VARCHAR(64)",
            # Tri-state, not a boolean: many programmes simply do not say.
            # A false here would be a claim the awarding body never made.
            "tuition_coverage": "BOOLEAN",
            "living_cost_coverage": "BOOLEAN",
            "travel_coverage": "BOOLEAN",
            # Tri-state: True = confirmed fully funded, False = confirmed not fully funded,
            # None = unknown/not confirmed. No default, so existing rows read as unknown.
            "fully_funded": "BOOLEAN",
            # Structured funding details per programme/track (JSON array)
            "funding_details": "JSON",
            # Structured detail, split by origin so published rules and derived
            # guidance are never stored as the same kind of fact.
            "official_details": "JSON",
            "applicant_utility": "JSON",
            "programme_verification": "JSON",
            # Automatic garbage collection of closed records. The candidate clock
            # is persisted because "held every condition continuously for the
            # grace period" is not derivable from any column already on the row.
            "auto_delete_candidate_since": "TIMESTAMPTZ",
            # Operator override, checked before every other condition.
            "deletion_protected": "BOOLEAN NOT NULL DEFAULT FALSE",
            # Academic eligibility - structured fields for departments, fields, programmes
            "departments": "JSON",
            "eligible_fields": "JSON",
            "eligible_programmes": "JSON",
            "academic_provenance": "JSON",
        }'''

new_additions = '''additions = {
            # Backward-compatible URL slugs for legacy links.
            "legacy_id": "INTEGER UNIQUE",
            "image_url": "VARCHAR(2048)",
            "image_source_url": "VARCHAR(2048)",
            "image_source_type": "VARCHAR(32)",
            "image_kind": "VARCHAR(32)",
            "image_verified_at": "TIMESTAMPTZ",
            "image_alt_text": "VARCHAR(512)",
            "image_evaluation_status": "VARCHAR(32)",
            "image_evaluated_at": "TIMESTAMPTZ",
            # Archiving. NOT NULL with a default, so existing rows are
            # immediately, correctly un-archived rather than NULL, which would
            # make ``is_archived.is_(False)`` exclude the whole table.
            "is_archived": "BOOLEAN NOT NULL DEFAULT FALSE",
            "archived_at": "TIMESTAMPTZ",
            "archived_reason": "VARCHAR(120)",
            # Award economics, separated from the short ``funding`` label. See
            # the model for why a stipend must not read as full funding.
            "funding_amount": "NUMERIC(12, 2)",
            "funding_currency": "VARCHAR(8)",
            "funding_period": "VARCHAR(64)",
            # Tri-state, not a boolean: many programmes simply do not say.
            # A false here would be a claim the awarding body never made.
            "tuition_coverage": "BOOLEAN",
            "living_cost_coverage": "BOOLEAN",
            "travel_coverage": "BOOLEAN",
            # Tri-state: True = confirmed fully funded, False = confirmed not fully funded,
            # None = unknown/not confirmed. No default, so existing rows read as unknown.
            "fully_funded": "BOOLEAN",
            # Structured funding details per programme/track (JSON array)
            "funding_details": "JSON",
            # Structured detail, split by origin so published rules and derived
            # guidance are never stored as the same kind of fact.
            "official_details": "JSON",
            "applicant_utility": "JSON",
            "programme_verification": "JSON",
            # Automatic garbage collection of closed records. The candidate clock
            # is persisted because "held every condition continuously for the
            # grace period" is not derivable from any column already on the row.
            "auto_delete_candidate_since": "TIMESTAMPTZ",
            # Operator override, checked before every other condition.
            "deletion_protected": "BOOLEAN NOT NULL DEFAULT FALSE",
            # Academic eligibility - structured fields for departments, fields, programmes
            "departments": "JSON",
            "eligible_fields": "JSON",
            "eligible_programmes": "JSON",
            "academic_provenance": "JSON",
        }'''

if old_additions in content:
    content = content.replace(old_additions, new_additions)
    with open('backend/app/database.py', 'w') as f:
        f.write(content)
    print("Successfully updated PostgreSQL additions dict")
else:
    print("Could not find the exact old_additions string")

# Now also update the SQLite additions dict
# Let's check if there's a similar one for SQLite
sqlite_old = '''additions = {
            # Mirrors of the PostgreSQL additions above. ``is_archived`` was the
            # load-bearing omission: ``public_visibility_conditions`` filters on
            # ``is_archived.is_(False)``, so its absence made every public list,
            # stats and detail query raise OperationalError on SQLite. NOT NULL with
            # a default, so existing rows read as correctly un-archived rather than
            # NULL, which the predicate would exclude.
            "is_archived": "BOOLEAN NOT NULL DEFAULT FALSE",
            "archived_at": "DATETIME",
            "archived_reason": "VARCHAR(120)",
            # Award economics, separated from the short ``funding`` label. See
            # the model for why a stipend must not read as full funding.
            "funding_amount": "NUMERIC(12, 2)",
            "funding_currency": "VARCHAR(8)",
            "funding_period": "VARCHAR(64)",
            # Tri-state, not a boolean: many programmes simply do not say.
            "tuition_coverage": "BOOLEAN",
            "living_cost_coverage": "BOOLEAN",
            "travel_coverage": "BOOLEAN",
            # Tri-state: True = confirmed fully funded, False = confirmed not fully funded,
            # None = unknown/not confirmed. No default, so existing rows read as unknown.
            "fully_funded": "BOOLEAN",
            # Structured funding details per programme/track (JSON array)
            "funding_details": "JSON",
            # Structured detail, split by origin so published rules and derived
            # guidance are never stored as the same kind of fact.
            "official_details": "JSON",
            "applicant_utility": "JSON",
            "programme_verification": "JSON",
            # Automatic garbage collection of closed records; see the model.
            "auto_delete_candidate_since": "DATETIME",
            "deletion_protected": "BOOLEAN NOT NULL DEFAULT FALSE",
            # Academic eligibility - structured fields for departments, fields, programmes
            "departments": "JSON NOT NULL DEFAULT '[]'",
            "eligible_fields": "JSON NOT NULL DEFAULT '[]'",
            "eligible_programmes": "JSON NOT NULL DEFAULT '[]'",
            "academic_provenance": "JSON",
        }'''

sqlite_new = '''additions = {
            # Backward-compatible URL slugs for legacy links.
            "legacy_id": "INTEGER UNIQUE",
            # Mirrors of the PostgreSQL additions above. ``is_archived`` was the
            # load-bearing omission: ``public_visibility_conditions`` filters on
            # ``is_archived.is_(False)``, so its absence made every public list,
            # stats and detail query raise OperationalError on SQLite. NOT NULL with
            # a default, so existing rows read as correctly un-archived rather than
            # NULL, which the predicate would exclude.
            "is_archived": "BOOLEAN NOT NULL DEFAULT FALSE",
            "archived_at": "DATETIME",
            "archived_reason": "VARCHAR(120)",
            # Award economics, separated from the short ``funding`` label. See
            # the model for why a stipend must not read as full funding.
            "funding_amount": "NUMERIC(12, 2)",
            "funding_currency": "VARCHAR(8)",
            "funding_period": "VARCHAR(64)",
            # Tri-state, not a boolean: many programmes simply do not say.
            "tuition_coverage": "BOOLEAN",
            "living_cost_coverage": "BOOLEAN",
            "travel_coverage": "BOOLEAN",
            # Tri-state: True = confirmed fully funded, False = confirmed not fully funded,
            # None = unknown/not confirmed. No default, so existing rows read as unknown.
            "fully_funded": "BOOLEAN",
            # Structured funding details per programme/track (JSON array)
            "funding_details": "JSON",
            # Structured detail, split by origin so published rules and derived
            # guidance are never stored as the same kind of fact.
            "official_details": "JSON",
            "applicant_utility": "JSON",
            "programme_verification": "JSON",
            # Automatic garbage collection of closed records; see the model.
            "auto_delete_candidate_since": "DATETIME",
            "deletion_protected": "BOOLEAN NOT NULL DEFAULT FALSE",
            # Academic eligibility - structured fields for departments, fields, programmes
            "departments": "JSON NOT NULL DEFAULT '[]'",
            "eligible_fields": "JSON NOT NULL DEFAULT '[]'",
            "eligible_programmes": "JSON NOT NULL DEFAULT '[]'",
            "academic_provenance": "JSON",
        }'''

if sqlite_old in content:
    content = content.replace(sqlite_old, sqlite_new)
    with open('backend/app/database.py', 'w') as f:
        f.write(content)
    print("Successfully updated SQLite additions dict")
else:
    print("Could not find the exact sqlite_old string")
"