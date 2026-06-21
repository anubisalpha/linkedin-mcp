# LinkedIn MCP Server

A **ToS-compliant** [Model Context Protocol](https://modelcontextprotocol.io/) server for LinkedIn, using only the official LinkedIn API.

Unlike other LinkedIn MCP servers that rely on scraping (which violates LinkedIn's User Agreement and risks account bans), this server uses LinkedIn's official Consumer API with proper OAuth 2.0 authentication.

## Features

| Tool | Description |
|---|---|
| `linkedin_login` | OAuth 2.0 sign-in — opens your browser for secure authorization |
| `linkedin_logout` | Clear stored authentication tokens |
| `linkedin_status` | Check auth status and token info |
| `linkedin_profile` | Get your name, email, photo, and locale |
| `linkedin_create_text_post` | Publish a text post (public or connections-only) |
| `linkedin_create_article_post` | Share a URL/article with commentary |
| `linkedin_create_image_post` | Upload an image and publish with text |
| `linkedin_delete_post` | Delete a post by its URN |

All write operations require explicit user approval before executing, keeping the integration compliant with LinkedIn's API Terms of Use (no automated posting).

## Prerequisites

1. **Python 3.10+**
2. A **LinkedIn Developer App** — create one at [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
3. Enable these products on your app (under the Products tab):
   - **Sign in with LinkedIn using OpenID Connect**
   - **Share on LinkedIn**
4. Add `http://localhost:8585/callback` as an **Authorized redirect URL** (under the Auth tab)
5. Note your **Client ID** and **Client Secret** from the Auth tab

## Installation

```bash
# Clone the repository
git clone https://github.com/anubisalpha/linkedin-mcp.git
cd linkedin-mcp

# Install dependencies
pip install -e .
```

## Configuration

### Claude Code

Add to your `.mcp.json` (or `~/.claude/.mcp.json` for global):

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

### Environment Variables

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

## ToS Compliance

This server is designed to comply with LinkedIn's [User Agreement](https://www.linkedin.com/legal/user-agreement) and [API Terms of Use](https://www.linkedin.com/legal/l/api-terms-of-use):

- Uses only the **official API** — no scraping, crawling, or browser automation
- **No automated posting** — every publish action requires human approval
- **Minimal data access** — only requests the scopes needed
- **No data storage beyond tokens** — profile data is fetched on demand, not cached
- **No mass messaging** — the server publishes individual posts, not bulk content

## Rate Limits

- **150 posts per day** per member
- **100,000 API calls per day** per application

## License

MIT
