# LinkedIn MCP Server

A **ToS-compliant** [Model Context Protocol](https://modelcontextprotocol.io/) server for LinkedIn, using only the official LinkedIn API.

Unlike other LinkedIn MCP servers that rely on scraping (which violates LinkedIn's User Agreement and risks account bans), this server uses LinkedIn's official Consumer API with proper OAuth 2.0 authentication.

## Quick start

```bash
git clone https://github.com/anubisalpha/linkedin-mcp.git
cd linkedin-mcp
pip install -e .
```

Add to your Claude Code `.mcp.json`:

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "python",
      "args": ["-m", "linkedin_mcp.server"],
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret"
      }
    }
  }
}
```

> **Important:** Replace `your_client_id` and `your_client_secret` with your actual values. Environment variable references like `${LINKEDIN_CLIENT_ID}` are not supported — use the literal strings.

Restart Claude Code, then ask: *"Log in to my LinkedIn account"*

## Features

| Tool | Description |
|---|---|
| `linkedin_login` | OAuth 2.0 sign-in — opens your browser for secure authorization |
| `linkedin_logout` | Clear stored authentication tokens |
| `linkedin_status` | Check auth status and token expiry |
| `linkedin_profile` | Get your name, email, photo, and locale |
| `linkedin_create_text_post` | Publish a text post (public or connections-only) |
| `linkedin_create_article_post` | Share a URL/article with commentary |
| `linkedin_create_image_post` | Upload an image and publish with text |
| `linkedin_delete_post` | Delete a post by its URN |

All write operations require explicit user approval before executing, keeping the integration compliant with LinkedIn's API Terms of Use (no automated posting).

## Setting up a LinkedIn Developer App

Before you can use this MCP server, you need a LinkedIn Developer App. Here's how:

### 1. Create the app

Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) and click **Create app**.

You'll need:
- **App name** — e.g. "My LinkedIn MCP"
- **LinkedIn Page** — link to any LinkedIn company page you admin (or create one)
- **App logo** — a square PNG image (minimum 100x100px)
- **Privacy policy URL** — a URL to your privacy policy (you can host one via GitHub Pages — see below)

### 2. Enable the required products

On your app's **Products** tab, request access to:
- **Sign in with LinkedIn using OpenID Connect** — grants `openid`, `profile`, `email` scopes
- **Share on LinkedIn** — grants `w_member_social` scope

Both are self-serve and activate immediately.

### 3. Configure the redirect URL

On the **Auth** tab:
1. Copy your **Client ID** and **Client Secret**
2. Under **Authorized redirect URLs for your app**, add: `http://localhost:8585/callback`

### 4. Privacy policy (if you need one)

If you don't have a privacy policy URL, you can use GitHub Pages:

1. Fork this repository
2. Go to your fork's **Settings > Pages**
3. Set source to **Deploy from a branch**, branch `main`, folder `/docs`
4. Your privacy policy will be at: `https://yourusername.github.io/linkedin-mcp/privacy-policy`

A template privacy policy is included at [`docs/privacy-policy.md`](docs/privacy-policy.md).

## Installation

### Requirements

- Python 3.10+
- A configured LinkedIn Developer App (see above)

### Install

```bash
git clone https://github.com/anubisalpha/linkedin-mcp.git
cd linkedin-mcp
pip install -e .
```

## Configuration

### Claude Code

Add to your project `.mcp.json` or `~/.claude/.mcp.json` (global):

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "python",
      "args": ["-m", "linkedin_mcp.server"],
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret"
      }
    }
  }
}
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "python",
      "args": ["-m", "linkedin_mcp.server"],
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret"
      }
    }
  }
}
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `LINKEDIN_CLIENT_ID` | Yes | Your LinkedIn app's Client ID |
| `LINKEDIN_CLIENT_SECRET` | Yes | Your LinkedIn app's Client Secret |
| `LINKEDIN_MCP_TOKEN_PATH` | No | Custom path for token storage (default: `~/.linkedin-mcp/tokens.json`) |

## Usage

### First-time login

Ask Claude to log you in:

> "Log in to my LinkedIn account"

This opens your browser for LinkedIn's OAuth consent page. After authorizing, the token is stored locally and lasts 60 days.

### Posting content

> "Write a LinkedIn post about the project I just shipped and publish it"

Claude will draft the post and show you the exact content before publishing. You approve or reject via the standard tool approval prompt.

### Sharing an article

> "Share this article on LinkedIn with a short commentary: https://example.com/article"

### Posting with an image

> "Create a LinkedIn post about our team event and attach the photo at /path/to/image.jpg"

## How it works

1. **Authentication**: Standard OAuth 2.0 Authorization Code Flow. Your browser handles the LinkedIn login — credentials never pass through the MCP server.
2. **Token storage**: Access tokens are saved locally at `~/.linkedin-mcp/tokens.json`. Tokens expire after 60 days.
3. **Human-in-the-loop**: Every write action (post, delete) requires explicit user approval in your MCP client before the API call is made.
4. **API scope**: Uses only `openid`, `profile`, `email`, and `w_member_social` — the minimum required for profile reading and content posting.

## ToS compliance

This server is designed to comply with LinkedIn's [User Agreement](https://www.linkedin.com/legal/user-agreement) and [API Terms of Use](https://www.linkedin.com/legal/l/api-terms-of-use):

- Uses only the **official API** — no scraping, crawling, or browser automation
- **No automated posting** — every publish action requires human approval
- **Minimal data access** — only requests the scopes needed
- **No data storage beyond tokens** — profile data is fetched on demand, not cached
- **No mass messaging** — the server publishes individual posts, not bulk content

## Rate limits

- **150 posts per day** per member
- **100,000 API calls per day** per application

## Architecture

See [docs/architecture.md](docs/architecture.md) for implementation details, design decisions, and API reference.

## License

MIT
