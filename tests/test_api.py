"""Tests for linkedin_mcp.api — LinkedIn API client, approval stamp, post building."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linkedin_mcp import api
from linkedin_mcp.models import PostResult


class TestApprovalStamp:
    def test_default_stamp(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LINKEDIN_MCP_APPROVAL_STAMP", None)
            stamp = api._get_approval_stamp()
            assert "AI-drafted" in stamp
            assert "Human-approved" in stamp

    def test_custom_stamp(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_APPROVAL_STAMP": "Custom stamp"}):
            assert api._get_approval_stamp() == "Custom stamp"

    def test_empty_stamp_disables(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_APPROVAL_STAMP": ""}):
            assert api._get_approval_stamp() == ""

    def test_stamp_text_appends(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_APPROVAL_STAMP": " [approved]"}):
            assert api._stamp_text("Hello") == "Hello [approved]"

    def test_stamp_text_noop_when_empty(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_APPROVAL_STAMP": ""}):
            assert api._stamp_text("Hello") == "Hello"


class TestBuildUgcPost:
    def test_text_post_structure(self):
        post = api._build_ugc_post("person123", "Hello LinkedIn", "PUBLIC")
        assert post["author"] == "urn:li:person:person123"
        assert post["lifecycleState"] == "PUBLISHED"
        content = post["specificContent"]["com.linkedin.ugc.ShareContent"]
        assert content["shareCommentary"]["text"] == "Hello LinkedIn"
        assert content["shareMediaCategory"] == "NONE"
        assert post["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"] == "PUBLIC"

    def test_connections_visibility(self):
        post = api._build_ugc_post("p1", "text", "CONNECTIONS")
        assert post["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"] == "CONNECTIONS"

    def test_with_media(self):
        media = [{"status": "READY", "originalUrl": "https://example.com"}]
        post = api._build_ugc_post("p1", "text", "PUBLIC", "ARTICLE", media)
        content = post["specificContent"]["com.linkedin.ugc.ShareContent"]
        assert content["shareMediaCategory"] == "ARTICLE"
        assert content["media"] == media

    def test_no_media_key_when_none(self):
        post = api._build_ugc_post("p1", "text")
        content = post["specificContent"]["com.linkedin.ugc.ShareContent"]
        assert "media" not in content


class TestGetProfile:
    @patch("linkedin_mcp.api.httpx.get")
    def test_returns_profile(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "abc",
                "name": "Test User",
                "given_name": "Test",
                "family_name": "User",
                "email": "test@example.com",
                "email_verified": True,
                "picture": "https://pic.url",
                "locale": "en_GB",
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        profile = api.get_profile("token")
        assert profile.name == "Test User"
        assert profile.email == "test@example.com"
        assert profile.sub == "abc"


class TestCreateTextPost:
    @patch("linkedin_mcp.api._stamp_text", return_value="Hello stamped")
    @patch("linkedin_mcp.api.httpx.post")
    def test_creates_post(self, mock_post, mock_stamp):
        mock_post.return_value = MagicMock(
            status_code=201,
            headers={"X-RestLi-Id": "urn:li:share:999"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        result = api.create_text_post("token", "person1", "Hello", "PUBLIC")
        assert result.urn == "urn:li:share:999"
        assert result.status == "created"

        body = mock_post.call_args[1]["json"]
        assert body["author"] == "urn:li:person:person1"
        text = body["specificContent"]["com.linkedin.ugc.ShareContent"]["shareCommentary"]["text"]
        assert text == "Hello stamped"


class TestCreateArticlePost:
    @patch("linkedin_mcp.api._stamp_text", return_value="Commentary stamped")
    @patch("linkedin_mcp.api.httpx.post")
    def test_creates_article_post(self, mock_post, mock_stamp):
        mock_post.return_value = MagicMock(
            status_code=201,
            headers={"X-RestLi-Id": "urn:li:share:888"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        result = api.create_article_post(
            "token", "p1", "Commentary", "https://example.com",
            title="Title", description="Desc"
        )
        assert result.urn == "urn:li:share:888"

        body = mock_post.call_args[1]["json"]
        media = body["specificContent"]["com.linkedin.ugc.ShareContent"]["media"]
        assert len(media) == 1
        assert media[0]["originalUrl"] == "https://example.com"
        assert media[0]["title"]["text"] == "Title"


class TestDeletePost:
    @patch("linkedin_mcp.api.httpx.delete")
    def test_deletes_post(self, mock_delete):
        mock_delete.return_value = MagicMock(status_code=204)
        mock_delete.return_value.raise_for_status = MagicMock()

        result = api.delete_post("token", "urn:li:share:123")
        assert result.status == "deleted"
        assert "123" in result.urn

    @patch("linkedin_mcp.api.httpx.delete")
    def test_url_encodes_urn(self, mock_delete):
        mock_delete.return_value = MagicMock(status_code=204)
        mock_delete.return_value.raise_for_status = MagicMock()

        api.delete_post("token", "urn:li:share:123")
        url = mock_delete.call_args[0][0]
        assert "%3A" in url


class TestHeaders:
    def test_includes_bearer_and_restli(self):
        h = api._headers("my_token")
        assert h["Authorization"] == "Bearer my_token"
        assert h["X-Restli-Protocol-Version"] == "2.0.0"
