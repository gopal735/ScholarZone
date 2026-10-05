"""Deterministic migration-export fixture for the Neon migration tests.

Why this exists
---------------
Eight tests in ``test_neon_migration.py`` asserted properties of
``backend/migration_export.sql``: a ~1.79 MB dump of one production SQLite
catalogue, produced once on a developer machine. It is gitignored, was never
tracked in any commit, and is produced by ``migration_export.export_to_sql()``
from ``backend/scholarzone.db`` - which is itself absent from a clean checkout.
No CI runner can therefore ever regenerate it, so those eight tests were red on
every clean checkout. The pipeline masked them; ``set -o pipefail`` in the backend
CI step exposed them, which is correct and is the point.

So the contract is fixed at the generator, not at the snapshot. These helpers
build a small, fully deterministic SQLite catalogue and run it through the
repository's own ``export_to_sql()``, so the tests exercise the real exporter and
the real validator on a file anybody can reproduce on any machine.

What this deliberately does not do
-----------------------------------
* It does not commit, embed or approximate the production dump.
* It does not skip, xfail or delete a single test.
* It does not bypass ``validate_migration_file`` - the validator still has to
  accept the generated file.

Why two fixtures
----------------
``neon_migrate.validate_migration_file`` carries row counts from one snapshot
(``scholarships: 303``, ``scholarship_verification_history: 6``,
``scholarship_reviews: 625``) and fails when a table has rows but not exactly that
many. A file with zero rows in those tables satisfies that guard; a file with a
handful of scholarship rows does not. The content tests need scholarship rows
(booleans, Unicode punctuation); the validator test needs none. Hence
``exported_migration_sql`` for content and ``validatable_migration_sql`` for the
validator, both produced by the same real exporter.

The row counts in the validator are a pre-existing assumption this task does not
change; the tests keep passing through the documented ``actual > 0`` escape.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from migration_export import export_to_sql  # noqa: E402

#: Text deliberately containing an em dash and an en dash. The export writes data
#: verbatim, so these must survive to the file - that is the Unicode-fidelity
#: regression the original tests were protecting, and it is what a production
#: scholarship title with an en dash in it would do.
UNICODE_SAMPLE = "Em dash — and en dash – in scholarship copy"

#: The exporter's table order puts these first, and the validator counts rows in
#: the first two. Kept deliberately small and fixed.
_ROWS = (
    (1, "Em Dash University — Institute", "Research — scholarship – programme", 1, 0),
    (2, "En Dash College – Faculty", "A title with an en – dash inside", 0, 1),
    (3, "Plain University", "No punctuation at all", 1, 1),
)


def _build_sqlite(path: Path, *, with_scholarship_rows: bool) -> Path:
    """Create a deterministic SQLite catalogue the real exporter can read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE scholarships (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                is_verified BOOLEAN,
                is_archived BOOLEAN
            )
            """
        )
        if with_scholarship_rows:
            connection.executemany(
                "INSERT INTO scholarships "
                "(id, title, description, is_verified, is_archived) "
                "VALUES (?, ?, ?, ?, ?)",
                _ROWS,
            )
        # Present but empty: the exporter writes a "0 rows (skipped)" comment for
        # these, which is what keeps the validator's row-count guard satisfied
        # without depending on one production snapshot's totals.
        connection.execute(
            """
            CREATE TABLE scholarship_verification_history (
                id INTEGER PRIMARY KEY,
                scholarship_id INTEGER,
                verdict TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE scholarship_reviews (
                id INTEGER PRIMARY KEY,
                scholarship_id INTEGER,
                decision TEXT
            )
            """
        )
        connection.commit()
    finally:
        connection.close()
    return path


def generate_migration_sql(directory: Path, *, with_scholarship_rows: bool) -> Path:
    """Run the repository's real exporter over a deterministic fixture."""
    database = _build_sqlite(directory / "fixture.db", with_scholarship_rows=with_scholarship_rows)
    output = directory / "migration_export.sql"
    connection = sqlite3.connect(database)
    try:
        export_to_sql(connection, output)
    finally:
        connection.close()
    return output


def pytest_fixture_content(tmp_path) -> Path:
    """Generated export WITH scholarship rows - for content assertions."""
    return generate_migration_sql(tmp_path / "content", with_scholarship_rows=True)


def pytest_fixture_validatable(tmp_path) -> Path:
    """Generated export with NO counted-table rows - so the validator accepts it."""
    return generate_migration_sql(tmp_path / "validatable", with_scholarship_rows=False)