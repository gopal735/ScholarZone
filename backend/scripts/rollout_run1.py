"""
CONTROLLED PRODUCTION ROLLOUT - Run 1
Batch size: 3 scholarships maximum
"""
import json
import logging
import sqlite3
import sys
import time
from datetime import date, datetime

# Configure logging to capture all telemetry
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rollout_run1.log', mode='w'),
    ]
)

# Import after logging setup
sys.path.insert(0, 'C:/Users/GopaL/Desktop/Projects folder/ScholarZone/backend')

from app.services.scheduler_config import SchedulerConfig
from app.services.scheduler_engine import SchedulerEngine
from app.database import get_session_factory

def main():
    print("=" * 70)
    print("CONTROLLED PRODUCTION ROLLOUT - RUN 1")
    print("=" * 70)

    # Pre-run state
    db = sqlite3.connect('scholarzone.db')
    db.row_factory = sqlite3.Row

    cur = db.cursor()
    cur.execute('SELECT COUNT(*) as cnt FROM scholarships')
    pre_total = cur.fetchone()['cnt']

    cur.execute('SELECT status, COUNT(*) as cnt FROM scholarships GROUP BY status')
    pre_status = {r['status']: r['cnt'] for r in cur.fetchall()}

    cur.execute('SELECT COUNT(*) as cnt FROM scholarship_verification_history')
    pre_history = cur.fetchone()['cnt']

    print(f"\nPRE-RUN STATE:")
    print(f"  Total scholarships: {pre_total}")
    print(f"  Status breakdown: {pre_status}")
    print(f"  Verification history entries: {pre_history}")

    # Get IDs that will be selected (first 3 due candidates)
    today = date.today().isoformat()
    cur.execute('''
        SELECT id, title, official_source_url
        FROM scholarships
        WHERE official_source_url IS NOT NULL
        AND (next_verification_due <= ? OR next_verification_due IS NULL)
        ORDER BY next_verification_due ASC
        LIMIT 3
    ''', (today,))
    selected = cur.fetchall()
    selected_ids = [r['id'] for r in selected]

    print(f"\nSELECTED SCHOLARSHIPS (will be processed):")
    for r in selected:
        print(f"  ID={r['id']}: {r['title'][:60] if r['title'] else 'N/A'}")
        print(f"    URL: {r['official_source_url'][:80] if r['official_source_url'] else 'N/A'}")

    # Capture pre-run field values for selected scholarships
    pre_fields = {}
    for sid in selected_ids:
        cur.execute('''
            SELECT id, title, status, is_verified, verification_status,
                   deadline_display, application_link, last_verified_at,
                   next_verification_due
            FROM scholarships WHERE id = ?
        ''', (sid,))
        row = cur.fetchone()
        if row:
            pre_fields[sid] = dict(row)

    db.close()

    # Start scheduler with batch_size=3
    print(f"\n{'='*70}")
    print(f"STARTING SCHEDULER (batch_size=3)")
    print(f"{'='*70}")

    config = SchedulerConfig(batch_size=3, max_workers=2)
    session_factory = get_session_factory()

    engine = SchedulerEngine(
        session_factory=session_factory,
        config=config,
    )

    start_time = datetime.now()
    print(f"  Start time: {start_time.isoformat()}")

    engine.start()

    # Process any due retries first
    retries = engine.process_due_retries()
    print(f"  Retries processed: {retries}")

    # Submit batch (this will process up to 3 scholarships)
    submitted = engine.submit_batch()
    print(f"  Jobs submitted: {submitted}")

    # Wait for completion
    engine.shutdown(wait=True)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"  End time: {end_time.isoformat()}")
    print(f"  Duration: {duration:.2f}s")

    # Post-run state
    print(f"\n{'='*70}")
    print(f"POST-RUN STATE")
    print(f"{'='*70}")

    db = sqlite3.connect('scholarzone.db')
    db.row_factory = sqlite3.Row

    cur = db.cursor()
    cur.execute('SELECT COUNT(*) as cnt FROM scholarships')
    post_total = cur.fetchone()['cnt']

    cur.execute('SELECT status, COUNT(*) as cnt FROM scholarships GROUP BY status')
    post_status = {r['status']: r['cnt'] for r in cur.fetchall()}

    cur.execute('SELECT COUNT(*) as cnt FROM scholarship_verification_history')
    post_history = cur.fetchone()['cnt']

    print(f"  Total scholarships: {post_total} (delta: {post_total - pre_total})")
    print(f"  Status breakdown: {post_status}")
    print(f"  Verification history entries: {post_history} (delta: {post_history - pre_history})")

    # Detailed changes for selected scholarships
    print(f"\nCHANGES FOR SELECTED SCHOLARSHIPS:")
    for sid in selected_ids:
        cur.execute('''
            SELECT id, title, status, is_verified, verification_status,
                   deadline_display, application_link, last_verified_at,
                   next_verification_due
            FROM scholarships WHERE id = ?
        ''', (sid,))
        row = cur.fetchone()
        post_fields = dict(row) if row else {}

        pre = pre_fields.get(sid, {})

        changes = []
        for key in post_fields:
            if key in pre and pre.get(key) != post_fields.get(key):
                changes.append(f"    {key}: {pre.get(key)} -> {post_fields.get(key)}")

        if changes:
            print(f"  ID={sid}: {post_fields.get('title', 'N/A')[:50]}")
            for c in changes:
                print(c)
        else:
            print(f"  ID={sid}: No field changes")

    # New verification history entries
    print(f"\nNEW VERIFICATION HISTORY ENTRIES:")
    cur.execute('''
        SELECT h.id, h.scholarship_id, h.field_name, h.old_value, h.new_value,
               h.change_type, h.verification_status, h.source_url, h.created_at
        FROM scholarship_verification_history h
        WHERE h.scholarship_id IN ({})
        ORDER BY h.created_at DESC
    '''.format(','.join('?' * len(selected_ids))), selected_ids)

    history_entries = cur.fetchall()
    if history_entries:
        for h in history_entries:
            print(f"  Scholarship {h['scholarship_id']}: {h['field_name']}")
            print(f"    old: {h['old_value']}")
            print(f"    new: {h['new_value']}")
            print(f"    status: {h['verification_status']}")
            print(f"    created: {h['created_at']}")
    else:
        print("  (none)")

    # Safety checks
    print(f"\n{'='*70}")
    print(f"SAFETY CHECKS")
    print(f"{'='*70}")

    # Check for duplicate records
    cur.execute('SELECT COUNT(*) as cnt FROM scholarships')
    final_count = cur.fetchone()['cnt']
    dup_check = "PASS" if final_count == pre_total else "FAIL"
    print(f"  [dup_check] Total records unchanged: {final_count} == {pre_total} -> {dup_check}")

    # Check for duplicate URLs
    cur.execute('''
        SELECT official_source_url, COUNT(*) as cnt
        FROM scholarships
        WHERE official_source_url IS NOT NULL
        GROUP BY official_source_url
        HAVING cnt > 1
    ''')
    dup_urls = cur.fetchall()
    url_check = "PASS" if len(dup_urls) == 0 else "FAIL"
    print(f"  [url_check] Duplicate URLs: {len(dup_urls)} -> {url_check}")

    # Check for unexpected status changes
    status_changed = False
    for sid in selected_ids:
        cur.execute('SELECT status FROM scholarships WHERE id = ?', (sid,))
        row = cur.fetchone()
        pre = pre_fields.get(sid, {})
        if row and pre.get('status') != row['status']:
            status_changed = True
            print(f"  [status_check] ID {sid}: {pre.get('status')} -> {row['status']}")
    status_check = "INFO" if status_changed else "PASS"
    print(f"  [status_check] Status changes detected: {status_changed} -> {status_check}")

    # Check for new test records
    cur.execute('SELECT COUNT(*) as cnt FROM scholarships WHERE title LIKE "%test%" OR title LIKE "%TEST%" OR title LIKE "%Test%"')
    test_records = cur.fetchone()['cnt']
    test_check = "PASS" if test_records == 0 else "FAIL"
    print(f"  [test_check] Test records found: {test_records} -> {test_check}")

    # Check audit history integrity
    audit_check = "PASS"
    for sid in selected_ids:
        cur.execute('''
            SELECT COUNT(*) as cnt FROM scholarship_verification_history
            WHERE scholarship_id = ? AND field_name IS NOT NULL
        ''', (sid,))
        cnt = cur.fetchone()['cnt']
        if cnt > 0:
            # Verify each history entry has required fields
            cur.execute('''
                SELECT id, source_url, change_type FROM scholarship_verification_history
                WHERE scholarship_id = ?
            ''', (sid,))
            entries = cur.fetchall()
            for e in entries:
                if not e['source_url'] or not e['change_type']:
                    audit_check = "FAIL"
                    print(f"  [audit_check] ID {sid} history entry {e['id']} missing required fields")
    print(f"  [audit_check] Audit history integrity: {audit_check}")

    db.close()

    # Summary
    print(f"\n{'='*70}")
    print(f"RUN 1 SUMMARY")
    print(f"{'='*70}")
    print(f"  Start time: {start_time.isoformat()}")
    print(f"  End time: {end_time.isoformat()}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Scholarships selected: {len(selected_ids)}")
    print(f"  Jobs submitted: {submitted}")
    print(f"  Retries processed: {retries}")
    print(f"  New history entries: {post_history - pre_history}")
    print(f"  Total records delta: {post_total - pre_total}")
    print(f"\n  Safety checks:")
    print(f"    Duplicate records: {dup_check}")
    print(f"    Duplicate URLs: {url_check}")
    print(f"    Status changes: {status_check}")
    print(f"    Test records: {test_check}")
    print(f"    Audit integrity: {audit_check}")

    all_pass = all(x == "PASS" for x in [dup_check, url_check, test_check, audit_check])
    print(f"\n  RESULT: {'CLEAN' if all_pass else 'ISSUES DETECTED'}")

    return all_pass


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
