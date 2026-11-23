#!/usr/bin/env python3

import sys, os, json, hashlib

from datetime import datetime, timezone, date

from urllib.parse import urlparse

sys.path.insert(0, 'backend')

from app.database import get_session_factory

from app.services.closed_deletion import execute_deletion, save_report, ClosedScholarshipManifest

from app.models import PurgeExecutionLedger

from sqlalchemy import select, text, inspect



SCHEMA_VERSION_SUPPORTED = "1.0"



def _verify_write_identity(db):

    required = ["EXPECTED_NEON_PROJECT_ID", "EXPECTED_NEON_BRANCH_ID",

                "EXPECTED_NEON_BRANCH_NAME", "EXPECTED_DATABASE_NAME",

                "EXPECTED_DATABASE_HOST"]

    for var in required:

        if not os.environ.get(var):

            print('ERROR: missing required env ' + var); sys.exit(1)



    write_url = os.environ.get("SCHOLARZONE_DATABASE_URL", "")

    if not write_url:

        print('ERROR: SCHOLARZONE_DATABASE_URL not set'); sys.exit(1)

    parsed = urlparse(write_url)

    expected_user = parsed.username

    expected_host = parsed.hostname

    if not expected_host:

        print('ERROR: invalid database URL host'); sys.exit(1)

    expected_host_cfg = os.environ["EXPECTED_DATABASE_HOST"].strip().lower()

    if expected_host.strip().lower() != expected_host_cfg:

        print('ERROR: database host mismatch'); sys.exit(1)



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

        print('ERROR: cannot read DB identity: ' + str(e)); sys.exit(1)



    if row is None:

        print('ERROR: cannot read DB identity'); sys.exit(1)



    if row["db_name"] != os.environ["EXPECTED_DATABASE_NAME"]:

        print('ERROR: database mismatch'); sys.exit(1)

    if expected_user and row["db_user"] != expected_user:

        print('ERROR: database user mismatch'); sys.exit(1)

    if not row["project_id"] or row["project_id"] != os.environ["EXPECTED_NEON_PROJECT_ID"]:

        print('ERROR: neon project mismatch'); sys.exit(1)

    if not row["branch_id"] or row["branch_id"] != os.environ["EXPECTED_NEON_BRANCH_ID"]:

        print('ERROR: neon branch mismatch'); sys.exit(1)

    if not row["branch_name"] or row["branch_name"] != os.environ["EXPECTED_NEON_BRANCH_NAME"]:

        print('ERROR: neon branch name mismatch'); sys.exit(1)

    if row["server_addr"] is None or str(row["server_addr"]).strip() == "":

        print('ERROR: database host identity unavailable'); sys.exit(1)



def _verify_ledger_schema(db):

    bind = db.get_bind() if hasattr(db, "get_bind") else None

    if bind is None:

        print('ERROR: no DB bind for ledger verification'); sys.exit(1)

    inspector = inspect(bind)

    if not inspector.has_table("purge_execution_ledger"):

        print('ERROR: purge_execution_ledger table missing'); sys.exit(1)

    ucs = {uc.get("name") for uc in inspector.get_unique_constraints("purge_execution_ledger")}

    indexes = inspector.get_indexes("purge_execution_ledger")

    unique_index_names = {ix.get("name") for ix in indexes if ix.get("unique")}

    required = {"uq_purge_execution_ledger_merge_sha", "uq_purge_execution_ledger_execution_key"}

    if not required.issubset(ucs | unique_index_names):

        print('ERROR: purge_execution_ledger unique constraints missing'); sys.exit(1)

    cols = {c["name"] for c in inspector.get_columns("purge_execution_ledger")}

    required_cols = {"id","pr_number","merge_commit_sha","execution_key","manifest_sha256",

                     "manifest_schema_version","manifest_target_count","started_at","completed_at",

                     "execution_status","deleted_count","workflow_run_id","reference_date","audit_metadata"}

    if not required_cols.issubset(cols):

        print('ERROR: purge_execution_ledger columns missing'); sys.exit(1)



def _verify_manifest_artifact():

    manifest_path = "artifacts/deletion_manifest.json"

    metadata_path = "artifacts/manifest_metadata.json"

    if not os.path.exists(manifest_path) or not os.path.exists(metadata_path):

        print('ERROR: manifest artifact missing'); sys.exit(1)

    with open(manifest_path, "rb") as f:

        raw = f.read()

    try:

        manifest_data = json.loads(raw.decode("utf-8"))

    except Exception:

        print('ERROR: invalid manifest JSON'); sys.exit(1)

    try:

        with open(metadata_path) as f:

            metadata = json.load(f)

    except Exception:

        print('ERROR: invalid manifest metadata JSON'); sys.exit(1)

    if not isinstance(manifest_data, list):

        print('ERROR: manifest must be a list'); sys.exit(1)

    if not manifest_data:

        print('ERROR: NO_TARGETS: empty manifest cannot authorize deletion'); sys.exit(1)

    # IDs

    ids = []

    for rec in manifest_data:

        if not isinstance(rec, dict):

            print('ERROR: invalid manifest record'); sys.exit(1)

        if "scholarship_id" not in rec:

            print('ERROR: missing scholarship_id'); sys.exit(1)

        sid = rec["scholarship_id"]

        if isinstance(sid, bool) or not isinstance(sid, int) or sid <= 0:

            print('ERROR: invalid scholarship_id'); sys.exit(1)

        ids.append(sid)

    if len(ids) != len(set(ids)):

        print('ERROR: duplicate scholarship_id in manifest'); sys.exit(1)

    # Schema version

    schema_version = metadata.get("schema_version")

    if not schema_version or schema_version != SCHEMA_VERSION_SUPPORTED:

        print('ERROR: unsupported or missing schema version'); sys.exit(1)

    # Hash

    calculated = hashlib.sha256(raw).hexdigest()

    meta_hash = metadata.get("manifest_hash")

    if not meta_hash or calculated != meta_hash:

        print('ERROR: manifest hash mismatch'); sys.exit(1)

    # Trusted outputs

    trusted_hash = os.environ.get("EXPECTED_MANIFEST_SHA256")

    if trusted_hash and trusted_hash != calculated:

        print('ERROR: trusted manifest hash mismatch'); sys.exit(1)

    trusted_count = os.environ.get("EXPECTED_MANIFEST_COUNT")

    try:

        trusted_count_int = int(trusted_count) if trusted_count is not None else None

    except (ValueError, TypeError):

        trusted_count_int = None

    meta_count = metadata.get("manifest_target_count")

    if not isinstance(meta_count, int) or meta_count <= 0:

        print('ERROR: invalid manifest target count'); sys.exit(1)

    if meta_count != len(manifest_data):

        print('ERROR: manifest target count mismatch'); sys.exit(1)

    if trusted_count_int is not None and trusted_count_int != len(manifest_data):

        print('ERROR: trusted manifest count mismatch'); sys.exit(1)

    trusted_schema = os.environ.get("EXPECTED_MANIFEST_SCHEMA_VERSION")

    if trusted_schema and trusted_schema != schema_version:

        print('ERROR: trusted schema version mismatch'); sys.exit(1)

    # Reference date

    ref_date_str = metadata.get("reference_date")

    if not ref_date_str:

        print('ERROR: missing reference date'); sys.exit(1)

    try:

        date.fromisoformat(ref_date_str)

    except (ValueError, TypeError):

        print('ERROR: invalid reference date'); sys.exit(1)

    trusted_ref = os.environ.get("EXPECTED_MANIFEST_REFERENCE_DATE")

    if trusted_ref and trusted_ref != ref_date_str:

        print('ERROR: trusted reference date mismatch'); sys.exit(1)

    # generated_at

    if not metadata.get("generated_at"):

        print('ERROR: missing generated_at'); sys.exit(1)

    return manifest_data, metadata, ref_date_str



def main():

    sf = get_session_factory()

    merge_sha = os.environ.get('MERGE_COMMIT_SHA', '')

    if not merge_sha:

        print('ERROR: MERGE_COMMIT_SHA not set'); sys.exit(1)

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
