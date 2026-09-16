# Quartermaster 🛡️📦

**Intelligent Project Onboarding, Armory Engine & Automated Skill Sweeper for Antigravity AI Agents**

Quartermaster is the centralized provisioning engine for Antigravity (AGY) coding assistants. Instead of overloading agents with hundreds of global skills—which dilutes system prompts, inflates token overhead, and induces tool hallucination—Quartermaster inspects your active workspace, detects its technology stack, and provisions tailored, self-contained capabilities directly into your project's local `.agents/` directory.

Quartermaster operates with **armory independence**: it does not ship with static skills inside the repository. Instead, it references a configurable external **skills library** (defaulting to `~/.gemini/skills-library`).

---

## Core Capabilities

1. **External Armory Referencing & Settings**: Dynamically references your central skills library with interactive settings (`--config`, `--config-set skills-library <path>`).
2. **Dual Provisioning (Plugins & Skills)**:
   - **Full Plugins** &rarr; `<project_path>/.agents/plugins/<plugin_name>/` (preserving `plugin.json`, `rules/`, `skills/`, `hooks.json`, `mcp_config.json`, and `agents/`).
   - **Standalone Skills** &rarr; `<project_path>/.agents/skills/<skill_name>/` (preserving `SKILL.md`, `scripts/`, `references/`, and `resources/`).
3. **Semantic Capability Classification**:
   - **General AI-SDLC**: Foundational engineering guardrails applicable to any project regardless of language (e.g. `pr-review`, `spec`, `preflight`, `wayfinder`, `adlc-*`).
   - **Domain-Specific**: Technology-bound capabilities (e.g. Flutter architecture, Firebase rules, DevTools debugging, bioinformatics).
4. **Brand-New Project Scoping Dialogue**:
   - Detects uninitialized or empty workspaces (`unscoped_new_project`).
   - Guides the user through a scoping conversation with a mandatory **"I'm not sure yet"** option.
   - If scope is unclear, provisions *only* universal General AI-SDLC guardrails, keeping the workspace lean until frameworks are chosen.
5. **Quartermaster Sweep (`--sweep`)**:
   - Audits current workspace tech against installed `.agents/` inventory.
   - Identifies newly relevant skills/plugins to onboard as your codebase evolves.
   - Highlights pruning candidates if underlying frameworks were removed.
6. **Scheduled Daily Background Sweeps (Zero Friction)**:
   - Configurable recurring daily cron task (`0 9 * * *`).
   - Runs with `--additions-only` to silently evaluate newly relevant tools without nagging or recommending skill removal.
7. **Zero-Dependency Engine**: Built with pure Python 3 standard library modules—no pip installations required.

---

## Armory Catalog & The 7 Domains

Quartermaster categorizes capabilities across 7 functional domains:

| # | Domain | Packages Included | Description |
|---|--------|-------------------|-------------|
| **1** | **Mobile & Multiplatform** | `flutter`, `android-cli-plugin` | Flutter architecture, layout, testing, serialization, and Android CLI / emulator tooling. |
| **2** | **Web, Frontend & Design** | `chrome-devtools-plugin`, `modern-web-guidance-plugin`, `impeccable` | Craft UI/UX design, modern web architecture, responsive layouts, Chrome DevTools, and web performance. |
| **3** | **Cloud & Backend** | `firebase`, `cloudrun` | Firebase Firestore, Auth, Hosting, App Hosting, Security Rules auditing, and serverless compute. |
| **4** | **Testing, Spec-Driven Development & ADLC** | `spark-skills`, `agora-adlc`, `conductor` | Spec-driven engineering (`spec`), PR review guardrails (`pr-review`), pre-commit verification (`preflight`), Conductor tracks, and Agora ADLC loops. |
| **5** | **Synthetic Data & Simulation** | `synthetikos` | Persona simulation (`customer`, `colleague`), corporate ledgers, multi-agent synthetic datasets, and verification. |
| **6** | **Science & Bio-Informatics** | `science` | AlphaFold, PDB, PubMed, arXiv search, NCBI sequence retrieval, UniProt, ChEMBL, genomics, and `uv`. |
| **7** | **AI Agent Development** | `google-antigravity-sdk` | Multi-agent workflows, Antigravity SDK tool building, agent orchestration, and evaluation. |

---

## Directory Structure

```
/Users/owaino/quartermaster/
├── scripts/
│   └── quartermaster.py           # Core CLI, detection, settings & provisioning engine
└── README.md                      # System documentation & usage guide
```

*Note: The central library of curated plugins and skills lives externally in `~/.gemini/skills-library`.*

---

## CLI Usage

### 1. Interactive Settings & Library Configuration
```bash
# Launch interactive settings menu
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --config

# View the currently active skills-library path
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --config-get skills-library

# Change the skills-library path
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --config-set skills-library /path/to/my-library
```

### 2. Workspace Reconnaissance (`--scan`)
Scans a target project directory for manifests (`pubspec.yaml`, `package.json`, `pyproject.toml`, `firebase.json`, `Cargo.toml`, etc.):
```bash
# Scan current directory
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --scan

# Scan specific project directory
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --scan /path/to/my-project
```

### 3. View Complete Armory Catalog (`--catalog`)
Displays all 7 domains, plugins, skills, and capability tiers (`general_ai_sdlc` vs `domain_specific`):
```bash
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --catalog
```

### 4. Outfitting & Capability Provisioning (`--provision`)
Copies selected skills or full plugins into `<project_path>/.agents/`:
```bash
# Provision standalone skills (copies into .agents/skills/)
python3 /Users/owaino/quartermaster/scripts/quartermaster.py \
  --provision /path/to/my-project \
  --skills impeccable,spec,pr-review

# Provision full plugins (copies into .agents/plugins/)
python3 /Users/owaino/quartermaster/scripts/quartermaster.py \
  --provision /path/to/my-project \
  --plugins spark-skills,firebase
```

### 5. Quartermaster Sweep (`--sweep`)
Audits active workspace inventory and cross-references the central armory:
```bash
# On-demand audit (reports additions and potential pruning)
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --sweep /path/to/my-project

# Automated / scheduled mode (strictly evaluates additions, suppresses pruning)
python3 /Users/owaino/quartermaster/scripts/quartermaster.py --sweep /path/to/my-project --additions-only --json
```

---

## Antigravity (AGY) Integration

When using Antigravity, Quartermaster is activated via:
- `/quartermaster`: Guided 5-stage interactive onboarding.
- `/quartermaster sweep`: Project evolution audit.
- Daily Scheduled Task: Recurring cron (`0 9 * * *`) that executes a non-intrusive background sweep with zero friction.
