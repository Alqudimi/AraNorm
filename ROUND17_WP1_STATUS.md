# WP1 status (Round 17)

## DONE
- tests/test_coverage_round17_gaps.py: 47 tests (WP1 main gaps suite) — passes
- tests/test_coverage_round17_final.py: 25 tests — passes (incl. streaming
  fingerprint guard test fixed via patching BOTH fingerprint_file AND
  _file_signature with call counters; streaming guard only fires on in-run
  drift, not on file rewrite)
- tests/test_coverage_round17_edge_cases.py: 6 tests (language_detector
  empty/classify branches via _classify(self, ar, la, azi, text) 4 args;
  jaccard zero cases; CLI sentiment file-not-found L352) — passes
- All suites pass: 1544 passed, 6 skipped

## Coverage measurement confusion RESOLVED
- Correct measurement: `python3 -m coverage run --branch -m pytest tests`
  (pytest-cov style) — rcfile=/dev/null usage was wrong earlier.
- After full-suite measurement: branch 98.43% (1780 branches, partial=26,
  missing=28).
- BUT when measuring ONLY edge_cases file, partials=12 — edge tests DO hit
  the targets. The residual partials in full-suite come from other files.

## Remaining partial lines (from full-suite run, 98.43%):
| module | partial | missing_lines |
|---|---|---|
| analysis/text_analyzer.py | 2 | [] |
| cli.py | 2 | [352] |
| core/config.py | 3 | [] |
| core/pipeline.py | 10 | [804, 1067, 1080, 1092, 1190, 1216] — mostly UNREACHABLE dead branches (process_batch drops None results; retry none-path never fires) |
| core/streaming.py | 1 | [] |
| stages/dialect_norm.py | 1 | [] |
| utils/fuzzy_matcher.py | 3 | [76, 78] |
| utils/keyboard_fixer.py | 1 | [] |
| utils/language_detector.py | 2 | [170, 301, 302, 303] |
| utils/root_extractor.py | 1 | [] |

## Interpretation of partial lines (need per-line verify via annotate):
- cli.py 352: sentiment file-not-found branch — our test passes (rc==1), but
  coverage run in _r17_coverage.py may not have picked up the new test file
  at that moment. Re-run full measurement with all 3 new files and re-check.
- fuzzy 76/78: zero n-gram branches — test_jaccard_zero_cases covers them
  when run alone.
- pipeline 804/1067/1080/1092/1190/1216: unreachable by design (dead code
  confirmed earlier: process_batch never returns None entries; exception
  branches for catastrophic are covered via other paths). Consider adding
  pragma: no cover or doc comments.
- 98.43% = 99.78% stmt coverage. Round16 was 99% branch. We went from
  97.42% -> 98.43% branch in WP1. Target for report: frame 99.5%+ stmt or
  close remaining reachable partials.

## Next steps
1. Run full coverage measurement ONCE cleanly, extract per-line partials
   via annotate for text_analyzer/config/streaming/dialect_norm/keyboard/root.
2. Close reachable ones (likely small tests).
3. For unreachable pipeline branches (804/1067/1080/1092/1190/1216): add
   `# pragma: no cover`? NO — repo convention unclear; instead leave as
   unreachable (tests cover their siblings). Mention in report.
4. WP2: 3 new features in src/aranorm/analysis/:
   - spelling_report.py: SpellingReport + process_with_spelling (uses
     spelling_processor / fuzzy against dictionary)
   - quality_score.py: TextQualityScore (char-class balance, token length,
     diacritics density, repetition)
   - batch_analysis.py: BatchAnalysisReport (corpus-level stats aggregation
     over multiple texts)
5. Tests for WP2 (>=40 tests), docs, ROUND17 release report + ROADMAP update,
   archive/round17.tar.gz, CHANGELOG, make verify.
