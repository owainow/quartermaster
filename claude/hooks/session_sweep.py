#!/usr/bin/env python3
"""
Quartermaster SessionStart Hook for Claude Code.
Performs a fast, non-blocking check (<20ms if recent) to alert developers
if codebase changes warrant a capability sweep.
"""

import json
import os
import subprocess
import sys
import time

SWEEP_INTERVAL_SECONDS = 86400  # 24 hours
TIMEOUT_BACKOFF_SECONDS = 3600   # 1 hour backoff on timeout/error

def main():
    try:
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd in (home, "/", "/tmp"):
            sys.exit(0)

        # Store cache timestamps in user config directory, never inside the active workspace
        import hashlib
        cache_dir = os.path.expanduser("~/.claude/quartermaster/sweep_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cwd_hash = hashlib.sha256(cwd.encode("utf-8")).hexdigest()[:16]
        marker_file = os.path.join(cache_dir, f"{cwd_hash}.timestamp")

        now = time.time()
        if os.path.exists(marker_file):
            try:
                with open(marker_file, "r", encoding="utf-8") as f:
                    last_run = float(f.read().strip())
                if now - last_run < SWEEP_INTERVAL_SECONDS:
                    # Checked recently; exit immediately (<5ms)
                    sys.exit(0)
            except Exception:
                pass

        # Write early timestamp to prevent session startup freeze loops
        try:
            with open(marker_file, "w", encoding="utf-8") as f:
                f.write(str(now))
        except Exception:
            pass

        # Locate quartermaster.py dynamically
        script_dir = os.path.dirname(os.path.abspath(__file__))
        qm_candidates = [
            os.environ.get("QUARTERMASTER_SCRIPT", ""),
            os.path.expanduser("~/.claude/skills/quartermaster/scripts/quartermaster.py"),
            os.path.abspath(os.path.join(script_dir, "..", "skills", "quartermaster", "scripts", "quartermaster.py")),
            os.path.abspath(os.path.join(script_dir, "..", "..", "scripts", "quartermaster.py")),
            os.path.abspath(os.path.join(script_dir, "scripts", "quartermaster.py")),
        ]
        qm_script = None
        for c in qm_candidates:
            if c and os.path.exists(c):
                qm_script = c
                break

        if not qm_script:
            sys.exit(0)

        # Run in strictly read-only check mode: zero file additions, zero pruning, no CLAUDE.md rewrites
        cmd = [
            sys.executable,
            qm_script,
            "--sweep", cwd,
            "--harness", "claude",
            "--check-only",
            "--json",
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            adds = len(data.get("additions_recommended", []))
            prunes = len(data.get("pruning_candidates", []))

            if adds > 0 or prunes > 0:
                parts = []
                if adds > 0:
                    parts.append(f"{adds} capability addition(s)")
                if prunes > 0:
                    parts.append(f"{prunes} pruning candidate(s)")
                summary = " and ".join(parts)
                msg = f"[Quartermaster] Workspace audit recommendation: {summary} detected. Run /quartermaster sweep to align your project capabilities."
                payload = {
                    "systemMessage": msg,
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": msg,
                    },
                }
                print(json.dumps(payload))

    except Exception:
        # Never fail or block session startup on background hook
        pass

    sys.exit(0)

if __name__ == "__main__":
    main()
