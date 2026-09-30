import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest

import session_sweep


class TestClaudeSessionSweepHook:
    def test_hook_recent_cooldown_exits_early(self, tmp_path, monkeypatch):
        import hashlib
        monkeypatch.chdir(tmp_path)
        cache_dir = Path(os.path.expanduser("~/.claude/quartermaster/sweep_cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        cwd_hash = hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
        marker_file = cache_dir / f"{cwd_hash}.timestamp"
        # Write timestamp from 10 seconds ago
        marker_file.write_text(str(time.time() - 10))

        # Should exit 0 immediately
        with pytest.raises(SystemExit) as exc:
            session_sweep.main()
        assert exc.value.code == 0

    def test_hook_corrupted_marker_file_continues(self, tmp_path, monkeypatch):
        import hashlib
        monkeypatch.chdir(tmp_path)
        cache_dir = Path(os.path.expanduser("~/.claude/quartermaster/sweep_cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        cwd_hash = hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
        marker_file = cache_dir / f"{cwd_hash}.timestamp"
        marker_file.write_text("corrupted-not-a-number")

        # Mock subprocess.run to verify it continues past the broken marker
        called = []
        def mock_subp(cmd, *args, **kwargs):
            called.append(cmd)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=json.dumps({"additions_recommended": [], "pruning_candidates": []}))

        monkeypatch.setattr(subprocess, "run", mock_subp)

        with pytest.raises(SystemExit) as exc:
            session_sweep.main()
        assert exc.value.code == 0
        assert len(called) == 1

    def test_hook_missing_qm_script_exits_cleanly(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Mock os.path.exists to return False for the script
        orig_exists = os.path.exists
        def mock_exists(p):
            if "quartermaster.py" in str(p):
                return False
            return orig_exists(p)
        monkeypatch.setattr(os.path, "exists", mock_exists)

        with pytest.raises(SystemExit) as exc:
            session_sweep.main()
        assert exc.value.code == 0

    def test_hook_reports_additions_and_prunings(self, tmp_path, monkeypatch, capsys):
        import hashlib
        monkeypatch.chdir(tmp_path)

        def mock_subp(cmd, *args, **kwargs):
            payload = {
                "additions_recommended": [{"name": "new-tool"}],
                "pruning_candidates": [{"name": "old-tool"}],
            }
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=json.dumps(payload))

        monkeypatch.setattr(subprocess, "run", mock_subp)

        with pytest.raises(SystemExit) as exc:
            session_sweep.main()
        assert exc.value.code == 0

        out = capsys.readouterr().out
        assert "[Quartermaster] Workspace audit recommendation:" in out
        assert "1 capability addition(s)" in out
        assert "1 pruning candidate(s)" in out

        # Verify marker file was written in user cache
        cache_dir = Path(os.path.expanduser("~/.claude/quartermaster/sweep_cache"))
        cwd_hash = hashlib.sha256(str(tmp_path).encode("utf-8")).hexdigest()[:16]
        marker_file = cache_dir / f"{cwd_hash}.timestamp"
        assert marker_file.exists()
        assert float(marker_file.read_text()) > 0

    def test_hook_suppresses_exceptions(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Make os.path.exists raise an unexpected exception
        def mock_fail(p):
            raise RuntimeError("Filesystem failure")
        monkeypatch.setattr(os.path, "exists", mock_fail)

        with pytest.raises(SystemExit) as exc:
            session_sweep.main()
        assert exc.value.code == 0
