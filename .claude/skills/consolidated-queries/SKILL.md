---
name: consolidated-queries
description: Merge outstanding query lists from all active services into a unified tracker
argument-hint: "[client name]"
---

# Consolidated Query List

Merge outstanding queries from audit and tax services into a single tracking list with PM-level reference numbers.

## Usage

```
/consolidated-queries ABC Trading Sdn Bhd
```

## Workflow

### Step 1: Load Engagement & Locate Query Files

```python
import sys
sys.path.insert(0, r"C:\Users\khjan\Downloads\Pilot - Project Manager Main Agent")
from tools.pm_engine import PMEngine

engine = PMEngine()
engagement = engine.load_engagement(client_name)
```

### Step 2: Read Queries from Sub-Agents

**Audit queries** — scan the audit client folder for files containing "Query" or "QRY":
- Typically in folders like `F_Completion/` or `G_Outstanding/`
- Format: markdown tables with columns like Ref, Description, WP Ref, Status, Response

**Tax queries** — read from `07_PBC_QUERY/`:
- Files like `QRY_01_Query_List.md`, `QRY_02_Client_Response.md`
- Format: markdown tables with columns like Ref, Description, Amount, Status, Response

**Compilation queries** — the compilation agent does not have a formal query system. Skip unless files are found.

### Step 3: Parse & Merge

For each query item, extract:
- Original reference (e.g., "Q001" from tax, "AQ-01" from audit)
- Service source (audit/tax/compilation)
- Description
- Working paper reference
- Amount involved (if any)
- Date raised
- Status (Open/Responded/Resolved/Withdrawn)
- Client response
- Resolution date

Assign PM-level reference numbers:
- `PM-A001`, `PM-A002` ... for audit queries
- `PM-T001`, `PM-T002` ... for tax queries
- `PM-C001`, `PM-C002` ... for compilation queries

### Step 4: Generate Output

Save as `queries_consolidated.md` in the PM client folder:

```markdown
# Consolidated Query List — [Company Name]
Generated: [date]

## Summary
| Status | Audit | Tax | Total |
|--------|-------|-----|-------|
| Open | 2 | 1 | 3 |
| Responded | 0 | 1 | 1 |
| Resolved | 1 | 2 | 3 |
| **Total** | **3** | **4** | **7** |

## Open Queries (Requiring Client Response)

| PM Ref | Service | Original Ref | Description | Amount (RM) | Date Raised | Status |
|--------|---------|-------------|-------------|-------------|-------------|--------|
| PM-A001 | Audit | AQ-01 | Related party transactions | 150,000 | 01/03/2026 | Open |
| PM-T001 | Tax | Q001 | Bad debts write-off nature | 3,500 | 07/03/2026 | Open |

## Responded Queries (Pending Review)
[table]

## Resolved Queries
[table]
```

### Step 5: Update engagement.json

```python
engagement['queries_summary'] = {
    'total': total_count,
    'open': open_count,
    'resolved': resolved_count,
    'last_updated': datetime.now().isoformat()
}
engine.save_engagement(client_name, engagement)
```

## Notes

- Queries typically arise during active audit/tax work, so run this **after** sub-agents have been working
- The query list is useful for `/client-summary` and `/email-client` to communicate outstanding items
- Re-run whenever queries are raised or resolved
