# Round 17 — final branch gap state (post WP1)

## Final measurement (clean run, _r17_final_coverage.py)
- 1544 passed, 6 skipped, stmt 99.7845%, branch 98.4270% (1780 branches:
  covered=1752, partial=26, missing=2)
- Baseline Round16: 99% branch. WP1 improved from 97.42% -> 98.43%.
- Note: the pipeline unreachable branches (804, 1067, 1080, 1092, 1190,
  1216) are dead code confirmed (process_batch drops None results; the
  "no-result during initial pass" RuntimeError path never fires because
  initial list never contains None entries under collect mode).

## Per-module status (partial / missing):
| module | branch% | partial | missing |
|---|---|---|---|
| text_analyzer | 87.5 | 2 | 0 |
| cli | 98.86 | 2 | [352] |
| config | 96.59 | 3 | 0 |
| pipeline | 96.06 | 10 | [804,1067,1080,1092,1190,1216] |
| streaming | 98.89 | 1 | 0 |
| dialect_norm | 95.0 | 1 | 0 |
| fuzzy_matcher | 94.0 | 3 | [76,78] |
| keyboard_fixer | 95.45 | 1 | 0 |
| language_detector | 86.67 | 2 | [170,301,302,303] |
| root_extractor | 87.5 | 1 | 0 |

## Edge case tests ADDED (test_coverage_round17_edge_cases.py, 6 pass):
- jaccard zero cases (fuzzy 76/78), sentiment file-not-found (cli 352),
  language_detector empty + _classify branches. BUT full-suite partials
  unchanged (26 partial still) — likely because these lines are PARTIAL
  not missing; the test passes but branch not fully exercised.
- The _r17_partial_lines.py annotate extraction printed NOTHING (annotate
  markers probably "> " 2-char prefix with num at 4:11 wrong for this
  coverage version; need to inspect raw annotate file format first).

## Next concrete actions
1. Fix annotate parsing (inspect one annotate file manually: head -5,
   find ">  " prefix lines).
2. Add targeted tests for each remaining partial:
   - cli 352: ensure main(["sentiment","--file",missing]) returns 1 AND
     coverage shows branch executed (it did; may be the sentiment handler
     reads args differently — verify dest names).
   - text_analyzer partials (analyze empty? chars-only?), config partials
     (merge edge cases), streaming 1 partial (completed=True early return
     maybe), dialect_norm partial, keyboard partial, root_extractor partial.
   - language_detector missing 170, 301-303 (arabizi threshold branches) —
     need real text inputs through detect_detailed that hit those branches
     (ratios/ arabizi_score computed from text, not direct args).
   - pipeline unreachable: leave + comment in report; optionally add
     pragma no cover to 6 dead lines.
3. WP2 features after gaps close: spelling_report.py (SpellingReport,
   process_with_spelling on pipeline), quality_score.py (TextQualityScore),
   batch_analysis.py (BatchAnalysisReport corpus stats). >=40 tests.
4. Then: docs + ROUND17 report + archive/round17.tar.gz + CHANGELOG +
   make verify (black/flake8/mypy).
