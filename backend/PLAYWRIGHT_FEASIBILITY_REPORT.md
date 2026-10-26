# Playwright JS-Rendering Feasibility Report

**Date:** 2026-09-05  
**Objective:** Determine whether optional JavaScript rendering with Playwright materially improves image discovery for the 290 rejected scholarships.  
**Scope:** READ-ONLY prototype. No changes to ImageDiscoveryService or ImageValidator. Zero database writes.

---

## Methodology

1. Identified the cleanest integration point: `ImageDiscoveryService._fetch_page()` — add an optional `render_js` parameter that returns rendered HTML instead of static `httpx` response. All downstream parsing (BeautifulSoup, image extraction, validation) remains unchanged.
2. Selected 5 representative scholarships known for modern JS-heavy frameworks or text-heavy academic sites:
   - ID 63: Michigan State University (Next.js, 14 static candidates)
   - ID 68: Gates Cambridge Scholarship (modern CMS, 10 static candidates)
   - ID 17: Erasmus+ Student Exchange (EU modern portal, 4 static candidates)
   - ID 65: Clarendon Fund Scholarship (Oxford, 0 static candidates — HTTP 403)
   - ID 121: Berea College Tuition Promise (Next.js, 13 static candidates)
3. For each scholarship, ran the existing static discovery pipeline, then ran a prototype JS-rendered path using Playwright Chromium (`wait_until="domcontentloaded"`, 1s settle).
4. Ran both candidate sets through the unchanged `ImageValidator`.
5. Measured: new images discovered, valid content images, rejected images, runtime.

---

## Results

| ID | Scholarship | Static Candidates | JS Candidates | New Images | New Valid | New Rejected | Static Fetch | JS Render | Overhead |
|----|-------------|-------------------|---------------|------------|-----------|--------------|--------------|-----------|----------|
| 63 | MSU Int'l Merit | 14 | 14 | 0 | 0 | 0 | 2,831 ms | 3,324 ms | +493 ms |
| 68 | Gates Cambridge | 10 | 10 | 0 | 0 | 0 | 1,699 ms | 5,169 ms | +3,470 ms |
| 17 | Erasmus+ Exchange | 4 | 4 | 0 | 0 | 0 | 939 ms | 4,141 ms | +3,202 ms |
| 65 | Clarendon Fund | 0 | 5 | 5 | 0 | 5 | 415 ms | 2,174 ms | +1,759 ms |
| 121 | Berea College | 13 | 13 | 0 | 0 | 0 | 502 ms | 4,213 ms | +3,711 ms |

**Aggregate:**
- **New images discovered via JS rendering:** 5 (all from Clarendon only)
- **New valid images (APPROVED / HUMAN_REVIEW):** 0
- **New rejected images:** 5 (all Clarendon images returned HTTP 403)
- **Average static fetch time:** 1,277 ms
- **Average JS render time:** 3,804 ms
- **Average rendering overhead:** +2,527 ms per page (~2.5x slower)

---

## Analysis

### Why JS Rendering Did Not Help

1. **Next.js proxy URLs are already visible in static HTML.**  
   MSU and Berea both expose `_next/image?url=...&w=...&q=...` paths in the initial HTML. The validator rejects these as infrastructure signals, but Playwright rendering does not surface any additional original-image URLs that bypass the proxy.

2. **Modern academic CMS sites serve the same DOM content.**  
   Gates Cambridge and Erasmus+ returned identical image sets in static vs rendered DOM. The image discovery failure is not a JS-rendering problem — it is a content-availability problem (text-heavy pages, JS-loaded carousels with generic institutional assets, or login-gated media).

3. **Oxford assets are anti-bot protected.**  
   Clarendon's static fetch returned HTTP 403. Playwright rendered 5 image URLs, but every image URL itself returned HTTP 403 when fetched by the validator. The asset server (`assets-oxweb.admin.ox.ac.uk`) blocks non-browser or unauthenticated requests regardless of rendering method.

4. **No new APPROVED or HUMAN_REVIEW candidates.**  
   The 5 newly discovered Clarendon images were all rejected as unreachable. Across all 5 scholarships, the confidence and approval rates were identical between static and rendered paths.

---

## Integration Assessment

**Cleanest integration point:** `ImageDiscoveryService._fetch_page()` at `app/services/image_discovery.py:134`.

A minimal optional integration would look like:

```python
def _fetch_page(self, url: str, render_js: bool = False) -> PageFetchResult:
    if render_js:
        return self._fetch_page_js(url)
    # existing httpx logic ...
```

This keeps `ImageDiscoveryService` and `ImageValidator` completely untouched. The `render_js` flag would be passed from a new orchestrator (e.g., `JsAugmentedDiscoveryService`) so the existing dry-run pipeline is unaffected.

**However, integration is NOT recommended** for the following reasons:

- **Zero yield:** 0 new valid images across 5 representative scholarships.
- **High cost:** +2.5s average overhead per page. Scaled to 297 scholarships, this adds ~12+ minutes of pure rendering time with no coverage gain.
- **No coverage improvement:** The bottleneck is not missing images in static HTML; it is that official pages genuinely lack suitable cover photography, or their images are behind authentication/CDN bot protection.

---

## Verdict

**Playwright JS rendering is NOT worth integrating into the ScholarZone image discovery pipeline.**

The existing static-HTML pipeline already captures all publicly accessible image URLs on these sites. The discovery gap is caused by:
- Text-heavy official pages without program photography
- JS-rendered carousels that contain only generic institutional assets
- Authenticated or anti-bot-protected media servers
- Strict validator rules that correctly reject logos, banners, and infrastructure proxies

**Recommended next step:**  
Focus manual curation effort on high-priority scholarships with known public media kits (e.g., Chevening, Rhodes, Gates Cambridge press rooms) rather than investing in browser automation. If the team later decides to automate, the integration point is documented above and the prototype code can be resurrected from this report.
