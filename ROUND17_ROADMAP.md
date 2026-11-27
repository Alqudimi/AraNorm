# ROUND 17 ROADMAP — Near-Perfect Coverage & Enterprise Analytics Suite

**Project:** AraNorm — Enterprise-Grade Arabic Text Normalization Engine
**Round:** 17 of ongoing enterprise development cycle
**Date:** 2026-08-19
**Author:** Manus AI

## 1. Round objectives

Round 16 concluded with 99% overall statement coverage and 97.42% branch coverage (1,734 of 1,780 branches), a hardened CLI at 95%, and two analytical features (`TextSimilarityMatrix`, `TextDiffReport`). Round 17 pursues two complementary goals in the manner of a large engineering organization: closing the last residual branch gaps to push branch coverage beyond 99% without rewriting any existing code, and shipping an enterprise-grade feature set that extends the engine's analytical and quality-assurance capabilities. All work follows the established conventions: append-only evolution of existing modules, tests in `tests/test_coverage_round17_*.py`, and a green `make verify` gate (Black, Flake8, Mypy) before archiving.

## 2. Phase-1 findings (gap analysis)

The full-suite branch measurement (`pytest --cov --cov-branch` per `pyproject.toml`) identifies 44 partial branches across 14 files, all of them small and well-understood. None of them is a structural defect; every gap corresponds to a real, testable code path that the Round 16 suites simply did not exercise. The table below summarizes the residual gaps by module.

| Module | Coverage | Missing/partial | Nature of gap |
|---|---|---|---|
| `cli.py` | 95% stmt / 13 partial | 92, 134, 156–160, 228→232, 269–271, 352, 357, 389, 408→410, 469→473, 610–613, 618–622, 694–698, 786–787, 851, 1270–1271 | File-not-found branches in normalize/tokenize/detect, retry-failure printing, dialect text output, plugin failure report, tqdm ImportError fallback, `--skip-errors`, stream cancellation report, unknown-command dispatch |
| `pipeline.py` | 98% stmt / 12 partial | 541→548, 644, 804, 809→816, 816→833, 1067, 1080, 1092, 1190, 1199→1214, 1216, 1365 | Stop-words metadata, `hooks.after_process`, collect-policy `RuntimeError`, async cancellation raises, `fail_fast` re-raise, async retry, `enable_option` TypeError |
| `normalizer.py` | 95% | lines 47, 61 | `TaaMarbutaProcessor`/`RepeatedPunctuationProcessor` branches under flag combinations |
| `language_detector.py` | 94% | 170, 301–303 | All-whitespace detection, Arabizi branch |
| `fuzzy_matcher.py` | 97% | 76, 78, 181→183 | Empty n-gram guards, stem/root index population |
| `streaming.py` | 99% | 322→exit | Fingerprint-mismatch `OSError` |
| `number_words_processor.py` | 99% | 234→239 | Compound و-prefixed suffix lookup |
| `text_analyzer.py`, `stemmer.py`, `root_extractor.py`, `text_stats.py`, `keyboard_fixer.py`, `dialect_norm.py` | 98–99% | one partial each | Loopback and device branches |

## 3. Work packages

### WP1 — Gap strengthening (priority: highest)

A single focused test suite `tests/test_coverage_round17_gaps.py` exercises every residual path with genuine inputs. Notable techniques: constructing an Arabizi-dominant Latin input for the 301–303 branch; an all-whitespace input for line 170; feeding plugin-discovery failures by injecting a broken plugin entry into `ProcessorRegistry` for the 469→473 branch; triggering `hooks.after_process` via the public `hooks` API; exercising the collect-policy `RuntimeError` branch by making a stage processor return `None`; driving the async cancellation raises via `process_batch_async` with a `CancellationToken` that is cancelled mid-flight; and the `enable_option` TypeError via `PipelineConfig.enable_option` with a non-boolean target. Expected outcome: branch coverage ≥ 99.5%.

### WP2 — New features (three features, enterprise grade)

The feature selection balances analytical depth (consistent with Round 16's `TextSimilarityMatrix`/`TextDiffReport`) and quality assurance (spelling tooling already sketched in `SpellingProcessor`).

**F1 — `SpellingReport` / `process_with_spelling(text)`** (new module `src/aranorm/analysis/spelling_report.py`): an analytical report that applies `SpellingProcessor` and, for each correction, records position, original token, corrected token, and correction category (alef, hamza, waw-hamza, definite article, ta-marbuta, common misspelling). Returns per-text statistics (correction count, categories, ratio). Wired into `pipeline.process_with_spelling(text)` mirroring the Round 16 `process_with_diff` contract.

**F2 — `TextQualityScore`** (extends `src/aranorm/analysis/`): a composite quality assessment combining normalized-vs-original edit distance, diacritics density, repetition ratio, and spelling-correction density into a 0–100 score with per-factor breakdown and label (excellent/good/fair/poor). Reuses existing `normalizer_utils` primitives — no new external dependencies.

**F3 — `BatchReport` enrichment — `pipeline.process_batch_with_report(values)`** (in `core/pipeline.py`): returns a `BatchAnalysisReport` with aggregate statistics (success ratio, average processing time, longest/shortest inputs, top corrections when spelling stage enabled), mirroring the Round 15 `AnalysisReport` pattern. Small and natural given existing batch machinery.

### WP3 — Engineering hardening

Documentation additions in `API_REFERENCE.md` and `CHANGELOG.md` for the three new features; typing refinements where WP2 touches untyped helpers; regression tests covering the new public APIs end-to-end through the pipeline (≥ 60 new tests); final `make verify` sweep; Round 17 release report and enterprise archive.

## 4. Success criteria

Branch coverage ≥ 99.5%; overall statement coverage ≥ 99%; test count ≥ 1,540 with zero failures; `make verify` clean (Black, Flake8, Mypy); all three new features covered ≥ 95% branch with genuine behavior assertions (no dead-code tests); archive `archive/round17.tar.gz` with SHA256 checksums; `CHANGELOG.md` and `ROUND17_RELEASE_REPORT.md` delivered.
