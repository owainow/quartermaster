#!/usr/bin/env bash
set -e

# Quartermaster Installer for Anthropic Claude Code

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.claude/skills/quartermaster"
CONFIG_DIR="${HOME}/.claude/quartermaster"

echo "================================================================================"
echo "  QUARTERMASTER INSTALLER - ANTHROPIC CLAUDE CODE"
echo "================================================================================"

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found on your PATH." >&2
  exit 1
fi

mkdir -p "${HOME}/.claude/skills"
mkdir -p "${CONFIG_DIR}"

# Initialize default configuration if missing
if [ ! -f "${CONFIG_DIR}/config.json" ]; then
  cat <<EOF > "${CONFIG_DIR}/config.json"
{
  "skills-library": "${HOME}/.gemini/skills-library",
  "auto-add": true,
  "suggest-pruning": true,
  "auto-prune": false,
  "pruning-mode": "aggressive"
}
EOF
fi

if [ -e "${TARGET_DIR}" ] || [ -L "${TARGET_DIR}" ]; then
  echo "Existing Quartermaster skill detected at ${TARGET_DIR}."
  read -p "Overwrite existing installation? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation aborted by user."
    exit 0
  fi
  rm -rf "${TARGET_DIR}"
fi

# Link the Claude-native skill into global Claude skills directory
ln -s "${SCRIPT_DIR}/skills/quartermaster" "${TARGET_DIR}"

echo ""
echo "Quartermaster skill successfully linked to: ${TARGET_DIR}"
echo ""
echo "Claude Code automatically discovers skills in ~/.claude/skills/."
echo "You can now open any project in Claude Code and run:"
echo "  /quartermaster          (Onboard workspace and equip tailored capabilities)"
echo "  /quartermaster sweep    (Audit project tech and review pruning recommendations)"
echo "  /quartermaster catalog  (Browse all available armory capabilities)"
echo ""
echo "Alternative: To run as a local Claude Code plugin with lifecycle hooks:"
echo "  claude --plugin-dir ${SCRIPT_DIR}"
echo ""
echo "================================================================================"
