# Project Manager Agent - Memory

## Created
- Date: 2026-03-08
- Purpose: Orchestrate audit, tax, and compilation sub-agents

## Sub-Agent Locations
- Audit: `C:\Users\khjan\Downloads\Pilot - Audit - Claude`
- Tax: `C:\Users\khjan\Downloads\Pilot - TAX- Calude`
- Compilation: `C:\Users\khjan\Downloads\Pilot - MPERS Compilation - Stand Alone - Claude`

## Sub-Agent Client Folder Patterns
- Audit: `Clients/AWP_[ClientName]_FYE[Year]/` (sections A-G)
- Tax: `Clients/[CLIENT NAME] YA [YEAR]/` (folders 01-09)
- Compilation: `Clients/[Company Legal Name]/` (source/ + output/)

## Architecture Decisions
- **Agent Teams (experimental)** for delegation — teammates have their own CLAUDE.md + skills
- PM is **Team Lead** using Delegate Mode (Shift+Tab) — never does implementation work
- Teammates spawned in sub-agent project directories — each auto-reads its own CLAUDE.md
- **Peer-to-peer messaging** between teammates (tax ↔ audit, no routing through Lead)
- Feature flag: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.json`
- **Fallback**: If Agent Teams unavailable, PM still works as coordination hub (user cd's to agents manually)
- PM reads sub-agent files directly for status checks (no teammate spawn for reads)
- engagement.json is single source of truth per client
- PBC deduplication uses DOCUMENT_ALIASES table
- All file-based (no database)
- Dashboard on port 8100, sub-agent viewers on port 8000
- Gmail API (OAuth2) for client emails

## Agent Teams Configuration
- Enabled: `~/.claude/settings.json` → `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"`
- Recommended terminal: tmux (split-pane mode to see all teammates)
- Task registry: `~/.claude/tasks/{team-name}/` (auto-managed by Agent Teams)
- Teammates are ephemeral — they terminate after task completion
- No session resume for teams — if terminal crashes, swarm is lost (filesystem changes persist)

## Completed Engagements
(none yet)

## Known Issues & Lessons Learned
- Agent Teams is experimental — may have stability issues
- Each teammate consumes its own context window and tokens (3 teammates = ~3x cost)
- Teammates don't share conversation history — quality depends on spawn prompt clarity
- Auto-memory can write incorrect summaries — verify MEMORY.md periodically
- If teammates conflict on file edits, Git-based file locking resolves it
