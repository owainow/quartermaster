#!/usr/bin/env python3
"""
Quartermaster - Project Onboarding and Skill Provisioning Engine
Scans project tech stacks, discovers available skills and plugins from an external armory library,
and provisions scoped, tailored capabilities directly into `<project_path>/.agents/`.

Supports:
- External skills-library referencing with interactive settings configuration
- Full Antigravity plugin provisioning (.agents/plugins/) and standalone skill provisioning (.agents/skills/)
- Semantic capability tiers: General AI-SDLC vs Domain-Specific
- Interactive brand-new project scoping with "I'm not sure yet" support
- Quartermaster Sweep (--sweep) for ongoing auditing (additions and pruning)
- Non-intrusive background additions-only mode (--additions-only) for daily scheduled sweeps

Zero external dependencies. Pure Python 3 standard library.
"""

import argparse
import glob
import json
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Configuration Paths
GLOBAL_CONFIG_DIR = os.path.expanduser("~/.gemini/quartermaster")
GLOBAL_CONFIG_FILE = os.path.join(GLOBAL_CONFIG_DIR, "config.json")
FALLBACK_CONFIG_FILE = os.path.expanduser("~/.quartermaster/config.json")

DEFAULT_LIBRARY_PATH = os.path.expanduser("~/.gemini/skills-library")

# 7 Core Armory Categories and Package Mappings
CATEGORIES_DEF = [
    {
        "name": "Mobile & Multiplatform",
        "packages": ["flutter", "android-cli-plugin", "android-cli"],
        "display_name": "Mobile & Multiplatform (flutter, android-cli)",
        "description": "Cross-platform mobile apps (Flutter, Dart) and Android CLI tooling",
    },
    {
        "name": "Web, Frontend & Design",
        "packages": [
            "chrome-devtools-plugin",
            "chrome-devtools",
            "modern-web-guidance-plugin",
            "modern-web-guidance",
            "impeccable",
        ],
        "display_name": "Web, Frontend & Design (chrome-devtools, modern-web-guidance, impeccable)",
        "description": "High-craft frontend design, modern web architecture, DevTools debugging & extensions",
    },
    {
        "name": "Cloud & Backend",
        "packages": ["firebase", "cloudrun"],
        "display_name": "Cloud & Backend (firebase, cloudrun)",
        "description": "Firebase ecosystem (Firestore, Auth, Hosting, Rules) and Cloud Run serverless deployment",
    },
    {
        "name": "Testing, Spec-Driven Development & ADLC",
        "packages": ["spark-skills", "agora-adlc", "conductor"],
        "display_name": "Testing, Spec-Driven Development & ADLC (spark-skills, agora-adlc, conductor)",
        "description": "Autonomous SDLC (ADLC), Conductor track management, spec generation, code review & preflight",
    },
    {
        "name": "Synthetic Data & Simulation",
        "packages": ["synthetikos"],
        "display_name": "Synthetic Data & Simulation (synthetikos)",
        "description": "Synthetic customer/colleague personas, multi-agent simulation & evaluation datasets",
    },
    {
        "name": "Science & Bio-Informatics",
        "packages": ["science"],
        "display_name": "Science & Bio-Informatics (science)",
        "description": "Computational biology, literature search (arXiv/PubMed), PDB/AlphaFold, genomics & drug discovery",
    },
    {
        "name": "AI Agent Development",
        "packages": ["google-antigravity-sdk"],
        "display_name": "AI Agent Development (google-antigravity-sdk)",
        "description": "Antigravity agent workflows, prompt engineering, subagent orchestration & evaluation",
    },
]

# Capability Classification: General AI-SDLC vs Domain-Specific
GENERAL_AI_SDLC_PACKAGES = {"spark-skills", "agora-adlc", "conductor"}
GENERAL_AI_SDLC_SKILLS = {
    "spec",
    "pr-review",
    "preflight",
    "wayfinder",
    "adlc-amend",
    "adlc-audit",
    "adlc-clarify",
    "adlc-constitution",
    "adlc-critique",
    "adlc-explore",
    "adlc-init",
    "adlc-plan",
    "adlc-release",
    "adlc-run",
    "adlc-test",
    "adlc-verify",
    "conductor-implement",
    "conductor-new-track",
    "conductor-revert",
    "conductor-setup",
    "conductor-status",
    "conductor-switch",
    "adversary",
    "critic",
    "reviewer",
    "planner",
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
    cfg_file = get_active_config_file()
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {
        "skills-library": DEFAULT_LIBRARY_PATH,
    }


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
    cfg[key] = value
    save_config(cfg)
    return cfg


def resolve_library_path(custom_path: Optional[str] = None) -> str:
    """
    Resolve the active Quartermaster library path with priority:
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

    expanded_default = os.path.abspath(DEFAULT_LIBRARY_PATH)
    return expanded_default


def interactive_config() -> None:
    """Interactive command-line configuration session."""
    cfg = load_config()
    print("=" * 80)
    print("  QUARTERMASTER INTERACTIVE SETTINGS CONFIGURATION")
    print("=" * 80)
    print(f"Current Config File: {get_active_config_file()}")
    print("\nActive Settings:")
    for k, v in sorted(cfg.items()):
        print(f"  * {k:<20} = {v}")

    print("-" * 80)
    print("Options:")
    print("  1. Update 'skills-library' path")
    print("  2. Reset settings to default")
    print("  3. Exit")

    choice = input("\nEnter choice [1-3] (default: 3): ").strip()
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
        default_cfg = {"skills-library": DEFAULT_LIBRARY_PATH}
        save_config(default_cfg)
        print("\nSettings reset to default.")
    else:
        print("\nNo changes made.")


# ==============================================================================
# Frontmatter & Manifest Parsing
# ==============================================================================

def parse_skill_frontmatter(content: str) -> Dict[str, str]:
    """Parse YAML frontmatter from a SKILL.md document without external YAML dependencies."""
    meta: Dict[str, str] = {}
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
# Armory Cataloging (Skills & Plugins with Capability Classification)
# ==============================================================================

def get_catalog(library_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Discovers all packages, plugins, and skills in the configured skills-library.
    Categorizes into 7 functional domains and tags with capability_type
    ('general_ai_sdlc' vs 'domain_specific').
    """
    lib_dir = resolve_library_path(library_path)
    if not os.path.exists(lib_dir):
        return {
            "library_path": lib_dir,
            "error": f"Library path does not exist: {lib_dir}",
            "total_skills": 0,
            "total_plugins": 0,
            "total_packages": 0,
            "categories": {},
            "plugins": [],
            "skills": [],
        }

    pkg_to_cat = {}
    for cat_def in CATEGORIES_DEF:
        for pkg in cat_def["packages"]:
            pkg_to_cat[pkg.lower()] = cat_def["name"]

    # Discover top-level package directories
    package_dirs = [
        d for d in os.listdir(lib_dir)
        if os.path.isdir(os.path.join(lib_dir, d)) and not d.startswith(".")
    ]

    all_plugins: List[Dict[str, Any]] = []
    all_skills: List[Dict[str, Any]] = []

    for pkg in sorted(package_dirs):
        pkg_dir = os.path.join(lib_dir, pkg)
        cat_name = pkg_to_cat.get(pkg.lower(), "Testing, Spec-Driven Development & ADLC")

        # Check for plugin manifest (plugin.json)
        plugin_manifest_path = os.path.join(pkg_dir, "plugin.json")
        is_plugin = os.path.exists(plugin_manifest_path)

        pkg_capability_type = (
            "general_ai_sdlc"
            if pkg.lower() in GENERAL_AI_SDLC_PACKAGES
            else "domain_specific"
        )

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

            plugin_info = {
                "name": plugin_name,
                "package": pkg,
                "category": cat_name,
                "capability_type": pkg_capability_type,
                "version": plugin_version,
                "description": plugin_desc,
                "source_dir": pkg_dir,
                "manifest_file": plugin_manifest_path,
                "components": components,
            }
            all_plugins.append(plugin_info)

        # Discover all SKILL.md files inside package
        skill_files = glob.glob(os.path.join(pkg_dir, "**", "SKILL.md"), recursive=True)
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

            skill_capability_type = (
                "general_ai_sdlc"
                if (pkg_capability_type == "general_ai_sdlc" or name.lower() in GENERAL_AI_SDLC_SKILLS)
                else "domain_specific"
            )

            subdirs = [
                d for d in os.listdir(skill_dir)
                if os.path.isdir(os.path.join(skill_dir, d))
            ]

            all_skills.append({
                "name": name,
                "dir_name": os.path.basename(skill_dir),
                "package": pkg,
                "category": cat_name,
                "capability_type": skill_capability_type,
                "source_dir": skill_dir,
                "skill_file": sf,
                "description": desc,
                "version": version,
                "subdirs": subdirs,
                "parent_plugin": plugin_info["name"] if plugin_info else None,
            })

    # Group by category
    categories_dict: Dict[str, Dict[str, Any]] = {}
    for cat_def in CATEGORIES_DEF:
        cat_name = cat_def["name"]
        cat_skills = [s for s in all_skills if s["category"] == cat_name]
        cat_plugins = [p for p in all_plugins if p["category"] == cat_name]

        pkgs_dict: Dict[str, List[Dict[str, Any]]] = {}
        for s in cat_skills:
            pkgs_dict.setdefault(s["package"], []).append(s)

        categories_dict[cat_name] = {
            "display_name": cat_def["display_name"],
            "description": cat_def["description"],
            "packages": pkgs_dict,
            "plugins": cat_plugins,
            "plugin_count": len(cat_plugins),
            "skill_count": len(cat_skills),
        }

    return {
        "library_path": lib_dir,
        "total_packages": len(package_dirs),
        "total_plugins": len(all_plugins),
        "total_skills": len(all_skills),
        "categories": categories_dict,
        "plugins": all_plugins,
        "skills": all_skills,
    }


# ==============================================================================
# Workspace Reconnaissance & Stack Detection
# ==============================================================================

def detect_stack(project_path: str) -> Dict[str, Any]:
    """
    Scans project root and key subdirectories for manifest files.
    Identifies frameworks, detects brand new / uninitialized projects,
    and returns tailored recommendations separated by capability type.
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

    def add_skill_rec(
        name: str,
        package: str,
        category: str,
        capability_type: str,
        reason: str,
        priority: str = "High",
    ):
        norm = name.lower().replace("_", "-")
        if norm not in seen_skill_names:
            seen_skill_names.add(norm)
            recommended_skills.append({
                "name": name,
                "package": package,
                "category": category,
                "capability_type": capability_type,
                "reason": reason,
                "priority": priority,
            })

    def add_plugin_rec(
        name: str,
        category: str,
        capability_type: str,
        reason: str,
        priority: str = "High",
    ):
        norm = name.lower().replace("_", "-")
        if norm not in seen_plugin_names:
            seen_plugin_names.add(norm)
            recommended_plugins.append({
                "name": name,
                "category": category,
                "capability_type": capability_type,
                "reason": reason,
                "priority": priority,
            })

    def safe_read(path: str, max_chars: int = 10000) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
        except Exception:
            return ""

    # Check for Flutter / Dart (pubspec.yaml)
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

        add_plugin_rec(
            "flutter",
            "Mobile & Multiplatform",
            "domain_specific",
            "Complete Flutter plugin with architecture, layout, and testing tooling",
        )
        add_skill_rec(
            "flutter-apply-architecture-best-practices",
            "flutter",
            "Mobile & Multiplatform",
            "domain_specific",
            "Essential architecture & structure standards for Flutter apps",
        )
        add_skill_rec(
            "dart-add-unit-test",
            "flutter",
            "Mobile & Multiplatform",
            "domain_specific",
            "Best practices for test doubles, fixtures, and assertions",
        )
        add_skill_rec(
            "flutter-build-responsive-layout",
            "flutter",
            "Mobile & Multiplatform",
            "domain_specific",
            "Responsive layout patterns across screen sizes and orientations",
        )
        add_skill_rec(
            "dart-run-static-analysis",
            "flutter",
            "Mobile & Multiplatform",
            "domain_specific",
            "Linter rule enforcement and static analysis diagnostics",
        )

        if "http:" in content or "dio:" in content:
            add_skill_rec(
                "flutter-use-http-package",
                "flutter",
                "Mobile & Multiplatform",
                "domain_specific",
                "Detected HTTP networking dependencies",
            )
        if "json_annotation:" in content or "json_serializable:" in content:
            add_skill_rec(
                "flutter-implement-json-serialization",
                "flutter",
                "Mobile & Multiplatform",
                "domain_specific",
                "Detected JSON code generation annotations",
            )
        if "go_router:" in content or "auto_route:" in content:
            add_skill_rec(
                "flutter-setup-declarative-routing",
                "flutter",
                "Mobile & Multiplatform",
                "domain_specific",
                "Detected declarative router dependencies",
            )

    # Check for Android Native Project
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
        add_plugin_rec(
            "android-cli-plugin",
            "Mobile & Multiplatform",
            "domain_specific",
            "Android CLI management, emulators, logcat, and APK builds",
        )

    # Check for Node.js / Web / TypeScript (package.json)
    package_json_path = os.path.join(proj_dir, "package.json")
    if os.path.exists(package_json_path):
        manifests_found.append("package.json")
        content = safe_read(package_json_path)
        frameworks = []
        is_frontend = False

        if "react" in content:
            frameworks.append("React")
            is_frontend = True
        if "next" in content:
            frameworks.append("Next.js")
            is_frontend = True
        if "vue" in content:
            frameworks.append("Vue")
            is_frontend = True
        if "svelte" in content:
            frameworks.append("Svelte")
            is_frontend = True
        if "tailwind" in content or os.path.exists(os.path.join(proj_dir, "tailwind.config.js")):
            frameworks.append("Tailwind CSS")
            is_frontend = True
        if "vite" in content:
            frameworks.append("Vite")
            is_frontend = True
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

        add_skill_rec(
            "impeccable",
            "impeccable",
            "Web, Frontend & Design",
            "domain_specific",
            "Elite frontend craft, design polish, UX audit, and component refinement",
        )
        add_plugin_rec(
            "modern-web-guidance-plugin",
            "Web, Frontend & Design",
            "domain_specific",
            "Architectural standards, clean idioms, and web performance patterns",
        )
        add_plugin_rec(
            "chrome-devtools-plugin",
            "Web, Frontend & Design",
            "domain_specific",
            "DevTools MCP inspection, runtime debugging, and DOM inspection",
        )

    # Check for Chrome Extension (manifest.json)
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
            add_skill_rec(
                "chrome-extensions",
                "modern-web-guidance-plugin",
                "Web, Frontend & Design",
                "domain_specific",
                "Chrome extension architecture, permissions, and background workers",
            )
            add_plugin_rec(
                "chrome-devtools-plugin",
                "Web, Frontend & Design",
                "domain_specific",
                "Inspection of extension popups, options pages, and content scripts",
            )

    # Check for Firebase (firebase.json, .firebaserc)
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
        add_plugin_rec(
            "firebase",
            "Cloud & Backend",
            "domain_specific",
            "Complete Firebase ecosystem plugin (Firestore, Auth, Rules, App Hosting)",
        )
        add_skill_rec(
            "firebase-basics",
            "firebase",
            "Cloud & Backend",
            "domain_specific",
            "Foundational Firebase CLI, project initialization, and emulator suite",
        )
        add_skill_rec(
            "firebase-firestore",
            "firebase",
            "Cloud & Backend",
            "domain_specific",
            "Firestore schema design, querying, and transactional operations",
        )
        add_skill_rec(
            "firebase-security-rules-auditor",
            "firebase",
            "Cloud & Backend",
            "domain_specific",
            "Audit and hardening of Firestore & Cloud Storage security rules",
        )

    # Check for Python (pyproject.toml, requirements.txt, Pipfile, setup.py)
    pyproject_path = os.path.join(proj_dir, "pyproject.toml")
    requirements_path = os.path.join(proj_dir, "requirements.txt")
    pipfile_path = os.path.join(proj_dir, "Pipfile")
    setup_path = os.path.join(proj_dir, "setup.py")

    py_manifests = [
        m for m in [pyproject_path, requirements_path, pipfile_path, setup_path]
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

        add_skill_rec(
            "uv",
            "science",
            "Science & Bio-Informatics",
            "domain_specific",
            "Ultra-fast Python package management and virtual environments via uv",
        )

        if any(kw in combined_py for kw in ["antigravity", "google-genai", "gemini"]) or os.path.exists(os.path.join(proj_dir, "agents")):
            add_plugin_rec(
                "google-antigravity-sdk",
                "AI Agent Development",
                "domain_specific",
                "Antigravity SDK for multi-agent workflows, subagents, and tool execution",
            )

        bio_keywords = ["biopython", "scanpy", "rdkit", "anndata", "pytorch", "torch", "scipy", "numpy", "alphafold", "bioinfor"]
        if any(kw in combined_py for kw in bio_keywords):
            technologies.append({
                "name": "Scientific / Bio-Informatics",
                "manifest": primary_py,
                "details": "Scientific and computational biology libraries detected",
            })
            add_plugin_rec(
                "science",
                "Science & Bio-Informatics",
                "domain_specific",
                "Biomedical databases (PubMed, arXiv, NCBI, UniProt) and AlphaFold",
            )

    # Check for Rust (Cargo.toml)
    if os.path.exists(os.path.join(proj_dir, "Cargo.toml")):
        manifests_found.append("Cargo.toml")
        technologies.append({
            "name": "Rust Ecosystem",
            "manifest": "Cargo.toml",
            "details": "Cargo build system and crates",
        })

    # Check for Go (go.mod)
    if os.path.exists(os.path.join(proj_dir, "go.mod")):
        manifests_found.append("go.mod")
        technologies.append({
            "name": "Go Platform",
            "manifest": "go.mod",
            "details": "Go modules dependency management",
        })

    # Check for Containers (Dockerfile, docker-compose)
    if os.path.exists(os.path.join(proj_dir, "Dockerfile")) or os.path.exists(os.path.join(proj_dir, "docker-compose.yml")):
        doc_manifest = "Dockerfile" if os.path.exists(os.path.join(proj_dir, "Dockerfile")) else "docker-compose.yml"
        manifests_found.append(doc_manifest)
        technologies.append({
            "name": "Containerization / Docker",
            "manifest": doc_manifest,
            "details": "Container build specifications and multi-service definitions",
        })

    # Universal High-Confidence Baseline: General AI-SDLC Skills
    # Universal guardrails that elevate software engineering regardless of technology
    add_skill_rec(
        "spec",
        "spark-skills",
        "Testing, Spec-Driven Development & ADLC",
        "general_ai_sdlc",
        "Spec-driven engineering: write clear functional specs before writing code",
        priority="Baseline",
    )
    add_skill_rec(
        "pr-review",
        "spark-skills",
        "Testing, Spec-Driven Development & ADLC",
        "general_ai_sdlc",
        "Adversarial pull request critique, bug detection, and regression guard",
        priority="Baseline",
    )
    add_skill_rec(
        "preflight",
        "spark-skills",
        "Testing, Spec-Driven Development & ADLC",
        "general_ai_sdlc",
        "Pre-commit sanity verification, lint checks, and test runner assurance",
        priority="Baseline",
    )
    add_skill_rec(
        "wayfinder",
        "spark-skills",
        "Testing, Spec-Driven Development & ADLC",
        "general_ai_sdlc",
        "Deep codebase navigation, dependency mapping, and orientation",
        priority="Baseline",
    )

    # Detect if brand-new or uninitialized project
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
            "prompt": "This workspace appears to be a brand new project. What type of project are you building?",
            "options": [
                {"label": "Web / Frontend App", "category": "Web, Frontend & Design"},
                {"label": "Mobile App (Flutter / Android)", "category": "Mobile & Multiplatform"},
                {"label": "Cloud & Backend API / Microservices", "category": "Cloud & Backend"},
                {"label": "AI Agent / Multi-Agent System", "category": "AI Agent Development"},
                {"label": "Data Science / Scientific Computing", "category": "Science & Bio-Informatics"},
                {"label": "I'm not sure yet", "category": "General AI-SDLC Only"},
            ],
            "recommendation_on_unclear": (
                "When scope is unclear or 'I\\'m not sure yet' is chosen, Quartermaster equips "
                "only General AI-SDLC skills (e.g. adversarial review, spec-driven engineering, "
                "preflight verification), keeping the project uncluttered until domain decisions emerge."
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
    force_type: Optional[str] = None,  # "skill" or "plugin" or None (auto)
) -> Dict[str, Any]:
    """
    Provisions requested assets into `<project_path>/.agents/`.
    - Full plugins &rarr; `<project_path>/.agents/plugins/<plugin_name>/`
    - Standalone skills &rarr; `<project_path>/.agents/skills/<skill_name>/`
    Maintains self-contained copies with no global side effects.
    """
    proj_dir = os.path.abspath(os.path.expanduser(project_path))
    os.makedirs(proj_dir, exist_ok=True)

    target_skills_dir = os.path.join(proj_dir, ".agents", "skills")
    target_plugins_dir = os.path.join(proj_dir, ".agents", "plugins")

    catalog = get_catalog(library_path)
    all_skills = catalog.get("skills", [])
    all_plugins = catalog.get("plugins", [])

    # Index plugins by normalized name
    plugin_map: Dict[str, Dict[str, Any]] = {}
    for p in all_plugins:
        p_name = p["name"].lower()
        plugin_map[p_name] = p
        plugin_map[p_name.replace("-plugin", "")] = p
        plugin_map[p_name.replace("_", "-")] = p
        plugin_map[p["package"].lower()] = p

    # Index skills by normalized name
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

        # If user explicitly asked for plugin or asset is in plugin map
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
                    "category": plugin["category"],
                    "capability_type": plugin["capability_type"],
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
                    "category": skill["category"],
                    "capability_type": skill["capability_type"],
                    "source": src_dir,
                    "destination": dest_dir,
                    "files_copied": file_count,
                    "status": "provisioned",
                })
            handled = True

        # Route 3: Package name expansion (if not a plugin, expand to all contained skills)
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
                        "category": skill["category"],
                        "capability_type": skill["capability_type"],
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
# Quartermaster Sweep (Project & Armory Audit)
# ==============================================================================

def sweep_project(
    project_path: str,
    library_path: Optional[str] = None,
    additions_only: bool = False,
) -> Dict[str, Any]:
    """
    Performs a thorough sweep of the project:
    1. Audits current workspace tech stack and manifests.
    2. Audits installed skills & plugins in `<project>/.agents/`.
    3. Cross-references the armory library:
       - Identifies newly matching skills/plugins to add.
       - If additions_only is False: identifies installed skills whose underlying tech was removed (pruning candidates).
       - If additions_only is True (background mode): pruning candidates are suppressed.
    """
    proj_dir = os.path.abspath(os.path.expanduser(project_path))
    scan = detect_stack(proj_dir)
    catalog = get_catalog(library_path)

    target_skills_dir = os.path.join(proj_dir, ".agents", "skills")
    target_plugins_dir = os.path.join(proj_dir, ".agents", "plugins")

    # Audit installed skills
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

    # Audit installed plugins
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

    # Evaluate recommended additions (skills/plugins recommended by scan that are NOT yet installed)
    additions: List[Dict[str, Any]] = []

    for rec_plugin in scan.get("recommended_plugins", []):
        p_name = rec_plugin["name"].lower()
        if p_name not in installed_plugin_names:
            additions.append({
                "name": rec_plugin["name"],
                "type": "plugin",
                "category": rec_plugin["category"],
                "capability_type": rec_plugin.get("capability_type", "domain_specific"),
                "reason": rec_plugin["reason"],
                "priority": rec_plugin.get("priority", "High"),
            })

    for rec_skill in scan.get("recommended_skills", []):
        s_name = rec_skill["name"].lower()
        # Only add if neither the skill nor its parent plugin is installed
        parent_pkg = rec_skill.get("package", "").lower()
        if s_name not in installed_skill_names and parent_pkg not in installed_plugin_names:
            additions.append({
                "name": rec_skill["name"],
                "type": "skill",
                "category": rec_skill["category"],
                "capability_type": rec_skill.get("capability_type", "domain_specific"),
                "reason": rec_skill["reason"],
                "priority": rec_skill.get("priority", "High"),
            })

    # Evaluate pruning candidates (only if additions_only is False)
    pruning_candidates: List[Dict[str, Any]] = []
    if not additions_only:
        manifest_list = scan.get("manifests_found", [])

        # Check installed skills for relevance
        catalog_skills_by_name = {s["name"].lower(): s for s in catalog.get("skills", [])}
        for s in installed_skills:
            s_name = s["name"].lower()
            cat_entry = catalog_skills_by_name.get(s_name)
            if not cat_entry:
                continue

            # General AI-SDLC skills are never pruning candidates
            if cat_entry.get("capability_type") == "general_ai_sdlc":
                continue

            pkg = cat_entry.get("package", "").lower()
            # If Flutter skill but no pubspec
            if "flutter" in pkg and "pubspec.yaml" not in manifest_list:
                pruning_candidates.append({
                    "name": s["name"],
                    "type": "skill",
                    "reason": "Installed Flutter skill but no pubspec.yaml found in workspace",
                })
            # If Firebase skill but no firebase.json
            elif "firebase" in pkg and not any("firebase" in m for m in manifest_list):
                pruning_candidates.append({
                    "name": s["name"],
                    "type": "skill",
                    "reason": "Installed Firebase skill but no firebase.json / .firebaserc found in workspace",
                })
            # If Android CLI but no Gradle/android
            elif "android" in pkg and not any("android" in m or "gradle" in m for m in manifest_list):
                pruning_candidates.append({
                    "name": s["name"],
                    "type": "skill",
                    "reason": "Installed Android CLI tool but no Android/Gradle manifests found",
                })

    return {
        "project_path": proj_dir,
        "library_path": catalog.get("library_path"),
        "scan_status": scan.get("status"),
        "manifests_found": scan.get("manifests_found", []),
        "technologies": scan.get("technologies", []),
        "installed_plugins": installed_plugins,
        "installed_skills": installed_skills,
        "additions_recommended": additions,
        "pruning_candidates": pruning_candidates if not additions_only else [],
        "additions_only_mode": additions_only,
    }


# ==============================================================================
# Text Formatters for CLI Output
# ==============================================================================

def format_catalog_text(catalog: Dict[str, Any]) -> str:
    """Formats the catalog into an organized armory overview."""
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

    cat_index = 1
    categories = catalog.get("categories", {})
    for cat_name, cat_data in categories.items():
        lines.append("")
        lines.append(
            f"[{cat_index}] {cat_data.get('display_name')} "
            f"({cat_data.get('plugin_count')} plugins, {cat_data.get('skill_count')} skills)"
        )
        lines.append(f"    {cat_data.get('description')}")
        lines.append("    " + "-" * 72)

        plugins = cat_data.get("plugins", [])
        if plugins:
            lines.append("    [Full Plugins]")
            for p in plugins:
                comp_str = ", ".join(p.get("components", []))
                lines.append(f"      * [PLUGIN] {p['name']:<30} (contains: {comp_str})")
                lines.append(f"        {p['description']}")
            lines.append("")

        packages = cat_data.get("packages", {})
        for pkg_name, skills in packages.items():
            lines.append(f"    Package: {pkg_name} ({len(skills)} skills)")
            for s in skills:
                name = s["name"]
                desc = s["description"]
                short_desc = desc if len(desc) <= 65 else desc[:62] + "..."
                tier = f"[{s.get('capability_type', 'domain_specific')}]"
                lines.append(f"      * {name:<35} {tier:<20} : {short_desc}")
            lines.append("")
        cat_index += 1

    lines.append("=" * 80)
    lines.append("To provision, run:")
    lines.append("  python3 quartermaster.py --provision <path> --skills <skill1,skill2,...>")
    lines.append("  python3 quartermaster.py --provision <path> --plugins <plugin1,...>")
    lines.append("=" * 80)
    return "\n".join(lines)


def format_scan_text(scan: Dict[str, Any]) -> str:
    """Formats project scan results into a reconnaissance report."""
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  QUARTERMASTER RECONNAISSANCE REPORT")
    lines.append(f"  Target Workspace: {scan.get('project_path')}")
    lines.append(f"  Status: {scan.get('status')}")
    lines.append("=" * 80)

    # Scoping Dialogue Notice for brand new projects
    if scan.get("is_brand_new"):
        lines.append("\n>>> BRAND NEW / UNINITIALIZED PROJECT DETECTED <<<")
        dialogue = scan.get("scoping_dialogue", {})
        lines.append(f"Question: {dialogue.get('prompt')}")
        lines.append("Options:")
        for opt in dialogue.get("options", []):
            lines.append(f"  [ ] {opt['label']:<32} -> {opt['category']}")
        lines.append(f"\nGuiding Policy:\n  {dialogue.get('recommendation_on_unclear')}")

    # Manifests
    manifests = scan.get("manifests_found", [])
    if manifests:
        lines.append("\n[Detected Manifests]")
        for m in manifests:
            lines.append(f"  * {m}")
    else:
        lines.append("\n[Detected Manifests]")
        lines.append("  (No standard project manifest files identified in root)")

    # Technologies
    technologies = scan.get("technologies", [])
    if technologies:
        lines.append("\n[Identified Tech Stack & Frameworks]")
        for t in technologies:
            lines.append(f"  * {t['name']:<28} [{t['manifest']}] -> {t['details']}")

    # Recommended Plugins
    plugins = scan.get("recommended_plugins", [])
    if plugins:
        lines.append(f"\n[Recommended Full Plugins ({len(plugins)})]")
        for p in plugins:
            p_badge = f"[{p.get('priority', 'High')}]"
            lines.append(f"  * [PLUGIN] {p['name']:<30} {p_badge:<10} ({p['category']})")
            lines.append(f"    Rationale: {p['reason']}")

    # Recommended Skills
    recs = scan.get("recommended_skills", [])
    lines.append(f"\n[High-Confidence Recommended Skills ({len(recs)})]")
    if recs:
        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for r in recs:
            by_cat.setdefault(r["category"], []).append(r)

        for cat, items in by_cat.items():
            lines.append(f"\n  -- {cat} --")
            for item in items:
                p_badge = f"[{item.get('priority', 'High')}]"
                tier_badge = f"<{item.get('capability_type', 'domain_specific')}>"
                lines.append(
                    f"    * {item['name']:<36} {p_badge:<10} {tier_badge:<18} (pkg: {item['package']})"
                )
                lines.append(f"      Rationale: {item['reason']}")

    lines.append("\n" + "=" * 80)
    quick_items = [p["name"] for p in plugins] + [r["name"] for r in recs[:6]]
    if quick_items:
        lines.append("Quick Provision Command:")
        lines.append(
            f"  python3 quartermaster.py --provision {scan.get('project_path')} --skills {','.join(quick_items)}"
        )
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

    # Installed inventory
    i_plugins = swp.get("installed_plugins", [])
    i_skills = swp.get("installed_skills", [])
    lines.append(f"\n[Active Workspace Inventory] ({len(i_plugins)} plugins, {len(i_skills)} skills)")
    for p in i_plugins:
        lines.append(f"  * [PLUGIN] {p['name']:<30} in .agents/plugins/")
    for s in i_skills:
        lines.append(f"  * [SKILL]  {s['name']:<30} in .agents/skills/")
    if not i_plugins and not i_skills:
        lines.append("  (No skills or plugins currently provisioned in .agents/)")

    # Additions
    additions = swp.get("additions_recommended", [])
    lines.append(f"\n[Recommended New Capabilities to Onboard ({len(additions)})]")
    if additions:
        for a in additions:
            t_badge = "[PLUGIN]" if a["type"] == "plugin" else "[SKILL] "
            p_badge = f"[{a.get('priority', 'High')}]"
            lines.append(f"  * + {t_badge} {a['name']:<30} {p_badge:<10} ({a['category']})")
            lines.append(f"      Rationale: {a['reason']}")
    else:
        lines.append("  (All recommended capabilities for current stack are already provisioned)")

    # Pruning candidates (if not additions_only)
    if not swp.get("additions_only_mode"):
        pruning = swp.get("pruning_candidates", [])
        lines.append(f"\n[Potential Pruning Candidates ({len(pruning)})]")
        if pruning:
            for pr in pruning:
                lines.append(f"  * - [{pr['type'].upper()}] {pr['name']:<30}")
                lines.append(f"      Note: {pr['reason']}")
        else:
            lines.append("  (No obsolete or unneeded capabilities detected)")

    lines.append("\n" + "=" * 80)
    if additions:
        quick_names = ",".join([a["name"] for a in additions])
        lines.append("Quick Onboard Command:")
        lines.append(
            f"  python3 quartermaster.py --provision {swp.get('project_path')} --skills {quick_names}"
        )
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
        "--additions-only",
        action="store_true",
        help="In sweep mode, strictly evaluate additions and suppress pruning recommendations (ideal for scheduled tasks).",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Launch interactive settings configuration or display current configuration.",
    )
    parser.add_argument(
        "--config-get",
        metavar="KEY",
        help="Get the value of a specific configuration setting (e.g. skills-library).",
    )
    parser.add_argument(
        "--config-set",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Set a configuration setting (e.g. --config-set skills-library /path/to/library).",
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
        cfg = set_config_value(key, os.path.expanduser(val))
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
            swp_res = sweep_project(
                project_path=args.sweep,
                library_path=args.library,
                additions_only=args.additions_only,
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
                    force_type = None  # Mixed

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
