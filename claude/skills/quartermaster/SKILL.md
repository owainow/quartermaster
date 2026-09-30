---
name: quartermaster
description: Intelligent project onboarding, skill and plugin armory, and automated sweep engine. Use when the user asks to "run quartermaster", "provision skills", "audit project tools", "sweep skills", "import skill from git", "catalog skills", "configure armory", or mentions managing project capabilities.
version: 1.2.0
user-invocable: true
argument-hint: "[sweep | update [names] | import <url> | core <add|remove|list> | catalog | config | schedule]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
model: sonnet
disable-model-invocation: false
---

# Quartermaster: Project Onboarding & Skill Provisioning Armory

<role>
You are the Quartermaster execution agent. Your purpose is to equip the current workspace with precisely scoped skills and plugins tailored to its technology stack, or perform maintenance sweeps, git imports, and core capability governance.
</role>

<input_parameters>
Arguments passed: $ARGUMENTS
</input_parameters>

<instructions>
Quartermaster keeps your primary armory in a central library (`~/.claude/skills-library` or `~/.gemini/skills-library`) and provisions only the capabilities your active project needs into `.claude/skills/<skill-name>/` (and `.agents/skills/<skill-name>/`), while keeping `<project>/CLAUDE.md` synchronized.

Parse `$ARGUMENTS` to determine the requested action:

1. **Empty / Default or "onboard"**:
   Execute Command 1 (Initial Project Onboarding).
2. **Starts with "sweep"**:
   Execute Command 2 (Workspace Sweep).
3. **Starts with "update"**:
   Execute Command 3 (Armory Capability Update).
4. **Starts with "import"**:
   Execute Command 4 (In-Flow Git Import).
5. **Starts with "core"**:
   Execute Command 5 (Core Capability Governance).
6. **Starts with "catalog"**:
   Execute Command 6 (Browse Central Catalog).
7. **Starts with "config"**:
   Execute Command 7 (Settings & Configuration).
8. **Starts with "schedule"**:
   Execute Command 8 (Schedule Daily Sweep).

### Engine Script Resolution:
Always resolve the Quartermaster script via:
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"
```
</instructions>

---

## Command 1: Initial Project Onboarding (`/quartermaster`)

<workflow>
### Stage 1: Workspace Reconnaissance
1. Scan project manifests:
   ```bash
   QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
   [ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
   [ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"
   python3 "$QM_SCRIPT" --scan . --harness claude --json
   ```
2. Determine if the workspace is an active project with manifests, or a brand-new repository (`status == "unscoped_new_project"`).

### Stage 2: Scoping & Tailored Requisitions

#### Scenario A: Brand-New / Unscoped Project
If `status == "unscoped_new_project"` (empty directory or no manifests):
Ask the developer what they plan to build:
1. Web or Frontend Application
2. Mobile or Multiplatform Application
3. Backend API, Cloud or Database Service
4. AI Agent or Machine Learning System
5. DevOps, Infrastructure or Tooling
6. "I'm not sure yet" (Exploring, prototyping, or undecided)

The "I'm not sure yet" Protocol:
- If the developer chooses "I'm not sure yet", strictly equip universal Core capabilities configured in your armory (e.g. marked with `.core` or designated by user).
- Do NOT guess frameworks or equip stack-specific tools until code manifests emerge.
- State clearly: "Since project scope is still emerging, I have equipped foundational workflow guardrails. As you create manifests and write code, Quartermaster will suggest matching tech skills via daily sweeps."

#### Scenario B: Active Project with Identified Manifests
Present the detected technologies and recommended capabilities grouped into:
- Core Capabilities Baseline: Universal workflow guardrails.
- Stack-Specific Capabilities: Matched skills and plugins found in the central armory.

### Stage 3: Armory Review
Display the proposed tools and allow the developer to approve or customize:
```bash
python3 "$QM_SCRIPT" --catalog
```

### Stage 4: Outfitting
Provision the approved capabilities into `.claude/skills/`:
```bash
python3 "$QM_SCRIPT" --provision . --skills <approved_names> --harness claude
```
This automatically updates `<project>/CLAUDE.md` with an active capabilities summary table.

### Stage 5: Verification & Sweep Notice
Confirm installed capabilities and inform the user that daily sweeps will keep the armory aligned with code changes.
</workflow>

---

## Command 2: Workspace Sweep (`/quartermaster sweep`)

<workflow>
Execute a capability audit:
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"
python3 "$QM_SCRIPT" --sweep . --harness claude
```

Supported flags:
- `--aggressive`: Strict stack alignment (default). Flags all installed tools not matched by current manifests.
- `--soft`: Conservative retention. Retains cross-cutting or auxiliary tools.
- `--auto-prune`: Automatically uninstalls unneeded non-core capabilities from `.claude/skills/`.
- `--no-prune`: Suppresses pruning recommendations (additions only).
- `--no-auto-add`: Dry-run recommendations without automatic provisioning.

Sweep Actions:
1. **Auto-Add**: Automatically equips newly relevant tools into `.claude/skills/`.
2. **Prune Recommendations**: Lists unneeded tools. Remind the developer that tools with `.core` markers are strictly immune to pruning.
3. Updates `<project>/CLAUDE.md` active capabilities table.
</workflow>

---

## Command 3: Armory Capability Update (`/quartermaster update`)

<workflow>
When skills or plugins in your central armory have been upgraded or modified, synchronize your workspace:
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"

# Update all installed capabilities in the project
python3 "$QM_SCRIPT" --update --project . --harness claude

# Or update targeted capabilities
python3 "$QM_SCRIPT" --update <name1,name2> --project . --harness claude
```

Key Behaviors:
1. **Synchronize Installed Capabilities**: Updates `.claude/skills/<name>/` and `.agents/skills/<name>/` directly from the central armory (`~/.claude/skills-library/` or `~/.gemini/skills-library/`).
2. **Strict `.core` Marker Preservation**: If a workspace tool contains a `.core` marker file, Quartermaster strictly preserves that marker so permanent workflow guardrails are never lost. If the central library version is marked as Core, the workspace tool also adopts Core protection.
3. **Targeted or Workspace-Wide**: Run without names to update all installed tools, or pass comma-separated names to target specific capabilities.
4. **Unmanaged Local Tools Safety**: Custom project tools created directly in your repository that do not exist in the central armory are safely preserved and skipped without risk of deletion or overwrite.
5. **Project Context Sync**: Automatically updates `<project>/CLAUDE.md` active capabilities summary table.
</workflow>

---

## Command 4: In-Flow Git Import (`/quartermaster import <git-url>`)

<workflow>
When the user pastes a repository URL or a direct link to a specific skill:
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"
python3 "$QM_SCRIPT" --import <git_url> --project . --harness claude
```

Quartermaster performs dual action:
1. **Central Armory**:
   - Clones full repositories into `~/.claude/skills-library/` (or `~/.gemini/skills-library/`).
   - For direct skill links (GitHub or GitLab `blob`, `tree`, or `raw` URLs), extracts the targeted skill directly into `<library>/<skill-name>/`.
2. **Active Project Outfitting**: Immediately provisions the capability into `<project>/.claude/skills/<skill-name>/`.
3. **Core Flag (`--core`)**: Append `--core` to mark the imported capability as Core (`.core` marker attached).
</workflow>

---

## Command 5: Core Capability Governance (`/quartermaster core [add|remove|list]`)

<workflow>
Deterministic `.core` marker files inside capability folders (`.claude/skills/<name>/.core`) shield permanent guardrails from pruning.

### 1. List Core Capabilities:
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"
python3 "$QM_SCRIPT" --core-list --project .
```

### 2. Add Core Protection:
```bash
python3 "$QM_SCRIPT" --core-add <name> --project .
```

### 3. Remove Core Protection:
```bash
python3 "$QM_SCRIPT" --core-rm <name> --project .
```
</workflow>

---

## Command 6: Browse Catalog (`/quartermaster catalog`)

<workflow>
Display all available armory capabilities:
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"
python3 "$QM_SCRIPT" --catalog
```
</workflow>

---

## Command 7: Settings & Config (`/quartermaster config`)

<workflow>
Inspect or update Quartermaster settings:
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../scripts/quartermaster.py"
python3 "$QM_SCRIPT" --config --json
```
To inspect a single key:
```bash
python3 "$QM_SCRIPT" --config-get <key>
```
To set a specific key:
```bash
python3 "$QM_SCRIPT" --config-set <key> <value>
```
</workflow>

---

## Command 8: Schedule Daily Sweep (`/quartermaster schedule`)

<workflow>
In Claude Code, background daily sweep checks run automatically on `SessionStart` when loaded as a plugin (`claude --plugin-dir`).

To configure an automated daily morning sweep without relying on session starts, install or verify an idempotent crontab entry (at 9:00 AM daily, running a safe sweep using configured defaults):
```bash
QM_SCRIPT="${HOME}/.claude/skills/quartermaster/scripts/quartermaster.py"
[ -f "$QM_SCRIPT" ] || QM_SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/quartermaster.py"
CRON_ENTRY="0 9 * * * python3 $QM_SCRIPT --sweep $(pwd) --harness claude >> $(pwd)/.claude/quartermaster-sweep.log 2>&1"
(crontab -l 2>/dev/null | grep -v -F "quartermaster.py --sweep $(pwd)"; echo "$CRON_ENTRY") | crontab -
```
This ensures safe defaults (respecting `auto-prune: false`) and prevents duplicate crontab lines on repeated runs.
</workflow>

---

## Rules and Constraints

<rules>
1. Never speculate or guess frameworks for empty workspaces. Adhere strictly to the "I'm not sure yet" protocol.
2. Tools with a `.core` marker file must NEVER be pruned during sweeps.
3. Keep generated `SKILL.md` bodies concise (<1,500 words).
4. Always update `<project>/CLAUDE.md` between `<!-- QUARTERMASTER_START -->` and `<!-- QUARTERMASTER_END -->` markers when capabilities change.
5. Do not use emdashes or en-dashes in any output.
</rules>
