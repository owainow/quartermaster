import os
import shutil
import subprocess
from pathlib import Path
import pytest
import quartermaster


class TestFindProjectRoot:
    def test_find_project_root_git(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        (root / ".git").mkdir()
        sub = root / "src" / "deep"
        sub.mkdir(parents=True)

        found = quartermaster.find_project_root(str(sub))
        assert found == str(root)

    def test_find_project_root_markers(self, tmp_path):
        # pyproject.toml
        root = tmp_path / "py-proj"
        root.mkdir()
        (root / "pyproject.toml").write_text("[project]\n")
        assert quartermaster.find_project_root(str(root)) == str(root)

        # package.json
        node_root = tmp_path / "node-proj"
        node_root.mkdir()
        (node_root / "package.json").write_text("{}")
        assert quartermaster.find_project_root(str(node_root)) == str(node_root)

    def test_find_project_root_none(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert quartermaster.find_project_root(str(empty)) is None


class TestImportLibraryAsset:
    def test_import_targeted_skill_from_deep_url(self, tmp_path, sample_skills_library, monkeypatch):
        # Deep URL targeting skills/my-skill/SKILL.md
        url = "https://github.com/example/monorepo/blob/main/skills/my-skill/SKILL.md"

        def mock_clone(cmd, *args, **kwargs):
            dest = cmd[-1]
            skill_folder = Path(dest) / "skills" / "my-skill"
            skill_folder.mkdir(parents=True, exist_ok=True)
            (skill_folder / "SKILL.md").write_text(
                "---\n"
                "name: my-skill\n"
                "description: Target skill description\n"
                "---\n"
                "# Content\n"
            )
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_clone)

        res = quartermaster.import_library_asset(
            git_url=url,
            library_path=str(sample_skills_library),
            is_core=True,
        )
        assert res["status"] == "installed"
        assert res["name"] == "my-skill"
        assert res["is_core"] is True
        installed = sample_skills_library / "my-skill"
        assert installed.exists()
        assert (installed / ".core").exists()

    def test_import_targeted_skill_from_raw_github_url(self, tmp_path, sample_skills_library, monkeypatch):
        url = "https://raw.githubusercontent.com/example/repo/main/skills/raw-skill/SKILL.md"

        def mock_clone(cmd, *args, **kwargs):
            dest = cmd[-1]
            skill_folder = Path(dest) / "skills" / "raw-skill"
            skill_folder.mkdir(parents=True, exist_ok=True)
            (skill_folder / "SKILL.md").write_text(
                "---\n"
                "name: raw-skill\n"
                "description: Raw skill description\n"
                "---\n"
                "# Content\n"
            )
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_clone)

        res = quartermaster.import_library_asset(
            git_url=url,
            library_path=str(sample_skills_library),
        )
        assert res["status"] == "installed"
        assert res["name"] == "raw-skill"

    def test_import_whole_repo_skill(self, tmp_path, sample_skills_library, monkeypatch):
        url = "https://github.com/example/standalone-skill.git"

        def mock_clone(cmd, *args, **kwargs):
            dest = cmd[-1]
            p = Path(dest)
            p.mkdir(parents=True, exist_ok=True)
            (p / "SKILL.md").write_text(
                "---\n"
                "name: standalone-skill\n"
                "description: Standalone skill\n"
                "---\n"
                "# Content\n"
            )
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_clone)

        res = quartermaster.import_library_asset(
            git_url=url,
            library_path=str(sample_skills_library),
        )
        assert res["status"] == "installed"
        assert (sample_skills_library / "standalone-skill").exists()

    def test_import_force_overwrite(self, sample_skills_library, monkeypatch):
        url = "https://github.com/example/python-test.git"

        def mock_clone(cmd, *args, **kwargs):
            dest = cmd[-1]
            p = Path(dest)
            p.mkdir(parents=True, exist_ok=True)
            (p / "SKILL.md").write_text("---\nname: python-test\n---\n")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_clone)

        res = quartermaster.import_library_asset(
            git_url=url,
            library_path=str(sample_skills_library),
            force=True,
        )
        assert res["status"] == "installed"

    def test_import_already_exists_without_force(self, sample_skills_library):
        res = quartermaster.import_library_asset(
            git_url="https://github.com/example/python-test.git",
            library_path=str(sample_skills_library),
            force=False,
        )
        assert res["status"] == "exists"

    def test_import_git_clone_failure(self, sample_skills_library, monkeypatch):
        def mock_clone_fail(cmd, *args, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=128, cmd=cmd, output="", stderr="Repository not found"
            )

        monkeypatch.setattr(subprocess, "run", mock_clone_fail)

        res = quartermaster.import_library_asset(
            git_url="https://github.com/example/broken-repo.git",
            library_path=str(sample_skills_library),
        )
        assert res["status"] == "error"
        assert "Repository not found" in res.get("error", "")

    def test_import_missing_skill_in_targeted_repo(self, sample_skills_library, monkeypatch):
        url = "https://github.com/example/empty-repo/blob/main/skills/missing-skill/SKILL.md"

        def mock_clone_empty(cmd, *args, **kwargs):
            dest = cmd[-1]
            Path(dest).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_clone_empty)

        res = quartermaster.import_library_asset(
            git_url=url,
            library_path=str(sample_skills_library),
        )
        assert res["status"] == "error"
        assert "No skill definition" in res.get("error", "")
