import os
import shutil
from pathlib import Path
import pytest
import quartermaster


class TestSweepProject:
    def test_sweep_auto_add_provisions_recommended(self, tmp_path, sample_skills_library):
        proj = tmp_path / "py-app"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname = 'py-app'\n")

        res = quartermaster.sweep_project(
            project_path=str(proj),
            library_path=str(sample_skills_library),
            auto_add=True,
            suggest_pruning=False,
            auto_prune=False,
            harness="agy",
        )
        assert res["auto_add_enabled"] is True
        equipped_names = [e["name"] for e in res.get("provisioned_additions", [])]
        # Core capabilities (like preflight, spec) are equipped
        assert len(equipped_names) > 0
        assert (proj / ".agents" / "skills").exists()

    def test_sweep_no_auto_add(self, tmp_path, sample_skills_library):
        proj = tmp_path / "py-app"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname = 'py-app'\n")

        res = quartermaster.sweep_project(
            project_path=str(proj),
            library_path=str(sample_skills_library),
            auto_add=False,
            suggest_pruning=False,
            auto_prune=False,
            harness="agy",
        )
        assert len(res.get("provisioned_additions", [])) == 0
        assert len(res.get("additions_recommended", [])) > 0

    def test_sweep_protects_core_from_pruning(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname = 'app'\n")

        skills_dir = proj / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        # Install 'spec' (core) and 'docker-compose' (non-core)
        spec_dest = skills_dir / "spec"
        shutil.copytree(sample_skills_library / "spec", spec_dest)

        docker_dest = skills_dir / "docker-compose"
        shutil.copytree(sample_skills_library / "docker-compose", docker_dest)

        res = quartermaster.sweep_project(
            project_path=str(proj),
            library_path=str(sample_skills_library),
            auto_add=False,
            suggest_pruning=True,
            auto_prune=False,
            pruning_mode="aggressive",
            harness="agy",
        )
        candidate_names = [c["name"] for c in res.get("pruning_candidates", [])]
        # 'spec' must NOT be in candidates because it is core
        assert "spec" not in candidate_names
        # 'docker-compose' is in candidates because no dockerfile exists
        assert "docker-compose" in candidate_names

    def test_sweep_auto_prune(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname = 'app'\n")

        skills_dir = proj / ".agents" / "skills"
        skills_dir.mkdir(parents=True)
        docker_dest = skills_dir / "docker-compose"
        shutil.copytree(sample_skills_library / "docker-compose", docker_dest)

        res = quartermaster.sweep_project(
            project_path=str(proj),
            library_path=str(sample_skills_library),
            auto_add=False,
            suggest_pruning=True,
            auto_prune=True,
            pruning_mode="aggressive",
            harness="agy",
        )
        pruned_names = [p["name"] for p in res.get("pruned_items", [])]
        assert "docker-compose" in pruned_names
        assert not docker_dest.exists()

    def test_sweep_soft_pruning_mode(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname = 'app'\n")

        skills_dir = proj / ".agents" / "skills"
        skills_dir.mkdir(parents=True)
        # Install arbitrary skill that is not flutter/firebase/android/docker
        custom_tool = skills_dir / "my-custom-utility"
        custom_tool.mkdir()
        (custom_tool / "SKILL.md").write_text("# Utility\n")

        res = quartermaster.sweep_project(
            project_path=str(proj),
            library_path=str(sample_skills_library),
            auto_add=False,
            suggest_pruning=True,
            auto_prune=False,
            pruning_mode="soft",
            harness="agy",
        )
        candidate_names = [c["name"] for c in res.get("pruning_candidates", [])]
        # In soft mode, generic custom tools are retained
        assert "my-custom-utility" not in candidate_names

    def test_sweep_prunes_unneeded_plugin(self, tmp_path, sample_skills_library):
        proj = tmp_path / "target-plugin-prune"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname = 'app'\n")

        plugins_dir = proj / ".agents" / "plugins"
        plugins_dir.mkdir(parents=True)
        # Add flutter to central library as a stack plugin
        fl_lib = sample_skills_library / "flutter"
        fl_lib.mkdir(exist_ok=True)
        (fl_lib / "plugin.json").write_text('{"name": "flutter", "tier": "stack"}')

        # Install non-core flutter plugin into a python project
        flutter_plugin = plugins_dir / "flutter"
        flutter_plugin.mkdir()
        (flutter_plugin / "plugin.json").write_text('{"name": "flutter", "tier": "stack"}')

        res = quartermaster.sweep_project(
            project_path=str(proj),
            library_path=str(sample_skills_library),
            auto_add=False,
            suggest_pruning=True,
            auto_prune=True,
            pruning_mode="aggressive",
            harness="agy",
        )
        pruned_names = [p["name"] for p in res.get("pruned_items", [])]
        assert "flutter" in pruned_names
        assert not flutter_plugin.exists()
