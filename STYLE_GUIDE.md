# Style Guide

This document defines the coding style for AraNorm. It supplements PEP 8, PEP 257, and PEP 484.

---

## Formatting

- **Line length**: 120 characters (configured in `pyproject.toml`)
- **Formatter**: [black](https://github.com/psf/black) — run `make format` before committing
- **Import sorter**: [isort](https://pycqa.github.io/isort/) with `profile = "black"`
- **Encoding**: UTF-8 everywhere; CSV exports use UTF-8-BOM (`utf-8-sig`) for Excel compatibility

---

## Type Annotations

All public functions, methods, and class attributes **must** be type-annotated.

```python
# ✅ Correct
def normalize(self, text: str, max_length: Optional[int] = None) -> str:
    ...

# ❌ Missing annotations
def normalize(self, text, max_length=None):
    ...
```

Use `from __future__ import annotations` at the top of every source file for forward-reference support.

Use `Optional[X]` (not `X | None`) for Python 3.9 compatibility.

---

## Docstrings

Use **Google style** docstrings for all public functions, classes, and modules.

```python
def process(self, text: str) -> str:
    """Normalize Arabic text.

    Applies all configured processors in sequence.

    Parameters
    ----------
    text:
        Input Arabic string. Must be a non-empty string.

    Returns
    -------
    str
        Normalized text.

    Raises
    ------
    InvalidTextError
        When *text* is not a string.

    Example
    -------
    >>> processor.process("أحمـد")
    'احمد'
    """
```

> **Note**: AraNorm uses NumPy-style section headers (dashes) for readability in long docstrings.

- Every **public class** needs a module-level docstring.
- Every **public method** needs a docstring with at least one `Example`.
- Private methods (`_name`) need a brief one-line docstring only.

---

## Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Module | `snake_case` | `alef_processor.py` |
| Class | `PascalCase` | `ALEFProcessor` |
| Function / method | `snake_case` | `normalize_alef()` |
| Constant | `UPPER_SNAKE` | `_ALEF_VARIANTS` |
| Private | `_leading_underscore` | `_build_processors()` |
| Type variable | `PascalCase` | `T` |

---

## Processor Conventions

- Every processor must define a `name: str` class attribute.
- Processors should inherit from `TextProcessor` (which provides `_record()` boilerplate) or implement `Processor` directly.
- Processors must be **stateless** w.r.t. the text being processed — any state (compiled regexes, loaded data) must be in `__init__` or module-level constants.
- Processors must be **thread-safe**.

---

## Error Handling

- Raise domain-specific exceptions from `aranorm.exceptions`, never raw `Exception`.
- Use `raise XxxError("message") from original_exc` to preserve exception chains.
- Catch only the exceptions you can meaningfully handle; let others propagate.
- Do not swallow exceptions silently — log with `LOGGER.warning(...)` at minimum.

---

## Imports

Order (enforced by isort):
1. Standard library
2. Third-party libraries
3. Local imports (`from aranorm.xxx import ...`)

Use `TYPE_CHECKING` guards for imports only needed at type-check time:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aranorm.core.pipeline import NormalizationResult
```

---

## Data Files

- JSON data files must use UTF-8 encoding and 2-space indentation.
- Stop-word lists (`.txt`) must be one word per line, UTF-8, no BOM.
- Data loading must use `pathlib.Path` (not `os.path`).
- All data loads must be wrapped in a `try/except` that raises `DataLoadError`.
