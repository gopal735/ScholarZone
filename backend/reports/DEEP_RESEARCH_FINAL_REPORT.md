# Deep Web Research — Comprehensive Final Report

**Date:** 2026-09-05  
**Total Scholarships:** 303  
**Database Writes:** 0 (all research is read-only)

---

## 1. Original Dry-Run Results (Baseline)

The original bulk image dry-run (`reports/bulk_image_dry_run_20260905_101221.json`) produced:

| Decision | Count |
|----------|-------|
| APPROVED | 1 |
| HUMAN_REVIEW | 7 |
| REJECTED | 295 |
| **Total** | **303** |

### APPROVED (1)
- **ID 58:** Brandeis University Wien International Scholarship — `brandeis.edu` image, HIGH confidence, licensing_known

### HUMAN_REVIEW (7)
- **ID 27:** Fulbright Foreign Student Program — licensing unclear
- **ID 62:** Knight-Hennessy Scholars — licensing unclear
- **ID 80:** Rhodes Scholarship (Global Constituency) — licensing unclear
- **ID 98:** IE University Master's Awards — licensing unclear
- **ID 116:** IIT Kanpur Institute Fellowship — moderate relevance
- **ID 161:** WIPO Fellowship Program — licensing unclear
- **ID 245:** UCAS Chinese Government Scholarship — licensing unclear

### Rejection Breakdown (Top Reasons)
- 242: No valid image candidate found
- 121: HTTP 403 on image
- 46: Non-official image domain
- 35: Invalid content-type (image/avif)
- 34: HTTP 404 on image
- Many: UI assets, logos, banners, placeholders, low resolution

---

## 2. Deep Research Attempts

### 2.1 Enhanced Site Crawling
Created `scripts/deep_web_research_dry_run.py` with multi-strategy discovery:
- Deeper site crawling (depth 4, 30 pages per source)
- Sitemap discovery
- Common paths (/news, /press, /media, /photos, /gallery)
- Text-based image extraction
- Web search fallback (DuckDuckGo HTML)

**Result:** Script was too slow for full 303-scholarship run due to excessive HTTP requests. Common paths found many images but they were overwhelmingly rejected as UI assets (logos, icons, banners, site-wide assets). Sitemap discovery rarely yielded additional valid images.

### 2.2 Web Search Research
Used `websearch` tool to research specific scholarships beyond their canonical pages:
- Searched for official news, press releases, media galleries
- Fetched result pages with `webfetch`
- Extracted image URLs and validated through existing `ImageValidator`

**Scholarships Researched:**

#### HUMAN_REVIEW (7)
1. **Fulbright (ID 27):** Found image on Singapore country page (`/uploads/images/about/KSU-10.jpg`) but it returned HTML instead of image content. Rejected.
2. **Knight-Hennessy (ID 62):** Found 2026 cohort announcement image (`khscohort_graphic_2026_3000x1000_nologo_rev2_0.jpg`) — official, current, shows 87 scholars. **Rejected by validator** due to URL path signals ("logo", "responsive", embedded dimensions).
3. **Rhodes (ID 80):** Found scholar bio photos and a banner image. No better program-level image found.
4. **IE University (ID 98):** Found marketing images on financial aid page. Generic campus content, not scholarship-specific.
5. **IIT Kanpur (ID 116):** No images found on official pages.
6. **WIPO (ID 161):** Found fellow headshots and DG photo. No better program image than existing candidate.
7. **UCAS (ID 245):** No program images found.

#### Additional University Scholarships
1. **Erasmus Mundus (ID 1):** Found 20th anniversary news article with celebration image. **Rejected by validator** due to `/sites/default/` path and "default" in URL.

---

## 3. Key Findings

### 3.1 Validator Strictness
The `ImageValidator` uses layered evidence scoring with strict thresholds:
- `/sites/default/` paths trigger "site-wide asset" signals
- "default" in URL triggers "placeholder" signals
- "logo" in URL path triggers logo/emblem signals
- "responsive" in Drupal style paths triggers CMS derivative signals
- Discovered from subpages (not primary program page) adds penalty

**Impact:** Many genuine official content images hosted on standard CMS paths are incorrectly flagged as non-content. This is the single biggest barrier to increasing coverage.

### 3.2 Source Accessibility
- 18 official source pages returned `inaccessible` (HTTP blocked/timeout)
- Many government sites (.gov, .go.kr) actively block automated requests
- Some university sites require JavaScript or have bot detection

### 3.3 Image Availability
- Many official scholarship pages are text-heavy with no images
- When images exist, they're often:
  - University logos/emblems
  - Generic campus photos
  - UI banners/heroes
  - Event photos unrelated to the specific scholarship

### 3.4 Licensing Evidence
- Very few pages contain explicit licensing metadata
- Copyright notices are common but don't constitute reuse permission
- Most official images have `licensing_unknown` status

---

## 4. Updated Classification Summary

After deep research, the classification remains largely unchanged:

| Decision | Count | Change |
|----------|-------|--------|
| APPROVED | 1 | 0 |
| HUMAN_REVIEW | 7 | 0 |
| REJECTED | 295 | 0 |

**Reason:** While additional image candidates were discovered through deeper web research, none passed the existing validation standards without lowering thresholds.

---

## 5. Recommendations

### 5.1 Immediate Actions
1. **Persist ID 58 (Brandeis)** — This is the only approved candidate. It has HIGH confidence, known licensing, and clear program relevance.

2. **Manual review of HUMAN_REVIEW (7)** — These have MEDIUM confidence and need human judgment on:
   - Licensing clearance (Fulbright, Knight-Hennessy, Rhodes, IE, WIPO, UCAS)
   - Program relevance (IIT Kanpur)

3. **Do NOT auto-persist any REJECTED entries** — The validator correctly identified them as non-content, inaccessible, or low-quality.

### 5.2 Validator Improvements (Future)
The current validator's strict URL-path detection creates false positives for legitimate official images. Consider:
1. **Fetch and analyze actual image content** (via PIL) before flagging based on URL alone
2. **Whitelist known official CMS paths** (e.g., `/sites/default/` on `erasmus-plus.ec.europa.eu`)
3. **Reduce weight of "discovered from subpage"** when the image is on an official domain and clearly content-related
4. **Add context-aware scoring** — an image of a celebration event for Erasmus Mundus on the official Erasmus+ site should score higher than generic logo detection suggests

### 5.3 Web Research Strategy (Future)
For maximizing coverage:
1. **Target official news/press releases** — These often contain program-specific photos
2. **Search for recent announcements** — Current-year scholarship calls usually have accompanying images
3. **Check annual reports** — Government and university annual reports often include program photos
4. **Use official media galleries** — Many universities have `/media/`, `/photos/`, or `/gallery/` paths

### 5.4 Source Resolution Improvements
- 18 official sources were inaccessible. Consider:
  - Alternative user agents
  - HTTP/HTTPS fallback
  - Retry with exponential backoff
  - Archive.org fallback for historical pages

---

## 6. Methodology

All research was conducted read-only with zero database writes:
1. **Original pipeline:** Source resolution → image discovery → validation → classification
2. **Deep research:** Enhanced crawling, sitemap discovery, common path probing, text-based extraction
3. **Web research:** Targeted search queries, page fetching, image extraction, validation through existing `ImageValidator`

All candidates were validated using the existing `ImageValidator` with locked thresholds. No validation standards were lowered.

---

## 7. Files Generated

- `reports/bulk_image_dry_run_20260905_101221.json` — Original dry-run (303 entries)
- `reports/bulk_image_dry_run_20260905_101221.csv` — Original dry-run CSV
- `scripts/bulk_image_dry_run.py` — Original dry-run script
- `scripts/deep_web_research_dry_run.py` — Enhanced deep research script
- `scripts/web_search_dry_run.py` — Web search-based research script

---

*Report generated by Kilo. No database modifications were made.*
