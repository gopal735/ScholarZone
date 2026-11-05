# GATE 3: Complete Dependency Audit

## Overview
Gate 3 discovers ALL foreign key dependencies on `scholarships.id` dynamically and verifies zero references to the 34 target IDs.

## Implementation
**Script**: `.github/scripts/gate3_dependencies.py`

## Discovery Process

### 1. Dynamic FK Discovery
Queries `information_schema` to find ALL foreign keys referencing `scholarships.id`:
- Schema-qualified table names
- Referencing columns
- Referenced table/column
- ON DELETE / ON UPDATE behavior

### 2. CASCADE Detection
Scans ALL foreign keys for `ON DELETE CASCADE` behavior

### 3. Reference Counting
Counts references to the 34 target IDs across ALL referencing tables

### 4. Safety Decision
`safe_to_delete = (cascade_count == 0) AND (total_refs == 0)`

## Output
Produces `gate3_result.json`:
```json
{
  "fk_metadata": [...],
  "cascade_fk_count": 0,
  "cascade_details": [],
  "reference_counts": {"table.column": 0, ...},
  "total_references_to_targets": 0,
  "safe_to_delete": true
}
```

## Exit Codes
- `0`: Safe to delete (no cascade, zero refs)
- `1`: CASCADE found or references exist
- Other: Query error or permission issue

## Required Permissions
- Read-only access to `information_schema`
- `SELECT` on all referencing tables