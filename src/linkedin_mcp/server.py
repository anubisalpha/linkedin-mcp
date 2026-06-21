#!/usr/bin/env python3
"""LinkedIn MCP Server — ToS-compliant LinkedIn integration via the official API."""

import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from . import api, auth

server = Server("linkedin-mcp")


def _get_credentials() -> tuple[str, str]:
    client_id = os.environ.get("LINKEDIN_CLIENT_ID", "")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables are required. "
            "Create a LinkedIn Developer App at https://www.linkedin.com/developers/apps"
        )
    return client_id, client_secret


def _require_token() -> auth.TokenData:
    token = auth.load_token()
    if not token:
        raise RuntimeError("Not logged in. Use the linkedin_login tool first.")
    return token


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="linkedin_login",
            description=(
                "Log in to LinkedIn via OAuth 2.0. Opens your browser for authorization. "
                "You must have a LinkedIn Developer App configured with 'Sign in with LinkedIn' "
                "and 'Share on LinkedIn' products enabled."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="linkedin_logout",
            description="Clear stored LinkedIn authentication tokens.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="linkedin_status",
            description="Check current LinkedIn authentication status and token info.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="linkedin_profile",
            description="Get the authenticated LinkedIn member's profile (name, email, photo, locale).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="linkedin_create_text_post",
            description=(
                "Publish a text-only post to LinkedIn. "
                "The post content is sent exactly as provided — review before approving."
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
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="linkedin_create_article_post",
            description=(
                "Share a URL/article on LinkedIn with commentary. "
                "The post is published exactly as provided — review before approving."
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
                },
                "required": ["text", "url"],
            },
        ),
        Tool(
            name="linkedin_create_image_post",
            description=(
                "Upload an image and publish a post with it on LinkedIn. "
                "The post is published exactly as provided — review before approving."
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
                },
                "required": ["text", "image_path"],
            },
        ),
        Tool(
            name="linkedin_delete_post",
            description="Delete a LinkedIn post by its URN.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_urn": {
                        "type": "string",
                        "description": "The URN of the post to delete (returned when the post was created).",
                    },
                },
                "required": ["post_urn"],
            },
        ),
    ]


@server.call_tool()
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
        elif name == "linkedin_create_text_post":
            return await _handle_text_post(arguments)
        elif name == "linkedin_create_article_post":
            return await _handle_article_post(arguments)
        elif name == "linkedin_create_image_post":
            return await _handle_image_post(arguments)
        elif name == "linkedin_delete_post":
            return await _handle_delete_post(arguments)
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
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=(
                    f"Logged in.\n"
                    f"Member ID: {token.sub}\n"
                    f"Scopes: {token.scope}\n"
                    f"Token lifetime: {token.expires_in // 86400} days"
                ),
            )
        ]
    )


async def _handle_profile() -> CallToolResult:
    token = _require_token()
    profile = api.get_profile(token.access_token)
    return CallToolResult(content=[TextContent(type="text", text=profile.summary())])


async def _handle_text_post(args: dict) -> CallToolResult:
    token = _require_token()
    text = args["text"]
    visibility = args.get("visibility", "PUBLIC")
    result = api.create_text_post(token.access_token, token.sub, text, visibility)
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def _handle_article_post(args: dict) -> CallToolResult:
    token = _require_token()
    result = api.create_article_post(
        access_token=token.access_token,
        person_urn=token.sub,
        text=args["text"],
        url=args["url"],
        title=args.get("title", ""),
        description=args.get("description", ""),
        visibility=args.get("visibility", "PUBLIC"),
    )
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def _handle_image_post(args: dict) -> CallToolResult:
    token = _require_token()
    result = api.create_image_post(
        access_token=token.access_token,
        person_urn=token.sub,
        text=args["text"],
        image_path=args["image_path"],
        title=args.get("title", ""),
        description=args.get("description", ""),
        visibility=args.get("visibility", "PUBLIC"),
    )
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def _handle_delete_post(args: dict) -> CallToolResult:
    token = _require_token()
    result = api.delete_post(token.access_token, args["post_urn"])
    return CallToolResult(content=[TextContent(type="text", text=result.message)])


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
