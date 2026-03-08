---
name: pm-viewer
description: Generate and update the Project Manager interactive dashboard (pm_viewer.html, server.py, START_DASHBOARD.bat) for portfolio-level monitoring of all client engagements across Audit, Tax, and Compilation services.
---

# PM Viewer — Interactive Dashboard Generator

## Purpose

Generate and maintain the Project Manager dashboard — a single-page HTML application backed by a lightweight Python HTTP server. The dashboard provides a portfolio-level view of all client engagements, consolidated PBC tracking, query monitoring, and deadline management.

## Files Generated

| File | Location | Description |
|------|----------|-------------|
| `pm_viewer.html` | Project root | Single-file HTML dashboard with embedded CSS and JavaScript |
| `server.py` | Project root | Python HTTP server (stdlib only) serving the dashboard and API endpoints |
| `START_DASHBOARD.bat` | Project root | Windows batch launcher — starts server and opens browser |

## Dashboard Features

### Portfolio Overview (Default View)
- **KPI Cards** — Total Clients, PBC Outstanding, Open Queries, Upcoming Deadlines
- **Client Card Grid** — Responsive grid with traffic-light status borders, service pills, progress bars
- **Upcoming Deadlines** — Sorted list with days-remaining countdown

### Client Detail View (Click a Client Card)
- Client header with company info (legal name, reg no, FYE, contact)
- Per-service panels (Audit / Tax / Compilation) with status badge, progress bar, stage label
- Consolidated PBC table — sortable, filterable (All / Outstanding / Received), color-coded
- Query list — PM Ref, Service, Description, Amount, Status, Date Raised
- Deadlines section

### Navigation
- Left panel (dark nav, #1e293b) with client list, search filter, service type filter
- "Refresh All" button to re-scan all sub-agent folders
- Auto-refresh every 60 seconds

## Server Configuration

- **Port:** 8100
- **Dependencies:** Python stdlib only (`http.server`, `json`, `os`)
- **Imports:** `tools.pm_engine.PMEngine`, `tools.status_reader.StatusReader`

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve pm_viewer.html |
| GET | `/api/engagements` | List all engagements (summary) |
| GET | `/api/engagement/<client>` | Full engagement data for one client |
| GET | `/api/pbc/<client>` | Parse pbc_consolidated.md and return as JSON |
| GET | `/api/queries/<client>` | Parse queries_consolidated.md and return as JSON |
| GET | `/api/status/<client>` | Live probe sub-agent folders via StatusReader |
| GET | `/api/dashboard` | Aggregated dashboard data (all clients + KPIs) |
| POST | `/api/refresh` | Re-scan all sub-agent folders, update engagement.json files |

## Workflow

1. User runs `/pm-viewer` or `START_DASHBOARD.bat`
2. Server starts on port 8100
3. Browser opens to `http://localhost:8100`
4. Dashboard loads data via fetch calls to `/api/dashboard`
5. User browses portfolio, clicks into client details
6. "Refresh All" triggers `/api/refresh` to re-probe sub-agent folders

## Regeneration Triggers

Regenerate the dashboard files when:
- A new client engagement is created (`/new-engagement`)
- PBC status is updated (`/consolidated-pbc`)
- Service status changes (progress updates from sub-agents)
- Query list is updated (`/consolidated-queries`)
- Dashboard layout or feature changes are requested

## Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| Nav Background | #1e293b | Left navigation panel |
| Nav Text | #94a3b8 | Inactive nav items |
| Nav Active | #f8fafc | Active/hover nav items |
| Primary (Blue) | #3b82f6 | Audit service, primary actions |
| Success (Green) | #22c55e | Received status, good progress |
| Warning (Amber) | #f59e0b | Pending status, medium progress |
| Danger (Red) | #ef4444 | Outstanding status, low progress |
| Info (Teal) | #06b6d4 | Deadlines, info badges |
| Compilation Purple | #8b5cf6 | Compilation service pills |
| Card Background | #ffffff | Content cards |
| Card Border | #e2e8f0 | Card outlines |
| Body Background | #f1f5f9 | Main content area |
