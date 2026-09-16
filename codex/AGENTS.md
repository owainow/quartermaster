# Agent Guidelines: Quartermaster Capability Governance

<!-- QUARTERMASTER_START -->
## Active Agent Capabilities (Managed by Quartermaster)

This repository uses Quartermaster to manage project-scoped capabilities in `.agents/skills/`.

| Capability | Type | Path | Status |
| :--- | :--- | :--- | :--- |
| `spec` | Skill | `.agents/skills/spec` | Core (Protected) |
| `pr-review` | Skill | `.agents/skills/pr-review` | Core (Protected) |
| `pm` | Skill | `.agents/skills/pm` | Core (Protected) |
| `preflight` | Skill | `.agents/skills/preflight` | Core (Protected) |
| `wayfinder` | Skill | `.agents/skills/wayfinder` | Core (Protected) |

Direct Mentions: `$quartermaster`, `$quartermaster sweep`
<!-- QUARTERMASTER_END -->

---

## Directives for Autonomous Codex Agents

1. **Check Installed Skills Before Implementation**:
   Before proposing ad-hoc scripts or complex boilerplate, inspect `.agents/skills/` to see if a dedicated capability is already outfitted for the task.

2. **Core Guardrail Protection**:
   Folders in `.agents/skills/` or `.agents/plugins/` that contain a `.core` marker file are protected permanent guardrails. Do not delete or prune these tools.

3. **Align Capabilities on Dependency Changes**:
   When introducing new frameworks or package manifests to the codebase, mention `$quartermaster sweep` to auto-equip corresponding skills from the central armory.

4. **Pruning Hygiene**:
   When removing frameworks or retiring dependencies, run a sweep with `$quartermaster sweep --auto-prune` to keep the workspace free from capability bloat.
