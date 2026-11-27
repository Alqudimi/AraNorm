# ROUND 16 P2 STATE (after gap suite run)

## Coverage report for targeted files (all tests, branch=True, omit=/dev/null):
- core/config.py: 99% (3 BrPart: 155->exit, 329->328, 335->334)
- core/contracts.py: 100%
- core/runtime.py: 100%
- utils/exporters.py: 100%
- utils/progress.py: 100%
- core/spec.py: 99% (missing line 111)
- stages/normalizer.py: 95% (missing 47, 61)
- utils/language_detector.py: 94% (missing 170, 301-303)
- core/pipeline.py: 98% (BrPart 12: 541->548, 644, 804, 809->816, 816->833, 1067, 1080, 1092, 1190, 1199->1214, 1216, 1365)

## Tests file: tests/test_coverage_round16_gaps.py — 35 passing.

## Remaining branch gaps analysis (need real fixes, not only tests):
1. spec.py line 111: `if not isinstance(self.metadata, dict): raise ConfigurationError("metadata must be a dictionary")` — my test PipelineSpec(...,metadata=[1,2,3]) FAILED because validation order: pipeline_class validation happens first ("Unsupported pipeline_class")! So line 111 unreachable from normal constructor with invalid class. FIX: metadata check must happen before class check, OR test with valid class "ArabicNormalizationPipeline" — wait I already used valid class! Trace said: "Unsupported pipeline_class: 'aranorm.core.pipeline.ArabicNormalizationPipeline'" — because __post_init__/class check uses a different accepted string list. Need to see spec.py lines 80-115 to fix ordering (move metadata check first).
2. language_detector.py 170, 301-303: fallback paths. detect_language("---!!!...") returned "unknown" ✓ (test passes) but coverage still shows 301-303 — those are probably other paths (e.g., detect with arabizi fallback, or is_arabic). Need to read lines 160-175 and 295-310.
3. stages/normalizer.py 47, 61: ligatures/tatweel processor build branches — test passes (35 passing) but coverage unchanged; maybe the flag defaults already True in "light"? Check config: normalize_ligatures/tatweel defaults. My config passed flags True. Lines 47/61 might be "if self.config.normalize_ligatures" branches where processor added; coverage may show them missing because they ARE executed... BrPart 2 with stmts 47/61 missing means the if-true branch missing? Test passed assertions — processors present. Hmm, need to read lines 40-65.
4. pipeline.py remaining 12 branches: need targeted configs (stop_words via config field works? long_text test passes but 541->548 still missing), retry paths 804/809-833 (sync batch retry catastrophic path works via RuntimeError patch but missing...), async 1067/1080/1092/1190/1199-1214/1216, 1365 (add_cleaner unknown option test passes coverage but branch still missing? test passed - maybe coverage run used OLD file version).
   NOTE: 1365 test test_builder_add_cleaner_unknown_option_raises PASSED — pipeline coverage still shows 1365 BrPart. Either branch is different wording or the test covers a different ValueError.

## test failures investigation (dialect + matrix)
- dialect test fails in FULL run due to module leakage from another old test file using camel_tools mock (test_models.py or similar; test_coverage_round13_p0 clean). Need binary search among remaining files (test_models, test_cli?, etc).
- test_integration_matrix::test_absent_dependency_cleanup_does_not_pollute_module_registry fails in clean env: asserts pandas exists (`original is not ...`) — fails when pandas not installed. Should skipif not pandas or expect None.

## Strategy for deeper gaps: coverage.run used ALL tests including my new suite — branches still missing are genuinely unexercised. Read exact source lines and design precise configs.

## Other facts
- test_stages.py::test_dialect_identifier_camel_raises_without_package FAILED (2 failed total in full run — check what; likely interaction with conftest camel_tools fake leakage).
- DialectTarget enum: none/coda/msa. Preset: light/standard/deep/social_media.
- StopWordsConfig params: mode=(remove|extract|highlight|count), scope=(universal|msa_only|dialect_aware|custom), preserve_negation, remove_filler etc.
- PipelineConfig fields: preset, dialect_target(DialectTarget.NONE), supported_dialects, stop_words_config(default None), resource_limits, detect_* does NOT exist.
- process_async/process fallback flow: executor calls self.process(fallback_value); fallback must be accepted by process validation (str) — test used original(text) returning NormalizationResult then failing returns args[-1] which then process() re-validation?? Actually process accepts str only; fallback returned NormalizationResult → error. Final working test: failing returns args[-1] (pass through).
- asyncio retry tests: process_batch_async mocked via side_effect=BatchProcessingError(errors={0:..}, results=None) works for exhausted-retries coverage.
- CancellationToken in aranorm.core.contracts (not core.cancellation).

## Detailed gap analysis (after spec.py fix: line 110-111 dead branch → assert kept coverage, removed dead branch)

normalizer.py gaps 47 & 61: real lines = 47 (TaaMarbutaProcessor branch: `if self.config.normalize_taa_marbuta`) and 61 (RepeatedPunctuationProcessor branch: `if self.config.remove_extra_punctuation`). My suite had test with normalize_taa_marbuta=True + remove_extra_punctuation=True — but report still shows missing. Likely because those config flags require explicit flags in PipelineConfig — check PipelineConfig has those flags. Test passed assertion, so processors present... but coverage says stmts 47,61 NOT covered → meaning my flags NOT passed or test uses different config. Need to verify PipelineConfig fields: normalize_taa_marbuta and remove_extra_punctuation exist.

detector.py gaps 170 (arabizi_score >= threshold branch at line ~300? Actually 170 is likely the "empty text returns unknown" at ~168-175) and 301-303 (module-level convenience detect_language/is_arabic at 313+ — stmts 301-303 are likely lines in detect() e.g. "mixed" return at ~290?). Report showed missing 170, 301-303 with stmt count 4. detect_language convenience IS used in my gaps test (line 206) but coverage says missing → the file in report may differ. Actually convenience at 313-327. 301-303 = maybe inside detect() after arabizi check: `return "mixed"`? Need read lines 285-305. 170 = empty text early return (~168). Test used "---!!!..." (non-empty). Add empty string test.

dialect test failure: need full error output (grep returned empty — session switching issue). test_stages.py::test_dialect_identifier_camel_raises_without_package — likely my conftest autouse (camel_tools delitem) interacts: conftest fixture deletes camel_tools AFTER test_optional? Actually conftest fixture runs before each test globally (module-level autouse scope=function) — camel_tools deleted before dialect test, then test imports DialectIdentifierStage which late-imports camel_tools.dialectid → ImportError → IntegrationUnavailableError ✓ should pass. Failure maybe different. Run individually with full output.

## Resolution plan for leakage (key context)
The conftest module-level autouse fixture `_isolate_optional_modules` only applies to tests within conftest's own module — that's why leakage across files persisted. After editing conftest, the cleanest universal fix is to register fakes in `_isolate_optional_modules` AND ensure each new suite file (test_coverage_round16_models.py, test_coverage_round16_integrations.py) registers the same fake names in its own local autouse fixture, because module-level autouse fixtures apply only to their own unit. However pytest actually DOES apply conftest fixtures globally when conftest.py is in a parent directory (tests/conftest.py applies to all tests under tests/). So the conftest edit alone should fix cross-file leakage. Verify with full run.

## Also fix (old files)
- tests/test_integration_matrix.py line ~152: `test_absent_dependency_cleanup_does_not_pollute_module_registry` fails in clean env (no pandas) with `assert original is not ...`. Fix: skipif pandas missing, or expect None case.
- tests/test_coverage_round16_integrations.py `_make_fake_nltk` etc use `sys.modules.setdefault` (permanent). Replace with direct setitem + monkeypatch undo via local fixture finalizer OR conftest now covers it. After conftest fix, setdefault values get deleted next test start — but remain until then: same test's second raise check in test_optional_dependency_contracts may pass since conftest cleans per test.
- models file: `_make_fake_camel_tools`/`_make_fake_transformers` setitem directly → remains until conftest fixture deletes at next test start. OK with conftest fix.

## Remaining work order
1. Fix matrix test (skipif / None-aware) + verify conftest fix resolves dialect failure in full run.
2. Verify integrations files don't break (setdefault leaves entries until next fixture).
3. Coverage measurement of all P2 targets (config 96-97%→ aim 100, spec done, contracts 100, runtime 98, exporters 99, progress 99, normalizer 98, detector 97, pipeline 96).
4. WP4: TextSimilarityMatrix + TextDiffReport new features with tests.
5. make verify (lint/mypy/pytest+coverage) → release report + archive.

## FINAL coverage status (after conftest fix + matrix skipif fix)
- Full run: 1424 passed, 0 failed, 6 skipped
- TOTAL: 99% stmt (need branch %: run with branch=True)
- cli.py 94% missing stmts: 92, 98, 117-121, 134, 153, 156-160, 269-271, 292, 352, 357, 389, 394, 596-598, 610-613, 618-622, 680, 692, 694-698, 786-787, 851, 1270-1271, 1283
- pipeline.py 99% missing: 644, 804, 1067, 1080, 1092, 1190, 1216, 1365
- All other src files 100%!

## Next: WP4 new features
TextSimilarityMatrix (text_comparator.py exists? 100% covered → exists since round15?) — CHECK what exists first; don't duplicate.
Plan: 1) read text_comparator/analysis APIs; 2) build TextSimilarityMatrix in analysis/ (pairwise similarity of list of texts with metrics) + TextDiffReport (diff between two normalized texts: token-level diff report); tests + coverage.
Then: make verify → round16 report + archive.

## WP4 design decisions
- TextComparator API: compare(text_a, text_b) → SimilarityResult (frozen dataclass with jaccard/cosine/content metrics, shared_tokens, unique_to_a/b, verdict, to_dict). compare_batch exists, rank_by_similarity, find_duplicates.
- New feature 1: `TextSimilarityMatrix` (analysis/similarity_matrix.py): input list of texts → pairwise SimilarityResult matrix; methods: matrix (list of lists scores), find_closest_pairs(threshold), top_n_pairs(n), to_dict, json dump. Builds on TextComparator.compare (O(n^2), n(n-1)/2 unique pairs).
- New feature 2: `TextDiffReport` (analysis/text_diff_report.py): token-level LCS-based diff between two texts (after normalization): sequence of diff ops (equal/insert/delete), stats (similarity ratio, changed tokens), to_dict/json. Uses difflib.SequenceMatcher.
- Both added to analysis/__init__.py exports + tests/test_coverage_round16_new_features.py (~50+ tests).
