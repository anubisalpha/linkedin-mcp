# LinkedIn Posting Pipeline

A local web dashboard for drafting, approving, scheduling, and publishing LinkedIn posts through the MCP server.

## Setup

**Fastest way to get started:** Copy the setup prompt from **[PIPELINE_SETUP_PROMPT.md](../PIPELINE_SETUP_PROMPT.md)** and paste it into Claude Code. Claude will verify the install, start the server, and optionally configure auto-start and automated posting — you just click "allow" on each step.

> Need to do it manually instead? Follow the steps below.

### Prerequisites

- **Python 3.10+** — no additional packages required (stdlib only)
- **LinkedIn MCP server** — must be set up and authenticated if you want to publish posts (see the [main setup guide](../SETUP.md)). The pipeline works without it for drafting and scheduling, but won't be able to publish.

### Install

The pipeline lives inside the LinkedIn MCP project — no separate install needed.

```bash
cd pipeline
python server.py
```

On first run, the server creates the stage folders (`draft/`, `approved/`, `scheduled/`, `completed/`) and the `pages/` directory automatically.

Open [http://localhost:8420](http://localhost:8420) in your browser.

### Custom port

Set the `PORT` environment variable before starting:

```bash
PORT=9000 python server.py
```

### Start on login (optional)

To have the pipeline server start automatically when you log in to Windows:

```powershell
schtasks /create /tn "LinkedIn Pipeline Server" /tr "pythonw pipeline\server.py" /sc onlogon /rl limited /f
```

To remove it later:

```powershell
schtasks /delete /tn "LinkedIn Pipeline Server" /f
```

### Setting up automated posting (optional)

To have posts published automatically at their scheduled date and time, ask Claude Code to create a scheduled task:

> "Set up a LinkedIn posting check that runs every day at 9 AM"

See [Automated schedule check](#automated-schedule-check) below for schedule options and details.

### File structure

```
pipeline/
├── server.py           # API server and request handler
├── test_server.py      # Test suite (46 tests)
├── README.md
├── posting-plan.md     # Auto-generated index of all posts
├── pages/
│   ├── index.html      # Pipeline management UI (Kanban board)
│   └── schedule.html   # Schedule view with due/overdue alerts
├── draft/              # New and work-in-progress posts
├── approved/           # Reviewed, ready to schedule
├── scheduled/          # Assigned a date and time, waiting to publish
└── completed/          # Successfully posted
```

## How it works

Posts move through four stages as markdown files with YAML frontmatter:

| Stage | Folder | Description |
|---|---|---|
| **Draft** | `draft/` | New ideas, rough drafts, work in progress |
| **Approved** | `approved/` | Reviewed and ready to be scheduled |
| **Scheduled** | `scheduled/` | Assigned a post date, waiting for that day |
| **Completed** | `completed/` | Successfully posted to LinkedIn |

### Post file format

Each post is a markdown file named `YYYY-MM-DD-short-slug.md`:

```markdown
---
type: text | article | image | document | poll
target_date: 2026-06-25
target_time: 14:00
visibility: PUBLIC | CONNECTIONS
url: https://example.com        # article type only
image: /path/to/image.png       # image type only
tags: [topic1, topic2]
posted_date: 2026-06-25 14:01   # added automatically on publish
---

Post content goes here...
```

| Field | Required | Description |
|---|---|---|
| `type` | Yes | Post format: `text`, `article`, `image`, `document`, or `poll` |
| `target_date` | When scheduling | Date to publish (YYYY-MM-DD) |
| `target_time` | No | Time to publish (HH:MM, defaults to 09:00) |
| `visibility` | No | `PUBLIC` (default) or `CONNECTIONS` |
| `url` | For articles | Link URL for article-type posts |
| `image` | For images | File path for image-type posts |
| `tags` | No | Metadata tags (not added to post content) |
| `posted_date` | Auto | Added automatically when published |

### Workflow

1. **Draft** — Create a post in the web UI or as a `.md` file in `draft/`
2. **Approve** — Review the draft, then move to approved
3. **Schedule** — Set a target date and time, then schedule
4. **Post** — At the scheduled time, the post is published via the LinkedIn MCP tools
5. **Complete** — After posting, the file moves to `completed/` with a `posted_date`

Editing a post that is already approved or scheduled automatically moves it back to draft for re-approval.

### Limits

- Posts exceeding **3,000 characters** cannot be scheduled — edit them down first
- The completed column shows the **12 most recent** posts (older posts remain on disk)

The web UI provides full CRUD management through the pipeline stages, with modals for creating, editing, reviewing, and scheduling posts.

## Automated schedule check

The pipeline can automatically check for due posts and prompt you to publish them. This uses Claude Code's scheduled tasks feature.

### Setting up the schedule

Ask Claude Code to create a scheduled posting check:

> "Set up a LinkedIn posting check that runs every day at 9 AM"

Or for multiple checks per day:

> "Set up a LinkedIn posting check that runs at 9 AM and 5 PM on weekdays"

Claude will create a scheduled task using the appropriate cron expression. Common schedules:

| Schedule | Cron expression | Description |
|---|---|---|
| `0 9 * * *` | Daily at 9:00 AM | Once a day, every day |
| `0 9 * * 1-5` | Weekdays at 9:00 AM | Skip weekends |
| `0 9,17 * * *` | Daily at 9 AM and 5 PM | Twice daily |
| `0 9,13,17 * * 1-5` | Weekdays 9 AM, 1 PM, 5 PM | Three times daily, weekdays only |
| `0 */4 * * *` | Every 4 hours | Frequent checks throughout the day |

### What the scheduled task does

1. Reads all `.md` files in `scheduled/`
2. A post is **due** when its `target_date` has passed, or when `target_date` is today and the current time is at or past `target_time` (defaults to 09:00)
3. Publishes each due post automatically via the LinkedIn MCP tools, oldest first
4. Moves published posts to `completed/` with a `posted_date` timestamp

### Safeguards

| Rule | Limit |
|---|---|
| **Max posts per run** | 3 — remaining posts carry over to the next run |
| **Minimum gap between posts** | 10 seconds — prevents rapid-fire posting |
| **Over-length posts** | Cannot be scheduled (blocked at 3,000 characters) |

Scheduling a post is the approval step — by moving a post to `scheduled/` with a date and time, you've signed off on its content.

This pipeline is designed for personal posting cadence (1–2 posts per week), not mass marketing.

### Changing the schedule

> "Change my LinkedIn posting check to run at 8 AM and 6 PM"

> "Pause the LinkedIn posting check"

> "Resume the LinkedIn posting check"

### Manual check

You can also check for due posts any time without waiting for the schedule:

- **Web UI:** Open [http://localhost:8420/schedule](http://localhost:8420/schedule) to see due/overdue posts and publish with one click
- **Ask Claude:** "Check if I have any LinkedIn posts due today"

## Configuration

| Setting | Default | Description |
|---|---|---|
| `PORT` env var | `8420` | Server port — set before starting |

## Testing

```bash
cd pipeline
python -m pytest test_server.py -v
```

46 tests covering all server functions and API endpoints.

## Integration with LinkedIn MCP

The pipeline manages post content locally. When a scheduled post is due, it publishes through the LinkedIn MCP tools (`linkedin_create_text_post`, `linkedin_create_article_post`, etc.). The approval step is scheduling itself — once a post has a date and time, it will be published automatically when due.
