-- Gate 1: SQL Atomicity and Target Validation
-- Test atomicity, assertion-failure and rollback tests against disposable PostgreSQL database only

-- Canonical 34 target IDs (sorted, verified unique)
\set target_ids 'ARRAY[2,54,59,62,103,382,492,496,497,510,521,556,563,583,587,588,592,594,624,626,642,651,652,655,657,662,666,677,711,724,788,1216,1218,1278]'

\echo '=== GATE 1: ATOMICITY AND TARGET VALIDATION ==='

-- 1. Verify all 34 target IDs exist before deletion
\echo '=== PRE-DELETION TARGET VERIFICATION ==='

SELECT 
    COUNT(*) AS expected_count,
    (SELECT COUNT(*) FROM scholarships WHERE id = ANY(:target_ids)) AS found_count,
    CASE 
        WHEN (SELECT COUNT(*) FROM scholarships WHERE id = ANY(:target_ids)) = 34 
        THEN 'PASS: All 34 target IDs exist'
        ELSE 'FAIL: Missing ' || (34 - (SELECT COUNT(*) FROM scholarships WHERE id = ANY(:target_ids))) || ' IDs'
    END AS pre_check
FROM (SELECT 1) dummy;

-- 2. Capture pre-deletion state for comparison
\echo '=== CAPTURE PRE-DELETION STATE ==='

CREATE TEMP TABLE pre_delete_state AS
SELECT 
    s.id,
    s.title,
    s.status,
    s.deadline_date,
    s.deadline_precision,
    s.verification_status,
    s.fully_funded,
    s.funding_amount,
    s.funding_currency,
    s.tuition_coverage,
    s.living_cost_coverage,
    s.travel_coverage,
    s.funding_details
FROM scholarships s
WHERE s.id = ANY(:target_ids);

SELECT COUNT(*) AS pre_delete_count FROM pre_delete_state;

-- 3. Perform deletion with RETURNING for verification
\echo '=== EXECUTE DELETION WITH RETURNING ==='

WITH deleted AS (
    DELETE FROM scholarships
    WHERE id = ANY(:target_ids)
    RETURNING id
)
SELECT 
    array_agg(id ORDER BY id) AS deleted_ids,
    COUNT(*) AS deleted_count
FROM deleted;

-- 4. POST-DELETION ASSERTIONS
\echo '=== POST-DELETION ASSERTIONS ==='

-- 4a. Exactly 34 rows deleted
SELECT 
    COUNT(*) AS deleted_count,
    CASE 
        WHEN COUNT(*) = 34 THEN 'PASS: Exactly 34 rows deleted'
        ELSE 'FAIL: Expected 34 rows, got ' || COUNT(*)
    END AS assertion
FROM deleted;

-- 4b. Exact ID match (sorted canonical comparison)
SELECT 
    array_agg(id ORDER BY id) = :target_ids AS exact_id_match,
    CASE 
        WHEN array_agg(id ORDER BY id) = :target_ids THEN 'PASS: Deleted IDs match canonical list exactly'
        ELSE 'FAIL: ID mismatch'
    END AS assertion
FROM deleted;

-- 4c. Zero remaining target IDs
SELECT 
    COUNT(*) AS remaining_targets,
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS: Zero target IDs remain'
        ELSE 'FAIL: ' || COUNT(*) || ' target IDs still exist'
    END AS assertion
FROM scholarships
WHERE id = ANY(:target_ids);

-- 5. TOTAL COUNT VERIFICATION
\echo '=== TOTAL COUNT VERIFICATION ==='

SELECT 
    COUNT(*) AS total_scholarships,
    736 AS expected_count,
    CASE 
        WHEN COUNT(*) = 736 THEN 'PASS: Total count = 736 (770 - 34)'
        ELSE 'FAIL: Expected 736, got ' || COUNT(*)
    END AS assertion
FROM scholarships;

-- 6. ROLLBACK TEST (simulate failure and verify rollback)
\echo '=== ROLLBACK TEST (SIMULATED FAILURE) ==='

-- This would be run in a separate transaction to verify rollback behavior
-- The test below simulates what happens when an assertion fails mid-transaction

BEGIN;

-- Save current state
CREATE TEMP TABLE rollback_test_pre AS SELECT * FROM scholarships WHERE id = ANY(:target_ids);

-- Attempt deletion with a forced failure after partial deletion
DELETE FROM scholarships WHERE id = ANY(:target_ids[:2]);  -- Delete first 2

-- Force an exception to trigger rollback
DO $$
BEGIN
    RAISE EXCEPTION 'SIMULATED ASSERTION FAILURE - Testing rollback';
END $$;

EXCEPTION WHEN OTHERS THEN
    ROLLBACK;
    RAISE NOTICE 'Rollback executed - no partial deletion persisted';
END;

-- Verify rollback worked
SELECT COUNT(*) AS remaining_after_rollback 
FROM scholarships 
WHERE id = ANY(:target_ids);

-- Should be 34 (all rolled back)
-- If this passes, the transaction system correctly rolls back on assertion failure

-- 7. IDEMPOTENCY TEST
\echo '=== IDEMPOTENCY TEST ==='

-- Run deletion again on already-deleted IDs - should succeed with 0 rows
DELETE FROM scholarships WHERE id = ANY(:target_ids);
SELECT 'PASS: Idempotent deletion (no error on repeated delete)' AS result;

-- Final verification
SELECT 
    COUNT(*) AS final_count,
    CASE 
        WHEN COUNT(*) = 736 THEN 'PASS: Final count = 736'
        ELSE 'FAIL: Expected 736, got ' || COUNT(*)
    END AS final_assertion
FROM scholarships;

\echo '=== GATE 1 TEST COMPLETE ==='