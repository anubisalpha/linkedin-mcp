# LinkedIn MCP Server — Setup Guide

This guide walks you through everything from scratch. No prior experience with MCP servers, APIs, or command-line tools is needed.

By the end you'll be able to ask Claude to write and publish LinkedIn posts for you — with your approval on every post before it goes live.

---

## What you'll need

- **Claude Code** (the CLI, desktop app, or web app at claude.ai/code)
- **Python 3.10 or newer** installed on your computer
- **A LinkedIn account** (personal — the one you want to post from)
- About **15 minutes** for the initial setup

---

## Step 1 — Install Python (if you don't have it)

Check if Python is already installed by opening a terminal and typing:

```
python --version
```

If you see `Python 3.10` or higher, you're good — skip to Step 2.

**If not installed:**

- **Windows**: Download from [python.org/downloads](https://www.python.org/downloads/). During installation, **tick the box that says "Add Python to PATH"** — this is important.
- **Mac**: Run `brew install python` if you have Homebrew, or download from [python.org/downloads](https://www.python.org/downloads/).
- **Linux**: Run `sudo apt install python3 python3-pip` (Ubuntu/Debian) or `sudo dnf install python3` (Fedora).

---

## Step 2 — Download and install the LinkedIn MCP server

Open a terminal and run these three commands one at a time:

```
git clone https://github.com/anubisalpha/linkedin-mcp.git
cd linkedin-mcp
pip install -e .
```

**Don't have git?** You can download the code as a ZIP instead:
1. Go to [github.com/anubisalpha/linkedin-mcp](https://github.com/anubisalpha/linkedin-mcp)
2. Click the green **Code** button, then **Download ZIP**
3. Extract the ZIP to a folder you'll remember (e.g. `Documents/linkedin-mcp`)
4. Open a terminal in that folder and run: `pip install -e .`

---

## Step 3 — Create a LinkedIn Developer App

This is the most involved step, but it's all done through LinkedIn's website — no coding required.

### 3a. Go to LinkedIn's Developer Portal

Open [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) and sign in with your LinkedIn account.

### 3b. Create a new app

Click **Create app** and fill in:

| Field | What to enter |
|---|---|
| **App name** | Anything you like, e.g. "My LinkedIn MCP" |
| **LinkedIn Page** | Select a LinkedIn company/organisation page you manage. If you don't have one, you'll need to [create a LinkedIn Page](https://www.linkedin.com/company/setup/new/) first — it can be a simple page just for this purpose. |
| **App logo** | Any square image (minimum 100x100 pixels). A simple coloured square works fine. |
| **Privacy policy URL** | See the note below. |

**Privacy policy:** LinkedIn requires a URL. The easiest option is to use the one included with this project:

1. Fork the repository on GitHub (click **Fork** at [github.com/anubisalpha/linkedin-mcp](https://github.com/anubisalpha/linkedin-mcp))
2. In your fork, go to **Settings > Pages**
3. Under "Build and deployment", set source to **Deploy from a branch**, branch `main`, folder `/docs`
4. After a minute or two, your privacy policy will be live at: `https://YOUR-USERNAME.github.io/linkedin-mcp/privacy-policy`
5. Use that URL in the LinkedIn app form

### 3c. Enable the required products

Once your app is created, go to the **Products** tab and request access to these two products:

1. **Sign in with LinkedIn using OpenID Connect**
2. **Share on LinkedIn**

Both activate immediately — no approval wait.

### 3d. Set up the redirect URL

Go to the **Auth** tab of your app:

1. Scroll down to **Authorized redirect URLs for your app**
2. Click **Add redirect URL**
3. Enter exactly: `http://localhost:8585/callback`
4. Click **Update**

### 3e. Copy your credentials

While still on the **Auth** tab:

1. Copy your **Client ID** (a string like `78jgxxvnamackh`)
2. Click the eye icon next to **Client Secret** and copy that too

**Keep these safe** — you'll need them in the next step.

---

## Step 4 — Connect the server to Claude Code

You need to tell Claude Code where to find the LinkedIn MCP server and your credentials.

### Find the right config file

The file is called `.mcp.json`. Where it lives depends on your setup:

- **Project-level** (recommended): Create `.mcp.json` in the folder where you run Claude Code
- **Global** (works everywhere): Create it at `~/.claude/.mcp.json`
  - **Windows**: `C:\Users\YOUR_NAME\.claude\.mcp.json`
  - **Mac/Linux**: `~/.claude/.mcp.json`

### Add this to the file

If the file doesn't exist yet, create it. If it already exists and has other MCP servers configured, add the `"linkedin"` section inside the existing `"mcpServers"` block.

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "python",
      "args": ["-m", "linkedin_mcp.server"],
      "env": {
        "LINKEDIN_CLIENT_ID": "paste_your_client_id_here",
        "LINKEDIN_CLIENT_SECRET": "paste_your_client_secret_here"
      }
    }
  }
}
```

**Replace** `paste_your_client_id_here` and `paste_your_client_secret_here` with the actual values you copied from LinkedIn. Keep the quote marks.

> **Important:** Use the actual values, not variable references like `${LINKEDIN_CLIENT_ID}`. The literal strings must be in the file.

### Restart Claude Code

Close and reopen Claude Code (or restart the CLI) so it picks up the new configuration.

---

## Step 5 — First-time login

Open Claude Code and paste this prompt:

```
Run linkedin_setup to check my configuration, then help me log in to LinkedIn.
```

Claude will:
1. Check that your credentials are configured correctly
2. Flag anything that's missing or misconfigured
3. Walk you through the OAuth login (opening your browser to LinkedIn's sign-in page)
4. Confirm everything is working

After you authorise in your browser, the token is stored locally on your machine and lasts 60 days.

---

## You're done!

From now on, you can ask Claude things like:

- *"Write a LinkedIn post about [topic] and publish it"*
- *"Share this article on LinkedIn: [URL]"*
- *"Create a poll asking my network about [question]"*
- *"Upload this PDF to LinkedIn with a summary: [file path]"*
- *"Check my LinkedIn posting history"*
- *"Run a health check on my LinkedIn connection"*

Claude will always show you a preview of the exact content before publishing. Nothing goes live without your explicit approval.

---

## Troubleshooting

### "LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables are required"

Your `.mcp.json` file isn't being found, or the credentials aren't set correctly. Check:
- The file is saved in the right location
- The JSON is valid (no missing commas or brackets)
- You used the actual credential strings, not `${VAR}` references
- You restarted Claude Code after editing the file

### "Token rejected by LinkedIn (401 Unauthorized)"

Your token has expired (they last 60 days). Ask Claude: *"Log me back in to LinkedIn"*

### "Missing required scope(s)"

You need to enable both products on your LinkedIn Developer App:
1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Select your app, go to the **Products** tab
3. Make sure both **Sign in with LinkedIn using OpenID Connect** and **Share on LinkedIn** are enabled

### The OAuth login page won't load

Check that the redirect URL is set correctly:
1. Go to your app's **Auth** tab on LinkedIn
2. Make sure `http://localhost:8585/callback` is listed under redirect URLs
3. Make sure no other application is using port 8585

### "Error: File not found" when posting a document

Use the full absolute path to the file, e.g.:
- Windows: `C:\Users\YourName\Documents\report.pdf`
- Mac/Linux: `/Users/yourname/Documents/report.pdf`

---

## Quick reference — what Claude can do

| Ask Claude to... | What happens |
|---|---|
| Write and publish a post | Drafts text, shows preview, publishes after your OK |
| Share an article/URL | Fetches link preview, creates article post |
| Create a poll | Sets up poll with your question and options |
| Upload a document | Uploads PDF/PPTX/DOCX to LinkedIn as a document post |
| Post with an image | Uploads image and creates post |
| Check status | Shows auth status, token expiry, health |
| View history | Shows all your published posts |
| Undo last post | Deletes the most recently published post |
| Delete a post | Removes a specific post by URN |
