"""Single source of truth for the supervisor-discovery DDL.

Two callers need this DDL and they must not disagree: the startup/dev upgrade
path in :mod:`app.database`, and the out-of-band production migration in
``backend/migrate_schema.py``. Writing the statements twice is how a column ends
up present in one path and absent in the other, which is invisible until a
production query fails on a field that validates fine locally. Both import from
here instead.

Every statement is additive and guarded, so applying this repeatedly is a no-op
and never rewrites existing data. No ``ALTER``, no ``DROP``, and no change to
``scholarships``: the catalogue table is not touched by this feature.

Types are chosen to behave identically on PostgreSQL and SQLite. ``JSON`` is used
rather than ``JSONB`` because the repository's export tooling rewrites ``JSON`` to
``JSONB`` and mixing the two across these tables is the documented source of
silent write differences.
"""

from __future__ import annotations

#: table name -> {"postgresql": column list, "sqlite": column list}
NEW_TABLE_DDL: dict[str, dict[str, str]] = {
    "contact_templates": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            template_key VARCHAR(64) NOT NULL,
            title VARCHAR(160) NOT NULL,
            degree_level VARCHAR(32),
            subject_hint VARCHAR(255),
            body_text TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_contact_templates_key UNIQUE (template_key)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_key VARCHAR(64) NOT NULL,
            title VARCHAR(160) NOT NULL,
            degree_level VARCHAR(32),
            subject_hint VARCHAR(255),
            body_text TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_contact_templates_key UNIQUE (template_key)
        """,
    },
    "scholarship_supervisor_coverage": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            status VARCHAR(32) NOT NULL DEFAULT 'search_pending',
            verified_supervisor_count INTEGER NOT NULL DEFAULT 0,
            evidence_state VARCHAR(32) NOT NULL DEFAULT 'not_collected',
            last_checked_at TIMESTAMPTZ,
            next_check_at TIMESTAMPTZ,
            last_error_summary TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_supervisor_coverage_scholarship UNIQUE (scholarship_id)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            status VARCHAR(32) NOT NULL DEFAULT 'search_pending',
            verified_supervisor_count INTEGER NOT NULL DEFAULT 0,
            evidence_state VARCHAR(32) NOT NULL DEFAULT 'not_collected',
            last_checked_at DATETIME,
            next_check_at DATETIME,
            last_error_summary TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_supervisor_coverage_scholarship UNIQUE (scholarship_id)
        """,
    },
    "professor_profiles": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            canonical_name VARCHAR(255) NOT NULL,
            title VARCHAR(120),
            institution_name VARCHAR(255) NOT NULL,
            department_name VARCHAR(255),
            official_profile_url VARCHAR(2048) NOT NULL,
            official_email VARCHAR(320),
            official_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            lab_url VARCHAR(2048),
            personal_academic_url VARCHAR(2048),
            research_areas JSON NOT NULL DEFAULT '[]',
            research_keywords JSON NOT NULL DEFAULT '[]',
            profile_status VARCHAR(32) NOT NULL DEFAULT 'active',
            last_verified_at TIMESTAMPTZ,
            next_verification_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_professor_official_profile_url UNIQUE (official_profile_url)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name VARCHAR(255) NOT NULL,
            title VARCHAR(120),
            institution_name VARCHAR(255) NOT NULL,
            department_name VARCHAR(255),
            official_profile_url VARCHAR(2048) NOT NULL,
            official_email VARCHAR(320),
            official_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            lab_url VARCHAR(2048),
            personal_academic_url VARCHAR(2048),
            research_areas JSON NOT NULL DEFAULT '[]',
            research_keywords JSON NOT NULL DEFAULT '[]',
            profile_status VARCHAR(32) NOT NULL DEFAULT 'active',
            last_verified_at DATETIME,
            next_verification_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_professor_official_profile_url UNIQUE (official_profile_url)
        """,
    },
    "scholarship_professor_links": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            relationship_type VARCHAR(40) NOT NULL,
            evidence_source_url VARCHAR(2048) NOT NULL,
            evidence_source_type VARCHAR(32) NOT NULL,
            evidence_quote_or_summary TEXT,
            retrieved_at TIMESTAMPTZ,
            verified_at TIMESTAMPTZ,
            verification_status VARCHAR(24) NOT NULL DEFAULT 'unverified',
            confidence INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_scholarship_professor_relationship
                UNIQUE (scholarship_id, professor_id, relationship_type)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            relationship_type VARCHAR(40) NOT NULL,
            evidence_source_url VARCHAR(2048) NOT NULL,
            evidence_source_type VARCHAR(32) NOT NULL,
            evidence_quote_or_summary TEXT,
            retrieved_at DATETIME,
            verified_at DATETIME,
            verification_status VARCHAR(24) NOT NULL DEFAULT 'unverified',
            confidence INTEGER,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_scholarship_professor_relationship
                UNIQUE (scholarship_id, professor_id, relationship_type)
        """,
    },
    "supervisor_source_evidence": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            scholarship_id INTEGER REFERENCES scholarships(id),
            link_id INTEGER REFERENCES scholarship_professor_links(id),
            source_url VARCHAR(2048) NOT NULL,
            source_host VARCHAR(255) NOT NULL,
            source_type VARCHAR(32) NOT NULL,
            retrieved_at TIMESTAMPTZ NOT NULL,
            verified_at TIMESTAMPTZ,
            verification_status VARCHAR(24) NOT NULL DEFAULT 'unverified',
            evidence_summary TEXT,
            http_status INTEGER,
            content_hash VARCHAR(64),
            CONSTRAINT uq_supervisor_evidence_professor_source
                UNIQUE (professor_id, source_url, source_type)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            scholarship_id INTEGER REFERENCES scholarships(id),
            link_id INTEGER REFERENCES scholarship_professor_links(id),
            source_url VARCHAR(2048) NOT NULL,
            source_host VARCHAR(255) NOT NULL,
            source_type VARCHAR(32) NOT NULL,
            retrieved_at DATETIME NOT NULL,
            verified_at DATETIME,
            verification_status VARCHAR(24) NOT NULL DEFAULT 'unverified',
            evidence_summary TEXT,
            http_status INTEGER,
            content_hash VARCHAR(64),
            CONSTRAINT uq_supervisor_evidence_professor_source
                UNIQUE (professor_id, source_url, source_type)
        """,
    },
    "professor_availability": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            scope VARCHAR(32) NOT NULL,
            state VARCHAR(24) NOT NULL DEFAULT 'unknown',
            source_url VARCHAR(2048) NOT NULL,
            verified_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_professor_availability_scope UNIQUE (professor_id, scope)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            scope VARCHAR(32) NOT NULL,
            state VARCHAR(24) NOT NULL DEFAULT 'unknown',
            source_url VARCHAR(2048) NOT NULL,
            verified_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_professor_availability_scope UNIQUE (professor_id, scope)
        """,
    },
    "professor_outreach_records": {
        "postgresql": """
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            application_id INTEGER,
            status VARCHAR(24) NOT NULL DEFAULT 'not_contacted',
            draft_subject VARCHAR(255),
            draft_body TEXT,
            first_contacted_at TIMESTAMPTZ,
            last_contacted_at TIMESTAMPTZ,
            follow_up_due_at TIMESTAMPTZ,
            response_status VARCHAR(24),
            response_at TIMESTAMPTZ,
            next_action VARCHAR(255),
            notes TEXT,
            template_id INTEGER REFERENCES contact_templates(id),
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_outreach_user_scholarship_professor
                UNIQUE (user_id, scholarship_id, professor_id)
        """,
        "sqlite": """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            scholarship_id INTEGER NOT NULL REFERENCES scholarships(id),
            professor_id INTEGER NOT NULL REFERENCES professor_profiles(id),
            application_id INTEGER,
            status VARCHAR(24) NOT NULL DEFAULT 'not_contacted',
            draft_subject VARCHAR(255),
            draft_body TEXT,
            first_contacted_at DATETIME,
            last_contacted_at DATETIME,
            follow_up_due_at DATETIME,
            response_status VARCHAR(24),
            response_at TIMESTAMPTZ,
            next_action VARCHAR(255),
            notes TEXT,
            template_id INTEGER REFERENCES contact_templates(id),
            version INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_outreach_user_scholarship_professor
                UNIQUE (user_id, scholarship_id, professor_id)
        """,
    },
}

#: Index definitions as ``name ON table (columns)``, without the CREATE prefix.
#: migrate_schema.py splits on " ON " to recover the index name when it decides
#: whether the index already exists, so the prefix belongs to the caller.
NEW_TABLE_INDEXES: dict[str, list[str]] = {
    "contact_templates": [
        "ix_contact_templates_active ON contact_templates (is_active)",
    ],
    "scholarship_supervisor_coverage": [
        "ix_supervisor_coverage_status ON scholarship_supervisor_coverage (status)",
        "ix_supervisor_coverage_next_check_at ON scholarship_supervisor_coverage (next_check_at)",
        "ix_supervisor_coverage_scholarship_id ON scholarship_supervisor_coverage (scholarship_id)",
    ],
    "professor_profiles": [
        "ix_professor_institution_name ON professor_profiles (institution_name)",
        "ix_professor_institution_department ON professor_profiles (institution_name, department_name)",
        "ix_professor_canonical_name ON professor_profiles (canonical_name)",
        "ix_professor_profile_status ON professor_profiles (profile_status)",
        "ix_professor_next_verification_at ON professor_profiles (next_verification_at)",
    ],
    "scholarship_professor_links": [
        "ix_professor_links_scholarship_status ON scholarship_professor_links (scholarship_id, verification_status)",
        "ix_professor_links_scholarship_id ON scholarship_professor_links (scholarship_id)",
        "ix_professor_links_professor_id ON scholarship_professor_links (professor_id)",
        "ix_professor_links_verification_status ON scholarship_professor_links (verification_status)",
    ],
    "supervisor_source_evidence": [
        "ix_supervisor_evidence_professor_id ON supervisor_source_evidence (professor_id)",
        "ix_supervisor_evidence_scholarship_id ON supervisor_source_evidence (scholarship_id)",
        "ix_supervisor_evidence_source_host ON supervisor_source_evidence (source_host)",
    ],
    "professor_availability": [
        "ix_professor_availability_professor_id ON professor_availability (professor_id)",
    ],
    "professor_outreach_records": [
        "ix_outreach_user_status ON professor_outreach_records (user_id, status)",
        "ix_outreach_user_follow_up ON professor_outreach_records (user_id, follow_up_due_at)",
        "ix_outreach_professor_id ON professor_outreach_records (professor_id)",
        "ix_outreach_scholarship_id ON professor_outreach_records (scholarship_id)",
    ],
}

#: Every table this feature introduces. Used by the post-apply validation so a
#: missing table is a startup failure with a named object rather than a 500 on
#: the first request that touches it.
REQUIRED_NEW_TABLES: tuple[str, ...] = tuple(NEW_TABLE_DDL)


def create_table_statements(dialect: str) -> list[str]:
    """Return the guarded ``CREATE TABLE`` statements for ``dialect``.

    Ordered by dependency: referenced tables are created before the tables that
    reference them, so this is safe to run against an empty database in one pass.
    """
    if dialect not in ("postgresql", "sqlite"):
        raise ValueError(f"Unsupported dialect: {dialect}")
    return [
        f"CREATE TABLE IF NOT EXISTS {name} ({ddl[dialect]})"
        for name, ddl in NEW_TABLE_DDL.items()
    ]


def index_statements() -> list[str]:
    """Return guarded ``CREATE INDEX IF NOT EXISTS`` statements for both dialects."""
    return [
        f"CREATE INDEX IF NOT EXISTS {definition}"
        for indexes in NEW_TABLE_INDEXES.values()
        for definition in indexes
    ]


__all__ = [
    "NEW_TABLE_DDL",
    "NEW_TABLE_INDEXES",
    "REQUIRED_NEW_TABLES",
    "create_table_statements",
    "index_statements",
]