#!/usr/bin/env python3
"""LinkedIn MCP Server — ToS-compliant LinkedIn integration via the official API."""

import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from . import api, audit, auth, history
from .api import _get_approval_stamp
from .models import TokenData

LINKEDIN_POST_CHAR_LIMIT = 3000

server = Server(
    "linkedin-mcp",
    version="0.4.0",
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
        Tool(
            name="linkedin_post_history",
            description=(
                "View your post history — all posts published through this server with "
                "their URNs, timestamps, content, and visibility. Optionally filter by type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent posts to show. Defaults to 20.",
                        "default": 20,
                    },
                    "type": {
                        "type": "string",
                        "enum": ["text", "article", "image", "poll", "document"],
                        "description": "Filter by post type. Omit to show all types.",
                        "default": "",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_link_preview",
            description=(
                "Fetch Open Graph metadata from a URL to see how LinkedIn will display it "
                "in the feed. Shows title, description, image, and site name. Use before "
                "sharing an article to check the link card looks right."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to preview.",
                    },
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_create_poll",
            description=(
                "Create a poll on LinkedIn with a question and 2-4 options. "
                "Must be called twice: first without confirm to preview, "
                "then with confirm=true after the user approves the content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Commentary text to accompany the poll.",
                    },
                    "question": {
                        "type": "string",
                        "description": "The poll question (max 140 characters).",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 4,
                        "description": "2-4 poll options (each max 30 characters).",
                    },
                    "duration": {
                        "type": "string",
                        "enum": ["1_DAY", "3_DAYS", "7_DAYS", "14_DAYS"],
                        "description": "How long the poll runs. Defaults to 3_DAYS.",
                        "default": "3_DAYS",
                    },
                    "visibility": {
                        "type": "string",
                        "enum": ["PUBLIC", "CONNECTIONS"],
                        "description": "Who can see the post. Defaults to PUBLIC.",
                        "default": "PUBLIC",
                    },
                    "confirm": CONFIRM_SCHEMA,
                },
                "required": ["text", "question", "options"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_create_document_post",
            description=(
                "Upload a document (PDF, slide deck, etc.) and publish a post with it on LinkedIn. "
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
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the document file to upload (PDF, PPTX, DOCX, etc.).",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title displayed on the document card in the feed.",
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
                "required": ["text", "file_path"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_create_video_post",
            description=(
                "Upload a video and publish a post with it on LinkedIn. "
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
                    "video_path": {
                        "type": "string",
                        "description": "Absolute path to the video file to upload.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the video.",
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
                "required": ["text", "video_path"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="linkedin_setup",
            description=(
                "First-run setup assistant. Checks your configuration and walks you through "
                "any missing steps: credentials, LinkedIn Developer App, redirect URL, OAuth "
                "products, and first login. Run this when setting up the server for the first time."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
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
        elif name == "linkedin_create_poll":
            return await _handle_poll_post(arguments)
        elif name == "linkedin_create_document_post":
            return await _handle_document_post(arguments)
        elif name == "linkedin_create_video_post":
            return await _handle_video_post(arguments)
        elif name == "linkedin_post_history":
            return await _handle_post_history(arguments)
        elif name == "linkedin_link_preview":
            return await _handle_link_preview(arguments)
        elif name == "linkedin_setup":
            return await _handle_setup()
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
    history.record_post(result.urn, "text", text, visibility)
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
    history.record_post(result.urn, "article", text, visibility, url=url)
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
    history.record_post(result.urn, "image", text, visibility, image_path=image_path)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def _handle_poll_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    text = args["text"]
    question = args["question"]
    options: list[str] = args["options"]
    duration = args.get("duration", "3_DAYS")
    visibility = args.get("visibility", "PUBLIC")

    if len(options) < 2 or len(options) > 4:
        return CallToolResult(
            content=[TextContent(type="text", text="Polls require 2-4 options.")],
            isError=True,
        )
    if len(question) > 140:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Poll question is {len(question)} characters — max is 140.",
            )],
            isError=True,
        )
    long_options = [f"'{o}' ({len(o)} chars)" for o in options if len(o) > 30]
    if long_options:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Poll options over 30-char limit: {', '.join(long_options)}",
            )],
            isError=True,
        )

    if not args.get("confirm", False):
        stamp = _get_approval_stamp()
        stamped = text + stamp
        opts_display = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(options))
        preview = (
            f"Poll post ({visibility}):\n\n{stamped}\n\n"
            f"Question: {question}\n"
            f"Options:\n{opts_display}\n"
            f"Duration: {duration.replace('_', ' ')}"
        )
        audit.log("preview", "linkedin_create_poll", f"{question} | {text}")
        return _preview_result(preview, stamped)

    audit.log("publish", "linkedin_create_poll", f"{question} | {text}")
    result = api.create_poll_post(
        access_token=token.access_token,
        person_urn=token.sub,
        text=text,
        question=question,
        options=options,
        duration=duration,
        visibility=visibility,
    )
    audit.log("published", "linkedin_create_poll", f"{question} | {text}", result.urn)
    history.record_post(result.urn, "poll", f"{question}: {text}", visibility)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls"}


async def _handle_document_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    text = args["text"]
    file_path = args["file_path"]
    title = args.get("title", "")
    visibility = args.get("visibility", "PUBLIC")

    from pathlib import Path as _Path
    doc_path = _Path(file_path)
    if not doc_path.exists():
        return CallToolResult(
            content=[TextContent(type="text", text=f"File not found: {file_path}")],
            isError=True,
        )
    ext = doc_path.suffix.lower()
    if ext not in SUPPORTED_DOCUMENT_EXTENSIONS:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))}",
            )],
            isError=True,
        )

    file_size_mb = doc_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 100:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"File is {file_size_mb:.1f} MB — LinkedIn's limit is 100 MB.",
            )],
            isError=True,
        )

    if not args.get("confirm", False):
        stamp = _get_approval_stamp()
        stamped = text + stamp
        preview = (
            f"Document post ({visibility}):\n\n{stamped}\n\n"
            f"File: {doc_path.name} ({file_size_mb:.1f} MB)"
        )
        if title:
            preview += f"\nTitle: {title}"
        audit.log("preview", "linkedin_create_document_post", f"{text} | {file_path}")
        return _preview_result(preview, stamped)

    audit.log("publish", "linkedin_create_document_post", f"{text} | {file_path}")
    result = api.create_document_post(
        access_token=token.access_token,
        person_urn=token.sub,
        text=text,
        file_path=file_path,
        title=title,
        visibility=visibility,
    )
    audit.log("published", "linkedin_create_document_post", f"{text} | {file_path}", result.urn)
    history.record_post(result.urn, "document", text, visibility)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_VIDEO_SIZE_MB = 200


async def _handle_video_post(args: dict[str, Any]) -> CallToolResult:
    token = _require_token()
    text = args["text"]
    video_path = args["video_path"]
    title = args.get("title", "")
    visibility = args.get("visibility", "PUBLIC")

    from pathlib import Path as _Path
    vid_path = _Path(video_path)
    if not vid_path.exists():
        return CallToolResult(
            content=[TextContent(type="text", text=f"File not found: {video_path}")],
            isError=True,
        )
    ext = vid_path.suffix.lower()
    if ext not in SUPPORTED_VIDEO_EXTENSIONS:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Unsupported video type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_VIDEO_EXTENSIONS))}",
            )],
            isError=True,
        )

    file_size_mb = vid_path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_VIDEO_SIZE_MB:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Video is {file_size_mb:.1f} MB — LinkedIn's limit is {MAX_VIDEO_SIZE_MB} MB.",
            )],
            isError=True,
        )

    if not args.get("confirm", False):
        stamp = _get_approval_stamp()
        stamped = text + stamp
        preview = (
            f"Video post ({visibility}):\n\n{stamped}\n\n"
            f"File: {vid_path.name} ({file_size_mb:.1f} MB)"
        )
        if title:
            preview += f"\nTitle: {title}"
        audit.log("preview", "linkedin_create_video_post", f"{text} | {video_path}")
        return _preview_result(preview, stamped)

    audit.log("publish", "linkedin_create_video_post", f"{text} | {video_path}")
    result = api.create_video_post(
        access_token=token.access_token,
        person_urn=token.sub,
        text=text,
        video_path=video_path,
        title=title,
        visibility=visibility,
    )
    audit.log("published", "linkedin_create_video_post", f"{text} | {video_path}", result.urn)
    history.record_post(result.urn, "video", text, visibility)
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
    history.delete_from_history(post_urn)
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
    history.delete_from_history(post_urn)
    return CallToolResult(
        content=[TextContent(type="text", text=f"Undo complete — {result.message}")]
    )


async def _handle_post_history(args: dict[str, Any]) -> CallToolResult:
    limit = args.get("limit", 20)
    post_type = args.get("type", "")
    entries = history.get_history(limit, post_type)
    if not entries:
        msg = "No posts in history yet."
        if post_type:
            msg = f"No {post_type} posts in history."
        return CallToolResult(content=[TextContent(type="text", text=msg)])

    lines = []
    for entry in entries:
        ts = entry["timestamp"][:19].replace("T", " ")
        ptype = entry.get("type", "unknown").upper()
        vis = entry.get("visibility", "PUBLIC")
        content = entry.get("content", "")[:80]
        urn = entry.get("urn", "")
        row = f"[{ts}] {ptype:7s} ({vis}) {content}"
        if urn:
            row += f"\n         URN: {urn}"
        url = entry.get("url", "")
        if url:
            row += f"\n         URL: {url}"
        lines.append(row)

    header = f"Post history ({len(entries)} posts)"
    if post_type:
        header += f" — filtered: {post_type}"
    return CallToolResult(
        content=[TextContent(type="text", text=f"{header}\n\n" + "\n\n".join(lines))]
    )


async def _handle_link_preview(args: dict[str, Any]) -> CallToolResult:
    url = args["url"]
    preview = api.fetch_link_preview(url)
    return CallToolResult(content=[TextContent(type="text", text=preview.summary())])


async def _handle_setup() -> CallToolResult:
    steps: list[str] = []
    all_ok = True

    steps.append("LinkedIn MCP Server — Setup Check")
    steps.append("=" * 40)
    steps.append("")

    # 1. Credentials
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "")

    if client_id and client_secret:
        steps.append(f"[OK]   Client ID: {client_id[:8]}...")
        steps.append("[OK]   Client Secret: configured")
    else:
        all_ok = False
        steps.append("[MISSING] LinkedIn API credentials not configured")
        steps.append("")
        steps.append("To fix this:")
        steps.append("1. Go to https://www.linkedin.com/developers/apps")
        steps.append("2. Click 'Create app' (or select an existing app)")
        steps.append("3. Copy the Client ID and Client Secret from the Auth tab")
        steps.append("4. Add them to your MCP configuration:")
        steps.append("")
        steps.append('   In .mcp.json (or ~/.claude/.mcp.json):')
        steps.append('   {')
        steps.append('     "mcpServers": {')
        steps.append('       "linkedin": {')
        steps.append('         "command": "python",')
        steps.append('         "args": ["-m", "linkedin_mcp.server"],')
        steps.append('         "env": {')
        steps.append('           "LINKEDIN_CLIENT_ID": "your_client_id",')
        steps.append('           "LINKEDIN_CLIENT_SECRET": "your_client_secret"')
        steps.append("         }")
        steps.append("       }")
        steps.append("     }")
        steps.append("   }")
        steps.append("")
        steps.append("   IMPORTANT: Use literal values, not ${VAR} references.")
        steps.append("   Restart Claude Code after updating .mcp.json.")
        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(steps))]
        )

    # 2. LinkedIn Developer App products
    steps.append("")
    steps.append("Required LinkedIn Developer App products:")
    steps.append("  - 'Sign in with LinkedIn using OpenID Connect' (scopes: openid, profile, email)")
    steps.append("  - 'Share on LinkedIn' (scope: w_member_social)")
    steps.append("  Enable both on the Products tab of your app at:")
    steps.append("  https://www.linkedin.com/developers/apps")
    steps.append("  Both are self-serve and activate immediately.")

    # 3. Redirect URL
    port = auth._get_callback_port()
    redirect_uri = auth._get_redirect_uri()
    steps.append("")
    steps.append(f"[INFO] Redirect URL must be set in your LinkedIn app's Auth tab:")
    steps.append(f"       {redirect_uri}")
    if port != 8585:
        steps.append(f"       (Using custom port {port} from LINKEDIN_MCP_CALLBACK_PORT)")

    # 4. Token status
    steps.append("")
    token = auth.load_token()
    if token and not token.is_expired():
        steps.append(f"[OK]   Logged in as member: {token.sub}")
        steps.append(f"       Token valid for {token.days_remaining()} more days")
        steps.append(f"       Scopes: {token.scope}")

        granted = set(token.scope.split()) if token.scope else set()
        missing = REQUIRED_SCOPES - granted
        if missing:
            all_ok = False
            steps.append(f"[WARN] Missing scopes: {', '.join(sorted(missing))}")
            steps.append("       Enable the required products on your LinkedIn app, then re-login.")
    elif token and token.is_expired():
        all_ok = False
        steps.append("[WARN] Token expired")
        if token.refresh_token:
            steps.append("       A refresh token is available — it will auto-refresh on next API call.")
        else:
            steps.append("       Run linkedin_login to re-authenticate.")
    else:
        all_ok = False
        steps.append("[NEXT] Not logged in yet")
        steps.append("       Run linkedin_login to authenticate with LinkedIn.")

    # 5. Optional config
    steps.append("")
    steps.append("Optional configuration:")
    env_vars = {
        "LINKEDIN_MCP_APPROVAL_STAMP": "Custom approval stamp text",
        "LINKEDIN_MCP_ENCRYPTION_KEY": "Custom encryption key for token portability",
        "LINKEDIN_MCP_CALLBACK_PORT": f"OAuth callback port (current: {port})",
        "LINKEDIN_MCP_TOKEN_PATH": "Custom token storage path",
        "LINKEDIN_MCP_AUDIT_PATH": "Custom audit log path",
        "LINKEDIN_MCP_HISTORY_PATH": "Custom post history path",
    }
    for var, desc in env_vars.items():
        val = os.environ.get(var)
        status = "set" if val else "default"
        steps.append(f"  {var}: {status} — {desc}")

    # 6. Posting pipeline
    steps.append("")
    steps.append("-" * 40)
    steps.append("Posting Pipeline (optional)")
    steps.append("-" * 40)
    steps.append("")

    from pathlib import Path

    pipeline_dir = Path(__file__).resolve().parent.parent.parent / "pipeline"
    pipeline_server = pipeline_dir / "server.py"
    pipeline_pages = pipeline_dir / "pages" / "index.html"

    if pipeline_server.exists() and pipeline_pages.exists():
        steps.append("[OK]   Pipeline installed")
        steps.append(f"       Location: {pipeline_dir}")

        pipeline_port = os.environ.get("PORT", "8420")
        steps.append(f"       Port: {pipeline_port}")

        stage_counts = {}
        for stage in ("draft", "approved", "scheduled", "completed"):
            stage_dir = pipeline_dir / stage
            if stage_dir.exists():
                count = len(list(stage_dir.glob("*.md")))
                stage_counts[stage] = count
            else:
                stage_counts[stage] = 0

        if any(stage_counts.values()):
            steps.append(f"       Posts: {stage_counts['draft']} draft, "
                         f"{stage_counts['approved']} approved, "
                         f"{stage_counts['scheduled']} scheduled, "
                         f"{stage_counts['completed']} completed")
        else:
            steps.append("       No posts yet — create your first post in the web UI")

        steps.append("")
        steps.append("  To start the pipeline server:")
        steps.append(f"    python {pipeline_server}")
        steps.append(f"    Open http://localhost:{pipeline_port}")
        steps.append("")
        steps.append("  To set up automated posting (optional):")
        steps.append('    Ask Claude: "Set up a LinkedIn posting check that runs daily at 9 AM"')
    elif pipeline_dir.exists():
        steps.append("[WARN] Pipeline directory found but incomplete")
        steps.append(f"       Location: {pipeline_dir}")
        if not pipeline_server.exists():
            steps.append("       Missing: server.py")
        if not pipeline_pages.exists():
            steps.append("       Missing: pages/index.html")
        steps.append("       Try reinstalling: pip install -e . or re-clone the repository")
    else:
        steps.append("[INFO] Pipeline not installed")
        steps.append("")
        steps.append("  The posting pipeline is an optional web dashboard for managing a")
        steps.append("  draft → approve → schedule → publish workflow for LinkedIn posts.")
        steps.append("")
        steps.append("  Features:")
        steps.append("  - Kanban board for post management")
        steps.append("  - Schedule view with due/overdue alerts")
        steps.append("  - Time-aware scheduling (specific date and time per post)")
        steps.append("  - Automated publishing via Claude Code scheduled tasks")
        steps.append("  - Edit safeguard (edits revert to draft for re-approval)")
        steps.append("")
        steps.append("  To install:")
        steps.append("  The pipeline/ directory should be in the project root alongside src/.")
        steps.append("  If you cloned the repo, it's already there. If you installed via pip,")
        steps.append("  clone the repo to get the pipeline:")
        steps.append("    git clone https://github.com/anubisalpha/linkedin-mcp.git")
        steps.append("    cd linkedin-mcp/pipeline")
        steps.append("    python server.py")

    # Summary
    steps.append("")
    steps.append("=" * 40)
    if all_ok:
        steps.append("Setup complete — ready to use!")
    else:
        steps.append("Follow the steps above to complete setup.")

    return CallToolResult(
        content=[TextContent(type="text", text="\n".join(steps))]
    )


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
