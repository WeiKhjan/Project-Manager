---
name: delegate
description: Spawn a specialist teammate (with own CLAUDE.md + skills) to perform audit, tax, or compilation work
argument-hint: "[audit|tax|compilation|all] [task description]"
---

# Delegate to Specialist Teammate (Agent Teams)

Spawn a teammate in the target agent's project directory. The teammate automatically reads that project's CLAUDE.md, gains access to its skills, and works with full specialist context.

**Requires:** Agent Teams feature enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)

## Usage

```
/delegate audit Generate PBC checklist and prepare AWP for bank and cash
/delegate tax Prepare full tax computation for YA 2025
/delegate compilation Generate MPERS financial statements from trial balance
/delegate all Set up engagement folders and generate initial PBC checklists
```

## Teammate Spawn Prompts

### Audit Teammate

**Working directory:** `C:\Users\khjan\Downloads\Pilot - Audit - Claude`
**Auto-reads:** Audit CLAUDE.md (ISA, MPERS/MFRS, AWP conventions, sections A-G)
**Skills gained:** `/awp`, `/fs`, `/viewer`, `/pbc`, `/query`, `/materiality`, `/risk-assessment`

```
Spawn Prompt:
"You are working on a statutory audit engagement.

Client: [Company Legal Name]
Company No: [Registration Number]
Financial Year End: [FYE Date]
Reporting Framework: [MPERS/MFRS]

Task: [Specific instruction]

Working folder: Clients/AWP_[ClientName]_FYE[Year]/"
```

**Common tasks to delegate:**
- "Create engagement folder with standard A-G sections and 00_Index.md"
- "Generate PBC checklist for the audit engagement"
- "Run /materiality based on revenue RM [amount]"
- "Run /risk-assessment for the engagement"
- "Run /awp bank to generate bank and cash working papers"
- "Run /awp receivables to generate trade receivables working papers"
- "Run /fs to draft full financial statements"
- "Run /viewer to generate the audit working papers viewer"

---

### Tax Teammate

**Working directory:** `C:\Users\khjan\Downloads\Pilot - TAX- Calude`
**Auto-reads:** Tax CLAUDE.md (ITA 1967, Form C, variable system, SME rates)
**Skills gained:** `/tax-computation`, `/capital-allowance`, `/pbc`, `/excel`, `/pdf`, `/email`, `/viewer`

```
Spawn Prompt:
"You are working on a Form C tax engagement.

Client: [CLIENT NAME IN UPPERCASE]
Company No: [Registration Number]
Year of Assessment: [YA Year]
Basis Period: [Start Date] to [End Date]

Task: [Specific instruction]

Working folder: Clients/[CLIENT NAME] YA [YEAR]/"
```

**Common tasks to delegate:**
- "Create engagement folder with 01-09 subfolders and master_data.json"
- "Assess information completeness and generate PBC checklist in 07_PBC_QUERY/"
- "Prepare full tax computation using the malaysian-tax-computation skill"
- "Prepare capital allowance schedule from the fixed asset register"
- "Generate tax_viewer.html and START_VIEWER.bat"
- "Export PBC checklist to Excel workbook"

---

### Compilation Teammate

**Working directory:** `C:\Users\khjan\Downloads\Pilot - MPERS Compilation - Stand Alone - Claude`
**Auto-reads:** Compilation CLAUDE.md (MPERS, ISRS 4410, FSEngine, Companies Act 2016)
**Skills gained:** `/fs`, `/mpers-fs`, `client-engagement`

```
Spawn Prompt:
"You are working on an MPERS financial statements compilation.

Client: [Company Legal Name]
Company No: [Registration Number]
Financial Year End: [FYE Date]

Task: [Specific instruction]

Working folder: Clients/[Company Legal Name]/"
```

**Common tasks to delegate:**
- "Set up engagement folder with source/ and output/ directories"
- "Analyze the trial balance in source/ and build fs_data dictionary"
- "Run /fs to generate the full MPERS financial statements DOCX"
- "Review formatting and ensure compliance with Companies Act 2016"

---

## Delegate All (Parallel Spawn)

`/delegate all [task]` spawns teammates for ALL enabled services simultaneously.

Example: User says "Set up ABC Trading — they need audit, tax, and compilation"

The Lead:
1. Loads `engagement.json` to check which services are enabled
2. Spawns all enabled teammates in parallel
3. Each teammate works independently in its own project directory
4. Teammates can message each other directly if they need information

---

## Task Dependencies

When creating tasks, specify blocking relationships:

```
Example dependency chain:

1. Compilation teammate: "Compile financial statements from TB"
   → No dependencies, can start immediately

2. Audit teammate: "Prepare audit working papers"
   → Blocked until: Compilation completes FS (needs finalized figures)

3. Tax teammate: "Prepare tax computation"
   → Blocked until: Audit confirms adjusted income figures
```

The task registry auto-unblocks downstream tasks when prerequisites complete.

---

## Peer-to-Peer Messaging

Teammates can communicate directly — no need to route through the Lead:

| From | To | Example Message |
|------|----|----------------|
| Tax | Audit | "What is the depreciation charge per P&L for FYE 2024?" |
| Audit | Tax | "Depreciation is RM 45,200. See AA_03_Depreciation.md" |
| Audit | Compilation | "Please confirm the directors' report signing date" |
| Tax | Compilation | "Is revenue per audited FS RM 2.5M or RM 2.8M?" |

This enables teammates to resolve micro-dependencies without consuming the Lead's context window.

---

## After Teammates Complete

Once teammates finish their work, the Lead:

1. **Reads output files** from each sub-agent project directory (using Read/Glob tools directly)
2. **Updates engagement.json** — service status, progress percentage
3. **Runs consolidation** — suggest `/consolidated-pbc` and `/consolidated-queries` to merge results
4. **Reports to user** — summary of what was completed, what's outstanding

```python
# Update status after teammate completion
engine.update_service_status(client_name, 'audit', 'in_progress', 60)
engine.update_service_status(client_name, 'tax', 'completed', 100)
```

---

## Delegate Mode Reminder

As Team Lead, activate **Delegate Mode** (Shift+Tab) to prevent yourself from doing implementation work. In Delegate Mode, the Lead is restricted to:
- Spawning and managing teammates
- Creating and assigning tasks
- Reviewing completed output
- Consolidating results
- Communicating with the user

---

## Fallback: If Agent Teams Unavailable

If the feature flag is not yet active or experimental issues occur:
1. The PM still tracks engagements, consolidates PBC, and generates summaries
2. User manually `cd` to each sub-agent project for specialist execution
3. User returns to PM for consolidation and client communication
