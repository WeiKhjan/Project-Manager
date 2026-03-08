---
name: client-summary
description: Generate a professional client communication summary with progress, outstanding PBC, queries, and deadlines
argument-hint: "[client name]"
---

# Client Summary

Generate a professional, client-facing summary document suitable for email or meeting communication.

## Usage

```
/client-summary ABC Trading Sdn Bhd
```

## Workflow

### Step 1: Gather Data

Load the following from the PM client folder:
1. `engagement.json` — client details, services, deadlines
2. `pbc_consolidated.md` — outstanding documents (run `/consolidated-pbc` first if stale)
3. `queries_consolidated.md` — outstanding queries (run `/consolidated-queries` first if stale)

Also probe sub-agent folders for latest status using StatusReader.

### Step 2: Generate Summary

Create a professional memo saved as `notes/client_memo_YYYY-MM-DD.md`:

```markdown
# Engagement Status Update
## [Company Legal Name]
Date: [DD Month YYYY]

---

Dear [Contact Person],

We write to provide an update on the progress of your engagement and to highlight items requiring your attention.

### 1. Engagement Overview

| Service | Status | Expected Completion |
|---------|--------|-------------------|
| Statutory Audit | In Progress (60%) | [Deadline] |
| Tax Computation (Form C) | Pending Information | [Deadline] |
| Financial Statements Compilation | Not Yet Started | [Deadline] |

### 2. Documents Still Required

The following documents are still outstanding and are needed to proceed:

**HIGH PRIORITY** (blocking progress):
| # | Document | Required For |
|---|----------|-------------|
| 1 | General Ledger | Audit, Tax |
| 2 | Fixed Asset Register (with invoices) | Audit, Tax |

**MEDIUM PRIORITY** (needed soon):
| # | Document | Required For |
|---|----------|-------------|
| 1 | Staff listing with remuneration | Tax |
| 2 | Bank reconciliation (Dec 2024) | Audit |

### 3. Queries Requiring Your Response

| # | Query | Service | Date Raised |
|---|-------|---------|-------------|
| 1 | Nature of RM 3,500 bad debt write-off | Tax | 07 Mar 2026 |
| 2 | Related party transaction details | Audit | 01 Mar 2026 |

### 4. Key Deadlines

| Deadline | Date | Days Remaining |
|----------|------|---------------|
| Form C Filing (LHDN) | 31 Jul 2025 | 145 |
| Audit Report | 30 Jun 2025 | 114 |

### 5. Next Steps

1. Please provide the outstanding documents listed above at your earliest convenience
2. Please respond to the queries raised — your response will allow us to proceed with the engagement
3. [Any other specific actions]

We appreciate your prompt attention to these matters.

Best regards,
[Firm Name]
```

### Step 3: Summary Options

After generating the memo, offer the user:
1. **Email** — "Shall I send this to the client via `/email-client`?"
2. **Excel** — "Shall I export the PBC tracker as an Excel attachment via `/excel-export`?"
3. **Edit** — "Would you like to modify anything before sending?"

## Tone & Style

- Professional but accessible (the client is typically a business owner, not an accountant)
- Use plain language for document names (avoid jargon like "PBC", say "documents required")
- Group outstanding items by priority (HIGH = blocking progress, MEDIUM = needed soon, LOW = nice to have)
- Always include specific deadlines and days remaining
- Be concise — the client should understand what's needed in under 2 minutes of reading
