#!/usr/bin/env bash
set -e

# Quartermaster Installer for Anthropic Claude Code

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.claude/skills/quartermaster"
CONFIG_DIR="${HOME}/.claude/quartermaster"

FORCE=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes|-f|--force)
      FORCE=1
      ;;
  esac
done

echo "================================================================================"
echo "  QUARTERMASTER INSTALLER - ANTHROPIC CLAUDE CODE"
echo "================================================================================"

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found on your PATH." >&2
  exit 1
fi

mkdir -p "${HOME}/.claude/skills"
mkdir -p "${CONFIG_DIR}"

LIB_PATH="${HOME}/.claude/skills-library"
if [ ! -d "${LIB_PATH}" ] && [ -d "${HOME}/.gemini/skills-library" ]; then
  LIB_PATH="${HOME}/.gemini/skills-library"
fi

# Initialize default configuration if missing
if [ ! -f "${CONFIG_DIR}/config.json" ]; then
  cat <<EOF > "${CONFIG_DIR}/config.json"
{
  "skills-library": "${LIB_PATH}",
  "auto-add": true,
  "suggest-pruning": true,
  "auto-prune": false,
  "pruning-mode": "aggressive"
}
EOF
fi

if [ -e "${TARGET_DIR}" ] || [ -L "${TARGET_DIR}" ]; then
  if [ "$FORCE" -eq 0 ]; then
    if [ -t 0 ]; then
      read -p "Overwrite existing installation at ${TARGET_DIR}? [y/N] " -n 1 -r
      echo
      if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation aborted by user."
        exit 0
      fi
    else
      echo "Non-interactive environment detected; overwriting existing installation."
    fi
  fi
  rm -rf "${TARGET_DIR}"
fi

# Link the Claude-native skill into global Claude skills directory
ln -snf "${SCRIPT_DIR}/skills/quartermaster" "${TARGET_DIR}"

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
