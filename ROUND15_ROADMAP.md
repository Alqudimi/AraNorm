# Round 15 — Roadmap: Server Hardening, Stages/Processors Closure & Feature Extensions

**Project:** AraNorm — Arabic text normalization platform
**Round:** 15 (موجـة 15 — تقوية الخادم وإغلاق الفجوات وتوسيع الميزات)
**Author:** Manus AI
**Date:** 2026-08-18

## 1. Motivation

Round 14 delivered four production features (fuzzy matcher, keyboard fixer, config merge, long-text processing) and raised statement coverage to **97.5%** (5711/5856) with **1150 tests** passing and `make verify` green. However, a measured residual of **~120 uncovered lines** remains concentrated in five areas that were deliberately deferred: the HTTP server (`server.py`, 15 uncovered lines), the pipeline stage adapters (`stages/*.py`), processor internals (`processors/*.py`), and scattered defensive arcs in `utils/*.py`. In addition, three functional capabilities remain partial: text statistics lacks readability analytics, the exporters module lacks JSON-Lines batch export, and the morphological/dialect stages lack graceful degradation modes. Round 15 closes all of these **without rewriting anything from scratch**, by appending targeted test suites and small, isolated feature extensions — consistent with the standing contract of clean code, enterprise discipline, and exhaustive verification.

## 2. Baseline (verified at round start)

| Metric | Value |
|---|---|
| Statement coverage | 97.5% (5711/5856) |
| Branch coverage | 93.0% (1624/1746) |
| Passing tests | 1150 (5 skipped) |
| `make verify` | Green (black / flake8 / mypy / pytest) |

## 3. Gap inventory (measured with `coverage report -m --branch`)

| Module | Branch | Missing arcs / lines |
|---|---|---|
| server.py | 88.6% | lines 46,47,50,86,87,89,93,149,151,198,279,307,312,366,380; 8 arcs |
| stages/normalizer.py | 68.8% | 10 arcs, lines 47, 61 |
| stages/morphological.py | 83.3% | arc 26→29, line 29 |
| stages/stop_words_stage.py | 83.3% | arc 57→62 |
| stages/dialect_norm.py | 95.0% | arc 184→186 |
| stages/cleaner.py | 95.0% | arc 47→49 |
| processors/normalization_processor.py | 62.5% | line 76; arcs 75→76, 118→120, 120→125 |
| processors/text_cleaning_processors.py | 50.0% | arcs 78→80, 80→82 |
| processors/number_words_processor.py | 95.5% | arc 234→239 |
| utils/stemmer.py | 90.0% | arcs 227→234, 238→241, 280→282 |
| utils/fuzzy_matcher.py | 90.0% | lines 76,78,174,248,301; 5 arcs |
| utils/language_detector.py | 86.7% | lines 170, 301–303 (documented dead code, untouched) |
| utils/root_extractor.py | 87.5% | arc 120→115 |
| utils/text_stats.py | 92.9% | arc 143→142 |
| utils/tokenizer.py | 96.4% | arc 190→198 |
| utils/keyboard_fixer.py | 95.5% | arc 165→162 |

## 4. Work plan

### P0 — Server hardening (`test_coverage_round15_p0_server.py`)
Full HTTP integration suite against `AraNormHTTPServer`: normalize endpoint happy path, unsupported media type, missing/invalid Content-Length, oversized body, JSON decode errors, streaming endpoint path resolution (inside/outside root), streaming conflicts (`StreamingSessionConflictError`, `StreamingSourceChangedError`), invalid text, generic request rejection, `create_server` validation (boolean max_body_bytes, bad streaming root), and `run_server` mutual-exclusion of config/spec paths. Expected: server.py → ≥98% branch.

### P1 — Stages & processors (`test_coverage_round15_p1_stages.py`, `test_coverage_round15_p1_processors.py`)
All-normalizer-flags-disabled config (exercises `stages/normalizer.py` empty-processor path), MorphologicalStage with a non-callable analyzer lacking `analyze()` (TypeError path), CleanerStage remove_english toggles, StopWordsStage plain `process()` alias with `context=None`, dialect-norm HF fallback path, NormalizationProcessor branch matrix, text_cleaning_processors mismatch branch, number_words fallback conversion.

### P1 — Utility residuals (`test_coverage_round15_p1_utils_residuals.py`)
stemmer defensive arcs, fuzzy_matcher residuals (score 0 filtering, empty index, root-None boosts, similarity tie-break), root_extractor/text_stats/tokenizer loop-back arcs, keyboard_fixer 165→162.

### F1 — Advanced text statistics (`aranorm.utils.text_stats.readability_index`)
Arabic readability index (word/sentence ratio, syllable approximation via diacritic + shadda presence) plus lexical diversity (type-token ratio with morphological normalization) and sentence-length distribution; small CLI `aranorm stats` extension.

### F2 — JSON-Lines batch export (`aranorm.utils.exporters.export_jsonl`)
Streaming-friendly NDJSON writer for corpora with optional progress; small CLI wiring.

### F3 — Morphological stage graceful degradation (`MorphologicalStage` config fallback mode)
When analyzer is unavailable, fall back to a stemmer-backed simple list instead of crashing; keeps TypeError path testable.

### F4 — Pipeline `analyze` convenience composition
`analyze(text)` classmethod composing stats + language detection + normalization in one result object (`AnalysisReport`).

## 5. Acceptance criteria

1. `make verify` green end-to-end (black, flake8, mypy, pytest, type checks).
2. Statement coverage ≥ 98.5% overall; branch coverage ≥ 95%; **server.py ≥ 98% branch**; all stages ≥ 98% branch.
3. ≥ 1250 passing tests (≈ +100 new tests across 4 new test files + feature tests).
4. Each new feature covered ≥ 95% branch by its own dedicated test file.
5. No regressions: all 1150 previous tests still pass.
6. Release report + enterprise archive (docs/evidence/source/*.tar.gz/SHA256SUMS) mirroring previous rounds' structure.

## 6. Out of scope (documented)

`utils/language_detector.py` lines 170/301–303 remain documented defensive dead code (mathematically unreachable input states per Round 14 analysis). Round 15 does not fabricate tests to hit them.
