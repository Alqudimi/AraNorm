# Troubleshooting

Common problems and how to fix them.

---

## Import Errors

### `ModuleNotFoundError: No module named 'aranorm'`

The package is not installed in the active Python environment.

```bash
pip install aranorm
# or for development
pip install -e .
```

### `ModuleNotFoundError: No module named 'camel_tools'`

You used `use_camel_tools=True` but the optional extra is not installed.

```bash
pip install "aranorm[camel]"
```

### `ModuleNotFoundError: No module named 'transformers'`

You used `dialect_target="coda"` with a `ModelDialectStrategy` but ML deps are missing.

```bash
pip install "aranorm[ml]"
```

---

## Runtime Errors

### `InvalidTextError: expected str, got <class 'NoneType'>`

You passed `None` instead of a string. Validate your input:

```python
text = text or ""  # replace None with empty string
result = pipeline.process(text)
```

### `ConfigurationError: stop_words_config.scope='dialect_aware' requires dialects`

When using `dialect_aware` scope you must specify dialect codes:

```python
StopWordsConfig(
    scope="dialect_aware",
    dialects=frozenset({"EGY", "GLF"}),
)
```

### `ConfigurationError: scope='custom' requires custom_stop_words`

Provide at least one custom stop word:

```python
StopWordsConfig(
    scope="custom",
    custom_stop_words=frozenset({"كلمة"}),
)
```

### `DataLoadError: cannot open dialect_mappings.json`

The package data files are missing. This can happen if you installed from source without running `pip install -e .`:

```bash
pip install -e .
# or
python setup.py develop
```

---

## Incorrect Results

### Alef normalization not working

Ensure `normalize_alef=True` is set (it is the default for `standard` and `deep` presets):

```python
config = PipelineConfig(normalize_alef=True)
```

### Stop words not being removed

1. Check that `stop_words_config` is set on the config:
   ```python
   config = PipelineConfig(stop_words_config=StopWordsConfig(mode="remove"))
   ```
2. Check that the word is actually in the registry:
   ```python
   from aranorm.core.stop_words_registry import StopWordsRegistry
   registry = StopWordsRegistry()
   print("في" in registry.get_words("universal"))
   ```

### Wrong dialect detected

The heuristic identifier uses word-level markers. Short texts with no dialect markers default to MSA. Use CAMeL Tools for better accuracy on short texts:

```bash
pip install "aranorm[camel]"
```

```python
from aranorm.stages.dialect_id import DialectIdentifier
identifier = DialectIdentifier(use_camel_tools=True)
result = identifier.identify("شلون")
```

---

## Performance Issues

### Processing is slow for large batches

Use `n_workers > 1`:

```python
results = pipeline.process_batch(texts, n_workers=4)
```

### Memory usage is high

Use `NormalizationCache` only if you have many **repeated** texts. For unique texts, it wastes memory:

```python
from aranorm.utils.cache import NormalizationCache
cache = NormalizationCache(pipeline, maxsize=1000)  # limit cache size
```

---

## Build / Package Issues

### `twine check dist/*` fails

Ensure your `README.md` uses valid RST or Markdown:

```bash
python -m build
twine check dist/*
```

### Missing data files in wheel

Ensure `pyproject.toml` has the correct `package-data` configuration:

```toml
[tool.setuptools.package-data]
aranorm = ["data/*.json", "data/stopwords/*.txt", "data/stopwords/domains/*.txt", "py.typed"]
```

---

## Getting Help

- Search [existing issues](https://github.com/Alqudimi/AraNorm/issues)
- Open a [new issue](https://github.com/Alqudimi/AraNorm/issues/new/choose)
- Check [FAQ.md](FAQ.md)
