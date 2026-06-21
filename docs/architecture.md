# Architecture

Technical documentation for contributors and anyone wanting to understand how the LinkedIn MCP server works under the hood.

## Design principles

1. **ToS-compliant** — uses only LinkedIn's official Consumer API, no scraping
2. **Human-in-the-loop** — every write action requires explicit user approval before the API call fires
3. **Minimal footprint** — only two dependencies beyond the standard library (`mcp`, `httpx`)
4. **Cross-platform** — works on Windows, macOS, and Linux
5. **Privacy-first** — stores only auth tokens locally, no telemetry, no data caching

## Project structure

```
linkedin-mcp/
├── pyproject.toml              # Package metadata, dependencies
├── README.md                   # User-facing setup guide
├── LICENSE                     # MIT
├── .gitignore
├── .env.example                # Template for credentials
├── docs/
│   ├── architecture.md         # This file
│   ├── privacy-policy.md       # Privacy policy (served via GitHub Pages)
│   ├── logo.svg                # App logo (SVG source)
│   └── logo.png                # App logo (512x512 PNG for LinkedIn Developer Portal)
└── src/
    └── linkedin_mcp/
        ├── __init__.py
        ├── __main__.py         # Entry point for `python -m linkedin_mcp`
        ├── server.py           # MCP server — tool definitions and request routing
        ├── auth.py             # OAuth 2.0 flow, token storage, local callback server
        ├── api.py              # LinkedIn API client — profile, posts, image upload
        └── models.py           # Dataclasses for tokens, profiles, and post results
```

## Module details

### server.py — MCP tool definitions

The MCP entry point. Registers 8 tools using the `mcp` SDK's decorator pattern:

- **Auth tools** (`linkedin_login`, `linkedin_logout`, `linkedin_status`) — manage the OAuth session
- **Read tools** (`linkedin_profile`) — fetch data from LinkedIn's API
- **Write tools** (`linkedin_create_text_post`, `linkedin_create_article_post`, `linkedin_create_image_post`, `linkedin_delete_post`) — publish or delete content

Each handler delegates to `auth.py` or `api.py` and wraps results in `CallToolResult` with `TextContent`. Errors are caught and returned as `isError=True` results rather than crashing the server.

The server runs via `stdio_server()`, communicating with the MCP client over stdin/stdout.

### auth.py — OAuth 2.0 authentication

Implements LinkedIn's 3-legged OAuth Authorization Code Flow:

1. **`start_login()`** — builds the authorization URL with CSRF state token and opens the user's browser
2. **`wait_for_callback()`** — starts a local HTTP server on `localhost:8585` to capture the OAuth redirect
3. **`exchange_code()`** — exchanges the authorization code for an access token via LinkedIn's token endpoint
4. **`fetch_sub()`** — calls the userinfo endpoint to get the member's `sub` identifier (used as the person URN for posting)

**Token storage**: tokens are persisted as JSON at `~/.linkedin-mcp/tokens.json` (configurable via `LINKEDIN_MCP_TOKEN_PATH`). The file contains the access token, refresh token, scopes, expiry, and the member's `sub` identifier.

**Callback server**: uses Python's built-in `http.server.HTTPServer` with a custom handler. Runs in a daemon thread with a 120-second timeout. Logging is suppressed to avoid noise on stdout (which would interfere with MCP stdio communication).

### api.py — LinkedIn API client

Wraps LinkedIn's v2 REST API using `httpx`:

- **Profile**: `GET /v2/userinfo` — returns name, photo, email, locale
- **Text posts**: `POST /v2/ugcPosts` with `shareMediaCategory: NONE`
- **Article posts**: `POST /v2/ugcPosts` with `shareMediaCategory: ARTICLE` and a media array containing the URL
- **Image posts**: three-step process:
  1. `POST /v2/assets?action=registerUpload` — register the upload and get an upload URL
  2. `PUT {uploadUrl}` — upload the image binary
  3. `POST /v2/ugcPosts` with `shareMediaCategory: IMAGE` and the asset URN
- **Delete**: `DELETE /v2/ugcPosts/{encoded_urn}`

All requests include the `X-Restli-Protocol-Version: 2.0.0` header required by LinkedIn's API.

The author field on every post uses the format `urn:li:person:{sub}`, where `sub` comes from the stored token data.

### models.py — data models

Three dataclasses:

- **`TokenData`** — access token, expiry, scopes, sub, refresh token. Includes `save()` and `load()` methods for JSON persistence.
- **`Profile`** — member profile fields from the userinfo endpoint. Includes a `summary()` method for human-readable output.
- **`PostResult`** — post URN, status, and message returned after creating or deleting a post.

## LinkedIn API reference

### Endpoints used

| Endpoint | Method | Purpose | Scope required |
|---|---|---|---|
| `/oauth/v2/authorization` | GET | Start OAuth flow | — |
| `/oauth/v2/accessToken` | POST | Exchange code for token | — |
| `/v2/userinfo` | GET | Get member profile | `openid profile email` |
| `/v2/ugcPosts` | POST | Create a post | `w_member_social` |
| `/v2/ugcPosts/{urn}` | DELETE | Delete a post | `w_member_social` |
| `/v2/assets?action=registerUpload` | POST | Register image upload | `w_member_social` |

### Rate limits

- **150 posts/day** per member
- **100,000 API calls/day** per application
- Access tokens expire after **60 days**

### Visibility options

- `PUBLIC` — visible to anyone on LinkedIn
- `CONNECTIONS` — visible to 1st-degree connections only

## Design decisions

### Why official API only?

Every existing LinkedIn MCP server on GitHub uses browser automation or scraping services, which violates LinkedIn's User Agreement (Section 8.2). Accounts using these tools risk restriction or permanent bans. This server exists specifically to provide a legitimate alternative.

The trade-off is reduced functionality — the open Consumer API only exposes basic profile info and posting. Full profile data (experience, skills, projects, education) is locked behind partner programs. We believe ToS compliance is worth this trade-off.

### Why human-in-the-loop?

LinkedIn's API Terms of Use explicitly prohibit using "Content or the APIs to automate posting on the LinkedIn Services." By requiring user approval for every write action, the server stays compliant — the human reviews and confirms each post before it's published.

In Claude Code, this happens naturally via the tool approval prompt. In other MCP clients, the same principle applies — the client should present the action for confirmation before executing.

### Why not store profile data?

LinkedIn's API Terms of Use require that stored content must be "only for the duration necessary to provide your Application's services" and that developers "must not capture, copy, cache, or store any Content" except as expressly permitted. Since profile data can be fetched on demand in milliseconds, there's no reason to cache it.

### Why localhost callback instead of a hosted redirect?

A localhost callback server keeps the entire auth flow on the user's machine — no external server needed, no credentials transmitted to third parties, no hosting costs. The trade-off is that the user needs port 8585 available, but this is configurable if needed in a future release.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally with a LinkedIn Developer App
5. Submit a pull request

When adding new tools, follow the existing pattern: define the tool in `list_tools()`, add a handler function, and delegate to `api.py` for the actual API call.
