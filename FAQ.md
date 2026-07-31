# Frequently Asked Questions

---

## General

### What is AraNorm?

AraNorm is a production-grade Python library for normalizing Arabic text. It supports Modern Standard Arabic (MSA) and 8+ dialects, provides a composable pipeline architecture, and has zero mandatory runtime dependencies.

### Why use AraNorm instead of PyArabic or CAMeL Tools?

| Feature | AraNorm | PyArabic | CAMeL Tools |
|---------|:-------:|:--------:|:-----------:|
| Unified pipeline API | ✅ | ❌ | ❌ |
| Zero mandatory deps | ✅ | ✅ | ❌ |
| Dialect normalization | ✅ | ❌ | ✅ |
| Social media cleaning | ✅ | ❌ | ❌ |
| Stop-words system | ✅ | ❌ | ❌ |
| Arabizi conversion | ✅ | ❌ | ❌ |
| Batch + async | ✅ | ❌ | ❌ |

AraNorm is also fully type-annotated (PEP 561) and ships with a CLI.

---

## Installation

### Do I need any other packages?

No. The core is dependency-free. Optional extras add CAMeL Tools (dialect model) or Transformers (neural normalization).

### Why does `pip install aranorm[ml]` install PyTorch?

The `[ml]` extra enables neural CODA/MSA normalization via HuggingFace Transformers, which requires PyTorch. For CPU-only usage:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "aranorm[ml]"
```

---

## Usage

### What is the difference between `preset="standard"` and `preset="deep"`?

`standard` applies Unicode normalization, alef/hamza/diacritics normalization, URL cleaning, and whitespace fixing — suitable for most NLP tasks.

`deep` adds repeated-character normalization (`يياا` → `يا`) and is more aggressive with punctuation. Suitable for noisy social media text where spelling irregularities are common.

### How do I normalize without removing diacritics?

```python
config = PipelineConfig(preset="standard", remove_diacritics=False)
```

### How do I process a large file efficiently?

Use `process_batch()` with `n_workers > 1` or the CLI's `--file` option:

```bash
aranorm batch --file large_corpus.txt --format jsonl --output out.jsonl --workers 4
```

### How accurate is the dialect detection?

The built-in heuristic (no extra dependencies) achieves ~70–80% accuracy on common dialects. For >90% accuracy, install CAMeL Tools:

```bash
pip install "aranorm[camel]"
```

Then enable it in code:

```python
from aranorm.stages.dialect_id import DialectIdentifier
identifier = DialectIdentifier(use_camel_tools=True)
```

### Can I use individual processors without the full pipeline?

Yes:

```python
from aranorm.processors import ALEFProcessor, DiacriticsProcessor

text = "مَرْحَبًا بِأَحْمَد"
text = ALEFProcessor().process(text)
text = DiacriticsProcessor().process(text)
print(text)  # "مرحبا باحمد"
```

### How do I add custom stop words?

```python
from aranorm import PipelineConfig, StopWordsConfig

config = PipelineConfig(
    stop_words_config=StopWordsConfig(
        mode="remove",
        scope="custom",
        custom_stop_words=frozenset({"كلمة", "مثال", "نص"}),
    )
)
```

---

## Performance

### How fast is AraNorm?

On a modern CPU (single thread):
- `light` preset: ~50 000 texts/second
- `standard` preset: ~15 000 texts/second
- `deep` preset: ~8 000 texts/second

Use `n_workers > 1` in `process_batch()` for multi-threaded throughput.

### Does AraNorm use the GIL?

All processing is pure Python so the GIL applies. For CPU-bound batch workloads, use multiprocessing instead of threading if extreme throughput is required. The `n_workers` parameter uses `ThreadPoolExecutor`, which is effective for I/O-bound pipelines (e.g., with external model calls).

---

## Errors

### `InvalidTextError: expected str, got int`

You passed a non-string value to `pipeline.process()`. All inputs must be Python strings.

### `IntegrationUnavailableError: CAMeL Tools is required`

Install the optional extra: `pip install "aranorm[camel]"`.

### `ConfigurationError: stop_words_config.scope='dialect_aware' requires dialects`

When using `scope="dialect_aware"`, you must specify which dialects:

```python
StopWordsConfig(scope="dialect_aware", dialects=frozenset({"EGY", "GLF"}))
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to submit issues, feature requests, and pull requests.
