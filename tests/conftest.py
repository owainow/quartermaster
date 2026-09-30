import os
import sys
import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "claude" / "hooks"))

import quartermaster


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """
    Hermetically isolate user environment and quartermaster paths
    so no tests touch real host user directories or configs.
    """
    mock_home = tmp_path / "home"
    mock_home.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(mock_home))
    monkeypatch.delenv("QUARTERMASTER_HARNESS", raising=False)

    gemini_dir = mock_home / ".gemini"
    gemini_qm = gemini_dir / "quartermaster"
    gemini_qm.mkdir(parents=True, exist_ok=True)
    global_cfg = gemini_qm / "config.json"

    fallback_qm = mock_home / ".quartermaster"
    fallback_qm.mkdir(parents=True, exist_ok=True)
    fallback_cfg = fallback_qm / "config.json"

    claude_qm = mock_home / ".claude" / "quartermaster"
    claude_qm.mkdir(parents=True, exist_ok=True)
    claude_cfg = claude_qm / "config.json"

    codex_qm = mock_home / ".codex" / "quartermaster"
    codex_qm.mkdir(parents=True, exist_ok=True)
    codex_cfg = codex_qm / "config.json"

    default_lib = mock_home / ".gemini" / "skills-library"
    default_lib.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(quartermaster, "GLOBAL_CONFIG_DIR", str(gemini_qm))
    monkeypatch.setattr(quartermaster, "GLOBAL_CONFIG_FILE", str(global_cfg))
    monkeypatch.setattr(quartermaster, "FALLBACK_CONFIG_FILE", str(fallback_cfg))
    monkeypatch.setattr(quartermaster, "CLAUDE_CONFIG_DIR", str(claude_qm))
    monkeypatch.setattr(quartermaster, "CLAUDE_CONFIG_FILE", str(claude_cfg))
    monkeypatch.setattr(quartermaster, "CODEX_CONFIG_DIR", str(codex_qm))
    monkeypatch.setattr(quartermaster, "CODEX_CONFIG_FILE", str(codex_cfg))
    monkeypatch.setattr(
        quartermaster,
        "CONFIG_SEARCH_PATHS",
        [str(claude_cfg), str(codex_cfg), str(global_cfg), str(fallback_cfg)],
    )
    monkeypatch.setattr(quartermaster, "DEFAULT_LIBRARY_PATH", str(default_lib))
    monkeypatch.setitem(quartermaster.DEFAULT_CONFIG, "skills-library", str(default_lib))
    monkeypatch.setattr(
        quartermaster,
        "PROBE_LIBRARY_DIRS",
        [
            str(default_lib),
            str(mock_home / ".claude" / "skills-library"),
            str(mock_home / ".agents" / "skills-library"),
            str(mock_home / ".quartermaster" / "skills-library"),
        ],
    )

    yield {
        "home": mock_home,
        "global_config": global_cfg,
        "fallback_config": fallback_cfg,
        "claude_config": claude_cfg,
        "codex_config": codex_cfg,
        "library": default_lib,
    }


@pytest.fixture
def sample_skills_library(tmp_path):
    """
    Creates a sample skills library containing skills and plugins.
    Quartermaster catalogs directories directly under library_path.
    """
    lib_dir = tmp_path / "test-library"
    lib_dir.mkdir(parents=True, exist_ok=True)

    # 1. Standard skill: python-test
    py_skill = lib_dir / "python-test"
    py_skill.mkdir()
    (py_skill / "SKILL.md").write_text(
        "---\n"
        "name: python-test\n"
        "description: Run pytest and manage test fixtures for Python projects.\n"
        "---\n"
        "# Python Test Skill\n"
    )

    # 2. Core skill: spec (with .core file)
    spec_skill = lib_dir / "spec"
    spec_skill.mkdir()
    (spec_skill / "SKILL.md").write_text(
        "---\n"
        "name: spec\n"
        "description: Specification and requirements definition workflows.\n"
        "---\n"
        "# Spec Skill\n"
    )
    (spec_skill / ".core").write_text("core capability\n")

    # 3. Non-core standalone skill: docker-compose
    docker_skill = lib_dir / "docker-compose"
    docker_skill.mkdir()
    (docker_skill / "SKILL.md").write_text(
        "---\n"
        "name: docker-compose\n"
        "description: Docker compose stack orchestrator.\n"
        "---\n"
        "# Docker Compose\n"
    )

    # 4. Standard plugin: python-stack
    py_plugin = lib_dir / "python-stack"
    py_plugin.mkdir()
    (py_plugin / "plugin.json").write_text(
        json.dumps({
            "name": "python-stack",
            "version": "1.0.0",
            "description": "Complete Python development bundle including linting, typing, and testing.",
            "skills": ["python-test"],
            "tier": "stack",
        })
    )
    py_plugin_skill = py_plugin / "skills" / "python-lint"
    py_plugin_skill.mkdir(parents=True)
    (py_plugin_skill / "SKILL.md").write_text(
        "---\n"
        "name: python-lint\n"
        "description: Linting tools for Python.\n"
        "---\n"
        "# Lint\n"
    )

    # 5. Core plugin: preflight (with .core)
    core_plugin = lib_dir / "preflight"
    core_plugin.mkdir()
    (core_plugin / "plugin.json").write_text(
        json.dumps({
            "name": "preflight",
            "version": "1.0.0",
            "description": "Pre-commit sanity and verification pipeline.",
            "tier": "core",
        })
    )
    (core_plugin / ".core").write_text("core capability\n")

    # 6. Skill with invalid frontmatter
    bad_skill = lib_dir / "bad-skill"
    bad_skill.mkdir()
    (bad_skill / "SKILL.md").write_text("No frontmatter header at all here.")

    return lib_dir


@pytest.fixture
def sample_project(tmp_path):
    """
    Creates a sample project workspace with git root and stack files.
    """
    proj = tmp_path / "my-project"
    proj.mkdir()
    (proj / ".git").mkdir()
    (proj / "pyproject.toml").write_text("[project]\nname = 'sample-project'\n")
    return proj
