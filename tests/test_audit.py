"""Tests for linkedin_mcp.audit — NDJSON audit logging."""

import json
import os
from unittest.mock import patch

import pytest

from linkedin_mcp import audit


class TestAuditLog:
    @patch("linkedin_mcp.audit._get_log_path")
    def test_log_creates_file_and_writes_entry(self, mock_path, tmp_path):
        log_path = tmp_path / "audit.log"
        mock_path.return_value = log_path

        audit.log("preview", "linkedin_create_text_post", "Hello world")

        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["action"] == "preview"
        assert entry["tool"] == "linkedin_create_text_post"
        assert entry["content_summary"] == "Hello world"
        assert "timestamp" in entry
        assert "result" not in entry

    @patch("linkedin_mcp.audit._get_log_path")
    def test_log_with_result(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "audit.log"
        audit.log("published", "linkedin_create_text_post", "Post text", "urn:li:share:123")

        lines = (tmp_path / "audit.log").read_text(encoding="utf-8").strip().splitlines()
        entry = json.loads(lines[0])
        assert entry["result"] == "urn:li:share:123"

    @patch("linkedin_mcp.audit._get_log_path")
    def test_log_appends_multiple_entries(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "audit.log"

        audit.log("preview", "tool1", "first")
        audit.log("publish", "tool2", "second")
        audit.log("published", "tool2", "second", "urn:123")

        lines = (tmp_path / "audit.log").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

    @patch("linkedin_mcp.audit._get_log_path")
    def test_log_truncates_long_content(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "audit.log"
        long_text = "x" * 1000
        audit.log("preview", "tool", long_text)

        lines = (tmp_path / "audit.log").read_text(encoding="utf-8").strip().splitlines()
        entry = json.loads(lines[0])
        assert len(entry["content_summary"]) == 500

    @patch("linkedin_mcp.audit._get_log_path")
    def test_log_creates_parent_dirs(self, mock_path, tmp_path):
        mock_path.return_value = tmp_path / "deep" / "nested" / "audit.log"
        audit.log("test", "tool", "content")
        assert (tmp_path / "deep" / "nested" / "audit.log").exists()


class TestGetLogPath:
    def test_default_path(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LINKEDIN_MCP_AUDIT_PATH", None)
            path = audit._get_log_path()
            assert path.name == "audit.log"
            assert ".linkedin-mcp" in str(path)

    def test_custom_path(self):
        with patch.dict(os.environ, {"LINKEDIN_MCP_AUDIT_PATH": "/tmp/my_audit.log"}):
            path = audit._get_log_path()
            assert path.name == "my_audit.log"
