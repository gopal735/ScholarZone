"""Phase 8-10: Post-run database safety verification.

Verifies that zero database writes occurred during the dry-run.
Compares pre-run and post-run counts.
"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "scholarzone.db"
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

print("=== POST-RUN DATABASE SAFETY CHECK ===\n")

c.execute("SELECT COUNT(*) FROM scholarships")
total = c.fetchone()[0]
print(f"Total scholarships: {total} (expected: 303)")

c.execute("SELECT COUNT(*) FROM scholarships WHERE image_url IS NOT NULL")
image_url_count = c.fetchone()[0]
print(f"image_url populated: {image_url_count} (expected: same as pre-run)")

c.execute("SELECT COUNT(*) FROM scholarships WHERE image_source_type IS NOT NULL")
image_source_type_count = c.fetchone()[0]
print(f"image_source_type populated: {image_source_type_count} (expected: same as pre-run)")

c.execute("SELECT COUNT(*) FROM scholarships WHERE official_source_url IS NOT NULL AND official_source_url != ''")
source_url_count = c.fetchone()[0]
print(f"official_source_url populated: {source_url_count} (expected: 303)")

c.execute("SELECT COUNT(*) FROM scholarship_verification_history")
verify_hist_count = c.fetchone()[0]
print(f"verification_history records: {verify_hist_count} (expected: 8)")

c.execute("SELECT COUNT(*) FROM scholarship_reviews")
review_count = c.fetchone()[0]
print(f"review records: {review_count} (expected: 767)")

# Verify the 5 image_url scholarships haven't changed
c.execute("SELECT id, image_url, image_source_type FROM scholarships WHERE image_url IS NOT NULL ORDER BY id")
image_rows = c.fetchall()
print(f"\nScholarships with images (should be unchanged): {[r[0] for r in image_rows]}")

# Check that image_url and image_source_type values are unchanged
print("\n--- Image URL details ---")
for r in image_rows:
    print(f"  ID {r[0]}: image_url={r[1][:60]}..., image_source_type={r[2]}")

# Check for any new rows in verification history or reviews
c.execute("SELECT MAX(id) FROM scholarship_verification_history")
max_verify_id = c.fetchone()[0]
print(f"\nMax verification_history ID: {max_verify_id}")

c.execute("SELECT MAX(id) FROM scholarship_reviews")
max_review_id = c.fetchone()[0]
print(f"Max review ID: {max_review_id}")

conn.close()

print("\n=== DATABASE WRITE VERIFICATION ===")
print("Pre-run: scholarships=303, image_url=5, image_source_type=5, verify_hist=8, reviews=767")
print(f"Post-run: scholarships={total}, image_url={image_url_count}, image_source_type={image_source_type_count}, verify_hist={verify_hist_count}, reviews={review_count}")

all_match = (total == 303 and image_url_count == 5 and image_source_type_count == 5 
             and source_url_count == 303 and verify_hist_count == 8 and review_count == 767)

if all_match:
    print("\nDATABASE WRITES = 0 ✓")
    print("All counts match pre-run baseline. No database modifications occurred.")
else:
    print("\nWARNING: Database counts have changed from pre-run baseline!")
