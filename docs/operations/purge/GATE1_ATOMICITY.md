# GATE 1: SQL Atomicity Test

## Test Script: `gate1_test.sql`

Run against a disposable PostgreSQL 16 instance:
```bash
psql -v target_ids='ARRAY[2,54,59,62,103,382,492,496,497,510,521,556,563,583,587,588,592,594,624,626,642,651,652,655,657,662,666,677,711,724,788,1216,1218,1278]' -f gate1_test.sql
```

## Test Script: `gate1_test.py`

```bash
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test python gate1_test.py
```

## Test Coverage
- ✅ Pre-deletion target verification (34 IDs)
- ✅ Exact ID match (sorted canonical comparison)
- ✅ Zero remaining target IDs
- ✅ Total count verification (736 = 770 - 34)
- ✅ Rollback test (simulated assertion failure → rollback)
- ✅ Idempotency test (repeated DELETE returns 0 rows)

## Test Output (Expected)
```
=== GATE 1: ATOMICITY AND TARGET VALIDATION ===
Target IDs: [2, 54, 59, ...]
Count: 34

Pre-deletion count: 34/34
Deleted 34 rows
Deleted IDs match canonical list: PASS
Zero remaining targets: PASS
Total count verification: 736 - PASS
Rollback test: PASSED
Idempotency test: PASSED

✅ GATE 1 PASSED
```

## Rollback Test Details
1. Begin transaction
2. Create temp table with pre-state
3. Delete first 2 records
4. Force exception
6. Verify rollback restores all 34 records
6. Verify no partial deletion persisted

## CI Integration
```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test
    ports: ["5432:5432"]
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```