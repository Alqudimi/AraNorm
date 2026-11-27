# Contributing to AraNorm

Thank you for your interest in contributing to AraNorm! This document explains how to set up your development environment, submit changes, and follow the project's standards.

شكراً لاهتمامك بالمساهمة في AraNorm! يشرح هذا المستند كيفية تهيئة بيئة التطوير، وتقديم التغييرات، واتباع معايير المشروع.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Making Changes](#making-changes)
5. [Testing](#testing)
6. [Code Quality](#code-quality)
7. [Submitting a Pull Request](#submitting-a-pull-request)
8. [Reporting Bugs](#reporting-bugs)
9. [Requesting Features](#requesting-features)
10. [Releasing](#releasing)

---

## Code of Conduct

This project adheres to the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- `git`

### Fork and Clone

```bash
git clone https://github.com/Alqudimi/AraNorm.git
cd AraNorm
```

---

## Development Setup

```bash
# Install the package in editable mode with all dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

---

## Making Changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes, keeping commits atomic and descriptive.
3. Update `CHANGELOG.md` under `[Unreleased]`.
4. Add or update tests for every code path you touch.
5. Update docstrings and documentation if applicable.

### Branch Naming Conventions

| Prefix      | When to use                       |
|-------------|-----------------------------------|
| `feat/`     | New features                      |
| `fix/`      | Bug fixes                         |
| `docs/`     | Documentation only                |
| `refactor/` | Code restructuring, no behavior change |
| `perf/`     | Performance improvements          |
| `test/`     | Test improvements                 |
| `chore/`    | Build, CI, dependency updates     |

---

## Testing

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/aranorm --cov-report=term-missing

# Run a specific test file
python -m pytest tests/test_pipeline.py -v

# Run only fast tests (skip slow)
python -m pytest -m "not slow"
```

Target: **≥ 90% coverage** on all new code. The suite includes contract, property-based (Hypothesis), concurrency, CLI, and packaging smoke tests — new features should extend the matching suites.

---

## Code Quality

```bash
# Everything in one command
make verify

# Or individually:
black src/ tests/ --line-length=120   # format
isort src/ tests/                     # sort imports
flake8 src/ tests/                    # lint
mypy src/                             # type-check
```

All checks must pass before a PR can be merged. The CI pipeline enforces this.

### Style Summary

- Line length: **120 characters**
- Docstrings: **Google style** with `Parameters`, `Returns`, `Raises`, `Example` sections
- Type hints: **required** on all public functions and methods
- No breaking changes without a deprecation notice and major version bump

See the [style guide](docs/style-guide.md) for the complete style reference.

---

## Submitting a Pull Request

1. Push your branch to your fork.
2. Open a PR against `main` in the upstream repository.
3. Fill in the PR template completely.
4. Ensure all CI checks pass.
5. Request a review from a maintainer.

PRs that add new processors, analysis components, or integrations must include:
- Unit tests with ≥ 90% coverage
- A docstring with at least one `Example`
- An entry in `CHANGELOG.md`

---

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:
- AraNorm version (`aranorm version`)
- Python version
- Minimal reproducible example
- Expected vs. actual output

---

## Requesting Features

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).
Describe the use-case before proposing implementation details.

---

## Releasing

Releases are automated via the [`release.yml`](.github/workflows/release.yml) workflow (PyPI Trusted Publishing — no tokens or secrets required):

1. Update `version` in `pyproject.toml`, `src/aranorm/__init__.py`, and `CHANGELOG.md`.
2. Merge to `main` and wait for the Quality workflow to pass.
3. Tag and push:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
4. The workflow builds sdist + wheel, validates metadata, runs installed-artifact smoke tests, publishes to PyPI, and creates the GitHub Release with artifacts.

One-time setup for the maintainer: register the trusted publisher at
<https://pypi.org/manage/account/publishing/> (project `aranorm`, owner `Alqudimi`, repo `AraNorm`, workflow `release.yml`, environment `pypi`) and create a `pypi` environment in the repository settings.
