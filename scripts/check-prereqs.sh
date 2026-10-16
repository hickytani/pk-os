#!/usr/bin/env bash
# check-prereqs.sh — Verify that development prerequisites are installed.
# Phase 0: checks documentation/CI tools only.
# Usage: ./scripts/check-prereqs.sh

set -euo pipefail

FAILED=0

check() {
  local name="$1"
  local cmd="$2"

  if command -v "$cmd" &>/dev/null; then
    local ver
    ver=$("$cmd" --version 2>&1 | head -1 || true)
    echo "  OK  $name ($ver)"
  else
    echo " FAIL $name ($cmd not found)"
    FAILED=1
  fi
}

echo "=== PK-OS Prerequisite Check (Phase 0) ==="
echo ""
echo "-- Required tools --"
check "git"            git
check "shellcheck"     shellcheck
check "yamllint"       yamllint
check "node"           node
check "markdownlint"   markdownlint-cli2

echo ""
echo "-- Optional / Phase 1+ tools --"
for tool in python3 qemu-system-x86_64 mmdebstrap debootstrap xorriso veritysetup cryptsetup; do
  if command -v "$tool" &>/dev/null; then
    echo "  OK  $tool (installed)"
  else
    echo " INFO $tool (not installed -- will be needed for image builds)"
  fi
done

echo ""
if [ "$FAILED" -ne 0 ]; then
  echo "Prerequisite check FAILED. Please install missing tools."
  exit 1
fi

echo "All required Phase 0 tools are present."
exit 0
