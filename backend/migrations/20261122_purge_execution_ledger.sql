-- Migration: purge_execution_ledger
-- Version: 20261122
-- Purpose: Provision the dedicated purge execution ledger table for PR #107.
-- This migration is idempotent and does not modify scholarship data.

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
    deleted_count INTEGER NOT NULL DEFAULT 0
);

-- Unique constraints (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_purge_execution_ledger_merge_sha'
    ) THEN
        ALTER TABLE purge_execution_ledger
            ADD CONSTRAINT uq_purge_execution_ledger_merge_sha UNIQUE (merge_commit_sha);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_purge_execution_ledger_execution_key'
    ) THEN
        ALTER TABLE purge_execution_ledger
            ADD CONSTRAINT uq_purge_execution_ledger_execution_key UNIQUE (execution_key);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_purge_execution_ledger_merge_commit_sha
    ON purge_execution_ledger (merge_commit_sha);
CREATE INDEX IF NOT EXISTS ix_purge_execution_ledger_execution_key
    ON purge_execution_ledger (execution_key);
