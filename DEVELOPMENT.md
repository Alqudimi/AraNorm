# Development Guide

This guide covers everything needed to develop, test, and build AraNorm locally.

---

## Prerequisites

- Python 3.9–3.13
- `git`
- (Optional) `pyenv` or `conda` for Python version management

---

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/Alqudimi/AraNorm.git
cd AraNorm

# 2. Install in editable mode with dev dependencies
pip install -e ".[dev,quality]"

# 3. Install pre-commit hooks
pre-commit install

# 4. Verify setup
python -m pytest tests/ -q
```

---

## Project Layout

```
.
├── src/aranorm/       ← Source code (PEP 517 src layout)
├── tests/             ← Test suite
├── docs/              ← API documentation
├── scripts/           ← Utility scripts (benchmark, etc.)
├── examples/          ← Example scripts
├── .github/           ← GitHub Actions, issue templates
├── pyproject.toml     ← Build configuration and metadata
├── Makefile           ← Common development tasks
└── CHANGELOG.md       ← Release history
```

---

## Common Tasks

```bash
# Run all tests
make test

# Run tests with coverage report
make test-cov

# Format code
make format

# Lint
make lint

# Type-check
make type-check

# Build distribution
make build

# Clean build artifacts
make clean
```

---

## Running a Single Test

```bash
python -m pytest tests/test_pipeline.py::test_pipeline_normalizes_alef_by_default -v
```

---

## Adding a New Processor

1. Create `src/aranorm/processors/my_processor.py`:

```python
"""My new processor."""
from aranorm.processors._base import TextProcessor

class MyProcessor(TextProcessor):
    """One-line description.

    Example
    -------
    >>> MyProcessor().process("input")
    'output'
    """
    name = "my_processor"

    def transform(self, text: str) -> str:
        # your transformation here
        return text
```

2. Export it from `src/aranorm/processors/__init__.py`:

```python
from aranorm.processors.my_processor import MyProcessor
```

3. Add it to the `__all__` list in `src/aranorm/processors/__init__.py`.

4. Wire it into the appropriate stage (e.g., `OrthographicNormalizer`) if needed.

5. Add tests in `tests/test_processors.py`.

---

## Adding a New Analysis Module

1. Create `src/aranorm/analysis/my_analyzer.py`.
2. Add unit tests in `tests/test_analysis.py`.
3. Export from `src/aranorm/analysis/__init__.py`.
4. Document in `docs/API.md`.

---

## Building the Package

```bash
pip install build
python -m build
# Produces dist/aranorm-*.whl and dist/aranorm-*.tar.gz

# Validate with twine
pip install twine
twine check dist/*
```

---

## Updating Data Files

Dialect mappings and stop-word lists live in `src/aranorm/data/`. After editing:

1. Verify the JSON is valid: `python -c "import json; json.load(open('src/aranorm/data/dialect_mappings.json'))"`
2. Run the full test suite.
3. Update `CHANGELOG.md`.

---

## Releasing a New Version

See [RELEASE_PROCESS.md](RELEASE_PROCESS.md).
