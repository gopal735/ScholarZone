"""Verify JSON-LD parsing in isolation."""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from bs4 import BeautifulSoup

HTML = (
    "<html><body>"
    '<script type="application/ld+json">'
    '{"@context":"https://schema.org","@type":"EducationalOrganization",'
    '"description":"A graduate scholarship for students from developing countries."}'
    "</script>"
    "</body></html>"
)

soup = BeautifulSoup(HTML, "html.parser")
tags = soup.find_all("script", type="application/ld+json")
print("tags:", len(tags))
for t in tags:
    raw = t.string or t.get_text() or ""
    print("raw repr:", repr(raw))
    try:
        print("parsed:", json.loads(raw))
    except Exception as exc:
        print("json error:", type(exc).__name__, exc)

from app.services.section_extractor import extract_jsonld

facts = extract_jsonld(HTML)
print("\nextract_jsonld ->", len(facts), "facts")
for f in facts:
    print("  ", f.field_name, "|", f.value[:70], "| conf:", f.confidence)
