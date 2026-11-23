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

UPDATE purge_execution_ledger
SET id = nextval('purge_execution_ledger_id_seq')
WHERE id IS NULL;

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
PY