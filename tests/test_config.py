import json
import os
import sys
from pathlib import Path
import pytest
import quartermaster


class TestConfigManagement:
    def test_get_active_config_file_fallback_to_global(self, isolated_env):
        # When no config file exists yet, returns GLOBAL_CONFIG_FILE
        active = quartermaster.get_active_config_file()
        assert active == str(isolated_env["global_config"])

    def test_get_active_config_file_precedence(self, isolated_env):
        # Create fallback config
        isolated_env["fallback_config"].write_text(json.dumps({"source": "fallback"}))
        assert quartermaster.get_active_config_file() == str(isolated_env["fallback_config"])

        # Create global config (higher precedence than fallback)
        isolated_env["global_config"].write_text(json.dumps({"source": "global"}))
        assert quartermaster.get_active_config_file() == str(isolated_env["global_config"])

        # Create codex config (higher precedence than global)
        isolated_env["codex_config"].write_text(json.dumps({"source": "codex"}))
        assert quartermaster.get_active_config_file() == str(isolated_env["codex_config"])

        # Create claude config (highest precedence)
        isolated_env["claude_config"].write_text(json.dumps({"source": "claude"}))
        assert quartermaster.get_active_config_file() == str(isolated_env["claude_config"])

    def test_load_default_config_when_none_exists(self, isolated_env):
        cfg = quartermaster.load_config()
        assert cfg["skills-library"] == str(isolated_env["library"])
        assert cfg["auto-add"] is True
        assert cfg["suggest-pruning"] is True
        assert cfg["auto-prune"] is False
        assert cfg["pruning-mode"] == "aggressive"

    def test_load_config_merges_with_defaults(self, isolated_env):
        isolated_env["global_config"].write_text(
            json.dumps({"auto-prune": True, "custom-setting": "custom-val"})
        )
        cfg = quartermaster.load_config()
        assert cfg["auto-prune"] is True
        assert cfg["custom-setting"] == "custom-val"
        assert cfg["auto-add"] is True

    def test_save_config_creates_directories_and_file(self, tmp_path, isolated_env, monkeypatch):
        custom_cfg = tmp_path / "deep" / "nested" / "config.json"
        monkeypatch.setattr(quartermaster, "GLOBAL_CONFIG_FILE", str(custom_cfg))

        quartermaster.save_config({"test_key": "test_val"})
        assert custom_cfg.exists()
        saved = json.loads(custom_cfg.read_text())
        assert saved["test_key"] == "test_val"

    def test_get_and_set_config_value(self, isolated_env):
        assert quartermaster.get_config_value("auto-prune") is False
        assert quartermaster.get_config_value("nonexistent_key") is None

        # Set string
        quartermaster.set_config_value("pruning-mode", "soft")
        assert quartermaster.get_config_value("pruning-mode") == "soft"

        # Set boolean representations
        quartermaster.set_config_value("auto-prune", "true")
        assert quartermaster.get_config_value("auto-prune") is True

        quartermaster.set_config_value("auto-prune", "0")
        assert quartermaster.get_config_value("auto-prune") is False

        quartermaster.set_config_value("auto-add", "no")
        assert quartermaster.get_config_value("auto-add") is False

        quartermaster.set_config_value("auto-add", "yes")
        assert quartermaster.get_config_value("auto-add") is True

    def test_resolve_library_path_custom(self, tmp_path):
        custom = tmp_path / "custom-lib"
        custom.mkdir()
        assert quartermaster.resolve_library_path(str(custom)) == str(custom)
        nonexistent = tmp_path / "does-not-exist"
        assert quartermaster.resolve_library_path(str(nonexistent)) == str(nonexistent)

    def test_resolve_library_path_from_config(self, isolated_env):
        lib = isolated_env["home"] / "configured-lib"
        lib.mkdir()
        quartermaster.set_config_value("skills-library", str(lib))
        assert quartermaster.resolve_library_path() == str(lib)

    def test_resolve_library_path_probe(self, isolated_env, monkeypatch):
        # Empty out config to test probing
        monkeypatch.setattr(quartermaster, "load_config", lambda *args, **kwargs: {})
        probe_target = isolated_env["home"] / ".agents" / "skills-library"
        probe_target.mkdir(parents=True)
        monkeypatch.setattr(quartermaster, "PROBE_LIBRARY_DIRS", [str(probe_target)])
        assert quartermaster.resolve_library_path() == str(probe_target)

    def test_interactive_config_exit_default(self, monkeypatch, capsys):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _: "7")
        quartermaster.interactive_config()
        out = capsys.readouterr().out
        assert "QUARTERMASTER SETTINGS" in out
        assert "No changes made." in out

    def test_interactive_config_toggles(self, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        # Test choice 2 (toggle auto-add)
        monkeypatch.setattr("builtins.input", lambda _: "2")
        quartermaster.interactive_config()
        assert quartermaster.get_config_value("auto-add") is False

        # Test choice 3 (toggle suggest-pruning)
        monkeypatch.setattr("builtins.input", lambda _: "3")
        quartermaster.interactive_config()
        assert quartermaster.get_config_value("suggest-pruning") is False

        # Test choice 4 (toggle auto-prune)
        monkeypatch.setattr("builtins.input", lambda _: "4")
        quartermaster.interactive_config()
        assert quartermaster.get_config_value("auto-prune") is True

        # Test choice 5 (toggle pruning-mode)
        monkeypatch.setattr("builtins.input", lambda _: "5")
        quartermaster.interactive_config()
        assert quartermaster.get_config_value("pruning-mode") == "soft"

        # Test choice 6 (reset defaults)
        monkeypatch.setattr("builtins.input", lambda _: "6")
        quartermaster.interactive_config()
        assert quartermaster.get_config_value("auto-add") is True

    def test_interactive_config_update_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        new_lib = tmp_path / "my-interactive-lib"
        new_lib.mkdir()

        inputs = iter(["1", str(new_lib)])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        quartermaster.interactive_config()
        assert quartermaster.get_config_value("skills-library") == str(new_lib)

    def test_interactive_config_update_path_warning_cancel(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        not_exist = tmp_path / "not-exist-dir"
        inputs = iter(["1", str(not_exist), "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        quartermaster.interactive_config()
        # Should not update
        assert quartermaster.get_config_value("skills-library") != str(not_exist)
