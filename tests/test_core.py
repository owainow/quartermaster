from pathlib import Path
import pytest
import quartermaster


class TestCoreDesignation:
    def test_mark_and_unmark_core_in_library(self, sample_skills_library):
        # docker-compose is initially non-core
        res_mark = quartermaster.mark_core("docker-compose", library_path=str(sample_skills_library))
        assert res_mark["status"] == "marked"
        marker_path = sample_skills_library / "docker-compose" / ".core"
        assert marker_path.exists()

        # Unmark
        res_unmark = quartermaster.unmark_core("docker-compose", library_path=str(sample_skills_library))
        assert res_unmark["status"] == "unmarked"
        assert not marker_path.exists()

        # Unmark again - should return not_found
        res_unmark2 = quartermaster.unmark_core("docker-compose", library_path=str(sample_skills_library))
        assert res_unmark2["status"] == "not_found"

    def test_mark_and_unmark_core_in_project(self, tmp_path):
        proj = tmp_path / "my-proj"
        proj.mkdir()
        skills_dir = proj / ".agents" / "skills"
        skills_dir.mkdir(parents=True)
        local_skill = skills_dir / "my-custom-skill"
        local_skill.mkdir()
        (local_skill / "SKILL.md").write_text("# My Custom Skill\n")

        res = quartermaster.mark_core("my-custom-skill", project_path=str(proj))
        assert res["status"] == "marked"
        assert (local_skill / ".core").exists()

        res_unmark = quartermaster.unmark_core("my-custom-skill", project_path=str(proj))
        assert res_unmark["status"] == "unmarked"
        assert not (local_skill / ".core").exists()

    def test_mark_core_nonexistent(self, sample_skills_library):
        res = quartermaster.mark_core("nonexistent-tool-xyz", library_path=str(sample_skills_library))
        assert res["status"] == "not_found"

    def test_list_core(self, sample_skills_library, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        skills_dir = proj / ".agents" / "skills"
        skills_dir.mkdir(parents=True)
        local_core = skills_dir / "local-core-tool"
        local_core.mkdir()
        (local_core / ".core").write_text("core")

        res = quartermaster.list_core(library_path=str(sample_skills_library), project_path=str(proj))
        core_names = [c["name"] for c in res["core_capabilities"]]
        assert "spec" in core_names
        assert "preflight" in core_names
        assert "local-core-tool" in core_names
