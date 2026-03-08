---
name: new-engagement
description: Register a new client and define which services (audit, tax, compilation) are needed for the engagement
---

# New Engagement Registration

Register a new client in the Project Manager system and define which services are required.

## Usage

```
/new-engagement
```

## Workflow

### Step 1: Collect Client Information

Ask the user for the following (skip any the user has already provided):

| Field | Required | Example |
|-------|----------|---------|
| Company legal name | Yes | ABC Trading Sdn Bhd |
| Company registration number | Yes | 202401012345 |
| Tax file number | No | C 2512345-06 |
| Financial year end date | Yes | 31 December 2024 |
| Financial year start date | Yes | 1 January 2024 |
| Reporting framework | Yes | MPERS or MFRS |
| Principal activities | Yes | Trading of computer hardware |
| Contact person name | Yes | Mr. Tan Ah Kow |
| Contact email | Yes | tan@abctrading.com |
| Contact phone | No | 012-345-6789 |

### Step 2: Define Services

Ask the user which services are needed (can be any combination):

- **Audit** — Statutory audit under ISA/MPERS/MFRS
- **Tax** — Form C tax computation under ITA 1967
- **Compilation** — MPERS financial statements compilation under ISRS 4410

### Step 3: Set Deadlines

For each enabled service, ask for or calculate deadlines:
- **Tax**: Default = FYE + 7 months (Form C filing deadline)
- **Audit**: Ask user for expected audit report date
- **Compilation**: Default = FYE + 6 months (circulation deadline)

### Step 4: Create Engagement

Use the PMEngine to create the engagement:

```python
import sys
sys.path.insert(0, r"C:\Users\khjan\Downloads\Pilot - Project Manager Main Agent")
from tools.pm_engine import PMEngine

engine = PMEngine()
engagement = engine.create_engagement(
    client_data={
        'legal_name': '...',
        'display_name': '...',
        'registration_no': '...',
        'tax_file_no': '...',
        'fye_date': '...',
        'fy_start': '...',
        'reporting_framework': '...',
        'principal_activities': '...',
        'contact_person': '...',
        'contact_email': '...',
        'contact_phone': '...'
    },
    services={
        'audit': True,
        'tax': True,
        'compilation': False
    }
)
```

### Step 5: Report Summary

After creation, display:
1. Client folder created: `Clients/[Company Name]/`
2. Services enabled and their deadlines
3. Sub-agent folder paths (where working papers will be stored)
4. Suggested next steps:
   - "Run `/consolidated-pbc` to generate initial PBC checklist"
   - "Run `/delegate audit [task]` to set up audit engagement folder"
   - "Run `/delegate tax [task]` to set up tax engagement folder"

## Notes

- The `display_name` is the UPPERCASE version with "SDN. BHD." formatting (e.g., "ABC TRADING SDN. BHD.")
- For tax, the Year of Assessment (YA) is typically the year the basis period ends. For FYE 31 Dec 2024, YA = 2025.
- engagement.json is the single source of truth for this client in the PM system.
