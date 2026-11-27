# Round 14 — Roadmap: Coverage, Retry Robustness & CLI Contracts

**Author:** Manus AI · **Date:** 2026-08-18 · **Status:** Execution

## Context

Round 13 ended with 995 tests passing (5 optional skips), 96% line coverage over 5,574 measured lines, and all quality gates green. Round 14 keeps the same enterprise methodology: fix line basis, analyze gaps with evidence, execute in priority batches (P0/P1/P2), verify with the full gate suite, and deliver with a release report and a verifiable enterprise archive. Nothing is rewritten from scratch; production changes only follow proven test evidence.

## Gap analysis (evidence-based)

The full `make test-cov` report identifies `cli.py` (95 missing lines, 85%) and `core/pipeline.py` (49 missing lines, 90%) as the highest-value targets, followed by `server.py` (15 missing, 93%) and `language_detector.py` (6 missing, 94%). Remaining gaps are small defensive branches in utility modules (`metrics`, `cache`, `stemmer`, `tokenizer`, `corpus_analyzer`, `exporters`, `progress`, `summarizer`, `contracts`, `runtime`, `spec`). Each targeted line was individually inspected with `sed` before being added to the scope, so every test in this round closes a verified gap rather than a guess.

## Scope and acceptance criteria

| Batch | Targets | Acceptance |
|---|---|---|
| P0 — pipeline retry & async robustness | `pipeline.py` lines 544 (retry type validation), 685 (async bounds), 942 (max_retries bounds), 1161 (builder option rejection), 1092 (spec fingerprint mismatch), 1020/631 (cancellation in retry loops), 600 (no-result RuntimeError), 737/880 (fallback inner exceptions) | All targeted lines + branches green; no test touches unverified behavior; sync/async parity preserved |
| P1 — language detection & utilities | `language_detector.py` 170/287/298/301-303, `metrics.py`, `stemmer.py`, `tokenizer.py`, `cache.py`, `corpus_analyzer.py` | `language_detector.py` reaches 100%; utility modules each gain verified deterministic cases |
| P2 — CLI & server contracts | `cli.py` clusters 92-134 (I/O errors), 153-160 (retry return code 2), 520-622 (stdin/empty errors), 851/885/889 (serve streaming flags), 1270-1271 (help on no args); `server.py` edge cases; `summarizer.py` line 60 | Documented return codes and stderr messages asserted; `cli.py` coverage rises measurably; no reliance on installed CLI |

Hard gates: `make verify` must remain green; test count must increase (expected ~1,020+); overall coverage must not regress below 96%; no new `flake8`/`black`/`mypy` issues; benchmark must stay above 500 texts/s; `twine check` passes; archive must pass SHA-256 self-verification.

## Out of scope

Optional-dependency integrations (spaCy, NLTK, scikit-learn) remain skipped and documented, consistent with all previous rounds. Spec-driven pipeline features are tested only via already-contract-tested paths. No new features without test evidence; no architectural changes.

## Delivery

`ROUND14_RELEASE_REPORT.md`, `ROUND14_ROADMAP.md`, three test files (`test_coverage_round14_p0_pipeline.py`, `test_coverage_round14_p1_utils.py`, `test_coverage_round14_p2_cli.py`), updated `CHANGELOG.md`, distribution packages in `dist/`, and `archive/round14/round14-enterprise-archive.tar.gz` with SHA-256 self-verification (SHA256SUMS excludes itself).
