from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _get_history_path() -> Path:
    custom = os.environ.get("LINKEDIN_MCP_HISTORY_PATH")
    if custom:
        return Path(custom)
    return Path.home() / ".linkedin-mcp" / "history.json"


def _load_history() -> list[dict[str, str]]:
    path = _get_history_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (json.JSONDecodeError, ValueError):
        return []


def _save_history(entries: list[dict[str, str]]) -> None:
    path = _get_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def record_post(
    urn: str,
    post_type: str,
    content_summary: str,
    visibility: str = "PUBLIC",
    url: str = "",
    image_path: str = "",
) -> None:
    entries = _load_history()
    entry: dict[str, str] = {
        "urn": urn,
        "type": post_type,
        "content": content_summary[:500],
        "visibility": visibility,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if url:
        entry["url"] = url
    if image_path:
        entry["image_path"] = image_path
    entries.append(entry)
    _save_history(entries)


def get_history(limit: int = 20, post_type: str = "") -> list[dict[str, str]]:
    entries = _load_history()
    if post_type:
        entries = [e for e in entries if e.get("type") == post_type]
    return entries[-limit:]


def delete_from_history(urn: str) -> bool:
    entries = _load_history()
    filtered = [e for e in entries if e.get("urn") != urn]
    if len(filtered) == len(entries):
        return False
    _save_history(filtered)
    return True
