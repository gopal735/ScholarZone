"""Audit every public record's deadline and funding fields for honesty.

The checks are deliberately conservative: they flag anything that is not a
deadline statement the catalogue can defend, and they never propose a new value.
A deadline is only removed when the stored text is provably not a deadline.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.deadline_semantics import (  # noqa: E402
    DEADLINE_PRECISION_VALUES,
    classify_deadline_text,
)

HERE = Path(__file__).resolve().parent
RAW = {int(k): v for k, v in json.loads((HERE / "live_raw.json").read_text(encoding="utf-8")).items()}

#: Text that names something other than an application deadline. Each pattern is a
#: documented reason the stored value is not a scholarship deadline.
NOT_A_DEADLINE = [
    ("refund", re.compile(r"\brefund", re.I)),
    ("payment", re.compile(r"\b(pay(?:ment|ments)?\s+(of|by)|bank transfer|remit(?:tance)?|wire)\b", re.I)),
    ("embassy_appointment", re.compile(r"\b(embassy|consulate)\b.{0,60}\b(interview|appointment|collection|document)\b", re.I)),
    ("visa_appointment", re.compile(r"\b(visa|immigration)\b.{0,40}\b(appointment|interview)\b", re.I)),
    ("fee_payment", re.compile(r"\b(payment|settlement)\s+of\s+(the\s+)?(tuition|application|registration)\s+fee", re.I)),
    ("administrative", re.compile(r"\b(orientation|registration\s+period|enrolment|enrollment|acceptance\s+by\s+the\s+college|document\s+verification)\b", re.I)),
    ("award_notification", re.compile(r"\b(notification|results?|award\s+letter)\b.{0,40}\b(date|by)\b", re.I)),
    ("not_a_deadline_literal", re.compile(r"\bnot\s+a\s+deadline\b|\bno\s+deadline\b|\bdeadline\s+(?:is\s+)?(?:not|has)\b", re.I)),
]

#: A deadline display that names no month at all is either rolling/annual or prose.
MONTHS = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.I,
)


def audit_deadlines() -> list[dict]:
    findings: list[dict] = []
    for sid, row in sorted(RAW.items()):
        display = (row.get("deadline_display") or "").strip()
        ddate = row.get("deadline_date")
        precision = row.get("deadline_precision")
        period = (row.get("application_period") or "").strip()
        notes: list[str] = []

        for label, rx in NOT_A_DEADLINE:
            for field, value in (("deadline_display", display), ("application_period", period)):
                if value and rx.search(value):
                    notes.append(f"{field}:{label}")

        if precision and precision not in DEADLINE_PRECISION_VALUES:
            notes.append(f"precision_not_in_vocabulary:{precision}")

        kind = classify_deadline_text(display)
        if display and not MONTHS.search(display) and kind.value == "unknown":
            notes.append("prose_without_month_or_policy")
        if ddate and not display:
            notes.append("date_without_display")
        if display and MONTHS.search(display) and not ddate and precision in ("exact", "month"):
            notes.append("month_claimed_but_no_date")

        if notes:
            findings.append(
                {
                    "id": sid,
                    "title": row.get("title"),
                    "deadline_display": display,
                    "deadline_date": ddate,
                    "deadline_precision": precision,
                    "application_period": period,
                    "flags": notes,
                }
            )
    return findings


def audit_funding() -> list[dict]:
    findings: list[dict] = []
    for sid, row in sorted(RAW.items()):
        label = (row.get("funding") or "").strip()
        amount = row.get("funding_amount")
        fully = row.get("fully_funded")
        tuition = row.get("tuition_coverage")
        living = row.get("living_cost_coverage")
        notes: list[str] = []
        if not label:
            notes.append("no_funding_label")
        if fully is True and tuition is not True:
            notes.append("fully_funded_without_tuition_coverage")
        if fully is True and living is False:
            notes.append("fully_funded_but_living_not_covered")
        if amount is not None and fully is True and tuition is False:
            notes.append("fully_funded_but_tuition_explicitly_not_covered")
        if notes:
            findings.append(
                {
                    "id": sid,
                    "title": row.get("title"),
                    "funding": label,
                    "funding_amount": amount,
                    "funding_currency": row.get("funding_currency"),
                    "tuition_coverage": tuition,
                    "living_cost_coverage": living,
                    "fully_funded": fully,
                    "flags": notes,
                }
            )
    return findings


def main() -> None:
    dl = audit_deadlines()
    fu = audit_funding()
    (HERE / "audit_deadlines.json").write_text(json.dumps(dl, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "audit_funding.json").write_text(json.dumps(fu, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"deadline findings: {len(dl)}")
    for f in dl:
        print(f"  {f['id']:>4} {f['flags']} :: {(f['deadline_display'] or '')[:90]!r}")
    print(f"\nfunding findings: {len(fu)}")
    for f in fu:
        print(f"  {f['id']:>4} {f['flags']} :: {f['funding']!r}")


if __name__ == "__main__":
    main()