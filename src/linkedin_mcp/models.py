from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TokenData:
    access_token: str
    expires_in: int
    scope: str
    sub: str = ""
    refresh_token: str = ""
    refresh_token_expires_in: int = 0

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> TokenData | None:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


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
