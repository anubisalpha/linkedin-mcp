# LinkedIn Posting Pipeline — Setup Prompt

Copy the prompt below and paste it into Claude Code. Claude will set up the posting pipeline dashboard and optionally configure it to start automatically.

**Prerequisite:** The LinkedIn MCP server should already be installed and authenticated. If not, use [SETUP_PROMPT.md](SETUP_PROMPT.md) first.

---

## The prompt

Copy everything inside the box below and paste it into Claude Code:

````
I want to set up the LinkedIn posting pipeline — the local web dashboard for drafting, scheduling, and publishing LinkedIn posts. Please do the full setup for me.

Here's what needs to happen:

1. Check that the LinkedIn MCP server is already installed. If not, tell me to run the main setup first.
2. Check that the pipeline/ directory exists in the project root with server.py and pages/. If the repo was cloned, it should already be there. If not, explain how to get it.
3. Create the stage folders if they don't exist: draft/, approved/, scheduled/, completed/
4. Start the pipeline server (python pipeline/server.py) and verify it responds on http://localhost:8420
5. Open the web UI and confirm both the Pipeline page and the Schedule page load correctly
6. Ask me: "Would you like the pipeline server to start automatically when your computer starts?"

If I say yes to auto-start:
7. Create a Windows scheduled task called "LinkedIn Pipeline Server" that:
   - Runs at user logon (not at system startup — it should run as my user)
   - Executes: pythonw pipeline/server.py (using pythonw so there's no console window)
   - Sets the working directory to the linkedin-mcp project root
   - Does NOT run with highest privileges (no admin needed)
   - Has a description: "Starts the LinkedIn posting pipeline dashboard on http://localhost:8420"
   Show me the schtasks command before running it so I can approve it.

8. Ask me: "Would you like to set up automated posting? This creates a Claude Code scheduled task that checks for due posts and publishes them at their scheduled time."

If I say yes to automated posting:
9. Set up a Claude Code scheduled task called "linkedin-posting-check" that runs daily at 9:00 AM to check for due posts and publish them automatically
10. Ask me if I'd like a different schedule (e.g. twice daily, weekdays only) and adjust if needed

Finally:
11. Run linkedin_setup to show the full status including the pipeline section
12. Show me a quick summary of the workflow: create a draft → approve → schedule with date and time → it posts automatically

Important:
- Do each step and show me the result before moving to the next
- If anything fails, explain what went wrong and how to fix it
- Don't ask me unnecessary questions — just do it and I'll approve each step
````

---

## What happens when you paste this

1. **Claude checks your installation** — verifies the MCP server and pipeline files are in place
2. **Claude creates the folders** — sets up draft/, approved/, scheduled/, completed/ if needed
3. **Claude starts the server** — launches the pipeline and verifies the web UI works
4. **Claude asks about auto-start** — if you say yes, it creates a Windows task to start the server at login (you approve the command)
5. **Claude asks about automated posting** — if you say yes, it sets up a daily scheduled task in Claude Code
6. **Claude shows the full status** — runs linkedin_setup to confirm everything is configured
7. **Done** — Claude summarises the workflow

Total user actions: ~3-4 clicks on "allow" + answering two yes/no questions.

---

## Managing the auto-start task

If you set up the Windows auto-start task, you can manage it later:

```powershell
# Check if it's running
schtasks /query /tn "LinkedIn Pipeline Server"

# Disable it
schtasks /change /tn "LinkedIn Pipeline Server" /disable

# Re-enable it
schtasks /change /tn "LinkedIn Pipeline Server" /enable

# Remove it entirely
schtasks /delete /tn "LinkedIn Pipeline Server" /f
```

Or open **Task Scheduler** (search "Task Scheduler" in the Start menu) and find it under the task library.
