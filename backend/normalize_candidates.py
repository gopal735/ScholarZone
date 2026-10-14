"""Normalize discovered candidate files to match validation schema."""

import json
from pathlib import Path


RESEARCH_DIR = Path("research_output")
NORMALIZED_DIR = Path("research_output_normalized")
NORMALIZED_DIR.mkdir(exist_ok=True)

# Field name mappings from various agent outputs to standard schema
FIELD_MAPPINGS = {
    "official_url": "official_source_url",
    "official_source_url": "official_source_url",
    "officialSourceUrl": "official_source_url",
    "url": "official_source_url",
    "source_url": "official_source_url",
    "degreeLevels": "degree_levels",
    "degree_levels": "degree_levels",
    "fundingType": "funding_type",
    "funding_type": "funding_type",
    "applicationDeadline": "application_deadline",
    "application_deadline": "application_deadline",
    "applicationOpeningDate": "application_opening_date",
    "application_opening_date": "application_opening_date",
    "eligibility_summary": "eligibility_summary",
    "eligibilitySummary": "eligibility_summary",
    "funding_details": "funding_details",
    "fundingDetails": "funding_details",
    "duration": "duration",
    "status": "status",
    "provider": "provider",
    "title": "title",
}


def normalize_record(record: dict[str, object], country: str) -> dict[str, object]:
    """Normalize a single record to standard schema."""
    normalized = {}
    
    # Map field names
    for key, value in record.items():
        standard_key = FIELD_MAPPINGS.get(key, key)
        normalized[standard_key] = value
    
    # Ensure required fields
    if "title" not in normalized or not normalized.get("title"):
        return None
    
    # Add country if missing
    if not normalized.get("country"):
        normalized["country"] = country
    
    # Ensure official_source_url exists
    if not normalized.get("official_source_url"):
        return None
    
    # Normalize URL
    url = str(normalized["official_source_url"]).strip().rstrip("/")
    if not url.startswith("https://") and not url.startswith("http://"):
        url = "https://" + url
    normalized["official_source_url"] = url
    
    # Normalize degree_levels to string
    if "degree_levels" in normalized:
        dl = normalized["degree_levels"]
        if isinstance(dl, list):
            normalized["degree_levels"] = ", ".join(str(d) for d in dl)
        else:
            normalized["degree_levels"] = str(dl)
    
    # Normalize funding_type
    if "funding_type" in normalized:
        ft = normalized["funding_type"]
        if isinstance(ft, list):
            normalized["funding_type"] = ", ".join(str(f) for f in ft)
        else:
            normalized["funding_type"] = str(ft)
    
    # Normalize status
    if "status" not in normalized:
        normalized["status"] = "UPCOMING"
    else:
        status = str(normalized["status"]).lower()
        if any(word in status for word in ["open", "active", "current"]):
            normalized["status"] = "OPEN"
        elif any(word in status for word in ["upcoming", "future", "next"]):
            normalized["status"] = "UPCOMING"
        elif any(word in status for word in ["closed", "ended", "past"]):
            normalized["status"] = "CLOSED"
        else:
            normalized["status"] = "UPCOMING"
    
    return normalized


def main():
    candidate_files = sorted(RESEARCH_DIR.glob("discovered_candidates_*.json"))
    print(f"Found {len(candidate_files)} candidate files to normalize")
    
    total_normalized = 0
    total_skipped = 0
    
    for cf in candidate_files:
        country = cf.stem.replace("discovered_candidates_", "").replace("_", " ").title()
        
        with open(cf, "r", encoding="utf-8") as f:
            candidates = json.load(f)
        
        normalized_candidates = []
        for candidate in candidates:
            normalized = normalize_record(candidate, country)
            if normalized:
                normalized_candidates.append(normalized)
            else:
                total_skipped += 1
        
        # Save normalized file
        output_path = NORMALIZED_DIR / f"normalized_{cf.name}"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(normalized_candidates, f, indent=2, ensure_ascii=False)
        
        print(f"{country}: {len(normalized_candidates)} normalized, {len(candidates) - len(normalized_candidates)} skipped")
        total_normalized += len(normalized_candidates)
    
    print(f"\nTotal normalized: {total_normalized}")
    print(f"Total skipped: {total_skipped}")
    print(f"Normalized files saved to: {NORMALIZED_DIR}")


if __name__ == "__main__":
    main()
