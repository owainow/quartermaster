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

def main():
    try:
        cwd = os.getcwd()
        marker_dir = os.path.join(cwd, ".claude")
        marker_file = os.path.join(marker_dir, ".quartermaster-last-sweep")

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

        # Locate quartermaster.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_root = os.path.abspath(os.path.join(script_dir, ".."))
        qm_script = os.path.abspath(os.path.join(plugin_root, "..", "scripts", "quartermaster.py"))

        if not os.path.exists(qm_script):
            sys.exit(0)

        cmd = [
            sys.executable,
            qm_script,
            "--sweep", cwd,
            "--harness", "claude",
            "--no-auto-add",
            "--json",
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            adds = len(data.get("additions", []))
            prunes = len(data.get("pruning_candidates", []))

            if adds > 0 or prunes > 0:
                parts = []
                if adds > 0:
                    parts.append(f"{adds} capability addition(s)")
                if prunes > 0:
                    parts.append(f"{prunes} pruning candidate(s)")
                summary = " and ".join(parts)
                print(f"[Quartermaster] Workspace audit recommendation: {summary} detected. Run /quartermaster sweep to align your project capabilities.")

        os.makedirs(marker_dir, exist_ok=True)
        with open(marker_file, "w", encoding="utf-8") as f:
            f.write(str(now))

    except Exception:
        # Never fail or block session startup on background hook
        pass

    sys.exit(0)

if __name__ == "__main__":
    main()
