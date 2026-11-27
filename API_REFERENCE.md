# API Reference

Complete reference for the AraNorm public API.

---

## Top-Level Imports

```python
from aranorm import (
    ArabicNormalizationPipeline,
    NormalizationResult,
    PipelineBuilder,
    PipelineConfig,
    Preset,
    DialectTarget,
    StopWordsConfig,
    StopWordsRegistry,
    ResourceLimits,
    BatchProcessingPolicy,
    BatchRetryPolicy,
    BatchRetryReport,
    PipelineHooks,
    CancellationToken,
    PipelineRuntime,
    RuntimeHealth,
    ReloadResult,
    PipelineSpec,
    PIPELINE_SPEC_SCHEMA_VERSION,
    StreamCheckpoint,
    StreamingSession,
    StreamingSessionReport,
    CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_CHECKPOINT_MAX_BYTES,
    DEFAULT_FINGERPRINT_CHUNK_BYTES,
    DEFAULT_SESSION_LOCK_SUFFIX,
    fingerprint_file,
    ProcessingMetrics,
    ProcessingMetricsSnapshot,
    # Exceptions
    AraNormError,
    BatchProcessingError,
    ConfigurationError,
    DataLoadError,
    DialectDetectionError,
    IntegrationUnavailableError,
    InvalidTextError,
    NormalizationError,
    ProcessingTimeoutError,
    ProcessingCancelledError,
    PluginDiscoveryFailure,
    PluginDiscoveryReport,
    ProcessorNotFoundError,
    StreamingSessionError,
    CheckpointError,
    StreamingSessionConflictError,
    StreamingSourceChangedError,
    __version__,
)
```

---

## Pipeline

### `ArabicNormalizationPipeline`

```python
pipeline = ArabicNormalizationPipeline(config=None)
```

**Constructor**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `PipelineConfig \| None` | `None` | Pipeline configuration. Defaults to `PipelineConfig()` (standard preset). |
| `cleaner` | `ContentCleaner \| None` | `None` | Custom content cleaner. |
| `normalizer` | `OrthographicNormalizer \| None` | `None` | Custom orthographic normalizer. |
| `dialect_identifier` | `DialectIdentifier \| None` | `None` | Custom dialect identifier. |

**Methods**

| Method | Signature | Description |
|--------|-----------|-------------|
| `process` | `(text: str) → NormalizationResult` | Process a single text |
| `process_batch` | `(texts, batch_size=32, n_workers=1, on_error=None, progress_callback=None, policy=None, cancellation_token=None) → List[NormalizationResult]` | Process a sequence in bounded chunks while preserving order |
| `process_iter` | `(texts, batch_size=32, n_workers=1, on_error=None, progress_callback=None, total=None, policy=None, cancellation_token=None) → Iterator[NormalizationResult]` | Lazily process an iterable with bounded memory |
| `process_async` | `async (text: str) → NormalizationResult` | Async single-text processing |
| `process_batch_async` | `async (texts, n_workers=4, policy=None, *, batch_size=32, on_error=None, progress_callback=None, cancellation_token=None) → List[NormalizationResult]` | Async bounded batch processing with stable order |
| `process_batch_retry` | `(texts, max_retries=3, batch_size=32, n_workers=1, ..., *, retry_policy=None) → BatchRetryReport` | Bounded retry pass over failed items while preserving input order |
| `process_batch_retry_async` | `async (texts, max_retries=3, n_workers=4, policy=None, *, batch_size=32, ..., retry_policy=None) → BatchRetryReport` | Async parity for bounded retries, cancellation, and stable ordering |
| `describe` | `() → Dict[str, Any]` | Human-readable pipeline description |
| `configuration_fingerprint` | `() → str` | Stable SHA-256 fingerprint of the effective configuration |
| `describe_operational` | `() → Dict[str, Any]` | Versioned, machine-readable operational metadata without input text |
| `to_spec` | `(*, metadata=None) → PipelineSpec` | Export declarative configuration and fingerprint; rejects non-serializable custom runtime components |
| `from_spec` | `classmethod (spec) → ArabicNormalizationPipeline` | Reconstruct a pipeline after schema, class, config, and fingerprint validation |
| `from_preset` | `classmethod (preset, **overrides) → ArabicNormalizationPipeline` | Construct from preset name |
| `from_config_dict` | `classmethod (data) → ArabicNormalizationPipeline` | Construct from dict |
| `builder` | `classmethod () → PipelineBuilder` | Return a builder instance |

### Cooperative cancellation

Create a `CancellationToken` and pass it to `process_iter`, `process_batch`, or `process_batch_async`. Calling `cancel()` stops new work at the next safe boundary and raises `ProcessingCancelledError`. AraNorm does not forcefully interrupt worker threads that are already running.

```python
from aranorm import ArabicNormalizationPipeline, CancellationToken

pipeline = ArabicNormalizationPipeline()
token = CancellationToken()

for result in pipeline.process_iter(texts, cancellation_token=token):
    if should_stop():
        token.cancel()
    print(result.normalized_text)
```

### Operational contracts

`BatchProcessingPolicy` controls failure handling (`fail_fast`, `collect`, or `skip`), while `BatchRetryPolicy` provides a typed, bounded retry contract for `process_batch_retry()` and `process_batch_retry_async()`. `PipelineHooks` exposes lifecycle hooks, `ProcessingMetrics` provides thread-safe counters, and `ResourceLimits` protects text, batch, and worker boundaries. `ProcessingMetrics` also supports `to_json()`, `from_json()`, and `merge()` for aggregation across workers. These contracts are optional and preserve the default behavior when omitted.

`BatchRetryReport` contains the ordered `results`, final `failed_indices`, `recovered_count`, `retry_attempts`, and a sanitized `retry_report`. It is designed for operational automation and does not include the original input text in its failure summary. Setting `max_retries=0` is valid and records initial failures without performing a retry pass.

`describe_operational()` returns a versioned dictionary containing the pipeline class, package version, configuration fingerprint, and sanitized configuration metadata. It is suitable for diagnostics and deployment inventories; it never includes the text being processed.

### `PipelineSpec`

`PipelineSpec` هو عقد JSON versioned لإعادة بناء pipeline من `PipelineConfig` فقط. يحفظ `schema_version` و`pipeline_class` و`config` و`config_fingerprint` و`metadata`؛ وتُرفض الحقول الزائدة، الإصدارات غير المدعومة، البصمات المتلاعب بها، والبيانات غير القابلة لـJSON قبل إعادة البناء. `metadata` تشخيصية ولا تُستخدم لبناء pipeline.

```python
spec = pipeline.to_spec(metadata={"owner": "nlp-platform"})
spec.write_file("pipeline.spec.json")
restored = PipelineSpec.read_file("pipeline.spec.json").to_pipeline()
assert restored.configuration_fingerprint() == pipeline.configuration_fingerprint()
```

`PipelineSpec.write_file()` يكتب الملف ذريًا باستخدام ملف مؤقت فريد، و`read_file()` يفرض حدًا دفاعيًا للحجم. كما يدعم `PipelineRuntime.reload_from_spec()` و`reload_from_spec_file()` النشر الذري مع الحفاظ على snapshot السابق عند الفشل. المواصفة لا تسمح تلقائيًا بتسلسل processors مخصصة أو state runtime؛ يجب تسجيل تلك المكونات كـplugins وإعادة حقنها صراحة في طبقة التطبيق.

### Resumable streaming

`StreamingSession` يعالج ملف UTF-8 كسطر لكل عنصر، ويكتب JSONL تدريجيًا ويحدّث checkpoint ذريًا بعد كل دفعة. يعتمد الاستئناف على تطابق مسار المصدر والخرج، وبصمة المصدر SHA-256، وبصمة إعداد pipeline؛ ولذلك يؤدي تغيير المصدر أو الإعداد إلى `CheckpointError` بدل دمج نتائج غير متوافقة.

```python
from aranorm import StreamingSession

session = StreamingSession(
    pipeline,
    "texts.txt",
    "results.jsonl",
    "results.checkpoint.json",
    batch_size=256,
    n_workers=4,
    max_input_bytes=1024 * 1024 * 1024,
    lock_enabled=True,
)
report = session.run(resume=True)
assert report.completed
```

| العقد | السلوك |
|---|---|
| `StreamCheckpoint` | dataclass مجمدة، versioned، تتحقق من المسارات والبصمات والمؤشرات، وتكتب عبر `write_atomic()` |
| `StreamingSession` | يعيد استخدام `process_iter()`؛ لا يكرر منطق التطبيع، ويحفظ التقدم بعد كل دفعة |
| `StreamingSessionReport` | تقرير typed يتضمن `processed_count` و`next_index` و`resumed` و`completed` و`cancelled` |
| `fingerprint_file(path, chunk_bytes=...)` | SHA-256 مقروء على أجزاء؛ يرفض حجم chunk أقل من 1024 بايت |
| `StreamCheckpoint.load(path, max_bytes=...)` | تحميل JSON محدود الحجم مع رفض schema والحقول والبصمات غير الصحيحة |
| `DEFAULT_SESSION_LOCK_SUFFIX` | اللاحقة `.lock` لملف القفل المحلي بجانب checkpoint |
| `lock_enabled=True` | قفل advisory محلي غير متزامن؛ يرفع `StreamingSessionConflictError` عند وجود مالك آخر |
| `_validate_distinct_paths()` | يرفض تطابق source/output/checkpoint أو aliases وsymlinks للملف نفسه |

الافتراضات الآمنة هي `batch_size=32` و`n_workers=1` وحد مصدر قدره 1 GiB، بينما يبلغ الحد الدفاعي الافتراضي لملف checkpoint مقدار 1 MiB. يستخدم `CancellationToken` للإلغاء التعاوني. ترفع الجلسة `StreamingSessionError` لفشل المصدر أو التشغيل، و`CheckpointError` لمخالفة عقد checkpoint، و`StreamingSessionConflictError` لتعارض القفل، و`StreamingSourceChangedError` عند اكتشاف تغير المصدر أثناء التشغيل. يبقى `lock_enabled=False` في API للحفاظ على التوافق، ويمكن تفعيله صراحةً في التطبيقات المجدولة.

### Plugin discovery

`ProcessorRegistry.discover_report(group="aranorm.processors", strict=False)` discovers processor entry points and returns a deterministic `PluginDiscoveryReport`. The report contains the discovered names and serializable `PluginDiscoveryFailure` records. Invalid plugins and duplicates are isolated by default; `strict=True` raises at the first discovery error. The legacy `discover()` method remains available and still returns only the discovered names. The contract is compatible with installed `dist-info/entry_points.txt` metadata, and distribution-style success, invalid-subclass, and strict-failure paths are covered by `tests/test_plugin_installation_round8.py`.

```python
from aranorm import ProcessorRegistry

registry = ProcessorRegistry()
report = registry.discover_report()
print(report.to_dict())
```

---

### Pipeline runtime and service adapter

`PipelineRuntime` يضيف طبقة إدارة اختيارية فوق `ArabicNormalizationPipeline` للتطبيقات طويلة العمر. لا يغير مسار المعالجة المعتاد، ويحتفظ بـ snapshot صالح أثناء بناء snapshot جديد.

```python
from aranorm import PipelineConfig, PipelineRuntime

runtime = PipelineRuntime(PipelineConfig(preset="standard"))
old_pipeline = runtime.get_pipeline()
outcome = runtime.reload(PipelineConfig(preset="deep"))
assert outcome.success and outcome.generation == 1
assert runtime.health().ready
```

| العقد | السلوك |
|---|---|
| `get_pipeline()` | يعيد snapshot ثابتًا؛ reload لاحق ينشر كائنًا جديدًا ولا يطفر المرجع القديم |
| `reload(config)` | يبني ويحقق الإعداد قبل النشر؛ الفشل لا يهدم snapshot السابق |
| `reload_from_file(path)` | يقرأ JSON/YAML عبر `PipelineConfig.from_file()` ثم يستخدم نفس المسار الذري |
| `reload_from_spec(spec)` | يتحقق من `PipelineSpec` ثم ينشر pipeline جديدًا ذريًا |
| `reload_from_spec_file(path)` | يقرأ مواصفة JSON محدودة الحجم ثم يعيد تحميلها عبر نفس المسار الذري |
| `snapshot_spec()` | يعيد مواصفة snapshot الحالية بصورة دفاعية |
| `describe()` | يضم `describe_operational()` مع generation وstatus منقحين |
| `health()` | يعيد `RuntimeHealth` بحالتي `ready` و`degraded` دون نصوص المستخدم |

`ReloadResult.to_dict()` و`RuntimeHealth.to_dict()` يعيدان payloads ذات `schema_version=1`. عند فشل reload يبقى `generation` دون زيادة، ويُحفظ error type ورسالة bounded للتشخيص فقط.

الوحدة الاختيارية `aranorm.server` تقدم `ThreadingHTTPServer` بلا تبعية إضافية. لا يبدأ listener عند import. أمر التشغيل:

```bash
aranorm serve --host 127.0.0.1 --port 8765 --preset standard
aranorm serve --config pipeline.json --reload-interval 1.0
aranorm serve --spec pipeline.spec.json --reload-interval 1.0
aranorm serve --host 127.0.0.1 --port 8765 --streaming-enabled --streaming-root ./data
aranorm spec export --preset deep --output pipeline.spec.json
aranorm spec validate pipeline.spec.json --json
```

| المسار | الطريقة | العقد |
|---|---|---|
| `/health/live` | `GET` | liveness سريع مع `schema_version` |
| `/health/ready` | `GET` | readiness وgeneration وfingerprint وحالة degraded |
| `/v1/normalize` | `POST` | `{"text": "..."}` ثم `NormalizationResult.to_dict()` |
| `/v1/batch` | `POST` | `{"texts": ["..."], "batch_size": 32, "workers": 1}` |
| `/v1/describe` | `GET` | وصف تشغيلي منزوع الحساسية |
| `/v1/stream` | `POST`، opt-in | `{"source_path": "...", "output_path": "...", "checkpoint_path": "...", "resume": true}` |

يفرض الخادم `Content-Type: application/json`، وحدًا افتراضيًا لحجم body مقداره 2,000,000 بايت، ويرفض JSON غير الصحيح أو الدفعات غير الصالحة بعقود error versioned. يبقى `/v1/stream` معطلاً افتراضيًا؛ وعند تفعيله يمكن تمرير `streaming_root` أو `--streaming-root` لمحصلة مسارات داخل مجلد قائم، وتُرفض المسارات الخارجة أو aliases بـ`403 stream_path_forbidden`. يفرض endpoint القفل المحلي ويعيد `409 stream_conflict` أو `409 stream_source_changed` عند التعارض أو تغير المصدر. يتعامل endpoint مع ملفات محلية من payload، ولذلك يجب عدم تعريضه لمستخدمين غير موثوقين. TLS والمصادقة وrate limiting خارج هذا adapter ويجب توفيرها عبر reverse proxy إنتاجي.

### `NormalizationResult`

| Attribute | Type | Description |
|-----------|------|-------------|
| `original_text` | `str` | Raw input |
| `normalized_text` | `str` | Normalized output |
| `dialect` | `str \| None` | Detected dialect label |
| `dialect_confidence` | `float \| None` | Confidence (0.0–1.0) |
| `coda_text` | `str \| None` | CODA-normalized text |
| `msa_text` | `str \| None` | MSA-normalized text |
| `processing_time_ms` | `float \| None` | Processing duration |
| `applied_steps` | `List[str]` | Processor names that ran |
| `stop_words_removed` | `str \| None` | Text after stop-word removal |
| `stop_words_found` | `Set[str] \| None` | Stop words found |
| `stop_words_stats` | `Dict \| None` | Stop-word statistics |
| `steps_trace` | `List[Tuple[str, str]] \| None` | Optional ordered `(processor, action)` trace; populated only when `emit_steps_trace=True` |
| `is_msa` | `bool \| None` | Property: `dialect == "MSA"` |
| `dialect_label` | `str \| None` | Alias for `dialect` |
| `confidence_score` | `float \| None` | Alias for `dialect_confidence` |

**Methods**: `to_dict()`, `to_json()`, `from_dict()`, `to_csv_row()`

---

## Configuration

### `PipelineConfig`

See [CONFIGURATION.md](CONFIGURATION.md) for the full field reference.

**Key methods**: `to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`, `from_file()`, `copy_with()`, `validate()`

The `emit_steps_trace` boolean is opt-in and defaults to `False`. When enabled, each `NormalizationResult` may carry an ordered `steps_trace`; when disabled, the default remains `None` and legacy equality and CSV output remain unchanged.

### `StopWordsConfig`

See [CONFIGURATION.md](CONFIGURATION.md) for all fields.

---

## Processors

### Orthographic

| Class | Description |
|-------|-------------|
| `ALEFProcessor` | Normalize أإآٱ → ا |
| `AlefMaqsuraProcessor` | Normalize ى → ي |
| `HamzaProcessor` | Normalize hamza placement |
| `DiacriticsProcessor` | Remove tashkeel + tatweel |
| `TatweelProcessor` | Remove كشيدة (ـ) |
| `UnicodeProcessor` | NFKC normalization |
| `LigaturesProcessor` | Normalize Arabic ligatures |
| `TaaMarbutaProcessor` | Normalize ة → ه |
| `DigitsProcessor` | Normalize Arabic/Indic digits to ASCII |
| `RepeatedCharsProcessor` | Reduce يياا to يا |
| `WhitespaceProcessor` | Collapse whitespace |
| `SpacingProcessor` | Fix spacing around punctuation |
| `PunctuationProcessor` | Normalize punctuation marks |

### Content Cleaning

| Class | Description |
|-------|-------------|
| `URLProcessor` | Remove URLs |
| `EmailProcessor` | Remove email addresses |
| `MentionProcessor` | Remove @mentions |
| `HashtagProcessor` | Remove #hashtags (keep text) |
| `HTMLProcessor` | Strip HTML tags |
| `EmojiProcessor` | Remove emoji |
| `NonArabicProcessor` | Remove non-Arabic text |
| `EnglishProcessor` | Remove English text |
| `ArabiziProcessor` | Transliterate Arabizi → Arabic |

### Platform-Specific

| Class | Description |
|-------|-------------|
| `TwitterNormalizer` | Normalize Twitter text |
| `WhatsAppNormalizer` | Normalize WhatsApp text |
| `ChatNormalizer` | Normalize chat/messaging text |

### Stop-Words

| Class | Description |
|-------|-------------|
| `StopWordsProcessor` | Core stop-word processor (Trie-based) |
| `ContextAwareProcessor` | Negation-preserving stop-word removal |
| `DialectStopProcessor` | Dialect-specific stop words |
| `DomainStopProcessor` | Domain-specific stop words |
| `InternetStopProcessor` | Internet/social-media noise |
| `MorphologicalStopProcessor` | Morphological pattern matching |
| `PhraseStopProcessor` | Multi-word collocation removal |
| `ArabiziStopProcessor` | Arabizi filler word removal |

---

## Analysis

```python
from aranorm.analysis import (
    TextAnalyzer,
    SentimentAnalyzer,
    KeywordExtractor,
    ArabicReadabilityAnalyzer,
    ArabicTextSummarizer,
    CorpusAnalyzer,
    TextComparator,
)
```

| Class | Key Method | Returns |
|-------|-----------|---------|
| `TextAnalyzer` | `analyze(text)` | `TextAnalysisResult` |
| `SentimentAnalyzer` | `analyze(text)` | `SentimentResult` |
| `KeywordExtractor` | `extract(text, top_k=10)` | `List[Tuple[str, float]]` |
| `ArabicReadabilityAnalyzer` | `score(text)` | `float` (0–100) |
| `ArabicTextSummarizer` | `summarize(text, max_sentences=3)` | `str` |
| `CorpusAnalyzer` | `analyze(texts)` | `CorpusStats` |
| `TextComparator` | `similarity(text1, text2)` | `float` (0.0–1.0) |

---

## Utilities

```python
from aranorm.utils import (
    word_tokenize, sent_tokenize,
    stem, extract_root,
    compute_stats,
    NormalizationCache, BatchExporter, StreamingBatchExporter,
    TextChunker, chunk_text,
    is_arabic, detect_language,
    normalize_alef, remove_diacritics,
)
```

---

## CLI

```
aranorm <command> [options]

Commands:
  normalize    Normalize Arabic text
  batch        Batch normalization from file
  sentiment    Sentiment analysis
  keywords     Keyword extraction
  readability  Readability score
  summarize    Extractive summarization
  dialect      Dialect identification
  detect       Language/script detection
  compare      Text similarity
  corpus       Corpus-level statistics
  version      Print version (use --json for automation)
  describe     Print versioned pipeline metadata and configuration fingerprint
  plugins      Discover processor entry points and report failures
  stream       Run, resume, or inspect a resumable file session
  serve        Start the optional HTTP adapter
  info         Print pipeline info
```

```bash
aranorm normalize "أهلاً وسهلاً" --preset deep
aranorm batch --file texts.txt --format csv --output out.csv --workers 4
aranorm batch --file texts.txt --stream --batch-size 256 --format jsonl --output out.jsonl --skip-errors
aranorm normalize "النص التجريبي" --json --emit-steps-trace
aranorm batch --file texts.txt --format json --output out.json --retry --max-retries 3 --emit-steps-trace
aranorm dialect "شلونك وايد زين"
aranorm describe --preset deep --json
aranorm version --json
aranorm plugins --json
aranorm plugins --group aranorm.processors --strict
aranorm stream run --source texts.txt --output out.jsonl --checkpoint out.checkpoint.json --json
aranorm stream resume --source texts.txt --output out.jsonl --checkpoint out.checkpoint.json --json
aranorm stream status --checkpoint out.checkpoint.json --json
aranorm serve --streaming-enabled
```

`version --json` returns a stable object with `schema_version`, `package`, and `version`. The JSON form of `plugins` adds `schema_version` to the discovery report; the report's Python `to_dict()` contract remains unchanged.
