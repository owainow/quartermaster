# Quartermaster for OpenAI Codex CLI

Quartermaster equips OpenAI Codex projects with tailored capabilities in `.agents/skills/` plucked from your central armory, eliminating prompt bloat and preventing capability hallucination.

## Quick Installation

From the repository root:

```bash
./codex/install.sh
```

This installs a self-contained, relocation-proof copy of Quartermaster into `~/.agents/skills/quartermaster` and `~/.codex/skills/quartermaster` (pass `--dev` or `--link` to symlink directly to your active repository for live development). Because OpenAI Codex CLI natively scans `~/.agents/skills/` and `<project>/.agents/skills/` out of the box, Quartermaster is immediately active in all your repositories.

---

## Operating Quartermaster in Codex CLI

Codex CLI allows both natural language triggering and slash commands:

| Command | Purpose |
| :--- | :--- |
| **`/quartermaster`** | Scans current project manifests, guides scoping, and provisions capabilities into `.agents/skills/` |
| **`/quartermaster sweep`** | Audits installed capabilities against codebase manifests, auto-equips new matches, and suggests pruning |
| **`/quartermaster import <git-url>`** | Imports an external repository or skill into the armory and active project |
| **`/quartermaster core [add\|remove\|list]`** | Manages deterministic `.core` marker files shielding permanent guardrails from pruning |
| **`/quartermaster catalog`** | Lists all capabilities available across the central armory |

---

## Project Context (`AGENTS.md`) Synchronization

When Quartermaster provisions or prunes capabilities in a project, it automatically maintains a dedicated table inside `<project>/AGENTS.md` between:

```markdown
<!-- QUARTERMASTER_START -->
## Active Agent Capabilities (Managed by Quartermaster)
...
<!-- QUARTERMASTER_END -->
```

OpenAI Codex CLI automatically ingests `AGENTS.md` at session start, giving your coding agents clear awareness of outfitted tools.

