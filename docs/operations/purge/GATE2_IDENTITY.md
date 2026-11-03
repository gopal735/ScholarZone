# GATE 2: Production Identity Verification

## Overview
Gate 2 verifies the production database identity and confirms all 34 canonical scholarship records exist with correct metadata.

## Implementation

**Script**: `.github/scripts/gate2_identity.py`

### Required Environment Variables
- `SCHOLARZONE_DATABASE_URL_RO` - Read-only database connection string
- `EXPECTED_NEON_PROJECT_ID` - Expected Neon project ID
- `EXPECTED_NEON_BRANCH_NAME` - Expected branch name (default: "main")

### Required Database Role
- **Read-only role** with `CONNECT` and `SELECT` privileges only
- Connection must enforce `SET TRANSACTION READ ONLY`

### Verification Steps

1. **Database Identity Verification**
   - Database name
   - PostgreSQL version
   - Connected user
   - Server IP and port
   - Neon Project ID (`current_setting('neon.project_id')`)
   - Neon Branch ID (`current_setting('neon.branch_id')`)
   - Neon Branch Name (`current_setting('neon.branch_name')`)

2. **Identity Verification**
   - Neon Project ID must match `EXPECTED_NEON_PROJECT_ID`
   - Neon Branch Name must match `EXPECTED_NEON_BRANCH_NAME`

3. **Canonical ID Verification**
   - All 34 canonical IDs must exist
   - Return exact titles, statuses, deadlines, precision, verification status

### Output
Produces `gate2_result.json`:
```json
{
  "neon_project_id": "project-id",
  "neon_branch_id": "branch-id",
  "neon_branch_name": "main",
  "total_found": 34,
  "missing_ids": [],
  "all_present": true
}
```

### Exit Codes
- `0`: All 34 IDs present, identity verified
- `1`: Missing IDs or identity mismatch
- Other: Connection or query error

## Environment Requirements
- `SCHOLARZONE_DATABASE_URL_RO` - Read-only database URL
- `EXPECTED_NEON_PROJECT_ID` - Expected Neon project ID
- `EXPECTED_NEON_BRANCH_NAME` - Expected branch name (default: "main")

## CI Configuration
```yaml
environment: production-readonly
env:
  SCHOLARZONE_DATABASE_URL_RO: ${{ secrets.SCHOLARZONE_DATABASE_URL_RO }}
  EXPECTED_NEON_PROJECT_ID: ${{ secrets.EXPECTED_NEON_PROJECT_ID }}
  EXPECTED_NEON_BRANCH_NAME: main
```