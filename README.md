# Quartermaster

A smart provisioning engine and armory for Antigravity coding agents.

---

## Why Quartermaster?

If you have spent any time working with agentic coding assistants, you will have run into the skill bloat problem. The temptation early on is to install every interesting skill globally. Before long, your agent's system prompt is bloated with hundreds of lines of instructions it does not need for the task at hand. Token overhead climbs, prompt caching efficiency drops, and the model starts hallucinating tools or picking the wrong approach entirely.

A Flutter mobile developer does not need bioinformatics sequence tools loaded into their context window. A Python data engineer does not need Android emulator CLI commands. 

Quartermaster fixes this by flipping the model from global clutter to project-scoped isolation. It inspects your active workspace, figures out what technologies and frameworks you are actually using, and copies tailored, self-contained skills and plugins directly into your project's `.agents/` directory. 

Your repository gets a clean, version-controlled set of tools that any agent working in that workspace can discover automatically, with zero global side effects.

---

## Key Concepts

### 1. Library Independence
Quartermaster does not ship with a static bundle of skills inside this repository. Instead, it acts as a lean engine that references an external skills library (defaulting to `~/.gemini/skills-library`). You can point it to your team's shared repository or a local directory using the built-in settings command.

### 2. Full Plugin and Skill Support
Antigravity supports both standalone skills and full plugins. Quartermaster handles both:
* **Standalone Skills** live in `<project>/.agents/skills/<skill-name>/` with their own `SKILL.md`, scripts, and reference docs.
* **Full Plugins** live in `<project>/.agents/plugins/<plugin-name>/` and bundle multiple skills, rules (`AGENTS.md`), lifecycle hooks (`hooks.json`), and MCP server configurations into a single unit.

### 3. General AI-SDLC vs Domain-Specific Tools
Not all skills are created equal. Quartermaster classifies tools into two broad buckets:
* **General AI-SDLC**: Foundational engineering guardrails that apply to almost any software project regardless of language. Think spec-driven development (`spec`), adversarial PR review (`pr-review`), pre-commit sanity checks (`preflight`), and codebase orientation (`wayfinder`).
* **Domain-Specific**: Capabilities tied directly to a specific platform, framework, or runtime (Flutter architecture rules, Firebase security rules, Chrome DevTools debugging, PyTorch scientific tools).

### 4. Brand-New Projects and "I'm not sure yet"
When you run Quartermaster on a fresh, empty directory, there are no manifests (`package.json`, `pubspec.yaml`, etc.) to inspect. Rather than guessing or dumping random tools into your workspace, Quartermaster starts a quick scoping dialogue to ask what you are planning to build.

Crucially, there is always an option for **"I'm not sure yet"**. If you are just prototyping or haven't settled on a tech stack, Quartermaster equips only the universal General AI-SDLC skills. You get quality guardrails from day one without premature framework baggage.

### 5. Day-Two Operations: Sweeps and Scheduled Tasks
Software projects evolve. You might start with a simple Node backend, add Firebase authentication three weeks later, and introduce Tailwind for a new admin dashboard. 

Quartermaster includes a `sweep` command for ongoing audits:
* **Manual Sweep (`--sweep`)**: Audits your active workspace inventory in `.agents/`, re-scans manifests, and recommends newly relevant skills from the library. In interactive mode, it can also flag skills whose underlying dependencies were removed.
* **Scheduled Background Sweeps (`--additions-only`)**: Instead of intrusive lifecycle hooks that fire on every turn, Quartermaster can run as a daily scheduled task. In this mode, it runs quietly in the background and strictly looks for additions. It never nags you or recommends removing existing skills, ensuring zero friction.

---

## The 7 Armory Domains

Quartermaster categorizes capabilities from your skills library across 7 functional domains:

1. **Mobile & Multiplatform**: Flutter architecture, Dart testing, responsive layouts, and Android CLI / emulator tooling.
2. **Web, Frontend & Design**: Modern web architecture, high-craft UI/UX (`impeccable`), Chrome DevTools inspection, and web performance.
3. **Cloud & Backend**: Firebase (Firestore, Auth, Hosting, Rules auditing) and serverless compute (Cloud Run).
4. **Testing, Spec-Driven Development & ADLC**: Spec-driven engineering (`spec`), PR review guardrails (`pr-review`), preflight verification, Conductor tracks, and Agora ADLC loops.
5. **Synthetic Data & Simulation**: Persona simulations (`customer`, `colleague`), corporate ledgers, and multi-agent test datasets (`synthetikos`).
6. **Science & Bio-Informatics**: Literature search (arXiv, PubMed), computational biology (AlphaFold, PDB, NCBI), genomics, and fast Python environments (`uv`).
7. **AI Agent Development**: Multi-agent workflows, Antigravity SDK tool building, and orchestration.

---

## Setup & CLI Usage

Quartermaster is built with pure Python 3 standard library modules. There are no pip dependencies to install.

### 1. Configuring Your Skills Library
By default, Quartermaster looks for your central armory at `~/.gemini/skills-library`. You can view or change this at any time:

```bash
# Check current configuration
python3 scripts/quartermaster.py --config-get skills-library

# Point to a custom library path
python3 scripts/quartermaster.py --config-set skills-library /path/to/my/skills-library

# Or open the interactive settings menu
python3 scripts/quartermaster.py --config
```

### 2. Workspace Reconnaissance (`--scan`)
To inspect an existing project and see what skills match its tech stack:

```bash
# Scan current directory
python3 scripts/quartermaster.py --scan

# Scan a specific directory
python3 scripts/quartermaster.py --scan /path/to/my-project
```

If the target folder is empty or uninitialized, the scanner detects this and surfaces the scoping dialogue options.

### 3. Browsing the Catalog (`--catalog`)
To view all available plugins and skills discovered in your configured library:

```bash
python3 scripts/quartermaster.py --catalog
```

### 4. Provisioning Skills and Plugins (`--provision`)
To copy skills or full plugins into your workspace:

```bash
# Provision individual standalone skills into .agents/skills/
python3 scripts/quartermaster.py \
  --provision /path/to/my-project \
  --skills impeccable,spec,pr-review

# Provision full plugins into .agents/plugins/
python3 scripts/quartermaster.py \
  --provision /path/to/my-project \
  --plugins spark-skills,firebase
```

### 5. Running a Project Sweep (`--sweep`)
To audit what is currently installed against what your project now uses:

```bash
# Interactive on-demand sweep (shows additions and potential pruning)
python3 scripts/quartermaster.py --sweep /path/to/my-project

# Automated background sweep (additions only, machine-readable JSON)
python3 scripts/quartermaster.py --sweep /path/to/my-project --additions-only --json
```

---

## Using Quartermaster in Antigravity (AGY)

When working inside Antigravity, you can drive Quartermaster directly via chat:

* **`/quartermaster`**: Launches the guided 5-stage onboarding workflow (Recon &rarr; Scoping &rarr; Armory Review &rarr; Outfitting &rarr; Verification).
* **`/quartermaster sweep`**: Runs an on-demand audit of your project to see if newly added code warrants new skills.
* **Daily Cron Task**: Use the `/schedule` command or the built-in scheduler to run a quiet daily sweep (`0 9 * * *`), keeping your project equipped as it grows.
