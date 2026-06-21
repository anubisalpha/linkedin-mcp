"""Tests for linkedin_mcp.models — TokenData, Profile, PostResult."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from linkedin_mcp.models import PostResult, Profile, TokenData, _decrypt, _encrypt


class TestEncryption:
    def test_round_trip(self):
        plaintext = "secret token data"
        encrypted = _encrypt(plaintext)
        assert encrypted != plaintext
        assert _decrypt(encrypted) == plaintext

    def test_different_inputs_produce_different_ciphertext(self):
        a = _encrypt("token_a")
        b = _encrypt("token_b")
        assert a != b


class TestTokenData:
    def _make_token(self, **overrides) -> TokenData:
        defaults = {
            "access_token": "test_access_token",
            "expires_in": 5184000,
            "scope": "openid profile email w_member_social",
            "sub": "abc123",
            "refresh_token": "",
            "refresh_token_expires_in": 0,
        }
        defaults.update(overrides)
        return TokenData(**defaults)

    def test_save_and_load(self, tmp_path: Path):
        token = self._make_token()
        path = tmp_path / "tokens.json"
        token.save(path)
        assert path.exists()

        loaded = TokenData.load(path)
        assert loaded is not None
        assert loaded.access_token == "test_access_token"
        assert loaded.sub == "abc123"
        assert loaded.scope == "openid profile email w_member_social"

    def test_saved_file_is_encrypted(self, tmp_path: Path):
        token = self._make_token()
        path = tmp_path / "tokens.json"
        token.save(path)

        raw = path.read_text(encoding="utf-8")
        assert "test_access_token" not in raw
        assert not raw.startswith("{")

    def test_load_nonexistent_returns_none(self, tmp_path: Path):
        assert TokenData.load(tmp_path / "nope.json") is None

    def test_load_corrupt_file_returns_none(self, tmp_path: Path):
        path = tmp_path / "tokens.json"
        path.write_text("not valid data at all", encoding="utf-8")
        assert TokenData.load(path) is None

    def test_load_plain_json_backward_compat(self, tmp_path: Path):
        path = tmp_path / "tokens.json"
        data = {
            "access_token": "plain_token",
            "expires_in": 3600,
            "scope": "openid",
            "sub": "xyz",
            "refresh_token": "",
            "refresh_token_expires_in": 0,
            "created_at": "",
            "expires_at": "",
        }
        path.write_text(json.dumps(data), encoding="utf-8")

        loaded = TokenData.load(path)
        assert loaded is not None
        assert loaded.access_token == "plain_token"

    def test_save_sets_created_at_and_expires_at(self, tmp_path: Path):
        token = self._make_token()
        path = tmp_path / "tokens.json"
        token.save(path)

        loaded = TokenData.load(path)
        assert loaded.created_at != ""
        assert loaded.expires_at != ""

    def test_is_expired_false_when_fresh(self, tmp_path: Path):
        token = self._make_token(expires_in=86400)
        path = tmp_path / "tokens.json"
        token.save(path)
        loaded = TokenData.load(path)
        assert not loaded.is_expired()

    def test_is_expired_true_when_past(self):
        token = self._make_token()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        token.expires_at = past.isoformat()
        assert token.is_expired()

    def test_is_expired_false_when_no_expires_at(self):
        token = self._make_token()
        token.expires_at = ""
        assert not token.is_expired()

    def test_days_remaining(self):
        token = self._make_token()
        future = datetime.now(timezone.utc) + timedelta(days=30)
        token.expires_at = future.isoformat()
        assert token.days_remaining() == 30

    def test_days_remaining_zero_when_expired(self):
        token = self._make_token()
        past = datetime.now(timezone.utc) - timedelta(days=5)
        token.expires_at = past.isoformat()
        assert token.days_remaining() == 0

    def test_days_remaining_fallback_no_expires_at(self):
        token = self._make_token(expires_in=172800)
        token.expires_at = ""
        assert token.days_remaining() == 2

    def test_age_description_just_now(self):
        token = self._make_token()
        token.created_at = datetime.now(timezone.utc).isoformat()
        assert token.age_description() == "just now"

    def test_age_description_hours(self):
        token = self._make_token()
        token.created_at = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        assert "3 hours ago" in token.age_description()

    def test_age_description_days(self):
        token = self._make_token()
        token.created_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        assert "10 days ago" in token.age_description()

    def test_age_description_unknown(self):
        token = self._make_token()
        token.created_at = ""
        assert token.age_description() == "unknown"

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "deep" / "nested" / "tokens.json"
        token = self._make_token()
        token.save(path)
        assert path.exists()


class TestProfile:
    def test_summary_full(self):
        p = Profile(
            name="Test User",
            email="test@example.com",
            locale="en_GB",
            picture="https://example.com/pic.jpg",
        )
        s = p.summary()
        assert "Test User" in s
        assert "test@example.com" in s
        assert "en_GB" in s
        assert "pic.jpg" in s

    def test_summary_minimal(self):
        p = Profile(name="Test User")
        s = p.summary()
        assert "Test User" in s
        assert "Email" not in s


class TestPostResult:
    def test_fields(self):
        r = PostResult(urn="urn:li:share:123", status="created", message="Done")
        assert r.urn == "urn:li:share:123"
        assert r.status == "created"
        assert r.message == "Done"
