#!/usr/bin/env bash
set -e

# Quartermaster Installer for OpenAI Codex CLI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_DIR="${HOME}/.agents/skills/quartermaster"

echo "================================================================================"
echo "  QUARTERMASTER INSTALLER - OPENAI CODEX CLI"
echo "================================================================================"

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found on your PATH." >&2
  exit 1
fi

mkdir -p "${HOME}/.agents/skills"

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

# Link the Codex harness directory into ~/.agents/skills/quartermaster
ln -s "${SCRIPT_DIR}" "${TARGET_DIR}"

echo ""
echo "Quartermaster skill successfully linked to: ${TARGET_DIR}"
echo ""
echo "OpenAI Codex CLI natively scans ~/.agents/skills/ out of the box."
echo "You can now open any repository in Codex CLI and mention:"
echo "  \$quartermaster          (Onboard workspace and equip tailored capabilities)"
echo "  \$quartermaster sweep    (Audit project tech and review pruning recommendations)"
echo "  \$quartermaster catalog  (Browse all available armory capabilities)"
echo ""
echo "================================================================================"
