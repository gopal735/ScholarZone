import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.supervisor_public import _missing_schema_error, SchemaNotReadyError


class FakeUndefinedTable(Exception):
    pass


class FakeUndefinedColumn(Exception):
    pass


def test_missing_schema_error_detects_psycopg3_sqlstate():
    exc = Exception("relation does not exist")
    exc.pgcode = "42P01"
    assert _missing_schema_error(exc) is True


def test_missing_schema_error_detects_missing_column_sqlstate():
    exc = Exception("column does not exist")
    exc.sqlstate = "42703"
    assert _missing_schema_error(exc) is True


def test_missing_schema_error_rejects_unrelated_programming_error():
    exc = Exception("syntax error at or near SELECT")
    exc.pgcode = "42601"
    assert _missing_schema_error(exc) is False


def test_missing_schema_error_unwraps_sqlalchemy():
    class Orig(Exception):
        pgcode = "42P01"

    class Wrapped(Exception):
        pass

    wrapped = Wrapped("wrapped")
    wrapped.orig = Orig("orig")
    assert _missing_schema_error(wrapped) is True