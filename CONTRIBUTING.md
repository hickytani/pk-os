# Contributing to PK-OS

Thank you for your interest in contributing to PK-OS.

## Phase-Gate System

PK-OS development is organized into eight phases. Contributions are expected to target the current active phase. Review the roadmap in docs/architecture/ROADMAP.md before proposing work that spans multiple phases.

## Code of Conduct

All contributors must follow our Code of Conduct (CODE_OF_CONDUCT.md). Be respectful, inclusive, and constructive.

## How to Contribute

### Reporting Bugs

1. Search existing issues before opening a new one.
2. Use the Bug Report template in .github/ISSUE_TEMPLATE/.
3. Include reproduction steps, expected behavior, and actual behavior.
4. Attach relevant logs.
5. Security vulnerabilities: see SECURITY.md (do NOT file public issues).

### Requesting Features

1. Use the Feature Request template.
2. Explain the use case clearly.
3. Note which phase the feature targets.

### Pull Requests

1. Fork the repository and create a branch from main.
2. Follow the coding standards in this document.
3. Ensure all CI checks pass before requesting review.
4. Fill in the PR template completely.
5. At least one maintainer must approve before merging.
6. Squash commits on merge unless commit history is meaningful.

## Engineering Standards

### General

- Every change must have a clear, stated purpose.
- Claim only what is actually verified. Do not document planned features as working.
- A test must actually run to count as passing.
- Security issues require a test or reproduction procedure to be treated as confirmed.

### Shell Scripts

- Use bash with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Pass shellcheck (SC2006, SC2016, SC2034 etc.) with no suppressions unless documented.
- Quote all variable expansions.
- No hardcoded secrets or tokens.

### Python

- Target Python 3.11+.
- Use type hints on all public functions.
- Run through ruff for linting.
- 100% line coverage is not required, but critical paths must have tests.

### YAML / CI

- All YAML must pass yamllint with the project configuration.
- Pin GitHub Actions to a specific commit SHA, not floating tags.
- No credentials or tokens in workflow files.

### Documentation

- Markdown must pass markdownlint-cli2.
- No future features described as currently working.
- Include an accurate "Status" note at the top of any file describing planned functionality.

### Commit Messages

Use the Conventional Commits format:

    <type>(<scope>): <short description>

    [optional body]

    [optional footer]

Types: feat, fix, docs, ci, refactor, test, chore, security

Example:
    docs(adr): add ADR-001 for base distribution selection

### Branch Naming

    feature/<short-name>
    fix/<issue-number>-<short-name>
    docs/<topic>
    ci/<purpose>

## Running Validation Locally

    # Lint all files
    ./scripts/lint.sh

    # Check prerequisites
    ./scripts/check-prereqs.sh

## Architecture Decisions

Significant decisions must be recorded as Architecture Decision Records (ADRs) in docs/adr/.
Use the template at docs/adr/TEMPLATE.md. Each ADR must include alternatives, evaluation criteria, evidence, and the chosen option with rationale.

## License

By contributing to PK-OS, you agree that your contributions will be licensed under the GPL-2.0 License. See LICENSE for details.
