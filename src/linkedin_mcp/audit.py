from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _get_log_path() -> Path:
    custom = os.environ.get("LINKEDIN_MCP_AUDIT_PATH")
    if custom:
        return Path(custom)
    return Path.home() / ".linkedin-mcp" / "audit.log"


def log(action: str, tool: str, content_summary: str, result: str = "") -> None:
    """Append an audit entry to the log file.

    Each line is a self-contained JSON object for easy parsing.
    """
    path = _get_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "tool": tool,
        "content_summary": content_summary[:500],
    }
    if result:
        entry["result"] = result

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
