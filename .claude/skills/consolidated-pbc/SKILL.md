---
name: consolidated-pbc
description: Generate a consolidated PBC document checklist merging requirements from audit, tax, and compilation services
argument-hint: "[client name]"
---

# Consolidated PBC Checklist

Merge PBC (Provided By Client) document checklists from all active services into a unified list, eliminating duplicates and showing which documents are needed by which services.

## Usage

```
/consolidated-pbc ABC Trading Sdn Bhd
```

## Workflow

### Step 1: Load Engagement

```python
import sys
sys.path.insert(0, r"C:\Users\khjan\Downloads\Pilot - Project Manager Main Agent")
from tools.pm_engine import PMEngine
from tools.pbc_consolidator import PBCConsolidator

engine = PMEngine()
engagement = engine.load_engagement(client_name)
```

### Step 2: Consolidate

```python
consolidator = PBCConsolidator(engagement)
items, stats = consolidator.consolidate()
```

This will:
1. Read PBC files from the **audit** agent's client folder (any .md files with PBC-like tables)
2. Read PBC files from the **tax** agent's `07_PBC_QUERY/` folder
3. Infer compilation requirements from the hardcoded COMPILATION_REQUIRED_DOCS list
4. Merge and deduplicate items using the DOCUMENT_ALIASES table
5. Assign PM-level reference numbers (S01, F01, etc.)

### Step 3: Generate Output

```python
# Generate markdown
output_path = os.path.join(engine.clients_dir, client_name, 'pbc_consolidated.md')
consolidator.generate_consolidated_md(items, output_path)

# Update engagement.json with summary stats
engine.save_engagement(client_name, {
    ...engagement,
    'pbc_summary': {
        'total_items': stats['total'],
        'received': stats['received'],
        'outstanding': stats['outstanding'],
        'not_applicable': stats['n_a'],
        'last_updated': datetime.now().isoformat()
    }
})
```

### Step 4: Generate Excel (Optional)

If the user wants an Excel workbook, delegate to the `/excel-export` skill.

### Step 5: Display Summary

```
## Consolidated PBC Checklist — [Company Name]
Generated: [timestamp]

### Summary
| Metric | Count |
|--------|-------|
| Total Documents | 38 |
| Received | 12 |
| Outstanding | 22 |
| Not Applicable | 4 |

### By Service
| Service | Total | Received | Outstanding |
|---------|-------|----------|-------------|
| Audit | 25 | 7 | 18 |
| Tax | 30 | 10 | 20 |
| Compilation | 11 | 5 | 6 |

### Outstanding Items (grouped by category)
[Display the consolidated PBC table grouped by category]

### Documents Needed by Multiple Services
[Highlight documents that appear in 2+ services — these are highest priority]
```

## Deduplication Logic

The consolidator uses a DOCUMENT_ALIASES table to match equivalent documents across services:

| Canonical Name | Also Known As |
|---------------|---------------|
| Trial Balance | TB, Trial Balance (detailed) |
| General Ledger | GL, General Ledger (detailed) |
| Fixed Asset Register | FAR, Asset Register, PPE Register |
| SSM Company Profile | SSM Profile, Company Profile |
| etc. | |

When the same document appears in multiple services:
- **Needed For** shows all services (e.g., "Audit, Tax, Compilation")
- **Status** uses the best available status across services (Received > Pending > Outstanding)
- **Remarks** are merged

## Notes

- Run this skill **after** sub-agents have generated their PBC checklists (via `/delegate`)
- Re-run whenever PBC status changes (documents received, new queries raised)
- The compilation agent has no formal PBC system — its requirements are inferred from MPERS compilation standards
