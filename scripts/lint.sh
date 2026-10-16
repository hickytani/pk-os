#!/usr/bin/env bash
# lint.sh — Run all linters for the PK-OS repository.
# Usage: ./scripts/lint.sh

set -euo pipefail

FAILED=0

run_check() {
  local name="$1"
  shift
  echo "--- $name ---"
  if "$@"; then
    echo "  PASS: $name"
  else
    echo "  FAIL: $name"
    FAILED=1
  fi
  echo ""
}

# Markdown
run_check "markdownlint" markdownlint-cli2 "**/*.md" "#node_modules"

# YAML
run_check "yamllint" yamllint -d "{extends: default, rules: {line-length: {max: 120}}}" .

# Shell scripts
if find . -name "*.sh" -not -path "./node_modules/*" | grep -q .; then
  run_check "shellcheck" bash -c 'find . -name "*.sh" -not -path "./node_modules/*" | xargs shellcheck'
else
  echo "--- shellcheck --- (no .sh files found, skipping)"
fi

# Repository structure
run_check "structure-check" bash -c '
  required=(
    "README.md"
    "LICENSE"
    "CONTRIBUTING.md"
    "SECURITY.md"
    "CODE_OF_CONDUCT.md"
    ".gitignore"
    ".editorconfig"
    ".github/PULL_REQUEST_TEMPLATE.md"
    ".github/workflows/ci.yml"
    "docs/adr/ADR-001-base-distribution.md"
    "docs/architecture/ROADMAP.md"
    "docs/security/THREAT-MODEL.md"
    "docs/testing/FAILURE-MODE-MATRIX.md"
  )
  failed=0
  for f in "${required[@]}"; do
    if [ ! -f "$f" ]; then
      echo "  MISSING: $f"
      failed=1
    fi
  done
  exit $failed
'

echo "==============================="
if [ "$FAILED" -eq 0 ]; then
  echo "All checks passed."
  exit 0
else
  echo "One or more checks failed. See output above."
  exit 1
fi
