# Changelog

All notable changes to AraNorm will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Quadrilateral root extraction support
- GPU-accelerated batch processing
- REST API server mode (`aranorm serve`)
- Arabic spell-checker integration

---

## [1.2.0] - 2025-07-29

### Added
- **Stop-words subsystem** — full-featured stop-word pipeline with four modes (`remove`, `extract`, `highlight`, `count`) and four scopes (`universal`, `msa_only`, `dialect_aware`, `custom`)
- `ContextAwareProcessor` — negation-preserving stop-word removal (يحفظ النفي)
- `DialectStopProcessor` — dialect-specific stop words for EGY, GLF, LEV, IRQ, NOR, TUN
- `DomainStopProcessor` — domain-specific stop words (medical, legal, financial, news)
- `InternetStopProcessor` — internet/social-media noise removal
- `MorphologicalStopProcessor` — morphologically-aware stop-word filtering
- `PhraseStopProcessor` — multi-word collocation stop-word handling
- `ArabiziStopProcessor` — Arabizi filler-word removal
- `TextComparator` — Jaccard and cosine similarity metrics
- `CorpusAnalyzer` — aggregate statistics across document collections
- `NormalizationCache` — thread-safe LRU memoization wrapper
- `BatchExporter` — CSV, JSON, and JSONL export utilities
- `TextChunker` — sliding-window chunking with overlap support
- `ProgressCallback` — tqdm and console progress reporting
- `StopWordsRegistry` — Trie-backed, thread-safe registry
- Config serialization: `to_json()`, `from_json()`, `to_yaml()`, `from_yaml()`, `from_file()`
- `PipelineConfig.copy_with()` — immutable config derivation
- `PipelineConfig.validate()` — eager configuration validation
- `NormalizationResult.to_dict()`, `to_json()`, `from_dict()`, `to_csv_row()`
- `ArabicNormalizationPipeline.from_preset()`, `from_config_dict()`, `describe()`
- Async pipeline interface: `process_async()`, `process_batch_async()`
- `SDN` (Sudanese) and `MTN` (Mauritanian) dialect markers
- Platform processors: `TwitterNormalizer`, `WhatsAppNormalizer`, `ChatNormalizer`
- Enrichment processors: `CurrencyProcessor`, `DateTimeProcessor`, `NumberWordsProcessor`, `PhoneProcessor`
- `SpellingProcessor` — common misspelling correction
- `RedundancyProcessor` — invisible/zero-width character removal
- `SentenceNormalizerProcessor` — sentence-level normalization
- Full CLI (`aranorm`) with 12 subcommands
- HuggingFace Datasets, pandas, scikit-learn, NLTK, spaCy integrations
- `py.typed` marker for PEP 561 compliance

### Changed
- `PipelineConfig` preset `SOCIAL_MEDIA` now auto-enables filler/internet stop-word removal
- `DialectIdentifier` heuristic weighted scoring with gap-based confidence
- All processors now accept `Optional[ProcessorContext]` for standalone use

### Fixed
- `truncate_repeated_chars` regex pattern to correctly limit runs to `max_run`
- `ProcessorContext.record()` silently ignores duplicate step names

---

## [1.1.0] - 2025-04-15

### Added
- `ArabicTextSummarizer` — TF-IDF extractive summarization
- `SentimentAnalyzer` — lexicon-based sentiment scoring with intensity
- `KeywordExtractor` — TF-IDF keyword extraction with N-gram support
- `ArabicReadabilityAnalyzer` — FARS readability score (0–100)
- `TextAnalyzer` — comprehensive text statistics and complexity metrics
- `ArabicStemmer` — conservative light-stemmer (ISRI-inspired)
- `RootExtractor` — trilateral root extraction via morphological patterns
- `LanguageDetector` — Arabic / Latin / Arabizi / mixed script detection
- `ArabicTokenizer` — sentence and word tokenization with token metadata

### Changed
- Pipeline split into `ContentCleaner` + `OrthographicNormalizer` + `DialectIdentifier` stages
- `ProcessorRegistry` and `ProcessorFactory` made public API

---

## [1.0.0] - 2025-01-10

### Added
- Initial production release
- `ArabicNormalizationPipeline` with four presets (`light`, `standard`, `deep`, `social_media`)
- Core orthographic processors: `ALEFProcessor`, `HamzaProcessor`, `DiacriticsProcessor`, `TatweelProcessor`, `UnicodeProcessor`, `DigitsProcessor`, `LigaturesProcessor`
- Content-cleaning processors: `URLProcessor`, `EmailProcessor`, `MentionProcessor`, `HashtagProcessor`, `HTMLProcessor`, `EmojiProcessor`, `NonArabicProcessor`
- `ArabiziProcessor` — Arabizi-to-Arabic transliteration
- `DialectIdentifier` — heuristic dialect detection for 8 dialects
- `DialectNormalizer` — rule-based CODA and MSA normalization
- MIT License

[Unreleased]: https://github.com/Alqudimi/AraNorm/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/Alqudimi/AraNorm/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Alqudimi/AraNorm/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Alqudimi/AraNorm/releases/tag/v1.0.0
