"""The catalogue list response must expose the record's official source URL.

The gap this covers was an omission, not a decision. ``ScholarshipDetailResponse``
has always declared ``official_source_url``, and the comment above the withheld
fields enumerates exactly what is deliberately withheld - ``verification_notes``,
``verified_by``, ``next_verification_due``, all internal workflow metadata. An
awarding body's own page is none of those, so its absence from the base response
meant the catalogue row could render "Verified Oct 5, 2026" with nothing for a
reader to check it against. That is an assertion of diligence rather than
evidence of it, which is the one slot this product exists to fill.

The tests are deliberately narrow. They assert that the field is present on the
base class with the same type and default the detail schema already used, that it
survives serialisation with a real value and with ``None``, and that exposing it
in the base did not disturb the detail response's behaviour. Nothing here asserts
a row count or a production figure.
"""

from __future__ import annotations

import pytest

from app.schemas import ScholarshipDetailResponse, ScholarshipListResponse, ScholarshipResponse

SAMPLE = "https://erasmus-plus.ec.europa.eu/en/opportunities/opportunities-for-students"


def payload(**overrides):
    """The minimum ScholarshipResponse requires, plus any overrides.

    Built from the model rather than hard-coded so a future required field
    surfaces here as a clear failure instead of a silently weakened fixture.
    """
    from datetime import date, datetime, timezone

    base = {
        "id": 1,
        "title": "Erasmus+",
        "name": "Erasmus+",
        "country": "BE",
        "degree": "Bachelor",
        "degree_levels": "Bachelor",
        "funding": "Partial",
        "funding_type": "grant",
        "deadline_precision": "month",
        "updated_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


class TestListResponseExposesTheOfficialSource:
    def test_the_field_is_on_the_base_response(self):
        assert "official_source_url" in ScholarshipResponse.model_fields

    def test_it_is_optional(self):
        field = ScholarshipResponse.model_fields["official_source_url"]
        assert not field.is_required()
        assert ScholarshipResponse(**payload()).official_source_url is None
        assert (
            ScholarshipResponse(**payload(official_source_url=None)).official_source_url
            is None
        )

    def test_it_uses_the_same_type_as_the_detail_schema(self):
        base = ScholarshipResponse.model_fields["official_source_url"]
        detail = ScholarshipDetailResponse.model_fields["official_source_url"]
        assert base.annotation == detail.annotation
        assert base.default == detail.default

    def test_a_real_url_round_trips(self):
        assert (
            ScholarshipResponse(**payload(official_source_url=SAMPLE)).official_source_url
            == SAMPLE
        )

    def test_it_serialises_at_the_list_level(self):
        """The list envelope is what the catalogue actually reads."""
        envelope = ScholarshipListResponse.model_validate(
            {
                "items": [
                    payload(id=1, official_source_url=SAMPLE),
                    payload(id=2, title="No authoritative source",
                            official_source_url=None),
                ],
                "pagination": {"page": 1, "limit": 20, "total": 2, "total_pages": 1},
            }
        ).model_dump()
        assert [item["official_source_url"] for item in envelope["items"]] == [SAMPLE, None]

    def test_null_renders_as_null_rather_than_a_substitute(self):
        """No placeholder host, no truncation, no invented provenance."""
        dumped = ScholarshipResponse(**payload(official_source_url=None)).model_dump()
        assert dumped["official_source_url"] is None


class TestDetailResponseIsUndisturbed:
    """Exposing the field in the base must not change what detail returns.

    The subclass still declares the field, so it now serialises at its base-class
    position rather than the subclass's. Same field, same type, same value, same
    payload - which is why this asserts behaviour rather than field ordering.
    """

    def test_detail_still_carries_the_field(self):
        assert "official_source_url" in ScholarshipDetailResponse.model_fields

    def test_detail_returns_the_same_value(self):
        detail = ScholarshipDetailResponse(**payload(official_source_url=SAMPLE))
        assert detail.official_source_url == SAMPLE

    def test_detail_still_accepts_a_null(self):
        detail = ScholarshipDetailResponse(**payload(official_source_url=None))
        assert detail.official_source_url is None

    def test_detail_field_set_is_a_superset_of_the_base(self):
        """Every base field remains reachable through the subclass."""
        assert set(ScholarshipResponse.model_fields) <= set(ScholarshipDetailResponse.model_fields)


class TestTheFieldIsNotNewlyInvented:
    """The value must come from the record's own column, never be derived."""

    def test_no_default_is_supplied(self):
        field = ScholarshipResponse.model_fields["official_source_url"]
        assert field.default is None, "the field must not invent a value when absent"

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "not-a-url",
            "javascript:alert(1)",
        ],
    )
    def test_the_schema_does_not_rewrite_the_stored_value(self, value):
        """Validation of the URL itself belongs to the record's own pipeline.

        The schema's job here is to expose what is stored. Silently normalising or
        dropping a malformed value here would mean the API reported something the
        database does not hold, which is the same class of dishonesty this field
        exists to remove.
        """
        assert (
            ScholarshipResponse(**payload(official_source_url=value)).official_source_url
            == value
        )