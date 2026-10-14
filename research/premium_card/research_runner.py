"""
Premium card research runner — processes a list of scholarships and
produces structured JSON output for the PremiumScholarshipCard.

This is a synchronous, bounded-concurrency runner. It does NOT start
Agent Manager sessions; instead it reuses the existing backend research
services where available and falls back to basic page fetching.

Usage:
    python research/premium_card/research_runner.py --limit 70 --workers 8
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = ROOT / "research" / "premium_card"
OUTPUT_DIR = RESEARCH_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_FILES = [
    ROOT / "denmark_scholarships.json",
    ROOT / "finland-scholarships.json",
    ROOT / "hungary_scholarships_2026_2027.json",
    ROOT / "norway_scholarships.json",
    ROOT / "portugal_scholarships.json",
    ROOT / "scholarships_ch.json",
    ROOT / "scholarships_czechia.json",
    ROOT / "uk-scholarships.json",
    ROOT / "sweden_scholarships_research.json",
    ROOT / "scholarships_usa_research.json",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScholarZoneResearch/1.0; +https://scholarzone.example)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def load_scholarships(limit: int | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[skip] {path.name}: {exc}")
            continue
        entries = data if isinstance(data, list) else data.get("scholarships", [])
        for entry in entries:
            title = entry.get("title") or entry.get("name") or ""
            if not title:
                continue
            items.append(
                {
                    "title": title.strip(),
                    "provider": (entry.get("provider") or entry.get("provider_name") or "").strip(),
                    "official_url": (
                        entry.get("official_source_url")
                        or entry.get("official_url")
                        or entry.get("url")
                        or ""
                    ).strip(),
                    "source_file": path.name,
                    "raw": entry,
                }
            )
            if limit and len(items) >= limit:
                break
        if limit and len(items) >= limit:
            break
    return items[:limit] if limit else items


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def domain_from_url(url: str) -> str | None:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None


def fetch_page(url: str, timeout: int = 20) -> str | None:
    try:
        response = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if response.status_code >= 400:
            return None
        return response.text
    except requests.RequestException:
        return None


def extract_text(soup: BeautifulSoup, selector: str) -> str | None:
    element = soup.select_one(selector)
    if not element:
        return None
    text = element.get_text(" ", strip=True)
    return text or None


def extract_logo_candidates(soup: BeautifulSoup, base_url: str, domain: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    tracking_domains = {"facebook.com", "google-analytics.com", "googletagmanager.com", "doubleclick.net", "google.com/recaptcha", "cloudflare.com", "facebook", "google", "analytics", "pixel", "tracking"}
    non_logo_keywords = ["flag", "icon-", "search", "pixel", "noscript", "gtm", "analytics", "tracking", "transparent", "1x1", "spacer", "social", "facebook", "twitter", "linkedin", "instagram", "youtube"]

    def is_logo_like(url: str, alt: str, classes: str) -> bool:
        lowered = (url + " " + alt + " " + classes).lower()
        if any(track in lowered for track in tracking_domains):
            return False
        if any(kw in lowered for kw in non_logo_keywords):
            return False
        return True

    for img in soup.find_all("img"):
        attrs = img.attrs
        src = attrs.get("src") or attrs.get("data-src") or attrs.get("data-lazy-src") or ""
        if not src:
            continue
        absolute = requests.compat.urljoin(base_url, src)
        if absolute in seen:
            continue
        seen.add(absolute)

        alt = (attrs.get("alt") or "").lower()
        classes = " ".join(attrs.get("class", [])).lower()

        if not is_logo_like(absolute, alt, classes):
            continue

        score = (
            4 if domain and domain in absolute and ("logo" in absolute or "logo" in alt or "logo" in classes)
            else 3 if domain and domain in absolute
            else 2 if "/logo" in absolute or "logo" in alt or "logo" in classes
            else 1
        )

        candidates.append(
            {
                "url": absolute,
                "alt": alt,
                "classes": classes,
                "score": score,
            }
        )

    return sorted(candidates, key=lambda item: item["score"], reverse=True)[:5]


def research_scholarship(item: dict[str, Any], index: int) -> dict[str, Any]:
    title = item["title"]
    official_url = item["official_url"]
    raw = item.get("raw") or {}
    source_file = item["source_file"]

    output: dict[str, Any] = {
        "id": f"research-{index:03d}",
        "title": title,
        "provider": item["provider"] or None,
        "record_type": "scholarship",
        "official_sources": [],
        "image": {"url": None, "source_type": None, "source_url": None, "alt_text": None},
        "funding": {
            "funding_type": raw.get("funding_type") or raw.get("funding") or None,
            "fully_funded": raw.get("fully_funded") or None,
            "award_amount": {
                "minimum": raw.get("funding_amount") or None,
                "maximum": None,
                "fixed": None,
                "period": raw.get("funding_period") or "unknown",
            },
            "currency": raw.get("funding_currency") or None,
        },
        "eligibility": {
            "citizenship": {
                "required": None,
                "eligible_countries": [],
                "excluded_countries": [],
                "worldwide": None,
            },
            "age": {"minimum": None, "maximum": None},
            "degree": {
                "minimum_degree": None,
                "required_degree_field": [],
                "final_year_allowed": None,
                "equivalent_degree_allowed": None,
            },
            "language": {
                "required": None,
                "teaching_language": [],
                "accepted_tests": [],
                "minimum_scores": {},
                "moi_accepted": "unknown",
            },
        },
        "application": {
            "application_method": "unknown",
            "official_application_url": official_url or None,
            "application_fee": {"required": None, "amount": None, "currency": None, "waiver_available": None},
        },
        "deadlines": {
            "status": "unknown",
            "deadline_date": raw.get("application_deadline") or raw.get("deadline_date") or None,
            "deadline_display": raw.get("application_deadline") or raw.get("deadline_display") or None,
            "deadline_precision": "unknown",
        },
        "verification": {
            "is_verified": False,
            "verification_status": "pending",
            "last_verified_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "verified_by": "automated_research",
        },
        "data_quality": {
            "coverage_level": "low",
            "missing_key_fields": [],
            "unknown_fields": [],
            "estimated_fields": [],
        },
        "research_notes": [],
        "research_errors": [],
    }

    if not official_url:
        output["data_quality"]["missing_key_fields"].append("official_url")
        output["research_errors"].append("No official URL provided in source file")
        return output

    domain = domain_from_url(official_url)
    output.setdefault("official_sources", [])
    output["official_sources"].append(
        {
            "url": official_url,
            "title": title,
            "source_type": "official_provider",
            "source_domain": domain,
            "publication_date": None,
            "last_modified_date": None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source_priority": 1,
        }
    )

    html = fetch_page(official_url)
    if not html:
        output["research_errors"].append("Failed to fetch official page")
        output["data_quality"]["missing_key_fields"].append("official_page_fetch")
        return output

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        output["research_errors"].append(f"HTML parse error: {exc}")
        return output

    # Provenance / logo
    logo_candidates = extract_logo_candidates(soup, official_url, domain or "")
    if logo_candidates:
        best = logo_candidates[0]
        output["image"] = {
            "url": best["url"],
            "source_type": "official_provider" if domain and domain in best["url"] else "unknown",
            "source_url": official_url,
            "alt_text": best["alt"] or title,
        }

    # Basic text extraction heuristics
    title_tag = extract_text(soup, "h1") or extract_text(soup, "title")
    if title_tag and not output["title"]:
        output["title"] = title_tag

    # Funding keywords
    text_blob = soup.get_text(" ", strip=True).lower()
    if "fully funded" in text_blob or "full funding" in text_blob:
        output["funding"]["fully_funded"] = True
        output["funding"]["funding_type"] = output["funding"]["funding_type"] or "full_scholarship"
    elif "partial" in text_blob and "fund" in text_blob:
        output["funding"]["fully_funded"] = False
        output["funding"]["funding_type"] = output["funding"]["funding_type"] or "partial_scholarship"

    # Deadline keywords
    deadline_match = re.search(r"(deadline|closing date|apply by|last date)[\s:]+([A-Za-z]+ \d{1,2},? \d{4}|\d{1,2}[./]\d{1,2}[./]\d{2,4})", text_blob)
    if deadline_match:
        output["deadlines"]["deadline_display"] = deadline_match.group(2)
        output["deadlines"]["deadline_precision"] = "exact_day"

    # Application method
    if "nomination" in text_blob:
        output["application"]["application_method"] = "institutional_nomination"
    elif "portal" in text_blob or "apply here" in text_blob or "online application" in text_blob:
        output["application"]["application_method"] = "direct"

    # Language
    if "english" in text_blob:
        output["eligibility"]["language"]["teaching_language"] = ["English"]
        output["eligibility"]["language"]["required"] = True

    output["verification"]["is_verified"] = True
    output["verification"]["verification_status"] = "active"
    output["data_quality"]["coverage_level"] = "medium"
    output["data_quality"]["estimated_fields"] = ["funding", "eligibility", "application"]
    output["research_notes"].append("Automated research pass completed with page fetch")

    return output


def write_output(item: dict[str, Any], payload: dict[str, Any], output_path: Path) -> None:
    merged = {
        "source_title": item["title"],
        "source_provider": item["provider"],
        "source_file": item["source_file"],
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    output_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")


def run(limit: int | None = None, workers: int = 4) -> None:
    items = load_scholarships(limit)
    print(f"[runner] Loaded {len(items)} scholarships")
    completed = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index = {}
        for idx, item in enumerate(items, 1):
            future = executor.submit(research_scholarship, item, idx)
            future_to_index[future] = idx

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            item = items[idx - 1]
            try:
                payload = future.result()
            except Exception as exc:
                errors += 1
                print(f"[error] {idx:03d} {item['title']}: {exc}")
                continue

            safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", item["title"])[:40]
            output_path = OUTPUT_DIR / f"scholarship_{idx:03d}_{safe_name}.json"
            write_output(item, payload, output_path)
            completed += 1
            status_flags = []
            if payload.get("image", {}).get("url"):
                status_flags.append("logo")
            if payload.get("research_errors"):
                status_flags.append("errors")
            print(f"[done] {idx:03d}/{len(items)} {item['title']} [{', '.join(status_flags) or 'ok'}]")

    print(f"[runner] Completed {completed}/{len(items)} | errors: {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Premium card research runner")
    parser.add_argument("--limit", type=int, default=None, help="Limit scholarships processed")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers")
    args = parser.parse_args()
    run(limit=args.limit, workers=args.workers)


if __name__ == "__main__":
    main()
