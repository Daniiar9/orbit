# Orbit

Relationship timing intelligence for founders, consultants, and senior operators who sell through relationships. Know when to show up. Know what to bring. Never pitch first.

Orbit is built for:
- Founders running relationship-led sales
- Consultants and agency owners managing high-value accounts
- Senior AEs and enterprise reps with strategic account lists
- Operators who maintain networks for years, not quarters

Not for: SDR teams, bulk outreach, or anyone who measures success in email volume.

## Philosophy

- **No action without signal.** Every recommendation cites a specific, observable event. No time-based follow-ups. No "it's been 2 weeks, reach out."
- **No automated messages.** Orbit never sends anything on your behalf. It surfaces opportunities. You decide what to do.
- **No bulk anything.** MAX_PROSPECTS = 40 by design. This is a relationship tool, not a pipeline spray tool.
- **Only publicly visible signals.** Orbit only acts on posts, comments, public company news, and job postings. If a prospect would feel "watched" rather than "engaged," the recommendation is blocked.
- **Evidence-based recommendations only.** Every suggestion cites specific signals with dates. No generic networking advice. No AI-generated warmth.

## What Orbit is not

Orbit is not an AI SDR.
It is not a sequencing tool.
It is not a personalization engine.
It does not send messages on your behalf.
It does not manufacture urgency.
It does not fake relationship strength.

Orbit is relationship intelligence with behavioral restraint.
It helps you act with better judgment, not higher volume.

## Installation

```bash
git clone https://github.com/your-username/orbit.git
cd orbit
uv pip install -e .
```

## LinkedIn Setup

Orbit uses Patchright to read public LinkedIn activity. You must log in once to save your session:

```bash
orbit-login
```

A browser window will open. Log in to LinkedIn manually. Once you see your feed, return to the terminal and press Enter. Your session is saved locally and reused for headless scraping.

If LinkedIn blocks a session, just run `orbit-login` again.

## Configuration

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for the intelligence layer |
| `EXA_API_KEY` | Yes | — | Exa API key for web signal search |
| `LINKEDIN_SESSION_PATH` | No | `~/.orbit/linkedin_session` | Path to saved LinkedIn session |
| `DATABASE_PATH` | No | `~/.orbit/orbit.db` | SQLite database location |
| `MAX_PROSPECTS` | No | `40` | Maximum active prospects |
| `SCAN_RATE_LIMIT` | No | `5` | LinkedIn requests per minute |
| `LOG_LEVEL` | No | `INFO` | Logging level |

The server will fail to start if `OPENAI_API_KEY` or `EXA_API_KEY` are missing. Missing LinkedIn session produces a warning but doesn't block startup — Exa-only signals still work.

## Claude Desktop / Claude Code Configuration

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "orbit": {
      "command": "orbit",
      "env": {
        "OPENAI_API_KEY": "your_key_here",
        "EXA_API_KEY": "your_key_here"
      }
    }
  }
}
```

Or for Claude Code, add to your MCP settings:

```json
{
  "mcpServers": {
    "orbit": {
      "command": "orbit",
      "env": {
        "OPENAI_API_KEY": "your_key_here",
        "EXA_API_KEY": "your_key_here"
      }
    }
  }
}
```

## Available Tools

### Prospect Management

| Tool | Description | Read/Write |
|---|---|---|
| `orbit_add_prospect` | Add a prospect with LinkedIn URL and context | Write |
| `orbit_remove_prospect` | Archive a prospect (keeps history) | Write |
| `orbit_update_context` | Update why someone is on your list | Write |
| `orbit_import_csv` | Import from Sales Navigator CSV export | Write |

### Signal Tools

| Tool | Description | Read/Write |
|---|---|---|
| `orbit_get_signals` | Get recent signals for a prospect | Read |
| `orbit_get_opportunities` | What should I do today? | Read |
| `orbit_scan_prospect` | Force a fresh signal scan for one prospect | Write |
| `orbit_scan_all` | Scan all active prospects (rate-limited) | Write |

### Engagement Tracking

| Tool | Description | Read/Write |
|---|---|---|
| `orbit_log_engagement` | Log what you did and their response | Write |
| `orbit_get_engagement_history` | Full log of touches and responses | Read |

### Intelligence Tools

| Tool | Description | Read/Write |
|---|---|---|
| `orbit_get_value_ideas` | What can you share that's genuinely useful? | Read |
| `orbit_get_intro_angle` | Natural intro angle (blocked unless state = ready) | Read |
| `orbit_get_relationship` | Full relationship summary | Read |

### Overview

| Tool | Description | Read/Write |
|---|---|---|
| `orbit_get_overview` | Full active list grouped by state | Read |
| `orbit_get_stats` | Dashboard stats | Read |

## Example Workflows

### "I have a Sales Navigator list, how do I start?"

```
Use orbit_import_csv with the path to your CSV export.
Orbit scans each prospect, ranks them by signal density,
and tells you which ones are worth adding and which to skip.
```

### "What should I do today?"

```
Use orbit_get_opportunities.
Returns prospects with actionable signals right now,
grouped by action type: engage, share, or intro.
If nothing is actionable, it says so. No busywork.
```

### "I commented on someone's post, now what?"

```
Use orbit_log_engagement with type="commented" and a description.
Orbit updates the relationship state, records the interaction,
and tells you what to do next based on their response (or lack of one).
```

### "A prospect replied to my message"

```
Use orbit_log_engagement with type="received_reply",
include their response text, and set response_depth
(shallow / moderate / deep). This is what moves the
relationship state forward.
```

### "Is this prospect worth keeping?"

```
Use orbit_get_relationship. Check signal_density.
Below 3? Orbit recommends removal — there's not enough
observable signal to engage meaningfully.
```

## Anti-Creepiness Commitment

Orbit only uses publicly visible information. Period.

What this means in practice:
- Recommendations are based on posts, comments, public company news, and job postings
- Orbit never references profile view timestamps, exact timing of likes, invisible observation behavior, or deep historical scraping
- If a recommendation would make the prospect feel "watched" rather than "engaged," it is blocked
- The intelligence layer is explicitly instructed to never suggest actions that reveal invisible monitoring

This isn't just a feature — it's a core product principle. If you're building on top of Orbit, this rule is non-negotiable. See CONTRIBUTING.md for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
 
