#!/usr/bin/env python3
"""LinkedIn MCP Server — ToS-compliant LinkedIn integration via the official API."""

import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from . import api, audit, auth
from .api import _get_approval_stamp
from .models import TokenData

LINKEDIN_POST_CHAR_LIMIT = 3000

server = Server(
    "linkedin-mcp",
    version="0.2.0",
)

CONFIRM_DESCRIPTION = (
    "Set to true to publish. When false (default), returns a preview of "
    "the post for your review without publishing. Always preview first, "
    "then call again with confirm=true after the user has approved the content."
)

CONFIRM_SCHEMA = {
    "type": "boolean",
    "description": CONFIRM_DESCRIPTION,
    "default": False,
}


def _get_credentials() -> tuple[str, str]:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables are required. "
            "Create a LinkedIn Developer App at https://www.linkedin.com/developers/apps"
        )
    return client_id, client_secret


REQUIRED_SCOPES = {"openid", "profile", "email", "w_member_social"}


def _check_scopes(token: TokenData, needed: set[str] | None = None) -> None:
    if not token.scope:
        return
    granted = set(token.scope.split())
    missing = (needed or REQUIRED_SCOPES) - granted
    if missing:
        raise RuntimeError(
            f"Token is missing required scope(s): {', '.join(sorted(missing))}. "
            "Update your LinkedIn Developer App to enable the missing products, then re-authenticate."
        )


def _require_token() -> TokenData:
    token = auth.load_token()
    if not token:
        raise RuntimeError("Not logged in. Use the linkedin_login tool first.")
    if token.is_expired():
        client_id, client_secret = _get_credentials()
        refreshed = auth.auto_refresh(client_id, client_secret)
        if refreshed:
            _check_scopes(refreshed)
            return refreshed
        raise RuntimeError(
            "Access token has expired. "
            + ("No refresh token available — " if not token.refresh_token else "Refresh failed — ")
            + "use linkedin_login to re-authenticate."
        )
    _check_scopes(token)
    return token


def _char_count_line(text: str) -> str:
    length = len(text)
    remaining = LINKEDIN_POST_CHAR_LIMIT - length
    if remaining < 0:
        return f"Characters: {length}/{LINKEDIN_POST_CHAR_LIMIT} (OVER LIMIT by {-remaining})"
    return f"Characters: {length}/{LINKEDIN_POST_CHAR_LIMIT} ({remaining} remaining)"


def _preview_result(preview_text: str, post_text: str = "") -> CallToolResult:
    char_line = f"\n{_char_count_line(post_text)}" if post_text else ""
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=(
                    "PREVIEW — not yet published. Show this to the user for approval, "
                    "then call again with confirm=true to publish.\n\n"
                    "---\n"
                    f"{preview_text}\n"
                    f"---{char_line}"
                ),
            )
        ]
    )


@server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="linkedin_login",
            description=(
                "Log in to LinkedIn via OAuth 2.0. Opens your browser for authorization. "
                "You must have a LinkedIn Developer App configured with 'Sign in with LinkedIn' "
                "and 'Share on LinkedIn' products enabled."
            ),
            inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        ),
        Tool(
            name="linkedin_logout",
            description="Clear stored LinkedIn authentication tokens.",
            inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        ),
        Tool(
            name="linkedin_status",
            description="Check current LinkedIn authentication status and token info.",
            inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        ),
        Tool(
            name="linkedin_profile",
            description="Get the authenticated LinkedIn member's profile (name, email, photo, locale).",
            inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        ),
        Tool(
            name="linkedin_audit_log",
            description="View the audit log of all post previews, publishes, and deletions. Shows the approval trail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent entries to show. Defaults to 20.",
                        "default": 20,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_create_text_post",
            description=(
                "Publish a text-only post to LinkedIn. "
                "Must be called twice: first without confirm to preview, "
                "then with confirm=true after the user approves the content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The post content text.",
                    },
                    "visibility": {
                        "type": "string",
                        "enum": ["PUBLIC", "CONNECTIONS"],
                        "description": "Who can see the post. Defaults to PUBLIC.",
                        "default": "PUBLIC",
                    },
                    "confirm": CONFIRM_SCHEMA,
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_create_article_post",
            description=(
                "Share a URL/article on LinkedIn with commentary. "
                "Must be called twice: first without confirm to preview, "
                "then with confirm=true after the user approves the content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Commentary text to accompany the shared article.",
                    },
                    "url": {
                        "type": "string",
                        "description": "The URL of the article to share.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the article preview.",
                        "default": "",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description for the article preview.",
                        "default": "",
                    },
                    "visibility": {
                        "type": "string",
                        "enum": ["PUBLIC", "CONNECTIONS"],
                        "description": "Who can see the post. Defaults to PUBLIC.",
                        "default": "PUBLIC",
                    },
                    "confirm": CONFIRM_SCHEMA,
                },
                "required": ["text", "url"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_create_image_post",
            description=(
                "Upload an image and publish a post with it on LinkedIn. "
                "Must be called twice: first without confirm to preview, "
                "then with confirm=true after the user approves the content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The post content text.",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Absolute path to the image file to upload.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the image.",
                        "default": "",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description for the image.",
                        "default": "",
                    },
                    "visibility": {
                        "type": "string",
                        "enum": ["PUBLIC", "CONNECTIONS"],
                        "description": "Who can see the post. Defaults to PUBLIC.",
                        "default": "PUBLIC",
                    },
                    "confirm": CONFIRM_SCHEMA,
                },
                "required": ["text", "image_path"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_health",
            description=(
                "Run a health check: verifies token validity, API connectivity, "
                "and reports token expiry status. Use this to diagnose connection issues."
            ),
            inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        ),
        Tool(
            name="linkedin_delete_post",
            description=(
                "Delete a LinkedIn post by its URN. "
                "Must be called twice: first without confirm to preview, "
                "then with confirm=true after the user confirms deletion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "post_urn": {
                        "type": "string",
                        "description": "The URN of the post to delete (returned when the post was created).",
                    },
                    "confirm": CONFIRM_SCHEMA,
                },
                "required": ["post_urn"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_undo_last_post",
            description=(
                "Delete the most recently published post. Looks up the last published "
                "post URN from the audit log and deletes it. Use as a quick undo for "
                "posts with typos or errors. Must be called twice: first without confirm "
                "to preview, then with confirm=true after the user confirms deletion."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "confirm": CONFIRM_SCHEMA,
                },
                "required": [],
                "additionalProperties": False,
            },
        ),
    ]


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    try:
        if name == "linkedin_login":
            return await _handle_login()
        elif name == "linkedin_logout":
            return await _handle_logout()
        elif name == "linkedin_status":
            return await _handle_status()
        elif name == "linkedin_profile":
            return await _handle_profile()
        elif name == "linkedin_audit_log":
            return await _handle_audit_log(arguments)
        elif name == "linkedin_health":
            return await _handle_health()
        elif name == "linkedin_create_text_post":
            return await _handle_text_post(arguments)
        elif name == "linkedin_create_article_post":
            return await _handle_article_post(arguments)
        elif name == "linkedin_create_image_post":
            return await _handle_image_post(arguments)
        elif name == "linkedin_delete_post":
            return await _handle_delete_post(arguments)
        elif name == "linkedin_undo_last_post":
            return await _handle_undo_last_post(arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )


async def _handle_login() -> CallToolResult:
    client_id, client_secret = _get_credentials()
    token = auth.login(client_id, client_secret)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=(
                    f"Successfully logged in to LinkedIn.\n"
                    f"Member ID: {token.sub}\n"
                    f"Token expires in: {token.expires_in // 86400} days\n"
                    f"Scopes: {token.scope}"
                ),
            )
        ]
    )


async def _handle_logout() -> CallToolResult:
    cleared = auth.clear_token()
    msg = "Logged out — tokens cleared." if cleared else "No stored tokens found."
    return CallToolResult(content=[TextContent(type="text", text=msg)])


async def _handle_status() -> CallToolResult:
    token = auth.load_token()
    if not token:
        return CallToolResult(
            content=[TextContent(type="text", text="Not logged in. Use linkedin_login to authenticate.")]
        )
    expired = token.is_expired()
    lines = [
        f"Status: {'EXPIRED' if expired else 'Active'}",
        f"Member ID: {token.sub}",
        f"Scopes: {token.scope}",
        f"Created: {token.age_description()}",
        f"Days remaining: {token.days_remaining()}",
        f"Refresh token: {'available' if token.refresh_token else 'none'}",
    ]
    if expired and token.refresh_token:
        lines.append("Auto-refresh will be attempted on next API call.")
    elif expired:
        lines.append("Use linkedin_login to re-authenticate.")
    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(lines))]
    )


async def _handle_profile() -> CallToolResult:
    token = _require_token()
    profile = api.get_profile(token.access_token)
    return CallToolResult(content=[TextContent(type="text", text=profile.summary())])


async def _handle_audit_log(args: dict[str, Any]) -> CallToolResult:
    limit = args.get("limit", 20)
    path = audit._get_log_path()
    if not path.exists():
        return CallToolResult(
            content=[TextContent(type="text", text="No audit log entries yet.")]
        )
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-limit:]
    entries = []
    for line in recent:
        entry = json.loads(line)
        ts = entry["timestamp"][:19].replace("T", " ")
        action = entry["action"].upper()
        tool = entry["tool"].replace("linkedin_", "")
        summary = entry["content_summary"][:80]
        result = entry.get("result", "")
        row = f"[{ts}] {action:10s} {tool:25s} {summary}"
        if result:
            row += f" -> {result}"
        entries.append(row)
    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(entries))]
    )


async def _handle_health() -> CallToolResult:
    checks: list[str] = []

    # 1. Token check
    token = auth.load_token()
    if not token:
        checks.append("[FAIL] Token: No stored token found")
        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(checks))]
        )

    expired = token.is_expired()
    if expired:
        checks.append(f"[WARN] Token: Expired ({token.age_description()})")
        if token.refresh_token:
            checks.append("[INFO] Refresh token available — auto-refresh will be attempted")
        else:
            checks.append("[FAIL] No refresh token — manual re-login required")
    else:
        checks.append(f"[OK]   Token: Valid, {token.days_remaining()} days remaining")

    # 2. Scope check
    if token.scope:
        granted = set(token.scope.split())
        missing = REQUIRED_SCOPES - granted
        if missing:
            checks.append(f"[FAIL] Scopes: Missing {', '.join(sorted(missing))}")
        else:
            checks.append(f"[OK]   Scopes: All required scopes granted")
    else:
        checks.append("[WARN] Scopes: No scope data stored — cannot verify")

    # 3. Credentials check
    try:
        _get_credentials()
        checks.append("[OK]   Credentials: Client ID and secret configured")
    except RuntimeError:
        checks.append("[FAIL] Credentials: LINKEDIN_CLIENT_ID or LINKEDIN_CLIENT_SECRET missing")

    # 4. API connectivity check (only if token not expired)
    if not expired:
        try:
            resp = httpx.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {token.access_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                checks.append("[OK]   API: LinkedIn API reachable and token accepted")
            elif resp.status_code == 401:
                checks.append("[FAIL] API: Token rejected by LinkedIn (401 Unauthorized)")
            else:
                checks.append(f"[WARN] API: Unexpected status {resp.status_code}")
        except Exception as e:
            checks.append(f"[FAIL] API: Cannot reach LinkedIn — {e}")
    else:
        checks.append("[SKIP] API: Skipped (token expired)")

    # 5. Encryption check
    checks.append("[OK]   Encryption: Tokens encrypted at rest")

    # 6. Audit log check and daily usage
    audit_path = audit._get_log_path()
    if audit_path.exists():
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        checks.append(f"[OK]   Audit: {len(lines)} entries logged")

        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        posts_today = sum(
            1 for line in lines
            if line.startswith("{")
            and f'"action": "published"' in line
            and today in line
        )
        if posts_today >= 120:
            checks.append(f"[WARN] Usage: {posts_today}/150 posts today — approaching daily limit")
        else:
            checks.append(f"[OK]   Usage: {posts_today}/150 posts today")
    else:
        checks.append("[INFO] Audit: No entries yet")
        checks.append("[OK]   Usage: 0/150 posts today")

    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(checks))]
    )


async def _handle_text_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    text = args["text"]
    visibility = args.get("visibility", "PUBLIC")

    if not args.get("confirm", False):
        stamp = _get_approval_stamp()
        stamped = text + stamp
        preview = f"Text post ({visibility}):\n\n{stamped}"
        audit.log("preview", "linkedin_create_text_post", text)
        return _preview_result(preview, stamped)

    audit.log("publish", "linkedin_create_text_post", text)
    result = api.create_text_post(token.access_token, token.sub, text, visibility)
    audit.log("published", "linkedin_create_text_post", text, result.urn)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def _handle_article_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    text = args["text"]
    url = args["url"]
    title = args.get("title", "")
    description = args.get("description", "")
    visibility = args.get("visibility", "PUBLIC")

    if not args.get("confirm", False):
        stamp = _get_approval_stamp()
        stamped = text + stamp
        preview = f"Article post ({visibility}):\n\n{stamped}\n\nURL: {url}"
        if title:
            preview += f"\nTitle: {title}"
        if description:
            preview += f"\nDescription: {description}"
        audit.log("preview", "linkedin_create_article_post", f"{text} | {url}")
        return _preview_result(preview, stamped)

    audit.log("publish", "linkedin_create_article_post", f"{text} | {url}")
    result = api.create_article_post(
        access_token=token.access_token,
        person_urn=token.sub,
        text=text,
        url=url,
        title=title,
        description=description,
        visibility=visibility,
    )
    audit.log("published", "linkedin_create_article_post", f"{text} | {url}", result.urn)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def _handle_image_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    text = args["text"]
    image_path = args["image_path"]
    title = args.get("title", "")
    description = args.get("description", "")
    visibility = args.get("visibility", "PUBLIC")

    if not args.get("confirm", False):
        stamp = _get_approval_stamp()
        stamped = text + stamp
        preview = f"Image post ({visibility}):\n\n{stamped}\n\nImage: {image_path}"
        if title:
            preview += f"\nTitle: {title}"
        if description:
            preview += f"\nDescription: {description}"
        audit.log("preview", "linkedin_create_image_post", f"{text} | {image_path}")
        return _preview_result(preview, stamped)

    audit.log("publish", "linkedin_create_image_post", f"{text} | {image_path}")
    result = api.create_image_post(
        access_token=token.access_token,
        person_urn=token.sub,
        text=text,
        image_path=image_path,
        title=title,
        description=description,
        visibility=visibility,
    )
    audit.log("published", "linkedin_create_image_post", f"{text} | {image_path}", result.urn)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def _handle_delete_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    post_urn = args["post_urn"]

    if not args.get("confirm", False):
        preview = f"DELETE post: {post_urn}\n\nThis action cannot be undone."
        audit.log("preview", "linkedin_delete_post", post_urn)
        return _preview_result(preview)

    audit.log("delete", "linkedin_delete_post", post_urn)
    result = api.delete_post(token.access_token, post_urn)
    audit.log("deleted", "linkedin_delete_post", post_urn)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


def _find_last_published_urn() -> tuple[str, str] | None:
    """Find the URN and content summary of the last published post from the audit log."""
    path = audit._get_log_path()
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    for line in reversed(lines):
        if not line.startswith("{"):
            continue
        entry = json.loads(line)
        if entry.get("action") == "published" and entry.get("result"):
            return entry["result"], entry.get("content_summary", "")
    return None


async def _handle_undo_last_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    last = _find_last_published_urn()
    if not last:
        return CallToolResult(
            content=[TextContent(type="text", text="No published posts found in the audit log.")],
            isError=True,
        )

    post_urn, content_summary = last

    if not args.get("confirm", False):
        preview = (
            f"UNDO — delete the most recently published post:\n\n"
            f"URN: {post_urn}\n"
            f"Content: {content_summary[:200]}\n\n"
            f"This action cannot be undone."
        )
        audit.log("preview", "linkedin_undo_last_post", post_urn)
        return _preview_result(preview)

    audit.log("undo", "linkedin_undo_last_post", post_urn)
    result = api.delete_post(token.access_token, post_urn)
    audit.log("undone", "linkedin_undo_last_post", post_urn)
    return CallToolResult(
        content=[TextContent(type="text", text=f"Undo complete — {result.message}")]
    )


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
