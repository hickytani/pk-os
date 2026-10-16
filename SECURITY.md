# Security Policy

## Supported Versions

PK-OS has not yet reached its first release. There are no supported production versions at this time.

| Version | Supported |
|---|---|
| Phase 0 (pre-release) | Development only, no security support |

Once the first release ships (Phase 7), this table will be updated with actual support windows.

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub Issues.**

To report a security issue, please email: security@pk-os.dev (placeholder -- maintainers will update this before first release)

Alternatively, use GitHub private vulnerability reporting:
  https://github.com/hickytani/pk-os/security/advisories/new

### What to include

- A description of the vulnerability.
- Steps to reproduce it.
- The impact you believe it has.
- Any suggested mitigations.
- Whether you want to be credited in the security advisory.

### What to expect

- Acknowledgment within 5 business days.
- An initial assessment within 10 business days.
- We will keep you informed of our progress.
- We request a 90-day embargo before public disclosure to allow a fix to be prepared and released.
- Critical issues that are being actively exploited may require shorter timelines.

## Security Architecture

The project security model and threat model are documented in docs/security/.

Key principles:
- The desktop shell must not have unrestricted administrative access.
- Privileged system services are narrowly scoped.
- Update artifacts are cryptographically signed.
- Secrets must not appear in repository files, logs, or CI outputs.
- All security claims require verifiable evidence.

## Scope

In scope:
- The PK-OS build system and image generation pipeline.
- The desktop shell and system services.
- The update mechanism.
- CI/CD pipeline security.
- Dependencies and supply chain.

Out of scope (currently):
- Upstream kernel vulnerabilities -- report to kernel.org.
- Vulnerabilities in upstream packages -- report to the respective upstream project.
- Social engineering attacks against maintainers.

## Disclosure Policy

We follow a responsible disclosure approach. When a fix is ready:
1. A security advisory is published on GitHub.
2. The fix is released with a clear security note in the changelog.
3. Credit is given to the reporter (if desired).
