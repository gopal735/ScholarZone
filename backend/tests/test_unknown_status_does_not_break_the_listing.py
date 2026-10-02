"""A record with an undefined status must not take a whole page down.

Some catalogue rows carry "active" in the status column, which is a
verification_status value rather than a round status. A strict enum made Pydantic
raise, and because a page serialises as one object, three such rows turned every
page containing them into HTTP 500. That is why
/api/scholarships?limit=100&page=4 failed while page=3 succeeded: the bad rows
sit past the third page.

The value is now surfaced as null so the interface can say "status not published"
rather than inventing one.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.schemas import ScholarshipResponse, ScholarshipStatus


def record(**overrides):
    base = dict(
        id=1,
        title="Test programme",
        name="Test programme",
        country="Canada",
        degree="PhD",
        degree_levels="PhD",
        funding="Full",
        funding_type="Fully Funded",
        deadline_precision="month",
        status=ScholarshipStatus.OPEN,
        is_verified=True,
        updated_at=date(2026, 10, 1),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def build(**overrides) -> ScholarshipResponse:
    return ScholarshipResponse.model_validate(record(**overrides))


class TestValidStatusesPassThrough:
    @pytest.mark.parametrize("value", ["open", "upcoming", "closing-soon", "closed"])
    def test_known_statuses_survive(self, value):
        assert build(status=value).status == value


class TestUnknownStatusIsSurfacedNotRaised:
    @pytest.mark.parametrize("value", ["active", "verified", "OPEN", "", "unknown"])
    def test_unknown_status_becomes_null(self, value):
        # The regression value is "active": a verification_status that reached the
        # status column.
        assert build(status=value).status is None

    def test_none_is_kept(self):
        assert build(status=None).status is None

    def test_one_bad_row_cannot_break_the_page(self):
        good = build(status="open")
        bad = build(id=2, status="active")
        other_good = build(id=3, status="closed")
        page = [good, bad, other_good]
        assert len(page) == 3
        assert [item.status for item in page] == [
            ScholarshipStatus.OPEN,
            None,
            ScholarshipStatus.CLOSED,
        ]

    def test_the_record_is_still_listed(self):
        # Nulling the status must not drop the scholarship from the catalogue.
        item = build(status="active")
        assert item.id == 1
        assert item.title == "Test programme"


class TestOtherFieldsUnaffected:
    def test_provenance_fields_still_serialize(self):
        item = build(
            status="active",
            image_url="https://example.org/logo.svg",
            last_verified_at=date(2026, 10, 1),
        )
        assert item.image_url == "https://example.org/logo.svg"
        assert item.last_verified_at == date(2026, 10, 1)