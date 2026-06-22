# LinkedIn MCP Server

A **ToS-compliant** [Model Context Protocol](https://modelcontextprotocol.io/) server for LinkedIn, using only the official LinkedIn API.

Unlike other LinkedIn MCP servers that rely on scraping (which violates LinkedIn's User Agreement and risks account bans), this server uses LinkedIn's official Consumer API with proper OAuth 2.0 authentication.

## Quick start

**Fastest way to get started:** Copy the setup prompt from **[SETUP_PROMPT.md](SETUP_PROMPT.md)** and paste it into Claude Code. Claude will clone the repo, install it, configure your credentials, and log you in — you just click "allow" on each step.

> Need to do it manually instead? Follow the step-by-step [Setup Guide](SETUP.md) or continue reading below.

## Features

### Tools

| Tool | Description |
|---|---|
| `linkedin_login` | OAuth 2.0 sign-in — opens your browser for secure authorization |
| `linkedin_logout` | Clear stored authentication tokens |
| `linkedin_status` | Check auth status, token expiry, and refresh token availability |
| `linkedin_health` | Run a health check — token validity, API connectivity, encryption, audit log |
| `linkedin_profile` | Get your name, email, photo, and locale |
| `linkedin_audit_log` | View the audit trail of all post previews, publishes, and deletions |
| `linkedin_create_text_post` | Publish a text post (public or connections-only) |
| `linkedin_create_article_post` | Share a URL/article with commentary |
| `linkedin_create_image_post` | Upload an image and publish with text |
| `linkedin_create_poll` | Create a poll with 2-4 options and configurable duration |
| `linkedin_create_document_post` | Upload a document (PDF, PPTX, DOCX, etc.) and publish with text |
| `linkedin_delete_post` | Delete a post by its URN |
| `linkedin_undo_last_post` | Quick-delete the most recently published post (undo) |
| `linkedin_post_history` | View your post history — URNs, timestamps, content, with optional type filter |
| `linkedin_link_preview` | Fetch Open Graph metadata from a URL to preview how LinkedIn will display it |
| `linkedin_setup` | First-run setup assistant — checks config and walks through any missing steps |

All write operations require explicit user approval before executing, keeping the integration compliant with LinkedIn's API Terms of Use (no automated posting).

### Security and compliance

- **Human-in-the-loop** — Every write tool uses a two-step confirm pattern: preview first (default), then publish only after explicit approval
- **Approval stamp** — Published posts include a configurable stamp showing the content was human-approved
- **Audit logging** — Every preview, publish, and delete is recorded in a local NDJSON audit log
- **Token encryption** — Access tokens are encrypted at rest using Fernet with a machine-derived key
- **Token refresh** — Silently refreshes expired tokens when a refresh token is available, avoiding unnecessary re-authentication
- **Health check** — Diagnose issues with a single tool call: checks token validity, API connectivity, credential configuration, and audit log status
- **Character count** — Post previews show character count against LinkedIn's 3,000-character limit, preventing over-length submissions
- **Undo/recall** — Quick-delete the most recently published post with a single tool call, without needing to look up the URN
- **MCP Inspector compatible** — All tool schemas include `additionalProperties: false` and the server declares its version for strict MCP spec compliance
- **Scope verification** — Checks that the stored token has all required scopes before attempting API actions, failing fast with a clear message
- **Configurable encryption key** — Optionally provide your own encryption key via environment variable for token portability between machines
- **Configurable callback port** — Change the OAuth callback port from the default 8585 via environment variable
- **Type checked** — Full mypy strict mode with no errors across all modules
- **CI pipeline** — GitHub Actions runs tests and type checking on Python 3.10, 3.11, and 3.12 for every push and PR
- **Post history** — Local record of all published posts with URNs, timestamps, content, and type filtering
- **Link preview** — Fetch Open Graph metadata from URLs before sharing to check the link card
- **First-run setup** — Interactive setup assistant that checks configuration and walks through missing steps
- **Poll creation** — Create LinkedIn polls with 2-4 options and configurable duration (1, 3, 7, or 14 days)
- **Document posts** — Upload and share PDFs, slide decks, and other documents as native LinkedIn document posts
- **Minimal scope** — Only requests the API scopes needed (`openid`, `profile`, `email`, `w_member_social`)

### Testing

The project includes a comprehensive test suite with **217 unit tests** (99% coverage) covering all modules:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

| Test file | Tests | Coverage |
|---|---|---|
| `test_models.py` | 24 | Encryption, token save/load, expiry, backward compatibility, configurable key |
| `test_auth.py` | 29 | OAuth flow, token refresh, auto-refresh logic, configurable port, callback handler, real HTTP callback tests |
| `test_api.py` | 35 | Post building, approval stamp, API calls, URL encoding, image upload, link preview, polls, documents |
| `test_audit.py` | 7 | NDJSON logging, truncation, directory creation, configurable path |
| `test_history.py` | 14 | Post recording, retrieval, filtering, deletion, corruption handling |
| `test_server.py` | 108 | All tool handlers, call routing, preview enforcement, health check, undo, polls, documents, setup, MCP Inspector |

## Setup

- **[Setup Prompt](SETUP_PROMPT.md)** — paste into Claude Code and let it do everything for you
- **[Manual Setup Guide](SETUP.md)** — step-by-step if you prefer to do it yourself

### Requirements

- Python 3.10+
- A [LinkedIn Developer App](https://www.linkedin.com/developers/apps) with "Sign in with LinkedIn" and "Share on LinkedIn" enabled

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `LINKEDIN_CLIENT_ID` | Yes | Your LinkedIn app's Client ID |
| `LINKEDIN_CLIENT_SECRET` | Yes | Your LinkedIn app's Client Secret |
| `LINKEDIN_MCP_TOKEN_PATH` | No | Custom token storage path (default: `~/.linkedin-mcp/tokens.json`) |
| `LINKEDIN_MCP_APPROVAL_STAMP` | No | Text appended to posts. Set to empty string to disable. |
| `LINKEDIN_MCP_AUDIT_PATH` | No | Custom audit log path (default: `~/.linkedin-mcp/audit.log`) |
| `LINKEDIN_MCP_ENCRYPTION_KEY` | No | Custom encryption key for token portability between machines |
| `LINKEDIN_MCP_HISTORY_PATH` | No | Custom post history path (default: `~/.linkedin-mcp/history.json`) |
| `LINKEDIN_MCP_CALLBACK_PORT` | No | OAuth callback port (default: `8585`) |

## How it works

1. **Authentication** — Standard OAuth 2.0 Authorization Code Flow via your browser. Credentials never pass through the MCP server.
2. **Token storage** — Encrypted at rest using Fernet. Tokens expire after 60 days; refresh tokens are used automatically when available.
3. **Human-in-the-loop** — Every write action requires explicit user approval before the API call is made.
4. **Minimal scope** — Only `openid`, `profile`, `email`, and `w_member_social`.

## ToS compliance

- Uses only the **official LinkedIn API** — no scraping, crawling, or browser automation
- **No automated posting** — every publish requires human approval
- **No data storage beyond tokens** — profile data is fetched on demand, not cached

## Rate limits

- **150 posts per day** per member
- **100,000 API calls per day** per application

## Architecture

See [docs/architecture.md](docs/architecture.md) for implementation details and design decisions.

## License

MIT
