#!/usr/bin/env python3
"""
Quartermaster - Project-Scoped Capability Provisioner & Armory Engine
References an external central skills library, plucks only project-relevant skills and plugins
into `<project_path>/.agents/`, scopes brand-new projects, and provides sweep audits with
configurable pruning governance and in-flow git library imports.

Features:
- External central library referencing (default: ~/.gemini/skills-library)
- Dynamic in-flow git imports (--import <git-url>) directly into central library
- Dual provisioning: Full plugins (.agents/plugins/) and standalone skills (.agents/skills/)
- Clean capability tiers: Core AI-SDLC (universal) vs Stack-Specific
- Interactive brand-new project scoping with "I'm not sure yet" fallback
- Project sweep (--sweep) for ongoing audits (additions and pruning)
- Configurable pruning settings: suggest-pruning (default: true) and auto-prune (default: false)

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
from typing import Any, Dict, List, Optional, Set, Tuple

# Configuration Paths
GLOBAL_CONFIG_DIR = os.path.expanduser("~/.gemini/quartermaster")
GLOBAL_CONFIG_FILE = os.path.join(GLOBAL_CONFIG_DIR, "config.json")
FALLBACK_CONFIG_FILE = os.path.expanduser("~/.quartermaster/config.json")

DEFAULT_LIBRARY_PATH = os.path.expanduser("~/.gemini/skills-library")

DEFAULT_CONFIG: Dict[str, Any] = {
    "skills-library": DEFAULT_LIBRARY_PATH,
    "auto-add": True,
    "suggest-pruning": True,
    "auto-prune": False,
}

# Universal Core AI-SDLC Capabilities (apply to any software project regardless of language/stack)
CORE_AI_SDLC_PACKAGES = {"spark-skills", "agora-adlc", "conductor"}
CORE_AI_SDLC_SKILLS = {
    "spec",
    "pm",
    "spec-split",
    "wayfinder",
    "pr-review",
    "pr-ready",
    "preflight",
    "adversary",
    "adlc-plan",
    "adlc-constitution",
    "adlc-clarify",
    "adlc-amend",
    "adlc-explore",
    "adlc-init",
    "adlc-test",
    "adlc-verify",
    "adlc-critique",
    "adlc-run",
    "adlc-audit",
    "conductor-setup",
    "conductor-new-track",
    "conductor-implement",
    "conductor-status",
    "conductor-review",
    "conductor-switch",
    "conductor-revert",
    "critic",
    "reviewer",
    "planner",
    "tester",
}


# ==============================================================================
# Configuration & Settings Management
# ==============================================================================

def get_active_config_file() -> str:
    """Returns the primary config file path."""
    if os.path.exists(GLOBAL_CONFIG_FILE):
        return GLOBAL_CONFIG_FILE
    if os.path.exists(FALLBACK_CONFIG_FILE):
        return FALLBACK_CONFIG_FILE
    return GLOBAL_CONFIG_FILE


def load_config() -> Dict[str, Any]:
    """Loads Quartermaster settings from disk or returns defaults."""
    cfg = dict(DEFAULT_CONFIG)
    cfg_file = get_active_config_file()
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict[str, Any]) -> str:
    """Saves Quartermaster settings to disk."""
    cfg_file = GLOBAL_CONFIG_FILE
    os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return cfg_file


def get_config_value(key: str) -> Optional[Any]:
    """Retrieves a specific configuration value."""
    cfg = load_config()
    return cfg.get(key)


def set_config_value(key: str, value: Any) -> Dict[str, Any]:
    """Sets a specific configuration value and persists it."""
    cfg = load_config()
    # Normalize booleans if passed as string
    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes", "on"):
            value = True
        elif value.lower() in ("false", "0", "no", "off"):
            value = False
    cfg[key] = value
    save_config(cfg)
    return cfg


def resolve_library_path(custom_path: Optional[str] = None) -> str:
    """
    Resolve the active Quartermaster library path:
    1. CLI argument (--library)
    2. Configured 'skills-library' setting
    3. Default location (~/.gemini/skills-library)
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
    print(f"  * suggest-pruning = {cfg.get('suggest-pruning')} (suggest unneeded skills to remove during sweep)")
    print(f"  * auto-prune      = {cfg.get('auto-prune')} (automatically remove unneeded skills during sweep)")

    print("-" * 80)
    print("Options:")
    print("  1. Update 'skills-library' path")
    print(f"  2. Toggle 'auto-add' (currently: {cfg.get('auto-add', True)})")
    print(f"  3. Toggle 'suggest-pruning' (currently: {cfg.get('suggest-pruning')})")
    print(f"  4. Toggle 'auto-prune' (currently: {cfg.get('auto-prune')})")
    print("  5. Reset settings to default")
    print("  6. Exit")

    choice = input("\nEnter choice [1-6] (default: 6): ").strip()
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
        save_config(dict(DEFAULT_CONFIG))
        print("\nSettings reset to default.")
    else:
        print("\nNo changes made.")


# ==============================================================================
# In-Flow Library Import via Git URL
# ==============================================================================

def import_library_asset(
    git_url: str,
    library_path: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Clones a skill or plugin repository directly into the central skills library.
    Allows developers to expand their armory without breaking flow.
    """
    lib_dir = resolve_library_path(library_path)
    os.makedirs(lib_dir, exist_ok=True)

    cleaned_url = git_url.strip().rstrip("/")
    repo_name = os.path.basename(cleaned_url)
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    dest_dir = os.path.join(lib_dir, repo_name)
    if os.path.exists(dest_dir):
        if not force:
            return {
                "status": "exists",
                "message": f"Asset '{repo_name}' already exists in library: {dest_dir}. Use --force to overwrite.",
                "name": repo_name,
                "destination": dest_dir,
            }
        shutil.rmtree(dest_dir)

    cmd = ["git", "clone", "--depth", "1", git_url, dest_dir]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "error": f"Failed to clone repository: {e.stderr or e.stdout}",
            "git_url": git_url,
        }

    is_plugin = os.path.exists(os.path.join(dest_dir, "plugin.json"))
    skill_files = glob.glob(os.path.join(dest_dir, "**", "SKILL.md"), recursive=True)

    return {
        "status": "installed",
        "name": repo_name,
        "is_plugin": is_plugin,
        "skills_count": len(skill_files),
        "destination": dest_dir,
        "library_path": lib_dir,
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

            p_tier = "core" if pkg.lower() in CORE_AI_SDLC_PACKAGES else "stack"

            plugin_info = {
                "name": plugin_name,
                "package": pkg,
                "tier": p_tier,
                "version": plugin_version,
                "description": plugin_desc,
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

            s_tier = "core" if (name.lower() in CORE_AI_SDLC_SKILLS or pkg.lower() in CORE_AI_SDLC_PACKAGES) else "stack"

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

def detect_stack(project_path: str) -> Dict[str, Any]:
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

    # Flutter / Dart (pubspec.yaml)
    pubspec_path = os.path.join(proj_dir, "pubspec.yaml")
    if os.path.exists(pubspec_path):
        manifests_found.append("pubspec.yaml")
        content = safe_read(pubspec_path)
        tech_details = ["Dart"]
        if "flutter:" in content or "sdk: flutter" in content:
            tech_details.append("Flutter SDK")

        technologies.append({
            "name": "Flutter / Dart",
            "manifest": "pubspec.yaml",
            "details": ", ".join(tech_details),
        })

        add_plugin_rec("flutter", "stack", "Flutter architecture, responsive layouts, and Dart unit testing")
        add_skill_rec("flutter-apply-architecture-best-practices", "flutter", "stack", "Architecture and structure standards for Flutter")
        add_skill_rec("dart-add-unit-test", "flutter", "core", "Unit test doubles, fixtures, and assertions for Dart")
        add_skill_rec("flutter-build-responsive-layout", "flutter", "stack", "Responsive layout patterns across devices")

        if "http:" in content or "dio:" in content:
            add_skill_rec("flutter-use-http-package", "flutter", "stack", "HTTP networking patterns")
        if "json_annotation:" in content or "json_serializable:" in content:
            add_skill_rec("flutter-implement-json-serialization", "flutter", "stack", "JSON code generation and serialization")
        if "go_router:" in content or "auto_route:" in content:
            add_skill_rec("flutter-setup-declarative-routing", "flutter", "stack", "Declarative routing patterns")

    # Android Native
    android_dir = os.path.join(proj_dir, "android")
    has_gradle = (
        os.path.exists(os.path.join(proj_dir, "build.gradle"))
        or os.path.exists(os.path.join(proj_dir, "build.gradle.kts"))
        or (os.path.exists(android_dir) and os.path.isdir(android_dir))
    )
    if has_gradle:
        manifest_name = "android/ or build.gradle"
        manifests_found.append(manifest_name)
        technologies.append({
            "name": "Android Native / Gradle",
            "manifest": manifest_name,
            "details": "Android Gradle build system and device tools",
        })
        add_plugin_rec("android-cli-plugin", "stack", "Android CLI management, emulators, logcat, and APK builds")

    # Node.js / Web / TypeScript (package.json)
    package_json_path = os.path.join(proj_dir, "package.json")
    if os.path.exists(package_json_path):
        manifests_found.append("package.json")
        content = safe_read(package_json_path)
        frameworks = []

        if "react" in content:
            frameworks.append("React")
        if "next" in content:
            frameworks.append("Next.js")
        if "vue" in content:
            frameworks.append("Vue")
        if "svelte" in content:
            frameworks.append("Svelte")
        if "tailwind" in content or os.path.exists(os.path.join(proj_dir, "tailwind.config.js")):
            frameworks.append("Tailwind CSS")
        if "vite" in content:
            frameworks.append("Vite")
        if "express" in content:
            frameworks.append("Express")
        if "fastify" in content:
            frameworks.append("Fastify")
        if os.path.exists(os.path.join(proj_dir, "tsconfig.json")):
            frameworks.append("TypeScript")

        details_str = ", ".join(frameworks) if frameworks else "JavaScript/Node.js"
        technologies.append({
            "name": "Web & Node.js Platform",
            "manifest": "package.json",
            "details": details_str,
        })

        add_skill_rec("impeccable", "impeccable", "stack", "Frontend design craft, layout polish, UX audit, and component refinement")
        add_plugin_rec("modern-web-guidance-plugin", "stack", "Modern web architecture standards, clean idioms, and web performance")
        add_plugin_rec("chrome-devtools-plugin", "stack", "Chrome DevTools MCP runtime inspection and debugging")

    # Chrome Extension (manifest.json)
    manifest_json_path = os.path.join(proj_dir, "manifest.json")
    if os.path.exists(manifest_json_path):
        content = safe_read(manifest_json_path)
        if "manifest_version" in content:
            manifests_found.append("manifest.json")
            technologies.append({
                "name": "Chrome Extension",
                "manifest": "manifest.json",
                "details": "Chrome Extension manifest (v2/v3)",
            })
            add_skill_rec("chrome-extensions", "modern-web-guidance-plugin", "stack", "Chrome extension architecture, permissions, and background workers")
            add_plugin_rec("chrome-devtools-plugin", "stack", "DevTools inspection of popups and content scripts")

    # Firebase (firebase.json, .firebaserc)
    firebase_json_path = os.path.join(proj_dir, "firebase.json")
    firebaserc_path = os.path.join(proj_dir, ".firebaserc")
    if os.path.exists(firebase_json_path) or os.path.exists(firebaserc_path):
        manifest_name = "firebase.json" if os.path.exists(firebase_json_path) else ".firebaserc"
        manifests_found.append(manifest_name)
        technologies.append({
            "name": "Firebase Platform",
            "manifest": manifest_name,
            "details": "Cloud Firestore, Auth, Hosting, and Security Rules",
        })
        add_plugin_rec("firebase", "stack", "Firebase Firestore, Auth, Hosting, and Security Rules")
        add_skill_rec("firebase-basics", "firebase", "stack", "Firebase CLI, project initialization, and emulator suite")
        add_skill_rec("firebase-firestore", "firebase", "stack", "Firestore schema design, querying, and transactions")
        add_skill_rec("firebase-security-rules-auditor", "firebase", "core", "Audit and hardening of Firestore & Cloud Storage security rules")

    # Python (pyproject.toml, requirements.txt, Pipfile, setup.py)
    py_manifests = [
        m for m in [
            os.path.join(proj_dir, "pyproject.toml"),
            os.path.join(proj_dir, "requirements.txt"),
            os.path.join(proj_dir, "Pipfile"),
            os.path.join(proj_dir, "setup.py"),
        ]
        if os.path.exists(m)
    ]
    if py_manifests:
        primary_py = os.path.basename(py_manifests[0])
        manifests_found.append(primary_py)
        combined_py = " ".join([safe_read(m) for m in py_manifests]).lower()

        py_details = ["Python 3"]
        if "fastapi" in combined_py:
            py_details.append("FastAPI")
        if "flask" in combined_py:
            py_details.append("Flask")
        if "django" in combined_py:
            py_details.append("Django")

        technologies.append({
            "name": "Python Environment",
            "manifest": primary_py,
            "details": ", ".join(py_details),
        })

        add_skill_rec("uv", "science", "stack", "Ultra-fast Python package management and virtual environments via uv")

        if any(kw in combined_py for kw in ["antigravity", "google-genai", "gemini"]) or os.path.exists(os.path.join(proj_dir, "agents")):
            add_plugin_rec("google-antigravity-sdk", "stack", "Antigravity SDK for multi-agent workflows, subagents, and tool execution")

    # Containers / Docker
    if os.path.exists(os.path.join(proj_dir, "Dockerfile")) or os.path.exists(os.path.join(proj_dir, "docker-compose.yml")):
        doc_manifest = "Dockerfile" if os.path.exists(os.path.join(proj_dir, "Dockerfile")) else "docker-compose.yml"
        manifests_found.append(doc_manifest)
        technologies.append({
            "name": "Containerization / Docker",
            "manifest": doc_manifest,
            "details": "Container build specifications and multi-service definitions",
        })
        add_plugin_rec("cloudrun", "stack", "Serverless container deployment and traffic routing")

    # Universal Core AI-SDLC Baseline (Equipped for any repository)
    add_skill_rec("spec", "spark-skills", "core", "Spec-driven engineering: write clear functional specs before writing code", priority="Baseline")
    add_skill_rec("pr-review", "spark-skills", "core", "Adversarial pull request critique, bug detection, and regression guard", priority="Baseline")
    add_skill_rec("preflight", "spark-skills", "core", "Pre-commit sanity verification, lint checks, and test runner assurance", priority="Baseline")
    add_skill_rec("wayfinder", "spark-skills", "core", "Deep codebase navigation, dependency mapping, and orientation", priority="Baseline")

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
                "only universal Core AI-SDLC guardrails (spec-driven design, adversarial PR review, preflight checks), "
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
) -> Dict[str, Any]:
    """
    Provisions requested assets into `<project_path>/.agents/`.
    - Full plugins &rarr; `<project_path>/.agents/plugins/<plugin_name>/`
    - Standalone skills &rarr; `<project_path>/.agents/skills/<skill_name>/`
    """
    proj_dir = os.path.abspath(os.path.expanduser(project_path))
    os.makedirs(proj_dir, exist_ok=True)

    target_skills_dir = os.path.join(proj_dir, ".agents", "skills")
    target_plugins_dir = os.path.join(proj_dir, ".agents", "plugins")

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
            dest_dir = os.path.join(target_plugins_dir, canonical_name)

            if dest_dir not in seen_destinations:
                seen_destinations.add(dest_dir)
                os.makedirs(target_plugins_dir, exist_ok=True)
                src_dir = plugin["source_dir"]
                shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)

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
                shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)

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
                    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
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

    return {
        "project_path": proj_dir,
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
) -> Dict[str, Any]:
    """
    Audits the workspace:
    1. Checks active inventory in `.agents/`.
    2. Re-scans manifests and dependencies.
    3. Identifies newly relevant additions:
       - If auto_add is True (default): automatically provisions them into `.agents/`.
    4. Evaluates unneeded stack tools:
       - If suggest_pruning is True: lists them as removal recommendations.
       - If auto_prune is True: automatically uninstalls them from `.agents/`.
    """
    cfg = load_config()
    final_auto_add = auto_add if auto_add is not None else cfg.get("auto-add", True)
    final_suggest_pruning = suggest_pruning if suggest_pruning is not None else cfg.get("suggest-pruning", True)
    final_auto_prune = auto_prune if auto_prune is not None else cfg.get("auto-prune", False)

    proj_dir = os.path.abspath(os.path.expanduser(project_path))
    scan = detect_stack(proj_dir)
    catalog = get_catalog(library_path)

    target_skills_dir = os.path.join(proj_dir, ".agents", "skills")
    target_plugins_dir = os.path.join(proj_dir, ".agents", "plugins")

    installed_skills: List[Dict[str, Any]] = []
    if os.path.exists(target_skills_dir):
        for s_name in sorted(os.listdir(target_skills_dir)):
            s_path = os.path.join(target_skills_dir, s_name)
            if os.path.isdir(s_path):
                installed_skills.append({
                    "name": s_name,
                    "path": s_path,
                    "type": "skill",
                })

    installed_plugins: List[Dict[str, Any]] = []
    if os.path.exists(target_plugins_dir):
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
    catalog_skills_by_name = {s["name"].lower(): s for s in catalog.get("skills", [])}

    for s in installed_skills:
        s_name = s["name"].lower()
        cat_entry = catalog_skills_by_name.get(s_name)
        tier = cat_entry.get("tier", "stack") if cat_entry else "stack"
        pkg = (cat_entry.get("package") or "").lower() if cat_entry else s_name

        # Core AI-SDLC skills are never pruned
        if tier == "core" or s_name in CORE_AI_SDLC_SKILLS or pkg in CORE_AI_SDLC_PACKAGES:
            continue

        is_orphaned = False
        reason = ""

        if ("flutter" in pkg or "flutter" in s_name) and "pubspec.yaml" not in manifest_list:
            is_orphaned = True
            reason = "Flutter skill installed but no pubspec.yaml found in workspace"
        elif ("firebase" in pkg or "firebase" in s_name) and not any("firebase" in m for m in manifest_list):
            is_orphaned = True
            reason = "Firebase skill installed but no firebase.json / .firebaserc found in workspace"
        elif ("android" in pkg or "android" in s_name) and not any("android" in m or "gradle" in m for m in manifest_list):
            is_orphaned = True
            reason = "Android CLI tool installed but no Android/Gradle manifests found"

        if is_orphaned:
            candidate = {
                "name": s["name"],
                "type": "skill",
                "path": s["path"],
                "reason": reason,
            }
            if final_auto_prune:
                try:
                    shutil.rmtree(s["path"])
                    pruned_items.append(candidate)
                except Exception as e:
                    candidate["error"] = str(e)
                    pruning_candidates.append(candidate)
            elif final_suggest_pruning:
                pruning_candidates.append(candidate)

    catalog_plugins_by_name = {p["name"].lower(): p for p in catalog.get("plugins", [])}
    for p in installed_plugins:
        p_name = p["name"].lower()
        cat_entry = catalog_plugins_by_name.get(p_name)
        tier = cat_entry.get("tier", "stack") if cat_entry else "stack"

        # Core AI-SDLC plugins are never pruned
        if tier == "core" or p_name in CORE_AI_SDLC_PACKAGES:
            continue

        is_orphaned = False
        reason = ""

        if "flutter" in p_name and "pubspec.yaml" not in manifest_list:
            is_orphaned = True
            reason = "Flutter plugin installed but no pubspec.yaml found in workspace"
        elif "firebase" in p_name and not any("firebase" in m for m in manifest_list):
            is_orphaned = True
            reason = "Firebase plugin installed but no firebase.json / .firebaserc found in workspace"
        elif "android" in p_name and not any("android" in m or "gradle" in m for m in manifest_list):
            is_orphaned = True
            reason = "Android CLI plugin installed but no Android/Gradle manifests found"

        if is_orphaned:
            candidate = {
                "name": p["name"],
                "type": "plugin",
                "path": p["path"],
                "reason": reason,
            }
            if final_auto_prune:
                try:
                    shutil.rmtree(p["path"])
                    pruned_items.append(candidate)
                except Exception as e:
                    candidate["error"] = str(e)
                    pruning_candidates.append(candidate)
            elif final_suggest_pruning:
                pruning_candidates.append(candidate)

    return {
        "project_path": proj_dir,
        "library_path": catalog.get("library_path"),
        "scan_status": scan.get("status"),
        "manifests_found": scan.get("manifests_found", []),
        "technologies": scan.get("technologies", []),
        "installed_plugins": installed_plugins,
        "installed_skills": installed_skills,
        "additions_recommended": additions,
        "provisioned_additions": provisioned_additions,
        "auto_add_enabled": final_auto_add,
        "pruning_candidates": pruning_candidates,
        "pruned_items": pruned_items,
        "suggest_pruning_enabled": final_suggest_pruning,
        "auto_prune_enabled": final_auto_prune,
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
    lines.append("=" * 80)

    i_plugins = swp.get("installed_plugins", [])
    i_skills = swp.get("installed_skills", [])
    lines.append(f"\n[Active Workspace Inventory] ({len(i_plugins)} plugins, {len(i_skills)} skills)")
    for p in i_plugins:
        lines.append(f"  * [PLUGIN] {p['name']:<30} in .agents/plugins/")
    for s in i_skills:
        lines.append(f"  * [SKILL]  {s['name']:<30} in .agents/skills/")
    if not i_plugins and not i_skills:
        lines.append("  (No skills or plugins currently provisioned in .agents/)")

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
            lines.append(f"  * - [{pr['type'].upper()}] {pr['name']:<30} (removed from .agents/)")
            lines.append(f"      Note: {pr['reason']}")

    candidates = swp.get("pruning_candidates", [])
    if candidates:
        lines.append(f"\n[Suggested Unneeded Capabilities to Remove ({len(candidates)})]")
        for pr in candidates:
            lines.append(f"  * - [{pr['type'].upper()}] {pr['name']:<30}")
            lines.append(f"      Note: {pr['reason']}")
    elif not pruned and swp.get("suggest_pruning_enabled"):
        lines.append("\n[Suggested Unneeded Capabilities to Remove (0)]")
        lines.append("  (No obsolete or unneeded capabilities detected)")

    lines.append("\n" + "=" * 80)
    if prov_additions:
        lines.append(f"Status: Auto-equipped {len(prov_additions)} matching capabilities into .agents/.")
    elif additions:
        lines.append("Status: New capabilities detected. Run /quartermaster sweep to equip.")
    else:
        lines.append("Status: Workspace armory is fully aligned and up to date.")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_import_text(res: Dict[str, Any]) -> str:
    """Formats git import result."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER LIBRARY IMPORT")
    lines.append("=" * 80)
    if res.get("status") == "installed":
        t = "Plugin" if res.get("is_plugin") else "Package/Skill"
        lines.append(f"Success: Installed {t} '{res.get('name')}' into central library.")
        lines.append(f"Destination: {res.get('destination')}")
        lines.append(f"Skills Discovered: {res.get('skills_count')}")
        lines.append("\nThis capability is now available to be provisioned into any workspace.")
    elif res.get("status") == "exists":
        lines.append(f"Notice: {res.get('message')}")
    else:
        lines.append(f"Error: {res.get('error')}")
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
        "--no-auto-add",
        action="store_true",
        help="In sweep mode, do not automatically equip newly recommended capabilities (recommendation only).",
    )
    parser.add_argument(
        "--import",
        dest="import_url",
        metavar="GIT_URL",
        help="Clone and install a skill or plugin git repository directly into your central skills library.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite when importing into library.",
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
        "--library",
        metavar="PATH",
        help="Override skills-library directory path for this execution.",
    )

    args = parser.parse_args()

    # Import Git Repo into Central Library
    if args.import_url:
        res = import_library_asset(
            git_url=args.import_url,
            library_path=args.library,
            force=args.force,
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

    # If no action flag passed, show help
    if not args.catalog and args.scan is None and not args.provision and args.sweep is None:
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
            scan_res = detect_stack(args.scan)
            if args.json:
                print(json.dumps(scan_res, indent=2))
            else:
                print(format_scan_text(scan_res))
            return 0

        if args.sweep is not None:
            suggest_prune = False if args.no_prune else None
            auto_p = True if args.auto_prune else None
            auto_a = False if args.no_auto_add else None

            swp_res = sweep_project(
                project_path=args.sweep,
                library_path=args.library,
                auto_add=auto_a,
                suggest_pruning=suggest_prune,
                auto_prune=auto_p,
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
