# LinkedIn MCP Server — One-Click Setup Prompt

Copy the prompt below and paste it into Claude Code. Claude will handle the installation, configuration, and login for you.

The only thing you need to do beforehand is **create a LinkedIn Developer App** to get your Client ID and Client Secret. Claude will walk you through that if you haven't done it yet.

---

## The prompt

Copy everything inside the box below and paste it into Claude Code:

````
I want to set up the LinkedIn MCP server so I can publish LinkedIn posts through you. Please do the full setup for me — I'll just approve the steps as you go.

Here's what needs to happen:

1. Clone the repo from https://github.com/anubisalpha/linkedin-mcp.git (skip if already cloned)
2. Install it with pip install -e .
3. Ask me for my LinkedIn Client ID and Client Secret. If I don't have them yet, explain exactly how to create a LinkedIn Developer App and get them — keep it brief, tell me the exact pages to visit and buttons to click:
   - Create app at https://www.linkedin.com/developers/apps
   - Enable "Sign in with LinkedIn using OpenID Connect" and "Share on LinkedIn" on the Products tab
   - Add http://localhost:8585/callback as a redirect URL on the Auth tab
   - Copy Client ID and Client Secret from the Auth tab
4. Once I give you the credentials, write them into my .mcp.json (create the file if it doesn't exist, merge with existing config if it does). Use the literal credential values in the env block, not ${VAR} references.
5. Tell me to restart Claude Code so the MCP server loads, and that I should paste "continue linkedin setup" when I'm back.

When I say "continue linkedin setup":
6. Run the linkedin_setup tool to verify everything is configured
7. Run linkedin_login to start the OAuth flow (this will open my browser)
8. Once logged in, run linkedin_setup again to confirm everything is working
9. Show me a quick summary of what I can now do (post text, articles, polls, documents, images)

Important:
- Do each step and show me the result before moving to the next
- If anything fails, explain what went wrong and how to fix it
- Don't ask me unnecessary questions — just do it and I'll approve each step
````

---

## What happens when you paste this

1. **Claude clones and installs the server** — you click "allow" on the terminal commands
2. **Claude asks for your credentials** — you paste your LinkedIn Client ID and Client Secret (if you don't have them, Claude tells you exactly where to get them)
3. **Claude writes your config file** — you click "allow" on the file write
4. **You restart Claude Code** — close and reopen so the new MCP server loads
5. **You paste "continue linkedin setup"** — Claude runs the setup check and opens your browser for LinkedIn login
6. **You authorise in your browser** — click "Allow" on LinkedIn's consent page
7. **Done** — Claude confirms everything is working and shows you what you can do

Total user actions: ~5 clicks on "allow" + pasting credentials + one browser authorisation.
