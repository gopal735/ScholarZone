"""Fetch Brandeis page and inspect the wein.jpg image context."""
import httpx

url = "https://www.brandeis.edu/isso/images/programs/wien/"
resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0, follow_redirects=True)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('content-type')}")
print(f"Length: {len(resp.text)}")

# Find the image in the HTML
if "wein.jpg" in resp.text:
    idx = resp.text.find("wein.jpg")
    print(f"\nContext around wein.jpg (chars {max(0,idx-200)} to {idx+200}):")
    print(resp.text[max(0,idx-200):idx+200])
else:
    print("wein.jpg not found in page")
