#!/usr/bin/env bash
set -e

# Quartermaster Installer for Google Antigravity (AGY)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.gemini/config/skills/quartermaster"

FORCE=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes|-f|--force)
      FORCE=1
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

# Create symbolic link from repo root to global skills directory
ln -snf "${REPO_ROOT}" "${TARGET_DIR}"

echo ""
echo "Quartermaster successfully linked to: ${TARGET_DIR}"
echo ""
echo "Antigravity automatically discovers skills in ~/.gemini/config/skills/."
echo "You can now open any project in Antigravity and run:"
echo "  /quartermaster          (Onboard workspace and equip tailored capabilities)"
echo "  /quartermaster sweep    (Audit project tech and review pruning recommendations)"
echo "  /quartermaster catalog  (Browse all available armory capabilities)"
echo ""
echo "================================================================================"
