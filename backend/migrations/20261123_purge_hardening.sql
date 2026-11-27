-- Repair a partially initialized ledger table that lacks its primary key.
ALTER TABLE purge_execution_ledger ADD COLUMN IF NOT EXISTS id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_attrdef d
        JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE d.adrelid = 'purge_execution_ledger'::regclass
          AND a.attname = 'id'
    ) THEN
        CREATE SEQUENCE IF NOT EXISTS purge_execution_ledger_id_seq;
        ALTER TABLE purge_execution_ledger
            ALTER COLUMN id SET DEFAULT nextval('purge_execution_ledger_id_seq');
    END IF;
END $$;

-- Attach the sequence to the column if a default is missing entirely.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_attrdef d
        JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
        WHERE d.adrelid = 'purge_execution_ledger'::regclass
          AND a.attname = 'id'
    ) THEN
        CREATE SEQUENCE IF NOT EXISTS purge_execution_ledger_id_seq;
        ALTER TABLE purge_execution_ledger
            ALTER COLUMN id SET DEFAULT nextval('purge_execution_ledger_id_seq');
    END IF;
END $$;

-- Advance the sequence past the maximum existing ID BEFORE backfilling NULLs,
-- so nextval() never collides with an existing row. Never move it backwards.
DO $$
DECLARE
    max_id BIGINT;
    cur_val BIGINT;
BEGIN
    SELECT MAX(id) INTO max_id FROM purge_execution_ledger;
    SELECT last_value INTO cur_val FROM purge_execution_ledger_id_seq;
    IF max_id IS NOT NULL THEN
        IF cur_val IS NULL OR max_id >= cur_val THEN
            PERFORM setval('purge_execution_ledger_id_seq', max_id, true);
        END IF;
    ELSE
        IF cur_val IS NULL OR cur_val < 1 THEN
            PERFORM setval('purge_execution_ledger_id_seq', 1, false);
        END IF;
    END IF;
END $$;

UPDATE purge_execution_ledger
SET id = nextval('purge_execution_ledger_id_seq')
WHERE id IS NULL;

-- Re-synchronize after backfill (never move backwards).
DO $$
DECLARE
    max_id BIGINT;
    cur_val BIGINT;
BEGIN
    SELECT MAX(id) INTO max_id FROM purge_execution_ledger;
    SELECT last_value INTO cur_val FROM purge_execution_ledger_id_seq;
    IF max_id IS NOT NULL THEN
        IF cur_val IS NULL OR max_id >= cur_val THEN
            PERFORM setval('purge_execution_ledger_id_seq', max_id, true);
        END IF;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'purge_execution_ledger_pkey'
          AND conrelid = 'purge_execution_ledger'::regclass
    ) THEN
        ALTER TABLE purge_execution_ledger ADD PRIMARY KEY (id);
    END IF;
END $$;

-- Allow detached outreach history after a scholarship is permanently deleted.
ALTER TABLE professor_outreach_records
    ALTER COLUMN scholarship_id DROP NOT NULL;
