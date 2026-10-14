"""Directly test what the GET returns for Brandeis wein.jpg."""
import httpx

url = "https://www.brandeis.edu/isso/images/programs/wien/wein.jpg"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

print("=== HEAD request ===")
try:
    resp_head = httpx.head(url, headers=headers, timeout=30.0, follow_redirects=True)
    print(f"Status: {resp_head.status_code}")
    print(f"Content-Type: {resp_head.headers.get('content-type')}")
    print(f"Length: {len(resp_head.content)}")
except Exception as e:
    print(f"HEAD error: {e}")

print("\n=== GET request (stream=True) ===")
try:
    resp_get = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True, stream=True)
    print(f"Status: {resp_get.status_code}")
    print(f"Content-Type: {resp_get.headers.get('content-type')}")
    actual_ct = resp_get.headers.get("content-type", "").split(";")[0].strip().lower()
    print(f"Normalized CT: {actual_ct}")
    body = resp_get.read()
    print(f"Body length: {len(body)}")
    print(f"Body first 100 chars: {body[:100]}")
    resp_get.close()
except Exception as e:
    print(f"GET error: {e}")

print("\n=== GET request (no stream) ===")
try:
    resp_get2 = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
    print(f"Status: {resp_get2.status_code}")
    print(f"Content-Type: {resp_get2.headers.get('content-type')}")
    actual_ct2 = resp_get2.headers.get("content-type", "").split(";")[0].strip().lower()
    print(f"Normalized CT: {actual_ct2}")
    print(f"Body length: {len(resp_get2.content)}")
    print(f"Body first 100 chars: {resp_get2.content[:100]}")
except Exception as e:
    print(f"GET error: {e}")
