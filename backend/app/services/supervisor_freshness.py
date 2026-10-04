"""Freshness policy for supervisor facts.

Identity changes slowly. A person's title, department and research areas stay
roughly true for months. Availability does not: a page saying "I am accepting
applications for 2027" is false the moment that round closes, and quietly
republishing it a year later is the specific failure this policy exists to
prevent.

So the two kinds of fact get different clocks. When a claim ages past its window
it is reported as ``stale`` rather than deleted - the underlying observation was
real, and erasing it would make the record look like nothing was ever found.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .supervisor_status import AvailabilityState, PUBLISHABLE_AVAILABILITY_STATES

#: Identity and research areas. Long, because a faculty page rarely changes in a
#: way that makes a stored name wrong.
IDENTITY_REFRESH_DAYS = 90

#: Contact details and availability. Much shorter, because these are the claims a
#: student would act on and be embarrassed by if they were out of date.
CONTACT_REFRESH_DAYS = 30

#: A verified relationship whose source has not been re-read in this long is
#: reported as stale evidence rather than as current fact.
RELATIONSHIP_REFRESH_DAYS = 120


def _as_utc(value: datetime | None) -> datetime | None:
    """Return ``value`` as an aware UTC datetime.

    SQLite round-trips a timezone-aware column as naive, so comparing a stored
    timestamp against ``datetime.now(timezone.utc)`` raises. Normalising on read
    keeps the dialect difference out of every caller.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def age_days(value: datetime | None, now: datetime | None = None) -> float | None:
    """Return how many days old ``value`` is, or ``None`` if it is unset."""
    moment = _as_utc(value)
    if moment is None:
        return None
    reference = _as_utc(now) or datetime.now(timezone.utc)
    return (reference - moment).total_seconds() / 86400.0


def identity_is_stale(last_verified_at: datetime | None, now: datetime | None = None) -> bool:
    """Return whether identity data should be re-read before being relied on."""
    age = age_days(last_verified_at, now)
    if age is None:
        # Never verified is the most stale thing there is, but it is reported as
        # unknown rather than stale, so this stays a re-read trigger only.
        return True
    return age > IDENTITY_REFRESH_DAYS


def availability_is_stale(verified_at: datetime | None, now: datetime | None = None) -> bool:
    age = age_days(verified_at, now)
    if age is None:
        return True
    return age > CONTACT_REFRESH_DAYS


def effective_availability_state(
    state: str,
    verified_at: datetime | None,
    now: datetime | None = None,
) -> str:
    """Return the state to publish for one availability claim.

    Only the two positive-evidence states can decay. ``unknown`` and
    ``not_published`` are already absences and stay absences; a stale absence is
    still an absence, and promoting it to ``stale`` would imply something was
    once known.
    """
    if state in PUBLISHABLE_AVAILABILITY_STATES and availability_is_stale(verified_at, now):
        return str(AvailabilityState.STALE)
    return state


def relationship_is_stale(verified_at: datetime | None, now: datetime | None = None) -> bool:
    age = age_days(verified_at, now)
    if age is None:
        return False
    return age > RELATIONSHIP_REFRESH_DAYS


def next_check_at(verified: bool, now: datetime | None = None) -> datetime:
    """Return when this record should next be re-read.

    A verified record is re-checked on the slower identity clock; an unverified
    one is re-attempted sooner, because the cheapest useful outcome is turning it
    into a verified record.
    """
    reference = _as_utc(now) or datetime.now(timezone.utc)
    window = IDENTITY_REFRESH_DAYS if verified else 7
    return reference + timedelta(days=window)


__all__ = [
    "CONTACT_REFRESH_DAYS",
    "IDENTITY_REFRESH_DAYS",
    "RELATIONSHIP_REFRESH_DAYS",
    "age_days",
    "availability_is_stale",
    "effective_availability_state",
    "identity_is_stale",
    "next_check_at",
    "relationship_is_stale",
]