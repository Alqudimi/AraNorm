# Testing Guide

AraNorm maintains a comprehensive test suite with 420+ tests covering all major components.

---

## Running Tests

```bash
# All tests (recommended)
python -m pytest

# With verbose output
python -m pytest -v

# With coverage
python -m pytest --cov=src/aranorm --cov-report=term-missing --cov-report=html

# Stop on first failure
python -m pytest -x

# Skip slow tests
python -m pytest -m "not slow"

# Run only integration tests (requires optional deps)
python -m pytest -m integration
```

---

## Test Structure

```
tests/
├── __init__.py
├── fixtures/
│   ├── __init__.py
│   └── sample_texts.py        ← Shared text fixtures (BATCH_1000, DIALECT_MARKERS, EDGE_CASES)
├── test_analysis.py           ← TextAnalyzer, SentimentAnalyzer, KeywordExtractor…
├── test_cli.py                ← CLI subcommand tests
├── test_new_features.py       ← Utils, enrichment processors, new analysis modules
├── test_new_processors.py     ← Platform processors, specialized processors
├── test_pipeline.py           ← Integration tests for full pipeline
├── test_pipeline_enhanced.py  ← Builder, config serialization, async, cache
├── test_processors.py         ← Unit tests for each processor
├── test_stages.py             ← Stage-level tests (cleaner, normalizer, dialect_id)
├── test_stop_words/
│   ├── test_context_aware.py  ← ContextAwareProcessor
│   ├── test_dialect.py        ← DialectStopProcessor
│   └── test_integrations.py   ← Stop-word framework integrations
```

---

## Coverage Targets

| Module | Target |
|--------|--------|
| `core/` | ≥ 95% |
| `processors/` | ≥ 90% |
| `stages/` | ≥ 90% |
| `utils/` | ≥ 85% |
| `analysis/` | ≥ 85% |
| `models/` | ≥ 60% (lazy-loaded) |
| `integrations/` | ≥ 60% (optional deps) |

---

## Writing Tests

### Conventions

- One test per behavior.
- Test name format: `test_<component>_<behavior>_<condition>`.
- Use `pytest.mark.parametrize` for multiple input variants.
- Use `pytest.raises` with a specific exception class.

### Example

```python
import pytest
from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.exceptions import InvalidTextError

def test_alef_normalizer_strips_all_variants():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(normalize_alef=True))
    result = pipeline.process("أحمد إبراهيم آمن ٱلله")
    assert "أ" not in result.normalized_text
    assert "إ" not in result.normalized_text
    assert "آ" not in result.normalized_text

def test_pipeline_raises_on_non_string():
    pipeline = ArabicNormalizationPipeline()
    with pytest.raises(InvalidTextError):
        pipeline.process(42)

@pytest.mark.parametrize("text,expected_dialect", [
    ("شلونك وايد زين", "GLF"),
    ("عايز أروح", "EGY"),
    ("كيفك هلق", "LEV"),
])
def test_dialect_detection(text, expected_dialect):
    pipeline = ArabicNormalizationPipeline()
    assert pipeline.process(text).dialect == expected_dialect
```

---

## Testing Optional Dependencies

Tests that require optional packages should be skipped gracefully:

```python
import pytest

pytest.importorskip("sklearn", reason="scikit-learn not installed")

def test_sklearn_adapter():
    from aranorm.integrations.sklearn_stopwords import SklearnStopWordsAdapter
    adapter = SklearnStopWordsAdapter()
    stop_words = adapter.to_sklearn_list()
    assert len(stop_words) > 0
```

---

## Performance Tests

```bash
# Run the benchmark script
python scripts/benchmark.py

# The light preset smoke test (1 000 texts in < 10 s)
python -m pytest tests/test_pipeline.py::test_light_preset_processes_1000_texts_under_10s -v
```
