# Quartermaster for Google Antigravity (AGY)

Quartermaster equips Antigravity workspaces with project-scoped skills (`.agents/skills/`) and full plugins (`.agents/plugins/`) plucked from your central armory (`~/.gemini/skills-library/`).

## Quick Installation

From the repository root:

```bash
./agy/install.sh
```

Or clone directly into Antigravity's global customization directory:

```bash
git clone https://github.com/owainow/quartermaster.git ~/.gemini/config/skills/quartermaster
```

Antigravity auto-discovers skills inside `~/.gemini/config/skills/`, making `/quartermaster` immediately available in all workspaces on your machine.

---

## Chat-First Slash Commands

Quartermaster is operated directly from your Antigravity chat:

| Slash Command | What It Does |
| :--- | :--- |
| **`/quartermaster`** | Scans current workspace, guides project scoping, and provisions capabilities into `.agents/` |
| **`/quartermaster sweep`** | Audits active tools against codebase manifests, auto-equips new matches, and flags unneeded tools |
| **`/quartermaster import <git-url>`** | Clones a git repo or extracts a deep skill link into your central library and active project |
| **`/quartermaster core [add\|remove\|list]`** | Manages deterministic `.core` marker files protecting permanent guardrails from pruning |
| **`/quartermaster catalog`** | Lists all available skills and plugins across your armory |
| **`/quartermaster config`** | Checks or updates library path, auto-add, and pruning settings |
| **`/quartermaster schedule`** | Registers an automated daily background sweep using Antigravity's native scheduler |

---

## Architecture & Features

- **Project Scoping**: Detects frameworks from project manifests (`package.json`, `pubspec.yaml`, `pyproject.toml`, `Cargo.toml`, `go.mod`).
- **"I'm Not Sure Yet" Protocol**: When starting an empty repository without decided tech, equips universal Core capabilities (`spec`, `pr-review`, `pm`, `preflight`, `wayfinder`) and defers stack-specific tools until code manifests emerge.
- **Deterministic Core Governance**: Capabilities marked with `.core` files are permanent guardrails and are strictly immune to sweep pruning.
- **Aggressive vs Soft Pruning**: Configure strict stack alignment (`aggressive`, default) or conservative retention (`soft`).
