import json
import subprocess
import sys
from pathlib import Path
import pytest
import quartermaster


class TestCLI:
    def test_cli_help_when_no_args(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["quartermaster"])
        ret = quartermaster.main()
        assert ret == 0
        captured = capsys.readouterr()
        assert "Quartermaster:" in captured.out

    def test_cli_catalog(self, sample_skills_library, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["quartermaster", "--catalog", "--library", str(sample_skills_library)])
        ret = quartermaster.main()
        assert ret == 0
        out = capsys.readouterr().out
        assert "QUARTERMASTER ARMORY CATALOG" in out

        # JSON mode
        monkeypatch.setattr(sys, "argv", ["quartermaster", "--catalog", "--library", str(sample_skills_library), "--json"])
        ret = quartermaster.main()
        assert ret == 0
        json_out = json.loads(capsys.readouterr().out)
        assert "skills" in json_out
        assert "plugins" in json_out

    def test_cli_scan(self, sample_project, sample_skills_library, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--scan", str(sample_project), "--library", str(sample_skills_library)]
        )
        ret = quartermaster.main()
        assert ret == 0
        out = capsys.readouterr().out
        assert "Target Workspace:" in out

        # JSON mode
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--scan", str(sample_project), "--library", str(sample_skills_library), "--json"]
        )
        ret = quartermaster.main()
        assert ret == 0
        json_out = json.loads(capsys.readouterr().out)
        assert "technologies" in json_out

    def test_cli_provision(self, sample_project, sample_skills_library, monkeypatch, capsys):
        # Error when no --skills or --plugins
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--provision", str(sample_project), "--library", str(sample_skills_library)]
        )
        assert quartermaster.main() == 1
        capsys.readouterr()

        # Valid provisioning
        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "--provision", str(sample_project),
                "--skills", "python-test",
                "--plugins", "python-stack",
                "--library", str(sample_skills_library),
            ]
        )
        ret = quartermaster.main()
        assert ret == 0
        assert "QUARTERMASTER OUTFITTING REPORT" in capsys.readouterr().out

        # JSON mode
        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "--provision", str(sample_project),
                "--skills", "spec",
                "--library", str(sample_skills_library),
                "--json",
            ]
        )
        ret = quartermaster.main()
        assert ret == 0
        json_out = json.loads(capsys.readouterr().out)
        assert json_out["provisioned_count"] >= 1

    def test_cli_sweep(self, sample_project, sample_skills_library, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "--sweep", str(sample_project),
                "--library", str(sample_skills_library),
                "--aggressive",
                "--no-auto-add",
            ]
        )
        ret = quartermaster.main()
        assert ret == 0
        assert "QUARTERMASTER SWEEP AUDIT REPORT" in capsys.readouterr().out

        # Sweep JSON mode with --soft and --no-prune
        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "--sweep", str(sample_project),
                "--library", str(sample_skills_library),
                "--soft",
                "--no-prune",
                "--json",
            ]
        )
        ret = quartermaster.main()
        assert ret == 0
        json_out = json.loads(capsys.readouterr().out)
        assert "technologies" in json_out

    def test_cli_config_commands(self, monkeypatch, capsys):
        # --config-set
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--config-set", "auto-prune", "true"]
        )
        assert quartermaster.main() == 0
        capsys.readouterr()

        # --config-set JSON
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--config-set", "auto-prune", "false", "--json"]
        )
        assert quartermaster.main() == 0
        assert json.loads(capsys.readouterr().out)["auto-prune"] is False

        # --config-get
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--config-get", "auto-prune"]
        )
        ret = quartermaster.main()
        assert ret == 0
        assert "False" in capsys.readouterr().out

        # --config-get JSON
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--config-get", "auto-prune", "--json"]
        )
        assert quartermaster.main() == 0
        assert json.loads(capsys.readouterr().out)["auto-prune"] is False

        # --config JSON
        monkeypatch.setattr(sys, "argv", ["quartermaster", "--config", "--json"])
        assert quartermaster.main() == 0
        assert "skills-library" in json.loads(capsys.readouterr().out)

        # --config interactive (enter '7' to exit)
        monkeypatch.setattr("builtins.input", lambda _: "7")
        monkeypatch.setattr(sys, "argv", ["quartermaster", "--config"])
        assert quartermaster.main() == 0
        capsys.readouterr()

    def test_cli_core_commands(self, sample_skills_library, sample_project, monkeypatch, capsys):
        # --core-list
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-list", "--library", str(sample_skills_library), "--project", str(sample_project)]
        )
        assert quartermaster.main() == 0
        assert "QUARTERMASTER CORE CAPABILITIES REPORT" in capsys.readouterr().out

        # --core-list JSON
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-list", "--library", str(sample_skills_library), "--json"]
        )
        assert quartermaster.main() == 0
        assert "core_capabilities" in json.loads(capsys.readouterr().out)

        # --core-add
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-add", "docker-compose", "--library", str(sample_skills_library)]
        )
        assert quartermaster.main() == 0
        capsys.readouterr()

        # --core-add JSON
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-add", "docker-compose", "--library", str(sample_skills_library), "--json"]
        )
        assert quartermaster.main() == 0
        assert json.loads(capsys.readouterr().out)["status"] == "marked"

        # --core-rm
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-rm", "docker-compose", "--library", str(sample_skills_library)]
        )
        assert quartermaster.main() == 0
        capsys.readouterr()

        # --core-rm JSON
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-rm", "docker-compose", "--library", str(sample_skills_library), "--json"]
        )
        assert quartermaster.main() == 1  # status is not_found now because it was removed, returning 1
        assert json.loads(capsys.readouterr().out)["status"] == "not_found"

    def test_cli_import_command(self, sample_skills_library, monkeypatch, capsys):
        # Mock subprocess.run for clone
        def mock_clone(cmd, *args, **kwargs):
            dest = cmd[-1]
            p = Path(dest)
            p.mkdir(parents=True, exist_ok=True)
            (p / "SKILL.md").write_text("---\nname: imported-cli-tool\n---\n")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_clone)

        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "--import", "https://github.com/example/imported-cli-tool.git",
                "--library", str(sample_skills_library),
                "--no-project",
            ]
        )
        ret = quartermaster.main()
        assert ret == 0
        assert "Central Armory: Installed" in capsys.readouterr().out

        # JSON mode
        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "--import", "https://github.com/example/imported-cli-tool.git",
                "--library", str(sample_skills_library),
                "--no-project",
                "--json",
            ]
        )
        ret = quartermaster.main()
        assert ret == 0
        assert json.loads(capsys.readouterr().out)["status"] == "exists"

    def test_cli_sync_docs(self, sample_project, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--sync-docs", "--project", str(sample_project), "--harness", "claude"]
        )
        assert quartermaster.main() == 0
        assert "Synchronized project documentation:" in capsys.readouterr().out

        # JSON mode
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--sync-docs", "--project", str(sample_project), "--harness", "codex", "--json"]
        )
        assert quartermaster.main() == 0
        json_out = json.loads(capsys.readouterr().out)
        assert "codex" in json_out

    def test_cli_exception_handling(self, monkeypatch, capsys):
        # Force exception in scan
        def mock_error(*args, **kwargs):
            raise RuntimeError("Simulated crash")
        monkeypatch.setattr(quartermaster, "detect_stack", mock_error)

        monkeypatch.setattr(sys, "argv", ["quartermaster", "--scan", "."])
        assert quartermaster.main() == 1
        assert "Quartermaster error: Simulated crash" in capsys.readouterr().err

        monkeypatch.setattr(sys, "argv", ["quartermaster", "--scan", ".", "--json"])
        assert quartermaster.main() == 1
        err_json = json.loads(capsys.readouterr().err)
        assert err_json["error"] == "Simulated crash"

    def test_cli_update(self, sample_project, sample_skills_library, monkeypatch, capsys):
        # 1. Provision something first
        quartermaster.provision_assets(
            project_path=str(sample_project),
            asset_names=["python-test"],
            library_path=str(sample_skills_library),
        )

        # 2. Update via --update
        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "--update",
                "--project", str(sample_project),
                "--library", str(sample_skills_library),
            ]
        )
        assert quartermaster.main() == 0
        out = capsys.readouterr().out
        assert "QUARTERMASTER ARMORY UPDATE REPORT" in out
        assert "python-test" in out

        # 3. Update via positional update command with target and --json
        monkeypatch.setattr(
            sys, "argv",
            [
                "quartermaster",
                "update",
                "python-test",
                "--project", str(sample_project),
                "--library", str(sample_skills_library),
                "--json",
            ]
        )
        assert quartermaster.main() == 0
        json_out = json.loads(capsys.readouterr().out)
        assert json_out["status"] == "success"
        assert json_out["updated_count"] == 1

    def test_cli_sweep_modes_and_config(self, sample_project, sample_skills_library, monkeypatch, capsys):
        # Soft mode
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--sweep", str(sample_project), "--library", str(sample_skills_library), "--soft"]
        )
        assert quartermaster.main() == 0
        assert "Conservative Retention" in capsys.readouterr().out

        # Aggressive mode
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--sweep", str(sample_project), "--library", str(sample_skills_library), "--aggressive"]
        )
        assert quartermaster.main() == 0
        assert "Strict Stack Alignment" in capsys.readouterr().out

        # Config set & get
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--config-set", "pruning-mode", "soft"]
        )
        assert quartermaster.main() == 0
        capsys.readouterr()

        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--config-get", "pruning-mode"]
        )
        assert quartermaster.main() == 0
        assert "soft" in capsys.readouterr().out

        # Check-only / dry-run mode
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--sweep", str(sample_project), "--library", str(sample_skills_library), "--check-only"]
        )
        assert quartermaster.main() == 0
        capsys.readouterr()

        # Core add & rm
        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-add", "python-test", "--project", str(sample_project), "--library", str(sample_skills_library)]
        )
        assert quartermaster.main() == 0
        capsys.readouterr()

        monkeypatch.setattr(
            sys, "argv",
            ["quartermaster", "--core-rm", "python-test", "--project", str(sample_project), "--library", str(sample_skills_library)]
        )
        assert quartermaster.main() == 0
        assert "Removed Core designation" in capsys.readouterr().out
