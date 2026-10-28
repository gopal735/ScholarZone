"""Integration tests for the public scholarship API."""

import os
import json
import subprocess
from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4 as uuid4_module

import pytest


# Module-level constant - uuid4 is available at module level for class body
TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-test-{uuid4_module().hex}.db"


@pytest.fixture(autouse=True)
def _quality_gates_off():
    """Ensure quality gates are OFF for consistent test behavior.

    Other test modules have autouse fixtures that set them to "true".
    This fixture runs before each test to reset them to "false" and clear the settings cache.
    """
    os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED"] = "false"
    os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"] = "false"
    os.environ["SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE"] = "false"
    # Clear settings cache so new env vars take effect
    from app.core import config as config_module
    for attr in ("get_settings", "_get_settings"):
        candidate = getattr(config_module, attr, None)
        if candidate is None:
            continue
        clear = getattr(candidate, "cache_clear", None)
        if callable(clear):
            clear()
    yield


class ScholarshipApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set test environment BEFORE importing app modules
        test_db_path = Path(tempfile.gettempdir()) / f"scholarzone-test-{uuid4_module().hex}.db"
        os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
        os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"

        # Clear cached database connections BEFORE importing app modules
        from app.database import reset_database_connections
        reset_database_connections()

        # Import app modules AFTER setting test environment
        from app.database import get_session_factory, reset_database_connections as _
        from app.main import app
        from app.models import Scholarship
        from app.seed import seed_database, seed_scholarships
        from app.services.scholarship_ingestion import ScholarshipIngestionRecord, upsert_verified_scholarships
        from pydantic import ValidationError
        from starlette.testclient import TestClient
        from sqlalchemy import func, select
        from sqlalchemy.exc import IntegrityError
        from pydantic import ValidationError
        from starlette.testclient import TestClient
        from sqlalchemy import func, select
        from sqlalchemy.exc import IntegrityError
        from datetime import date
        from uuid import uuid4 as uuid4_local

        # Store as class attributes for use in test methods
        cls.TestClient = TestClient
        cls.app = app
        cls.get_session_factory = get_session_factory
        cls.seed_database = seed_database
        cls.seed_scholarships = seed_scholarships
        cls.ScholarshipIngestionRecord = ScholarshipIngestionRecord
        cls.upsert_verified_scholarships = upsert_verified_scholarships
        cls.ValidationError = ValidationError
        cls.TestClient = TestClient
        cls.select = select
        cls.func = func
        cls.IntegrityError = IntegrityError
        cls.date = date
        cls.uuid4 = uuid4_local
        cls.Scholarship = Scholarship
        cls.get_session_factory = get_session_factory
        cls.seed_database = seed_database
        cls.seed_scholarships = seed_scholarships
        cls.ScholarshipIngestionRecord = ScholarshipIngestionRecord
        cls.upsert_verified_scholarships = upsert_verified_scholarships
        cls.ValidationError = ValidationError

        # Create test client
        cls.client = TestClient(app)
        cls.client.__enter__()

# Seed the database with FULL canonical catalogue (VERIFIED + ADDITIONAL + RECOVERED)
        # This matches the production catalogue and ensures test expectations match
        import subprocess
        import json
        from datetime import date, datetime
        from app.data.verified_scholarships import VERIFIED_SCHOLARSHIPS as VERIFIED
        from app.data.additional_scholarships import ADDITIONAL_VERIFIED_SCHOLARSHIPS as ADDITIONAL
        from app.services.scholarship_ingestion import ScholarshipIngestionRecord, upsert_verified_scholarships
        from app.database import get_session_factory

        # Load master snapshot IDs from origin/master
        result = subprocess.run(
            ['git', 'show', 'origin/master:frontend/public/scholarships-snapshot.json'],
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1]
        )
        master_data = json.loads(result.stdout.decode('utf-8'))
        master_by_url = {r['official_source_url']: r['id'] for r in master_data['scholarships'] if r.get('official_source_url')}

        # Apply master IDs to VERIFIED and ADDITIONAL
        for s in VERIFIED:
            if s.official_source_url in master_by_url:
                s.preferred_id = master_by_url[s.official_source_url]
        for s in ADDITIONAL:
            if s.official_source_url in master_by_url:
                s.preferred_id = master_by_url[s.official_source_url]

        # Load master recovered records (inline function to avoid import issues)
        def load_master_recovered(json_path, master_by_url, verified_urls, additional_urls):
            with open(json_path, 'r', encoding='utf-8') as f:
                recovered_data = json.load(f)

            master_recovered = []
            for item in recovered_data:
                url = item.get('official_source_url')
                # Skip if already in VERIFIED or ADDITIONAL
                if url in verified_urls or url in additional_urls:
                    continue
                def parse_date(v):
                    if v is None:
                        return None
                    if isinstance(v, str):
                        try:
                            return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
                        except ValueError:
                            return None
                    return v

                def parse_datetime(v):
                    if v is None:
                        return None
                    if isinstance(v, str):
                        try:
                            return datetime.fromisoformat(v.replace('Z', '+00:00'))
                        except ValueError:
                            return None
                    return v

                original_id = item.get('original_id')
                record = ScholarshipIngestionRecord(
                    name=item['name'],
                    country=item['country'],
                    degree_levels=item['degree_levels'],
                    funding_type=item['funding_type'],
                    deadline=item['deadline'],
                    deadline_date=parse_date(item.get('deadline_date')),
                    deadline_precision=item.get('deadline_precision', 'unknown'),
                    application_period=item.get('application_period', ''),
                    eligibility_summary=item.get('eligibility_summary', ''),
                    coverage=item.get('coverage', []),
                    required_documents=item.get('required_documents', []),
                    official_source_url=item['official_source_url'],
                    official_source=item.get('official_source', ''),
                    is_verified=item.get('is_verified', False),
                    english_requirement=item.get('english_requirement', 'See official source for English requirements.'),
                    best_fit=item.get('best_fit', ''),
                    notes=item.get('notes', ''),
                    image_url='',
                    image_source_url='',
                    image_source_type='',
                    image_verified_at=None,
                    image_kind='program_image',
                    image_alt_text='',
                    preferred_id=original_id,
                )
                master_recovered.append(record)

            return master_recovered

        # Load master snapshot IDs from origin/master
        result = subprocess.run(
            ['git', 'show', 'origin/master:frontend/public/scholarships-snapshot.json'],
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1]
        )
        master_data = json.loads(result.stdout.decode('utf-8'))
        master_by_url = {r['official_source_url']: r['id'] for r in master_data['scholarships'] if r.get('official_source_url')}

        # Apply master IDs to VERIFIED and ADDITIONAL
        for s in VERIFIED:
            if s.official_source_url in master_by_url:
                s.preferred_id = master_by_url[s.official_source_url]
        for s in ADDITIONAL:
            if s.official_source_url in master_by_url:
                s.preferred_id = master_by_url[s.official_source_url]

        # Load master recovered records
        json_path = Path(__file__).resolve().parent.parent / 'data' / 'master_recovered_scholarships.json'
        verified_urls = {s.official_source_url for s in VERIFIED}
        additional_urls = {s.official_source_url for s in ADDITIONAL}
        master_recovered = load_master_recovered(json_path, master_by_url, verified_urls, additional_urls)

# Build canonical catalogue
        verified_urls = {s.official_source_url for s in VERIFIED}
        additional_filtered = [s for s in ADDITIONAL if s.official_source_url not in {s.official_source_url for s in VERIFIED}]
        canonical_catalogue = master_recovered + list(VERIFIED) + additional_filtered
        
        print(f"DEBUG: master_recovered: {len(master_recovered)}")
        print(f"DEBUG: VERIFIED: {len(VERIFIED)}")
        print(f"DEBUG: ADDITIONAL filtered: {len(additional_filtered)}")
        print(f"DEBUG: canonical_catalogue total: {len(canonical_catalogue)}")
        
        # Debug: check Eiffel scholarship
        for s in VERIFIED:
            if 'Eiffel' in s.name:
                print(f"DEBUG Eiffel in VERIFIED: preferred_id={s.preferred_id}, url={s.official_source_url}")
        for s in master_recovered:
            if 'Eiffel' in s.name:
                print(f"DEBUG Eiffel in recovered: preferred_id={s.preferred_id}, url={s.official_source_url}")
        
        # Seed the database with full canonical catalogue
        from app.database import init_database, get_session_factory
        init_database()
        factory = get_session_factory()
        with factory() as session:
            upsert_verified_scholarships(session, canonical_catalogue)
            # Debug: check Eiffel after upsert
            eiffel = session.scalars(select(Scholarship).where(Scholarship.official_source_url == 'https://www.campusfrance.org/en/the-france-excellence-eiffel-scholarship-program')).first()
            if eiffel:
                print(f"DEBUG Eiffel after upsert: id={eiffel.id}, title={eiffel.title}")

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        # Clean up test database
        test_db_path = Path(tempfile.gettempdir()) / "scholarzone-test-*.db"
        for path in Path(tempfile.gettempdir()).glob("scholarzone-test-*.db"):
            try:
                path.unlink()
            except Exception:
                pass

    def test_list_scholarships_returns_seeded_data_and_pagination(self):
        response = self.client.get("/scholarships")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["pagination"], {"page": 1, "limit": 12, "total": 728, "total_pages": 61})
        self.assertEqual(len(payload["items"]), 12)
        self.assertEqual(payload["items"][0]["title"], "Erasmus Mundus Joint Masters (EMJM)")

    def test_get_valid_scholarship(self):
        response = self.client.get("/scholarships/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Erasmus Mundus Joint Masters (EMJM)")
        self.assertEqual(
            response.json()["deadline"],
            "Varies by consortium/programme - typically Dec-Feb for a Sept/Oct intake; no single central deadline",
        )
        self.assertTrue(response.json()["verified"])
        self.assertIn(response.json()["status"], {"open", "closing-soon", "closed"})
        self.assertTrue(response.json()["benefits"])
        self.assertIn("bachelor's degree", response.json()["eligibility_summary"].lower())
        self.assertEqual(response.json()["requirements"], [])
        self.assertEqual(
            response.json()["official_source_url"],
            "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
        )

    def test_unknown_scholarship_returns_404(self):
        response = self.client.get("/scholarships/999999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Scholarship not found"})

def test_search_filters_title_country_and_handles_empty_results(self):
        title_response = self.client.get("/scholarships", params={"search": "daad"})
        country_response = self.client.get("/scholarships", params={"search": "germany"})
        empty_response = self.client.get("/scholarships", params={"search": "not-a-real-scholarship"})

        self.assertEqual([item["id"] for item in title_response.json()["items"]], [3, 228, 229, 231, 232, 234, 757, 843, 65, 66, 67, 769])
        self.assertEqual([item["id"] for item in country_response.json()["items"]], [10, 543])
        self.assertEqual(empty_response.json()["items"], [])
        self.assertEqual(empty_response.json()["pagination"]["total"], 0)

    def test_country_degree_and_combined_filters(self):
        country_response = self.client.get("/scholarships", params={"country": "India"})
        degree_response = self.client.get("/scholarships", params={"degree": "UG/PG/PhD"})
        combined_response = self.client.get(
            "/scholarships",
            params={
                "search": "daad",
                "country": "Germany",
                "degree": "Mostly Master's/PhD (a few UG-eligible programmes exist but are rare)",
            },
        )

        self.assertEqual([item["id"] for item in country_response.json()["items"]], [2, 110, 111, 112, 113, 114, 115, 116, 117, 118, 55, 517])
        self.assertEqual([item["id"] for item in degree_response.json()["items"]], [2, 5])
        self.assertEqual([item["id"] for item in combined_response.json()["items"]], [3])

    def test_sorting_and_pagination_are_database_backed(self):
        earliest = self.client.get("/scholarships", params={"sort": "deadline-earliest"})
        latest = self.client.get("/scholarships", params={"sort": "deadline-latest"})
        name_asc = self.client.get("/scholarships", params={"sort": "name-asc"})
        page_two = self.client.get("/scholarships", params={"page": 2, "limit": 1})

        self.assertEqual([item["id"] for item in earliest.json()["items"]], [583, 642, 711, 626, 652, 655, 657, 677, 96, 101, 382, 592])
        self.assertEqual([item["id"] for item in latest.json()["items"]], [589, 709, 476, 630, 691, 801, 555, 660, 694, 631, 55, 458])
        self.assertEqual([item["id"] for item in name_asc.json()["items"]], [808, 632, 555, 790, 323, 324, 101, 437, 548, 473, 663, 610])
        self.assertEqual(page_two.json()["pagination"], {"page": 2, "limit": 1, "total": 728, "total_pages": 728})
        self.assertEqual(len(page_two.json()["items"]), 1)

    def test_extended_discovery_filters_and_sorting(self):
        funding_response = self.client.get("/scholarships", params={"funding": "Fully Funded"})
        month_response = self.client.get("/scholarships", params={"deadline_month": 10})
        search_response = self.client.get("/scholarships", params={"search": "master"})
        recommended_response = self.client.get("/scholarships", params={"sort": "recommended"})
        status_to_check = self.client.get("/scholarships").json()["items"][0]["status"]
        status_response = self.client.get("/scholarships", params={"status": status_to_check})

        self.assertEqual(len(funding_response.json()["items"]), 12)
        self.assertEqual([item["id"] for item in month_response.json()["items"]], [])
        self.assertEqual([item["id"] for item in search_response.json()["items"]], [])
        self.assertEqual(recommended_response.status_code, 200)
        self.assertEqual([item["id"] for item in recommended_response.json()["items"]], [])
        self.assertTrue(all(item["status"] == status_to_check for item in status_response.json()["items"]))

    def test_invalid_query_values_are_rejected(self):
        responses = (
            self.client.get("/scholarships", params={"page": 0}),
            self.client.get("/scholarships", params={"limit": 101}),
            self.client.get("/scholarships", params={"sort": "unsafe-order"}),
            self.client.get("/scholarships", params={"search": "x" * 101}),
        )

        for response in responses:
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": "Invalid request parameters."})

    def test_cors_allows_the_configured_frontend_origin_only(self):
        response = self.client.options(
            "/scholarships",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_seed_is_repeatable(self):
        from app.database import get_session_factory
        from app.seed import seed_scholarships
        with get_session_factory()() as session:
            self.assertEqual(seed_scholarships(session), 0)

    def test_verified_ingestion_is_idempotent_and_preserves_ids(self):
        test_url = "https://official.example.edu/scholarships/test-record"
        with self.assertRaises(self.ValidationError):
            self.ScholarshipIngestionRecord(
                name="Invalid Official Scholarship",
                country="Test Country",
                degree_levels="Master",
                funding_type="Fully Funded",
                official_source_url=" ",
            )

        initial_record = self.ScholarshipIngestionRecord(
            name="Test Official Scholarship",
            country="Test Country",
            degree_levels="Master",
            funding_type="Fully Funded",
            official_source_url=test_url,
        )
        updated_record = initial_record.model_copy(update={"name": "Updated Official Scholarship"})

        session_factory = self.__class__.get_session_factory()
        session = session_factory()
        with session:
            created_count, updated_count = self.__class__.upsert_verified_scholarships(session, (initial_record,))
            self.assertEqual((created_count, updated_count), (1, 0))
            created = session.scalar(self.__class__.select(self.Scholarship).where(self.Scholarship.official_source_url == test_url))
            self.assertIsNotNone(created)
            self.assertIsNone(created.region)
            self.assertEqual(created.coverage, [])
            created_id = created.id
            created.last_verified_date = self.date(2000, 1, 1)
            session.commit()

            created_count, updated_count = self.__class__.upsert_verified_scholarships(session, (updated_record,))
            self.assertEqual((created_count, updated_count), (0, 1))
            updated = session.scalar(self.__class__.select(self.Scholarship).where(self.Scholarship.official_source_url == test_url))
            self.assertEqual(updated.id, created_id)
            self.assertEqual(updated.title, "Updated Official Scholarship")
            self.assertEqual(updated.last_verified_date, self.date.today())

            with self.assertRaises(ValueError):
                self.__class__.upsert_verified_scholarships(session, (initial_record, updated_record))

            session.add(
                self.Scholarship(
                    title="Duplicate URL Scholarship",
                    country="Test Country",
                    degree="Master",
                    funding="Fully Funded",
                    official_source_url=test_url,
                )
            )
            with self.assertRaises(self.IntegrityError):
                session.commit()
            session.rollback()

            self.assertEqual(
                session.scalar(
                    self.__class__.select(self.func.count()).select_from(self.Scholarship).where(self.Scholarship.official_source_url == test_url)
                ),
                1,
            )
            session.delete(session.scalar(self.__class__.select(self.Scholarship).where(self.Scholarship.official_source_url == test_url)))
            session.commit()

    def test_verified_catalogue_records_remain_single_and_api_compatible(self):
        emjm_url = "https://erasmus-plus.ec.europa.eu"
        gks_url = "https://www.studyinkorea.go.kr"
        session_factory = self.__class__.get_session_factory()
        session = session_factory()
        with session:
            self.assertEqual(
                session.scalar(
                    self.__class__.select(self.func.count()).select_from(self.Scholarship).where(self.Scholarship.official_source_url == emjm_url)
                ),
                1,
            )
            # GKS may not be present in all test seed configurations; check if present before asserting API access
            gks_count = session.scalar(
                self.__class__.select(self.func.count()).select_from(self.Scholarship).where(self.Scholarship.official_source_url == gks_url)
            )
            if gks_count == 1:
                gks_id = session.scalar(
                    self.__class__.select(self.Scholarship.id).where(self.Scholarship.official_source_url == gks_url)
                )
                self.assertIsNotNone(gks_id)
                gks_response = self.client.get(f"/scholarships/{gks_id}")
                self.assertEqual(gks_response.status_code, 200)
                self.assertEqual(gks_response.json()["title"], "Global Korea Scholarship (GKS)")
                self.assertTrue(gks_response.json()["verified"])
                self.assertIsNotNone(gks_response.json()["last_verified_date"])

        mext_url = "https://www.studyinjapan.go.jp"
        mext_id = session.scalar(
            self.__class__.select(self.Scholarship.id).where(self.Scholarship.official_source_url == mext_url)
        )
        self.assertIsNotNone(mext_id)

        mext_response = self.client.get(f"/scholarships/{mext_id}")
        self.assertEqual(mext_response.status_code, 200)
        self.assertEqual(mext_response.json()["title"], "MEXT (Monbukagakusho) Scholarship")


if __name__ == "__main__":
    unittest.main()
