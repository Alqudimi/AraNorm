# Architecture

This document describes the internal architecture of AraNorm, its design decisions, and how the components interact.

---

## Overview

AraNorm is structured as a **composable, layered pipeline** where each layer has a single responsibility. The design follows the Strategy pattern, the Chain-of-Responsibility pattern, and the Builder pattern.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ArabicNormalizationPipeline                          │
│                                                                          │
│  ┌──────────────────┐  ┌─────────────────────────┐  ┌───────────────┐  │
│  │  ContentCleaner  │→ │  OrthographicNormalizer  │→ │ DialectStage  │  │
│  │                  │  │                          │  │               │  │
│  │ HTML · URL · @   │  │ alef · hamza · diacritics│  │ identify      │  │
│  │ emoji · #tag     │  │ tatweel · unicode · digits│  │ CODA / MSA   │  │
│  └──────────────────┘  └─────────────────────────┘  └───────────────┘  │
│                                         │                               │
│                              ┌──────────▼──────────┐                   │
│                              │  StopWordsStage      │ (optional)        │
│                              │  remove / extract /  │                   │
│                              │  highlight / count   │                   │
│                              └─────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Package Layout

```
src/aranorm/
├── __init__.py              ← Public API surface (what users import)
├── cli.py                   ← CLI entry point
├── core/
│   ├── base.py              ← Processor ABC + ProcessorContext
│   ├── config.py            ← PipelineConfig + enums + serialization
│   ├── pipeline.py          ← ArabicNormalizationPipeline + NormalizationResult
│   ├── registry.py          ← ProcessorRegistry + ProcessorFactory
│   ├── stop_words_config.py ← StopWordsConfig (immutable dataclass)
│   └── stop_words_registry.py ← Trie-backed stop-word registry
├── stages/
│   ├── cleaner.py           ← ContentCleaner (composes cleaning processors)
│   ├── dialect_id.py        ← DialectIdentifier (heuristic + CAMeL adapter)
│   ├── dialect_norm.py      ← DialectNormalizer (CODA/MSA strategies)
│   ├── morphological.py     ← MorphologicalProcessor (injected adapter)
│   ├── normalizer.py        ← OrthographicNormalizer (composes processors)
│   └── stop_words_stage.py  ← StopWordsStage
├── processors/              ← 25+ individual, composable processors
├── analysis/                ← Text analytics (statistics, sentiment, keywords…)
├── models/                  ← Lazy ML model wrappers (Transformers, CAMeL)
├── integrations/            ← Third-party adapters (pandas, HuggingFace…)
├── utils/                   ← Standalone utilities (tokenizer, stemmer, cache…)
├── exceptions/              ← Exception hierarchy
└── data/                    ← Bundled JSON and text data files
```

---

## Core Abstractions

### `Processor` (ABC)

Every text transformation implements the `Processor` interface:

```python
class Processor(ABC):
    name: str

    @abstractmethod
    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str: ...
```

This minimal interface enables processors to be used standalone or composed into stages.

### `ProcessorContext`

A mutable metadata bag passed through every stage:

- `applied_steps`: ordered list of processor names that ran
- `metadata`: free-form key/value store for inter-processor data

### `PipelineConfig`

A `dataclass` carrying all pipeline flags. Key design decisions:

- **Accepts `str` or enum** for `preset` and `dialect_target` — enables configuration from JSON/YAML without enum imports.
- **`__post_init__`** normalizes string values to enums.
- **Serializable**: `to_json()` / `from_json()` / `to_yaml()` / `from_yaml()` / `from_file()`.
- **Immutable derivation**: `copy_with(**overrides)` never mutates the original.

### `NormalizationResult`

A `dataclass` returned by `pipeline.process()`. All fields are typed. Set fields (`stop_words_found`) are serialized as sorted lists in `to_dict()` for JSON compatibility.

---

## Stages vs. Processors

| Layer      | Responsibility |
|------------|----------------|
| **Stage**  | Composes multiple processors; reads `PipelineConfig` to decide which ones to enable |
| **Processor** | Single transformation; pure text-in / text-out + optional context recording |

Stages own the "which processors to run and in what order" logic. Processors own the "how to transform" logic. This separation makes it easy to add, remove, or reorder processors without touching the stage.

---

## Dialect Detection

AraNorm ships two strategies, selected automatically:

| Strategy | Accuracy | Dependency |
|----------|----------|------------|
| Heuristic (lexical markers) | ~70–80% | None |
| CAMeL Tools (MADAR corpus) | >90% | `pip install aranorm[camel]` |

The heuristic uses a weighted marker table per dialect. The confidence score is derived from the gap between the top-scoring and second-scoring dialect.

---

## Stop-Words Subsystem

The stop-words system is built on a **Trie-backed registry** (`StopWordsRegistry`) for O(k) lookup where k is word length. The registry is loaded lazily and cached.

```
StopWordsConfig
    ↓
StopWordsStage
    ↓ (delegates to)
StopWordsProcessor  ← universal / MSA words (Trie)
DialectStopProcessor ← dialect-specific words
ContextAwareProcessor ← negation-preserving
MorphologicalStopProcessor ← prefix/suffix matching
PhraseStopProcessor ← multi-word collocations
```

---

## Optional Dependencies

AraNorm uses **lazy imports** everywhere an optional dependency is needed:

```python
try:
    from transformers import AutoModelForSeq2SeqLM
except ImportError as error:
    raise IntegrationUnavailableError("Install with: pip install aranorm[ml]") from error
```

This means the core library has **zero mandatory runtime dependencies** and can be imported and used without any `pip install` beyond `aranorm` itself.

---

## Thread Safety

- `ArabicNormalizationPipeline.process()` is **thread-safe** — all state is local to each call.
- `NormalizationCache` uses an `RLock` for thread-safe LRU eviction.
- `StopWordsRegistry` is loaded once and is thereafter read-only.
- `DialectIdentifier` loads the CAMeL model lazily; concurrent first-calls may race, but subsequent calls are safe.

---

## Performance Profile

| Operation | Typical throughput |
|-----------|-------------------|
| `light` preset, single text | ~50 000 texts/s |
| `standard` preset, single text | ~15 000 texts/s |
| `deep` preset, single text | ~8 000 texts/s |
| Batch (n_workers=4) | ~3–4× single-threaded |
| With stop-words stage | ~10–20% overhead |

All benchmarks on a modern laptop (M-series / Ryzen 7). See `scripts/benchmark.py`.
