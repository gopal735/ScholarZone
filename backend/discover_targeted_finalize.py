"""Probe all candidate image URLs and produce final consolidated summary for the 10 scholarships."""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

OUT = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_targeted_FINAL.json')
TARGETED = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_targeted.json')
RETRY = Path(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\image_discovery_targeted_retry.json')

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def probe(url, timeout=20):
    headers = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            r = client.get(url)
            ct = r.headers.get("content-type", "")
            cl = r.headers.get("content-length")
            ok = r.status_code == 200 and ct.startswith("image/")
            w, h = None, None
            if ok and ct in ("image/png", "image/jpeg", "image/webp", "image/gif"):
                data = r.content
                try:
                    if ct == "image/png" and len(data) > 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
                        import struct
                        w, h = struct.unpack(">II", data[16:24])
                    elif ct == "image/jpeg" and len(data) > 4 and data[:2] == b"\xff\xd8":
                        i = 2
                        while i < len(data) - 9:
                            if data[i] != 0xff: i += 1; continue
                            mk = data[i+1]
                            if mk in (0xc0,0xc1,0xc2,0xc3):
                                h = int.from_bytes(data[i+5:i+7], "big"); w = int.from_bytes(data[i+7:i+9], "big"); break
                            seg = int.from_bytes(data[i+2:i+4], "big"); i += 2 + seg
                    elif ct == "image/gif" and len(data) > 10 and data[:6] in (b"GIF87a", b"GIF89a"):
                        w = int.from_bytes(data[6:8], "little"); h = int.from_bytes(data[8:10], "little")
                    elif ct == "image/webp" and len(data) > 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                        if data[12:16] == b"VP8X":
                            w = int.from_bytes(data[24:27], "little") + 1; h = int.from_bytes(data[27:30], "little") + 1
                except: pass
            return {"reachable": ok, "http_status": r.status_code, "content_type": ct, "width": w, "height": h, "content_length": int(cl) if cl and cl.isdigit() else None}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


# Taiwan: best from og:image
taiwan = {
    "scholarship_id": 34,
    "title": "Taiwan Scholarship Program",
    "official_source_url": "https://www.studyintaiwan.org/taiwan_scholarship",
    "best_image_url": "https://web.archive.org/web/20230115030643im_/https://www.studyintaiwan.org/contents/frontend/assets/images/sit_og.jpg",
    "live_image_url": "https://www.studyintaiwan.org/contents/frontend/assets/images/sit_og.jpg",
    "source_page": "https://web.archive.org/web/2023/https://www.studyintaiwan.org/taiwan_scholarship",
    "discovery_method": "og:image (via Wayback Machine; live site SSL-blocked)",
    "alt_text": None,
    "notes": "Live domain (studyintaiwan.org) returned SSL CERTIFICATE_VERIFY_FAILED and edutwscholarship.moe.gov.tw DNS failed. Re-fetched via Wayback Machine 2023 snapshot."
}

# Load other 9 from prior runs
data_t = json.loads(TARGETED.read_text(encoding="utf-8"))
data_r = json.loads(RETRY.read_text(encoding="utf-8"))
all_data = {r["scholarship_id"]: r for r in data_t}
for r in data_r:
    all_data[r["scholarship_id"]] = r

# Probe each best image
final = []
for sid in [26, 28, 29, 30, 31, 32, 33, 34, 35, 36]:
    if sid == 34:
        rec = {"scholarship_id": taiwan["scholarship_id"], "title": taiwan["title"], "official_source_url": taiwan["official_source_url"], "best_image_url": taiwan["best_image_url"], "source_page": taiwan["source_page"], "discovery_method": taiwan["discovery_method"], "alt_text": taiwan["alt_text"]}
        print(f"\nID {sid}: probing live image...")
        live_probe = probe(taiwan["live_image_url"])
        rec["live_image_probe"] = live_probe
        if live_probe.get("width") and live_probe.get("height"):
            rec["width"] = live_probe["width"]; rec["height"] = live_probe["height"]
        else:
            wb_probe = probe(taiwan["best_image_url"])
            rec["wayback_image_probe"] = wb_probe
            rec["width"] = wb_probe.get("width"); rec["height"] = wb_probe.get("height")
        rec["notes"] = taiwan["notes"]
        final.append(rec)
        continue

    r = all_data.get(sid)
    if not r:
        final.append({"scholarship_id": sid, "error": "no data"}); continue
    rec = {
        "scholarship_id": sid,
        "title": r.get("title"),
        "official_source_url": r.get("official_source_url") or r.get("db_official_source_url"),
        "best_image_url": r.get("best_image_url"),
        "source_page": r.get("source_page"),
        "discovery_method": r.get("discovery_method"),
        "alt_text": r.get("alt_text"),
        "width": r.get("width"),
        "height": r.get("height"),
    }
    if rec["best_image_url"]:
        print(f"ID {sid}: probing {rec['best_image_url'][:80]}...")
        p = probe(rec["best_image_url"])
        rec["image_probe"] = p
        if p.get("width") and p.get("height"):
            rec["width"] = p["width"]; rec["height"] = p["height"]
    else:
        rec["notes"] = r.get("notes", "No image found")
    final.append(rec)
    time.sleep(0.2)

OUT.write_text(json.dumps(final, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
print(f"\nFinal summary saved to {OUT}")
print("\n--- SUMMARY ---")
for r in final:
    print(f"\nID {r['scholarship_id']} - {r['title']}")
    print(f"  image: {r.get('best_image_url')}")
    print(f"  page:  {r.get('source_page')}")
    print(f"  method: {r.get('discovery_method')}  dims: {r.get('width')}x{r.get('height')}")
