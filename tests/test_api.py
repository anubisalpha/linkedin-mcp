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


class TestRegisterImageUpload:
    @patch("linkedin_mcp.api.httpx.post")
    def test_returns_upload_url_and_asset(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "value": {
                    "uploadMechanism": {
                        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest": {
                            "uploadUrl": "https://upload.example.com/upload"
                        }
                    },
                    "asset": "urn:li:digitalmediaAsset:abc123",
                }
            },
        )
        mock_post.return_value.raise_for_status = MagicMock()

        upload_url, asset_urn = api._register_image_upload("token", "person1")
        assert upload_url == "https://upload.example.com/upload"
        assert asset_urn == "urn:li:digitalmediaAsset:abc123"


class TestUploadImageBinary:
    @patch("linkedin_mcp.api.httpx.put")
    def test_uploads_file_bytes(self, mock_put, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        mock_put.return_value = MagicMock(status_code=201)
        mock_put.return_value.raise_for_status = MagicMock()

        api._upload_image_binary("token", "https://upload.example.com", str(img))
        mock_put.assert_called_once()
        assert mock_put.call_args[1]["content"] == img.read_bytes()


class TestCreateImagePost:
    @patch("linkedin_mcp.api.httpx.post")
    @patch("linkedin_mcp.api._upload_image_binary")
    @patch("linkedin_mcp.api._register_image_upload")
    def test_full_image_post_flow(self, mock_register, mock_upload, mock_post):
        mock_register.return_value = ("https://upload.example.com", "urn:li:digitalmediaAsset:x")
        mock_post.return_value = MagicMock(
            status_code=201,
            headers={"X-RestLi-Id": "urn:li:share:img1"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        result = api.create_image_post("token", "p1", "Photo!", "/pic.jpg")
        assert result.urn == "urn:li:share:img1"
        assert result.status == "created"
        mock_register.assert_called_once_with("token", "p1")
        mock_upload.assert_called_once_with("token", "https://upload.example.com", "/pic.jpg")

    @patch("linkedin_mcp.api.httpx.post")
    @patch("linkedin_mcp.api._upload_image_binary")
    @patch("linkedin_mcp.api._register_image_upload")
    def test_image_post_with_title_and_description(self, mock_register, mock_upload, mock_post):
        mock_register.return_value = ("https://upload.example.com", "urn:li:digitalmediaAsset:x")
        mock_post.return_value = MagicMock(
            status_code=201,
            headers={"X-RestLi-Id": "urn:li:share:img2"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        result = api.create_image_post(
            "token", "p1", "Photo!", "/pic.jpg",
            title="My Title", description="My Desc",
        )
        assert result.urn == "urn:li:share:img2"
        body = mock_post.call_args[1]["json"]
        media = body["specificContent"]["com.linkedin.ugc.ShareContent"]["media"]
        assert media[0]["title"]["text"] == "My Title"
        assert media[0]["description"]["text"] == "My Desc"


class TestLinkPreview:
    def test_summary_with_all_fields(self):
        preview = api.LinkPreview(
            url="https://example.com",
            title="Example Title",
            description="A great page",
            image="https://example.com/img.jpg",
            site_name="Example.com",
        )
        text = preview.summary()
        assert "Example Title" in text
        assert "A great page" in text
        assert "img.jpg" in text
        assert "Example.com" in text

    def test_summary_no_og_data(self):
        preview = api.LinkPreview(url="https://example.com")
        text = preview.summary()
        assert "No Open Graph metadata" in text

    @patch("linkedin_mcp.api.httpx.get")
    def test_fetch_parses_og_tags(self, mock_get):
        html = """
        <html><head>
        <meta property="og:title" content="Test Page">
        <meta property="og:description" content="A test description">
        <meta property="og:image" content="https://img.example.com/pic.jpg">
        <meta property="og:site_name" content="TestSite">
        </head></html>
        """
        mock_get.return_value = MagicMock(status_code=200, text=html)
        mock_get.return_value.raise_for_status = MagicMock()

        preview = api.fetch_link_preview("https://example.com")
        assert preview.title == "Test Page"
        assert preview.description == "A test description"
        assert preview.image == "https://img.example.com/pic.jpg"
        assert preview.site_name == "TestSite"

    @patch("linkedin_mcp.api.httpx.get")
    def test_fetch_handles_reversed_meta_attr_order(self, mock_get):
        html = '<html><head><meta content="Reversed Title" property="og:title"></head></html>'
        mock_get.return_value = MagicMock(status_code=200, text=html)
        mock_get.return_value.raise_for_status = MagicMock()

        preview = api.fetch_link_preview("https://example.com")
        assert preview.title == "Reversed Title"

    @patch("linkedin_mcp.api.httpx.get")
    def test_fetch_handles_no_og_tags(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text="<html><body>Plain page</body></html>")
        mock_get.return_value.raise_for_status = MagicMock()

        preview = api.fetch_link_preview("https://example.com")
        assert preview.title == ""
        assert preview.description == ""

    @patch("linkedin_mcp.api.httpx.get")
    def test_fetch_handles_http_error(self, mock_get):
        mock_get.side_effect = api.httpx.HTTPError("Connection refused")
        preview = api.fetch_link_preview("https://broken.example.com")
        assert "Could not fetch" in preview.description


class TestHeaders:
    def test_includes_bearer_and_restli(self):
        h = api._headers("my_token")
        assert h["Authorization"] == "Bearer my_token"
        assert h["X-Restli-Protocol-Version"] == "2.0.0"
