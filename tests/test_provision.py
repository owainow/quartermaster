import os
from pathlib import Path
import pytest
import quartermaster


class TestProvisionAssets:
    def test_provision_single_skill_agy(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target-proj"
        proj.mkdir()

        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["python-test"],
            library_path=str(sample_skills_library),
            harness="agy",
        )
        assert res["provisioned_count"] == 1
        assert len(res["provisioned"]) == 1
        assert res["provisioned"][0]["name"] == "python-test"
        assert res["provisioned"][0]["type"] == "skill"

        dest_dir = proj / ".agents" / "skills" / "python-test"
        assert dest_dir.exists()
        assert (dest_dir / "SKILL.md").exists()

    def test_provision_single_plugin_agy(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target-proj"
        proj.mkdir()

        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["python-stack"],
            library_path=str(sample_skills_library),
            harness="agy",
        )
        assert res["provisioned_count"] == 1
        assert res["provisioned"][0]["name"] == "python-stack"
        assert res["provisioned"][0]["type"] == "plugin"

        dest_dir = proj / ".agents" / "plugins" / "python-stack"
        assert dest_dir.exists()
        assert (dest_dir / "plugin.json").exists()

    def test_provision_package_expansion(self, tmp_path, sample_skills_library):
        proj = tmp_path / "pkg-expand-proj"
        proj.mkdir()

        # Force type skill on a package name that contains skills
        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["python-stack"],
            library_path=str(sample_skills_library),
            force_type="skill",
        )
        assert res["provisioned_count"] >= 1
        assert (proj / ".agents" / "skills" / "python-lint").exists()

    def test_provision_core_attaches_marker(self, tmp_path, sample_skills_library):
        proj = tmp_path / "core-proj"
        proj.mkdir()

        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["preflight"],
            library_path=str(sample_skills_library),
            harness="agy",
        )
        assert res["provisioned_count"] == 1
        dest_dir = proj / ".agents" / "plugins" / "preflight"
        assert (dest_dir / ".core").exists()

    def test_provision_claude_harness(self, tmp_path, sample_skills_library):
        proj = tmp_path / "claude-proj"
        proj.mkdir()

        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["python-test"],
            library_path=str(sample_skills_library),
            harness="claude",
        )
        dest_dir = proj / ".claude" / "skills" / "python-test"
        assert dest_dir.exists()

        # CLAUDE.md should be synced
        claude_md = proj / "CLAUDE.md"
        assert claude_md.exists()
        assert "python-test" in claude_md.read_text()

    def test_provision_codex_harness(self, tmp_path, sample_skills_library):
        proj = tmp_path / "codex-proj"
        proj.mkdir()

        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["python-test"],
            library_path=str(sample_skills_library),
            harness="codex",
        )
        dest_dir = proj / ".agents" / "skills" / "python-test"
        assert dest_dir.exists()

        agents_md = proj / "AGENTS.md"
        assert agents_md.exists()
        assert "python-test" in agents_md.read_text()

    def test_provision_missing_asset_not_found(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target-proj"
        proj.mkdir()

        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["nonexistent-tool"],
            library_path=str(sample_skills_library),
        )
        assert "nonexistent-tool" in res["not_found"]
        assert res["provisioned_count"] == 0

    def test_provision_force_type_restrictions(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target-proj"
        proj.mkdir()

        # If force_type is 'skill', a plugin-only request shouldn't match
        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["preflight"],
            library_path=str(sample_skills_library),
            force_type="skill",
        )
        assert "preflight" in res["not_found"]

    def test_provision_plugin_claude_unpacks_skills(self, tmp_path, sample_skills_library):
        proj = tmp_path / "claude-proj"
        proj.mkdir()
        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["python-stack"],
            library_path=str(sample_skills_library),
            harness="claude",
        )
        assert res["provisioned_count"] >= 1
        assert (proj / ".claude" / "skills" / "python-lint").exists()

    def test_provision_core_plugin_claude(self, tmp_path, sample_skills_library):
        proj = tmp_path / "claude-core-proj"
        proj.mkdir()
        # Add SKILL.md to preflight plugin
        (sample_skills_library / "preflight" / "SKILL.md").write_text("# Preflight\n")
        res = quartermaster.provision_assets(
            project_path=str(proj),
            asset_names=["preflight"],
            library_path=str(sample_skills_library),
            harness="claude",
        )
        assert res["provisioned_count"] >= 1
        dest = proj / ".claude" / "skills" / "preflight"
        assert dest.exists()
        assert (dest / ".core").exists()
