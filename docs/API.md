# API Reference — المرجع البرمجي

The complete public API surface of AraNorm 1.15.0, organized by module. Every symbol listed here is exported, typed, and covered by tests.

Import roots:

```python
import aranorm                          # pipeline, config, exceptions, core contracts
from aranorm.analysis import ...        # 45+ analyzers
from aranorm.processors import ...      # 48 processors
from aranorm.utils import ...           # tokenizers, stemmers, cache, exporters
from aranorm.integrations import ...    # pandas, sklearn, spaCy, NLTK, HF adapters
from aranorm.models import ...          # CODAModel, MSAModel, DialectIDModel
```

---

## Table of contents

1. [Pipeline](#pipeline)
2. [PipelineConfig](#pipelineconfig)
3. [StopWordsConfig](#stopwordsconfig)
4. [Batch contracts](#batch-contracts)
5. [Runtime & specs](#runtime--specs)
6. [Streaming](#streaming-1)
7. [Metrics & registry](#metrics--registry)
8. [Utils](#utils)
9. [Exceptions](#exceptions-1)
10. [Models](#models-1)

---

## Pipeline

### `ArabicNormalizationPipeline`

```python
from aranorm import ArabicNormalizationPipeline

pipeline = ArabicNormalizationPipeline(config=None)   # defaults to standard preset
```

Construction:

| Method | Signature | Purpose |
|---|---|---|
| `__init__` | `(config=None, cleaner=None, normalizer=None, dialect_identifier=None, metrics=None, hooks=None)` | Build with full dependency injection |
| `from_preset` | `(preset: str, **overrides) -> Pipeline` (classmethod) | Preset + tweaks |
| `from_config_dict` | `(data: Dict) -> Pipeline` (classmethod) | From plain dict |
| `from_spec` | `(spec) -> Pipeline` (classmethod) | From `PipelineSpec` (fingerprint-verified) |
| `builder` | `() -> PipelineBuilder` (classmethod) | Fluent builder |

Processing:

| Method | Returns | Notes |
|---|---|---|
| `process(text)` | `NormalizationResult` | Single text |
| `process_long_text(text, max_chunk_tokens=512, overlap_tokens=0)` | `NormalizationResult` | Chunked merge for long docs |
| `process_batch(texts, batch_size=32, n_workers=1, on_error=None, progress_callback=None, policy=None, cancellation_token=None)` | `List[NormalizationResult]` | Order-preserving, parallel |
| `process_batch_retry(texts, max_retries=3, ..., retry_policy=None)` | `BatchRetryReport` | Bounded per-item retries |
| `process_iter(texts, ...)` | `Iterator[NormalizationResult]` | Lazy, constant-memory |
| `await process_async(text)` | `NormalizationResult` | Thread-pool backed |
| `await process_batch_async(texts, n_workers=4, ...)` | `List[NormalizationResult]` | Async batch |
| `await process_batch_retry_async(texts, ...)` | `BatchRetryReport` | Async retry |

Introspection:

| Method | Returns |
|---|---|
| `describe()` | Human-readable config summary |
| `describe_operational()` | Versioned machine description |
| `configuration_fingerprint()` | SHA-256 of canonical config |
| `to_spec(metadata=None)` / `metrics_snapshot()` | `PipelineSpec` / `ProcessingMetricsSnapshot` |

### `NormalizationResult` (dataclass)

| Field | Type | Meaning |
|---|---|---|
| `original_text` | `str` | Raw input |
| `normalized_text` | `str` | Final output |
| `dialect` | `Optional[str]` | Detected label (EGY/GLF/LEV/.../MSA) |
| `dialect_confidence` | `Optional[float]` | 0–1 |
| `coda_text` / `msa_text` | `Optional[str]` | Present when `dialect_target` set |
| `processing_metadata` | `Dict[str, Any]` | Stage metadata |
| `applied_steps` | `List[str]` | Processors that ran |
| `processing_time_ms` | `Optional[float]` | Duration |
| `stop_words_removed` | `Optional[str]` | Text after stop-word removal |
| `stop_words_found` | `Optional[Set[str]]` | Matched stop words |
| `stop_words_stats` | `Optional[Dict]` | count / total_tokens / percentage / by_category |
| `stop_words_by_category` / `stop_words_by_dialect` | `Optional[Dict]` | Attribution |
| `steps_trace` | `Optional[List[Tuple[str, str]]]` | When `emit_steps_trace=True` |

Properties: `dialect_label`, `confidence_score`, `is_msa`. Methods: `to_dict()`, `to_json()`, `from_dict()`, `to_csv_row()`.

### `PipelineBuilder`

```python
pipeline = (
    ArabicNormalizationPipeline.builder()
    .add_cleaner(clean_urls=True, clean_mentions=True)          # clean_*/remove_* flags
    .add_normalizer(normalize_alef=True, normalize_tatweel=True)
    .add_dialect_processor(identify=True, normalize_to="msa", supported_dialects=None)
    .add_stop_words(mode="remove", scope="universal")
    .build()
)
```

---

## PipelineConfig

Full field reference in the [Configuration guide](configuration.md). API surface:

| Member | Signature |
|---|---|
| `to_dict()` / `to_json()` / `to_yaml()` | Serialization |
| `from_dict(data)` / `from_json(s)` / `from_yaml(s)` / `from_file(path)` | Deserialization (strict — unknown keys raise) |
| `from_preset(preset, **overrides)` | Preset factory |
| `merge(other)` | Field-aware merge → new config |
| `copy_with(**overrides)` | Flat override → new config |
| `validate()` | Raises `ConfigurationError` on conflicts |

Enums: `Preset` (`light`/`standard`/`deep`/`social_media`), `DialectTarget` (`none`/`coda`/`msa`).

### `ResourceLimits` (frozen)

`max_text_length=1_000_000`, `max_batch_size=10_000`, `max_workers=64`, `reject_null_bytes=True` — plus `to_dict()` / `from_dict()`.

---

## StopWordsConfig

Frozen dataclass — full semantics in the [Stop Words guide](stopwords.md).

| Field | Type | Default |
|---|---|---|
| `mode` | `str` | `"remove"` (`remove`/`extract`/`highlight`/`count`) |
| `scope` | `str` | `"universal"` (`universal`/`msa_only`/`dialect_aware`/`custom`) |
| `dialects` | `FrozenSet[str]` | `frozenset()` (EGY/GLF/LEV/IRQ/NOR/TUN/YEM/MSA) |
| `preserve_negation` | `bool` | `True` |
| `preserve_emphasis` | `bool` | `False` |
| `preserve_prepositions` | `bool` | `False` |
| `remove_filler` | `bool` | `True` |
| `remove_arabizi` / `remove_internet` / `remove_numbers` | `bool` | `False` |
| `custom_stop_words` / `excluded_stop_words` | `Optional[FrozenSet[str]]` | `None` |

Classmethods: `for_social_media()`, `for_dialect(*codes)`, `count_only()`.

### `StopWordsRegistry`

`is_stop(word, dialect=None, is_arabizi=False, is_internet=False)` · `get_words(scope, dialects=None)` · `get_by_category(category)` · `get_stats()` · `add_custom(words)` · `get_all_dialects()` — Trie-backed, O(word-length) lookup, LRU-cached.

---

## Batch contracts

```python
from aranorm import (
    BatchProcessingPolicy,   # mode: "fail_fast" | "collect" | "skip"
    BatchRetryPolicy,        # max_retries=3 (0-10), batch_size=32, n_workers=1
    BatchRetryReport,        # results, failed_indices, retry_report, to_dict()
    CancellationToken,       # cancel(), is_cancelled, raise_if_cancelled()
    PipelineHooks,           # before_process / after_process / on_error callables
    BatchProcessingError,    # .failed_indices, .errors, .results (partial)
)
```

`on_error: ErrorHandler = Callable[[int, str, Exception], Optional[str]]` — return a fallback string or `None` to skip.

---

## Runtime & specs

### `PipelineRuntime`

```python
from aranorm import PipelineRuntime

runtime = PipelineRuntime(config)          # or factory=callable
runtime.process(text)                      # snapshot-consistent
runtime.process_batch(texts, batch_size=32, n_workers=1)
runtime.get_pipeline()
runtime.reload(new_config) -> ReloadResult # atomic; old snapshot kept on failure
runtime.reload_from_file(path) / runtime.reload_from_spec_file(path)
runtime.health() -> RuntimeHealth          # .ready, .status ("ready"/"degraded")
runtime.describe() / runtime.spec() / runtime.generation
```

### `PipelineSpec` (frozen, schema v1)

`from_pipeline(pipeline, metadata=None)` · `from_dict` / `from_json(text, max_bytes=1MiB)` / `read_file(path)` · `to_pipeline()` (fingerprint-verified) · `to_json()` / `write_file(path)` (atomic). Constants: `PIPELINE_SPEC_SCHEMA_VERSION`, `DEFAULT_MAX_SPEC_BYTES`.

### `PipelineSnapshot`

`config`, `stage_order`, `aranorm_version`, `metadata` + `save/load/diff` — via `snapshot_pipeline(config)` or `aranorm snapshot save|restore`.

---

## Streaming

```python
from aranorm import StreamingSession, StreamCheckpoint, StreamingSessionReport, fingerprint_file

fingerprint_file(path, chunk_bytes=1_048_576) -> str            # streamed SHA-256

session = StreamingSession(
    pipeline, source_path, output_path, checkpoint_path,
    batch_size=32, n_workers=1, on_error=None,
    cancellation_token=None, max_input_bytes=1_073_741_824, lock_enabled=False,
)
report = session.run(resume=True)   # -> StreamingSessionReport(processed_count,
                                    #    next_index, resumed, completed, cancelled)
```

Checkpoint invariants: source SHA-256 + pipeline fingerprint + output path must all match, else `CheckpointError`. Source mutated mid-run → `StreamingSourceChangedError`. Another process holds the lock → `StreamingSessionConflictError`. See the [Streaming guide](streaming.md).

---

## Metrics & registry

```python
from aranorm import (
    ProcessingMetrics,             # record(success=, elapsed_ms=), snapshot(), reset(), merge()
    ProcessingMetricsSnapshot,     # total_items, succeeded, failed, average_time_ms,
                                   # throughput_per_second, to_dict/to_json/from_dict
    ProcessorRegistry,             # register/get/names/contains/snapshot/discover_report
    ProcessorFactory,              # create(name, **kwargs), available()
    PluginDiscoveryReport,         # .ok, .discovered, .failures, to_dict()
)
```

Plugin discovery: entry-point group `aranorm.processors` (`aranorm plugins --strict`).

---

## Utils

```python
from aranorm.utils import (
    # Tokenization
    ArabicTokenizer, word_tokenize, sent_tokenize,        # Token, Sentence dataclasses
    # Stemming & roots
    ArabicStemmer, stem, stem_sentence, RootExtractor, extract_root,
    # Language & keyboards
    LanguageDetector, detect_language, is_arabic,
    ArabicKeyboardFixer, fix_keyboard_text,
    # Fuzzy matching
    FuzzyArabicMatcher, fuzzy_search, blended_similarity, canonical_form,
    # Statistics
    compute_stats, compare_stats,                          # TextStats dataclass
    # Chunking
    TextChunker, chunk_text,                               # TextChunk dataclass
    # Caching
    NormalizationCache,                                    # LRU + single-flight
    # Export
    BatchExporter, StreamingBatchExporter, export_jsonl,   # csv/json/jsonl
    # Progress
    ProgressCallback, ConsoleProgressCallback, TqdmProgressCallback, NoOpProgressCallback,
    # Pure helpers
    normalize_alef, remove_diacritics, normalize_unicode, collapse_whitespace,
    strip_punctuation, levenshtein, contains_arabic,
)
from aranorm.utils.dialect_depth import DialectAnalyzer, analyze_dialect  # region scoring
from aranorm.utils.validators import validate_text
```

Highlights:

```python
NormalizationCache(pipeline, maxsize=4096)     # .process (single-flight), .stats(), .invalidate()
compute_stats(text, top_n=10) -> TextStats     # 18 metrics incl. readability_score
ArabicStemmer(strip_prefixes=True, strip_suffixes=True).stem("والكتب")  # → كتب
BatchExporter(results).to_csv/to_json/to_jsonl/to_dataframe
```

---

## Exceptions

All inherit from `AraNormError` (see the [hierarchy diagram](architecture.md#exception-hierarchy)):

```python
from aranorm import (
    AraNormError, NormalizationError, DialectDetectionError, InvalidTextError,
    ProcessorNotFoundError, IntegrationUnavailableError, ConfigurationError,
    ProcessingTimeoutError, ProcessingCancelledError, DataLoadError,
    BatchProcessingError, StreamingSessionError, CheckpointError,
    StreamingSessionConflictError, StreamingSourceChangedError,
)
```

---

## Models

Optional — require `[ml]` / `[camel]` extras (see the [Integrations guide](integrations.md)):

```python
from aranorm.models import CODAModel, MSAModel, DialectIDModel

coda = CODAModel("CAMeL-Lab/arabart")   # any HF Seq2Seq; downloads on first use
coda.normalize("شلونك اليوم") -> str

msa = MSAModel("Helsinki-NLP/opus-mt-ar-ar")
msa.normalize_batch([...]) -> List[str]

did = DialectIDModel(supported_dialects=["EGY", "GLF"])   # needs aranorm[camel]
did.predict("إزيك عامل إيه") -> ("EGY", 0.9)
```
