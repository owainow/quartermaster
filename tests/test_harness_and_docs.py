import os
from pathlib import Path
import pytest
import quartermaster


class TestDetectHarness:
    def test_explicit_harness(self):
        assert quartermaster.detect_harness(explicit_harness="claude") == "claude"
        assert quartermaster.detect_harness(explicit_harness="CODEX") == "codex"
        assert quartermaster.detect_harness(explicit_harness="agy") == "agy"
        assert quartermaster.detect_harness(explicit_harness="universal") == "universal"

    def test_env_harness(self, monkeypatch):
        monkeypatch.setenv("QUARTERMASTER_HARNESS", "claude")
        assert quartermaster.detect_harness() == "claude"

        monkeypatch.setenv("QUARTERMASTER_HARNESS", "codex")
        assert quartermaster.detect_harness() == "codex"

    def test_project_markers(self, tmp_path):
        # 1. Claude marker directory
        p1 = tmp_path / "p1"
        p1.mkdir()
        (p1 / ".claude").mkdir()
        assert quartermaster.detect_harness(str(p1)) == "claude"

        # 2. Claude marker file
        p2 = tmp_path / "p2"
        p2.mkdir()
        (p2 / "CLAUDE.md").write_text("# Claude Context\n")
        assert quartermaster.detect_harness(str(p2)) == "claude"

        # 3. Codex marker directory
        p3 = tmp_path / "p3"
        p3.mkdir()
        (p3 / ".codex").mkdir()
        assert quartermaster.detect_harness(str(p3)) == "codex"

        # 4. Codex marker file
        p4 = tmp_path / "p4"
        p4.mkdir()
        (p4 / "AGENTS.md").write_text("# Agents Context\n")
        assert quartermaster.detect_harness(str(p4)) == "codex"

        # 5. AGY marker directory
        p5 = tmp_path / "p5"
        p5.mkdir()
        (p5 / ".agents").mkdir()
        assert quartermaster.detect_harness(str(p5)) == "agy"

    def test_host_user_directory_fallback(self, tmp_path, monkeypatch):
        mock_home = tmp_path / "custom_home"
        mock_home.mkdir()
        monkeypatch.setenv("HOME", str(mock_home))

        # Only .claude exists in home
        (mock_home / ".claude").mkdir()
        empty_proj = tmp_path / "empty_proj"
        empty_proj.mkdir()
        assert quartermaster.detect_harness(str(empty_proj)) == "claude"

        # Clean and test only .codex exists in home
        (mock_home / ".claude").rmdir()
        (mock_home / ".codex").mkdir()
        assert quartermaster.detect_harness(str(empty_proj)) == "codex"

        # If .gemini exists, fallback to agy
        (mock_home / ".gemini").mkdir()
        assert quartermaster.detect_harness(str(empty_proj)) == "agy"

    def test_default_fallback(self, tmp_path):
        empty_proj = tmp_path / "empty_proj"
        empty_proj.mkdir()
        assert quartermaster.detect_harness(str(empty_proj)) == "agy"


class TestHarnessTargetPaths:
    def test_paths_claude(self, tmp_path):
        skills_path, plugins_path = quartermaster.get_harness_target_paths(str(tmp_path), "claude")
        assert skills_path == str(tmp_path / ".claude" / "skills")
        assert plugins_path == ""

    def test_paths_codex(self, tmp_path):
        skills_path, plugins_path = quartermaster.get_harness_target_paths(str(tmp_path), "codex")
        assert skills_path == str(tmp_path / ".agents" / "skills")
        assert plugins_path == str(tmp_path / ".agents" / "plugins")

    def test_paths_universal(self, tmp_path):
        skills_path, plugins_path = quartermaster.get_harness_target_paths(str(tmp_path), "universal")
        assert skills_path == str(tmp_path / ".agents" / "skills")
        assert plugins_path == str(tmp_path / ".agents" / "plugins")

    def test_paths_agy(self, tmp_path):
        skills_path, plugins_path = quartermaster.get_harness_target_paths(str(tmp_path), "agy")
        assert skills_path == str(tmp_path / ".agents" / "skills")
        assert plugins_path == str(tmp_path / ".agents" / "plugins")


class TestSyncDocs:
    def test_sync_claude_md_create_and_update(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        assert not claude_md.exists()

        active_skills = [{"name": "python-test", "path": str(tmp_path / ".claude" / "skills" / "python-test")}]
        active_plugins = [{"name": "python-stack", "path": str(tmp_path / ".claude" / "plugins" / "python-stack")}]

        # Initial creation
        result = quartermaster.sync_claude_md(
            str(tmp_path),
            active_skills=active_skills,
            active_plugins=active_plugins,
        )
        assert result == str(claude_md)
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "<!-- QUARTERMASTER_START -->" in content
        assert "<!-- QUARTERMASTER_END -->" in content
        assert "python-test" in content
        assert "python-stack" in content

        # Update existing CLAUDE.md while preserving outside content
        claude_md.write_text("# My Custom Title\n\n" + content + "\n\n# Custom Footer\n")
        quartermaster.sync_claude_md(
            str(tmp_path),
            active_skills=[{"name": "new-skill", "path": ".claude/skills/new-skill"}],
            active_plugins=[],
        )
        updated = claude_md.read_text()
        assert "# My Custom Title" in updated
        assert "# Custom Footer" in updated
        assert "new-skill" in updated
        assert "python-test" not in updated

    def test_sync_claude_md_empty_capabilities(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        quartermaster.sync_claude_md(str(tmp_path), [], [])
        content = claude_md.read_text()
        assert "*(None)*" in content

    def test_sync_agents_md_create_and_update(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        assert not agents_md.exists()

        result = quartermaster.sync_agents_md(
            str(tmp_path),
            active_skills=[{"name": "codex-skill", "path": ".agents/skills/codex-skill"}],
            active_plugins=[{"name": "codex-plugin", "path": ".agents/plugins/codex-plugin"}],
        )
        assert result == str(agents_md)
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "<!-- QUARTERMASTER_START -->" in content
        assert "<!-- QUARTERMASTER_END -->" in content
        assert "codex-skill" in content
        assert "codex-plugin" in content

        # Update preserving existing content
        agents_md.write_text("Prefix text\n" + content + "\nSuffix text")
        quartermaster.sync_agents_md(
            str(tmp_path),
            active_skills=[{"name": "updated-skill", "path": ".agents/skills/updated-skill"}],
            active_plugins=[],
        )
        updated = agents_md.read_text()
        assert "Prefix text" in updated
        assert "Suffix text" in updated
        assert "updated-skill" in updated

    def test_sync_agents_md_empty(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        quartermaster.sync_agents_md(str(tmp_path), [], [])
        assert "*(None)*" in agents_md.read_text()

    def test_sync_project_docs(self, tmp_path):
        # Create directories with installed skills
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "discovered-skill").mkdir()

        # Claude harness
        res_claude = quartermaster.sync_project_docs(str(tmp_path), "claude")
        assert res_claude["claude"] is not None
        assert "codex" not in res_claude
        assert (tmp_path / "CLAUDE.md").exists()
        assert "discovered-skill" in (tmp_path / "CLAUDE.md").read_text()

        # Codex harness
        codex_skills = tmp_path / ".agents" / "skills"
        codex_skills.mkdir(parents=True)
        (codex_skills / "codex-discovered").mkdir()

        res_codex = quartermaster.sync_project_docs(str(tmp_path), "codex")
        assert res_codex["codex"] is not None
        assert (tmp_path / "AGENTS.md").exists()

        # Universal harness syncs both
        res_universal = quartermaster.sync_project_docs(str(tmp_path), "universal")
        assert res_universal["claude"] is not None
        assert res_universal["codex"] is not None

        # AGY harness syncs none when no docs exist
        clean_proj = tmp_path / "clean_proj"
        clean_proj.mkdir()
        res_agy = quartermaster.sync_project_docs(str(clean_proj), "agy")
        assert res_agy == {}
