"""Tests for linkedin_mcp.history — post history storage."""

import json
import os
from unittest.mock import patch

import pytest

from linkedin_mcp import history


class TestGetHistoryPath:
    def test_default_path(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LINKEDIN_MCP_HISTORY_PATH", None)
            path = history._get_history_path()
            assert path.name == "history.json"
            assert ".linkedin-mcp" in str(path)

    def test_custom_path(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_HISTORY_PATH": "/tmp/h.json"}):
            path = history._get_history_path()
            assert path.name == "h.json"


class TestRecordPost:
    @patch("linkedin_mcp.history._get_history_path")
    def test_creates_file_and_records(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        history.record_post("urn:li:share:1", "text", "Hello", "PUBLIC")

        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["urn"] == "urn:li:share:1"
        assert data[0]["type"] == "text"
        assert data[0]["content"] == "Hello"
        assert data[0]["visibility"] == "PUBLIC"
        assert "timestamp" in data[0]

    @patch("linkedin_mcp.history._get_history_path")
    def test_appends_to_existing(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        history.record_post("urn:1", "text", "First")
        history.record_post("urn:2", "article", "Second", url="https://example.com")

        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[1]["url"] == "https://example.com"

    @patch("linkedin_mcp.history._get_history_path")
    def test_records_image_path(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        history.record_post("urn:1", "image", "Photo", image_path="/pic.jpg")

        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert data[0]["image_path"] == "/pic.jpg"

    @patch("linkedin_mcp.history._get_history_path")
    def test_truncates_long_content(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        history.record_post("urn:1", "text", "x" * 1000)

        data = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
        assert len(data[0]["content"]) == 500

    @patch("linkedin_mcp.history._get_history_path")
    def test_creates_parent_dirs(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "deep" / "history.json"
        history.record_post("urn:1", "text", "Hello")
        assert (tmp_path / "deep" / "history.json").exists()


class TestGetHistory:
    @patch("linkedin_mcp.history._get_history_path")
    def test_empty_when_no_file(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "nope.json"
        assert history.get_history() == []

    @patch("linkedin_mcp.history._get_history_path")
    def test_returns_all_entries(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        for i in range(5):
            history.record_post(f"urn:{i}", "text", f"Post {i}")

        result = history.get_history()
        assert len(result) == 5

    @patch("linkedin_mcp.history._get_history_path")
    def test_respects_limit(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        for i in range(10):
            history.record_post(f"urn:{i}", "text", f"Post {i}")

        result = history.get_history(limit=3)
        assert len(result) == 3
        assert result[0]["urn"] == "urn:7"

    @patch("linkedin_mcp.history._get_history_path")
    def test_filters_by_type(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        history.record_post("urn:1", "text", "Text post")
        history.record_post("urn:2", "article", "Article post")
        history.record_post("urn:3", "text", "Another text")

        result = history.get_history(post_type="article")
        assert len(result) == 1
        assert result[0]["type"] == "article"

    @patch("linkedin_mcp.history._get_history_path")
    def test_handles_corrupt_file(self, mock_path, tmp_path):
        path = tmp_path / "history.json"
        path.write_text("not valid json", encoding="utf-8")
        mock_path.return_value = path

        assert history.get_history() == []


class TestDeleteFromHistory:
    @patch("linkedin_mcp.history._get_history_path")
    def test_removes_matching_urn(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        history.record_post("urn:1", "text", "First")
        history.record_post("urn:2", "text", "Second")

        assert history.delete_from_history("urn:1") is True

        result = history.get_history()
        assert len(result) == 1
        assert result[0]["urn"] == "urn:2"

    @patch("linkedin_mcp.history._get_history_path")
    def test_returns_false_when_not_found(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "history.json"
        history.record_post("urn:1", "text", "Post")

        assert history.delete_from_history("urn:999") is False

    @patch("linkedin_mcp.history._get_history_path")
    def test_returns_false_when_no_file(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "nope.json"
        assert history.delete_from_history("urn:1") is False
