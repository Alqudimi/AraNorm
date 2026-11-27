# Partial-branch diff results (from _r17_diff_coverage.py)

Running edge_cases alone reduces partials dramatically vs full-suite base:
- text_analyzer 2->0, config 3->0, pipeline 10->0, streaming 1->0,
  dialect_norm 1->0, keyboard 1->0, root_extractor 1->0, fuzzy 3->2.
- cli.py 2->3 (WORSE — the missing_lines=[352] branch is NOT covered by
  edge_cases; a separate test needed).
- language_detector 2->6 (WORSE — our _classify direct calls do NOT hit
  the real classify branches; need real-text tests through detect_detailed).

## Interpretation
The "remaining" partials in full-suite are actually fully covered by
edge_cases when it runs alone; they become partial in full-suite due to
cross-test interference (mocks/state from other tests affecting coverage
recording — typical with sys.modules patching tests).

## Remaining REAL targets (persist in any measurement):
1. cli.py L352: sentiment handler file-not-found branch — the sentiment
   handler reads from --file but our test uses ["sentiment","--file",
   "/nonexistent"] and rc==1 passes. The missing branch may be elsewhere:
   check sentiment handler: maybe `texts = [line.rstrip("\n") for line in
   fh if line.strip()]` comprehension's filter branch (`if line.strip()`
   false path). Add test with file containing blank lines.
2. language_detector missing_lines=[170, 301, 302, 303]: real-text tests
   through detect_detailed/detect whose computed arabizi thresholds cross
   both ways. e.g.:
   - "مرحبا hello hello hello" (mixed, arabizi low) -> mixed
   - "marhaba ahlan wa sahlan" (latin dominant, arabizi high) -> arabizi
   - pure arabizi crossing at equal ratios: "ktb ktbt ktb" (arabizi score
     high w/ no arabic letters) -> arabizi vs unknown.
   - Line 170: detect_detailed empty branch (char-only empty result).
   Check _classify logic: arabizi_score computed from arabizi patterns vs
   latin words.

## Full-suite final numbers
1544 passed, stmt 99.7845%, branch 98.4270% (1780 branches, partial=26,
missing=2). The 26 partials are mostly cross-test artifacts; real code
coverage is effectively higher. Document honestly: 98.4% branch, 99.8%
stmt; remaining partials are cross-suite mock interference + 6
by-design unreachable pipeline dead branches.

## Plan from here
- Add 2-3 targeted tests: cli sentiment blank-lines file; language_detector
  real-text arabizi tests (via detect_detailed, not _classify).
- Re-run full suite, confirm partials <= ~10 and missing 0-2.
- WP2: 3 analysis features (SpellingReport, TextQualityScore,
  BatchAnalysisReport) + tests >=40 + docs.
- Then verify gate + report + archive.
