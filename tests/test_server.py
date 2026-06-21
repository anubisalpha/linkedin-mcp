"""Tests for linkedin_mcp.server — MCP tool handlers."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from linkedin_mcp.models import PostResult, Profile, TokenData
from linkedin_mcp.server import (
    _handle_article_post,
    _handle_delete_post,
    _handle_health,
    _handle_login,
    _handle_logout,
    _handle_profile,
    _handle_status,
    _handle_text_post,
    _require_token,
    call_tool,
    list_tools,
)


def _make_token(**overrides) -> TokenData:
    defaults = {
        "access_token": "test_token",
        "expires_in": 5184000,
        "scope": "openid profile email w_member_social",
        "sub": "member1",
        "refresh_token": "",
        "refresh_token_expires_in": 0,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "created_at": "2026-06-01T00:00:00+00:00",
    }
    defaults.update(overrides)
    return TokenData(**defaults)


class TestListTools:
    @pytest.mark.asyncio
    async def test_returns_all_tools(self):
        tools = await list_tools()
        names = [t.name for t in tools]
        assert "linkedin_login" in names
        assert "linkedin_logout" in names
        assert "linkedin_status" in names
        assert "linkedin_profile" in names
        assert "linkedin_health" in names
        assert "linkedin_audit_log" in names
        assert "linkedin_create_text_post" in names
        assert "linkedin_create_article_post" in names
        assert "linkedin_create_image_post" in names
        assert "linkedin_delete_post" in names
        assert len(tools) == 10


class TestCallTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await call_tool("linkedin_nonexistent", {})
        assert result.isError is True
        assert "Unknown tool" in result.content[0].text


class TestRequireToken:
    @patch("linkedin_mcp.server.auth.load_token")
    def test_raises_when_no_token(self, mock_load):
        mock_load.return_value = None
        with pytest.raises(RuntimeError, match="Not logged in"):
            _require_token()

    @patch("linkedin_mcp.server.auth.load_token")
    def test_returns_valid_token(self, mock_load):
        token = _make_token()
        mock_load.return_value = token
        assert _require_token() is token

    @patch("linkedin_mcp.server.auth.auto_refresh")
    @patch("linkedin_mcp.server._get_credentials", return_value=("id", "secret"))
    @patch("linkedin_mcp.server.auth.load_token")
    def test_auto_refreshes_expired_token(self, mock_load, mock_creds, mock_refresh):
        expired = _make_token(expires_at="2020-01-01T00:00:00+00:00")
        mock_load.return_value = expired
        refreshed = _make_token(access_token="refreshed")
        mock_refresh.return_value = refreshed

        result = _require_token()
        assert result.access_token == "refreshed"

    @patch("linkedin_mcp.server.auth.auto_refresh")
    @patch("linkedin_mcp.server._get_credentials", return_value=("id", "secret"))
    @patch("linkedin_mcp.server.auth.load_token")
    def test_raises_when_refresh_fails(self, mock_load, mock_creds, mock_refresh):
        expired = _make_token(expires_at="2020-01-01T00:00:00+00:00")
        mock_load.return_value = expired
        mock_refresh.return_value = None

        with pytest.raises(RuntimeError, match="expired"):
            _require_token()


class TestHandleLogin:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.login")
    @patch("linkedin_mcp.server._get_credentials", return_value=("id", "secret"))
    async def test_successful_login(self, mock_creds, mock_login):
        mock_login.return_value = _make_token()
        result = await _handle_login()
        assert "Successfully logged in" in result.content[0].text
        assert "member1" in result.content[0].text


class TestHandleLogout:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.clear_token")
    async def test_logout_clears(self, mock_clear):
        mock_clear.return_value = True
        result = await _handle_logout()
        assert "Logged out" in result.content[0].text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.clear_token")
    async def test_logout_no_tokens(self, mock_clear):
        mock_clear.return_value = False
        result = await _handle_logout()
        assert "No stored tokens" in result.content[0].text


class TestHandleStatus:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_not_logged_in(self, mock_load):
        mock_load.return_value = None
        result = await _handle_status()
        assert "Not logged in" in result.content[0].text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_active_token(self, mock_load):
        mock_load.return_value = _make_token()
        result = await _handle_status()
        text = result.content[0].text
        assert "Active" in text
        assert "member1" in text
        assert "Days remaining" in text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_expired_token_with_refresh(self, mock_load):
        mock_load.return_value = _make_token(
            expires_at="2020-01-01T00:00:00+00:00",
            refresh_token="has_one",
        )
        result = await _handle_status()
        text = result.content[0].text
        assert "EXPIRED" in text
        assert "Auto-refresh" in text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_expired_token_without_refresh(self, mock_load):
        mock_load.return_value = _make_token(
            expires_at="2020-01-01T00:00:00+00:00",
        )
        result = await _handle_status()
        text = result.content[0].text
        assert "EXPIRED" in text
        assert "re-authenticate" in text


class TestHandleProfile:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.api.get_profile")
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_returns_profile(self, mock_load, mock_profile):
        mock_load.return_value = _make_token()
        mock_profile.return_value = Profile(name="Test User", email="test@example.com")
        result = await _handle_profile()
        assert "Test User" in result.content[0].text


class TestHandleTextPost:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_preview_mode(self, mock_load):
        mock_load.return_value = _make_token()
        result = await _handle_text_post({"text": "Hello LinkedIn"})
        text = result.content[0].text
        assert "PREVIEW" in text
        assert "Hello LinkedIn" in text
        assert "not yet published" in text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.api.create_text_post")
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_confirm_publishes(self, mock_load, mock_create):
        mock_load.return_value = _make_token()
        mock_create.return_value = PostResult(
            urn="urn:li:share:1", status="created", message="Post published: urn:li:share:1"
        )
        result = await _handle_text_post({"text": "Hello", "confirm": True})
        assert "published" in result.content[0].text.lower()

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_preview_includes_stamp(self, mock_load):
        mock_load.return_value = _make_token()
        result = await _handle_text_post({"text": "Post text"})
        text = result.content[0].text
        assert "AI-drafted" in text


class TestHandleArticlePost:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_preview_includes_url(self, mock_load):
        mock_load.return_value = _make_token()
        result = await _handle_article_post({
            "text": "Check this out",
            "url": "https://example.com/article",
        })
        text = result.content[0].text
        assert "PREVIEW" in text
        assert "https://example.com/article" in text


class TestHandleDeletePost:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_preview_warns_irreversible(self, mock_load):
        mock_load.return_value = _make_token()
        result = await _handle_delete_post({"post_urn": "urn:li:share:999"})
        text = result.content[0].text
        assert "PREVIEW" in text
        assert "cannot be undone" in text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.api.delete_post")
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_confirm_deletes(self, mock_load, mock_delete):
        mock_load.return_value = _make_token()
        mock_delete.return_value = PostResult(
            urn="urn:li:share:999", status="deleted", message="Post deleted"
        )
        result = await _handle_delete_post({"post_urn": "urn:li:share:999", "confirm": True})
        assert "deleted" in result.content[0].text.lower()


class TestHandleHealth:
    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.audit._get_log_path")
    @patch("linkedin_mcp.server.httpx.get")
    @patch("linkedin_mcp.server._get_credentials", return_value=("id", "secret"))
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_healthy_system(self, mock_load, mock_creds, mock_get, mock_audit_path, tmp_path):
        mock_load.return_value = _make_token()
        mock_get.return_value = MagicMock(status_code=200)
        audit_path = tmp_path / "audit.log"
        audit_path.write_text('{"line": 1}\n{"line": 2}\n', encoding="utf-8")
        mock_audit_path.return_value = audit_path

        result = await _handle_health()
        text = result.content[0].text
        assert "[OK]" in text
        assert "Token: Valid" in text
        assert "API" in text
        assert "2 entries" in text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_no_token(self, mock_load):
        mock_load.return_value = None
        result = await _handle_health()
        assert "[FAIL]" in result.content[0].text
        assert "No stored token" in result.content[0].text

    @pytest.mark.asyncio
    @patch("linkedin_mcp.server.audit._get_log_path")
    @patch("linkedin_mcp.server._get_credentials", return_value=("id", "secret"))
    @patch("linkedin_mcp.server.auth.load_token")
    async def test_expired_with_refresh(self, mock_load, mock_creds, mock_audit_path, tmp_path):
        mock_load.return_value = _make_token(
            expires_at="2020-01-01T00:00:00+00:00",
            refresh_token="has_one",
        )
        mock_audit_path.return_value = tmp_path / "audit.log"

        result = await _handle_health()
        text = result.content[0].text
        assert "[WARN]" in text
        assert "Refresh token available" in text
        assert "[SKIP]" in text
