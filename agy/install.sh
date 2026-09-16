#!/usr/bin/env bash
set -e

# Quartermaster Installer for Google Antigravity (AGY)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.gemini/config/skills/quartermaster"

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
echo "  QUARTERMASTER INSTALLER - GOOGLE ANTIGRAVITY (AGY)"
echo "================================================================================"

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found on your PATH." >&2
  exit 1
fi

mkdir -p "${HOME}/.gemini/config/skills"

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

if [ "$DEV_MODE" -eq 1 ]; then
  # Developer mode: link directly to active repository
  ln -snf "${REPO_ROOT}" "${TARGET_DIR}"
  echo ""
  echo "Quartermaster skill linked in developer mode to: ${TARGET_DIR}"
  echo "Repository changes will take effect live without reinstalling."
else
  # Distribution default: self-contained, relocation-proof physical copy
  mkdir -p "${TARGET_DIR}"
  cp -f "${REPO_ROOT}/SKILL.md" "${TARGET_DIR}/"
  [ -f "${SCRIPT_DIR}/SKILL.md" ] && cp -f "${SCRIPT_DIR}/SKILL.md" "${TARGET_DIR}/"
  rm -rf "${TARGET_DIR}/scripts"
  cp -R "${REPO_ROOT}/scripts" "${TARGET_DIR}/scripts"
  echo ""
  echo "Quartermaster skill successfully installed (self-contained copy) to: ${TARGET_DIR}"
  echo "The installation is fully decoupled from the source repository."
fi

echo ""
echo "Antigravity automatically discovers skills in ~/.gemini/config/skills/."
echo "You can now open any project in Antigravity and run:"
echo "  /quartermaster          (Onboard workspace and equip tailored capabilities)"
echo "  /quartermaster sweep    (Audit project tech and review pruning recommendations)"
echo "  /quartermaster catalog  (Browse all available armory capabilities)"
echo ""
echo "================================================================================"
