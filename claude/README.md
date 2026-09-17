# Quartermaster for Anthropic Claude Code

Quartermaster equips Claude Code projects with tailored, project-scoped skills (`.claude/skills/`) plucked from your central armory, eliminating prompt bloat and preventing tool hallucination.

## Quick Installation

From the repository root:

```bash
./claude/install.sh
```

This installs a self-contained, relocation-proof copy of Quartermaster into `~/.claude/skills/quartermaster` (pass `--dev` or `--link` to symlink directly to your active repository for live development). Claude Code automatically discovers user skills in `~/.claude/skills/`, making `/quartermaster` immediately available in all projects across your machine.

---

## Operating Quartermaster in Claude Code

Quartermaster operates as both an autonomous agent capability and a direct slash command:

| Command | Purpose |
| :--- | :--- |
| **`/quartermaster`** | Scans current project manifests, guides scoping, and provisions capabilities into `.claude/skills/` |
| **`/quartermaster sweep`** | Audits installed capabilities against project manifests, auto-equips new matches, and suggests pruning |
| **`/quartermaster import <git-url>`** | Imports a git repository or extracts a specific skill into the armory and equips it |
| **`/quartermaster core [add\|remove\|list]`** | Manages deterministic `.core` marker files shielding permanent guardrails from pruning |
| **`/quartermaster catalog`** | Lists all capabilities available across the central armory |
| **`/quartermaster config`** | Views or updates Quartermaster configuration settings |
| **`/quartermaster schedule`** | Sets up daily automated sweep audits |

---

## Plugin Mode with Lifecycle Hooks

Quartermaster is fully packaged as a Claude Code plugin (`.claude-plugin/plugin.json`).

To run Claude Code with Quartermaster loaded as a plugin (enabling `SessionStart` daily sweep alerts):

```bash
claude --plugin-dir /path/to/quartermaster/claude
```

---

## Project Context (`CLAUDE.md`) Synchronization

When Quartermaster provisions or prunes capabilities in a project, it automatically updates a dedicated table inside `<project>/CLAUDE.md` between:

```markdown
<!-- QUARTERMASTER_START -->
## Active Project Capabilities (Managed by Quartermaster)
...
<!-- QUARTERMASTER_END -->
```

This gives Claude immediate visibility into active workspace capabilities upon session start.

