---
name: engagement-status
description: View progress and status across all services for one or all clients
argument-hint: "[client name] or leave blank for all clients"
---

# Engagement Status

Check the current progress of engagements by probing sub-agent project folders.

## Usage

```
/engagement-status                    # Show all clients
/engagement-status ABC Trading        # Show specific client
```

## Workflow

### Step 1: Load Engagement(s)

```python
import sys
sys.path.insert(0, r"C:\Users\khjan\Downloads\Pilot - Project Manager Main Agent")
from tools.pm_engine import PMEngine
from tools.status_reader import StatusReader

engine = PMEngine()
reader = StatusReader()
```

If a specific client name is provided, load that engagement. Otherwise, list all engagements.

### Step 2: Probe Sub-Agent Folders

For each client's enabled services, use the StatusReader to probe the sub-agent's folder:

```python
# Get the full path to the sub-agent's client folder
folder = engine.get_sub_agent_folder(client_name, service)

# Probe based on service type
if service == 'audit':
    status = reader.probe_audit_status(folder)
elif service == 'tax':
    status = reader.probe_tax_status(folder)
elif service == 'compilation':
    status = reader.probe_compilation_status(folder)
```

Or use the all-in-one method:
```python
engagement = engine.load_engagement(client_name)
all_status = reader.probe_all_services(engagement)
```

### Step 3: Update engagement.json

Update the progress and status in engagement.json based on probe results:

```python
engine.update_service_status(
    client_name,
    service,
    status['stage'],
    status['estimated_progress']
)
```

### Step 4: Display Status Report

**For a single client, show:**

```
## [Company Name] — Engagement Status
Updated: [timestamp]

### Services Overview
| Service | Status | Progress | Deadline | Notes |
|---------|--------|----------|----------|-------|
| Audit   | Fieldwork | ████████░░ 60% | 30 Jun 2025 | Sections A-D complete |
| Tax     | PBC Pending | ██░░░░░░░░ 10% | 31 Jul 2025 | Awaiting audited FS |
| Compilation | Not Started | ░░░░░░░░░░ 0% | — | — |

### Outstanding Items
- PBC: 19 items outstanding (consolidated)
- Queries: 3 open queries

### Recent Activity (last 7 days)
- [date] Tax: PBC_01_Document_Checklist.md created
- [date] Audit: A_01_Engagement_Letter.md updated

### Upcoming Deadlines
- 31 Jul 2025: Form C Filing (Tax) — 145 days remaining
- 30 Jun 2025: Audit Report (Audit) — 114 days remaining
```

**For all clients, show:**

```
## Portfolio Status Overview
Updated: [timestamp]

| Client | Audit | Tax | Compilation | PBC Outstanding | Queries Open | Next Deadline |
|--------|-------|-----|-------------|-----------------|--------------|---------------|
| ABC Trading | 60% ● | 10% ◐ | 0% ○ | 19 | 3 | 30 Jun 2025 |
| JATI KIRANA | — | 80% ● | — | 2 | 0 | 31 Jul 2025 |
```

Legend: ● In Progress | ◐ Pending | ○ Not Started | ✓ Complete

### Step 5: Log Status Update

```python
engine.add_status_log(client_name, f"Status check: Audit {progress}%, Tax {progress}%, Compilation {progress}%")
```

## Progress Heuristics

### Audit Agent
| Sections Found | Progress | Stage |
|---------------|----------|-------|
| Folder exists, empty | 5% | not_started |
| Section A | 15% | planning |
| Section B | 25% | planning |
| Sections C+D | 60% | fieldwork |
| Section E | 75% | fieldwork |
| Section F | 90% | completion |
| Section G + viewer | 100% | done |

### Tax Agent
| Folders Found | Progress | Stage |
|--------------|----------|-------|
| Folder exists, no subfolders | 5% | not_started |
| 01_TAX_COMPUTATION has files | 30% | in_progress |
| 02+03 exist | 60% | in_progress |
| 04-06 exist | 80% | in_progress |
| 07_PBC resolved | 90% | review |
| Viewer generated | 100% | done |

### Compilation Agent
| State | Progress | Stage |
|-------|----------|-------|
| Folder exists, empty | 5% | not_started |
| source/ has files | 10% | data_received |
| create_*_fs.py exists | 40% | in_progress |
| output/ has .docx | 90% | generated |
| Reviewed | 100% | done |
