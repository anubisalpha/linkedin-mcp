from __future__ import annotations

import http.server
import os
import secrets
import threading
import urllib.parse
import webbrowser

import httpx

from .models import TokenData

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
SCOPES = "openid profile email w_member_social"
CALLBACK_PORT = 8585
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"


def _get_token_path() -> "pathlib.Path":
    import pathlib

    custom = os.environ.get("LINKEDIN_MCP_TOKEN_PATH")
    if custom:
        return pathlib.Path(custom)
    return pathlib.Path.home() / ".linkedin-mcp" / "tokens.json"


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles the OAuth redirect and captures the authorization code."""

    auth_code: str | None = None
    auth_state: str | None = None
    error: str | None = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        if "error" in params:
            _OAuthCallbackHandler.error = params["error"][0]
            self._respond("LinkedIn authorization failed. You can close this tab.")
            return

        _OAuthCallbackHandler.auth_code = params.get("code", [None])[0]
        _OAuthCallbackHandler.auth_state = params.get("state", [None])[0]
        self._respond("Authorization successful! You can close this tab and return to Claude.")

    def _respond(self, message: str) -> None:
        body = f"<html><body><h2>{message}</h2></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, format: str, *args: object) -> None:
        pass


def start_login(client_id: str) -> str:
    """Build the authorization URL and open it in the browser.

    Returns the CSRF state token for verification.
    """
    state = secrets.token_urlsafe(32)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": SCOPES,
    }
    url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    webbrowser.open(url)
    return state


def wait_for_callback(expected_state: str, timeout: float = 120) -> str:
    """Start a local HTTP server and wait for the OAuth callback.

    Returns the authorization code.
    """
    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.auth_state = None
    _OAuthCallbackHandler.error = None

    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), _OAuthCallbackHandler)
    server.timeout = timeout

    received = threading.Event()
    original_do_GET = _OAuthCallbackHandler.do_GET

    def patched_do_GET(self: _OAuthCallbackHandler) -> None:
        original_do_GET(self)
        received.set()

    _OAuthCallbackHandler.do_GET = patched_do_GET  # type: ignore[assignment]

    try:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        if not received.wait(timeout=timeout):
            raise TimeoutError("OAuth callback not received within timeout")
    finally:
        server.shutdown()
        _OAuthCallbackHandler.do_GET = original_do_GET  # type: ignore[assignment]

    if _OAuthCallbackHandler.error:
        raise RuntimeError(f"LinkedIn authorization error: {_OAuthCallbackHandler.error}")

    if _OAuthCallbackHandler.auth_state != expected_state:
        raise RuntimeError("OAuth state mismatch — possible CSRF attack")

    if not _OAuthCallbackHandler.auth_code:
        raise RuntimeError("No authorization code received")

    return _OAuthCallbackHandler.auth_code


def exchange_code(code: str, client_id: str, client_secret: str) -> TokenData:
    """Exchange the authorization code for an access token."""
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    data = resp.json()
    token = TokenData(
        access_token=data["access_token"],
        expires_in=data["expires_in"],
        scope=data.get("scope", ""),
        refresh_token=data.get("refresh_token", ""),
        refresh_token_expires_in=data.get("refresh_token_expires_in", 0),
    )
    return token


def fetch_sub(access_token: str) -> str:
    """Fetch the member's 'sub' identifier from the userinfo endpoint."""
    resp = httpx.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()["sub"]


def login(client_id: str, client_secret: str) -> TokenData:
    """Run the full OAuth login flow: browser auth, callback, token exchange.

    Returns a TokenData with the access token and sub identifier, saved to disk.
    """
    state = start_login(client_id)
    code = wait_for_callback(state)
    token = exchange_code(code, client_id, client_secret)
    token.sub = fetch_sub(token.access_token)
    token.save(_get_token_path())
    return token


def load_token() -> TokenData | None:
    """Load a previously saved token from disk."""
    return TokenData.load(_get_token_path())


def clear_token() -> bool:
    """Delete the stored token file. Returns True if a file was deleted."""
    path = _get_token_path()
    if path.exists():
        path.unlink()
        return True
    return False
