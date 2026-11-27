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
│   ├── streaming.py         ← StreamingSession + StreamCheckpoint + reports
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

### Long-lived service boundary

The core pipeline remains the normalization engine. `PipelineRuntime` is an optional orchestration boundary that owns the currently published pipeline snapshot, generation, reload outcome, and health diagnostics. It does not duplicate processor logic or store user text.

```
HTTP / CLI adapter (optional)
          │
          ▼
    PipelineRuntime ── atomic publish ──► ArabicNormalizationPipeline snapshot
          │                                      │
          ├── health / describe                 └── process / batch / metrics
          └── config file watcher (optional)
```

A reload validates and constructs the complete candidate before taking the runtime lock to publish it. Requests that already captured the previous snapshot finish on that object; later requests see the new generation. A failed candidate never replaces the previous snapshot and is represented as `degraded` diagnostics.

The standard-library HTTP adapter in `aranorm.server` is deliberately opt-in. It provides JSON contracts, body-size protection, and basic liveness/readiness endpoints, but it is not a replacement for a production gateway. TLS termination, authentication, authorization, rate limiting, and distributed observability belong outside this module.

### Resumable streaming boundary

`StreamingSession` is an adapter above the existing `ArabicNormalizationPipeline`; it owns file cursors, bounded batches, output commits, and durable progress, while the pipeline remains the only owner of normalization behavior. The session consumes one UTF-8 text item per line and delegates every batch to `process_iter()`, so streaming does not fork or duplicate the core processing path.

```
source UTF-8 file
        │ bounded lines
        ▼
StreamingSession ── process_iter() ──► pipeline snapshot
        │                                  │
        ├── append JSONL output             └── NormalizationResult
        └── atomic StreamCheckpoint
```

A checkpoint is accepted only when its version, source/output paths, source SHA-256, pipeline configuration fingerprint, and output offset are valid. Each committed batch is followed by `StreamCheckpoint.write_atomic()`, which writes a same-directory temporary file, flushes and fsyncs it, then publishes it with `os.replace`. Resume truncates the output back to the recorded `output_bytes` offset before continuing, preventing a partially written tail from being duplicated. The bounded checkpoint size and source `max_input_bytes` limit are defensive controls rather than substitutes for filesystem permissions.

The session rejects identical artifact paths and existing-file aliases, including symlinks, before opening output in write mode. This prevents a misconfigured output or checkpoint from truncating the source or destroying the progress marker. When `lock_enabled=True`, a non-blocking Unix advisory lock is acquired beside the checkpoint for the lifetime of the run; a second owner receives `StreamingSessionConflictError` instead of entering a competing writer path. The lock is deliberately local and is not a distributed lease.

The session records a lightweight source signature before iteration and verifies it at safe batch boundaries. A mutation raises `StreamingSourceChangedError` and leaves the last atomically published checkpoint as the recovery point. The content fingerprint remains the authoritative resume identity; the lightweight signature is an early-detection guard against mid-run mutation.

The optional `/v1/stream` HTTP endpoint and CLI `stream` commands are adapters over this same session. The HTTP endpoint is disabled by default because its payload names local filesystem paths; enabling it is an administrator decision and requires an authentication/authorization boundary outside the standard-library adapter. When `streaming_root` is configured, the server resolves and confines source, output, and checkpoint paths under that existing directory, rejects traversal and symlink escapes, and always enables the session lock. Typed conflicts and source mutations are translated to bounded `409` responses; path policy failures use `403`.

### Declarative pipeline specification

`PipelineSpec` is a versioned, JSON-compatible deployment boundary for the declarative portion of a pipeline. It stores the validated `PipelineConfig`, the supported pipeline class, a canonical SHA-256 configuration fingerprint, and bounded diagnostic metadata. It does not serialize processor instances, open resources, callbacks, or mutable runtime state.

The reconstruction path validates the schema version, rejects unknown fields, checks JSON compatibility, rebuilds through `PipelineConfig.from_dict()`, and compares the resulting fingerprint before returning a pipeline. `PipelineSpec.write_file()` uses a unique temporary file followed by an atomic replace; `PipelineRuntime.reload_from_spec_file()` reuses the existing publish-and-rollback path. This keeps persistence and deployment concerns outside the normalization core while making configuration promotion reproducible.

Installed plugins remain a separate extension boundary. A custom processor can be discovered through the documented entry-point group and then explicitly injected by the application; it is never silently reconstructed from untrusted spec metadata.

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
- `PipelineRuntime` publishes complete pipeline snapshots under an `RLock`; reload does not mutate a snapshot already captured by a request.
- `StreamingSession` is instance-local; checkpoint publication is atomic, resume validates source/output/pipeline identity before truncating or appending, and optional local locking prevents competing writers.
- `StreamingSession` rejects direct or symlink aliases among source/output/checkpoint and detects source mutation at batch boundaries.
- `ConfigReloadWatcher` is a daemon, opt-in file poller; it reports a failed reload without stopping the service and never runs on import.

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
