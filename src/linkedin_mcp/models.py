from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _derive_key() -> bytes:
    custom = os.environ.get("LINKEDIN_MCP_ENCRYPTION_KEY")
    if custom:
        key_bytes = hashlib.sha256(custom.encode()).digest()
        return base64.urlsafe_b64encode(key_bytes)
    machine_id = f"{platform.node()}-{platform.machine()}-linkedin-mcp"
    key_bytes = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def _encrypt(data: str) -> str:
    f = Fernet(_derive_key())
    return f.encrypt(data.encode()).decode()


def _decrypt(data: str) -> str:
    f = Fernet(_derive_key())
    return f.decrypt(data.encode()).decode()


@dataclass
class TokenData:
    access_token: str
    expires_in: int
    scope: str
    sub: str = ""
    refresh_token: str = ""
    refresh_token_expires_in: int = 0
    created_at: str = ""
    expires_at: str = ""

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.expires_at:
            from datetime import timedelta
            expiry = datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)
            self.expires_at = expiry.isoformat()
        plaintext = json.dumps(asdict(self), indent=2)
        encrypted = _encrypt(plaintext)
        path.write_text(encrypted, encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> TokenData | None:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        try:
            decrypted = _decrypt(raw)
            data = json.loads(decrypted)
        except (InvalidToken, Exception):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return None
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        expiry = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) >= expiry

    def days_remaining(self) -> int:
        if not self.expires_at:
            return self.expires_in // 86400
        expiry = datetime.fromisoformat(self.expires_at)
        delta = expiry - datetime.now(timezone.utc)
        return max(0, delta.days)

    def age_description(self) -> str:
        if not self.created_at:
            return "unknown"
        created = datetime.fromisoformat(self.created_at)
        delta = datetime.now(timezone.utc) - created
        if delta.days > 0:
            return f"{delta.days} days ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hours ago"
        return "just now"


@dataclass
class Profile:
    sub: str = ""
    name: str = ""
    given_name: str = ""
    family_name: str = ""
    picture: str = ""
    locale: str = ""
    email: str = ""
    email_verified: bool = False

    def summary(self) -> str:
        lines = [
            f"Name: {self.name}",
            f"Email: {self.email}" if self.email else None,
            f"Locale: {self.locale}" if self.locale else None,
            f"Picture: {self.picture}" if self.picture else None,
        ]
        return "\n".join(line for line in lines if line)


@dataclass
class PostResult:
    urn: str
    status: str
    message: str = ""
