# Agent Guidelines: Quartermaster Capability Governance

<!-- QUARTERMASTER_START -->
## Active Agent Capabilities (Managed by Quartermaster)

This repository uses Quartermaster to manage project-scoped capabilities in `.agents/skills/`.

| Capability | Type | Path | Status |
| :--- | :--- | :--- | :--- |
| *(None)* | - | - | Run `/quartermaster` to equip capabilities |

Commands: `/quartermaster`, `/quartermaster sweep`, `/quartermaster catalog`
<!-- QUARTERMASTER_END -->

---

## Directives for Autonomous Codex Agents

1. **Check Installed Skills Before Implementation**:
   Before proposing ad-hoc scripts or complex boilerplate, inspect `.agents/skills/` to see if a dedicated capability is already outfitted for the task.

2. **Core Guardrail Protection**:
   Folders in `.agents/skills/` or `.agents/plugins/` that contain a `.core` marker file are protected permanent guardrails. Do not delete or prune these tools.

3. **Align Capabilities on Dependency Changes**:
   When introducing new frameworks or package manifests to the codebase, run `/quartermaster sweep` to auto-equip corresponding skills from the central armory.

4. **Pruning Hygiene**:
   When removing frameworks or retiring dependencies, run a sweep with `/quartermaster sweep --auto-prune` to keep the workspace free from capability bloat.
