-- Archive retention for scholarship_evidence rows removed by permanent
-- scholarship deletion (ScholarZone PR #107, P0: Gate 6 evidence retention).
--
-- The live scholarship_evidence table previously referenced scholarships.id
-- with ON DELETE CASCADE, so deleting a scholarship silently destroyed the
-- evidence used to authorize that deletion. This migration:
--
--   1. Re-points the live FK to ON DELETE NO ACTION (fail closed: deleting a
--      scholarship can no longer cascade-delete evidence).
--   2. Creates scholarship_evidence_archive, an immutable table holding a
--      byte-exact copy of every evidence row deleted with a scholarship.
--   3. Adds a database-enforced trigger making the archive immutable.
--
-- The migration is idempotent and preserves all existing rows and
-- relationships. Existing evidence rows are untouched; they reference live
-- scholarships and simply become subject to the stricter FK policy.
--
-- Downgrade: intentionally NOT provided. The archive is retained by design;
-- restoring ON DELETE CASCADE is not possible without destroying historical
-- evidence, so a downgrade is an irreversible data-loss operation.

-- 1. Drop any existing live FK on scholarship_evidence -> scholarships and
--    re-create it with ON DELETE NO ACTION. The DO block is name-agnostic so
--    the migration works whether the FK was created by migration
--    20261124_scholarship_evidence.sql (default PG name) or by the ORM
--    (explicit name).
DO $$
DECLARE
    live_fk_name text;
BEGIN
    SELECT con.conname INTO live_fk_name
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    WHERE con.contype = 'f'
      AND con.conrelid = 'scholarship_evidence'::regclass
      AND con.confrelid = 'scholarships'::regclass
    ORDER BY con.conname
    LIMIT 1;
    IF live_fk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE scholarship_evidence DROP CONSTRAINT %I', live_fk_name);
    END IF;
END $$;

ALTER TABLE scholarship_evidence
    ADD CONSTRAINT fk_scholarship_evidence_scholarship_id
    FOREIGN KEY (scholarship_id)
    REFERENCES scholarships(id)
    ON DELETE NO ACTION;

-- 2. Immutable archive of every retained evidence row.
--    original_evidence_id is the primary key of the original row; the unique
--    constraint plus ON CONFLICT DO NOTHING in the deletion flow make
--    retention idempotent: a retry cannot duplicate or overwrite history.
CREATE TABLE IF NOT EXISTS scholarship_evidence_archive (
    id SERIAL PRIMARY KEY,
    original_evidence_id INTEGER NOT NULL UNIQUE,
    original_scholarship_id INTEGER NOT NULL,
    scholarship_legacy_id INTEGER,
    application_cycle VARCHAR(128) NOT NULL,
    official_domain VARCHAR(255) NOT NULL,
    official_url VARCHAR(2048) NOT NULL,
    source_title VARCHAR(512) NOT NULL,
    deadline DATE,
    deadline_precision VARCHAR(32) NOT NULL DEFAULT 'day',
    supporting_excerpt TEXT NOT NULL,
    excerpt_hash VARCHAR(64) NOT NULL,
    retrieval_date DATE NOT NULL,
    reviewer VARCHAR(120) NOT NULL,
    decision VARCHAR(64) NOT NULL,
    provenance TEXT,
    -- SHA-256 over the exact copied evidence content (see
    -- closed_deletion._evidence_content_hash); stored so retention can be
    -- verified by re-reading the archive row.
    content_hash VARCHAR(64) NOT NULL,
    -- Stable execution identifier of the purge run that retained this row.
    archive_execution_id VARCHAR(128),
    preserved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_scholarship_evidence_archive_original_scholarship_id
    ON scholarship_evidence_archive (original_scholarship_id);
CREATE INDEX IF NOT EXISTS ix_scholarship_evidence_archive_content_hash
    ON scholarship_evidence_archive (content_hash);

-- 3. Database-enforced immutability: retained evidence content cannot be
--    updated or deleted. Audit metadata (archive_execution_id) may be
--    refined by a later successful purge run, but every evidence-content
--    column is locked to its original value.
CREATE OR REPLACE FUNCTION protect_scholarship_evidence_archive() RETURNS trigger AS $protect$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'scholarship_evidence_archive is immutable: retained historical evidence cannot be deleted';
    END IF;
    IF (OLD.original_evidence_id IS DISTINCT FROM NEW.original_evidence_id
        OR OLD.original_scholarship_id IS DISTINCT FROM NEW.original_scholarship_id
        OR OLD.scholarship_legacy_id IS DISTINCT FROM NEW.scholarship_legacy_id
        OR OLD.application_cycle IS DISTINCT FROM NEW.application_cycle
        OR OLD.official_domain IS DISTINCT FROM NEW.official_domain
        OR OLD.official_url IS DISTINCT FROM NEW.official_url
        OR OLD.source_title IS DISTINCT FROM NEW.source_title
        OR OLD.deadline IS DISTINCT FROM NEW.deadline
        OR OLD.deadline_precision IS DISTINCT FROM NEW.deadline_precision
        OR OLD.supporting_excerpt IS DISTINCT FROM NEW.supporting_excerpt
        OR OLD.excerpt_hash IS DISTINCT FROM NEW.excerpt_hash
        OR OLD.retrieval_date IS DISTINCT FROM NEW.retrieval_date
        OR OLD.reviewer IS DISTINCT FROM NEW.reviewer
        OR OLD.decision IS DISTINCT FROM NEW.decision
        OR OLD.provenance IS DISTINCT FROM NEW.provenance
        OR OLD.content_hash IS DISTINCT FROM NEW.content_hash) THEN
        RAISE EXCEPTION 'scholarship_evidence_archive is immutable: retained historical evidence cannot be updated';
    END IF;
    RETURN NEW;
END;
$protect$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_scholarship_evidence_archive_immutable ON scholarship_evidence_archive;
CREATE TRIGGER trg_scholarship_evidence_archive_immutable
    BEFORE UPDATE OR DELETE ON scholarship_evidence_archive
    FOR EACH ROW
    EXECUTE FUNCTION protect_scholarship_evidence_archive();
