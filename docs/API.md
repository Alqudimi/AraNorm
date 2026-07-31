# AraNorm v1.2.0 — API Reference

## Table of Contents

1. [Pipeline](#pipeline)
2. [PipelineConfig](#pipelineconfig)
3. [NormalizationResult](#normalizationresult)
4. [PipelineBuilder](#pipelinebuilder)
5. [Stop Words](#stop-words)
6. [Text Analysis](#text-analysis)
7. [ReadabilityAnalyzer](#readabilityanalyzer)
8. [TextSummarizer](#textsummarizer)
9. [SentimentAnalyzer](#sentimentanalyzer)
10. [KeywordExtractor](#keywordextractor)
11. [TextComparator](#textcomparator)
12. [CorpusAnalyzer](#corpusanalyzer)
13. [NormalizationCache](#normalizationcache)
14. [BatchExporter](#batchexporter)
15. [LanguageDetector](#languagedetector)
16. [ProgressCallback](#progresscallback)
17. [Integrations](#integrations)
18. [Models](#models)
19. [Exceptions](#exceptions)
20. [CLI Reference](#cli-reference)

---

## Pipeline

### `ArabicNormalizationPipeline`

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

pipeline = ArabicNormalizationPipeline(config: PipelineConfig)
```

**Methods**

| Method | Signature | Description |
|--------|-----------|-------------|
| `process` | `(text: str) -> NormalizationResult` | Normalize a single text. |
| `process_batch` | `(texts, batch_size=32, n_workers=1, on_error=None, progress_callback=None) -> List[NormalizationResult]` | Normalize many texts, optionally in parallel. |
| `builder` | `() -> PipelineBuilder` | Start a fluent builder. |

**Example**

```python
pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
result = pipeline.process("شلونك حبيبي؟")
print(result.normalized_text, result.dialect, result.processing_time_ms)
```

---

## PipelineConfig

```python
from aranorm import PipelineConfig, Preset, DialectTarget

config = PipelineConfig(
    preset="standard",            # "light" | "standard" | "deep" | "social_media"
    dialect_target="none",        # "none" | "coda" | "msa"
    remove_diacritics=True,
    normalize_alef=True,
    stop_words_config=None,
)
```

**Presets**

| Preset | Description |
|--------|-------------|
| `light` | URL + emoji removal only. |
| `standard` | Alef normalization, diacritics, punctuation. |
| `deep` | All of standard + repeated chars, Arabizi handling. |
| `social_media` | Deep + hashtag/mention/RT stripping. |

**Key methods**

```python
# Create a variant without mutating the original
variant = config.copy_with(preset="deep", clean_emojis=True)

# Validate consistency (raises ConfigurationError on conflicts)
config.validate()

# Serialization
json_str  = config.to_json()
cfg2      = PipelineConfig.from_json(json_str)

yaml_str  = config.to_yaml()         # requires PyYAML
cfg3      = PipelineConfig.from_yaml(yaml_str)

cfg4      = PipelineConfig.from_file("config.json")  # .json / .yaml / .yml

# Presets
cfg5 = PipelineConfig.from_preset("social_media", clean_emojis=True)
```

---

## NormalizationResult

```python
@dataclass
class NormalizationResult:
    original_text: str
    normalized_text: str
    dialect: str                    # e.g. "EGY", "GLF", "MSA"
    dialect_confidence: float       # 0.0–1.0
    processing_time_ms: float       # wall-clock time in milliseconds
    applied_steps: List[str]
    processing_metadata: Dict[str, Any]

    # Set when DialectTarget.CODA
    coda_text: Optional[str]
    # Set when DialectTarget.MSA
    msa_text: Optional[str]

    # Set when stop_words_config is provided
    stop_words_removed: Optional[str]
    stop_words_found: Optional[Set[str]]
    stop_words_stats: Optional[Dict[str, Any]]
    stop_words_by_category: Optional[Dict[str, List[str]]]
    stop_words_by_dialect: Optional[Dict[str, List[str]]]
    applied_stop_words_steps: Optional[List[str]]
```

**Methods**

```python
result.to_dict()           # → dict
result.to_json()           # → JSON string
result.to_csv_row()        # → list of str (for CSV writing)

NormalizationResult.from_dict(d)   # reconstruct from dict
```

---

## PipelineBuilder

Fluent builder for composing custom pipelines.

```python
pipeline = (
    ArabicNormalizationPipeline.builder()
    .add_cleaner(urls=True, html=True, emojis=True)
    .add_normalizer(normalize_alef=True, normalize_diacritics=True)
    .add_dialect_processor(normalize_to="msa", supported_dialects=["EGY", "GLF"])
    .add_stop_words(mode="remove", scope="universal", remove_filler=True)
    .build()
)
```

---

## Stop Words

### `StopWordsConfig`

```python
from aranorm import StopWordsConfig

config = StopWordsConfig(
    mode="remove",          # "remove" | "extract" | "highlight" | "count"
    scope="universal",      # "universal" | "msa_only" | "dialect_aware" | "filler" | "social" | "arabizi" | "internet" | "numbers" | "custom"
    dialects=frozenset(),   # required when scope="dialect_aware"
    custom_stop_words=frozenset(),  # required when scope="custom"
    remove_filler=False,
    preserve_negation=True,
)

# Preset factory methods
StopWordsConfig.for_social_media()
StopWordsConfig.for_dialect("EGY", "GLF")
StopWordsConfig.count_only()
```

### `StopWordsRegistry`

```python
from aranorm import StopWordsRegistry

registry = StopWordsRegistry()
words = registry.get_words("universal")   # → Set[str]
stats = registry.get_stats()              # → Dict[str, int]
```

---

## Text Analysis

### `TextAnalyzer`

```python
from aranorm.analysis import TextAnalyzer, TextAnalysisResult

analyzer = TextAnalyzer()
result: TextAnalysisResult = analyzer.analyze("النص العربي")

result.total_words           # int
result.stop_words_count      # int
result.stop_words_ratio      # float
result.content_words         # List[str]
result.estimated_complexity  # str: "simple" | "moderate" | "complex"
result.lexical_diversity     # float (type-token ratio)
result.dialect_hint          # str or None
result.to_dict()
```

---

## ReadabilityAnalyzer

Computes a five-component Arabic readability score (0–100, higher = easier).

```python
from aranorm.analysis import ArabicReadabilityAnalyzer, ReadabilityResult

analyzer = ArabicReadabilityAnalyzer()
result: ReadabilityResult = analyzer.analyze("نص عربي هنا")

result.score                  # float 0–100
result.readability_label      # "very_easy" | "easy" | "moderate" | "complex" | "very_complex"
result.avg_sentence_length    # float (words per sentence)
result.avg_word_length        # float (chars per word)
result.long_word_ratio        # float (words > 6 chars / total)
result.complexity_marker_count  # int (prepositional phrases, nominal chains, etc.)
result.to_dict()
```

**Score bands**

| Score | Label |
|-------|-------|
| 80–100 | `very_easy` |
| 60–79  | `easy` |
| 40–59  | `moderate` |
| 20–39  | `complex` |
| 0–19   | `very_complex` |

---

## TextSummarizer

TF-IDF extractive summarization with position bias and stop-word filtering.

```python
from aranorm.analysis import ArabicTextSummarizer, SummaryResult

summarizer = ArabicTextSummarizer(max_sentences=3)
result: SummaryResult = summarizer.summarize("نص طويل جداً...")

result.summary_text             # str
result.original_sentence_count  # int
result.summary_sentence_count   # int
result.compression_ratio        # float (summary / original)
result.top_keywords             # List[str]
result.selected_indices         # List[int] (original sentence positions)
```

---

## SentimentAnalyzer

Lexicon-based Arabic sentiment analysis (no ML required).

```python
from aranorm.analysis import SentimentAnalyzer, SentimentResult

sa = SentimentAnalyzer()
result: SentimentResult = sa.analyze("هذا المنتج رائع جداً")

result.label           # "positive" | "negative" | "neutral"
result.score           # float (positive = +, negative = -)
result.confidence      # float 0–1
result.positive_words  # List[str]
result.negative_words  # List[str]
result.to_dict()

sa.get_lexicon_stats()  # → Dict with positive/negative/negation word counts
```

---

## KeywordExtractor

```python
from aranorm.analysis import KeywordExtractor, KeywordResult

kw = KeywordExtractor(top_n=10)
result: KeywordResult = kw.extract("نص عربي...")

result.top_keywords       # List[str]
result.keyword_scores     # Dict[str, float]
result.content_word_count # int
result.coverage_ratio     # float (content words / total)
result.to_dict()
```

---

## TextComparator

```python
from aranorm.analysis import TextComparator, SimilarityResult

comp = TextComparator()
result: SimilarityResult = comp.compare("نص أ", "نص ب")

result.overall_similarity     # float 0–1
result.jaccard_similarity     # float
result.cosine_similarity      # float
result.verdict                # "identical" | "very_similar" | "similar" | "related" | "different"
result.shared_content_words   # Set[str]
result.to_dict()
```

---

## CorpusAnalyzer

```python
from aranorm.analysis import CorpusAnalyzer

ca = CorpusAnalyzer()
result = ca.analyze(["doc 1", "doc 2", ...])

result.document_count           # int
result.corpus_stop_word_ratio   # float
result.lexical_diversity        # float
result.top_content_words        # List[Tuple[str, int]]
result.top_stop_words           # List[Tuple[str, int]]
```

---

## NormalizationCache

Thread-safe LRU memoization wrapper around any pipeline.

```python
from aranorm.utils import NormalizationCache

cache = NormalizationCache(pipeline, maxsize=10000)

result = cache.process("text")                          # single
results = cache.process_batch(["t1", "t2"])             # batch (each cached individually)

stats = cache.stats()     # → {"hits": int, "misses": int, "size": int, "maxsize": int}
cache.clear()             # evict all cached entries
```

---

## BatchExporter

Export a list of `NormalizationResult` objects to multiple formats.

```python
from aranorm.utils import BatchExporter

exporter = BatchExporter(
    results,
    fields=["original_text", "normalized_text", "dialect", "dialect_confidence", "processing_time_ms"],
)

# Write to files
exporter.to_csv("output.csv")         # UTF-8-sig for Excel compatibility
exporter.to_json("output.json")
exporter.to_jsonl("output.jsonl")

# Get strings (no file I/O)
csv_str   = exporter.to_csv_string()
json_str  = exporter.to_json_string()
jsonl_str = exporter.to_jsonl_string()

# Pandas DataFrame (requires pandas)
df = exporter.to_dataframe()
```

---

## LanguageDetector

Script-level language/script classification using Unicode character analysis.
No external dependencies required.

```python
from aranorm.utils import LanguageDetector, detect_language, is_arabic

detector = LanguageDetector()

# Simple API
label: str = detect_language("شلونك")      # "arabic"
flag: bool = is_arabic("مرحباً")            # True

# Rich result
from aranorm.utils import DetectionResult

result: DetectionResult = detector.detect_detailed("7abibi shloak")

result.label          # "arabizi" | "arabic" | "latin" | "mixed" | "numeric" | "unknown"
result.arabic_ratio   # float
result.latin_ratio    # float
result.arabizi_score  # float
result.char_count     # int
```

**Labels**

| Label | Meaning |
|-------|---------|
| `arabic` | Predominantly Arabic script |
| `arabizi` | Latin-script Arabic (transliteration) |
| `latin` | Predominantly Latin script |
| `mixed` | Significant mix of Arabic and Latin |
| `numeric` | Mostly digits |
| `unknown` | Cannot classify |

---

## ProgressCallback

Abstract base class for pipeline batch progress reporting.

```python
from aranorm.utils import (
    ProgressCallback,       # ABC
    NoOpProgressCallback,   # Silent no-op (default)
    ConsoleProgressCallback,  # ANSI progress bar
    TqdmProgressCallback,   # tqdm bar (requires tqdm)
)

class MyCallback(ProgressCallback):
    def on_start(self, total: int) -> None: ...
    def on_item(self, idx: int, text: str, success: bool) -> None: ...
    def on_finish(self) -> None: ...

# Use with process_batch
results = pipeline.process_batch(
    texts,
    progress_callback=ConsoleProgressCallback(total=len(texts)),
)
```

---

## Integrations

### `NLTKStopWordsAdapter`

```python
from aranorm.integrations import NLTKStopWordsAdapter

adapter = NLTKStopWordsAdapter()

words: List[str]       = adapter.to_nltk_list()          # sorted list
words: FrozenSet[str]  = adapter.to_frozenset()          # frozenset
filtered: List[str]    = adapter.filter_tokens(["أنا", "سعيد"])  # no NLTK needed
merged: List[str]      = adapter.merge_with_nltk()       # union with NLTK Arabic
merged                 = adapter.register_with_nltk()    # same + stores on adapter
```

### `SklearnStopWordsAdapter`

```python
from aranorm.integrations import SklearnStopWordsAdapter

adapter = SklearnStopWordsAdapter()
sw_set = adapter.to_sklearn_set()          # frozenset for TfidfVectorizer
vectorizer = adapter.build_tfidf_vectorizer(...)
```

### `SpacyStopWordsAdapter`

```python
from aranorm.integrations import SpacyStopWordsAdapter

adapter = SpacyStopWordsAdapter()
spacy_set = adapter.to_spacy_set()
adapter.patch_spacy_model(nlp)    # registers words in a loaded spaCy model
```

### `PandasNormalizer`

```python
from aranorm.integrations import PandasNormalizer

pn = PandasNormalizer(pipeline)
df["normalized"] = pn.transform_series(df["text"])
result_df = pn.transform_dataframe(df, text_col="text")
```

### `HuggingFaceNormalizer`

```python
from aranorm.integrations import HuggingFaceNormalizer

hn = HuggingFaceNormalizer(pipeline)
# Use as a Hugging Face Dataset map function
dataset = dataset.map(hn.map_fn, batched=True)
```

---

## Models

### `TransformersSeq2SeqModel`

Lazy-loading Seq2Seq wrapper.  Model is downloaded on first call to
`predict()` or `predict_batch()`.

```python
from aranorm.models._transformers_model import TransformersSeq2SeqModel

model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en", max_new_tokens=128)

output: str        = model.predict("مرحباً")
outputs: List[str] = model.predict_batch(["مرحباً", "كيف حالك"])

model.is_loaded()   # → bool
model.unload()      # free GPU/CPU memory
```

### `CODAModel`

```python
from aranorm.models import CODAModel

# Model name must be provided (no opinionated default)
model = CODAModel("CAMeL-Lab/arabart")
normalized: str        = model.normalize("شلونك وايد زين")
batch: List[str]       = model.normalize_batch(["text1", "text2"])
```

### `MSAModel`

```python
from aranorm.models import MSAModel

model = MSAModel("Helsinki-NLP/opus-mt-ar-ar")
msa: str         = model.normalize("شلونك؟")
batch: List[str] = model.normalize_batch(["text1", "text2"])
```

---

## Exceptions

| Exception | Base | When |
|-----------|------|------|
| `AraNormError` | `Exception` | All AraNorm errors |
| `NormalizationError` | `AraNormError` | Processor/model failure |
| `DialectDetectionError` | `AraNormError` | Dialect ID failure |
| `InvalidTextError` | `AraNormError, ValueError` | Non-string or empty input |
| `ProcessorNotFoundError` | `AraNormError, LookupError` | Unknown registry key |
| `IntegrationUnavailableError` | `AraNormError, RuntimeError` | Missing optional dependency |
| `ConfigurationError` | `AraNormError, ValueError` | Inconsistent config |
| `ProcessingTimeoutError` | `AraNormError, RuntimeError` | Exceeded time budget |
| `DataLoadError` | `AraNormError, IOError` | Missing data file |
| `BatchProcessingError` | `AraNormError` | Batch partial failure |

---

## CLI Reference

```
aranorm <command> [options]
```

| Command | Description |
|---------|-------------|
| `normalize` | Normalize text or file |
| `batch` | Bulk normalize with CSV/JSON/JSONL export |
| `stopwords` | Analyze stop words |
| `analyze` | Text statistics |
| `readability` | Compute readability score |
| `summarize` | Extractive summarization |
| `sentiment` | Sentiment analysis |
| `keywords` | Keyword extraction |
| `dialect` | Dialect identification |
| `detect` | Script/language detection |
| `compare` | Similarity between two texts |
| `tokenize` | Tokenize into words or sentences |
| `corpus` | Corpus-level analysis from file |
| `info` | Library version + registry stats |
| `version` | Print version and exit |

### `normalize`

```
aranorm normalize [TEXT] [--file FILE] [--output OUT]
                  [--preset {light,standard,deep,social_media}]
                  [--dialect-target {none,coda,msa}]
                  [--keep-diacritics] [--keep-urls] [--clean-emojis]
                  [--stop-words] [--sw-scope SCOPE]
                  [--workers N] [--json]
```

### `batch`

```
aranorm batch --file FILE [--output OUT] [--format {csv,json,jsonl}]
              [--preset PRESET] [--workers N] [--progress]
```

### `corpus`

```
aranorm corpus --file FILE [--top-n N] [--json]
```

### `readability`

```
aranorm readability TEXT [--json]
```

### `summarize`

```
aranorm summarize [TEXT] [--file FILE] [--max-sentences N] [--json]
```

### `detect`

```
aranorm detect TEXT [--json]
```

### `version`

```
aranorm version
```
