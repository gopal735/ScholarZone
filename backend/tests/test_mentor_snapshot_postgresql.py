"""PostgreSQL integration tests for Mentor discovery snapshot persistence.

These tests require a running PostgreSQL instance and are skipped unless
TEST_POSTGRESQL_URL is set.
"""

import os
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from app.database import get_db, get_engine, get_session_factory, init_database, reset_database_connections
from app.models import Base, Scholarship, User, MentorMessage, MentorConversation
from app.services.auth import hash_password
from app.services.mentor import conversation_service as cs
from app.services.mentor.discovery import run_discovery
from app.routers.mentor_conversations import _discovery_to_snapshot_payload, get_discovery
from app.test_db_safety import (
    validate_disposable_postgres_url,
    verify_disposable_db_identity,
    verify_disposable_db_marker,
    verify_expected_pg_version,
)

PASSWORD = "pg-mentor-9"
_seq = 0


def _next():
    global _seq
    _seq += 1
    return _seq


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRESQL_URL"),
    reason="TEST_POSTGRESQL_URL not set",
)
class TestMentorSnapshotPostgreSQL:
    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        pg_url = os.environ.get("TEST_POSTGRESQL_URL")
        allow = os.environ.get("SCHOLARZONE_ALLOW_DESTRUCTIVE_TEST_DB")
        expected_port_raw = os.environ.get("SCHOLARZONE_TEST_DB_PORT")
        if not expected_port_raw:
            raise RuntimeError("SCHOLARZONE_TEST_DB_PORT is required")
        expected_port = int(expected_port_raw)
        validate_disposable_postgres_url(pg_url, allow, expected_port)
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", pg_url)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        reset_database_connections()
        engine = get_engine()
        with engine.connect() as conn:
            verify_disposable_db_identity(conn, "scholarzone_test")
            verify_expected_pg_version(conn, os.environ.get("SCHOLARZONE_EXPECTED_PG_VERSION_NUM"))
            verify_disposable_db_marker(
                conn,
                os.environ.get("SCHOLARZONE_EXPECTED_DB_RUN_ID"),
                os.environ.get("SCHOLARZONE_EXPECTED_DB_MARKER_DIGEST"),
            )
        init_database()
        with engine.begin() as conn:
            for tbl in ("mentor_messages", "mentor_conversations", "scholarships", "users"):
                conn.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
        yield
        reset_database_connections()

    def _make_user(self, db):
        u = User(email=f"pg{_next()}@example.com", password_hash=hash_password(PASSWORD), is_active=True)
        db.add(u); db.commit(); db.refresh(u)
        return u

    def _make_sch(self, db, **kw):
        idx = _next()
        vals = {
            "title": f"Scholarship {idx}",
            "country": "Germany",
            "degree": "PhD",
            "funding": "Partial (Monthly stipend + insurance)",
            "official_source": f"Provider {idx}",
            "official_source_url": f"https://provider{idx}.example/programme",
            "verification_status": "active",
            "is_verified": True,
            "status": "open",
            "deadline_display": "Rolling",
        }
        vals.update(kw)
        s = Scholarship(**vals)
        db.add(s); db.commit(); db.refresh(s)
        return s

    def _make_snapshot_message(self, db, user, n=1):
        ids = []
        for _ in range(n):
            sch = self._make_sch(db)
            ids.append(sch.id)
        conv = MentorConversation(user_id=user.id, title="t")
        db.add(conv); db.commit(); db.refresh(conv)
        um = MentorMessage(conversation_id=conv.id, user_id=user.id, role="user", content="hi", status="completed", sequence_number=1)
        db.add(um); db.commit(); db.refresh(um)
        am = cs.reserve_assistant_message(db, user.id, conv.id, source_user_message_id=um.id, attempt_id="a1")
        discovery = run_discovery(db, "Find PhD scholarships with stipend in Europe", date.today())
        payload = _discovery_to_snapshot_payload(discovery)
        cs.complete_assistant_message(db, user.id, am.id, "answer", attempt_id="a1", discovery_payload=payload)
        db.commit()
        return conv, am, ids, payload

    def test_jsonb_round_trip(self):
        engine = get_engine()
        sf = get_session_factory()
        db = sf()
        user = self._make_user(db)
        self._make_sch(db)
        conv = MentorConversation(user_id=user.id, title="t")
        db.add(conv); db.commit(); db.refresh(conv)
        um = MentorMessage(conversation_id=conv.id, user_id=user.id, role="user", content="hi", status="completed", sequence_number=1)
        db.add(um); db.commit(); db.refresh(um)
        am = cs.reserve_assistant_message(db, user.id, conv.id, source_user_message_id=um.id, attempt_id="a1")
        discovery = run_discovery(db, "Find PhD scholarships with stipend in Europe", date.today())
        payload = _discovery_to_snapshot_payload(discovery)
        cs.complete_assistant_message(db, user.id, am.id, "answer", attempt_id="a1", discovery_payload=payload)
        msg_id = am.id
        db.commit()
        db.close()

        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name='mentor_messages' AND column_name='discovery_payload'"
            )).fetchone()
            assert row is not None and row[0] == "jsonb"

        db2 = sf()
        msg = db2.get(MentorMessage, msg_id)
        assert msg is not None
        assert isinstance(msg.discovery_payload, dict)
        assert msg.discovery_payload.get("snapshot_version") == 1
        assert isinstance(msg.discovery_payload.get("snapshot_items"), list)
        assert msg.discovery_payload.get("result_count") == len(msg.discovery_payload.get("snapshot_items"))
        db2.close()

    def test_historical_pagination(self):
        sf = get_session_factory()
        db = sf()
        user = self._make_user(db)
        conv, am, ids, payload = self._make_snapshot_message(db, user, 5)
        # page 1
        r1 = get_discovery(conv.id, am.id, page=1, page_size=2, db=db, user=user)
        assert r1["pagination"]["total"] == 5
        assert r1["pagination"]["total_pages"] == 3
        assert r1["returned_count"] == 2
        assert r1["pagination"]["has_more"] is True
        p1_ids = [m["scholarship_id"] for m in r1["potential_matches"]]
        r2 = get_discovery(conv.id, am.id, page=2, page_size=2, db=db, user=user)
        assert r2["returned_count"] == 2
        p2_ids = [m["scholarship_id"] for m in r2["potential_matches"]]
        assert set(p1_ids).isdisjoint(set(p2_ids))
        r3 = get_discovery(conv.id, am.id, page=3, page_size=2, db=db, user=user)
        assert r3["returned_count"] == 1
        assert r3["pagination"]["has_more"] is False
        all_ids = p1_ids + p2_ids + [m["scholarship_id"] for m in r3["potential_matches"]]
        assert sorted(all_ids) == sorted(ids)
        db.close()

    def test_historical_immutability(self):
        sf = get_session_factory()
        db = sf()
        user = self._make_user(db)
        conv, am, ids, payload = self._make_snapshot_message(db, user, 1)
        sch = db.get(Scholarship, ids[0])
        original_title = sch.title
        # mutate catalogue
        sch.title = "Changed Title"
        sch.funding = "Full tuition only (no stipend)"
        db.add(sch); db.commit()
        self._make_sch(db)
        r = get_discovery(conv.id, am.id, page=1, page_size=50, db=db, user=user)
        titles = [m["title"] for m in r["potential_matches"]]
        assert original_title in titles
        assert "Changed Title" not in titles
        assert r["pagination"]["total"] == 1
        db.close()

    def test_retry_integrity(self):
        sf = get_session_factory()
        db = sf()
        user = self._make_user(db)
        self._make_sch(db)
        conv = MentorConversation(user_id=user.id, title="t")
        db.add(conv); db.commit(); db.refresh(conv)
        um = MentorMessage(conversation_id=conv.id, user_id=user.id, role="user", content="hi", status="completed", sequence_number=1)
        db.add(um); db.commit(); db.refresh(um)
        am = cs.reserve_assistant_message(db, user.id, conv.id, source_user_message_id=um.id, attempt_id="attempt-a")
        cs.fail_assistant_message(db, user.id, am.id, "boom", attempt_id="attempt-a")
        claimed = cs.claim_retry_attempt(db, user.id, am.id, new_attempt_id="attempt-b")
        assert claimed is not None and claimed.attempt_id == "attempt-b"
        payload_b = {"snapshot_items": [{"scholarship_id": 2, "title": "B"}], "result_count": 1, "search_status": "POTENTIAL_MATCHES_FOUND", "snapshot_version": 1}
        cs.complete_assistant_message(db, user.id, am.id, "answer B", attempt_id="attempt-b", discovery_payload=payload_b)
        stale = cs.complete_assistant_message(db, user.id, am.id, "answer A", attempt_id="attempt-a", discovery_payload={"snapshot_items": [{"scholarship_id": 1, "title": "A"}], "result_count": 1})
        assert stale is not None
        assert stale.attempt_id == "attempt-b"
        assert stale.discovery_payload["snapshot_items"][0]["title"] == "B"
        db.close()

    def test_reconnection_durability(self):
        sf = get_session_factory()
        db = sf()
        user = self._make_user(db)
        conv, am, ids, payload = self._make_snapshot_message(db, user, 1)
        conv_id = conv.id
        am_id = am.id
        expected_count = payload["result_count"]
        db.close()
        # dispose original engine
        engine = get_engine()
        engine.dispose()
        reset_database_connections()
        # new engine/session
        new_sf = get_session_factory()
        new_db = new_sf()
        # need user in new session? user exists; fetch by id? We'll fetch from db
        user2 = new_db.get(User, user.id)
        r = get_discovery(conv_id, am_id, page=1, page_size=5, db=new_db, user=user2)
        assert r["result_count"] == expected_count
        msg = new_db.get(MentorMessage, am_id)
        assert msg.discovery_payload["result_count"] == expected_count
        new_db.close()
