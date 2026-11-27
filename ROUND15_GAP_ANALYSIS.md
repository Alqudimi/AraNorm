# Round 15 Gap Analysis — AraNorm

## Baseline (end of Round 14)
- Tests: 1150 passed, 5 skipped
- Statement coverage: 97.5% (5711/5856)
- Branch coverage: 93.0% (1624/1746)

## Coverage gaps by module (missing arcs / missing lines)

| Module | Branch % | Missing arcs | Missing lines |
|---|---|---|---|
| processors/text_cleaning_processors.py | 50.0% | 78->80, 80->82 | - |
| processors/normalization_processor.py | 62.5% | 75->76, 118->120, 120->125 | 76 |
| stages/normalizer.py | 68.8% | 40->42..64->66 (10) | 47, 61 |
| stages/morphological.py | 83.3% | 26->29 | 29 |
| stages/stop_words_stage.py | 83.3% | 57->62 | - |
| stages/dialect_norm.py | 95.0% | 184->186 | - |
| stages/cleaner.py | 95.0% | 47->49 | - |
| processors/number_words_processor.py | 95.5% | 234->239 | - |
| utils/keyboard_fixer.py | 95.5% | 165->162 | - |
| utils/stemmer.py | 90.0% | 227->234, 238->241, 280->282 | - |
| utils/fuzzy_matcher.py | 90.0% | 75->76, 77->78, 173->174, 181->183, 247->248 | 76, 78, 174, 248, 301 |
| utils/root_extractor.py | 87.5% | 120->115 | - |
| utils/language_detector.py | 86.7% | 169->170, 300->301, 301->302, 301->303 | 170, 301, 302, 303 |
| utils/text_stats.py | 92.9% | 143->142 | - |
| utils/tokenizer.py | 96.4% | 190->198 | - |
| server.py | 88.6% | 48->50, 88->89, 197->198, 278->279, 306->307, 311->312, 365->366, 379->380 | 46,47,50,86,87,89,93,149,151,198,279,307,312,366,380 |

## Plan focus (Phase 3 of Round 15)
1. **P0 — server.py**: largest gap (15 lines, 8 branches). Dedicated test suite.
2. **P0 — stages/*.py**: normalizer/cleaner/dialect_norm/morphological/stop_words_stage gaps.
3. **P0 — processors/normalization_processor.py, text_cleaning_processors.py, number_words_processor.py**: branch gaps.
4. **P1 — utils/ residual gaps**: stemmer(3), text_stats(1), tokenizer(1), keyboard_fixer(1), fuzzy_matcher(5), language_detector(4 documented dead), root_extractor(1).
5. **F1+ — New features** (round 15 extensions):
   - F1: `text_stats` — readability extension (Flesch-like Arabic readability index, word diversity, sentence-length distribution) + CLI integration
   - F2: `exporters` extension — JSON Lines + multi-format batch export
   - F3: `language_detector` improvement — more languages support extension / detection confidence API refinement
   - F4: pipeline — batch config profiles + preset composition already done R14; consider `analyze` convenience (text analyzer composition)

## Rules
- No rewrites from scratch. Append tests, extend modules.
- Every new feature needs a dedicated test file: tests/test_coverage_round15_*.py
- Maintain make verify green (black/flake8/mypy/pytest).

## Detailed understanding of missing branches (measured)

- `stages/normalizer.py` 40->42..64->66, lines 47/61: the `_build_processors` guard block — each `if self.config.<feature>` false-branch never taken (tests enable all flags) AND lines 47/61 missing = processors never EMPTY (always ≥1 enabled). Need a PipelineConfig that disables ALL normalizer flags (rare: config with every normalize_x=False) and one test with single disabled flag.
- `stages/morphological.py` 26->29, line 29: `raise TypeError("analyzer must be callable or expose analyze(text)")` — need analyzer that is neither callable nor has analyze().
- `stages/cleaner.py` 47->49: cleaner `_build_processors` false branch (config.remove_english=False probably already... 47->49 is the false path of remove_english or normalize_whitespace).
- `stages/dialect_norm.py` 184->186: false branch inside HF model load block (model already loaded / device None).
- `stages/stop_words_stage.py` 57->62: `process` alias path where context is None and result returns — needs calling stage.process() directly with context None.
- `processors/normalization_processor.py` line 76 + arcs 75->76, 118->120, 120->125: NormalizationProcessor branches (e.g., mode variations).
- `processors/text_cleaning_processors.py` 78->80, 80->82: EnglishProcessor branch (likely no-match case).
- `processors/number_words_processor.py` 234->239: branch in word-number conversion (fallback path).
- `utils/stemmer.py` 227->234, 238->241, 280->282: same defensive branches from R14 still missing in FULL-suite measurement (my R14 tests ran separately, maybe not picked up in branch measurement). Re-verify.
- `utils/fuzzy_matcher.py` lines 76,78,174,248,301 + arcs 75->76,77->78,173->174,181->183,247->248.
- `utils/keyboard_fixer.py` 165->162: arc loop-back in fix_text.
- `utils/language_detector.py` 170, 301-303: documented dead code (R14) — keep as-is.
- `utils/root_extractor.py` 120->115: loop-back arc.
- `utils/text_stats.py` 143->142: loop-back arc.
- `utils/tokenizer.py` 190->198: guard false path (short sentence extension).
- `server.py` (BIGGEST): lines 46,47,50 (resolve_stream_path ValueError path), 86,87,89,93 (request parse: JSON decode error, missing content-type, bad length), 149,151 (normalize endpoint errors), 198 (stream path errors), 279,307,312,366,380 (create_server validation, run_server mutual exclusion, watcher paths).

## Round 15 test files to create
1. tests/test_coverage_round15_p0_server.py — server.py full suite (HTTP client + error paths)
2. tests/test_coverage_round15_p1_stages.py — stages gaps
3. tests/test_coverage_round15_p1_processors.py — processors gaps
4. tests/test_coverage_round15_p1_utils_residuals.py — utils residuals
5. Features: F1 text_stats advanced (readability/diversity), F2 exporters JSONL batch, F3 dialect norm local fallback, F4 pipeline analyze convenience
