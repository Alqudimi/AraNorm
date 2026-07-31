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
    ProcessorNotFoundError,
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
| `process_batch` | `(texts, batch_size=32, n_workers=1, on_error=None, progress_callback=None) → List[NormalizationResult]` | Process a sequence of texts |
| `process_async` | `async (text: str) → NormalizationResult` | Async single-text processing |
| `process_batch_async` | `async (texts, n_workers=4) → List[NormalizationResult]` | Async batch processing |
| `describe` | `() → Dict[str, Any]` | Human-readable pipeline description |
| `from_preset` | `classmethod (preset, **overrides) → ArabicNormalizationPipeline` | Construct from preset name |
| `from_config_dict` | `classmethod (data) → ArabicNormalizationPipeline` | Construct from dict |
| `builder` | `classmethod () → PipelineBuilder` | Return a builder instance |

---

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
| `is_msa` | `bool \| None` | Property: `dialect == "MSA"` |
| `dialect_label` | `str \| None` | Alias for `dialect` |
| `confidence_score` | `float \| None` | Alias for `dialect_confidence` |

**Methods**: `to_dict()`, `to_json()`, `from_dict()`, `to_csv_row()`

---

## Configuration

### `PipelineConfig`

See [CONFIGURATION.md](CONFIGURATION.md) for the full field reference.

**Key methods**: `to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`, `from_file()`, `copy_with()`, `validate()`

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
    NormalizationCache, BatchExporter,
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
  version      Print version
  info         Print pipeline info
```

```bash
aranorm normalize "أهلاً وسهلاً" --preset deep
aranorm batch --file texts.txt --format csv --output out.csv --workers 4
aranorm dialect "شلونك وايد زين"
```
