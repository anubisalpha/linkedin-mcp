"""Tests for linkedin_mcp.auth — OAuth flow, token refresh, token persistence."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from linkedin_mcp import auth
from linkedin_mcp.models import TokenData


class TestStartLogin:
    @patch("webbrowser.open")
    def test_opens_browser_with_auth_url(self, mock_open):
        state = auth.start_login("test_client_id")
        assert len(state) > 0
        mock_open.assert_called_once()
        url = mock_open.call_args[0][0]
        assert "test_client_id" in url
        assert "localhost" in url and "8585" in url
        assert "openid" in url

    @patch("linkedin_mcp.auth.webbrowser.open")
    def test_returns_unique_state_each_call(self, mock_open):
        s1 = auth.start_login("id")
        s2 = auth.start_login("id")
        assert s1 != s2


class TestExchangeCode:
    @patch("linkedin_mcp.auth.httpx.post")
    def test_exchanges_code_for_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "new_token",
                "expires_in": 5184000,
                "scope": "openid profile",
                "refresh_token": "refresh_abc",
                "refresh_token_expires_in": 15552000,
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        token = auth.exchange_code("auth_code_123", "client_id", "client_secret")
        assert token.access_token == "new_token"
        assert token.refresh_token == "refresh_abc"
        assert token.expires_in == 5184000

        call_data = mock_post.call_args[1]["data"]
        assert call_data["grant_type"] == "authorization_code"
        assert call_data["code"] == "auth_code_123"

    @patch("linkedin_mcp.auth.httpx.post")
    def test_handles_no_refresh_token(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "token",
                "expires_in": 3600,
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        token = auth.exchange_code("code", "id", "secret")
        assert token.refresh_token == ""
        assert token.refresh_token_expires_in == 0


    @patch("linkedin_mcp.auth.httpx.post")
    def test_normalises_comma_separated_scopes(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "token",
                "expires_in": 3600,
                "scope": "email,openid,profile,w_member_social",
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        token = auth.exchange_code("code", "id", "secret")
        assert set(token.scope.split()) == {"email", "openid", "profile", "w_member_social"}


class TestFetchSub:
    @patch("linkedin_mcp.auth.httpx.get")
    def test_returns_sub_from_userinfo(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"sub": "member_xyz"},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        sub = auth.fetch_sub("access_token")
        assert sub == "member_xyz"
        assert "Bearer access_token" in mock_get.call_args[1]["headers"]["Authorization"]


class TestRefreshAccessToken:
    @patch("linkedin_mcp.auth.httpx.post")
    def test_successful_refresh(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "refreshed_token",
                "expires_in": 5184000,
                "scope": "openid",
                "refresh_token": "new_refresh",
                "refresh_token_expires_in": 15552000,
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        token = auth.refresh_access_token("old_refresh", "client_id", "secret")
        assert token is not None
        assert token.access_token == "refreshed_token"
        assert token.refresh_token == "new_refresh"

        call_data = mock_post.call_args[1]["data"]
        assert call_data["grant_type"] == "refresh_token"
        assert call_data["refresh_token"] == "old_refresh"

    @patch("linkedin_mcp.auth.httpx.post")
    def test_failed_refresh_returns_none(self, mock_post):
        mock_post.return_value = MagicMock(status_code=401)
        mock_post.return_value.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())
        )

        token = auth.refresh_access_token("bad_refresh", "id", "secret")
        assert token is None

    @patch("linkedin_mcp.auth.httpx.post")
    def test_preserves_old_refresh_token_if_not_returned(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "new_access",
                "expires_in": 3600,
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        token = auth.refresh_access_token("original_refresh", "id", "secret")
        assert token.refresh_token == "original_refresh"


    @patch("linkedin_mcp.auth.httpx.post")
    def test_normalises_comma_separated_scopes_on_refresh(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "refreshed",
                "expires_in": 3600,
                "scope": "email,openid,profile,w_member_social",
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        token = auth.refresh_access_token("refresh_tok", "id", "secret")
        assert set(token.scope.split()) == {"email", "openid", "profile", "w_member_social"}


class TestAutoRefresh:
    @patch("linkedin_mcp.auth.load_token")
    def test_returns_token_if_not_expired(self, mock_load):
        token = TokenData(
            access_token="valid",
            expires_in=86400,
            scope="openid",
            sub="abc",
            expires_at="2099-01-01T00:00:00+00:00",
        )
        mock_load.return_value = token

        result = auth.auto_refresh("id", "secret")
        assert result is token

    @patch("linkedin_mcp.auth.load_token")
    def test_returns_none_if_no_token(self, mock_load):
        mock_load.return_value = None
        assert auth.auto_refresh("id", "secret") is None

    @patch("linkedin_mcp.auth.load_token")
    def test_returns_none_if_expired_no_refresh_token(self, mock_load):
        token = TokenData(
            access_token="expired",
            expires_in=0,
            scope="openid",
            sub="abc",
            refresh_token="",
            expires_at="2020-01-01T00:00:00+00:00",
        )
        mock_load.return_value = token
        assert auth.auto_refresh("id", "secret") is None

    @patch("linkedin_mcp.auth._get_token_path")
    @patch("linkedin_mcp.auth.refresh_access_token")
    @patch("linkedin_mcp.auth.load_token")
    def test_refreshes_expired_token_with_refresh_token(self, mock_load, mock_refresh, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "tokens.json"
        expired_token = TokenData(
            access_token="old",
            expires_in=0,
            scope="openid",
            sub="member1",
            refresh_token="my_refresh",
            expires_at="2020-01-01T00:00:00+00:00",
        )
        mock_load.return_value = expired_token

        new_token = TokenData(
            access_token="fresh",
            expires_in=5184000,
            scope="openid",
        )
        mock_refresh.return_value = new_token

        result = auth.auto_refresh("id", "secret")
        assert result is not None
        assert result.access_token == "fresh"
        assert result.sub == "member1"


class TestLoadAndClearToken:
    @patch("linkedin_mcp.auth._get_token_path")
    def test_load_returns_none_when_no_file(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "nope.json"
        assert auth.load_token() is None

    @patch("linkedin_mcp.auth._get_token_path")
    def test_clear_returns_false_when_no_file(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "nope.json"
        assert auth.clear_token() is False

    @patch("linkedin_mcp.auth._get_token_path")
    def test_clear_deletes_file(self, mock_path, tmp_path):
        path = tmp_path / "tokens.json"
        path.write_text("data", encoding="utf-8")
        mock_path.return_value = path

        assert auth.clear_token() is True
        assert not path.exists()


class TestLogin:
    @patch("linkedin_mcp.auth._get_token_path")
    @patch("linkedin_mcp.auth.fetch_sub")
    @patch("linkedin_mcp.auth.exchange_code")
    @patch("linkedin_mcp.auth.wait_for_callback")
    @patch("linkedin_mcp.auth.start_login")
    def test_full_login_flow(self, mock_start, mock_wait, mock_exchange, mock_sub, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "tokens.json"
        mock_start.return_value = "state123"
        mock_wait.return_value = "auth_code_456"
        mock_exchange.return_value = TokenData(
            access_token="at",
            expires_in=5184000,
            scope="openid",
        )
        mock_sub.return_value = "member_id"

        token = auth.login("client_id", "client_secret")
        assert token.access_token == "at"
        assert token.sub == "member_id"

        mock_start.assert_called_once_with("client_id")
        mock_wait.assert_called_once_with("state123")
        mock_exchange.assert_called_once_with("auth_code_456", "client_id", "client_secret")


class TestConfigurableCallbackPort:
    def test_default_port(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LINKEDIN_MCP_CALLBACK_PORT", None)
            assert auth._get_callback_port() == 8585

    def test_custom_port(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_CALLBACK_PORT": "9090"}):
            assert auth._get_callback_port() == 9090

    def test_redirect_uri_uses_custom_port(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_CALLBACK_PORT": "7777"}):
            uri = auth._get_redirect_uri()
            assert "7777" in uri
            assert "localhost" in uri
            assert "/callback" in uri

    @patch("webbrowser.open")
    def test_start_login_uses_custom_port(self, mock_open):
        with patch.dict(os.environ, {"LINKEDIN_MCP_CALLBACK_PORT": "9999"}):
            auth.start_login("test_id")
            url = mock_open.call_args[0][0]
            assert "9999" in url


class TestGetTokenPath:
    def test_default_path(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LINKEDIN_MCP_TOKEN_PATH", None)
            path = auth._get_token_path()
            assert path.name == "tokens.json"
            assert ".linkedin-mcp" in str(path)

    def test_custom_path(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_TOKEN_PATH": "/tmp/custom_tokens.json"}):
            path = auth._get_token_path()
            assert path.name == "custom_tokens.json"


class TestOAuthCallbackHandler:
    def test_successful_callback(self):
        import io
        import http.server

        handler_class = auth._OAuthCallbackHandler
        handler_class.auth_code = None
        handler_class.auth_state = None
        handler_class.error = None

        request = MagicMock()
        request.makefile.return_value = io.BytesIO()

        handler = handler_class.__new__(handler_class)
        handler.client_address = ("127.0.0.1", 12345)
        handler.server = MagicMock()
        handler.requestline = "GET /callback?code=abc123&state=xyz HTTP/1.1"
        handler.path = "/callback?code=abc123&state=xyz"
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.request_version = "HTTP/1.1"

        handler.do_GET()

        assert handler_class.auth_code == "abc123"
        assert handler_class.auth_state == "xyz"
        assert handler_class.error is None

    def test_error_callback(self):
        import io

        handler_class = auth._OAuthCallbackHandler
        handler_class.auth_code = None
        handler_class.auth_state = None
        handler_class.error = None

        handler = handler_class.__new__(handler_class)
        handler.client_address = ("127.0.0.1", 12345)
        handler.server = MagicMock()
        handler.requestline = "GET /callback?error=access_denied HTTP/1.1"
        handler.path = "/callback?error=access_denied"
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.request_version = "HTTP/1.1"

        handler.do_GET()

        assert handler_class.error == "access_denied"
        assert handler_class.auth_code is None

    def test_404_for_wrong_path(self):
        import io

        handler_class = auth._OAuthCallbackHandler
        handler_class.auth_code = None
        handler_class.auth_state = None
        handler_class.error = None

        handler = handler_class.__new__(handler_class)
        handler.client_address = ("127.0.0.1", 12345)
        handler.server = MagicMock()
        handler.requestline = "GET /wrong HTTP/1.1"
        handler.path = "/wrong"
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.request_version = "HTTP/1.1"

        handler.do_GET()

        assert handler_class.auth_code is None
        assert handler_class.error is None


class TestWaitForCallback:
    def test_timeout_raises(self):
        with patch("linkedin_mcp.auth._get_callback_port", return_value=18901):
            with pytest.raises(TimeoutError, match="timeout"):
                auth.wait_for_callback("state123", timeout=0.3)

    def test_success_returns_code(self):
        import threading
        import urllib.request

        port = 18902
        with patch("linkedin_mcp.auth._get_callback_port", return_value=port):
            def send_callback():
                import time
                time.sleep(0.2)
                try:
                    urllib.request.urlopen(
                        f"http://localhost:{port}/callback?code=abc123&state=mystate",
                        timeout=2,
                    )
                except Exception:
                    pass

            t = threading.Thread(target=send_callback, daemon=True)
            t.start()
            code = auth.wait_for_callback("mystate", timeout=3)
            assert code == "abc123"

    def test_error_in_callback_raises(self):
        import threading
        import urllib.request

        port = 18903
        with patch("linkedin_mcp.auth._get_callback_port", return_value=port):
            def send_error():
                import time
                time.sleep(0.2)
                try:
                    urllib.request.urlopen(
                        f"http://localhost:{port}/callback?error=access_denied",
                        timeout=2,
                    )
                except Exception:
                    pass

            t = threading.Thread(target=send_error, daemon=True)
            t.start()
            with pytest.raises(RuntimeError, match="access_denied"):
                auth.wait_for_callback("state", timeout=3)

    def test_state_mismatch_raises(self):
        import threading
        import urllib.request

        port = 18904
        with patch("linkedin_mcp.auth._get_callback_port", return_value=port):
            def send_wrong_state():
                import time
                time.sleep(0.2)
                try:
                    urllib.request.urlopen(
                        f"http://localhost:{port}/callback?code=abc&state=wrong",
                        timeout=2,
                    )
                except Exception:
                    pass

            t = threading.Thread(target=send_wrong_state, daemon=True)
            t.start()
            with pytest.raises(RuntimeError, match="state mismatch"):
                auth.wait_for_callback("correct_state", timeout=3)

    def test_no_code_raises(self):
        import threading
        import urllib.request

        port = 18905
        with patch("linkedin_mcp.auth._get_callback_port", return_value=port):
            def send_no_code():
                import time
                time.sleep(0.2)
                try:
                    urllib.request.urlopen(
                        f"http://localhost:{port}/callback?state=mystate",
                        timeout=2,
                    )
                except Exception:
                    pass

            t = threading.Thread(target=send_no_code, daemon=True)
            t.start()
            with pytest.raises(RuntimeError, match="No authorization code"):
                auth.wait_for_callback("mystate", timeout=3)
