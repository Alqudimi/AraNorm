# ROUND 17 GAP ANALYSIS — 2026-08-19

## Base state after Round 16 (COMPLETE)
- make verify green: 1478 passed / 6 skipped / 0 failed; black/flake8/mypy clean.
- Overall branch coverage: 97.42% (1734/1780 branches), 99% stmt (6032 stmts, 41 missing).
- Archive at archive/round16/.
- Round 16 features: TextSimilarityMatrix, TextDiffReport + pipeline.process_with_diff().

## Measurement notes
- Correct measurement: `python3 -m pytest tests --cov=src/aranorm --cov-report=term-missing --cov-branch`
  (pyproject.toml: source=src/aranorm, omit models/integrations).
- `coverage run --rcfile=/dev/null` gives WRONG numbers (71% cli) — do NOT use rcfile=/dev/null.

## Residual branch gaps (pytest-cov, branch=True) — 44 partial branches total:

### cli.py 95% (13 partial, 25 missing stmts)
- 92, 352, 389: file-read branches in normalize/tokenize/detect handlers → tests pass nonexistent path BUT those handlers' except paths apparently unexecuted in measure?? (Actually they ARE executed — verify: sentiment/corpus/detect tests exist. The 92/352/389 NEVER markers = the file-not-found branches were tested in OTHER handlers; normalize/tokenize/file branches differ per handler.)
- 134: emit_steps_trace entry
- 156-160, 694-698: retry_report.failed_indices (batch retry failures printing) — batch tests don't trigger retries
- 228->232, 269-271: dialect non-json print + is_msa branch
- 408->410: normalize --format? (check)
- 469->473: plugins failure printing — need plugin raising discover
- 610-613: TqdmProgressCallback ImportError fallback
- 618-622: --skip-errors on_error callback
- 786-787: spec no-subcommand
- 851: stream cancelled
- 1270-1271: unknown command → print_help rc=1 (main([]) → SystemExit(2) first; need handler None case: args.command populated but no handler)

### pipeline.py 98% (12 partial, 8 missing)
- 541->548: stop-words stage with metadata
- 644: hooks.after_process(merged) — need hook
- 804, 809->816, 816->833: collect-policy no-result RuntimeError
- 1067, 1080: cancellation_token.raise_if_cancelled (async)
- 1092: fail_fast raise failure
- 1190, 1199->1214, 1216: async retry branches
- 1365: enable_option non-boolean field TypeError

### normalizer.py 95%: 47 (TaaMarbutaProcessor), 61 (RepeatedPunctuationProcessor) — flags
### fuzzy_matcher.py 97%: 76, 78 (ngram-jaccard empty guards), 181->183 (stem/root index)
### language_detector.py 94%: 170 (all-space/empty text detection), 301-303 (arabizi branch)
### streaming.py: 322->exit (fingerprint mismatch OSError)
### number_words 234->239 (compound و- suffix), dialect_norm 184->186 (device), keyboard 165->162, root 120->115, stemmer 280->282, text_stats 143->142, text_analyzer 125->124/130->129 (loopback partials)

## Round 17 candidate work (WP structure)
WP1 Gap strengthening (target 99%+ branch):
1. CLI: add tests covering normalize/tokenize/detect file-not-found branches, dialect non-json, plugins failure print, --skip-errors, tqdm fallback (ImportError path via sys.modules), spec no-subcommand via handler dispatch, batch retry failures.
2. Pipeline: hooks.after_process test; collect-policy RuntimeError branch; async cancellation_token raise (async batch); fail_fast raise; enable_option TypeError.
3. normalizer.py 47/61: OrthographicNormalizer flags disable test.
4. fuzzy_matcher: jaccard_ngram empty inputs; stem/root index branches.
5. language_detector: empty/all-space text; arabizi detection.
6. streaming 322->exit: fingerprint mismatch.
7. number_words compound و- form (e.g. "عشرون وخمسة" style) to hit 234->239 loopback.

WP2 New features (3 max, enterprise):
- F1: config "Preset presets registry/summary" — PipelineConfig.presets catalog + config validation summary (validate()) — small.
- F2: spelling_processor enhancement — configurable dictionary + suggestions (FuzzyArabicMatcher-based spelling correction stage).
- F3: pipeline checkpoint/resume for long batches? streaming exists. Alternative: BatchResult.with_statistics / AnalysisReport extensions.
- F3 alternative: `exporters.export_html()` report. Choose carefully.

WP3 Engineering: docs/typing/error-path coverage for WP2.
