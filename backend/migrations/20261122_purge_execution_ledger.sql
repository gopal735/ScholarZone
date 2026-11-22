-- Migration: purge_execution_ledger
-- Version: 20261122
-- Purpose: Provision the dedicated purge execution ledger table for PR #107.
-- Idempotent: safe to run repeatedly on PostgreSQL 16 and 18.

CREATE TABLE IF NOT EXISTS purge_execution_ledger (
    id SERIAL PRIMARY KEY,
    pr_number INTEGER,
    merge_commit_sha VARCHAR(64) NOT NULL,
    execution_key VARCHAR(128) NOT NULL,
    manifest_sha256 VARCHAR(64),
    manifest_schema_version VARCHAR(32),
    manifest_target_count INTEGER,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    execution_status VARCHAR(32) NOT NULL DEFAULT 'started',
    deleted_count INTEGER NOT NULL DEFAULT 0,
    workflow_run_id VARCHAR(64),
    reference_date VARCHAR(32),
    audit_metadata TEXT
);

-- Ensure every column exists even if the table was partially created earlier.
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS pr_number INTEGER;
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS merge_commit_sha VARCHAR(64);
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS execution_key VARCHAR(128);
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS manifest_sha256 VARCHAR(64);
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS manifest_schema_version VARCHAR(32);
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS manifest_target_count INTEGER;
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS execution_status VARCHAR(32);
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS deleted_count INTEGER;
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS workflow_run_id VARCHAR(64);
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS reference_date VARCHAR(32);
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS audit_metadata TEXT;

-- Backfill defaults for pre-existing rows where needed.
UPDATE purge_execution_ledger SET started_at = NOW() WHERE started_at IS NULL;
UPDATE purge_execution_ledger SET execution_status = 'started' WHERE execution_status IS NULL;
UPDATE purge_execution_ledger SET deleted_count = 0 WHERE deleted_count IS NULL;

-- Ensure NOT NULL constraints where the model requires them.
ALTER TABLE purge_execution_ledger ALTER COLUMN merge_commit_sha SET NOT NULL;
ALTER TABLE purge_execution_ledger ALTER COLUMN execution_key SET NOT NULL;
ALTER TABLE purge_execution_ledger ALTER COLUMN started_at SET NOT NULL;
ALTER TABLE purge_execution_ledger ALTER COLUMN started_at SET DEFAULT NOW();
ALTER TABLE purge_execution_ledger ALTER COLUMN execution_status SET NOT NULL;
ALTER TABLE purge_execution_ledger ALTER COLUMN execution_status SET DEFAULT 'started';
ALTER TABLE purge_execution_ledger ALTER COLUMN deleted_count SET NOT NULL;
ALTER TABLE purge_execution_ledger ALTER COLUMN deleted_count SET DEFAULT 0;

-- Unique constraints (scoped to this relation).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_purge_execution_ledger_merge_sha'
          AND conrelid = 'purge_execution_ledger'::regclass
    ) THEN
        ALTER TABLE purge_execution_ledger
            ADD CONSTRAINT uq_purge_execution_ledger_merge_sha UNIQUE (merge_commit_sha);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_purge_execution_ledger_execution_key'
          AND conrelid = 'purge_execution_ledger'::regclass
    ) THEN
        ALTER TABLE purge_execution_ledger
            ADD CONSTRAINT uq_purge_execution_ledger_execution_key UNIQUE (execution_key);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_purge_execution_ledger_merge_commit_sha
    ON purge_execution_ledger (merge_commit_sha);
CREATE INDEX IF NOT EXISTS ix_purge_execution_ledger_execution_key
    ON purge_execution_ledger (execution_key);
