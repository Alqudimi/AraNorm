# Changelog

All notable changes to AraNorm are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.15.0] — 2026-11-28

First public release on PyPI.

### Added
- `RhetoricalQuestionAnalyzer` / `analyze_rquestions`: Arabic interrogative
  detection covering inversion particles (أليس، ألم، ألا، أما، أليسوا),
  two-word inversion heads (ألم يكن), attached-hamza proclitics (أَ + verb),
  neutral-particle direct questions (هل + ؟), discourse-question markers
  (بأي، لماذا، كيف تظن، من ذا), and bare question sentences. Reports
  per-question spans with types, inversion/direct/marker counts, question
  density per 100 words, and an `interrogative-rich / moderate / plain`
  label (CLI: `rquestions`).
- `AnaphoraAnalyzer` / `analyze_anaphora`: cross-sentence cohesion engine
  tracking attached clitic pronouns (ـه، ـها، ـهم، نا...), independent
  pronouns (هو، هي، نحن...), demonstratives (هذا، تلك، أولئك), relative
  links (الذي، التي، الذين), and lexical re-mentions across sentence
  windows. Reports a variety-weighted cohesion score (0–1), reference
  density, mention spans, and a `tightly-cohesive / moderate / loose`
  label (CLI: `anaphora`).
- `WordPlayAnalyzer` / `analyze_wordplay`: Arabic wordplay detection built
  on consonant-skeleton phonetic similarity: jinās tām (exact skeleton
  match), jinās nāqiṣ (similarity ≥ 0.8), saj' via sentence-final rhyme
  runs, and pun words flanked by two distinct near-skeleton neighbours
  (CLI: `wordplay`).
- `NumericAnalyzer` now classifies written ordinals (الأول، الثانية،
  العشرين...) as a new `ordinal` span category.
- `QualityScoreAnalyzer` gained an eighth component `rhetorical_depth`
  (weight 0.03) blending rhetorical-questioning intensity with
  cross-sentence cohesion.

### Changed
- `AnalysisProfiler` now ships **22 axes** (was 19) adding `rquestions`,
  `anaphora` and `wordplay`, plus cross-signal insights.
- Packaging modernized to PEP 621 / PEP 639: SPDX license expression,
  verified publisher metadata, and a clean sdist manifest.
- Repository restructured for the public PyPI launch: consolidated
  documentation under `docs/`, expanded examples, community health files,
  and automated release publishing via GitHub Actions (Trusted Publishing).

### Fixed
- `ConfigReloadWatcher` now detects same-tick config rewrites on filesystems
  with coarse mtime granularity by comparing `(mtime, size)` instead of mtime
  alone — previously a config edit landing in the same timestamp tick as the
  previous write could be missed by the hot-reload watcher.

## [1.14.0]

### Added
- `ContrastAnalyzer` / `analyze_contrast`: antithesis (ṭibāq) detection
  with a 158-pair Arabic antonym lexicon; reports contrast pairs with
  conjunctive-prefix and definite-article normalization, a 10-word window
  for cross-sentence pairing, pair density, and a
  `contrastive / moderate / neutral` label (CLI: `contrast`).
- `FillerAnalyzer` / `analyze_fillers`: Arabic filler-phrase detector
  covering discourse fillers (في الحقيقة، بصراحة، بكل صراحة، بلا شك...)
  and defective immediate word repetitions, with density thresholds and a
  `filler_heavy / moderate / clean` label (CLI: `fillers`).
- `ComplexityAnalyzer` / `analyze_complexity`: morphological complexity
  profile via word-length distribution and fused-clitic length ratio, with
  a `complex / moderate / simple` label (CLI: `complexity`).

## [1.13.0]

### Added
- `QuotationAnalyzer` / `analyze_quotations`: quotation-environment
  analysis detecting paired Arabic quotation marks («» / "" / '...') and
  reporting verbs of direct speech, with per-text quotation ratio,
  per-category counts, positional spans, and a
  `quoted / partially_quoted / plain` label (CLI: `quotation`).
- `LoanwordAnalyzer` / `analyze_loanwords`: lexical-stratigraphy engine
  flagging transliterated loanwords against a 50+ entry colloquial/digital
  dictionary and detecting raw Latin-script fragments, reporting counts,
  ratios, a foreign-word density score and a
  `pure_arabic / mixed / loanword_heavy` label (CLI: `loans`).
- `RootDensityAnalyzer` / `analyze_root_density`: trilateral-root
  derivation profile counting unique roots, hapax-root ratio, top-root
  frequency, and a weighted diversity index with a
  `root_rich / moderate / sparse` label (CLI: `roots`).
- `AnalysisProfiler` expanded from 12 to 16 axes with four new
  cross-signal insights: `citation_heavy`, `loanwords_flagged`,
  `root_rich`, `person_named`.

## [1.12.0]

### Added
- `RhythmAnalyzer` / `analyze_rhythm`: Arabic prosody and rhythmic-cadence
  analysis combining saj' (rhymed-prose) detection, parallel sentence
  balance, whole-word repetition density, and verse-like poetic line
  ratio, blended into a normalized rhythm index (CLI: `rhythm`).
- `FigurateAnalyzer` / `analyze_figurative`: rhetorical-figure detection
  covering tashbīh (simile), ṭibāq (antithesis), tarāduf (synonymy) and
  takrīr (refrain) with per-occurrence offsets and a weighted figure
  index (CLI: `figurate`).
- `NumericAnalyzer` / `analyze_numeric`: extraction and classification of
  Western digits, Arabic-Indic digits (٠–٩), written number words
  (including compounds such as خمسُمائة), percentages and currencies, with
  mixed-digit-system flag and numeric density metrics (CLI: `numbers`).
- `dialect_depth` (utils): regional dialect weighting across Gulf,
  Levantine, Egyptian and Maghrebi marker families with density
  thresholds, dominant-region selection and per-region score traces.
- `TextQualityScore` gained a `rhetorical_richness` component (10%
  weight) feeding the CLI `quality` command.

## [1.11.0]

### Added
- `StyleAnalyzer` / `analyze_style`: Arabic register detection (formal /
  semi-formal / mixed / digital / informal) using formal-marker,
  colloquial-marker, and digital-signal analysis (CLI: `style`).
- `EmotionAnalyzer` / `analyze_emotions`: Plutchik-style emotion detection
  across eight buckets (joy, sadness, anger, fear, surprise, disgust,
  trust, hope) with dominance confidence and matched-word traces
  (CLI: `emotions`).
- `AnalysisProfiler` / `profile_text`: composite one-pass text profiling
  with an automated insight rule engine (CLI: `textprofile`).
- Spelling-confidence weighting in `TextQualityScore`: correction
  suggestions now penalize the spelling component proportionally to their
  confidence.

## [1.10.0]

### Added
- `WordFrequencyProfiler`: deep vocabulary profiling (corrected TTR,
  root TTR, lexical density, Zipf exponent diagnostics, ranked frequency
  table with first-occurrence positions) (CLI: `freqprofile`).
- `CoherenceAnalyzer` / `analyze_coherence`: deterministic weighted blend
  of lexical repetition, connective usage, sentence balance and topic
  consistency (CLI: `coherence`).
- `SpellingCorrection` now carries `suggestions` with confidence built
  from a fuzzy dictionary match.
- `TopicClassifier` lexicon extended to 13 domains (history, environment,
  culture, community added).
- `CorpusAnalyzer` gained `overlap_analysis`: full-pair Jaccard overlap
  matrix plus per-document distinctiveness scores.

## [1.9.0] — 2026-08-19

Major analytical and operational release.

### Added — Analyzers
- `EntityAnalyzer`: rule-based named-entity recognition for Arabic
  covering persons (honorific-title and name clusters), locations (with
  في/إلى/من prefix hints), organizations, monetary amounts, dates, and
  phone numbers — all with precise character offsets (`EntitySpan`).
- `TopicClassifier`: lexicon-driven topic classification across domains
  with evidence scores, normalized confidence, per-topic coverage, and
  batch helpers.
- `PronounAnalyzer`: decomposition of Arabic words into clitic segments
  (prefix / stem / suffix) identifying attached pronouns and their
  grammatical roles.
- `IdiomAnalyzer`: detection of 17+ fixed Arabic expressions with
  canonical forms, categories, and character offsets; results feed the
  spelling engine.
- `PipelineSnapshot`: versioned JSON persistence of a `PipelineConfig`
  with `diff()`, `save`/`load`, and the `snapshot_pipeline()` helper.

### Added — Operational infrastructure
- Versioned `PipelineSpec` contract for deterministic JSON serialization
  of declarative `PipelineConfig`, validated reconstruction, bounded
  metadata, and canonical configuration fingerprints; exposed via
  `to_spec()` / `from_spec()` and the `aranorm spec export|validate` CLI.
- `PipelineRuntime`: thread-safe pipeline snapshots, atomic configuration
  reload, generation tracking, and sanitized health/describe contracts.
- Standard-library HTTP server (`aranorm serve`) with threaded JSON
  endpoints for liveness, readiness, normalization, batch processing, and
  operational description; optional `ConfigReloadWatcher` for hot config
  reloads.
- Resumable streaming: versioned `StreamCheckpoint`, `StreamingSession`,
  and `StreamingSessionReport` for bounded file-to-file JSONL processing
  with atomic progress publication, source/pipeline fingerprint
  validation, cooperative cancellation, optional advisory locking, and
  CLI `stream run|resume|status`.
- `fingerprint_file()` with chunked SHA-256 calculation and defensive
  checkpoint/source size limits.
- Typed `StreamingSessionConflictError` and `StreamingSourceChangedError`
  for distinguishable operational recovery paths.

### Fixed
- `ProcessorFactory` no longer silently replaces an explicitly injected
  empty `ProcessorRegistry`.

## [1.8.0] — 2026-08-16

### Added
- Typed `BatchRetryPolicy` with defensive bounds and a documented retry
  contract for synchronous and asynchronous batch processing.
- `ArabicNormalizationPipeline.process_batch_retry_async()` with
  ordering, cancellation, and recovery parity with the synchronous API.
- CLI controls for `--emit-steps-trace`, `--retry`, `--max-retries`, and
  `--batch-size`, including machine-readable batch exports.

### Changed
- Batch exporters emit `steps_trace` as structured JSON.
- Retry failures preserve successful partial results through
  `BatchProcessingError.results`.

## [1.7.0] — 2026-08-16

### Added
- Opt-in operational tracing: `PipelineConfig(emit_steps_trace=True)`
  records ordered `(processor, action)` pairs in
  `NormalizationResult.steps_trace`.
- `ArabicNormalizationPipeline.process_batch_retry()` with a bounded
  single-threaded retry pass and a typed `BatchRetryReport` contract.
- `BatchProcessingError` now carries the successful `results` collected
  before failure, enabling downstream recovery without re-processing.
- Property-based (Hypothesis) test suite asserting invariants across
  idempotence, Arabic-character preservation, Latin pass-through, dialect
  robustness, and empty inputs.

## [1.6.0] — 2026-08-16

### Added
- Versioned JSON serialization and validation for
  `ProcessingMetricsSnapshot`, plugin discovery reports, and operational
  pipeline descriptions.
- Stable pipeline configuration fingerprints and `describe_operational()`
  introspection for automation, diagnostics, and cache-key inspection.
- Machine-readable CLI contracts for `version --json`, `describe`, and
  `plugins --json`.

### Changed
- `PipelineConfig` defensively copies `supported_dialects` during
  initialization so caller-owned lists cannot mutate an active
  configuration.

## [1.5.0] — 2026-08-16

### Added
- Cooperative, thread-safe `CancellationToken` with public
  `ProcessingCancelledError` for bounded sync, streaming, and async
  operations.
- Deterministic optional-dependency contract tests for pandas,
  HuggingFace Datasets, spaCy, and NLTK integrations.
- Expanded processor contracts for phrase and morphological stop-word
  normalization.

### Changed
- `process_batch_async()` mirrors synchronous batch semantics for bounded
  submission, stable ordering, fallback handling, progress callbacks, and
  failure policies.

## [1.4.0] — 2026-08-16

### Added
- Domain stop-words (`DomainStopProcessor`) for legal, medical, news, and
  religious corpora.
- Phrase stop-words (`PhraseStopProcessor`) for multi-word expressions.
- Context-aware stop-word removal preserving negation and emphasis.
- `AnalysisProfiler` v1 and batch analysis reports.

## [1.3.0] — 2026-08-16

### Added
- Dialect-aware stop-word lists for seven dialects (EGY, GLF, LEV, IRQ,
  NOR, TUN, YEM) with a high-performance Trie-backed registry.
- `StopWordsConfig` with modes (`remove` / `extract` / `highlight` /
  `count`) and scopes (`universal` / `msa_only` / `dialect_aware` /
  `custom`).
- Platform normalizers for Twitter/X, WhatsApp, and generic chat text.

## [1.2.0] — 2025-07-29

### Added
- `MorphologicalStopProcessor` with clitic and verb-form expansion.
- `PipelinesHooks` for before/after/error instrumentation.
- `ResourceLimits` defensive runtime limits (text length, batch size,
  workers, null-byte rejection).
- Batch processing policies (`fail_fast` / `collect` / `skip`) with
  `BatchProcessingError` aggregation.
- Progress callbacks and a streaming `process_iter()` generator with
  bounded memory.
- `NormalizationCache` — thread-safe LRU with single-flight deduplication.

## [1.1.0] — 2025-04-15

### Added
- `ArabicTextSummarizer` — TF-IDF extractive summarization.
- `SentimentAnalyzer` — lexicon-based sentiment scoring with intensity.
- `KeywordExtractor` — keyword extraction with n-gram support.
- `ArabicReadabilityAnalyzer` — readability score (0–100).
- `TextAnalyzer` — comprehensive text statistics and complexity metrics.
- `ArabicStemmer` — conservative light-stemmer (ISRI-inspired).
- `RootExtractor` — trilateral root extraction via morphological patterns.
- `LanguageDetector` — Arabic / Latin / Arabizi / mixed script detection.
- `ArabicTokenizer` — sentence and word tokenization with token metadata.

### Changed
- Pipeline split into `ContentCleaner` + `OrthographicNormalizer` +
  `DialectIdentifier` stages.
- `ProcessorRegistry` and `ProcessorFactory` made public API.

## [1.0.0] — 2025-01-10

### Added
- Initial production release.
- `ArabicNormalizationPipeline` with four presets (`light`, `standard`,
  `deep`, `social_media`).
- Core orthographic processors: alef, hamza, diacritics, tatweel,
  Unicode, digits, ligatures normalization.
- Content-cleaning processors: URLs, emails, mentions, hashtags, HTML,
  emojis, non-Arabic filtering.
- `ArabiziProcessor` — Arabizi-to-Arabic transliteration.
- `DialectIdentifier` — heuristic dialect detection for 8 dialects.
- `DialectNormalizer` — rule-based CODA and MSA normalization.
- MIT License.

[Unreleased]: https://github.com/Alqudimi/AraNorm/compare/v1.15.0...HEAD
[1.15.0]: https://github.com/Alqudimi/AraNorm/compare/v1.14.0...v1.15.0
[1.14.0]: https://github.com/Alqudimi/AraNorm/compare/v1.13.0...v1.14.0
[1.13.0]: https://github.com/Alqudimi/AraNorm/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/Alqudimi/AraNorm/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/Alqudimi/AraNorm/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/Alqudimi/AraNorm/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/Alqudimi/AraNorm/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/Alqudimi/AraNorm/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/Alqudimi/AraNorm/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/Alqudimi/AraNorm/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/Alqudimi/AraNorm/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/Alqudimi/AraNorm/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/Alqudimi/AraNorm/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Alqudimi/AraNorm/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Alqudimi/AraNorm/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Alqudimi/AraNorm/releases/tag/v1.0.0
