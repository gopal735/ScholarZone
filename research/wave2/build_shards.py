"""Build wave-2 discovery shards: find scholarships that are OPEN now and not yet in the DB.

50 shards = 8 research themes x 6 world regions (+2 global catch-alls), so no two
agents cover the same cell. Each shard carries the dedup list (existing hosts and
titles in that region) extracted from the live database.
"""
import json
import os
import sqlite3
from urllib.parse import urlsplit

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
DB = os.path.join(ROOT, "backend", "scholarzone.db")
OUT = os.path.join(ROOT, "research", "wave2", "shards")
os.makedirs(OUT, exist_ok=True)
TODAY = "2026-10-04"

REGIONS = {
    "europe": [
        "United Kingdom", "Ireland", "France", "Germany", "Netherlands", "Belgium", "Luxembourg",
        "Switzerland", "Austria", "Spain", "Portugal", "Italy", "Malta", "Sweden", "Norway",
        "Denmark", "Finland", "Iceland", "Estonia", "Latvia", "Lithuania", "Poland",
        "Czech Republic", "Slovakia", "Hungary", "Slovenia", "Croatia", "Romania", "Bulgaria",
        "Greece", "Cyprus", "European Union",
    ],
    "north_america": ["United States", "Canada", "Mexico", "Bermuda", "Puerto Rico"],
    "latin_america": [
        "Brazil", "Argentina", "Chile", "Colombia", "Peru", "Uruguay", "Paraguay", "Ecuador",
        "Bolivia", "Costa Rica", "Panama", "Cuba", "Dominican Republic", "Jamaica",
    ],
    "asia": [
        "China", "Japan", "South Korea", "Taiwan", "Mongolia", "India", "Pakistan", "Bangladesh",
        "Sri Lanka", "Nepal", "Bhutan", "Singapore", "Malaysia", "Indonesia", "Thailand",
        "Vietnam", "Philippines", "Kazakhstan", "Uzbekistan",
    ],
    "middle_east_africa": [
        "United Arab Emirates", "Saudi Arabia", "Qatar", "Kuwait", "Oman", "Bahrain", "Israel",
        "Jordan", "Lebanon", "Iran", "Iraq", "Egypt", "Morocco", "Tunisia", "Algeria",
        "Nigeria", "Ghana", "Kenya", "South Africa", "Ethiopia", "Tanzania", "Uganda",
        "Senegal", "Rwanda", "Zambia", "Namibia", "Botswana",
    ],
    "oceania": ["Australia", "New Zealand", "Fiji", "Papua New Guinea", "Samoa"],
}

THEMES = {
    "government": "Government-funded scholarships: national scholarship schemes, ministry-funded awards, "
                  "state/provincial programmes, bilateral government scholarships, and official government "
                  "study-abroad and exchange programmes.",
    "university": "University-funded scholarships: merit scholarships, tuition waivers, need-based aid, "
                  "international student bursaries, and faculty/department-level awards open to international "
                  "applicants.",
    "institution": "International institutions, foundations and NGOs: multilateral programmes (UN, UNESCO, "
                   "World Bank, regional development banks), research institutes, charitable trusts, corporate "
                   "and diaspora foundations, and professional associations that fund study abroad.",
    "subject": "Subject-specific awards: STEM/engineering, health and medicine, law, arts and music, "
               "architecture and design, journalism and media, sports, agriculture and food security.",
    "level": "Early-stage and bridging awards: foundation years, pre-master preparatory programmes, "
             "undergraduate and postgraduate awards open to students early in their studies, gap-year and "
             "youth mobility programmes, and short-credit exchange awards.",
    "targeted": "Targeted-need and underrepresented-group awards: women in STEM, first-generation students, "
                "low-income backgrounds, indigenous and minority students, refugees and displaced students, "
                "students with disabilities, and post-conflict or developing-country priority groups.",
    "fully_funded": "Fully-funded awards only: programmes where tuition, living costs and travel are covered by "
                    "the funder — doctoral, research and sponsored-student schemes, and the rare fully-funded "
                    "master's or bachelor's schemes.",
    "regional_multi": "Regional and multi-country programmes: schemes open to ALL nationalities of a specific "
                      "world region or income group, Erasmus Mundus / Erasmus+ and DAAD-style consortium "
                      "scholarships, ASEAN and African Union programmes, and cross-border tuition-waiver schemes.",
}

GLOBAL_THEMES = [
    ("global_1", "A worldwide sweep for currently-OPEN applications. Cover the awarding bodies you would "
                 "otherwise miss: national scholarship portals you have not seen, university international "
                 "office pages in countries nobody else covered, and multilingual official sites (German, "
                 "French, Spanish, Portuguese, Japanese, Korean, Turkish, Arabic). Prioritise breadth of "
                 "genuinely open programmes over depth on any one of them."),
    ("global_2", "A worldwide sweep for the awards applicants most often miss: named-branded scholarships, "
                 "competition and talent awards, essay and merit schemes, and honours programmes. Also cover "
                 "official pages published only as PDFs or in a page's native language, and any official "
                 "opportunity that a deadline within the next 12 months applies to."),
]

# ---- live database dedup index --------------------------------------------
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id,title,country,official_source,official_source_url,status,degree,funding "
    "FROM scholarships"
).fetchall()


def host_of(url):
    if not url:
        return ""
    try:
        h = urlsplit(url if "//" in url else "https://" + url).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except ValueError:
        return ""


countries = sorted({(r["country"] or "").strip() for r in rows if r["country"]})
by_country = {}
for r in rows:
    by_country.setdefault((r["country"] or "").strip(), []).append(r)


def dedup_for(country_list):
    titles, hosts, urls = [], [], []
    for c in country_list:
        for r in by_country.get(c, []):
            titles.append(r["title"])
            h = host_of(r["official_source_url"])
            if h:
                hosts.append(h)
            if r["official_source_url"]:
                urls.append(r["official_source_url"])
    return titles, hosts, urls


manifest = []
n = 0
for region_key, region_countries in REGIONS.items():
    for theme_key, theme_desc in THEMES.items():
        n += 1
        titles, hosts, urls = dedup_for(region_countries)
        payload = {
            "shard": f"w2-{n:02d}",
            "agent_id": f"w2_{n:02d}",
            "today": TODAY,
            "theme": theme_key,
            "region": region_key,
            "region_countries": region_countries,
            "theme_brief": theme_desc,
            "target_records": 8,
            "dedup": {
                "note": "Already in ScholarZone. Do NOT produce a record for any of these, and do not "
                        "produce a near-duplicate of one under a different name.",
                "existing_titles": sorted(set(titles)),
                "existing_hosts": sorted(set(hosts)),
                "existing_official_source_urls": sorted(set(urls)),
            },
            "all_countries_in_database": countries,
        }
        path = os.path.join(OUT, f"w2-{n:02d}.json")
        json.dump(payload, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        manifest.append({"shard": payload["shard"], "file": f"research/wave2/shards/{payload['shard']}.json",
                         "theme": theme_key, "region": region_key, "existing_in_region": len(titles)})

for key, desc in GLOBAL_THEMES:
    n += 1
    payload = {
        "shard": f"w2-{n:02d}",
        "agent_id": f"w2_{n:02d}",
        "today": TODAY,
        "theme": key,
        "region": "global",
        "region_countries": countries,
        "theme_brief": desc,
        "target_records": 8,
        "dedup": {
            "note": "The complete existing catalogue. Do NOT produce a record for any of these, and do not "
                    "produce a near-duplicate of one under a different name.",
            "existing_titles": sorted({r["title"] for r in rows}),
            "existing_hosts": sorted({h for h in (host_of(r["official_source_url"]) for r in rows) if h}),
            "existing_official_source_urls": sorted({r["official_source_url"] for r in rows if r["official_source_url"]}),
        },
        "all_countries_in_database": countries,
    }
    json.dump(payload, open(os.path.join(OUT, f"w2-{n:02d}.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    manifest.append({"shard": payload["shard"], "file": f"research/wave2/shards/{payload['shard']}.json",
                     "theme": key, "region": "global", "existing_in_region": len(rows)})

json.dump({"shards": len(manifest), "items": manifest},
          open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8"), indent=2)
print("wave-2 shards:", len(manifest))
print("db records indexed:", len(rows), "countries:", len(countries))
for m in manifest[:3]:
    print("  ", m)