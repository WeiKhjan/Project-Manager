# Project Manager Main Agent

A **Project Manager (Team Lead)** agent for Malaysian accounting and audit firms, built on Claude Code. Orchestrates three specialist sub-agents — **Audit**, **Tax**, and **Compilation** — from a single entry point.

## Architecture

```
You (human)
  │
  ▼
PM Agent (Team Lead)
  ├── Spawns Audit Teammate    → own CLAUDE.md + /awp, /fs, /viewer skills
  ├── Spawns Tax Teammate      → own CLAUDE.md + /tax-computation, /capital-allowance skills
  └── Spawns Compilation Teammate → own CLAUDE.md + /fs, /mpers-fs skills
```

The PM agent uses Claude Code's **Agent Teams** (experimental) to spawn teammates that each run in their own project directory with their own CLAUDE.md and skills. Teammates can communicate peer-to-peer.

## Prerequisites

### 1. Enable Agent Teams

Add to your global Claude Code settings (`~/.claude/settings.json`):

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### 2. Sub-Agent Projects

The PM expects three sub-agent projects at these locations:

| Agent | Project Directory |
|-------|------------------|
| Audit | `C:\Users\khjan\Downloads\Pilot - Audit - Claude` |
| Tax | `C:\Users\khjan\Downloads\Pilot - TAX- Calude` |
| Compilation | `C:\Users\khjan\Downloads\Pilot - MPERS Compilation - Stand Alone - Claude` |

> Update paths in `CLAUDE.md` and `tools/pm_engine.py` if your projects are in different locations.

### 3. Python Dependencies

```bash
pip install openpyxl google-auth-oauthlib google-api-python-client
```

### 4. Gmail API (Optional)

For email functionality:
1. Create a Google Cloud project and enable Gmail API
2. Download OAuth `credentials.json` to `.claude/gmail/`
3. Run: `python .claude/skills/email-client/scripts/gmail_auth.py`

## Skills

| Command | Description |
|---------|-------------|
| `/new-engagement` | Register a new client and define services (audit/tax/compilation) |
| `/engagement-status` | View progress across all services for one or all clients |
| `/consolidated-pbc` | Merge PBC checklists from audit/tax/compilation, deduplicate |
| `/consolidated-queries` | Merge outstanding query lists across services |
| `/client-summary` | Generate professional client communication memo |
| `/delegate [agent] [task]` | Spawn specialist teammate with own CLAUDE.md + skills |
| `/pm-viewer` | Generate/update the interactive HTML dashboard |
| `/email-client` | Send client emails via Gmail API |
| `/excel-export` | Export PBC/status to Excel workbooks |
| `/skill-creation` | Guide for creating new PM skills |

## Dashboard

Interactive HTML dashboard on **port 8100**:

```bash
python server.py
# or
START_DASHBOARD.bat
```

Features: Portfolio KPI cards, client status grid, consolidated PBC tracker, query tracker, deadline timeline.

## Project Structure

```
├── CLAUDE.md                    # PM agent identity & orchestration rules
├── .claude/
│   ├── settings.local.json      # Permissions
│   ├── launch.json              # Dashboard server config (port 8100)
│   ├── gmail/                   # Gmail OAuth credentials (gitignored)
│   └── skills/                  # 10 skills
├── tools/
│   ├── pm_engine.py             # Engagement CRUD
│   ├── pbc_consolidator.py      # PBC merging & deduplication
│   └── status_reader.py         # Sub-agent folder probing
├── Clients/                     # Engagement tracking (gitignored)
├── pm_viewer.html               # Interactive dashboard
├── server.py                    # Dashboard API server
├── START_DASHBOARD.bat          # Windows launcher
└── memory/MEMORY.md             # Persistent AI memory
```

## Usage

```bash
cd "Pilot - Project Manager Main Agent"
claude

# Register a client
> /new-engagement

# Delegate work (Agent Teams spawns teammates with own CLAUDE.md)
> /delegate all Set up engagement and generate PBC for ABC Trading

# Consolidate and communicate
> /consolidated-pbc ABC Trading
> /client-summary ABC Trading
> /email-client ABC Trading
```

## Fallback (Without Agent Teams)

If Agent Teams is not available, the PM still works as a **coordination hub**:
- Use PM for: engagement tracking, PBC consolidation, client summaries, dashboard
- `cd` to each sub-agent project directly for specialist execution

## License

Private — client data is confidential and gitignored.
