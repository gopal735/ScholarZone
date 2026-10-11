"""Final spot-check classifications for the records whose chunk agent had not returned.

Each classification is grounded in either (a) a page the lead auditor fetched
today, or (b) the research corpus's own verified status note, with that basis
stated in the record so a reviewer can tell the difference. Nothing here
invents a date, status, or value.
"""
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
TARGET = BASE / "backend/research_output/publish/intake_classification_2026-10-11.json"
INVENTORY = BASE / "backend/research_output/publish/intake_audit_2026-10-11.json"

spot = {
    115: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": ["https://www.icar.org.in (unreachable from this environment; corpus research recorded the official text)"],
        "page_evidence": "Basis: the research corpus's verified note for this record: 'The 2026 cycle's last date (September 25, 2026) has passed. The fellowship page and notification remain live, and the guidelines state applications are invited every year, so a further round is expected.' The ICAR domain was unreachable for live re-verification; classification rests on the corpus research note, confidence reduced accordingly.",
        "next_deadline_or_window": None,
        "funding_on_page": None,
        "confidence": 0.6,
        "last_checked_date": "2026-10-11",
    },
    246: {
        "classification": "temporarily_closed_awaiting_announcement",
        "official_evidence_urls": ["https://ensie.nankai.edu.cn/info/1047/1347.htm"],
        "page_evidence": "Basis: the research corpus's verified note: 'The published deadline was 18 May 2026, which has passed. The announcement page is the 2026 intake's call and no 2027 call was published on it at the time of verification.' The URL timed out on a live re-fetch; classification rests on the corpus note.",
        "next_deadline_or_window": None,
        "funding_on_page": None,
        "confidence": 0.6,
        "last_checked_date": "2026-10-11",
    },
    289: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": ["https://nawa.gov.pl/en/students/foreign-students/the-banach-scholarship-programme/call-for-proposals"],
        "page_evidence": "The official NAWA Banach call page renders (fetched 2026-10-11) but its readable content is site navigation rather than the call text. Basis for recurrence: the corpus note records the closed round as 'call no. 16/2026' - a numbered edition in an annual series - closing 8 May 2026 at 3:00 p.m. local time with results announced by 31 July 2026. The Banach Scholarship Programme is one of NAWA's standing programmes. Next-call date not published on the page.",
        "next_deadline_or_window": None,
        "funding_on_page": None,
        "confidence": 0.7,
        "last_checked_date": "2026-10-11",
    },
    315: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": [
            "https://isd.pku.edu.cn/en/detail.php?id=819",
            "https://isd.pku.edu.cn/en/scholarship.php",
        ],
        "page_evidence": "Official Peking University International Students Division page (fetched 2026-10-11): '2026 Scholarship Applications Are Now Open for Prospective International Graduate Students of Peking University', notice dated January 12, 2026, application windows 'until Beijing Time at 9:00 a.m. on March 9' (PKU) and 'until Beijing Time at 24:00 on March 17' (China Scholarship Council) - both passed. The Chinese Government Scholarship is an annual national programme; this notice is the annual cycle notice, so a further cycle is expected.",
        "next_deadline_or_window": None,
        "funding_on_page": "Full or partial tuition waiver, living stipend, housing, and medical insurance (Chinese Government Scholarship for Advanced Graduate Program)",
        "confidence": 0.8,
        "last_checked_date": "2026-10-11",
    },
    356: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": [
            "https://en.tka.hu/bilateral-state-scholarships-information-for-applicants",
            "https://en.tka.hu/programmes",
        ],
        "page_evidence": "Official Tempus Public Foundation page (fetched 2026-10-11): the applicants' page carries the standing bilateral state scholarship information and publishes the current call 'for the academic year 2026-2027' (semester/partial, full degree and study visits deadline '19 February 2026'; summer courses '27 February 2026, 5 pm CET'), with the programme structure available year on year (semester/partial, full degree, study visits, summer courses). The 2026-2027 round is closed; the scheme runs an annual academic-year cycle.",
        "next_deadline_or_window": None,
        "funding_on_page": "Free of charge participation in courses plus a stipend (with possible supplements and accommodation contribution depending on scholarship type)",
        "confidence": 0.75,
        "last_checked_date": "2026-10-11",
    },
    401: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": [
            "https://www.royalsociety.org.nz/what-we-do/funds-and-opportunities",
            "https://www.royalsociety.org.nz/what-we-do/funds-and-opportunities/tawhia-te-mana-research-fellowships/",
        ],
        "page_evidence": "Basis: the research corpus's verified note: 'The 2026 round closed 2.00pm NZST on 9 July 2026; results were announced late October 2026 per the published timetable.' The Royal Society of New Zealand runs the Tawhia te Mana Research Fellowships as a standing scheme with published annual rounds and results timetables; the 2026 round's closure is a cycle boundary, not an end.",
        "next_deadline_or_window": None,
        "funding_on_page": None,
        "confidence": 0.7,
        "last_checked_date": "2026-10-11",
    },
    444: {
        "classification": "temporarily_closed_awaiting_announcement",
        "official_evidence_urls": ["https://www.temasek.com.sg/en/our-community/temasek-scholarship/temasek-undergraduate-overseas-scholarship"],
        "page_evidence": "The Temasek page returned HTTP 403 on every fetch attempt (2026-10-11), so no live official status could be read. Basis: the research corpus's verified note: 'Temasek's page still states the Academic Year 2026/2027 window is open and has been extended until 15 September 2026, which is in the past as at the verification date of 10 October 2026.' Classification is the conservative one: no published next window, no live page read.",
        "next_deadline_or_window": None,
        "funding_on_page": None,
        "confidence": 0.5,
        "last_checked_date": "2026-10-11",
    },
    606: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": ["https://icssr.org/data-collection-abroad"],
        "page_evidence": "Basis: the research corpus's verified note: 'The HEC pages record that applications for Batch-IV closed on 28 August 2026 at 16:00 and that the number of available aircraft slots was abolished from that batch onwards.' The programme runs numbered batches (Batch-IV), i.e. a repeating series; the parallel sister record (id 517, ICSSR International Seminar participation) was verified live by the chunk agent as a rolling, year-round mechanism.",
        "next_deadline_or_window": None,
        "funding_on_page": None,
        "confidence": 0.6,
        "last_checked_date": "2026-10-11",
    },
    693: {
        "classification": "recurring_next_intake_expected",
        "official_evidence_urls": ["https://education.gov.bb/2026-errol-walton-barrow-scholarship"],
        "page_evidence": "Basis: the research corpus's verified note: 'Completed application forms for the 2026 round had to be submitted no later than August 6, 2026; the Ministry publishes a new call each year.' Recurrence is on the official wording.",
        "next_deadline_or_window": None,
        "funding_on_page": None,
        "confidence": 0.75,
        "last_checked_date": "2026-10-11",
    },
}

data = json.loads(TARGET.read_text(encoding="utf-8"))
inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))["closed_records"]
present = {r["id"] for r in data["records"]}

for rid, result in spot.items():
    if rid in present:
        for record in data["records"]:
            if record["id"] == rid:
                record.update(result)
        continue
    inv = next(r for r in inventory if r["id"] == rid)
    merged = {
        "id": rid,
        "title": inv["title"],
        "country": inv["country"],
        "degree": inv["degree"],
        "funding": inv["funding"],
        "funding_amount": inv["funding_amount"],
        "funding_currency": inv["funding_currency"],
        "funding_period": inv["funding_period"],
        "recorded_deadline": inv["deadline_date"],
        "days_since_deadline": inv["days_since_deadline"],
        "public_status": inv["public_status"],
        "db_status": inv["db_status"],
        "db_archived": inv["db_archived"],
        "db_verification_status": inv["db_verification_status"],
        "official_source_url": inv["official_source_url"],
    }
    merged.update(result)
    data["records"].append(merged)

data["_audit"]["missing"] = []
counts = dict(Counter(r["classification"] for r in data["records"]))
data["_audit"]["classification_counts"] = counts
data["_audit"]["records_classified"] = len(data["records"])
data["_audit"]["lead_spot_checks"] = sorted(set(data["_audit"].get("lead_spot_checks", []) + [49, 203, 647, 356, 315, 115, 246, 289, 401, 444, 606, 693]))
data["records"].sort(key=lambda r: r["id"])
TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("classified records:", len(data["records"]))
print("counts:", counts)
print("lead spot-checks:", data["_audit"]["lead_spot_checks"])
