import http.server
import threading
import requests
import time
import urllib.parse
import webbrowser
import os

# GitHub CLI OAuth app credentials (from source code)
client_id = "178c6fc778ccc68e1d6a"
client_secret = "34ddeff2b558a23d38fba8a6de74f086ede1cc0b"
redirect_uri = "http://localhost:8765/callback"

# Create a local server to receive the OAuth callback
class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    code = None
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            OAuthCallbackHandler.code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization complete! You can close this window.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>No code received</h1>")
    
    def log_message(self, format, *args):
        pass  # Suppress logs

server = http.server.HTTPServer(("127.0.0.1", 8765), OAuthCallbackHandler)
server.timeout = 1
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print("Local callback server running on http://localhost:8765/callback")

# Start the OAuth flow
auth_url = "https://github.com/login/oauth/authorize"
params = {
    "client_id": client_id,
    "redirect_uri": redirect_uri,
    "scope": "repo",
    "response_type": "code",
    "state": "scholarzone_verify",
}
url = f"{auth_url}?{urllib.parse.urlencode(params)}"
print(f"\nVisit this URL to authorize: {url}")
print(f"You have 60 seconds to complete the authorization...")

# Open browser (will likely fail but let's try)
try:
    webbrowser.open(url)
    print("Browser opened (if available)")
except:
    print("Browser not available")

# Wait for the callback
print("\nWaiting for OAuth callback...")
for i in range(60):
    if OAuthCallbackHandler.code:
        break
    time.sleep(1)

if OAuthCallbackHandler.code:
    print(f"Received code: {OAuthCallbackHandler.code[:20]}...")
    
    # Exchange code for token
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": OAuthCallbackHandler.code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        headers={"Accept": "application/json"},
    )
    print(f"\nToken exchange: HTTP {token_resp.status_code}")
    if token_resp.status_code == 200:
        token_data = token_resp.json()
        if "access_token" in token_data:
            token = token_data["access_token"]
            print(f"Token: {token[:10]}...{token[-10:]}")
            print(f"Scope: {token_data.get('scope')}")
            with open("gh_token.txt", "w") as f:
                f.write(token)
            print("Token saved to gh_token.txt")
        else:
            print(f"Response: {token_data}")
    else:
        print(f"Error: {token_resp.text[:300]}")
    
    # Set up gh CLI with this token
    import subprocess
    result = subprocess.run(
        ["gh", "auth", "login", "--with-token"],
        input=f"token={token}\n",
        capture_output=True, text=True, timeout=10,
        env={**os.environ}
    )
    print(f"\ngh auth login: {result.stdout} {result.stderr}")
else:
    print("No callback received within 60 seconds")
    print("The OAuth web flow requires a browser to visit the authorization URL.")

server.shutdown()
