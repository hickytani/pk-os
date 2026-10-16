#!/usr/bin/env bash
# lint.sh — Run all code, markdown, YAML, and shell linters.
# Usage: ./scripts/lint.sh

set -euo pipefail

FAILED=0

# Markdown
echo "--- markdownlint ---"
if command -v markdownlint-cli2 &>/dev/null; then
  if markdownlint-cli2 '**/*.md' '#node_modules'; then
    echo "  PASS: markdownlint"
  else
    echo "  FAIL: markdownlint"
    FAILED=1
  fi
else
  echo "--- markdownlint --- (markdownlint-cli2 not found, skipping)"
fi
echo ""

# YAML
echo "--- yamllint ---"
if yamllint .; then
  echo "  PASS: yamllint"
else
  echo "  FAIL: yamllint"
  FAILED=1
fi
echo ""

# Shell scripts
echo "--- shellcheck ---"
if find . -name "*.sh" -not -path "./node_modules/*" -exec shellcheck {} +; then
  echo "  PASS: shellcheck"
else
  echo "  FAIL: shellcheck"
  FAILED=1
fi
echo ""

# Repository structure
echo "--- structure-check ---"
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

missing=0
for f in "${required[@]}"; do
  if [ ! -f "$f" ]; then
    echo "  MISSING: $f"
    missing=1
  fi
done

if [ "$missing" -eq 0 ]; then
  echo "  PASS: structure-check"
else
  echo "  FAIL: structure-check"
  FAILED=1
fi
echo ""

echo "==============================="
if [ "$FAILED" -ne 0 ]; then
  echo "One or more checks failed. See output above."
  exit 1
fi

echo "All lint checks passed."
exit 0
