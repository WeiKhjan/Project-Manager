---
name: excel-export
description: Export consolidated PBC checklists and engagement status reports to professionally formatted Excel workbooks
argument-hint: "[client name] [type: pbc|status|all]"
---

# Excel Export

Generate Excel (.xlsx) workbooks for consolidated PBC checklists and/or engagement status reports. Output is saved to the client's `output/` folder.

## Usage

```
/excel-export ABC Trading Sdn Bhd pbc       # PBC workbook only
/excel-export ABC Trading Sdn Bhd status    # Status report only
/excel-export ABC Trading Sdn Bhd all       # Both workbooks
```

## Workflow

### Step 1: Load Engagement Data

```python
import sys
sys.path.insert(0, r"C:\Users\khjan\Downloads\Pilot - Project Manager Main Agent")
from tools.pm_engine import PMEngine
from tools.pbc_consolidator import PBCConsolidator

engine = PMEngine()
engagement = engine.load_engagement(client_name)
```

### Step 2: Generate PBC Excel (if type is `pbc` or `all`)

```python
import os
from scripts.create_consolidated_pbc import create_consolidated_pbc

consolidator = PBCConsolidator(engagement)
items, stats = consolidator.consolidate()

output_dir = os.path.join(engine.clients_dir, client_name, 'output')
os.makedirs(output_dir, exist_ok=True)

company = engagement['client']['legal_name']
output_path = os.path.join(output_dir, f"{company}_PBC_Consolidated.xlsx")
create_consolidated_pbc(client_name, items, stats, output_path)
```

This generates a multi-sheet workbook:
- **Summary** — totals, by-service breakdown, by-category breakdown
- **All Items** — full PBC list with colour-coded status (green/yellow/red)
- **Audit PBC** — filtered to audit-only items
- **Tax PBC** — filtered to tax-only items
- **Compilation PBC** — filtered to compilation-only items

### Step 3: Generate Status Report Excel (if type is `status` or `all`)

```python
from tools.status_reader import StatusReader
from scripts.create_status_report import create_status_report

reader = StatusReader()

# Build engagements list with full probed data
engagements = []
for eng_summary in engine.list_engagements():
    eng_data = engine.load_engagement(eng_summary['folder'])
    probe = reader.probe_all_services(eng_data)
    eng_data['_probe'] = probe
    engagements.append(eng_data)

output_path = os.path.join(output_dir, f"{company}_Status_Report.xlsx")
create_status_report(engagements, output_path)
```

This generates a multi-sheet workbook:
- **Portfolio Summary** — all clients with per-service progress, PBC outstanding, queries open, next deadline
- **Per-Client Detail** sheets — one sheet per client with service progress, outstanding PBC items, open queries, and deadlines

### Step 4: Confirm Output

Report the saved file path(s) to the user and log the export:

```python
engine.add_status_log(client_name, f"Excel export generated: {output_path}")
```

## Style Conventions

Both scripts share the same formatting conventions to match the firm's brand:
- **Header row**: Arial 11pt bold, white text on dark blue fill (#1F4E79)
- **Data rows**: Arial 10pt with thin borders on all cells
- **Status colour coding**: Green (#C6EFCE) = Received, Yellow (#FFEB9C) = Pending, Red (#FFC7CE) = Outstanding
- **Progress colour coding**: Green (>75%), Yellow (25-75%), Red (<25%)
- Freeze top row, auto-filter enabled, approximate column widths set

## Dependencies

- `openpyxl` (install with `pip install openpyxl` if not present)

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/create_consolidated_pbc.py` | Multi-sheet PBC workbook with summary, all items, and per-service filtered sheets |
| `scripts/create_status_report.py` | Portfolio status report with summary and per-client detail sheets |

## Notes

- Run `/consolidated-pbc` first to ensure PBC data is up to date before exporting
- Run `/engagement-status` first to refresh progress data before generating status reports
- Output files are saved to `Clients/[Company]/output/` and are gitignored
