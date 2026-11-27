-- Persistent authoritative evidence registry for Gate 6 (PR #107).
CREATE TABLE IF NOT EXISTS scholarship_evidence (
    id SERIAL PRIMARY KEY,
    scholarship_id INTEGER NOT NULL REFERENCES scholarships(id) ON DELETE NO ACTION,
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_scholarship_evidence_cycle
    ON scholarship_evidence (scholarship_id, application_cycle);

CREATE INDEX IF NOT EXISTS ix_scholarship_evidence_scholarship_id
    ON scholarship_evidence (scholarship_id);

CREATE INDEX IF NOT EXISTS ix_scholarship_evidence_deadline
    ON scholarship_evidence (deadline);
