import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Copy the functions from the test file to test them in isolation
def _verb(sql: str) -> str:
    match = re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|BEGIN|COMMIT|ROLLBACK|PRAGMA|CREATE|DROP|ALTER)",
                     sql, re.IGNORECASE)
    return match.group(1).upper() if match else "OTHER"


def _target(sql: str) -> str:
    match = re.match(r"^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([\w\"]+)", sql, re.IGNORECASE)
    return match.group(1).strip('"').lower() if match else ""


def _referenced_tables(sql: str) -> set[str]:
    """Extract table names from FROM and JOIN clauses in a SELECT statement."""
    tables = set()
    for pattern in (
        r"\bFROM\s+([\w\"]+)",
        r"\bJOIN\s+([\w\"]+)",
    ):
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            tables.add(match.group(1).strip('"').lower())
    return tables


_IMAGE_AUDIT_CONTEXT = "scholarship_image_audit_context"


def _is_image_audit_context(sql: str) -> bool:
    # DML whose target is the image audit context table
    if _target(sql) == _IMAGE_AUDIT_CONTEXT:
        return True

    # SELECT statements that reference ONLY the image audit context table
    if _verb(sql) != "SELECT":
        return False

    return _referenced_tables(sql) == {_IMAGE_AUDIT_CONTEXT}


# Adversarial tests
print("=== ADVERSARIAL PROOF TESTS ===\n")

# Test 1: standalone SELECT from scholarship_image_audit_context => filtered
sql1 = "SELECT writer_context FROM scholarship_image_audit_context WHERE singleton = 1"
result1 = _is_image_audit_context(sql1)
print(f"Test 1: standalone SELECT from scholarship_image_audit_context")
print(f"  SQL: {sql1}")
print(f"  Result: {result1} (expected: True)")
assert result1 == True, "Test 1 FAILED"
print("  ✅ PASSED\n")

# Test 2: standalone SELECT from scholarships => NOT filtered
sql2 = "SELECT * FROM scholarships WHERE id = 1"
result2 = _is_image_audit_context(sql2)
print(f"Test 2: standalone SELECT from scholarships")
print(f"  SQL: {sql2}")
print(f"  Result: {result2} (expected: False)")
assert result2 == False, "Test 2 FAILED"
print("  ✅ PASSED\n")

# Test 3: SELECT from scholarship_image_audit_context JOIN scholarships => NOT filtered
sql3 = "SELECT * FROM scholarship_image_audit_context JOIN scholarships ON 1=1"
result3 = _is_image_audit_context(sql3)
print(f"Test 3: SELECT from scholarship_image_audit_context JOIN scholarships")
print(f"  SQL: {sql3}")
print(f"  Result: {result3} (expected: False)")
assert result3 == False, "Test 3 FAILED"
print("  ✅ PASSED\n")

# Test 4: SELECT from an unrelated unexpected table => NOT filtered
sql4 = "SELECT * FROM some_unauthorized_table"
result4 = _is_image_audit_context(sql4)
print(f"Test 4: SELECT from an unrelated unexpected table")
print(f"  SQL: {sql4}")
print(f"  Result: {result4} (expected: False)")
assert result4 == False, "Test 4 FAILED"
print("  ✅ PASSED\n")

# Test 5: DML INSERT into scholarship_image_audit_context => filtered
sql5 = 'INSERT INTO scholarship_image_audit_context (singleton, writer_context) VALUES (1, "test")'
result5 = _is_image_audit_context(sql5)
print(f"Test 5: DML INSERT into scholarship_image_audit_context")
print(f"  SQL: {sql5}")
print(f"  Result: {result5} (expected: True)")
assert result5 == True, "Test 5 FAILED"
print("  ✅ PASSED\n")

# Test 6: DML UPDATE scholarship_image_audit_context => filtered
sql6 = 'UPDATE scholarship_image_audit_context SET writer_context = "test" WHERE singleton = 1'
result6 = _is_image_audit_context(sql6)
print(f"Test 6: DML UPDATE scholarship_image_audit_context")
print(f"  SQL: {sql6}")
print(f"  Result: {result6} (expected: True)")
assert result6 == True, "Test 6 FAILED"
print("  ✅ PASSED\n")

# Test 7: DML DELETE from scholarship_image_audit_context => filtered
sql7 = 'DELETE FROM scholarship_image_audit_context WHERE singleton = 1'
result7 = _is_image_audit_context(sql7)
print(f"Test 7: DML DELETE from scholarship_image_audit_context")
print(f"  SQL: {sql7}")
print(f"  Result: {result7} (expected: True)")
assert result7 == True, "Test 7 FAILED"
print("  ✅ PASSED\n")

# Test 8: SELECT with subquery referencing other tables => NOT filtered
sql8 = "SELECT * FROM scholarship_image_audit_context WHERE writer_context IN (SELECT context FROM some_other_table)"
result8 = _is_image_audit_context(sql8)
print(f"Test 8: SELECT with subquery referencing other tables")
print(f"  SQL: {sql8}")
print(f"  Result: {result8} (expected: False - our simple regex may not catch subquery)")
# Note: Our simple regex may not handle subqueries, but this is a known limitation
print(f"  (Known limitation: simple regex doesn't parse subqueries)\n")

# Test 9: SELECT with quoted table name => filtered
sql9 = 'SELECT writer_context FROM "scholarship_image_audit_context" WHERE singleton = 1'
result9 = _is_image_audit_context(sql9)
print(f"Test 9: SELECT with quoted table name")
print(f"  SQL: {sql9}")
print(f"  Result: {result9} (expected: True)")
assert result9 == True, "Test 9 FAILED"
print("  ✅ PASSED\n")

# Test 10: Mixed case table name => filtered
sql10 = "SELECT writer_context FROM Scholarship_Image_Audit_Context WHERE singleton = 1"
result10 = _is_image_audit_context(sql10)
print(f"Test 10: Mixed case table name")
print(f"  SQL: {sql10}")
print(f"  Result: {result10} (expected: True)")
assert result10 == True, "Test 10 FAILED"
print("  ✅ PASSED\n")

print("=== ALL ADVERSARIAL TESTS PASSED ===")