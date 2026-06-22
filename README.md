# LinkedIn MCP Server

A **ToS-compliant** [Model Context Protocol](https://modelcontextprotocol.io/) server for LinkedIn, using only the official LinkedIn API.

Unlike other LinkedIn MCP servers that rely on scraping (which violates LinkedIn's User Agreement and risks account bans), this server uses LinkedIn's official Consumer API with proper OAuth 2.0 authentication.

## Quick start

**Fastest way to get started:** Copy the setup prompt from **[SETUP_PROMPT.md](SETUP_PROMPT.md)** and paste it into Claude Code. Claude will clone the repo, install it, configure your credentials, and log you in — you just click "allow" on each step.

> Need to do it manually instead? Follow the step-by-step [Setup Guide](SETUP.md) or continue reading below.

## Posting pipeline

A built-in web dashboard for managing your LinkedIn content from draft to publish. Write posts as markdown files, move them through a kanban board, schedule them for specific dates and times, and let Claude post them automatically when they're due.

```
Draft  →  Approved  →  Scheduled  →  Completed
```

**Quick setup:** Copy the prompt from **[PIPELINE_SETUP_PROMPT.md](PIPELINE_SETUP_PROMPT.md)** into Claude Code — it handles the install, auto-start, and scheduled posting for you.

| Feature | Detail |
|---|---|
| **Kanban board** | Drag posts through each stage at [localhost:8420](http://localhost:8420) |
| **Schedule view** | Calendar of upcoming posts with due/overdue alerts |
| **Time-aware scheduling** | Set a specific date and time for each post |
| **Auto-publish** | Claude Code scheduled task posts automatically when due (max 3 per run, 10s apart) |
| **Edit safeguard** | Editing an approved or scheduled post moves it back to draft for re-approval |
| **Character limit** | Posts over 3,000 characters cannot be scheduled |
| **Zero dependencies** | Python stdlib only — no additional packages |

See [pipeline/README.md](pipeline/README.md) for full manual setup, configuration, and schedule options.

## MCP tools

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
| `linkedin_create_video_post` | Upload a video and publish with text |
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
- **Video posts** — Upload and publish video content (MP4, MOV, AVI, MKV, WEBM) up to 200 MB via LinkedIn's video upload API
- **Minimal scope** — Only requests the API scopes needed (`openid`, `profile`, `email`, `w_member_social`)

### Testing

The project includes a comprehensive test suite with **229 unit tests** (96% coverage) covering all modules:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

| Test file | Tests | Coverage |
|---|---|---|
| `test_models.py` | 24 | Encryption, token save/load, expiry, backward compatibility, configurable key |
| `test_auth.py` | 32 | OAuth flow, token refresh, auto-refresh logic, scope normalisation, configurable port, callback handler, real HTTP callback tests |
| `test_api.py` | 39 | Post building, approval stamp, API calls, URL encoding, image upload, video upload, link preview, polls, documents |
| `test_audit.py` | 7 | NDJSON logging, truncation, directory creation, configurable path |
| `test_history.py` | 14 | Post recording, retrieval, filtering, deletion, corruption handling |
| `test_server.py` | 115 | All tool handlers, call routing, preview enforcement, health check, undo, polls, documents, video, setup, MCP Inspector |

## Setup

- **[Setup Prompt](SETUP_PROMPT.md)** — paste into Claude Code and let it do everything for you
- **[Manual Setup Guide](SETUP.md)** — step-by-step if you prefer to do it yourself

### Requirements

- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** — this is an MCP server designed for use with Claude Code (requires an Anthropic subscription: Pro, Max, Team, or Enterprise). It also works with Claude Desktop for Cowork integration. See the [deployment notes](#deployment) below for other surfaces.
- **Python 3.10+**
- A [LinkedIn Developer App](https://www.linkedin.com/developers/apps) with "Sign in with LinkedIn" and "Share on LinkedIn" enabled

### Install

```bash
git clone https://github.com/anubisalpha/linkedin-mcp.git
cd linkedin-mcp
pip install -e .
```

This installs the `linkedin-mcp` CLI command. You can also run the server as a module:

```bash
linkedin-mcp          # CLI entry point
python -m linkedin_mcp  # module entry point (equivalent)
```

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

## Deployment

This server uses **stdio transport**, which means it runs locally alongside your MCP client.

| Surface | Transport | Status | Notes |
|---|---|---|---|
| **Claude Code** | stdio via `.mcp.json` | Supported | Primary target. Requires an Anthropic subscription. |
| **Claude Desktop / Cowork** | stdio via `claude_desktop_config.json` | Supported | Same server, different config file. Token cache is shared if on the same machine. |
| **claude.ai (web)** | Streamable HTTP | Not supported | Would require hosting the server publicly over HTTPS with a different transport layer. |

### `.mcp.json` example

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "linkedin-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret"
      }
    }
  }
}
```

Use `linkedin-mcp` (the CLI entry point) or `python -m linkedin_mcp` as the command. Use literal credential values, not `${VAR}` references.

## Architecture

See [docs/architecture.md](docs/architecture.md) for implementation details and design decisions.

## Support

If you find this useful, consider [buying me a coffee](https://buymeacoffee.com/anubisalpha). No pressure at all — but if you'd like to support the project, it's genuinely appreciated.

## License

MIT
