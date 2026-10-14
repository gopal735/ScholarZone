"""One-off cache-bust check against the deployed API.

The call is lazy — behind ``__main__`` — so importing this file costs
nothing. It used to run at import, which made every tool that so much as
scanned the directory (a linter, a test that enumerates scripts, an import
in a REPL) issue a live request against production. A script that performs
a network call on import cannot be inspected safely.
"""

if __name__ == "__main__":
    import requests

    r = requests.get(
        'https://scholarzone-api-2ee2d.containers.snapdeploy.app/health',
        timeout=60,
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'X-Cache-Bypass': '1'}
    )
    print(f"Status: {r.status_code}")
    print(f"X-Wake-Page: {r.headers.get('X-Wake-Page', 'not set')}")
    print(f"Content-Type: {r.headers.get('Content-Type', 'not set')}")
    print(f"Body (first 300 chars): {r.text[:300]}")
