# ScholarZone Official Cover Image Discovery — Dry-Run Report

**Date:** 2026-09-05  
**Total scholarships in database:** 303  
**Scholarships without images:** 297  
**Scholarships with existing images:** 6 (IDs: 1, 2, 3, 4, 5, 58)  

---

## Executive Summary

Automated discovery + validation was run on all 297 scholarships lacking cover images. The pipeline uses the existing `SourceResolverService`, `ImageDiscoveryService`, and `ImageValidator` components.

**Results:**
- **APPROVED (HIGH confidence):** 0
- **HUMAN_REVIEW (MEDIUM confidence):** 6
- **REJECTED (LOW confidence):** 291

The automated pipeline found very few usable official images because:
1. Many official scholarship pages are text-heavy government sites without program photography
2. Modern university sites load images via JavaScript, which static HTML fetching cannot capture
3. The validator strictly rejects logos, banners, UI assets, and images without clear licensing evidence
4. Many discovered images are generic site-wide assets rather than scholarship-specific content

---

## Automated Discovery Statistics

### By Source Type
| Type | Count |
|------|-------|
| University (`official_university`) | 33 |
| Official Scholarship Program (`official_scholarship`) | 11 |
| Provider (`official_provider`) | 9 |
| Government (`official_government`) | 9 |
| Unknown/None | 234 |

### By Source Resolution Type
| Resolution | Count |
|------------|-------|
| Exact Program Page | 200 |
| Official Application Page | 64 |
| Inaccessible | 17 |
| Root Domain | 9 |
| None | 6 |

### By Country (Top 10)
| Country | Count |
|---------|-------|
| Australia | 26 |
| USA | 24 |
| Austria | 22 |
| UK | 17 |
| Switzerland | 13 |
| Germany | 12 |
| Netherlands | 12 |
| Italy | 12 |
| Canada | 12 |
| France | 11 |

### Top Rejection Reasons
| Reason | Count |
|--------|-------|
| No candidates found | 284 |
| Non-content image (banner/logo/UI) | ~200+ |
| Invalid/unreachable image | ~50+ |
| Low resolution | ~30+ |
| Duplicate image | ~10+ |

---

## HUMAN_REVIEW Candidates (6)

These candidates passed automated validation but require manual verification due to licensing uncertainty.

| ID | Scholarship | Image URL | Source Page | Confidence | Reason |
|----|-------------|-----------|-------------|------------|--------|
| 27 | Fulbright Foreign Student Program | `https://foreign.fulbrightonline.org/images/home_sliders/slide-04.jpg` | Program page | MEDIUM | Licensing unclear |
| 62 | Knight-Hennessy Scholars | `https://knight-hennessy.stanford.edu/sites/g/files/sbiybj23586/files/styles/card_1192x596/public/media/image/khs_111519_0118_1.jpg` | Program overview | MEDIUM | Licensing unclear |
| 98 | IE University Master's Awards | `https://images.thesaurus.ie.edu/f/jpg/w/1280/h/768/laidlawstudents-1` | Scholarship list | MEDIUM | Licensing unclear |
| 80 | Rhodes Scholarship (Global) | `https://www.rhodeshouse.ox.ac.uk/media/4etp20fx/scholars-2023-01-23-1323.jpg` | Scholarship page | MEDIUM | Licensing unclear |
| 116 | IIT Kanpur Institute Fellowship | `https://iitk.ac.in/oir/images/cards/fact.jpg` | OIR page | MEDIUM | Moderate relevance |
| 161 | WIPO Fellowship Program | `https://www.wipo.int/documents/d/wipo/images-photos-director-general-daren-tang-with-the-young-experts-960.webp` | Fellowship page | MEDIUM | Licensing unclear |

**Note:** All 6 candidates are on official domains and appear to be genuine content photography, but none of the fetched pages contained explicit Creative Commons licensing or reuse permissions. Standard institutional © notices were present on all pages, which assert restriction rather than permission.

---

## Manual Research Findings

### Fulbright Foreign Student Program (ID 27)
- **Official page:** `https://foreign.fulbrightonline.org/about/foreign-student-program`
- **Image found:** `https://foreign.fulbrightonline.org/uploads/images/about/KSU-10.jpg`
- **Assessment:** Image described as "Foreign Fulbright Grantees" — genuine program photography
- **Issue:** Image URL redirects to login page when accessed directly; not publicly accessible without authentication
- **Decision:** Cannot use — requires authentication

### Gates Cambridge Scholarship (ID 68)
- **Official page:** `https://www.gatescambridge.org/programme/the-scholarship/`
- **Assessment:** Text-heavy page, no images captured in static HTML
- **Issue:** Likely JS-loaded images; no discoverable cover image via static fetch
- **Decision:** No trustworthy image found via automated or manual research

### Swiss Government Excellence Scholarship (ID 7)
- **Official page:** `https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships`
- **Assessment:** Pure text page, no images
- **Decision:** No trustworthy image found

### Eiffel Excellence Scholarship (ID 6)
- **Official page:** `https://www.campusfrance.org/en/france-excellence-eiffel-scholarship-program`
- **Assessment:** Page contains PDF leaflets but no hero/cover image in HTML
- **Issue:** PDFs contain stock photos (iStock) which are not suitable
- **Decision:** No trustworthy image found

---

## Top Source Domains (From Candidates)
| Domain | Count |
|--------|-------|
| campusfrance.org | Many (rejected) |
| daad.de | Many (rejected) |
| erasmus-plus.ec.europa.eu | Many (rejected) |
| studyinkorea.go.kr | Many (rejected) |
| studyinjapan.go.jp | Many (rejected) |

---

## Duplicate Images
- No duplicate image URLs were found across different scholarships in the automated results
- Each scholarship's best candidate (when found) was unique

---

## False-Positive Candidates
The validator correctly rejected:
- Logos and emblems (`logo_eiffel.jpg`, `logo-campus-france.png`)
- Social media icons (`Picto_Instagram_1.png`, `Picto_Facebook_1.png`)
- Generic banners (`header-banner.jpg`, `hero_desktop`)
- Stock images (`Fotolia_*`, `istockphoto-*`)
- UI elements (`btn_drawer_close.svg`, `icon_mobile_sns01.png`)
- Document/flyer scans (`english_scholarship_pamphlet_1.jpg`)
- Error/placeholder images

---

## Conclusions

1. **Automated discovery is insufficient** for this dataset. Out of 297 scholarships, only 6 produced candidates suitable for human review, and 0 achieved HIGH confidence.

2. **Official pages rarely expose suitable cover images** in static HTML. Many are:
   - Text-heavy government portals
   - JavaScript-rendered modern sites
   - PDF-based scholarship bulletins with stock photography
   - Generic institutional homepages

3. **Licensing is the primary blocker** for HIGH confidence. Even when genuine program photography is found, official pages rarely include explicit reuse permissions.

4. **Recommended approach for manual curation:**
   - Focus on scholarships with known visual branding (major programs like Chevening, Rhodes, Gates Cambridge)
   - Check official university/program media kits and press rooms
   - Verify licensing directly with institutions when possible
   - Accept that many government scholarships may not have suitable cover images

5. **Safe to persist:** The 6 HUMAN_REVIEW candidates are technically valid images on official domains, but require human verification of licensing before persistence.

---

## Recommendations

1. **Do not auto-persist any images** from this batch — the 0% HIGH confidence rate indicates the pipeline needs calibration for this dataset.

2. **Manual research priority list** (scholarships most likely to have official images):
   - Chevening Scholarship (UK) — has media kit
   - Rhodes Scholarship (Oxford) — has scholar photos
   - Gates Cambridge Scholarship — has program films/photos
   - Knight-Hennessy Scholars (Stanford) — has verified content image
   - Fulbright Program — has grantee photos (but access restricted)
   - DAAD Scholarship — may have imagery in JS-loaded components

3. **Pipeline improvements needed:**
   - Add JavaScript rendering support (Playwright/Selenium) for modern sites
   - Implement image deduplication across scholarship candidates
   - Add licensing detection from page footers and meta tags
   - Consider accepting standard institutional © for government/public scholarships where reuse is implied

---

*Report generated by automated batch discovery pipeline + manual verification*
