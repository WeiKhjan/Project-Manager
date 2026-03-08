---
name: skill-creation
description: Guide for creating new skills in the Project Manager agent
user-invocable: false
---

# Skill Creation Guide

## Skill Directory Structure

```
.claude/skills/<skill-name>/
├── SKILL.md              # Skill definition (required)
├── references/           # Large reference documents (optional)
│   └── *.md
└── scripts/              # Python/PowerShell scripts (optional)
    └── *.py
```

## SKILL.md Template

```yaml
---
name: skill-name
description: One-line description of what this skill does
argument-hint: "[optional arguments]"        # Shown in help
user-invocable: true                          # Default true; false = internal only
disable-model-invocation: false               # Default false; true = never auto-triggered
---

# Skill Title

Brief description of the skill's purpose.

## Usage

\```
/skill-name [arguments]
\```

## Workflow

### Step 1: ...
### Step 2: ...

## Notes
```

## Naming Conventions

- Skill directory: lowercase-hyphenated (e.g., `consolidated-pbc`)
- Max 64 characters
- Must be unique within the project

## Project-Specific Conventions

- Client data always in `Clients/[Company Name]/` (gitignored)
- Import tools via:
  ```python
  import sys
  sys.path.insert(0, r"C:\Users\khjan\Downloads\Pilot - Project Manager Main Agent")
  from tools.pm_engine import PMEngine
  ```
- Scripts use openpyxl for Excel, gmail API for email
- Follow existing style: professional tone, Malaysian accounting context

## Change Propagation

When creating/modifying a skill, also update:
1. `CLAUDE.md` — add to skills table
2. `memory/MEMORY.md` — document any new patterns
3. Related skills if they reference this one
