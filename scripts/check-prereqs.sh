#!/usr/bin/env bash
# check-prereqs.sh — Verify that development prerequisites are installed.
# Phase 0: checks documentation/CI tools only.
# Usage: ./scripts/check-prereqs.sh

set -euo pipefail

FAILED=0

check() {
  local name="$1"
  local cmd="$2"
  local min_version="${3:-}"

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
check_optional() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" &>/dev/null; then
    echo "  OK  $name (installed)"
  else
    echo " INFO $name ($cmd not installed -- not needed until Phase 1)"
  fi
}
check_optional "python3"    python3
check_optional "qemu"       qemu-system-x86_64
check_optional "mkosi"      mkosi
check_optional "debootstrap" debootstrap
check_optional "cosign"     cosign
check_optional "podman"     podman

echo ""
if [ "$FAILED" -eq 0 ]; then
  echo "All required prerequisites found."
  exit 0
else
  echo "One or more required prerequisites are missing."
  echo "See docs/development/SETUP.md for installation instructions."
  exit 1
fi
