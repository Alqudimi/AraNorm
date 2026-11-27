# Changelog

All notable changes to AraNorm will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.15.0] — Round 24: Rhetorical & Cohesion Expansion

### Added
- `RhetoricalQuestionAnalyzer` / `analyze_rquestions`: Arabic interrogative
  detection covering inversion particles (أليس، ألم، ألا، أما، أليسوا),
  two-word inversion heads (ألم يكن), attached-hamza proclitics (أَ + verb),
  neutral-particle direct questions (هل + ؟), discourse-question markers
  (بأي، لماذا، كيف تظن، من ذا), and bare question sentences (inversion or
  terminal ؟). Reports per-question spans with types, inversion/direct/
  marker counts, question density per 100 words, and an
  `interrogative-rich / moderate / plain` label (CLI: `rquestions`).
- `AnaphoraAnalyzer` / `analyze_anaphora`: cross-sentence cohesion engine
  tracking attached clitic pronouns (ـه، ـها، ـهم، نا...), independent
  pronouns (هو، هي، نحن...), demonstratives (هذا، تلك، أولئك), relative
  links (الذي، التي، الذين), and lexical re-mentions across sentence
  windows. Reports a variety-weighted cohesion score (0–1), reference
  density, mention spans, and a `tightly-cohesive / moderate / loose`
  label, with verbal-pattern ي exclusions to avoid false clitic hits on
  forms like يمشي/يرمي/يبني (CLI: `anaphora`).
- `WordPlayAnalyzer` / `analyze_wordplay`: Arabic wordplay detection
  built on consonant-skeleton phonetic similarity: jinās tām (exact
  skeleton match) and jinās nāqiṣ (similarity ≥ 0.8), saj' via
  sentence-final rhyme runs (suffix-rhyme on the last skeleton letters),
  and pun words flanked by two distinct near-skeleton neighbours. Reports
  typed mention spans, tām/nāqiṣ pair lists, saj line counts, pun words,
  wordplay density per 100 words, and a `playful / moderate / literal`
  label (CLI: `wordplay`).
- `NumericAnalyzer` now classifies written ordinals (الأول، الثانية،
  العشرين...) as a new `ordinal` span category with `ordinal_count` in
  the result payload.
- `QualityScoreAnalyzer` gained an eighth component `rhetorical_depth`
  (weight 0.03) blending rhetorical-questioning intensity with
  cross-sentence cohesion; remaining component weights rebalanced so the
  composite still sums to 1.00.

### Changed
- `AnalysisProfiler` now ships **22 axes** (was 19) adding `rquestions`,
  `anaphora` and `wordplay`, plus cross-signal insights:
  `interrogative_rich`, `tightly_cohesive`/`loose_cohesion`, and
  `wordplay_present`.
- Version bumped to 1.15.0; existing tests migrated to the 22-axis /
  8-component architecture; `make verify` (Black, Flake8, Mypy) clean.

## [1.14.0] — Round 23: Contrast, Filler & Complexity Expansion

### Added
- `ContrastAnalyzer` / `analyze_contrast`: antithesis (tibaq-mazji) detection
  engine with a 158-pair Arabic antonym lexicon; reports contrast pairs with
  conjunctive-prefix and definite-article normalisation, a 10-word window for
  cross-sentence pairing, pair density, and a
  `contrastive / moderate / neutral` label (CLI: `contrast`).
- `FillerAnalyzer` / `analyze_fillers`: Arabic filler-phrase detector covering
  discourse fillers (في الحقيقة، بصراحة، بكل صراحة، بكل تأكيد، بلا شك، لا شك
  أن، مثلا، يعني، من ناحية، من جهة أخرى...) plus verbatim word-repetition
  detection, reporting filler spans, repetition spans, both densities, and a
  `filler_heavy / moderate / clean` label (CLI: `fillers`).
- `ComplexityAnalyzer` / `analyze_complexity`: morphological complexity profiler
  computing average/max word length over diacritic-stripped letters, fused-word
  ratio (attached pronouns/clitics), the share of long words, and a length
  distribution histogram; reports a `complex / moderate / simple` label
  (CLI: `complexity`).
- `NumericAnalyzer` extended with a `time_expression` category: clock times
  (الساعة ٥:٣٠), named hours (الساعة العاشرة مساءً), past/future period shifts
  (أسبوعاً الماضي، الشهر القادم) and anchored periods of day (صباح اليوم، عشية).
- `QualityScoreAnalyzer` extended with a seventh component,
  `structural_balance` (parallel sentence balance via the rhythm engine,
  average clause length dispersion), with weights redistributed to sum to
  1.00: spelling 0.27, consistency 0.23, lexical_balance 0.20, readability
  0.10, diacritics 0.05, rhetorical_richness 0.08, structural_balance 0.07.
- `AnalysisProfiler` expanded from 16 to **19 axes** (`contrast`, `fillers`,
  `complexity`) with three new cross-signal insights:
  `contrastive_style`, `filler_heavy`, `complex_hard_to_read`.

### Changed
- Version bumped to 1.14.0; existing tests migrated to the 19-axis /
  7-component architecture; total branch coverage at 98% (>=95% target).

## [1.13.0] — Round 22: Discourse & Lexical Stratigraphy

### Added
- `QuotationAnalyzer` / `analyze_quotations`: quotation-environment analysis that
  detects paired quotation marks in Arabic typography (`«»` / `""` / `'...'`) as well
  as reporting verbs of direct speech, reporting a per-text quotation ratio,
  per-category counts, positional spans, and a `quoted / partially_quoted / plain`
  label (CLI: `quotation`).
- `LoanwordAnalyzer` / `analyze_loanwords`: lexical-stratigraphy engine that flags
  transliterated loanwords (with conjunctive-prefix normalisation) against a
  50+ entry colloquial/digital dictionary, detects raw Latin-script fragments,
  and reports loanword counts, Latin ratios, a foreign-word density score and a
  `pure_arabic / loanwords / mixed` label with positional spans and samples
  (CLI: `loans`).
- `RootDensityAnalyzer` / `analyze_root_density`: trilateral-root derivation
  profile that strips the definite article before root extraction, counts unique
  roots, derives hapax-root ratio, top-root frequency, and a weighted
  diversity index with a `root_rich / moderate / sparse` label (CLI: `roots`).
- `AnalysisProfiler` expanded from 12 to 16 axes with four new cross-signal
  insights: `citation_heavy`, `loanwords_flagged`, `root_rich`, and `person_named`.
- Three new CLI commands: `quotation`, `loans`, `roots` (JSON output supported).

### Changed
- Version bumped to 1.13.0.

---

## [1.12.0] — Round 21: Advanced Linguistic & Structural Analysis

### Added
- `RhythmAnalyzer` / `analyze_rhythm`: Arabic prosody and rhythmic-cadence analysis
  combining four deterministic indicators — saj' (سجع / rhymed-prose) detection via
  balanced clause pairs and trailing-stem overlap (with conjunctive-prefix and
  clitic-suffix normalisation), parallel sentence balance, whole-word repetition
  density (stop words excluded), and verse-like poetic line ratio — blended into a
  normalised rhythm index with ``rhythmic`` / ``semi_rhythmic`` / ``flat`` labels.
- `FigurateAnalyzer` / `analyze_figurative`: rhetorical-figure detection covering
  tashbih (تشبيه / simile via كما، مثل، كأن bridges), tibaq (طباق / antithesis),
  taraduf (ترادف / synonymy) and takrir (تكرير / refrain with character spans), with
  per-occurrence offsets and a weighted figure index (``rich`` / ``moderate`` /
  ``plain``).
- `NumericAnalyzer` / `analyze_numeric`: extraction and classification of Western
  digits, Arabic-Indic digits (٠–٩), written number words (including compounds such
  as خمسُمائة), percentages (٪/%) and currencies, with mixed-digit-system flag and
  numeric density metrics.
- `dialect_depth` (utils): regional dialect weighting across Gulf, Levantine,
  Egyptian and Maghrebi marker families with density thresholds, dominant-region
  selection and per-region score traces.
- `AnalysisProfiler` expanded to 12 axes (adds rhythm, figurate, numeric, dialect)
  with four new insight rules: formal-rhythmic, rhetorically-rich,
  mixed-digit-systems, dialectal-regional.
- `TextQualityScore` gained a ``rhetorical_richness`` component (10% weight) with a
  rebalanced weight table; the six-component model now feeds the CLI `quality`
  command.
- Three new CLI commands: `rhythm`, `figurate`, `numbers` (36 commands total).

### Changed
- Version bumped to 1.12.0.

---

## [1.11.0] — Round 20: Enterprise Linguistic Profiling Expansion

### Added
- `StyleAnalyzer` / `analyze_style`: Arabic register detection (formal / semi-formal /
  mixed / digital / informal) using formal marker, colloquial marker, and digital signal
  analysis (emoji, character elongation, chat slang) with a normalized style index.
- `EmotionAnalyzer` / `analyze_emotions`: Plutchik-style emotion detection across eight
  buckets (joy, sadness, anger, fear, surprise, disgust, trust, hope) with normalized
  token matching, dominance confidence, and matched-word traces.
- `AnalysisProfiler` / `profile_text`: composite one-pass text profiling combining
  sentiment, coherence, quality, readability, style, emotion, word-frequency and topic
  axes, with an automated insight rule engine (coherent-negative,
  positive-fragmented, high-quality-positive, negative-emotion).
- Spelling-confidence weighting in `TextQualityScore`: correction suggestions now
  penalize the spelling component proportionally to their confidence.
- Three new CLI commands: `style`, `emotions`, `textprofile` (33 commands total).

### Changed
- Version bumped to 1.11.0.

---
---

## [Unreleased]

### Round 19 — Vocabulary Analytics, Coherence & Expansion of Existing Engines

- Added `WordFrequencyProfiler`: deep vocabulary profiling (guiraud corrected TTR, Herdan-C root TTR, open-class lexical density, Zipf exponent diagnostics, ranked frequency table with first-occurrence positions). New CLI sub-command: `freqprofile`.
- Added deterministic `analyze_coherence` / `CoherenceAnalyzer`: weighted blend of lexical repetition, connective usage, sentence balance and topic consistency. New CLI sub-command: `coherence`.
- `SpellingCorrection` now carries `suggestions` with confidence built from a fuzzy dictionary match.
- `TopicClassifier` lexicon extended to 13 fields (history, environment, culture, community).
- `CorpusAnalyzer` gained `overlap_analysis`: full-pair Jaccard overlap matrix plus per-document distinctiveness scores.
- Version bump to 1.10.0; `make verify` (Black, Flake8, Mypy) clean.

### Round 16 — Full-Spectrum Hardening & Analytical Expansion

- Shipped two new analytical features: `TextSimilarityMatrix` (pairwise n-gram Jaccard similarity over a corpus, with canonicalization, top-k neighbor retrieval, threshold filtering, and corpus diagnostics) and `TextDiffReport` with `ArabicNormalizationPipeline.process_with_diff` (word-level insertions, deletions, unchanged counts, and change positions via a `ProcessWithDiff` adapter).
- Hardened the CLI (`cli.py`) to 95% branch coverage with a dedicated P0 suite covering all commands, stdin/fallback paths, `--stream` bulk processing, format exports (CSV/JSON/JSONL), output-file and unwriteable-path error paths, `serve` without the server module, and the `__main__` entry point.
- Added a fake-import harness for the optional-dependency layer: lazy adapters for HuggingFace (`HuggingFaceNormalizer`, `Dataset` + `DatasetDict`), NLTK, spaCy, scikit-learn, and Pandas now reach 98–100% branch coverage, alongside fake `transformers` tests for `TransformersSeq2SeqModel` and the `CODA`/`MSA`/`DialectIdentifier` model wrappers (99% for `models/`).
- Closed residual core gaps across `config.merge` (preset/dialect/stop-word/resource-limit branches), `PipelineSpec` metadata validation, `ResourceLimits`, `runtime._safe_error`, `BatchExporter`, `TqdmProgressCallback`, `OrthographicNormalizer` disabled flags, `language_detector` fallbacks, and the async batch retry/cancellation loop in `pipeline.py`.
- Removed a dead unreachable branch in `PipelineSpec` that could never be reached after earlier validation guarantees.
- Raised full-project branch coverage to 99% (from the Round 15 baseline of 95.08%); 1478 tests pass with `make verify` clean (Black, Flake8, Mypy) and 6 environment-dependent tests skipped.
- Hardened the integration test session: an isolated-module fixture plus per-file cleanup guarantees fake `sys.modules` entries (`nltk`, `spacy`, `pandas`, `datasets`, `transformers`, `camel_tools`) never pollute sibling tests.

### Round 13 — Coverage, Contracts & Analytical Reliability

- Added 29 deterministic contract and boundary tests for processors, dialect identification, configuration, stop-word registry, readability, keyword extraction, text analysis, comparison, sentiment, and summarization.
- Raised full-project coverage to 96%; reached 100% in the targeted configuration, registry, sentiment, comparison, text-analysis, readability, and keyword-extraction units.
- Fixed `PipelineConfig.from_file` so unsupported extensions raise `ValueError` before filesystem access, while supported missing files retain `FileNotFoundError` semantics.
- Passed `make verify`, Black, Flake8, Mypy, benchmark, security audit, package build, and Twine metadata validation.

### Fixed
- `ProcessorFactory` no longer silently replaces an explicitly injected empty `ProcessorRegistry`: the implicit falsy guard was replaced with an explicit `is None` check so callers can inject an intentionally empty registry.

### Added
- Versioned `PipelineSpec` contract for deterministic JSON serialization of declarative `PipelineConfig`, validated reconstruction, bounded metadata, and canonical configuration fingerprints.
- `ArabicNormalizationPipeline.to_spec()` / `from_spec()` and `PipelineRuntime.reload_from_spec()` / `reload_from_spec_file()` for atomic spec-based deployment and rollback-safe reloads.
- `aranorm spec export` and `aranorm spec validate` commands with deterministic JSON output and safe file handling.
- Optional `PipelineRuntime` for thread-safe pipeline snapshots, atomic configuration reload, generation tracking, and sanitized health/describe contracts.
- Standard-library `aranorm.server` adapter with threaded JSON endpoints for liveness, readiness, normalization, batch processing, and operational description.
- Optional `ConfigReloadWatcher` for debounced-by-mtime JSON/YAML reloads that preserve the last valid snapshot after failures.
- Installed-style processor plugin contract tests built from temporary `dist-info/entry_points.txt`, covering successful loading, invalid processors, and strict discovery.
- Round 8 contract suites covering runtime snapshots, reload rollback, HTTP validation, body limits, watcher behavior, CLI `serve`, and installed-artifact runtime exports.
- Versioned `StreamCheckpoint`, `StreamingSession`, and `StreamingSessionReport` contracts for bounded UTF-8 file processing, atomic progress publication, source/pipeline fingerprint validation, safe output truncation, and cooperative cancellation.
- `fingerprint_file()` with chunked SHA-256 calculation and defensive checkpoint/source size limits.
- CLI `stream run`, `stream resume`, and `stream status` commands with human-readable and machine-readable JSON output.
- Optional `/v1/stream` HTTP endpoint, disabled by default, for administrator-controlled local file sessions.
- Round 10 contract suites covering checkpoint round trips, real resume behavior, source changes, cancellation, CLI end-to-end flows, and HTTP opt-in validation.
- Typed `StreamingSessionConflictError` and `StreamingSourceChangedError` contracts for distinguishable operational recovery paths.
- Optional local advisory session locking with the documented `.lock` suffix and non-blocking conflict detection.
- Defensive artifact-path validation rejecting identical source/output/checkpoint paths and existing-file aliases, including symlink aliases.

### Changed
- The CLI now exposes `aranorm spec` export/validate workflows and accepts `--spec` for `serve`, while preserving existing command contracts and mutual exclusion with legacy config loading.
- The CLI now exposes `aranorm serve` without changing existing command contracts; the listener remains opt-in and is never started during import.
- Makefile now provides explicit `server-contracts`, `plugin-contracts`, and `installed-smoke` quality targets.
- CI now includes a Python 3.12 packaging job that builds wheel/sdist, runs `twine check`, and executes installed smoke contracts.
- API, architecture, README, and installation documentation now describe the runtime/service boundary and its reverse-proxy security limitations.
- API, architecture, README, and configuration documentation now describe the resumable streaming boundary, checkpoint invariants, CLI contracts, and the local-filesystem security boundary of `/v1/stream`.
- Makefile and CI expose a dedicated `streaming-contracts` gate in addition to the existing verification targets.
- `StreamingSession` now performs lightweight source-mutation checks at safe batch boundaries while preserving the last atomic checkpoint as the recovery point.
- `/v1/stream` now supports an optional `streaming_root` confinement policy, rejects traversal and symlink escapes, forces local session locking, and maps conflicts/source changes to bounded HTTP `409` responses.
- CLI streaming exposes `--lock`; server CLI exposes `--streaming-root` with explicit opt-in validation.
- README, API reference, architecture, and configuration documentation now describe the round 11 concurrency and filesystem-safety boundaries.

### Quality
- Round 12 closed all remaining line and branch gaps in `core/base.py`, `core/registry.py`, and the stop-words, phrase-stop, platform, and internet-stop processors to 100%; overall coverage rose to 95% across 5,574 measured lines with 966 tests passing. See `ROUND12_RELEASE_REPORT.md`.
- Round 9 targeted contracts: 65 passed across PipelineSpec, CLI, runtime, HTTP, and compatibility suites; full release verification remains a required gate before versioning.
- Round 10 targeted contracts include streaming, CLI, and HTTP opt-in suites; final counts and coverage are recorded in `ROUND10_RELEASE_REPORT.md` after the complete verification gate.
- `make verify`: 799 passed, 5 documented optional/dependency-related skips; Black, flake8, and mypy clean.
- Coverage: 94% across 4,899 measured package-source lines; `runtime.py` is 99% and `server.py` is 97% covered.
- `make server-contracts`, `make plugin-contracts`, and `make installed-smoke` pass independently.
- Round 8 performance and regex-security audits are stored in `performance_round8.json` and `security_round8.json`.
- Round 11 targeted contracts cover lock behavior, alias rejection, source mutation, streaming-root confinement, CLI compatibility, and typed HTTP error mapping.

### Planned
- Arabic spell-checker integration.

---

## [1.9.0] - 2026-08-19

### Added
- `EntityAnalyzer` in `aranorm.analysis`: rule-based named-entity recognition for Arabic covering six entity types — persons (including honorific-title clusters and name clusters), locations (with `في/إلى/من` prefix hints), organizations, monetary amounts, dates, and phone numbers — all with precise character offsets (`EntitySpan`) and per-type aggregation (`EntityAnalysisResult`).
- `TopicClassifier` in `aranorm.analysis`: lexicon-driven topic classification across ten domains (legal, medical, sports, religious, educational, economic, technical, media, travel, food) with raw evidence scores, normalised top-2-gap confidence, per-topic coverage, and batch `classify_batch` / `distribution` helpers.
- `PronounAnalyzer` in `aranorm.analysis`: decomposition of Arabic words into clitic segments (prefix / stem / suffix), identifying attached pronouns (`هم،ها،ي،ك،ني...`) and their grammatical roles, with aggregate `pronoun_statistics` over a corpus.
- `IdiomAnalyzer` in `aranorm.analysis`: detection of 17+ fixed Arabic expressions (`إن شاء الله`, `ما شاء الله`, `في الحال`, `على أي حال`, ...) with canonical forms, categories, and character offsets; results feed the spelling engine.
- Spelling-report idiom exclusion: `SpellingAnalyzer` now recognises idiom words and never flags them as spelling issues (e.g. `ان` inside `ان شاء الله` is no longer an error).
- `PipelineSnapshot` in `aranorm.core.snapshot`: versioned JSON persistence of a `PipelineConfig` with schema version, stage order, and free-form metadata, plus `diff()`, `save`/`load`, and the `snapshot_pipeline()` helper.
- Five new CLI commands: `aranorm entities`, `aranorm topics`, `aranorm pronouns`, `aranorm idioms`, and `aranorm snapshot save|restore`, all supporting text arguments, `--file`, and `--json` output.

### Quality
- `make verify` clean (Black, Flake8, Mypy over 102 source files); 1649 baseline tests passing; new feature suites included (see `ROUND18_RELEASE_REPORT.md`).

---

## [1.8.0] - 2026-08-16

### Added
- Typed `BatchRetryPolicy` with defensive bounds, stable serialization, deserialization validation, and a documented retry contract for synchronous and asynchronous batch processing.
- `ArabicNormalizationPipeline.process_batch_retry_async()` with ordering, cancellation, catastrophic-failure, and recovery parity with the synchronous API.
- CLI controls for `--emit-steps-trace`, `--retry`, `--max-retries`, and `--batch-size`, including machine-readable batch exports and structured trace output.
- Focused contract, property-based, coverage-gap, and CLI end-to-end tests for retry policy, trace opt-in, exporter schemas, and installed behavior.

### Changed
- Batch exporters now emit `steps_trace` as structured JSON rather than an ambiguous string representation.
- Retry failures preserve successful partial results through `BatchProcessingError.results`, while catastrophic causes remain observable in `BatchRetryReport`.
- Public API and configuration documentation now cover retry policy, async retry, trace emission, and the new CLI flags.

### Quality
- `make verify`: 752 passed, 5 documented optional/dependency-related skips; Black, flake8, and mypy clean.
- Coverage: 94% across 4,599 package-source lines.
- Round 7 performance and security audits completed; results are stored in `performance_round7.json` and `security_round7.json`.
- Release artifacts are validated with `twine check`, installed smoke tests, and multi-version `compileall` checks.

---

## [1.7.0] - 2026-08-16

### Added
- Opt-in operational tracing: ``PipelineConfig(emit_steps_trace=True)`` records ordered ``(processor, action)`` pairs in ``NormalizationResult.steps_trace`` with a defensive default of ``None`` that leaves equality, serialization, and CSV exports untouched.
- ``ArabicNormalizationPipeline.process_batch_retry()`` with a bounded single-threaded retry pass, a typed ``BatchRetryReport`` contract, catastrophic-failure reporting, and integration with ``BatchProcessingError.results``.
- ``BatchProcessingError`` now carries the successful ``results`` collected before failure, enabling downstream recovery without re-processing.
- Property-based (hypothesis) test suite asserting invariants across idempotence, Arabic-character preservation, Latin pass-through, dialect robustness, and empty inputs.
- Coverage-gap suites for domain stop-words, text chunking, cache boundaries, and CLI end-to-end contracts.

### Changed
- Sync batch failure paths now build the successful-results list incrementally so ``BatchProcessingError.results`` is always populated in collect mode.
- Catastrophic batch retries expose a ``catastrophic_cause`` class name in the retry summary instead of failing silently.

### Quality
- `make verify`: 731 passed, 5 documented optional/dependency-related skips; `mypy` clean across 86 source files.
- Coverage: 93% across the package source tree.
- Round 6 performance and security audits completed; results are stored in `performance_round6.json` and `security_round6.json`.

---

## [1.6.0] - 2026-08-16

### Added
- Versioned JSON serialization and validation for `ProcessingMetricsSnapshot`, plugin discovery reports, and operational pipeline descriptions.
- Stable pipeline configuration fingerprints and `describe_operational()` introspection for automation, diagnostics, and cache-key inspection.
- Machine-readable CLI contracts for `version --json`, `describe`, and `plugins --json`, including strict plugin-discovery diagnostics.
- Integration, serialization, security, and installed-artifact smoke suites covering optional dependency absence, hostile inputs, resource limits, wheel, and sdist behavior.

### Changed
- `PipelineConfig` now defensively copies `supported_dialects` during initialization so caller-owned lists cannot mutate an active configuration.
- Packaging metadata now uses a backend-compatible PEP 621 license-file declaration, preserving the MIT license while enabling reproducible wheel and sdist builds.

### Quality
- `make verify`: 660 passed, 5 documented optional/dependency-related skips.
- Wheel and sdist installed smoke validation passed outside the source tree.
- Round 5 performance and regex security audits completed; results are stored in `performance_round5.json` and `security_round5.json`.

---

## [1.5.0] - 2026-08-16

### Added
- Cooperative, thread-safe `CancellationToken` with public `ProcessingCancelledError` for bounded sync, streaming, and async operations.
- Deterministic optional-dependency contract tests for pandas, HuggingFace Datasets, spaCy, and NLTK integrations.
- Expanded processor contracts for phrase and morphological stop-word normalization, including common conjunction clitics.

### Changed
- `process_batch_async()` now mirrors synchronous batch semantics for bounded submission, stable ordering, fallback handling, progress callbacks, and failure policies while preserving the v1.4.0 positional `policy` argument.
- `PipelineBuilder` now resolves documented aliases, rejects unknown or invalid options atomically, and preserves the existing fluent API.
- Stop-word processors isolate injected registries and validate modes early, improving reuse and preventing cross-instance state leakage.
- Public API reference and README now document operational contracts, resource limits, cancellation boundaries, and async behavior.

### Fixed
- Prevented partial builder mutation when a later option is invalid.
- Added cooperative cancellation checks before callbacks, between items, and at bounded batch boundaries without forcefully interrupting active worker threads.

### Quality
- `pytest`: 595 passed, 2 optional integrations skipped.
- Coverage: 91% across the package source tree.
- `black`, `flake8`, and `mypy`: passed; mypy reports no issues across 86 source files.
- Compile compatibility checks passed on Python 3.9, 3.10, 3.11, and 3.12.
- Performance audit: approximately 473x sequential cache speedup on repeated inputs, one underlying single-flight call from 16 concurrent callers, and 10,000 streaming items with approximately 6 KB peak traced allocations.
- Regex security audit remained sub-millisecond at 20,000-character adversarial inputs for the tested patterns.

---

## [1.4.0] - 2026-08-16

### Added
- Typed architectural contracts for progress callbacks, pipeline hooks, error handling, and batch-processing policies (`fail_fast`, `collect`, and `skip`).
- Thread-safe `ProcessingMetrics` snapshots and registry plugin discovery through Python entry points.
- `ResourceLimits` configuration with bounded text length, batch size, worker count, and optional null-byte rejection.
- Security, compatibility, concurrency, exporter, language-detector, dialect-normalizer, and CLI contract test suites.
- Repeatable security and performance audit scripts for regex behavior, cache single-flight, streaming throughput, and bounded allocations.

### Changed
- `NormalizationResult`, `BatchProcessingError`, and configuration contracts now use defensive copies and strict round-trip serialization.
- `NormalizationCache` uses Future-based single-flight coordination to prevent duplicate concurrent work.
- Pipeline batch and streaming paths enforce resource limits before processing starts.
- HTML tag matching is constrained to avoid quadratic scanning on adversarial input containing repeated `<` characters.
- CI now validates the declared Python 3.9 minimum in addition to Python 3.10–3.13.

### Fixed
- Corrected Arabic language-detector scoring for punctuation-only input, Latin-only text, Arabizi indicators, and mixed-script threshold precedence.
- Corrected null-byte validation to inspect the actual Unicode NUL character.
- Preserved Python 3.9–3.11 compatibility by removing Python 3.12-only multiline f-string expression syntax.

### Quality
- `pytest`: 554 passed, 2 optional integrations skipped.
- Coverage: 89% across the package source tree.
- `flake8`: passed.
- `mypy`: passed with no issues across 86 source files.
- Compatibility smoke suites: 92 passed on each of Python 3.9, 3.10, and 3.11; full suite passed on Python 3.12.
- Performance audit: 999 cache hits after one miss for 1,000 repeated inputs; single-flight reduced concurrent underlying calls from 16 to 1; streaming processed 10,000 items with approximately 6 KB peak traced allocations.

---

## [1.3.0] - 2026-08-16

### Added
- `ArabicNormalizationPipeline.process_iter()` لمعالجة iterable على دفعات bounded مع الحفاظ على ترتيب النتائج ودعم التوازي.
- `StreamingBatchExporter` لتصدير النتائج تدريجيًا إلى CSV وJSON وJSONL عبر مسارات أو file-like objects.
- أوضاع CLI جديدة في `aranorm batch`: `--stream` و`--batch-size` و`--skip-errors`.
- `NormalizationCache.process_iter()` ومعامل `batch_size` في `process_batch()` للمعالجة المتدفقة مع إعادة استخدام النتائج المخزنة.
- اختبارات CLI وstreaming والكاش، ليصل خط الاختبارات إلى 440 اختبارًا ناجحًا.

### Changed
- أصبح مسار batch المتدفق لا يحمل الملف كاملًا في الذاكرة، ويحسب الأسطر غير الفارغة للتحقق من الإدخال وتغذية progress.
- عززت واجهة الكاش سلامة الاستعلامات المتزامنة في `__len__` و`__contains__`، مع تحقق مبكر من حدود `batch_size` و`n_workers`.
- حدّثت README ووثائق الاستخدام لتشمل streaming والكاش المتدفق وأمثلة CLI.

### Quality
- `pytest`: 440 passed, 1 optional integration skipped.
- `flake8`: ناجح.
- `mypy`: ناجح بلا أخطاء على 84 ملف مصدر.

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

[Unreleased]: https://github.com/Alqudimi/AraNorm/compare/v1.8.0...HEAD
[1.8.0]: https://github.com/Alqudimi/AraNorm/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/Alqudimi/AraNorm/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/Alqudimi/AraNorm/compare/v1.5.0...v1.6.0
[1.4.0]: https://github.com/Alqudimi/AraNorm/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/Alqudimi/AraNorm/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Alqudimi/AraNorm/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Alqudimi/AraNorm/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Alqudimi/AraNorm/releases/tag/v1.0.0
