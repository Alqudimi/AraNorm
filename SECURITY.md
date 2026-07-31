# Security Policy

## Supported Versions

See [SUPPORTED_VERSIONS.md](SUPPORTED_VERSIONS.md) for which versions receive security updates.

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Report security issues by emailing the maintainer directly or via GitHub's private vulnerability reporting feature:

1. Go to the [Security tab](https://github.com/Alqudimi/AraNorm/security) on GitHub.
2. Click **"Report a vulnerability"**.
3. Provide a description, steps to reproduce, impact assessment, and any suggested mitigations.

You will receive an acknowledgment within **48 hours** and a full response within **7 days**.

## Security Considerations

### AraNorm Core (Zero Dependencies)

The AraNorm core has **zero mandatory runtime dependencies**. The attack surface is minimal:

- **Input validation**: All text inputs are validated via `validate_text()`. Non-string inputs raise `InvalidTextError` immediately.
- **No file writes**: The core pipeline never writes to disk.
- **No network calls**: All processing is purely in-memory.
- **No code execution**: No `eval()`, `exec()`, or dynamic code generation.
- **No secrets**: AraNorm does not handle credentials, tokens, or sensitive data.

### Optional Dependencies

When using optional extras (`[ml]`, `[camel]`, `[full]`), you introduce third-party dependencies. Ensure you:

- Pin dependency versions in production environments.
- Review the security advisories for those packages independently.
- Use `pip audit` or `safety check` in your CI pipeline.

### File I/O

`PipelineConfig.from_file()` reads configuration files from disk. Ensure:

- Configuration files are not writable by untrusted users.
- Only `.json`, `.yaml`, and `.yml` extensions are accepted (other extensions raise `ValueError`).

### Path Traversal

The data loading utilities (`_load_dialect_mappings`, `StopWordsRegistry`) load bundled JSON and text files from within the package directory. These paths are resolved relative to the installed package and are not user-controllable.

## Disclosure Timeline

| Day | Action |
|-----|--------|
| 0   | Report received |
| 1–2 | Acknowledgment sent to reporter |
| 3–7 | Initial assessment and triage |
| 7–30 | Fix developed and tested |
| 30  | Fix released and CVE requested (if applicable) |
| 30+ | Public disclosure (coordinated with reporter) |
