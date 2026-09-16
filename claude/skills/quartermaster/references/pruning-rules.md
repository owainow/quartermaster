# Pruning Governance and Core Protection Rules

Quartermaster enforces strict capability hygiene to prevent context bloat and token waste.

## Pruning Modes

### 1. Aggressive Mode (Default: Strict Stack Alignment)
- Any capability not marked with a `.core` file must match a current, actively detected technology manifest.
- If a project transitions from a fullstack web app to a pure backend API (e.g. `package.json` removed), lingering web tools are immediately flagged for pruning.
- Why default to Aggressive? Re-equipping a tool from the local armory takes milliseconds. Retaining unneeded tools wastes prompt tokens and causes capability hallucination.

### 2. Soft Mode (Conservative Retention)
- Retains cross-cutting or auxiliary inspection tools even if manifests are missing.
- Only flags tools when there is a hard, explicit incompatibility (such as mobile tools in a non-mobile repo).

---

## Deterministic Core Protection (.core Marker Files)

- Core capabilities represent permanent workflow guardrails.
- A capability is designated Core if its directory contains a `.core` marker file.
- Core tools are strictly immune to sweep pruning, regardless of pruning mode.
- Users can add or remove Core status on demand:
  - Add Core: `/quartermaster core add <name>`
  - Remove Core: `/quartermaster core remove <name>`
