#!/usr/bin/env python3
"""
Quartermaster - Project-Scoped Capability Provisioner & Armory Engine
References an external central skills library, plucks only project-relevant skills and plugins
into `<project_path>/.agents/`, scopes brand-new projects, and provides sweep audits with
configurable pruning governance, deterministic Core capability tagging (.core), and in-flow git library imports.

Features:
- External central library referencing (default: ~/.gemini/skills-library)
- Dynamic in-flow git imports (--import <git-url>) directly into central library
- Dual provisioning: Full plugins (.agents/plugins/) and standalone skills (.agents/skills/)
- Clean capability tiers: Core Capabilities (deterministic .core marker) vs Stack-Specific
- Interactive brand-new project scoping with "I'm not sure yet" fallback
- Project sweep (--sweep) for ongoing audits (auto-equip and pruning governance)
- Core capability management (--core-add, --core-rm, --core-list)
- Configurable settings: suggest-pruning, auto-prune, pruning-mode (aggressive/soft)

Zero external dependencies beyond Python 3 standard library.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

# Configuration Paths
GLOBAL_CONFIG_DIR = os.path.expanduser("~/.gemini/quartermaster")
GLOBAL_CONFIG_FILE = os.path.join(GLOBAL_CONFIG_DIR, "config.json")
FALLBACK_CONFIG_FILE = os.path.expanduser("~/.quartermaster/config.json")

CLAUDE_CONFIG_DIR = os.path.expanduser("~/.claude/quartermaster")
CLAUDE_CONFIG_FILE = os.path.join(CLAUDE_CONFIG_DIR, "config.json")

CODEX_CONFIG_DIR = os.path.expanduser("~/.codex/quartermaster")
CODEX_CONFIG_FILE = os.path.join(CODEX_CONFIG_DIR, "config.json")

CONFIG_SEARCH_PATHS = [
    CLAUDE_CONFIG_FILE,
    CODEX_CONFIG_FILE,
    GLOBAL_CONFIG_FILE,
    FALLBACK_CONFIG_FILE,
]

DEFAULT_LIBRARY_PATH = os.path.expanduser("~/.gemini/skills-library")

PROBE_LIBRARY_DIRS = [
    os.path.expanduser("~/.gemini/skills-library"),
    os.path.expanduser("~/.claude/skills-library"),
    os.path.expanduser("~/.agents/skills-library"),
    os.path.expanduser("~/.quartermaster/skills-library"),
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "skills-library": DEFAULT_LIBRARY_PATH,
    "auto-add": True,
    "suggest-pruning": True,
    "auto-prune": False,
    "pruning-mode": "aggressive",
}

SUPPORTED_HARNESSES = ("agy", "claude", "codex", "universal")

# ==============================================================================
# Deterministic Core Capability Governance (.core marker file)
# ==============================================================================
CORE_MARKER_FILE = ".core"


# ==============================================================================
# Multi-Harness Detection & Target Path Resolution
# ==============================================================================

def safe_write_file(file_path: str, content: str) -> None:
    """Atomically write content to file_path using a temporary file."""
    target_dir = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(target_dir, exist_ok=True)
    tmp_path = f"{file_path}.tmp.{os.getpid()}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, file_path)


def detect_harness(project_path: Optional[str] = None, explicit_harness: Optional[str] = None) -> str:
    """
    Detects the active agent harness.
    Precedence:
    1. Explicit CLI argument (--harness) if not 'auto'
    2. QUARTERMASTER_HARNESS environment variable
    3. Active harness environment variables (CLAUDE_PROJECT_DIR, CODEX_HOME, etc.)
    4. Project marker files and directories:
       - .claude/ directory or CLAUDE.md -> 'claude'
       - .codex/ directory or AGENTS.md -> 'codex'
       - .gemini/ directory -> 'agy'
       - .agents/ directory -> 'codex' (if ~/.codex) or 'agy'
    5. Host user environment:
       - ~/.claude exists and neither ~/.gemini nor ~/.codex -> 'claude'
       - ~/.codex exists and not ~/.gemini -> 'codex'
       - ~/.gemini exists -> 'agy'
    6. Default fallback: 'agy'
    """
    if explicit_harness and explicit_harness.lower() != "auto":
        h = explicit_harness.lower().strip()
        if h in SUPPORTED_HARNESSES:
            return h

    env_h = os.environ.get("QUARTERMASTER_HARNESS", "").strip().lower()
    if env_h in SUPPORTED_HARNESSES:
        return env_h

    if os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return "claude"
    if os.environ.get("CODEX_HOME") or os.environ.get("CODEX_CLI"):
        return "codex"

    probe_dir = os.path.abspath(os.path.expanduser(project_path)) if project_path else os.getcwd()

    if os.path.exists(os.path.join(probe_dir, ".claude")) or os.path.exists(os.path.join(probe_dir, "CLAUDE.md")):
        return "claude"
    if os.path.exists(os.path.join(probe_dir, ".codex")) or os.path.exists(os.path.join(probe_dir, "AGENTS.md")):
        return "codex"
    if os.path.exists(os.path.join(probe_dir, ".gemini")):
        return "agy"
    if os.path.exists(os.path.join(probe_dir, ".agents")):
        if os.path.exists(os.path.expanduser("~/.codex")) and not os.path.exists(os.path.expanduser("~/.gemini")):
            return "codex"
        return "agy"

    if os.path.exists(os.path.expanduser("~/.claude")) and not os.path.exists(os.path.expanduser("~/.gemini")):
        return "claude"
    if os.path.exists(os.path.expanduser("~/.codex")) and not os.path.exists(os.path.expanduser("~/.gemini")):
        return "codex"
    if os.path.exists(os.path.expanduser("~/.gemini")):
        return "agy"

    return "agy"


def get_harness_target_paths(project_path: str, harness: str) -> Tuple[str, str]:
    """
    Returns (skills_dir, plugins_dir) for the given harness.
    - claude: <project>/.claude/skills and "" (Claude Code discovers .claude/skills only)
    - agy / codex / universal: <project>/.agents/skills and <project>/.agents/plugins
    """
    proj = os.path.abspath(os.path.expanduser(project_path))
    if harness == "claude":
        claude_skills = os.path.join(proj, ".claude", "skills")
        return (claude_skills, "")
    return (
        os.path.join(proj, ".agents", "skills"),
        os.path.join(proj, ".agents", "plugins"),
    )


# ==============================================================================
# Agent Context Documentation Synchronization (CLAUDE.md / AGENTS.md)
# ==============================================================================

def sync_claude_md(
    project_path: str,
    active_skills: List[Dict[str, Any]],
    active_plugins: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Maintains an active capabilities table inside <project>/CLAUDE.md between HTML comments:
    <!-- QUARTERMASTER_START --> and <!-- QUARTERMASTER_END -->.
    """
    claude_md_path = os.path.join(project_path, "CLAUDE.md")
    content = ""
    if os.path.exists(claude_md_path):
        try:
            with open(claude_md_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            sys.stderr.write(f"Warning: Could not read {claude_md_path}: {e}\n")
            return None

    start_marker = "<!-- QUARTERMASTER_START -->"
    end_marker = "<!-- QUARTERMASTER_END -->"

    block_lines = [
        start_marker,
        "## Active Project Capabilities (Managed by Quartermaster)",
        "",
        "This project is outfitted with project-scoped capabilities.",
        "",
        "| Capability | Type | Path | Status |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for s in sorted(active_skills, key=lambda x: x["name"]):
        s_name = s["name"]
        s_path = s.get("path", f".claude/skills/{s_name}")
        s_path_full = s_path if os.path.isabs(s_path) else os.path.join(project_path, s_path)
        rel_path = os.path.relpath(s_path_full, project_path)
        is_core = os.path.exists(os.path.join(s_path_full, CORE_MARKER_FILE))
        status = "Core (Protected)" if is_core else "Active"
        block_lines.append(f"| `{s_name}` | Skill | `{rel_path}` | {status} |")

    for p in sorted(active_plugins, key=lambda x: x["name"]):
        p_name = p["name"]
        p_path = p.get("path", f".claude/skills/{p_name}")
        p_path_full = p_path if os.path.isabs(p_path) else os.path.join(project_path, p_path)
        rel_path = os.path.relpath(p_path_full, project_path)
        is_core = os.path.exists(os.path.join(p_path_full, CORE_MARKER_FILE))
        status = "Core (Protected)" if is_core else "Active"
        block_lines.append(f"| `{p_name}` | Plugin | `{rel_path}` | {status} |")

    if not active_skills and not active_plugins:
        block_lines.append("| *(None)* | - | - | Run `/quartermaster` to equip capabilities |")

    block_lines.append("")
    block_lines.append("Commands: `/quartermaster`, `/quartermaster sweep`, `/quartermaster catalog`")
    block_lines.append(end_marker)
    new_block = "\n".join(block_lines)

    if start_marker in content and end_marker not in content:
        content = content.replace(start_marker, f"{start_marker}\n{end_marker}\n")

    pattern = re.compile(f"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL)
    if pattern.search(content):
        updated = pattern.sub(new_block, content)
    else:
        if content.strip():
            updated = content.rstrip() + "\n\n" + new_block + "\n"
        else:
            updated = "# Project Guidelines\n\n" + new_block + "\n"

    try:
        safe_write_file(claude_md_path, updated)
        return claude_md_path
    except Exception:
        return None


def sync_agents_md(
    project_path: str,
    active_skills: List[Dict[str, Any]],
    active_plugins: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Maintains an active capabilities table inside <project>/AGENTS.md between HTML comments:
    <!-- QUARTERMASTER_START --> and <!-- QUARTERMASTER_END -->.
    """
    agents_md_path = os.path.join(project_path, "AGENTS.md")
    content = ""
    if os.path.exists(agents_md_path):
        try:
            with open(agents_md_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            sys.stderr.write(f"Warning: Could not read {agents_md_path}: {e}\n")
            return None

    start_marker = "<!-- QUARTERMASTER_START -->"
    end_marker = "<!-- QUARTERMASTER_END -->"

    block_lines = [
        start_marker,
        "## Active Agent Capabilities (Managed by Quartermaster)",
        "",
        "This repository uses Quartermaster to manage project-scoped capabilities in `.agents/skills/`.",
        "",
        "| Capability | Type | Path | Status |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for s in sorted(active_skills, key=lambda x: x["name"]):
        s_name = s["name"]
        s_path = s.get("path", f".agents/skills/{s_name}")
        s_path_full = s_path if os.path.isabs(s_path) else os.path.join(project_path, s_path)
        rel_path = os.path.relpath(s_path_full, project_path)
        is_core = os.path.exists(os.path.join(s_path_full, CORE_MARKER_FILE))
        status = "Core (Protected)" if is_core else "Active"
        block_lines.append(f"| `{s_name}` | Skill | `{rel_path}` | {status} |")

    for p in sorted(active_plugins, key=lambda x: x["name"]):
        p_name = p["name"]
        p_path = p.get("path", f".agents/plugins/{p_name}")
        p_path_full = p_path if os.path.isabs(p_path) else os.path.join(project_path, p_path)
        rel_path = os.path.relpath(p_path_full, project_path)
        is_core = os.path.exists(os.path.join(p_path_full, CORE_MARKER_FILE))
        status = "Core (Protected)" if is_core else "Active"
        block_lines.append(f"| `{p_name}` | Plugin | `{rel_path}` | {status} |")

    if not active_skills and not active_plugins:
        block_lines.append("| *(None)* | - | - | Run `/quartermaster` to equip capabilities |")

    block_lines.append("")
    block_lines.append("Commands: `/quartermaster`, `/quartermaster sweep`, `/quartermaster catalog`")
    block_lines.append(end_marker)
    new_block = "\n".join(block_lines)

    if start_marker in content and end_marker not in content:
        content = content.replace(start_marker, f"{start_marker}\n{end_marker}\n")

    pattern = re.compile(f"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL)
    if pattern.search(content):
        updated = pattern.sub(new_block, content)
    else:
        if content.strip():
            updated = content.rstrip() + "\n\n" + new_block + "\n"
        else:
            updated = "# Agent Guidelines\n\n" + new_block + "\n"

    try:
        safe_write_file(agents_md_path, updated)
        return agents_md_path
    except Exception:
        return None


def sync_project_docs(
    project_path: str,
    harness: str,
    active_skills: Optional[List[Dict[str, Any]]] = None,
    active_plugins: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Optional[str]]:
    """
    Synchronizes project context files (CLAUDE.md, AGENTS.md) based on active harness.
    """
    proj = os.path.abspath(os.path.expanduser(project_path))
    results: Dict[str, Optional[str]] = {}

    if active_skills is None or active_plugins is None:
        active_skills = []
        active_plugins = []
        skills_dir, plugins_dir = get_harness_target_paths(proj, harness)
        if skills_dir and os.path.exists(skills_dir):
            for s in sorted(os.listdir(skills_dir)):
                sp = os.path.join(skills_dir, s)
                if os.path.isdir(sp) and not s.startswith("."):
                    active_skills.append({"name": s, "path": sp, "type": "skill"})
        if plugins_dir and os.path.exists(plugins_dir):
            for p in sorted(os.listdir(plugins_dir)):
                pp = os.path.join(plugins_dir, p)
                if os.path.isdir(pp) and not p.startswith("."):
                    active_plugins.append({"name": p, "path": pp, "type": "plugin"})

    if harness == "claude" or os.path.exists(os.path.join(proj, "CLAUDE.md")):
        results["claude"] = sync_claude_md(proj, active_skills, active_plugins)

    if harness == "codex" or os.path.exists(os.path.join(proj, "AGENTS.md")):
        results["codex"] = sync_agents_md(proj, active_skills, active_plugins)

    if harness == "universal":
        results["claude"] = sync_claude_md(proj, active_skills, active_plugins)
        results["codex"] = sync_agents_md(proj, active_skills, active_plugins)

    return results


# ==============================================================================
# Configuration & Settings Management
# ==============================================================================

def get_active_config_file(harness: Optional[str] = None) -> str:
    """Returns the primary config file path based on active harness or existing files."""
    if harness == "claude":
        return CLAUDE_CONFIG_FILE
    elif harness == "codex":
        return CODEX_CONFIG_FILE
    elif harness == "agy":
        return GLOBAL_CONFIG_FILE

    for p in CONFIG_SEARCH_PATHS:
        if os.path.exists(p):
            return p
    return GLOBAL_CONFIG_FILE


def load_config(harness: Optional[str] = None) -> Dict[str, Any]:
    """Loads Quartermaster settings from disk or returns defaults."""
    cfg = dict(DEFAULT_CONFIG)
    cfg_file = get_active_config_file(harness)
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict[str, Any], harness: Optional[str] = None) -> str:
    """Saves Quartermaster settings to disk atomically."""
    cfg_file = get_active_config_file(harness)
    content = json.dumps(cfg, indent=2) + "\n"
    safe_write_file(cfg_file, content)
    return cfg_file


def get_config_value(key: str, harness: Optional[str] = None) -> Optional[Any]:
    """Retrieves a specific configuration value."""
    cfg = load_config(harness)
    return cfg.get(key)


def set_config_value(key: str, value: Any, harness: Optional[str] = None) -> Dict[str, Any]:
    """Sets a specific configuration value and persists it."""
    cfg = load_config(harness)
    # Normalize booleans if passed as string
    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes", "on"):
            value = True
        elif value.lower() in ("false", "0", "no", "off"):
            value = False
        elif key in ("pruning-mode", "prune-mode"):
            value = value.lower()
            if value not in ("aggressive", "soft"):
                value = "aggressive"
    if key == "prune-mode":
        key = "pruning-mode"
    cfg[key] = value
    save_config(cfg, harness)
    return cfg


def resolve_library_path(custom_path: Optional[str] = None) -> str:
    """
    Resolve the active Quartermaster library path:
    1. CLI argument (--library)
    2. Configured 'skills-library' setting
    3. Existing library in PROBE_LIBRARY_DIRS
    4. Default location (~/.gemini/skills-library)
    """
    if custom_path:
        expanded = os.path.abspath(os.path.expanduser(custom_path))
        if os.path.exists(expanded):
            return expanded

    cfg = load_config()
    configured_lib = cfg.get("skills-library")
    if configured_lib:
        expanded = os.path.abspath(os.path.expanduser(configured_lib))
        if os.path.exists(expanded):
            return expanded

    for p in PROBE_LIBRARY_DIRS:
        if os.path.exists(p):
            return p

    return os.path.abspath(DEFAULT_LIBRARY_PATH)


def interactive_config() -> None:
    """Interactive command-line configuration session."""
    cfg = load_config()
    print("=" * 80)
    print("  QUARTERMASTER SETTINGS")
    print("=" * 80)
    print(f"Active Config File: {get_active_config_file()}")
    print("\nSettings:")
    print(f"  * skills-library  = {cfg.get('skills-library')}")
    print(f"  * auto-add        = {cfg.get('auto-add', True)} (automatically provision matching capabilities during sweep)")
    print(f"  * suggest-pruning = {cfg.get('suggest-pruning', True)} (suggest unneeded skills to remove during sweep)")
    print(f"  * auto-prune      = {cfg.get('auto-prune', False)} (automatically remove unneeded skills during sweep)")
    current_prune_mode = cfg.get("pruning-mode") or cfg.get("prune-mode") or "aggressive"
    print(f"  * pruning-mode    = {current_prune_mode} (aggressive = strict stack alignment; soft = conservative retention)")

    print("-" * 80)
    print("Options:")
    print("  1. Update 'skills-library' path")
    print(f"  2. Toggle 'auto-add' (currently: {cfg.get('auto-add', True)})")
    print(f"  3. Toggle 'suggest-pruning' (currently: {cfg.get('suggest-pruning', True)})")
    print(f"  4. Toggle 'auto-prune' (currently: {cfg.get('auto-prune', False)})")
    print(f"  5. Toggle 'pruning-mode' (currently: {current_prune_mode})")
    print("  6. Reset settings to default")
    print("  7. Exit")

    choice = input("\nEnter choice [1-7] (default: 7): ").strip()
    if choice == "1":
        current = cfg.get("skills-library", DEFAULT_LIBRARY_PATH)
        new_val = input(f"Enter new skills-library path [{current}]: ").strip()
        if new_val:
            expanded = os.path.abspath(os.path.expanduser(new_val))
            if not os.path.exists(expanded):
                print(f"\nWarning: Path does not exist on disk: {expanded}")
                confirm = input("Save anyway? (y/N): ").strip().lower()
                if confirm != "y":
                    print("Operation cancelled.")
                    return
            set_config_value("skills-library", expanded)
            print(f"\nUpdated 'skills-library' to: {expanded}")
    elif choice == "2":
        new_val = not cfg.get("auto-add", True)
        set_config_value("auto-add", new_val)
        print(f"\nUpdated 'auto-add' to: {new_val}")
    elif choice == "3":
        new_val = not cfg.get("suggest-pruning", True)
        set_config_value("suggest-pruning", new_val)
        print(f"\nUpdated 'suggest-pruning' to: {new_val}")
    elif choice == "4":
        new_val = not cfg.get("auto-prune", False)
        set_config_value("auto-prune", new_val)
        print(f"\nUpdated 'auto-prune' to: {new_val}")
    elif choice == "5":
        new_val = "soft" if current_prune_mode.lower() == "aggressive" else "aggressive"
        set_config_value("pruning-mode", new_val)
        print(f"\nUpdated 'pruning-mode' to: {new_val}")
    elif choice == "6":
        save_config(dict(DEFAULT_CONFIG))
        print("\nSettings reset to default.")
    else:
        print("\nNo changes made.")


# ==============================================================================
# In-Flow Library Import via Git URL & Project Auto-Outfitting
# ==============================================================================

def find_project_root(start_dir: Optional[str] = None) -> Optional[str]:
    """
    Determines if a directory is within an active project by looking for
    project markers (.git, .agents, manifests) walking up to the user home or filesystem root.
    Returns the absolute path to the project root, or None if outside a project.
    """
    if start_dir:
        curr = os.path.abspath(os.path.expanduser(start_dir))
    else:
        curr = os.path.abspath(os.getcwd())

    home = os.path.abspath(os.path.expanduser("~"))

    # Never treat user home or filesystem root as a project
    if curr == home or curr == "/":
        return None

    markers = {
        ".git",
        ".agents",
        "package.json",
        "pyproject.toml",
        "pubspec.yaml",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "requirements.txt",
        "Pipfile",
        "setup.py",
        "firebase.json",
        "Dockerfile",
        "docker-compose.yml",
    }

    probe = curr
    while probe and probe != home and probe != "/":
        for m in markers:
            if os.path.exists(os.path.join(probe, m)):
                return probe
        probe = os.path.dirname(probe)

    return None


def import_library_asset(
    git_url: str,
    library_path: Optional[str] = None,
    project_path: Optional[str] = None,
    force: bool = False,
    is_core: bool = False,
    harness: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Clones a skill or plugin repository directly into the central skills library.
    Supports:
    1. Direct Git repository URLs:
       https://github.com/owner/repo.git
    2. Deep GitHub or GitLab blob and tree URLs pointing to a specific skill:
       https://github.com/owner/repo/blob/main/skills/dependency-upgrade/SKILL.md
       https://github.com/owner/repo/tree/main/skills/dependency-upgrade
    3. Raw GitHub URLs:
       https://raw.githubusercontent.com/owner/repo/main/skills/dependency-upgrade/SKILL.md

    If a specific skill is targeted in a larger repository, Quartermaster extracts
    that exact skill into `~/.gemini/skills-library/<skill-name>/` so it exists directly
    in the central library as a standalone skill.

    If executed from within an active project (or if project_path is provided),
    also immediately provisions the imported capability into that project's .claude/skills/
    or .agents/skills/ depending on the detected harness.
    """
    lib_dir = resolve_library_path(library_path)
    os.makedirs(lib_dir, exist_ok=True)

    if not git_url or git_url.strip().startswith("-"):
        return {
            "status": "error",
            "error": f"Invalid git repository URL or flag: {git_url}",
            "git_url": git_url,
        }

    cleaned_url = git_url.strip().split("?")[0].split("#")[0].rstrip("/")
    clone_url = cleaned_url
    target_subpath: Optional[str] = None
    target_skill_name: Optional[str] = None

    # Pattern 1: GitHub / GitLab blob or tree URLs
    gh_match = re.match(
        r"^(https?://(?:github\.com|gitlab\.com)/[^/]+/[^/]+?)(?:/(?:-|blob|tree)/[^/]+(?:/(.*))?)?$",
        cleaned_url,
    )
    # Pattern 2: raw.githubusercontent.com URLs
    raw_match = re.match(
        r"^https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/[^/]+/(.*)$",
        cleaned_url,
    )

    if gh_match:
        base_repo = gh_match.group(1)
        clone_url = base_repo if base_repo.endswith(".git") else base_repo + ".git"
        sub = gh_match.group(2) or ""
        if sub:
            target_subpath = sub
    elif raw_match:
        owner = raw_match.group(1)
        repo = raw_match.group(2)
        clone_url = f"https://github.com/{owner}/{repo}.git"
        target_subpath = raw_match.group(3)

    if target_subpath:
        parts = [p for p in target_subpath.split("/") if p and p != "SKILL.md"]
        if parts:
            target_skill_name = parts[-1]

    # Determine if we should outfit into an active project
    active_project = None
    if project_path:
        active_project = find_project_root(project_path) or os.path.abspath(os.path.expanduser(project_path))
    else:
        active_project = find_project_root()

    active_harness = detect_harness(active_project, harness) if active_project else "agy"
    project_provisioned: List[Dict[str, Any]] = []

    # CASE 1: Targeted skill extracted from repository
    if target_skill_name:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cmd = ["git", "clone", "--depth", "1", "--", clone_url, tmp_dir]
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                return {
                    "status": "error",
                    "error": f"Failed to clone repository from {clone_url}: {e.stderr or e.stdout}",
                    "git_url": git_url,
                }

            candidate_dirs: List[str] = []
            if target_subpath:
                direct_p = os.path.join(tmp_dir, target_subpath)
                if os.path.isfile(direct_p):
                    direct_p = os.path.dirname(direct_p)
                if os.path.isdir(direct_p) and os.path.exists(os.path.join(direct_p, "SKILL.md")):
                    candidate_dirs.append(direct_p)

            if not candidate_dirs:
                for root, dirs, files in os.walk(tmp_dir):
                    if "SKILL.md" in files:
                        s_name = os.path.basename(root).lower().replace("_", "-")
                        if s_name == target_skill_name.lower().replace("_", "-"):
                            candidate_dirs.append(root)

            if not candidate_dirs:
                all_s = glob.glob(os.path.join(tmp_dir, "**", "SKILL.md"), recursive=True)
                available = [os.path.basename(os.path.dirname(p)) for p in all_s]
                avail_str = f" Available skills: {', '.join(available[:10])}" if available else ""
                return {
                    "status": "error",
                    "error": f"No skill definition (SKILL.md) found for '{target_skill_name}' in {clone_url}.{avail_str}",
                    "git_url": git_url,
                }

            src_skill_dir = candidate_dirs[0]
            try:
                with open(os.path.join(src_skill_dir, "SKILL.md"), "r", encoding="utf-8", errors="ignore") as f:
                    fm = parse_skill_frontmatter(f.read())
            except Exception:
                fm = {}

            raw_name = fm.get("name") or os.path.basename(src_skill_dir)
            clean_name = re.sub(r"[^a-zA-Z0-9._-]", "-", os.path.basename(raw_name.strip())).strip("-.")
            if not clean_name:
                clean_name = "custom-skill"
            canonical_name = clean_name

            dest_dir = os.path.abspath(os.path.join(lib_dir, canonical_name))
            if os.path.commonpath([dest_dir, lib_dir]) != lib_dir or dest_dir == lib_dir:
                return {"status": "error", "error": f"Invalid skill destination: {dest_dir}", "git_url": git_url}

            already_existed = os.path.exists(dest_dir)

            if already_existed and not force:
                status = "exists"
                message = f"Skill '{canonical_name}' already exists in central library: {dest_dir}."
            else:
                if already_existed and force:
                    if os.path.islink(dest_dir):
                        os.unlink(dest_dir)
                    else:
                        shutil.rmtree(dest_dir)
                shutil.copytree(
                    src_skill_dir,
                    dest_dir,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__"),
                )
                status = "installed"
                message = f"Installed skill '{canonical_name}' into central library: {dest_dir}."

            is_core_asset = (
                is_core
                or fm.get("core") is True
            )
            if is_core_asset:
                try:
                    with open(os.path.join(dest_dir, CORE_MARKER_FILE), "w", encoding="utf-8") as f:
                        f.write("# Quartermaster Core Capability\n")
                except Exception:
                    pass

            if active_project and os.path.isdir(active_project):
                proj_skills_dir, _ = get_harness_target_paths(active_project, active_harness)
                os.makedirs(proj_skills_dir, exist_ok=True)
                proj_dest_dir = os.path.abspath(os.path.join(proj_skills_dir, canonical_name))
                if os.path.commonpath([proj_dest_dir, proj_skills_dir]) != proj_skills_dir or proj_dest_dir == proj_skills_dir:
                    return {"status": "error", "error": f"Invalid project destination: {proj_dest_dir}", "git_url": git_url}
                if os.path.islink(proj_dest_dir):
                    os.unlink(proj_dest_dir)
                shutil.copytree(
                    dest_dir,
                    proj_dest_dir,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__"),
                )
                if is_core_asset:
                    try:
                        with open(os.path.join(proj_dest_dir, CORE_MARKER_FILE), "w", encoding="utf-8") as f:
                            f.write("# Quartermaster Core Capability\n")
                    except Exception:
                        pass
                file_count = sum(len(files) for _, _, files in os.walk(proj_dest_dir))
                project_provisioned.append({
                    "name": canonical_name,
                    "type": "skill",
                    "package": canonical_name,
                    "tier": "core" if is_core_asset else "stack",
                    "destination": proj_dest_dir,
                    "files_copied": file_count,
                    "status": "provisioned",
                })
                sync_project_docs(active_project, active_harness)

            return {
                "status": status,
                "name": canonical_name,
                "is_plugin": False,
                "target_skill": canonical_name,
                "skills_count": 1,
                "destination": dest_dir,
                "library_path": lib_dir,
                "project_path": active_project,
                "project_provisioned": project_provisioned,
                "is_core": is_core_asset,
                "harness": active_harness,
                "message": message,
            }

    # CASE 2: Whole repository import (plugin, package, or standalone repo)
    clean_repo_name = os.path.basename(clone_url.rstrip("/\\"))
    if clean_repo_name.endswith(".git"):
        clean_repo_name = clean_repo_name[:-4]
    clean_repo_name = re.sub(r"[^a-zA-Z0-9._-]", "-", clean_repo_name).strip("-.")
    if not clean_repo_name or clean_repo_name in (".", ".."):
        return {"status": "error", "error": f"Invalid repository URL: {git_url}", "git_url": git_url}

    repo_name = clean_repo_name
    dest_dir = os.path.abspath(os.path.join(lib_dir, repo_name))
    if os.path.commonpath([dest_dir, lib_dir]) != lib_dir or dest_dir == lib_dir:
        return {"status": "error", "error": f"Destination escapes skills library: {dest_dir}", "git_url": git_url}

    already_existed = os.path.exists(dest_dir)
    status = "installed"
    message = ""

    if already_existed and not force:
        status = "exists"
        message = f"Asset '{repo_name}' already exists in library: {dest_dir}."
    else:
        if already_existed and force:
            if os.path.islink(dest_dir):
                os.unlink(dest_dir)
            else:
                shutil.rmtree(dest_dir)

        cmd = ["git", "clone", "--depth", "1", "--", clone_url, dest_dir]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            status = "installed"
            message = f"Installed '{repo_name}' into central library: {dest_dir}."
        except subprocess.CalledProcessError as e:
            return {
                "status": "error",
                "error": f"Failed to clone repository: {e.stderr or e.stdout}",
                "git_url": git_url,
            }

    is_plugin = os.path.exists(os.path.join(dest_dir, "plugin.json"))
    skill_files = glob.glob(os.path.join(dest_dir, "**", "SKILL.md"), recursive=True)

    is_core_asset = is_core
    if is_core_asset:
        try:
            with open(os.path.join(dest_dir, CORE_MARKER_FILE), "w", encoding="utf-8") as f:
                f.write("# Quartermaster Core Capability\n")
        except Exception:
            pass

    if active_project and os.path.isdir(active_project):
        prov_res = provision_assets(
            project_path=active_project,
            asset_names=[repo_name],
            library_path=lib_dir,
            harness=active_harness,
        )
        project_provisioned = prov_res.get("provisioned", [])
        sync_project_docs(active_project, active_harness)

    return {
        "status": status,
        "name": repo_name,
        "is_plugin": is_plugin,
        "skills_count": len(skill_files),
        "destination": dest_dir,
        "library_path": lib_dir,
        "project_path": active_project,
        "project_provisioned": project_provisioned,
        "is_core": is_core_asset,
        "message": message,
    }


# ==============================================================================
# Frontmatter & Manifest Parsing
# ==============================================================================

def parse_skill_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML frontmatter from a SKILL.md document without external YAML dependencies."""
    meta: Dict[str, Any] = {}
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return meta
    fm = match.group(1)

    name_m = re.search(r"^name:\s*(.*)$", fm, re.MULTILINE)
    if name_m:
        meta["name"] = name_m.group(1).strip().strip("\"'")

    ver_m = re.search(r"^version:\s*(.*)$", fm, re.MULTILINE)
    if ver_m:
        meta["version"] = ver_m.group(1).strip().strip("\"'")

    tags_m = re.search(r"^tags:\s*\[(.*?)\]", fm, re.MULTILINE)
    if tags_m:
        meta["tags"] = [t.strip().strip("\"'") for t in tags_m.group(1).split(",") if t.strip()]

    lines = fm.split("\n")
    desc_lines: List[str] = []
    in_desc = False
    base_indent = None

    for line in lines:
        if re.match(r"^description:\s*", line):
            in_desc = True
            val = re.sub(r"^description:\s*", "", line).strip()
            if val and val not in (">", ">-", "|", "|-"):
                desc_lines.append(val.strip("\"'"))
                in_desc = False
            continue

        if in_desc:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if base_indent is None:
                base_indent = indent
            if indent >= base_indent:
                desc_lines.append(line.strip())
            else:
                in_desc = False

    if desc_lines:
        meta["description"] = " ".join(desc_lines)

    return meta


def parse_plugin_manifest(plugin_json_path: str) -> Dict[str, Any]:
    """Parse plugin.json manifest."""
    try:
        with open(plugin_json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ==============================================================================
# Armory Cataloging (Natural Package & Plugin Discovery)
# ==============================================================================

def get_catalog(library_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Discovers all packages, plugins, and skills in the configured skills-library.
    Groups naturally by Package / Plugin on disk.
    """
    lib_dir = resolve_library_path(library_path)
    if not os.path.exists(lib_dir):
        return {
            "library_path": lib_dir,
            "error": f"Library path does not exist: {lib_dir}",
            "total_packages": 0,
            "total_plugins": 0,
            "total_skills": 0,
            "packages": {},
            "plugins": [],
            "skills": [],
        }

    package_dirs = [
        d for d in os.listdir(lib_dir)
        if os.path.isdir(os.path.join(lib_dir, d)) and not d.startswith(".")
    ]

    packages_dict: Dict[str, Dict[str, Any]] = {}
    all_plugins: List[Dict[str, Any]] = []
    all_skills: List[Dict[str, Any]] = []

    for pkg in sorted(package_dirs):
        pkg_dir = os.path.join(lib_dir, pkg)

        plugin_manifest_path = os.path.join(pkg_dir, "plugin.json")
        is_plugin = os.path.exists(plugin_manifest_path)

        plugin_info: Optional[Dict[str, Any]] = None
        if is_plugin:
            manifest_data = parse_plugin_manifest(plugin_manifest_path)
            plugin_name = manifest_data.get("name") or pkg
            plugin_desc = manifest_data.get("description") or "No description provided."
            plugin_version = manifest_data.get("version")

            components = []
            if os.path.exists(os.path.join(pkg_dir, "skills")):
                components.append("skills")
            if os.path.exists(os.path.join(pkg_dir, "rules")):
                components.append("rules")
            if os.path.exists(os.path.join(pkg_dir, "hooks.json")):
                components.append("hooks")
            if os.path.exists(os.path.join(pkg_dir, "mcp_config.json")):
                components.append("mcp")
            if os.path.exists(os.path.join(pkg_dir, "agents")):
                components.append("agents")

            has_core_file = os.path.exists(os.path.join(pkg_dir, CORE_MARKER_FILE))
            is_core_manifest = manifest_data.get("core") is True
            p_tier = "core" if (has_core_file or is_core_manifest) else "stack"

            plugin_tags = manifest_data.get("tags", [])
            if not plugin_tags:
                plugin_tags = [w for w in re.split(r"[-_\s]+", plugin_name.lower()) if len(w) > 2]

            plugin_info = {
                "name": plugin_name,
                "package": pkg,
                "tier": p_tier,
                "version": plugin_version,
                "description": plugin_desc,
                "tags": plugin_tags,
                "source_dir": pkg_dir,
                "manifest_file": plugin_manifest_path,
                "components": components,
            }
            all_plugins.append(plugin_info)

        skill_files = glob.glob(os.path.join(pkg_dir, "**", "SKILL.md"), recursive=True)
        pkg_skills: List[Dict[str, Any]] = []

        for sf in sorted(skill_files):
            skill_dir = os.path.dirname(sf)
            try:
                with open(sf, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                content = ""

            meta = parse_skill_frontmatter(content)
            name = meta.get("name") or os.path.basename(skill_dir)
            desc = meta.get("description") or "No description available."
            version = meta.get("version")
            tags = meta.get("tags", [])
            if not tags:
                tags = [w for w in re.split(r"[-_\s]+", name.lower()) if len(w) > 2]

            has_core_file = (
                os.path.exists(os.path.join(skill_dir, CORE_MARKER_FILE))
                or os.path.exists(os.path.join(pkg_dir, CORE_MARKER_FILE))
            )
            is_core_frontmatter = meta.get("core") is True
            s_tier = "core" if (has_core_file or is_core_frontmatter) else "stack"

            subdirs = [
                d for d in os.listdir(skill_dir)
                if os.path.isdir(os.path.join(skill_dir, d))
            ]

            skill_entry = {
                "name": name,
                "dir_name": os.path.basename(skill_dir),
                "package": pkg,
                "tier": s_tier,
                "tags": tags,
                "source_dir": skill_dir,
                "skill_file": sf,
                "description": desc,
                "version": version,
                "subdirs": subdirs,
                "parent_plugin": plugin_info["name"] if plugin_info else None,
            }
            pkg_skills.append(skill_entry)
            all_skills.append(skill_entry)

        packages_dict[pkg] = {
            "name": pkg,
            "is_plugin": is_plugin,
            "plugin_info": plugin_info,
            "skills": pkg_skills,
            "skill_count": len(pkg_skills),
        }

    return {
        "library_path": lib_dir,
        "total_packages": len(package_dirs),
        "total_plugins": len(all_plugins),
        "total_skills": len(all_skills),
        "packages": packages_dict,
        "plugins": all_plugins,
        "skills": all_skills,
    }


# ==============================================================================
# Workspace Reconnaissance & Stack Matching
# ==============================================================================

def detect_stack(project_path: str, library_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans project root and subdirectories for manifest files.
    Identifies frameworks, detects uninitialized projects,
    and returns tailored recommendations.
    """
    proj_dir = os.path.abspath(os.path.expanduser(project_path))
    if not os.path.exists(proj_dir):
        return {
            "project_path": proj_dir,
            "status": "error",
            "error": f"Path does not exist: {proj_dir}",
            "manifests_found": [],
            "technologies": [],
            "recommended_skills": [],
            "recommended_plugins": [],
        }

    manifests_found: List[str] = []
    technologies: List[Dict[str, Any]] = []
    recommended_skills: List[Dict[str, Any]] = []
    recommended_plugins: List[Dict[str, Any]] = []
    seen_skill_names: Set[str] = set()
    seen_plugin_names: Set[str] = set()

    def add_skill_rec(name: str, package: str, tier: str, reason: str, priority: str = "High"):
        norm = name.lower().replace("_", "-")
        if norm not in seen_skill_names:
            seen_skill_names.add(norm)
            recommended_skills.append({
                "name": name,
                "package": package,
                "tier": tier,
                "reason": reason,
                "priority": priority,
            })

    def add_plugin_rec(name: str, tier: str, reason: str, priority: str = "High"):
        norm = name.lower().replace("_", "-")
        if norm not in seen_plugin_names:
            seen_plugin_names.add(norm)
            recommended_plugins.append({
                "name": name,
                "tier": tier,
                "reason": reason,
                "priority": priority,
            })

    def safe_read(path: str, max_chars: int = 10000) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
        except Exception:
            return ""

    # 1. Search directories (root + depth 1 subdirectories for monorepos)
    search_dirs = [proj_dir]
    try:
        for entry in sorted(os.listdir(proj_dir)):
            ep = os.path.join(proj_dir, entry)
            if os.path.isdir(ep) and not entry.startswith(".") and entry not in (
                "node_modules", "target", "build", "dist", ".git", ".venv", "venv", "__pycache__"
            ):
                search_dirs.append(ep)
    except Exception:
        pass

    detected_tech_tags: Set[str] = set()

    for s_dir in search_dirs:
        rel_prefix = "" if s_dir == proj_dir else f"{os.path.basename(s_dir)}/"

        # Flutter / Dart (pubspec.yaml)
        pubspec_path = os.path.join(s_dir, "pubspec.yaml")
        if os.path.exists(pubspec_path):
            m_name = f"{rel_prefix}pubspec.yaml"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                content = safe_read(pubspec_path)
                tech_details = ["Dart"]
                if "flutter:" in content or "sdk: flutter" in content:
                    tech_details.append("Flutter SDK")
                technologies.append({
                    "name": "Flutter / Dart",
                    "manifest": m_name,
                    "details": ", ".join(tech_details),
                    "tags": ["flutter", "dart", "mobile"],
                })
                detected_tech_tags.update(["flutter", "dart", "mobile"])

        # Android Native / Gradle
        android_dir = os.path.join(s_dir, "android")
        has_gradle = (
            os.path.exists(os.path.join(s_dir, "build.gradle"))
            or os.path.exists(os.path.join(s_dir, "build.gradle.kts"))
            or (os.path.exists(android_dir) and os.path.isdir(android_dir))
        )
        if has_gradle:
            m_name = f"{rel_prefix}build.gradle"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                technologies.append({
                    "name": "Android Native / Gradle",
                    "manifest": m_name,
                    "details": "Android Gradle build system and device tools",
                    "tags": ["android", "mobile", "gradle"],
                })
                detected_tech_tags.update(["android", "mobile", "gradle"])

        # Apple iOS / Swift
        has_ios = (
            os.path.exists(os.path.join(s_dir, "Podfile"))
            or os.path.exists(os.path.join(s_dir, "Package.swift"))
            or any(f.endswith(".xcodeproj") or f.endswith(".xcworkspace") for f in os.listdir(s_dir) if os.path.exists(s_dir) and os.path.isdir(s_dir))
        )
        if has_ios:
            m_name = f"{rel_prefix}Package.swift / Xcode"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                technologies.append({
                    "name": "Apple iOS / Swift",
                    "manifest": m_name,
                    "details": "Swift / Xcode project and Apple toolchain",
                    "tags": ["ios", "swift", "apple", "mobile", "xcode"],
                })
                detected_tech_tags.update(["ios", "swift", "apple", "mobile", "xcode"])

        # Node.js / Web / TypeScript (package.json)
        pkg_json = os.path.join(s_dir, "package.json")
        if os.path.exists(pkg_json):
            m_name = f"{rel_prefix}package.json"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                content = safe_read(pkg_json)
                frameworks = []
                w_tags = ["web", "frontend", "node", "javascript", "typescript"]
                if "react" in content:
                    frameworks.append("React")
                    w_tags.append("react")
                if "next" in content:
                    frameworks.append("Next.js")
                    w_tags.append("next")
                if "vue" in content:
                    frameworks.append("Vue")
                    w_tags.append("vue")
                if "svelte" in content:
                    frameworks.append("Svelte")
                    w_tags.append("svelte")
                if "tailwind" in content or os.path.exists(os.path.join(s_dir, "tailwind.config.js")):
                    frameworks.append("Tailwind CSS")
                    w_tags.append("tailwind")
                if "vite" in content:
                    frameworks.append("Vite")
                    w_tags.append("vite")
                if "express" in content:
                    frameworks.append("Express")
                if "fastify" in content:
                    frameworks.append("Fastify")
                if os.path.exists(os.path.join(s_dir, "tsconfig.json")):
                    frameworks.append("TypeScript")

                details_str = ", ".join(frameworks) if frameworks else "JavaScript/Node.js"
                technologies.append({
                    "name": "Web & Node.js Platform",
                    "manifest": m_name,
                    "details": details_str,
                    "tags": w_tags,
                })
                detected_tech_tags.update(w_tags)

        elif os.path.exists(os.path.join(s_dir, "index.html")) and s_dir == proj_dir:
            manifests_found.append("index.html")
            technologies.append({
                "name": "Static Web / HTML",
                "manifest": "index.html",
                "details": "Static HTML/CSS/JavaScript",
                "tags": ["web", "frontend", "html", "css"],
            })
            detected_tech_tags.update(["web", "frontend", "html", "css"])

        # Chrome Extension (manifest.json)
        manifest_json_path = os.path.join(s_dir, "manifest.json")
        if os.path.exists(manifest_json_path):
            content = safe_read(manifest_json_path)
            if "manifest_version" in content:
                m_name = f"{rel_prefix}manifest.json"
                if m_name not in manifests_found:
                    manifests_found.append(m_name)
                    technologies.append({
                        "name": "Chrome Extension",
                        "manifest": m_name,
                        "details": "Chrome Extension manifest (v2/v3)",
                        "tags": ["chrome-extension", "chrome", "web", "browser"],
                    })
                    detected_tech_tags.update(["chrome-extension", "chrome", "web", "browser"])

        # Firebase (firebase.json, .firebaserc)
        fb_json = os.path.join(s_dir, "firebase.json")
        fb_rc = os.path.join(s_dir, ".firebaserc")
        if os.path.exists(fb_json) or os.path.exists(fb_rc):
            m_name = f"{rel_prefix}firebase.json" if os.path.exists(fb_json) else f"{rel_prefix}.firebaserc"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                technologies.append({
                    "name": "Firebase Platform",
                    "manifest": m_name,
                    "details": "Cloud Firestore, Auth, Hosting, and Security Rules",
                    "tags": ["firebase", "backend", "cloud"],
                })
                detected_tech_tags.update(["firebase", "backend", "cloud"])

        # Python (pyproject.toml, requirements.txt, Pipfile, setup.py)
        py_files = [
            f for f in ["pyproject.toml", "requirements.txt", "Pipfile", "setup.py"]
            if os.path.exists(os.path.join(s_dir, f))
        ]
        if py_files:
            primary_py = f"{rel_prefix}{py_files[0]}"
            if primary_py not in manifests_found:
                manifests_found.append(primary_py)
                combined_py = " ".join([safe_read(os.path.join(s_dir, f)) for f in py_files]).lower()
                py_details = ["Python 3"]
                py_tags = ["python", "backend"]
                if "fastapi" in combined_py:
                    py_details.append("FastAPI")
                    py_tags.append("fastapi")
                if "flask" in combined_py:
                    py_details.append("Flask")
                    py_tags.append("flask")
                if "django" in combined_py:
                    py_details.append("Django")
                    py_tags.append("django")

                technologies.append({
                    "name": "Python Environment",
                    "manifest": primary_py,
                    "details": ", ".join(py_details),
                    "tags": py_tags,
                })
                detected_tech_tags.update(py_tags)

        # Rust (Cargo.toml)
        cargo_path = os.path.join(s_dir, "Cargo.toml")
        if os.path.exists(cargo_path):
            m_name = f"{rel_prefix}Cargo.toml"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                technologies.append({
                    "name": "Rust Platform",
                    "manifest": m_name,
                    "details": "Rust Cargo package specification",
                    "tags": ["rust"],
                })
                detected_tech_tags.update(["rust"])

        # Go (go.mod)
        go_mod_path = os.path.join(s_dir, "go.mod")
        if os.path.exists(go_mod_path):
            m_name = f"{rel_prefix}go.mod"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                technologies.append({
                    "name": "Go Platform",
                    "manifest": m_name,
                    "details": "Go module definition",
                    "tags": ["go", "golang"],
                })
                detected_tech_tags.update(["go", "golang"])

        # Containers / Docker
        dockerfile = os.path.join(s_dir, "Dockerfile")
        compose = os.path.join(s_dir, "docker-compose.yml")
        if os.path.exists(dockerfile) or os.path.exists(compose):
            m_name = f"{rel_prefix}Dockerfile" if os.path.exists(dockerfile) else f"{rel_prefix}docker-compose.yml"
            if m_name not in manifests_found:
                manifests_found.append(m_name)
                technologies.append({
                    "name": "Containerization / Docker",
                    "manifest": m_name,
                    "details": "Container build specifications and multi-service definitions",
                    "tags": ["docker", "container", "devops", "cloud"],
                })
                detected_tech_tags.update(["docker", "container", "devops", "cloud"])

    # 3. Dynamic Catalog Recommendations
    lib_path = resolve_library_path(library_path)
    try:
        catalog = get_catalog(lib_path)
    except Exception:
        catalog = {}

    # Core Baseline Capabilities from Catalog (.core marker or tier == "core")
    for p in catalog.get("plugins", []):
        if p.get("tier") == "core":
            add_plugin_rec(
                p["name"],
                "core",
                p.get("description") or "Universal core workflow plugin",
                priority="Baseline",
            )

    for s in catalog.get("skills", []):
        if s.get("tier") == "core":
            add_skill_rec(
                s["name"],
                s.get("package", ""),
                "core",
                s.get("description") or "Universal core workflow capability",
                priority="Baseline",
            )

    # Dynamic Stack-Matched Capabilities from Catalog
    def matches_tags(name: str, pkg: str, item_tags: List[str], desc: str, target_tags: Set[str]) -> Tuple[bool, str]:
        norm_n = name.lower().replace("_", "-")
        norm_p = pkg.lower().replace("_", "-")
        norm_d = desc.lower()

        for it in item_tags:
            t_clean = str(it).lower().replace("_", "-")
            if t_clean in target_tags:
                return True, f"Matched tag '{t_clean}'"

        for tt in target_tags:
            if len(tt) > 2 and (tt in norm_n or tt in norm_p):
                return True, f"Matched technology '{tt}'"
            if len(tt) > 3 and re.search(r"\b" + re.escape(tt) + r"\b", norm_d):
                return True, f"Matched capability description mentioning '{tt}'"

        return False, ""

    if detected_tech_tags:
        for p in catalog.get("plugins", []):
            if p.get("tier") == "core":
                continue
            matched, reason = matches_tags(
                p["name"],
                p.get("package", ""),
                p.get("tags", []),
                p.get("description", ""),
                detected_tech_tags,
            )
            if matched:
                add_plugin_rec(
                    p["name"],
                    "stack",
                    p.get("description") or f"Plugin matched to workspace: {reason}",
                    priority="High",
                )

        for s in catalog.get("skills", []):
            if s.get("tier") == "core":
                continue
            matched, reason = matches_tags(
                s["name"],
                s.get("package", ""),
                s.get("tags", []),
                s.get("description", ""),
                detected_tech_tags,
            )
            if matched:
                add_skill_rec(
                    s["name"],
                    s.get("package", ""),
                    "stack",
                    s.get("description") or f"Skill matched to workspace: {reason}",
                    priority="High",
                )


    is_brand_new = False
    if not manifests_found:
        entries = [
            e for e in os.listdir(proj_dir)
            if not e.startswith(".") and e.lower() not in ("readme.md", "license", "licence")
        ]
        if len(entries) == 0:
            is_brand_new = True

    status = "unscoped_new_project" if is_brand_new else "active_project"

    scoping_dialogue = None
    if is_brand_new:
        scoping_dialogue = {
            "prompt": "This workspace appears to be a brand-new project. What type of project are you building?",
            "options": [
                {"label": "Web or Frontend Application"},
                {"label": "Mobile or Multiplatform Application"},
                {"label": "Backend API, Cloud or Database Service"},
                {"label": "AI Agent or Machine Learning System"},
                {"label": "DevOps, Infrastructure or Tooling"},
                {"label": "I'm not sure yet"},
            ],
            "recommendation_on_unclear": (
                "When scope is undecided or 'I\\'m not sure yet' is chosen, Quartermaster equips "
                "only universal Core capabilities (specifications, adversarial code review, preflight checks), "
                "keeping your workspace lean until framework choices emerge."
            )
        }

    return {
        "project_path": proj_dir,
        "status": status,
        "is_brand_new": is_brand_new,
        "manifests_found": manifests_found,
        "technologies": technologies,
        "recommended_skills": recommended_skills,
        "recommended_plugins": recommended_plugins,
        "scoping_dialogue": scoping_dialogue,
    }


# ==============================================================================
# Dual Provisioning Engine (.agents/plugins/ and .agents/skills/)
# ==============================================================================

def provision_assets(
    project_path: str,
    asset_names: List[str],
    library_path: Optional[str] = None,
    force_type: Optional[str] = None,
    harness: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Provisions requested assets into project capability directories:
    - claude: <project>/.claude/skills/
    - agy / codex: <project>/.agents/skills/ and <project>/.agents/plugins/
    """
    proj_dir = os.path.abspath(os.path.expanduser(project_path))
    os.makedirs(proj_dir, exist_ok=True)

    active_harness = detect_harness(proj_dir, harness)
    target_skills_dir, target_plugins_dir = get_harness_target_paths(proj_dir, active_harness)

    catalog = get_catalog(library_path)
    all_skills = catalog.get("skills", [])
    all_plugins = catalog.get("plugins", [])

    plugin_map: Dict[str, Dict[str, Any]] = {}
    for p in all_plugins:
        p_name = p["name"].lower()
        plugin_map[p_name] = p
        plugin_map[p_name.replace("-plugin", "")] = p
        plugin_map[p_name.replace("_", "-")] = p
        plugin_map[p["package"].lower()] = p

    skill_map: Dict[str, Dict[str, Any]] = {}
    skill_by_pkg: Dict[str, List[Dict[str, Any]]] = {}
    for s in all_skills:
        s_name = s["name"].lower()
        skill_map[s_name] = s
        skill_map[s_name.replace("-", "_")] = s
        skill_map[s_name.replace("_", "-")] = s
        skill_map[s["dir_name"].lower()] = s
        skill_by_pkg.setdefault(s["package"].lower(), []).append(s)

    expanded_requests: List[str] = []
    for item in asset_names:
        for sub in item.split(","):
            sub_c = sub.strip()
            if sub_c:
                expanded_requests.append(sub_c)

    provisioned: List[Dict[str, Any]] = []
    not_found: List[str] = []
    seen_destinations: Set[str] = set()

    for req in expanded_requests:
        req_norm = req.lower().strip()
        handled = False

        is_plugin_match = (req_norm in plugin_map) if force_type != "skill" else False
        is_skill_match = (req_norm in skill_map) if force_type != "plugin" else False

        # Route 1: Full Plugin Provisioning
        if is_plugin_match and force_type != "skill":
            plugin = plugin_map[req_norm]
            canonical_name = plugin["name"]
            dest_parent = target_plugins_dir if target_plugins_dir else target_skills_dir
            dest_dir = os.path.join(dest_parent, canonical_name)

            if dest_dir not in seen_destinations:
                seen_destinations.add(dest_dir)
                os.makedirs(dest_parent, exist_ok=True)
                src_dir = plugin["source_dir"]
                shutil.copytree(
                    src_dir,
                    dest_dir,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__"),
                )

                if plugin["tier"] == "core":
                    try:
                        with open(os.path.join(dest_dir, CORE_MARKER_FILE), "w", encoding="utf-8") as f:
                            f.write("# Quartermaster Core Capability\n")
                    except Exception:
                        pass

                file_count = sum(len(files) for _, _, files in os.walk(dest_dir))
                provisioned.append({
                    "name": canonical_name,
                    "type": "plugin",
                    "package": plugin["package"],
                    "tier": plugin["tier"],
                    "source": src_dir,
                    "destination": dest_dir,
                    "files_copied": file_count,
                    "status": "provisioned",
                })
            handled = True

        # Route 2: Standalone Skill Provisioning
        elif is_skill_match:
            skill = skill_map[req_norm]
            canonical_name = skill["name"]
            dest_dir = os.path.join(target_skills_dir, canonical_name)

            if dest_dir not in seen_destinations:
                seen_destinations.add(dest_dir)
                os.makedirs(target_skills_dir, exist_ok=True)
                src_dir = skill["source_dir"]
                shutil.copytree(
                    src_dir,
                    dest_dir,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__"),
                )

                if skill["tier"] == "core":
                    try:
                        with open(os.path.join(dest_dir, CORE_MARKER_FILE), "w", encoding="utf-8") as f:
                            f.write("# Quartermaster Core Capability\n")
                    except Exception:
                        pass

                file_count = sum(len(files) for _, _, files in os.walk(dest_dir))
                provisioned.append({
                    "name": canonical_name,
                    "type": "skill",
                    "package": skill["package"],
                    "tier": skill["tier"],
                    "source": src_dir,
                    "destination": dest_dir,
                    "files_copied": file_count,
                    "status": "provisioned",
                })
            handled = True

        # Route 3: Package name expansion
        elif req_norm in skill_by_pkg:
            for skill in skill_by_pkg[req_norm]:
                canonical_name = skill["name"]
                dest_dir = os.path.join(target_skills_dir, canonical_name)
                if dest_dir not in seen_destinations:
                    seen_destinations.add(dest_dir)
                    os.makedirs(target_skills_dir, exist_ok=True)
                    src_dir = skill["source_dir"]
                    shutil.copytree(
                        src_dir,
                        dest_dir,
                        dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__"),
                    )

                    if skill["tier"] == "core":
                        try:
                            with open(os.path.join(dest_dir, CORE_MARKER_FILE), "w", encoding="utf-8") as f:
                                f.write("# Quartermaster Core Capability\n")
                        except Exception:
                            pass

                    file_count = sum(len(files) for _, _, files in os.walk(dest_dir))
                    provisioned.append({
                        "name": canonical_name,
                        "type": "skill",
                        "package": skill["package"],
                        "tier": skill["tier"],
                        "source": src_dir,
                        "destination": dest_dir,
                        "files_copied": file_count,
                        "status": "provisioned",
                    })
            handled = True

        if not handled:
            not_found.append(req)

    synced_docs = sync_project_docs(proj_dir, active_harness)

    return {
        "project_path": proj_dir,
        "harness": active_harness,
        "synced_docs": synced_docs,
        "requested": expanded_requests,
        "provisioned": provisioned,
        "provisioned_count": len(provisioned),
        "not_found": not_found,
    }


# ==============================================================================
# Quartermaster Sweep (Project & Armory Audit with Pruning Governance)
# ==============================================================================

def sweep_project(
    project_path: str,
    library_path: Optional[str] = None,
    auto_add: Optional[bool] = None,
    suggest_pruning: Optional[bool] = None,
    auto_prune: Optional[bool] = None,
    pruning_mode: Optional[str] = None,
    harness: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Audits the workspace:
    1. Checks active inventory in project capability directories (.claude/skills/ or .agents/).
    2. Re-scans manifests and dependencies.
    3. Identifies newly relevant additions:
       - If auto_add is True (default): automatically provisions them.
    4. Evaluates unneeded stack tools:
       - Pruning mode can be 'aggressive' (strict stack alignment) or 'soft' (conservative retention).
       - If suggest_pruning is True: lists them as removal recommendations.
       - If auto_prune is True: automatically uninstalls them.
    """
    cfg = load_config()
    final_auto_add = auto_add if auto_add is not None else cfg.get("auto-add", True)
    final_suggest_pruning = suggest_pruning if suggest_pruning is not None else cfg.get("suggest-pruning", True)
    final_auto_prune = auto_prune if auto_prune is not None else cfg.get("auto-prune", False)

    raw_mode = (
        pruning_mode
        if pruning_mode
        else (cfg.get("pruning-mode") or cfg.get("prune-mode") or "aggressive")
    )
    final_pruning_mode = str(raw_mode).lower().strip()
    if final_pruning_mode not in ("aggressive", "soft"):
        final_pruning_mode = "aggressive"

    proj_dir = os.path.abspath(os.path.expanduser(project_path))
    active_harness = detect_harness(proj_dir, harness)
    scan = detect_stack(proj_dir, library_path=library_path)
    catalog = get_catalog(library_path)

    target_skills_dir, target_plugins_dir = get_harness_target_paths(proj_dir, active_harness)

    installed_skills: List[Dict[str, Any]] = []
    if target_skills_dir and os.path.exists(target_skills_dir):
        for s_name in sorted(os.listdir(target_skills_dir)):
            s_path = os.path.join(target_skills_dir, s_name)
            if os.path.isdir(s_path):
                installed_skills.append({
                    "name": s_name,
                    "path": s_path,
                    "type": "skill",
                })

    installed_plugins: List[Dict[str, Any]] = []
    if target_plugins_dir and os.path.exists(target_plugins_dir):
        for p_name in sorted(os.listdir(target_plugins_dir)):
            p_path = os.path.join(target_plugins_dir, p_name)
            if os.path.isdir(p_path):
                installed_plugins.append({
                    "name": p_name,
                    "path": p_path,
                    "type": "plugin",
                })

    installed_skill_names = {s["name"].lower() for s in installed_skills}
    installed_plugin_names = {p["name"].lower() for p in installed_plugins}

    additions: List[Dict[str, Any]] = []

    for rec_plugin in scan.get("recommended_plugins", []):
        p_name = rec_plugin["name"].lower()
        if p_name not in installed_plugin_names:
            additions.append({
                "name": rec_plugin["name"],
                "type": "plugin",
                "tier": rec_plugin.get("tier", "stack"),
                "reason": rec_plugin["reason"],
                "priority": rec_plugin.get("priority", "High"),
            })

    for rec_skill in scan.get("recommended_skills", []):
        s_name = rec_skill["name"].lower()
        parent_pkg = rec_skill.get("package", "").lower()
        if s_name not in installed_skill_names and parent_pkg not in installed_plugin_names:
            additions.append({
                "name": rec_skill["name"],
                "type": "skill",
                "tier": rec_skill.get("tier", "stack"),
                "reason": rec_skill["reason"],
                "priority": rec_skill.get("priority", "High"),
            })

    # Automatically equip additions when auto_add is active
    provisioned_additions: List[Dict[str, Any]] = []
    if final_auto_add and additions:
        names_to_provision = [a["name"] for a in additions]
        prov_res = provision_assets(
            project_path=proj_dir,
            asset_names=names_to_provision,
            library_path=library_path,
            harness=active_harness,
        )
        provisioned_additions = prov_res.get("provisioned", [])

        # Update active lists so current inventory reflects the newly equipped tools
        for pa in provisioned_additions:
            if pa["type"] == "plugin":
                installed_plugins.append({
                    "name": pa["name"],
                    "path": pa["destination"],
                    "type": "plugin",
                })
                installed_plugin_names.add(pa["name"].lower())
            else:
                installed_skills.append({
                    "name": pa["name"],
                    "path": pa["destination"],
                    "type": "skill",
                })
                installed_skill_names.add(pa["name"].lower())

    pruning_candidates: List[Dict[str, Any]] = []
    pruned_items: List[Dict[str, Any]] = []

    manifest_list = scan.get("manifests_found", [])
    has_web = (
        any(m in ("package.json", "manifest.json", "index.html") for m in manifest_list)
        or os.path.exists(os.path.join(proj_dir, "package.json"))
        or os.path.exists(os.path.join(proj_dir, "index.html"))
        or os.path.exists(os.path.join(proj_dir, "manifest.json"))
    )
    has_flutter = (
        "pubspec.yaml" in manifest_list
        or os.path.exists(os.path.join(proj_dir, "pubspec.yaml"))
    )
    has_android = (
        any("android" in m or "gradle" in m for m in manifest_list)
        or os.path.exists(os.path.join(proj_dir, "android"))
        or os.path.exists(os.path.join(proj_dir, "build.gradle"))
        or os.path.exists(os.path.join(proj_dir, "build.gradle.kts"))
    )
    has_firebase = (
        any("firebase" in m for m in manifest_list)
        or os.path.exists(os.path.join(proj_dir, "firebase.json"))
        or os.path.exists(os.path.join(proj_dir, ".firebaserc"))
    )
    has_python = (
        any(m in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py") for m in manifest_list)
        or any(
            os.path.exists(os.path.join(proj_dir, f))
            for f in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py")
        )
    )
    has_docker = (
        any("docker" in m.lower() for m in manifest_list)
        or os.path.exists(os.path.join(proj_dir, "Dockerfile"))
        or os.path.exists(os.path.join(proj_dir, "docker-compose.yml"))
    )

    rec_plugin_names = {p["name"].lower().replace("_", "-") for p in scan.get("recommended_plugins", [])}
    rec_skill_names = {s["name"].lower().replace("_", "-") for s in scan.get("recommended_skills", [])}
    rec_packages = set(rec_plugin_names)
    for rs in scan.get("recommended_skills", []):
        pkg = (rs.get("package") or "").lower().replace("_", "-")
        if pkg:
            rec_packages.add(pkg)

    newly_added_skill_names = {
        pa["name"].lower().replace("_", "-")
        for pa in provisioned_additions
        if pa.get("type") == "skill"
    }
    newly_added_plugin_names = {
        pa["name"].lower().replace("_", "-")
        for pa in provisioned_additions
        if pa.get("type") == "plugin"
    }

    catalog_skills_by_name = {
        s["name"].lower().replace("_", "-"): s for s in catalog.get("skills", [])
    }
    catalog_plugins_by_name = {
        p["name"].lower().replace("_", "-"): p for p in catalog.get("plugins", [])
    }

    detected_tech_tags: Set[str] = set()
    for tech in scan.get("technologies", []):
        detected_tech_tags.update(tech.get("tags", []))

    for s in installed_skills:
        s_norm = s["name"].lower().replace("_", "-")
        cat_entry = catalog_skills_by_name.get(s_norm) or catalog_skills_by_name.get(s["name"].lower())

        # Unmanaged project skills protection: never prune custom local skills not in the central catalog
        if not cat_entry:
            continue

        tier = cat_entry.get("tier", "stack")
        pkg = ((cat_entry.get("package") or "").lower().replace("_", "-"))

        # Core capabilities (.core marker file or tier == "core") are permanent guardrails and never pruned
        has_core = os.path.exists(os.path.join(s["path"], CORE_MARKER_FILE)) or (tier == "core")
        if has_core:
            continue

        if s_norm in newly_added_skill_names:
            continue

        is_orphaned = False
        reason = ""

        if final_pruning_mode == "aggressive":
            is_matched = (s_norm in rec_skill_names) or (pkg in rec_packages)
            if not is_matched:
                is_orphaned = True
                reason = f"Skill '{s['name']}' does not match any currently active technology in this workspace"
        else:
            # Soft mode: conservative retention, only flag clear negative domain contradictions
            s_tags = set(cat_entry.get("tags", []))
            is_mobile = bool(s_tags & {"mobile", "flutter", "android", "ios"}) or any(k in s_norm for k in ("flutter", "android", "ios"))
            is_firebase = "firebase" in s_tags or "firebase" in s_norm
            has_mobile = bool(detected_tech_tags & {"mobile", "flutter", "android", "ios"})
            has_fb = "firebase" in detected_tech_tags

            if is_mobile and not has_mobile:
                is_orphaned = True
                reason = f"Mobile skill '{s['name']}' installed, but no mobile manifests found in workspace"
            elif is_firebase and not has_fb:
                is_orphaned = True
                reason = f"Firebase skill '{s['name']}' installed, but no firebase manifests found in workspace"

        if is_orphaned:
            candidate = {
                "name": s["name"],
                "type": "skill",
                "path": s["path"],
                "reason": reason,
            }
            if final_auto_prune:
                try:
                    if os.path.islink(s["path"]):
                        os.unlink(s["path"])
                    else:
                        shutil.rmtree(s["path"])
                    pruned_items.append(candidate)
                except Exception as e:
                    candidate["error"] = str(e)
                    pruning_candidates.append(candidate)
            elif final_suggest_pruning:
                pruning_candidates.append(candidate)

    for p in installed_plugins:
        p_norm = p["name"].lower().replace("_", "-")
        cat_entry = catalog_plugins_by_name.get(p_norm) or catalog_plugins_by_name.get(p["name"].lower())

        # Unmanaged project plugins protection: never prune custom local plugins not in the central catalog
        if not cat_entry:
            continue

        tier = cat_entry.get("tier", "stack")

        # Core capabilities (.core marker file or tier == "core") are permanent guardrails and never pruned
        has_core = os.path.exists(os.path.join(p["path"], CORE_MARKER_FILE)) or (tier == "core")
        if has_core:
            continue

        if p_norm in newly_added_plugin_names:
            continue

        is_orphaned = False
        reason = ""

        if final_pruning_mode == "aggressive":
            is_matched = p_norm in rec_plugin_names
            if not is_matched:
                is_orphaned = True
                reason = f"Plugin '{p['name']}' does not match any currently active technology in this workspace"
        else:
            # Soft mode: conservative retention, only flag clear negative domain contradictions
            p_tags = set(cat_entry.get("tags", []))
            is_mobile = bool(p_tags & {"mobile", "flutter", "android", "ios"}) or any(k in p_norm for k in ("flutter", "android", "ios"))
            is_firebase = "firebase" in p_tags or "firebase" in p_norm
            has_mobile = bool(detected_tech_tags & {"mobile", "flutter", "android", "ios"})
            has_fb = "firebase" in detected_tech_tags

            if is_mobile and not has_mobile:
                is_orphaned = True
                reason = f"Mobile plugin '{p['name']}' installed, but no mobile manifests found in workspace"
            elif is_firebase and not has_fb:
                is_orphaned = True
                reason = f"Firebase plugin '{p['name']}' installed, but no firebase manifests found in workspace"

        if is_orphaned:
            candidate = {
                "name": p["name"],
                "type": "plugin",
                "path": p["path"],
                "reason": reason,
            }
            if final_auto_prune:
                try:
                    if os.path.islink(p["path"]):
                        os.unlink(p["path"])
                    else:
                        shutil.rmtree(p["path"])
                    pruned_items.append(candidate)
                except Exception as e:
                    candidate["error"] = str(e)
                    pruning_candidates.append(candidate)
            elif final_suggest_pruning:
                pruning_candidates.append(candidate)

    pruned_paths = {item["path"] for item in pruned_items if "path" in item}
    pruned_names = {item["name"] for item in pruned_items if "name" in item}
    remaining_skills = [s for s in installed_skills if s["path"] not in pruned_paths and s["name"] not in pruned_names]
    remaining_plugins = [p for p in installed_plugins if p["path"] not in pruned_paths and p["name"] not in pruned_names]

    synced_docs = sync_project_docs(proj_dir, active_harness, remaining_skills, remaining_plugins)

    return {
        "project_path": proj_dir,
        "harness": active_harness,
        "synced_docs": synced_docs,
        "library_path": catalog.get("library_path"),
        "scan_status": scan.get("status"),
        "manifests_found": scan.get("manifests_found", []),
        "technologies": scan.get("technologies", []),
        "installed_plugins": remaining_plugins,
        "installed_skills": remaining_skills,
        "additions_recommended": additions,
        "provisioned_additions": provisioned_additions,
        "auto_add_enabled": final_auto_add,
        "pruning_mode": final_pruning_mode,
        "pruning_candidates": pruning_candidates,
        "pruned_items": pruned_items,
        "suggest_pruning_enabled": final_suggest_pruning,
        "auto_prune_enabled": final_auto_prune,
    }


# ==============================================================================
# Core Capability Management (.core marker governance)
# ==============================================================================

def mark_core(
    name: str,
    library_path: Optional[str] = None,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Designates a skill, plugin, or package as Core by creating a .core marker file.
    Searches in:
    1. Active project workspace (.agents/skills/<name> or .agents/plugins/<name>)
    2. Central skills library (plugin dir, package dir, or skill dir)
    """
    norm = name.strip().lower().replace("_", "-")
    marked_paths: List[str] = []
    lib_path = resolve_library_path(library_path)

    proj_dir = None
    if project_path:
        proj_dir = os.path.abspath(os.path.expanduser(project_path))
    else:
        proj_dir = find_project_root()

    # 1. Check workspace
    if proj_dir and os.path.exists(proj_dir):
        ws_targets = [
            os.path.join(proj_dir, ".agents", "skills", name),
            os.path.join(proj_dir, ".agents", "skills", norm),
            os.path.join(proj_dir, ".agents", "plugins", name),
            os.path.join(proj_dir, ".agents", "plugins", norm),
            os.path.join(proj_dir, ".claude", "skills", name),
            os.path.join(proj_dir, ".claude", "skills", norm),
            os.path.join(proj_dir, ".claude", "plugins", name),
            os.path.join(proj_dir, ".claude", "plugins", norm),
        ]
        for t in ws_targets:
            if os.path.isdir(t):
                marker = os.path.join(t, CORE_MARKER_FILE)
                try:
                    with open(marker, "w", encoding="utf-8") as f:
                        f.write("# Quartermaster Core Capability\n")
                    if marker not in marked_paths:
                        marked_paths.append(marker)
                except Exception:
                    pass

    # 2. Check central library
    if os.path.exists(lib_path):
        for entry in os.listdir(lib_path):
            entry_norm = entry.lower().replace("_", "-")
            entry_path = os.path.join(lib_path, entry)
            if os.path.isdir(entry_path) and entry_norm == norm:
                marker = os.path.join(entry_path, CORE_MARKER_FILE)
                try:
                    with open(marker, "w", encoding="utf-8") as f:
                        f.write("# Quartermaster Core Capability\n")
                    if marker not in marked_paths:
                        marked_paths.append(marker)
                except Exception:
                    pass

        for pkg in os.listdir(lib_path):
            pkg_dir = os.path.join(lib_path, pkg)
            if not os.path.isdir(pkg_dir) or pkg.startswith("."):
                continue
            for root, dirs, files in os.walk(pkg_dir):
                if "SKILL.md" in files:
                    skill_name = os.path.basename(root).lower().replace("_", "-")
                    if skill_name == norm:
                        marker = os.path.join(root, CORE_MARKER_FILE)
                        try:
                            with open(marker, "w", encoding="utf-8") as f:
                                f.write("# Quartermaster Core Capability\n")
                            if marker not in marked_paths:
                                marked_paths.append(marker)
                        except Exception:
                            pass

    success = len(marked_paths) > 0
    if success and proj_dir and os.path.exists(proj_dir):
        h = detect_harness(proj_dir)
        sync_project_docs(proj_dir, h)

    return {
        "status": "marked" if success else "not_found",
        "name": name,
        "marked_paths": marked_paths,
        "message": (
            f"Designated '{name}' as Core ({len(marked_paths)} location(s) updated)."
            if success
            else f"Capability or package '{name}' not found in library or workspace."
        ),
    }


def unmark_core(
    name: str,
    library_path: Optional[str] = None,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Removes Core designation from a skill, plugin, or package by deleting its .core marker file.
    """
    norm = name.strip().lower().replace("_", "-")
    unmarked_paths: List[str] = []
    lib_path = resolve_library_path(library_path)

    proj_dir = None
    if project_path:
        proj_dir = os.path.abspath(os.path.expanduser(project_path))
    else:
        proj_dir = find_project_root()

    # 1. Check workspace
    if proj_dir and os.path.exists(proj_dir):
        ws_targets = [
            os.path.join(proj_dir, ".agents", "skills", name),
            os.path.join(proj_dir, ".agents", "skills", norm),
            os.path.join(proj_dir, ".agents", "plugins", name),
            os.path.join(proj_dir, ".agents", "plugins", norm),
            os.path.join(proj_dir, ".claude", "skills", name),
            os.path.join(proj_dir, ".claude", "skills", norm),
            os.path.join(proj_dir, ".claude", "plugins", name),
            os.path.join(proj_dir, ".claude", "plugins", norm),
        ]
        for t in ws_targets:
            if os.path.isdir(t):
                marker = os.path.join(t, CORE_MARKER_FILE)
                if os.path.exists(marker):
                    try:
                        os.remove(marker)
                        if marker not in unmarked_paths:
                            unmarked_paths.append(marker)
                    except Exception:
                        pass

    # 2. Check central library
    if os.path.exists(lib_path):
        for entry in os.listdir(lib_path):
            entry_norm = entry.lower().replace("_", "-")
            entry_path = os.path.join(lib_path, entry)
            if os.path.isdir(entry_path) and entry_norm == norm:
                marker = os.path.join(entry_path, CORE_MARKER_FILE)
                if os.path.exists(marker):
                    try:
                        os.remove(marker)
                        if marker not in unmarked_paths:
                            unmarked_paths.append(marker)
                    except Exception:
                        pass

        for pkg in os.listdir(lib_path):
            pkg_dir = os.path.join(lib_path, pkg)
            if not os.path.isdir(pkg_dir) or pkg.startswith("."):
                continue
            for root, dirs, files in os.walk(pkg_dir):
                if "SKILL.md" in files:
                    skill_name = os.path.basename(root).lower().replace("_", "-")
                    if skill_name == norm:
                        marker = os.path.join(root, CORE_MARKER_FILE)
                        if os.path.exists(marker):
                            try:
                                os.remove(marker)
                                if marker not in unmarked_paths:
                                    unmarked_paths.append(marker)
                            except Exception:
                                pass

    success = len(unmarked_paths) > 0
    if success and proj_dir and os.path.exists(proj_dir):
        h = detect_harness(proj_dir)
        sync_project_docs(proj_dir, h)

    return {
        "status": "unmarked" if success else "not_found",
        "name": name,
        "unmarked_paths": unmarked_paths,
        "message": (
            f"Removed Core designation from '{name}' ({len(unmarked_paths)} marker(s) removed)."
            if success
            else f"No .core marker file found for '{name}' in library or workspace."
        ),
    }


def list_core(
    library_path: Optional[str] = None,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Lists all capabilities designated as Core across the central library and current workspace.
    """
    lib_path = resolve_library_path(library_path)
    proj_dir = None
    if project_path:
        proj_dir = os.path.abspath(os.path.expanduser(project_path))
    else:
        proj_dir = find_project_root()

    catalog = get_catalog(lib_path)
    core_items: Dict[str, Dict[str, Any]] = {}

    # From Library Catalog
    for p in catalog.get("plugins", []):
        if p.get("tier") == "core":
            p_name = p["name"]
            core_items[p_name] = {
                "name": p_name,
                "type": "plugin",
                "package": p.get("package", p_name),
                "in_library": True,
                "in_workspace": False,
                "description": p.get("description", ""),
            }

    for s in catalog.get("skills", []):
        if s.get("tier") == "core":
            s_name = s["name"]
            core_items[s_name] = {
                "name": s_name,
                "type": "skill",
                "package": s.get("package", ""),
                "in_library": True,
                "in_workspace": False,
                "description": s.get("description", ""),
            }

    # From Workspace
    if proj_dir and os.path.exists(proj_dir):
        ws_skills_dirs = [
            os.path.join(proj_dir, ".agents", "skills"),
            os.path.join(proj_dir, ".claude", "skills"),
        ]
        for ws_skills_dir in ws_skills_dirs:
            if os.path.isdir(ws_skills_dir):
                for s_name in os.listdir(ws_skills_dir):
                    s_dir = os.path.join(ws_skills_dir, s_name)
                    if os.path.isdir(s_dir) and os.path.exists(os.path.join(s_dir, CORE_MARKER_FILE)):
                        if s_name in core_items:
                            core_items[s_name]["in_workspace"] = True
                        else:
                            core_items[s_name] = {
                                "name": s_name,
                                "type": "skill",
                                "package": "workspace-local",
                                "in_library": False,
                                "in_workspace": True,
                                "description": "Workspace-local core capability",
                            }

        ws_plugins_dirs = [
            os.path.join(proj_dir, ".agents", "plugins"),
            os.path.join(proj_dir, ".claude", "plugins"),
        ]
        for ws_plugins_dir in ws_plugins_dirs:
            if os.path.isdir(ws_plugins_dir):
                for p_name in os.listdir(ws_plugins_dir):
                    p_dir = os.path.join(ws_plugins_dir, p_name)
                    if os.path.isdir(p_dir) and os.path.exists(os.path.join(p_dir, CORE_MARKER_FILE)):
                        if p_name in core_items:
                            core_items[p_name]["in_workspace"] = True
                        else:
                            core_items[p_name] = {
                                "name": p_name,
                                "type": "plugin",
                                "package": "workspace-local",
                                "in_library": False,
                                "in_workspace": True,
                                "description": "Workspace-local core capability",
                            }

    items_list = sorted(core_items.values(), key=lambda x: (x["type"], x["name"]))
    return {
        "library_path": lib_path,
        "project_path": proj_dir,
        "total_core": len(items_list),
        "core_capabilities": items_list,
    }


# ==============================================================================
# Text Formatters for CLI Output
# ==============================================================================

def format_catalog_text(catalog: Dict[str, Any]) -> str:
    """Formats the catalog grouping naturally by package and plugin."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER ARMORY CATALOG")
    lines.append(f"  Skills Library: {catalog.get('library_path')}")
    lines.append(
        f"  Total Packages: {catalog.get('total_packages')} | "
        f"Plugins: {catalog.get('total_plugins')} | "
        f"Skills: {catalog.get('total_skills')}"
    )
    lines.append("=" * 80)

    packages = catalog.get("packages", {})
    for pkg_name, pkg_data in packages.items():
        is_plugin = pkg_data.get("is_plugin", False)
        skills = pkg_data.get("skills", [])
        p_badge = "[PLUGIN]" if is_plugin else "[PACKAGE]"

        lines.append("")
        lines.append(f"{p_badge} {pkg_name} ({len(skills)} skills)")
        if is_plugin and pkg_data.get("plugin_info"):
            desc = pkg_data["plugin_info"].get("description", "")
            if desc:
                lines.append(f"  Description: {desc}")
            comps = pkg_data["plugin_info"].get("components", [])
            if comps:
                lines.append(f"  Contains: {', '.join(comps)}")

        lines.append("  " + "-" * 70)
        for s in skills:
            name = s["name"]
            desc = s["description"]
            short_desc = desc if len(desc) <= 65 else desc[:62] + "..."
            tier_badge = f"<{s.get('tier', 'stack')}>"
            lines.append(f"    * {name:<35} {tier_badge:<8} : {short_desc}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("To equip into your project, run /quartermaster or /quartermaster sweep in chat.")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_scan_text(scan: Dict[str, Any]) -> str:
    """Formats project scan results into a clean reconnaissance report."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER RECONNAISSANCE REPORT")
    lines.append(f"  Target Workspace: {scan.get('project_path')}")
    lines.append(f"  Status: {scan.get('status')}")
    lines.append("=" * 80)

    if scan.get("is_brand_new"):
        lines.append("\n>>> BRAND-NEW / UNINITIALIZED PROJECT DETECTED <<<")
        dialogue = scan.get("scoping_dialogue", {})
        lines.append(f"Question: {dialogue.get('prompt')}")
        lines.append("Options:")
        for opt in dialogue.get("options", []):
            lines.append(f"  [ ] {opt['label']}")
        lines.append(f"\nGuiding Policy:\n  {dialogue.get('recommendation_on_unclear')}")

    manifests = scan.get("manifests_found", [])
    if manifests:
        lines.append("\n[Detected Manifests]")
        for m in manifests:
            lines.append(f"  * {m}")
    else:
        lines.append("\n[Detected Manifests]")
        lines.append("  (No standard project manifest files identified)")

    technologies = scan.get("technologies", [])
    if technologies:
        lines.append("\n[Identified Tech Stack & Frameworks]")
        for t in technologies:
            lines.append(f"  * {t['name']:<28} [{t['manifest']}] -> {t['details']}")

    plugins = scan.get("recommended_plugins", [])
    if plugins:
        lines.append(f"\n[Recommended Full Plugins ({len(plugins)})]")
        for p in plugins:
            lines.append(f"  * [PLUGIN] {p['name']:<30} Rationale: {p['reason']}")

    recs = scan.get("recommended_skills", [])
    lines.append(f"\n[Recommended Skills ({len(recs)})]")
    if recs:
        for r in recs:
            tier_badge = f"<{r.get('tier', 'stack')}>"
            p_badge = f"[{r.get('priority', 'High')}]"
            lines.append(f"  * [SKILL]  {r['name']:<35} {p_badge:<10} {tier_badge:<8} (pkg: {r['package']})")
            lines.append(f"             Rationale: {r['reason']}")

    lines.append("\n" + "=" * 80)
    lines.append("Status: Reconnaissance complete.")
    lines.append("Run /quartermaster in chat to outfit these capabilities.")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_provision_text(prov: Dict[str, Any]) -> str:
    """Formats provisioning results into an outfitting confirmation report."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER OUTFITTING REPORT")
    lines.append(f"  Destination Workspace: {prov.get('project_path')}")
    lines.append(f"  Total Assets Provisioned: {prov.get('provisioned_count')}")
    lines.append("=" * 80)

    provisioned = prov.get("provisioned", [])
    if provisioned:
        lines.append("\n[Provisioned Capabilities]")
        for p in provisioned:
            t_badge = "[PLUGIN]" if p["type"] == "plugin" else "[SKILL] "
            lines.append(
                f"  * {t_badge} {p['name']:<32} ({p['files_copied']} files) -> {p['destination']}"
            )

    not_found = prov.get("not_found", [])
    if not_found:
        lines.append("\n[Unmatched Requisitions]")
        for nf in not_found:
            lines.append(f"  ! [NOT FOUND] {nf}")

    lines.append("\n" + "=" * 80)
    lines.append("Status: Provisioning complete. Scoped capabilities are isolated and active.")
    lines.append("Agents in this workspace will automatically discover these capabilities.")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_sweep_text(swp: Dict[str, Any]) -> str:
    """Formats sweep audit results into a clear action report."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER SWEEP AUDIT REPORT")
    lines.append(f"  Target Workspace: {swp.get('project_path')}")
    lines.append(f"  Skills Library: {swp.get('library_path')}")
    p_mode = swp.get("pruning_mode", "aggressive").capitalize()
    strat_desc = "Strict Stack Alignment" if p_mode == "Aggressive" else "Conservative Retention"
    lines.append(f"  Pruning Strategy: {p_mode} ({strat_desc})")
    lines.append("=" * 80)

    harness_label = swp.get("harness", "agy")
    tgt_desc = ".claude/skills/" if harness_label == "claude" else ".agents/"

    i_plugins = swp.get("installed_plugins", [])
    i_skills = swp.get("installed_skills", [])
    lines.append(f"\n[Active Workspace Inventory] ({len(i_plugins)} plugins, {len(i_skills)} skills)")
    for p in i_plugins:
        p_loc = ".claude/plugins/" if harness_label == "claude" else ".agents/plugins/"
        lines.append(f"  * [PLUGIN] {p['name']:<30} in {p_loc}")
    for s in i_skills:
        s_loc = ".claude/skills/" if harness_label == "claude" else ".agents/skills/"
        lines.append(f"  * [SKILL]  {s['name']:<30} in {s_loc}")
    if not i_plugins and not i_skills:
        lines.append(f"  (No skills or plugins currently provisioned in {tgt_desc})")

    prov_additions = swp.get("provisioned_additions", [])
    additions = swp.get("additions_recommended", [])

    if prov_additions:
        lines.append(f"\n[Auto-Equipped New Capabilities ({len(prov_additions)})]")
        for pa in prov_additions:
            t_badge = f"[{pa['type'].upper()}]"
            lines.append(f"  * + {t_badge} {pa['name']:<30} -> {pa['destination']}")
    elif additions:
        lines.append(f"\n[Recommended New Capabilities ({len(additions)})]")
        for a in additions:
            t_badge = "[PLUGIN]" if a["type"] == "plugin" else "[SKILL] "
            p_badge = f"[{a.get('priority', 'High')}]"
            lines.append(f"  * + {t_badge} {a['name']:<30} {p_badge:<10}")
            lines.append(f"      Rationale: {a['reason']}")
    else:
        lines.append("\n[New Capabilities]")
        lines.append("  (All recommended capabilities for current stack are already provisioned)")

    pruned = swp.get("pruned_items", [])
    if pruned:
        lines.append(f"\n[Auto-Pruned Unneeded Capabilities ({len(pruned)})]")
        for pr in pruned:
            lines.append(f"  * - [{pr['type'].upper()}] {pr['name']:<30} (removed from {tgt_desc})")
            lines.append(f"      Note: {pr['reason']}")

    candidates = swp.get("pruning_candidates", [])
    if candidates:
        lines.append(f"\n[Suggested Unneeded Capabilities to Remove ({len(candidates)})] (Strategy: {p_mode})")
        for pr in candidates:
            lines.append(f"  * - [{pr['type'].upper()}] {pr['name']:<30}")
            lines.append(f"      Note: {pr['reason']}")
    elif not pruned and swp.get("suggest_pruning_enabled"):
        lines.append(f"\n[Suggested Unneeded Capabilities to Remove (0)] (Strategy: {p_mode})")
        lines.append("  (No obsolete or unneeded capabilities detected)")

    lines.append("\n" + "=" * 80)
    if prov_additions:
        lines.append(f"Status: Auto-equipped {len(prov_additions)} matching capabilities into {tgt_desc}.")
    elif additions:
        lines.append("Status: New capabilities detected. Run /quartermaster sweep to equip.")
    else:
        lines.append("Status: Workspace armory is fully aligned and up to date.")
    if candidates and not pruned:
        lines.append("Note: To auto-remove suggested unneeded tools, run /quartermaster sweep --auto-prune or toggle auto-prune in /quartermaster config.")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_import_text(res: Dict[str, Any]) -> str:
    """Formats git import result."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER LIBRARY IMPORT")
    lines.append("=" * 80)

    status = res.get("status")
    if status in ("installed", "exists"):
        t = "Plugin" if res.get("is_plugin") else "Package/Skill"
        if status == "installed":
            lines.append(f"Central Armory: Installed {t} '{res.get('name')}' into library.")
            lines.append(f"  * Location: {res.get('destination')}")
            lines.append(f"  * Skills Discovered: {res.get('skills_count')}")
        else:
            lines.append(f"Central Armory: '{res.get('name')}' already exists in library ({res.get('destination')}).")
            lines.append(f"  * Skills Available: {res.get('skills_count')}")

        target_s = res.get("target_skill")
        if target_s:
            lines.append(f"  * Targeted Capability: {target_s}")
        if res.get("is_core"):
            lines.append("  * Core Status: Designated as Core (.core marker attached)")

        proj = res.get("project_path")
        proj_prov = res.get("project_provisioned", [])
        if proj and proj_prov:
            lines.append(f"\nActive Project Outfitting ({proj}):")
            for p in proj_prov:
                t_badge = f"[{p['type'].upper()}]"
                lines.append(f"  * Auto-equipped {t_badge} {p['name']} -> {p['destination']}")
        elif proj:
            lines.append(f"\nActive Project ({proj}):")
            lines.append(f"  * Capability is now available in project.")
        else:
            lines.append("\nNote: Import ran outside of an active project workspace. Added to central library only.")
    else:
        lines.append(f"Error: {res.get('error')}")

    lines.append("=" * 80)
    return "\n".join(lines)


def format_core_list(data: Dict[str, Any]) -> str:
    """Formats the list of Core capabilities."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER CORE CAPABILITIES REPORT")
    lines.append(f"  Skills Library: {data.get('library_path')}")
    if data.get("project_path"):
        lines.append(f"  Active Workspace: {data.get('project_path')}")
    lines.append(f"  Total Core Capabilities: {data.get('total_core', 0)}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(
        "Core capabilities are permanent workflow guardrails. They are auto-equipped"
    )
    lines.append(
        "into every project and are protected from pruning during sweeps."
    )
    lines.append("")

    items = data.get("core_capabilities", [])
    if not items:
        lines.append("No capabilities are currently designated as Core.")
        lines.append("Use /quartermaster core add <name> to designate a core capability.")
    else:
        lines.append(f"{'Capability':<28} {'Type':<10} {'Source':<18} {'Status'}")
        lines.append("-" * 75)
        for item in items:
            name = item["name"]
            c_type = item["type"].capitalize()
            in_lib = item.get("in_library", False)
            in_ws = item.get("in_workspace", False)
            if in_lib and in_ws:
                src = "Library + Project"
                status = "Active & Protected"
            elif in_ws:
                src = "Project Only"
                status = "Active & Protected"
            else:
                src = "Library Armory"
                status = "Ready to equip"
            lines.append(f"{name:<28} {c_type:<10} {src:<18} {status}")

    lines.append("")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_core_add(data: Dict[str, Any]) -> str:
    """Formats core designation confirmation."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER CORE DESIGNATION")
    lines.append("=" * 80)
    lines.append(data.get("message", ""))
    paths = data.get("marked_paths", [])
    if paths:
        lines.append("\nUpdated Marker Locations:")
        for p in paths:
            lines.append(f"  + {p}")
        lines.append("\nThis capability is now protected from pruning and auto-equipped on setup.")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_core_rm(data: Dict[str, Any]) -> str:
    """Formats core designation removal confirmation."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER CORE DESIGNATION REMOVAL")
    lines.append("=" * 80)
    lines.append(data.get("message", ""))
    paths = data.get("unmarked_paths", [])
    if paths:
        lines.append("\nRemoved Markers:")
        for p in paths:
            lines.append(f"  - {p}")
        lines.append("\nThis capability will now be subject to standard stack pruning during sweeps.")
    lines.append("=" * 80)
    return "\n".join(lines)


# ==============================================================================
# CLI Entry Point
# ==============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quartermaster: Project Onboarding & Skill Provisioning Armory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--scan",
        nargs="?",
        const=".",
        metavar="PATH",
        help="Scan project directory at PATH (default: current directory) and recommend tailored capabilities.",
    )
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Discover and display all available armory plugins and skills from the configured skills-library.",
    )
    parser.add_argument(
        "--provision",
        metavar="PATH",
        help="Target project directory to provision capabilities into (.agents/plugins/ or .agents/skills/).",
    )
    parser.add_argument(
        "--skills",
        metavar="NAME1,NAME2,...",
        help="Comma-separated list of skill or package/plugin names to provision.",
    )
    parser.add_argument(
        "--plugins",
        metavar="PLUGIN1,...",
        help="Comma-separated list of plugin names to provision into .agents/plugins/.",
    )
    parser.add_argument(
        "--sweep",
        nargs="?",
        const=".",
        metavar="PATH",
        help="Audit current workspace tech, review installed skills, and cross-reference library for additions/pruning.",
    )
    parser.add_argument(
        "--auto-prune",
        action="store_true",
        help="In sweep mode, automatically remove unneeded skills from .agents/.",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="In sweep mode, suppress pruning suggestions (additions only).",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="In sweep mode, enforce strict stack alignment (flag all installed tools not matched by current stack).",
    )
    parser.add_argument(
        "--soft",
        action="store_true",
        help="In sweep mode, use conservative retention (preserve auxiliary or cross-cutting tools).",
    )
    parser.add_argument(
        "--no-auto-add",
        action="store_true",
        help="In sweep mode, do not automatically equip newly recommended capabilities (recommendation only).",
    )
    parser.add_argument(
        "--import",
        dest="import_url",
        metavar="GIT_URL",
        help="Clone and install a skill or plugin git repository directly into your central skills library (and active project).",
    )
    parser.add_argument(
        "--project",
        metavar="PATH",
        help="Target project directory for provisioning during import or sweep.",
    )
    parser.add_argument(
        "--no-project",
        action="store_true",
        help="In import mode, skip project outfitting (import to central library only).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite when importing into library.",
    )
    parser.add_argument(
        "--core",
        action="store_true",
        help="In import mode, designate the imported capability as Core (.core marker attached).",
    )
    parser.add_argument(
        "--harness",
        choices=["agy", "claude", "codex", "universal", "auto"],
        default="auto",
        help="Agent harness target: agy, claude, codex, universal, or auto (default: auto).",
    )
    parser.add_argument(
        "--sync-docs",
        action="store_true",
        help="Synchronize project agent context documentation (CLAUDE.md / AGENTS.md).",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Launch interactive settings configuration or display current configuration.",
    )
    parser.add_argument(
        "--config-get",
        metavar="KEY",
        help="Get the value of a specific configuration setting (e.g. skills-library, auto-prune, suggest-pruning).",
    )
    parser.add_argument(
        "--config-set",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Set a configuration setting (e.g. --config-set auto-prune true).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw machine-readable JSON instead of formatted text.",
    )
    parser.add_argument(
        "--core-add",
        metavar="NAME",
        help="Designate a package, plugin, or skill as Core by attaching a .core marker file (protects from sweep pruning and auto-equips).",
    )
    parser.add_argument(
        "--core-rm",
        metavar="NAME",
        help="Remove Core designation from a package, plugin, or skill by deleting its .core marker file.",
    )
    parser.add_argument(
        "--core-list",
        action="store_true",
        help="List all capabilities designated as Core across the central armory and current workspace.",
    )
    parser.add_argument(
        "--library",
        metavar="PATH",
        help="Override skills-library directory path for this execution.",
    )

    # Defensive filter: clean extraneous 'sweep' positional arguments
    raw_args = sys.argv[1:]
    filtered_args = []
    seen_sweep = False
    for a in raw_args:
        if a == "--sweep":
            seen_sweep = True
            filtered_args.append(a)
        elif a == "sweep" and (seen_sweep or (filtered_args and filtered_args[-1] == "--sweep")):
            # Redundant literal 'sweep' argument
            continue
        elif a == "sweep" and not filtered_args:
            # Invoked as `quartermaster.py sweep` -> convert to `--sweep .`
            filtered_args.extend(["--sweep", "."])
            seen_sweep = True
        else:
            filtered_args.append(a)

    args = parser.parse_args(filtered_args)

    # Context Documentation Sync
    if args.sync_docs:
        proj = args.project if args.project else (find_project_root() or os.getcwd())
        active_h = detect_harness(proj, args.harness)
        docs = sync_project_docs(proj, active_h)
        if args.json:
            print(json.dumps(docs, indent=2))
        else:
            print("Synchronized project documentation:")
            for h, p in docs.items():
                if p:
                    print(f"  * [{h.upper()}] {p}")
        return 0

    # Import Git Repo into Central Library & Active Project
    if args.import_url:
        proj_arg = None
        if not args.no_project:
            proj_arg = args.project if args.project else find_project_root()

        res = import_library_asset(
            git_url=args.import_url,
            library_path=args.library,
            project_path=proj_arg,
            force=args.force,
            is_core=args.core,
            harness=args.harness,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(format_import_text(res))
        return 0 if res.get("status") in ("installed", "exists") else 1

    # Settings Actions
    if args.config_get:
        val = get_config_value(args.config_get)
        if args.json:
            print(json.dumps({args.config_get: val}, indent=2))
        else:
            print(val if val is not None else "")
        return 0

    if args.config_set:
        key, val = args.config_set
        cfg = set_config_value(key, val)
        if args.json:
            print(json.dumps(cfg, indent=2))
        else:
            print(f"Set '{key}' = {cfg.get(key)}")
        return 0

    if args.config:
        if args.json:
            print(json.dumps(load_config(), indent=2))
        else:
            interactive_config()
        return 0

    # Core Designation Actions
    if args.core_add:
        proj_arg = args.project if args.project else find_project_root()
        res = mark_core(args.core_add, library_path=args.library, project_path=proj_arg)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(format_core_add(res))
        return 0 if res.get("status") == "marked" else 1

    if args.core_rm:
        proj_arg = args.project if args.project else find_project_root()
        res = unmark_core(args.core_rm, library_path=args.library, project_path=proj_arg)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(format_core_rm(res))
        return 0 if res.get("status") == "unmarked" else 1

    if args.core_list:
        proj_arg = args.project if args.project else find_project_root()
        res = list_core(library_path=args.library, project_path=proj_arg)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(format_core_list(res))
        return 0

    # If no action flag passed, show help
    if (
        not args.catalog
        and args.scan is None
        and not args.provision
        and args.sweep is None
        and not args.core_list
    ):
        parser.print_help()
        return 0

    try:
        if args.catalog:
            catalog = get_catalog(args.library)
            if args.json:
                print(json.dumps(catalog, indent=2))
            else:
                print(format_catalog_text(catalog))
            return 0

        if args.scan is not None:
            scan_res = detect_stack(args.scan, library_path=args.library)
            if args.json:
                print(json.dumps(scan_res, indent=2))
            else:
                print(format_scan_text(scan_res))
            return 0

        if args.sweep is not None:
            suggest_prune = False if args.no_prune else None
            auto_p = True if args.auto_prune else None
            auto_a = False if args.no_auto_add else None
            p_mode = None
            if args.aggressive:
                p_mode = "aggressive"
            elif args.soft:
                p_mode = "soft"

            swp_res = sweep_project(
                project_path=args.sweep,
                library_path=args.library,
                auto_add=auto_a,
                suggest_pruning=suggest_prune,
                auto_prune=auto_p,
                pruning_mode=p_mode,
                harness=args.harness,
            )
            if args.json:
                print(json.dumps(swp_res, indent=2))
            else:
                print(format_sweep_text(swp_res))
            return 0

        if args.provision:
            items = []
            force_type = None
            if args.plugins:
                items.extend([p.strip() for p in args.plugins.split(",") if p.strip()])
                force_type = "plugin"
            if args.skills:
                items.extend([s.strip() for s in args.skills.split(",") if s.strip()])
                if force_type == "plugin":
                    force_type = None

            if not items:
                print(
                    "Error: --skills or --plugins is required when --provision is specified.",
                    file=sys.stderr,
                )
                return 1

            prov_res = provision_assets(
                project_path=args.provision,
                asset_names=items,
                library_path=args.library,
                force_type=force_type,
                harness=args.harness,
            )
            if args.json:
                print(json.dumps(prov_res, indent=2))
            else:
                print(format_provision_text(prov_res))
            return 0

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        else:
            print(f"Quartermaster error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
