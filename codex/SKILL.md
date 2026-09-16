---
name: quartermaster
description: Project-scoped skill and plugin manager. Scopes, equips, imports, and audits project capabilities into .agents/skills/ while preventing prompt bloat and protecting Core guardrails (.core).
metadata:
  short-description: Manage project skills and plugins in .agents/
---

# Quartermaster: Project Capability Armory for OpenAI Codex

Quartermaster manages repository-level capabilities in `.agents/skills/` and `.agents/plugins/`, maintaining project guidelines in `AGENTS.md`.

## Engine Script Resolution
Codex agents execute the Quartermaster Python engine via:
```bash
QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
```

---

## Operational Modes

### 1. Project Scoping & Onboarding
Inspect repository manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Dockerfile`).
Select matching capabilities from the central armory and provision them into `.agents/skills/`.

Execute stack scan:
```bash
QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
python3 "$QM_SCRIPT" --scan . --harness codex --json
```

When project stack is uncertain or when starting an empty repository:
- Strictly follow the "I'm not sure yet" protocol: equip universal Core capabilities configured in your armory (e.g. marked with `.core` or designated by user).
- Defer framework-specific tools until codebase manifests are created.

Provision approved capabilities:
```bash
QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${HOME}/.codex/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
python3 "$QM_SCRIPT" --provision . --skills <approved_names> --harness codex
```

### 2. Capability Audit & Tidy (Sweep)
Audit active capabilities against codebase manifests:
```bash
QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${HOME}/.codex/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
python3 "$QM_SCRIPT" --sweep . --harness codex
```

Supported flags:
- `--aggressive`: Enforce strict stack alignment (default).
- `--soft`: Conservative retention for auxiliary tools.
- `--auto-prune`: Remove unneeded tools not protected by `.core` markers.
- `--no-auto-add`: Output recommendations only without auto-equipping.

### 3. In-Flow Git Import
Import an external repository or extract a specific skill into the armory and active workspace:
```bash
QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${HOME}/.codex/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
python3 "$QM_SCRIPT" --import <git_url> --project . --harness codex
```
Append `--core` to mark the capability as a protected permanent guardrail.

### 4. Core Capability Governance
Deterministic `.core` marker files inside skill folders (`.agents/skills/<name>/.core`) shield permanent guardrails from sweep pruning.

- List Core capabilities:
  ```bash
  QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
  [ -f "$QM_SCRIPT" ] || QM_SCRIPT="${HOME}/.codex/skills/quartermaster/scripts/quartermaster.py"
  [ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
  python3 "$QM_SCRIPT" --core-list --project .
  ```
- Add Core protection:
  ```bash
  QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
  [ -f "$QM_SCRIPT" ] || QM_SCRIPT="${HOME}/.codex/skills/quartermaster/scripts/quartermaster.py"
  [ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
  python3 "$QM_SCRIPT" --core-add <name> --project .
  ```
- Remove Core protection:
  ```bash
  QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
  [ -f "$QM_SCRIPT" ] || QM_SCRIPT="${HOME}/.codex/skills/quartermaster/scripts/quartermaster.py"
  [ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
  python3 "$QM_SCRIPT" --core-rm <name> --project .
  ```

### 5. Catalog Inspection
List all available skills and plugins in the central armory:
```bash
QM_SCRIPT="${HOME}/.agents/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="scripts/quartermaster.py"
python3 "$QM_SCRIPT" --catalog
```

---

## Critical Invariants
1. Never guess tech stacks for empty projects. Adhere to the "I'm not sure yet" protocol.
2. Tools containing a `.core` marker file are permanent guardrails and must NEVER be pruned.
3. Keep project `<project>/AGENTS.md` synchronized with active capabilities.
