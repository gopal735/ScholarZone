#!/usr/bin/env python3

import sys, os, json, hashlib, re

from datetime import datetime, timezone, date

from urllib.parse import urlparse

sys.path.insert(0, 'backend')

from app.database import get_session_factory

from app.services.closed_deletion import execute_deletion, save_report, ClosedScholarshipManifest

from app.models import PurgeExecutionLedger

from sqlalchemy import select, text, inspect



SCHEMA_VERSION_SUPPORTED = "1.0"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")



def _fail(msg):
    print('ERROR: ' + msg); sys.exit(1)


def _verify_write_identity(db):

    required = ["EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID",

                "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME",

                "EXPECTED_DATABASE_HOST"]

    for var in required:

        if not os.environ.get(var):

            _fail('missing required env ' + var)



    write_url = os.environ.get("SCHOLARZONE_DATABASE_URL", "")

    if not write_url:

        _fail('SCHOLARZONE_DATABASE_URL not set')

    parsed = urlparse(write_url)

    expected_user = parsed.username

    expected_host = parsed.hostname

    if not expected_host:

        _fail('invalid database URL host')

    expected_host_cfg = os.environ["EXPECTED_DATABASE_HOST"].strip().lower()

    if expected_host.strip().lower() != expected_host_cfg:

        _fail('database host mismatch')



    try:

        row = db.execute(text("""

            SELECT current_database() AS db_name,

                   current_user AS db_user,

                   inet_server_addr() AS server_addr,

                   inet_server_port() AS server_port,

                   current_setting('neon.project_id', true) AS project_id,

                   current_setting('neon.branch_id', true) AS branch_id,

                   current_setting('neon.branch_name', true) AS branch_name,

                   version() AS pg_version

        """)).mappings().first()

    except Exception as e:

        _fail('cannot read DB identity: ' + str(e))



    if row is None:

        _fail('cannot read DB identity')



    if row["db_name"] != os.environ["EXPECTED_DATABASE_NAME"]:

        _fail('database mismatch')

    if expected_user and row["db_user"] != expected_user:

        _fail('database user mismatch')

    if not row["project_id"] or row["project_id"] != os.environ["EXPECTED_NEON_PROJECT_ID"]:

        _fail('neon project mismatch')

    if not row["branch_id"] or row["branch_id"] != os.environ["EXPECTED_NEON_BRANCH_ID"]:

        _fail('neon branch mismatch')

    if not row["branch_name"] or row["branch_name"] != os.environ["EXPECTED_NEON_BRANCH_NAME"]:

        _fail('neon branch name mismatch')

    if row["server_addr"] is None or str(row["server_addr"]).strip() == "":

        _fail('database host identity unavailable')



def _verify_ledger_schema(db):

    bind = db.get_bind() if hasattr(db, "get_bind") else None

    if bind is None:

        _fail('no DB bind for ledger verification')

    inspector = inspect(bind)

    if not inspector.has_table("purge_execution_ledger"):

        _fail('purge_execution_ledger table missing')

    # Semantic uniqueness check via pg_constraint / pg_index
    try:
        rows = db.execute(text("""
            SELECT
                con.conname AS constraint_name,
                con.contype AS constraint_type,
                pg_get_constraintdef(con.oid) AS definition,
                (SELECT array_agg(att.attname ORDER BY u.ord)
                   FROM unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord)
                   JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = u.attnum) AS columns,
                pg_get_expr(con.conpred, con.conrelid) AS predicate
            FROM pg_constraint con
            WHERE con.conrelid = 'purge_execution_ledger'::regclass
              AND con.contype = 'u'
        """)).mappings().all()
    except Exception as e:
        _fail('cannot inspect ledger constraints: ' + str(e))

    # Also inspect indexes for unique indexes
    try:
        idx_rows = db.execute(text("""
            SELECT
                i.relname AS index_name,
                ix.indisunique AS is_unique,
                ix.indpred IS NOT NULL AS has_predicate,
                pg_get_indexdef(ix.indexrelid) AS definition,
                (SELECT array_agg(a.attname ORDER BY u.ord)
                   FROM unnest(ix.indkey) WITH ORDINALITY AS u(attnum, ord)
                   JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = u.attnum
                   WHERE u.attnum > 0) AS columns
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            WHERE ix.indrelid = 'purge_execution_ledger'::regclass
        """)).mappings().all()
    except Exception as e:
        _fail('cannot inspect ledger indexes: ' + str(e))

    # Build set of (columns tuple, predicate is None, is_unique) for both constraints and unique indexes
    unique_single_cols = set()
    for r in rows:
        cols = r.get("columns")
        pred = r.get("predicate")
        if isinstance(cols, (list, tuple)) and len(cols) == 1 and cols[0] in ("merge_commit_sha", "execution_key"):
            if not pred:  # unconditional
                unique_single_cols.add(cols[0])
    for r in idx_rows:
        if not r.get("is_unique"):
            continue
        cols = r.get("columns")
        if r.get("has_predicate"):
            continue
        if isinstance(cols, (list, tuple)) and len(cols) == 1 and cols[0] in ("merge_commit_sha", "execution_key"):
            unique_single_cols.add(cols[0])

    if "merge_commit_sha" not in unique_single_cols:
        _fail('purge_execution_ledger missing unconditional single-column unique on merge_commit_sha')
    if "execution_key" not in unique_single_cols:
        _fail('purge_execution_ledger missing unconditional single-column unique on execution_key')

    # Column presence
    cols = {c["name"] for c in inspector.get_columns("purge_execution_ledger")}

    required_cols = {"id","pr_number","merge_commit_sha","execution_key","manifest_sha256",

                     "manifest_schema_version","manifest_target_count","started_at","completed_at",

                     "execution_status","deleted_count","workflow_run_id","reference_date","audit_metadata"}

    if not required_cols.issubset(cols):

        _fail('purge_execution_ledger columns missing')



def _verify_manifest_artifact():

    manifest_path = "artifacts/deletion_manifest.json"

    metadata_path = "artifacts/manifest_metadata.json"

    if not os.path.exists(manifest_path) or not os.path.exists(metadata_path):

        _fail('manifest artifact missing')

    with open(manifest_path, "rb") as f:

        raw = f.read()

    try:

        manifest_data = json.loads(raw.decode("utf-8"))

    except Exception:

        _fail('invalid manifest JSON')

    try:

        with open(metadata_path) as f:

            metadata = json.load(f)

    except Exception:

        _fail('invalid manifest metadata JSON')

    if not isinstance(manifest_data, list):

        _fail('manifest must be a list')

    if not manifest_data:

        _fail('NO_TARGETS: empty manifest cannot authorize deletion')

    # IDs

    ids = []

    for rec in manifest_data:

        if not isinstance(rec, dict):

            _fail('invalid manifest record')

        if "scholarship_id" not in rec:

            _fail('missing scholarship_id')

        sid = rec["scholarship_id"]

        if isinstance(sid, bool) or not isinstance(sid, int) or sid <= 0:

            _fail('invalid scholarship_id')

        ids.append(sid)

    if len(ids) != len(set(ids)):

        _fail('duplicate scholarship_id in manifest')

    # Schema version

    schema_version = metadata.get("schema_version")

    if not schema_version or schema_version != SCHEMA_VERSION_SUPPORTED:

        _fail('unsupported or missing schema version')

    # Hash

    calculated = hashlib.sha256(raw).hexdigest()

    meta_hash = metadata.get("manifest_hash")

    if not meta_hash or calculated != meta_hash:

        _fail('manifest hash mismatch')

    # Trusted outputs (MANDATORY - no optional bypass)

    trusted_hash = os.environ.get("EXPECTED_MANIFEST_SHA256")

    if not trusted_hash:

        _fail('EXPECTED_MANIFEST_SHA256 not set')

    if not SHA256_RE.fullmatch(trusted_hash.strip().lower()):

        _fail('invalid EXPECTED_MANIFEST_SHA256 format')

    if trusted_hash.strip().lower() != calculated:

        _fail('trusted manifest hash mismatch')

    trusted_count_raw = os.environ.get("EXPECTED_MANIFEST_COUNT")

    if not trusted_count_raw:

        _fail('EXPECTED_MANIFEST_COUNT not set')

    try:

        trusted_count_int = int(trusted_count_raw)

    except (ValueError, TypeError):

        _fail('invalid EXPECTED_MANIFEST_COUNT')

    if isinstance(trusted_count_int, bool) or trusted_count_int <= 0:

        _fail('invalid EXPECTED_MANIFEST_COUNT')

    meta_count = metadata.get("manifest_target_count")

    if not isinstance(meta_count, int) or isinstance(meta_count, bool) or meta_count <= 0:

        _fail('invalid manifest target count')

    if meta_count != len(manifest_data):

        _fail('manifest target count mismatch')

    if trusted_count_int != len(manifest_data):

        _fail('trusted manifest count mismatch')

    trusted_schema = os.environ.get("EXPECTED_MANIFEST_SCHEMA_VERSION")

    if not trusted_schema:

        _fail('EXPECTED_MANIFEST_SCHEMA_VERSION not set')

    if trusted_schema != schema_version:

        _fail('trusted schema version mismatch')

    # Reference date

    ref_date_str = metadata.get("reference_date")

    if not ref_date_str:

        _fail('missing reference date')

    try:

        date.fromisoformat(ref_date_str)

    except (ValueError, TypeError):

        _fail('invalid reference date')

    trusted_ref = os.environ.get("EXPECTED_MANIFEST_REFERENCE_DATE")

    if not trusted_ref:

        _fail('EXPECTED_MANIFEST_REFERENCE_DATE not set')

    if trusted_ref != ref_date_str:

        _fail('trusted reference date mismatch')

    # generated_at

    if not metadata.get("generated_at"):

        _fail('missing generated_at')

    # MERGE_COMMIT_SHA validation (mandatory full SHA)

    merge_sha_env = os.environ.get("MERGE_COMMIT_SHA", "")

    if not merge_sha_env or not SHA_RE.fullmatch(merge_sha_env):

        _fail('invalid or missing MERGE_COMMIT_SHA')

    return manifest_data, metadata, ref_date_str



def main():

    sf = get_session_factory()

    merge_sha = os.environ.get('MERGE_COMMIT_SHA', '')

    if not merge_sha or not SHA_RE.fullmatch(merge_sha):

        _fail('MERGE_COMMIT_SHA not set or invalid')

    manifest_data, metadata, ref_date_str = _verify_manifest_artifact()

    manifest = [ClosedScholarshipManifest(**m) for m in manifest_data]

    reference_date = date.fromisoformat(ref_date_str)

    execution_key = 'pr107:' + merge_sha

    with sf() as db:

        _verify_write_identity(db)

        _verify_ledger_schema(db)

        existing = db.execute(select(PurgeExecutionLedger).where(PurgeExecutionLedger.merge_commit_sha == merge_sha)).scalar_one_or_none()

        if existing:

            print('ALREADY_EXECUTED: Purge already executed for merge commit ' + merge_sha); sys.exit(2)

        ledger = PurgeExecutionLedger(pr_number=107, merge_commit_sha=merge_sha, execution_key=execution_key,

            manifest_sha256=metadata.get('manifest_hash'), manifest_schema_version=metadata.get('schema_version'),

            manifest_target_count=metadata.get('manifest_target_count') or len(manifest),

            execution_status='started', workflow_run_id=os.environ.get('GITHUB_RUN_ID'), reference_date=ref_date_str)

        db.add(ledger); db.flush()

        report = execute_deletion(db, manifest, dry_run=False, reference_date=reference_date)

        if report.errors or report.skipped_scholarship_ids or report.skipped:

            db.rollback(); print('ERRORS: ' + str(report.errors or report.skipped_scholarship_ids)); sys.exit(1)

        ledger.execution_status = 'completed'

        ledger.completed_at = datetime.now(timezone.utc)

        ledger.deleted_count = report.deleted_scholarships

        report_path = 'deletion_report.json'

        save_report(report, report_path)

        with open(report_path) as f:

            report_data = json.load(f)

        report_data['merge_commit_sha'] = merge_sha

        report_data['executed_at'] = datetime.now(timezone.utc).isoformat()

        with open(report_path, 'w') as f:

            json.dump(report_data, f, indent=2, default=str)

        db.commit()

        print('deleted_count=' + str(report.deleted_scholarships))

        print('report_path=' + report_path)



if __name__ == '__main__':

    main()