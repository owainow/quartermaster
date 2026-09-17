#!/usr/bin/env bash
set -e

# Quartermaster Installer for Anthropic Claude Code

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.claude/skills/quartermaster"
CONFIG_DIR="${HOME}/.claude/quartermaster"

FORCE=0
DEV_MODE=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes|-f|--force)
      FORCE=1
      ;;
    --dev|--link)
      DEV_MODE=1
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

LIB_PATH="~/.claude/skills-library"
if [ ! -d "${HOME}/.claude/skills-library" ] && [ -d "${HOME}/.gemini/skills-library" ]; then
  LIB_PATH="~/.gemini/skills-library"
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
      echo "Error: Existing installation found at ${TARGET_DIR}." >&2
      echo "In non-interactive mode, pass --force or -y to overwrite." >&2
      exit 1
    fi
  fi
  rm -rf "${TARGET_DIR}"
fi

if [ "$DEV_MODE" -eq 1 ]; then
  # Developer mode: link skill files and scripts directly to active repository
  mkdir -p "${TARGET_DIR}"
  ln -snf "${SCRIPT_DIR}/skills/quartermaster/SKILL.md" "${TARGET_DIR}/SKILL.md"
  if [ -d "${SCRIPT_DIR}/skills/quartermaster/references" ]; then
    ln -snf "${SCRIPT_DIR}/skills/quartermaster/references" "${TARGET_DIR}/references"
  fi
  ln -snf "${REPO_ROOT}/scripts" "${TARGET_DIR}/scripts"
  echo ""
  echo "Quartermaster skill linked in developer mode to: ${TARGET_DIR}"
  echo "Repository changes will take effect live without reinstalling."
else
  # Distribution default: self-contained, relocation-proof physical copy
  mkdir -p "${TARGET_DIR}"
  cp -R "${SCRIPT_DIR}/skills/quartermaster/"* "${TARGET_DIR}/" 2>/dev/null || cp -f "${SCRIPT_DIR}/skills/quartermaster/SKILL.md" "${TARGET_DIR}/"
  rm -rf "${TARGET_DIR}/scripts"
  cp -R "${REPO_ROOT}/scripts" "${TARGET_DIR}/scripts"
  echo ""
  echo "Quartermaster skill successfully installed (self-contained copy) to: ${TARGET_DIR}"
  echo "The installation is fully decoupled from the source repository."
fi

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
