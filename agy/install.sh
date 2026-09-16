#!/usr/bin/env bash
set -e

# Quartermaster Installer for Google Antigravity (AGY)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.gemini/config/skills/quartermaster"

echo "================================================================================"
echo "  QUARTERMASTER INSTALLER - GOOGLE ANTIGRAVITY (AGY)"
echo "================================================================================"

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found on your PATH." >&2
  exit 1
fi

mkdir -p "${HOME}/.gemini/config/skills"

if [ -e "${TARGET_DIR}" ] || [ -L "${TARGET_DIR}" ]; then
  echo "Existing Quartermaster installation detected at ${TARGET_DIR}."
  read -p "Overwrite existing installation? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation aborted by user."
    exit 0
  fi
  rm -rf "${TARGET_DIR}"
fi

# Create symbolic link from repo root to global skills directory
ln -s "${REPO_ROOT}" "${TARGET_DIR}"

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
