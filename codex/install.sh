#!/usr/bin/env bash
set -e

# Quartermaster Installer for OpenAI Codex CLI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.agents/skills/quartermaster"
CODEX_TARGET_DIR="${HOME}/.codex/skills/quartermaster"
CONFIG_DIR="${HOME}/.codex/quartermaster"

FORCE=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes|-f|--force)
      FORCE=1
      ;;
  esac
done

echo "================================================================================"
echo "  QUARTERMASTER INSTALLER - OPENAI CODEX CLI"
echo "================================================================================"

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found on your PATH." >&2
  exit 1
fi

mkdir -p "${HOME}/.agents/skills"
mkdir -p "${HOME}/.codex/skills"
mkdir -p "${CONFIG_DIR}"

LIB_PATH="${HOME}/.agents/skills-library"
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

# Link into ~/.agents/skills/quartermaster and ~/.codex/skills/quartermaster
ln -snf "${SCRIPT_DIR}" "${TARGET_DIR}"
ln -snf "${SCRIPT_DIR}" "${CODEX_TARGET_DIR}"

echo ""
echo "Quartermaster skill successfully linked to:"
echo "  - ${TARGET_DIR}"
echo "  - ${CODEX_TARGET_DIR}"
echo ""
echo "OpenAI Codex CLI natively scans ~/.agents/skills/ and ~/.codex/skills/."
echo "You can now open any repository in Codex CLI and run:"
echo "  /quartermaster          (Onboard workspace and equip tailored capabilities)"
echo "  /quartermaster sweep    (Audit project tech and review pruning recommendations)"
echo "  /quartermaster catalog  (Browse all available armory capabilities)"
echo ""
echo "================================================================================"

