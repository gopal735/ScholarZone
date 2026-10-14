"""Check Brandeis wein.jpg properties."""
import httpx
from PIL import Image
import io

url = "https://www.brandeis.edu/isso/images/programs/wien/wein.jpg"
resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0, follow_redirects=True)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('content-type')}")
print(f"Content-Length: {resp.headers.get('content-length')}")
print(f"Actual body length: {len(resp.content)}")

# Check if it's actually an image
ct = resp.headers.get("content-type", "").split(";")[0].strip().lower()
print(f"Normalized CT: {ct}")

if ct in ("image/jpeg", "image/png", "image/gif", "image/webp"):
    try:
        img = Image.open(io.BytesIO(resp.content))
        print(f"Dimensions: {img.width}x{img.height}")
        print(f"Mode: {img.mode}")
        print(f"Format: {img.format}")
    except Exception as e:
        print(f"Pillow error: {e}")
        # Check first bytes
        print(f"First 20 bytes: {resp.content[:20]}")
