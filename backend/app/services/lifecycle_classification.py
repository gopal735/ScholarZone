"""Backend-authoritative scholarship lifecycle classification.

Mirrors ``frontend/src/utils/lifecycle.js`` so the backend can filter,
paginate and count scholarships by lifecycle without the frontend
reconstructing the catalogue. The frontend values are preserved exactly:
opening, upcoming, open, closing_soon, closed, unknown.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

CLOSING_SOON_THRESHOLD_DAYS = 30
OPENING_WINDOW_DAYS = 60

MONTHS = {
    "january": 0, "february": 1, "march": 2, "april": 3, "may": 4, "june": 5,
    "july": 6, "august": 7, "september": 8, "october": 9, "november": 10, "december": 11,
}


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    try:
        return getattr(obj, key, None)
    except Exception:
        return None


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None
        m = re.match(r"^(\d{4})-(\d{2})$", text)
        if m:
            try:
                y, mo = int(m.group(1)), int(m.group(2))
                if mo == 12:
                    return date(y, 12, 31)
                return date(y, mo + 1, 1) - timedelta(days=1)
            except ValueError:
                return None
    return None


def _parse_opening_from_period(period: Any, reference: date) -> date | None:
    if not isinstance(period, str) or not period.strip():
        return None
    text = period

    m = re.search(r"opens?\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})", text, re.I)
    if m:
        d = _to_date(m.group(1))
        if d:
            return d
    m = re.search(r"opens?\s+(?:on\s+)?(\d{1,2}\s+[A-Za-z]+\s+\d{4})", text, re.I)
    if m:
        parts = m.group(1).split()
        if len(parts) == 3:
            day, mon, yr = parts
            mi = MONTHS.get(mon.lower())
            if mi is not None:
                try:
                    return date(int(yr), mi + 1, int(day))
                except ValueError:
                    pass
    m = re.search(r"(\d{4})\s+cycle:?.*?opens?\s+(\d{4}-\d{2}-\d{2})", text, re.I)
    if m:
        d = _to_date(m.group(2))
        if d:
            return d
    m = re.search(r"(?:call|applications?)\s+opens?\s+([A-Za-z]+\s+\d{4})", text, re.I)
    if m:
        parts = m.group(1).split()
        if len(parts) == 2:
            mon, yr = parts
            mi = MONTHS.get(mon.lower())
            if mi is not None:
                try:
                    return date(int(yr), mi + 1, 1)
                except ValueError:
                    pass
    m = re.search(r"(?:re-)?opens?\s+in\s+(early|mid|late)\s+([A-Za-z]+)", text, re.I)
    if m:
        qual, mon = m.group(1).lower(), m.group(2).lower()
        mi = MONTHS.get(mon)
        if mi is not None:
            day = 5 if qual == "early" else 15 if qual == "mid" else 25
            year = reference.year
            try:
                parsed = date(year, mi + 1, day)
            except ValueError:
                parsed = None
            if parsed is not None and parsed < reference:
                try:
                    parsed = date(year + 1, mi + 1, day)
                except ValueError:
                    parsed = None
            if parsed is not None:
                return parsed
    return None


def _days_diff(target: date | None, reference: date) -> int | None:
    if target is None:
        return None
    return (target - reference).days


def _has_future_cycle(scholarship: Any, reference: date) -> bool:
    period = _get(scholarship, "application_period")

    od = _get(scholarship, "opening_date")
    od_date = _to_date(od) if od is not None else None
    if od_date is not None:
        dd = _days_diff(od_date, reference)
        if dd is not None and dd > 0:
            return True

    if isinstance(period, str):
        m = re.search(r"opens?\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})", period, re.I)
        if m:
            d = _to_date(m.group(1))
            if d is not None and d > reference:
                return True
        m = re.search(r"(\d{4})\s+cycle:?.*?opens?\s+(\d{4}-\d{2}-\d{2})", period, re.I)
        if m:
            d = _to_date(m.group(2))
            if d is not None and d > reference:
                return True
        m = re.search(r"(?:call|applications?)\s+opens?\s+([A-Za-z]+\s+\d{4})", period, re.I)
        if m:
            parts = m.group(1).split()
            if len(parts) == 2:
                mon, yr = parts
                mi = MONTHS.get(mon.lower())
                if mi is not None:
                    try:
                        d = date(int(yr), mi + 1, 1)
                    except ValueError:
                        d = None
                    if d is not None and d > reference:
                        return True
        m = re.search(r"(?:re-)?opens?\s+in\s+(early|mid|late)\s+([A-Za-z]+)", period, re.I)
        if m:
            qual, mon = m.group(1).lower(), m.group(2).lower()
            mi = MONTHS.get(mon)
            if mi is not None:
                day = 5 if qual == "early" else 15 if qual == "mid" else 25
                year = reference.year
                try:
                    parsed = date(year, mi + 1, day)
                except ValueError:
                    parsed = None
                if parsed is not None and parsed <= reference:
                    try:
                        parsed = date(year + 1, mi + 1, day)
                    except ValueError:
                        parsed = None
                if parsed is not None and parsed > reference:
                    return True

    cycle_text = " ".join(
        str(v) for v in [_get(scholarship, "application_period"),
                         _get(scholarship, "deadline_display"),
                         _get(scholarship, "deadline")] if isinstance(v, str)
    )
    recurring = bool(re.search(r"\b(annually|annual|every year|each year|per year|yearly|rounds? per year)\b", cycle_text, re.I))
    names_month = bool(re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", cycle_text, re.I))
    if recurring and names_month:
        return True
    return False


def compute_lifecycle(scholarship: Any, reference_date: date | None = None) -> str:
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    deadline_date = _to_date(_get(scholarship, "deadline_date"))
    if deadline_date is None:
        deadline_date = _to_date(_get(scholarship, "deadline_display"))
    if deadline_date is None:
        dl = _get(scholarship, "deadline")
        if isinstance(dl, str):
            deadline_date = _to_date(dl)

    opening_date = _to_date(_get(scholarship, "opening_date"))
    if opening_date is None:
        od = _get(scholarship, "opening_display")
        if isinstance(od, str):
            opening_date = _to_date(od)
    if opening_date is None:
        opening_date = _parse_opening_from_period(_get(scholarship, "application_period"), reference_date)

    days_until_deadline = _days_diff(deadline_date, reference_date)
    days_until_opening = _days_diff(opening_date, reference_date)

    has_future_cycle = _has_future_cycle(scholarship, reference_date)

    has_any_date = deadline_date is not None or opening_date is not None

    raw_status = _get(scholarship, "status")
    status = raw_status.lower() if isinstance(raw_status, str) else ""
    is_archived = bool(_get(scholarship, "is_archived"))

    # 1. explicit closed/archived
    if status == "closed" or is_archived:
        if not has_future_cycle:
            return "closed"
    # 2. deadline passed
    if deadline_date is not None and days_until_deadline is not None and days_until_deadline < 0:
        if not has_future_cycle:
            return "closed"
    # 3. explicit upcoming
    if status == "upcoming":
        return "upcoming"
    if status == "closed" and has_future_cycle:
        return "upcoming"
    # 4. upcoming based on opening date beyond window
    if opening_date is not None and days_until_opening is not None and days_until_opening > OPENING_WINDOW_DAYS:
        return "upcoming"
    # 5. closing soon
    if deadline_date is not None and days_until_deadline is not None and 0 <= days_until_deadline <= CLOSING_SOON_THRESHOLD_DAYS:
        return "closing_soon"
    # 6. opening phase
    if opening_date is not None and days_until_opening is not None and 0 <= days_until_opening <= OPENING_WINDOW_DAYS:
        return "opening"
    # 7. deadline passed but future cycle
    if deadline_date is not None and days_until_deadline is not None and days_until_deadline < 0 and has_future_cycle:
        return "upcoming"
    # 8. default open
    if status == "open":
        if not has_any_date:
            return "unknown"
        return "open"
    # 9. unknown
    return "unknown"


def lifecycle_counts(items: list[Any], reference_date: date | None = None) -> dict[str, int]:
    counts = {"opening": 0, "upcoming": 0, "open": 0, "closing_soon": 0, "closed": 0, "unknown": 0}
    for item in items:
        lc = compute_lifecycle(item, reference_date)
        if lc in counts:
            counts[lc] += 1
    return counts
