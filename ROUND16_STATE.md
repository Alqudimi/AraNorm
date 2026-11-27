# ROUND 16 STATE — WP2 INTEGRATIONS + WP3 REMAINING — 2026-08-18

## WP2 STATUS (current session)
- tests/conftest.py CREATED: autouse fixture `_isolate_optional_modules` delitems nltk, nltk.corpus, spacy, pandas, datasets before every test (fixes fake-module leakage; without it test_optional's nltk=None tests DID NOT RAISE because fake submodules persisted).
- tests/test_coverage_round16_integrations.py REBUILT (~430 lines): fakes _FakeHFColumnar/_FakeHFDataset/_FakeHFDatasetDict (+_make_fake_datasets), _FakeSeries/_FakeDataFrame(_FakeRowsDataFrame pd.DataFrame(rows, index) constructor), _FakeLangDefaults/_FakeVocab(CACHED lexemes)/_FakeLexeme/_FakeNLP, _FakePipeline/_FakeResult, _make_fake_nltk (registers nltk AND nltk.corpus in sys.modules), _make_fake_spacy, _make_fake_pandas. Coverage after run: nltk 100%, spacy 100%, sklearn 100% (3 new tests), pandas 98% (only 52->56 branch), huggingface STILL 29% — new HF tests (dataset, datasetdict, remove_original, custom output col, expand default+custom, custom pipeline, missing-datasets) written, NOT yet run.
- SKLearn notes: StopWordsRegistry has no add_words; use registry._load_universal().insert(w). SklearnStopWordsAdapter to_sklearn_set/to_sklearn_list take scope kwarg.

## How to measure coverage (pyproject.toml omitS integrations + models — use /dev/null rcfile)
```bash
python3 -m coverage run --branch --rcfile=/dev/null --source=src/aranorm/integrations -m pytest -c /dev/null tests/test_coverage_round16_integrations.py tests/test_optional_dependency_contracts.py -q
python3 -m coverage report --rcfile=/dev/null --show-missing
```

## Remaining round 16 work
1. Run new HF tests → fix _FakeHFDatasetDict.map (it wraps each split: must reproduce the real code path — current impl may be broken, verify).
2. WP3: src/aranorm/models/_transformers_model.py (46 stmt, 0%) — sys.modules fake transformers; pattern in test_dialect_norm_contracts.py line 73/120/139. Then models coverage.
3. P2 small gaps: config.merge preset_override (314-319), spec OSError (111, 245-250), contracts n_workers<1 (123), runtime PermissionError (81), exporters to_dataframe ImportError (236-237), progress ImportError (166-167), normalizer.py 47/61, language_detector 170/301-303, pipeline.py branches (541->548, 644, 804, 809->816, 816->833, 1067, 1080, 1092, 1190, 1192->1199, 1199->1214, 1216, 1365).
4. P3 features: F1 TextSimilarityMatrix (utils/fuzzy_matcher.py, canonical_form-based), F2 TextDiffReport (utils/diff_report.py, word-level insertions/deletions/unchanged/changed_positions/ratio) + pipeline.process_with_diff(text) → (NormalizationResult, TextDiffReport).
5. Final make verify + ROUND16 archive.

## OLD ROUND 16 STATE — Phase 1 (Analysis)


## Base state after Round 15 (COMPLETE)
- make verify green: 1298 passed / 5 skipped / 0 failed; black/flake8/mypy clean.
- Branch coverage 95.08% overall. Archive at archive/round15/ (tar.gz + SHA256SUMS).
- Round 15 features: readability.corpus_summary(), exporters.export_jsonl(), core.pipeline.AnalysisReport (fixed abs-length bug).
- Server 100% stmt/~99% br; readability 100%; many files 100%.

## Round 16 Phase-1 coverage analysis (coverage run branch=True, /tmp/r16_coverage.txt, tests log /tmp/r16_tests.log)

### Files with 0% / very low coverage (import-gated, optional deps — candidates for harness-based testing, NOT unit-import-only):
- models/_transformers_model.py 0.00% (46 stmt) — transformers backend
- models/coda_model.py 0.00% (10), models/dialect_id_model.py 0.00% (20), models/msa_model.py 0.00% (10)
- models/__init__.py 0.00% (4)
- integrations/huggingface_integration.py 29.09% (31 miss, lines 47-53, 79-97, 124-136, 148-155)
- integrations/spacy_stopwords.py 50.00% (57-67)
- integrations/nltk_stopwords.py 68.97% (75, 136-143, 182-183)
- integrations/pandas_integration.py 88.68% (52->56, 155-160)

### Moderate coverage files (branch gaps):
- cli.py 82.13% (96 miss, 34 par): 92, 98, 117-121, 134, 153, 156-160, 228->232, 269-271, 287, 292, 308-312, 326-333, 352, 357, 366-367, 373, 389, 394, 402-412, 469->473, 498-502, 520, 522-523, 571-574, 596-598, 610-613, 618-622, 680, 692, 694-698, 714-715, 735-743, 781-783, 786-787, 851, 885, 889, 1270-1271, 1283
- config.py 95.71%: 155->exit, 314-319, 329->328, 335->334
- pipeline.py 97.47%: 541->548, 644, 804, 809->816, 816->833, 1067, 1080, 1092, 1190, 1192->1199, 1199->1214, 1216, 1365
- spec.py 98.52%: 111, 245->250
- normalizer.py 94.87%: 47, 61 (stmts missing)
- language_detector.py 93.55%: 170, 301-303
- fuzzy_matcher.py 97.11%: 76, 78, 181->183
- text_analyzer.py 98.23%: 125->124, 130->129 (loopbacks)
- stemmer 98.95% 280->282; root 97.50% 120->115; text_stats 98.98% 143->142; keyboard 99.01% 165->162; dialect_norm 99% 184->186; number_words 98.85% 234->239 (all loopback/partials)
- contracts.py 97.75%: 123; runtime.py 98.63%: 81; streaming.py 99.74% 322->exit; exporters.py 98.65%: 236-237; progress.py 97.50%: 166-167

### Key decisions for Round 16 (enterprise scope):
P0 (coverage):
1. Optional-integration harness tests: use monkeypatch to fake-import transformers/nltk/spaCy/pandas and exercise models/* and integrations/* — big gains (currently 0-69%).
2. CLI harness: round15/16 CLI tests for missing branches (96 miss). Check existing tests/test_cli*.py coverage of CLI.
3. config.py 314-319 (likely from_file errors), spec.py 111, contracts 123, runtime 81, exporters 236-237, progress 166-167: small targeted tests.
P1 (features) — candidate features (to finalize in roadmap):
- F1: `process_text_with_report()`? Already have AnalysisReport.from_result. Candidate: TextDiffReport utility / export_csv convenience?
- Candidates from gaps analysis perspective: 
  a) Fuzzy matcher: batch similarity matrix (jaccard_matrix) — analytical.
  b) Pipeline: `process_with_diff()` convenience returning AnalysisReport directly.
  c) Exporters: export_tsv/export_parquet-like or CSV with dialect quoting? CSV exists in BatchExporter.
  d) CLI: new subcommand? risky. 
  e) models: fallback mock/stub model support?
  f) text_stats: richer stats (unique_ratio trends)? corpus_analyzer 100% already.
- Decide 3 features max, consistent with existing architecture.
Round 16 files will be tests/test_coverage_round16_*.py.

## Phase-1 deep analysis (additional)
- CLI 82.13% (96 miss, 34 par): فجوات = أوامر فرعية غير مختبرة كليًا (analyze-text? compare preview, stats-print, sentiment report output, corpus analysis, spec validate, serve streaming flag, __main__ path) + فروع stdin/no-file + فروع أخطاء. النمط: output/print وCLI arg combos.
- models/ 0%: lazy transformers wrapper قابل للاختبار عبر sys.modules fake (نمط موجود في test_dialect_norm_contracts.py).
- integrations: huggingface 47-53 (init default pipeline)، 148-155 (_ensure_datasets)، normalize_dataset مع DatasetDict + Dataset (88-100)، expand_dataset 124-136؛ pandas 155-160 (apply_stop_words)؛ nltk 75 (to_frozenset exists?), 136-143 (filter_tokens), 182-183 (register_with_nltk tail)؛ spacy 57-67 (enrich_spacy).
- config.py 314-319: merge مع preset_override + dialect_target/stop_words/resource_limits overrides (Round 15 features غير مختبرة بالكامل في merge).
- exporters.py 236-237: BatchExporter.to_dataframe ImportError path.
- progress.py 166-167: TqdmProgressCallback ImportError path.
- spec.py 111 (metadata non-dict)، 245->250 (OSError + unlink OSError في write).
- contracts.py 123: n_workers < 1.
- runtime.py 81: PermissionError path.
- normalizer.py 47, 61: stmts في OrthographicNormalizer (flags: normalize_ligatures? tatweel?) — تحتاج copy_with تعطيل.
- language_detector.py 170, 301-303: detection fallbacks.
- fuzzy_matcher.py 76, 78 (dead guards n-empty)، 181->183 (add_many loopback).
- pipeline.py gaps: 541->548 (stop_words stage with metadata), 644 (avg stats), 804/809->816/816->833 (batch retry collect policy), 1067, 1080, 1092, 1190, 1192->1199, 1199->1214, 1216, 1365 (process_long_text branches, AnalysisReport? hooks?).
- CLI commands needing new tests: compare-preview, analyzer-print, sentiment-report-output, corpus-analysis, spec-validate-branch, serve-streaming-flag, __main__ entry.

## Round 16 planned work
P0: CLI harness tests (~15 tests, +coverage ~82%→95%)
P1: integration harness tests (models lazy load, huggingface normalize/expand, pandas apply_stop_words, nltk/spacy full paths) — ~12 tests
P2: config.merge preset_override/dialect/stop_words/resource_limits; spec OSError; contracts n_workers; runtime PermissionError; exporters to_dataframe ImportError; progress ImportError — ~8 tests
P3 features (3 max):
 F1 TextSimilarityMatrix in fuzzy_matcher: pairwise jaccard matrix for corpus — analytical
 F2 PipelineConfig.merge extensions covered + maybe `config.summary()`? (no — keep small)
 F3 exporters.export_tsv()? تافه. Better: `TextDiff` utility class (word-level diff Arabic) in utils/diff_report.py + pipeline.process_with_diff()
 F4 models: add `is_available()` classmethod?
Decision: F1=TextSimilarityMatrix, F2=TextDiffReport (word-level diff: insertions/deletions/unchanged per word) with process_with_diff convenience, F3=CLI? no — F3=corpus batch readability via corpus_analyzer (exists 100%). F3=export_jsonl fields already. Choose F3: `merge_configs` convenience + PipelineConfig.from_preset()? exists. Final: F1 TextSimilarityMatrix, F2 TextDiffReport + process_with_diff, F3 HuggingFace/Pandas dataset round-trip helpers? too coupled. Alternative F3: `process_file` convenience in pipeline. Decide in phase 3 after feasibility.

## Archive structure (from round14/15): archive/roundN/ {docs(CHANGELOG,REPORT,ROADMAP,GAP), evidence(verify.log, facts.txt), source(files+patch), SHA256SUMS, tar.gz, .sha256}


## CLI argparse facts discovered (IMPORTANT)
- main() calls parser.parse_args(argv) WITHOUT catching SystemExit → argparse errors (unknown flag, missing required) raise SystemExit(2) directly.
- Handler-internal errors (FileNotFoundError etc.) are caught in main's try/except → rc=1 + "Error: ..." to stderr.
- stream status checkpoint schema: {schema_version:1, source_path, output_path, source_fingerprint:64hex, pipeline_fingerprint:64hex, next_index, output_bytes, input_count, completed} — no cancelled/encoding/processed_count/version. schema_version must == CHECKPOINT_SCHEMA_VERSION (1).
- cli compare has NO --file-a/--file-b args (text_a, text_b positional; file-read happens inside handler? no — handler treats text as literal; file reading in _cmd_compare only via open on text path? tested: text arg '/tmp/x.txt' passed as-is → 'Text A: /tmp/x.txt').
- cli corpus uses --file -f (required). tokenize uses --file -f (optional) + --sentences + --split-clitics + --keep-punctuation.
- cli sentiment: --file → "Error: file not found:" rc=1. summarize: no args → reads stdin → "no text provided" rc=1 if blank.
- spec: subparsers required=True → SystemExit on `spec` alone.
- Unknown command (handler is None) → print_help + return 1 (works via main([])? No—args.command missing → SystemExit(2)).
- server.serve imported inside _cmd_serve: replace sys.modules["aranorm.server"] with fake whose .serve is mock.
- sentiment command keywords (CLI args): --file, possibly --json, --text positional.

## WP1 RESULT: CLI suite GREEN. 32 tests in test_coverage_round16_cli.py (32 passed), lint clean. cli.py coverage via make test-cov: 94% stmt (637 stmts, 39 missing: 92,98,117-121,134,153,156-160,269-271,292,352,357,389,394,596-598,610-613,618-622,680,692,694-698,786-787,851,1270-1271) — mostly unreachable/dead error paths (argparse errors raise SystemExit before reaching handlers). Full suite: 1330 passed 5 skipped. WP1 DONE.

## WP1 status (OLD context below)
- tests/test_coverage_round16_cli.py written (32 tests). Fixed: spec via `main(["spec","export","--preset","light","-o",f])` + validate; serve via _fake_server_module() (mock.patch.dict sys.modules {"aranorm.server": fake}); StreamCheckpoint fields = schema_version(1)/source_path/output_path/source_fingerprint(64hex)/pipeline_fingerprint(64hex)/next_index/output_bytes/input_count/completed (NO cancelled/encoding/processed_count/version); rc=2 for no-args and unknown flag; HEX64="a"*64.
- Latest run: 15 failed/17 passed — still to re-verify after last fixes (stream rc=0 asserts, entry point rc=2, unknown-flag rc=2). Run again.
- After CLI green: measure cli.py coverage → expect ≥95%.

## CLI structure (for WP1 tests)
- main(argv) returns rc. Commands registered in _handlers dict (cli.py ~1260): info, normalize, stopwords, analyze, dialect, keywords, compare, tokenize, sentiment, version, describe, plugins, readability, summarize, detect, batch, corpus, serve, stream, spec.
- CLI args: main(["info"]), main(["normalize", "أنا"]) etc. capsys for stdout; tmp_path for --file/--output.
- Uncovered CLI branches map:
  - 308-312: keywords command output (text/keywords preview loop) — main(["keywords", "text"])
  - 326-333: compare command output (Text A/B/Verdict/Overall/Jaccard/Content/Shared KW) — main(["compare", text_a, text_b])
  - 352, 357: compare --file paths (file read) — main(["compare", "--file-a", f1, "--file-b", f2])
  - 366-367: compare --json? / shared_kw absent path
  - 373: tokenize --sentences output loop ([s.index] s.text) — main(["tokenize", "--mode", "sentences", "text"])
  - 389: tokenize tokens path (print " | ".join(tokens)) — main(["tokenize", "text"])
  - 394, 402-412: sentiment command report output (Label/Arabic/Latin/Arabizi, FileNotFoundError) — main(["sentiment", "text"]); sentiment --file
  - 469->473: plugins failures print — need plugin failing discover
  - 498-502: readability print (Readability/Avg sent/Avg word/Long%/Complexity) — main(["readability", "long text..."])
  - 520, 522-523: summarize? (sys.stdin.read; "Error: no text provided.") — main(["summarize"]) with empty stdin → rc 1
  - 571-574: detect output (Label/Arabic/Latin/Arabizi) — main(["detect", "text"])
  - 596-598: detect --file FileNotFoundError — main(["detect", "--file", missing])
  - 610-613, 618-622: corpus analysis output + tqdm fallback — main(["corpus", file]) needs corpus command file format
  - 680: batch to_csv_string stdout — main(["batch", "--format", "csv", "--output", "-"?])
  - 692, 694-698: batch retry failures print + corpus empty file error
  - 714-715: corpus top_content output (corpus command success)
  - 735-743: corpus top stop words output
  - 781-783: spec validate output (Valid PipelineSpec/schema/fingerprint) — main(["spec", "validate", file])
  - 786-787: spec no subcommand → "Error: a spec sub-command is required." rc 2
  - 851: stream? (Cancelled: yes) — stream status report.cancelled path
  - 885: serve --streaming-enabled — main(["serve", "--streaming-enabled"]) with mocked serve()
  - 889: serve --streaming-root without enabled → ValueError → error print rc 1
  - 1270-1271: __main__ path (python -m aranorm.cli) → subprocess? rc=130 KeyboardInterrupt branch; or run main via argparse no-args → print_help rc 1 (851?)
  - 1283: Exception handler in main (unknown command → handler None → print_help → 1)
- Note: serve() must be mocked (mock.patch('aranorm.cli.serve') won't work — serve imported inside function: mock the module attribute: monkeypatch sys.modules or patch within cli._cmd_serve.
- corpus command: expects a corpus file — check _cmd_corpus input format (JSONL? one text per line?)
- plugins failures (469-473): need _discover_plugin that raises — registry plugin with broken entry?

## Integration harness patterns (WP2)
- test_dialect_norm_contracts.py line 73/120/139: monkeypatch.setitem(sys.modules, "transformers", fake_module) — reuse.
- TransformersSeq2SeqModel: __init__(model_name, device, max_new_tokens); _load(); predict/predict_batch; is_loaded; unload. Fake module needs AutoTokenizer.from_pretrained & AutoModelForSeq2SeqLM.from_pretrained + model.generate + tokenizer(..., return_tensors="pt"...) + decode.
- HuggingFaceNormalizer: __init__(pipeline=None, batch_size=512, num_proc=None) calls _ensure_datasets (raises if no 'datasets'); normalize_dataset(dataset, text_column, output_column, remove_original); expand_dataset(dataset, text_column, fields); _make_map_fn.
- pandas fake: need DataFrame/Series classes in fake pandas module.
- NLTKStopWordsAdapter: to_nltk_list(scope)/to_frozenset(scope)/filter_tokens(tokens)/merge_with_nltk()/register_with_nltk(). nltk.corpus.stopwords.words("arabic") must be faked (OSError path for missing corpus).
- SpacyStopWordsAdapter.enrich_spacy(nlp, scope) — fake nlp with Defaults.stop_words set + vocab.

## Feature F1 decision (final)
TextSimilarityMatrix in utils/fuzzy_matcher.py: class TextSimilarityMatrix(candidates: Iterable[str], n=3) with methods: similarity(i, j) -> float; top_neighbors(text, k=5, threshold=0.0) -> List[Tuple[str, float]]; matrix(as_list=False) -> dict; __len__; canonicalization via canonical_form.
## Feature F2 decision (final)
TextDiffReport in utils/diff_report.py (new module): dataclass word-level diff between original and normalized: insertions (words only in normalized), deletions (only in original), unchanged count, changed_positions list, simple_ratio. + method process_with_diff on ArabicNormalizationPipeline? OR standalone compare_texts(original, normalized). Keep both: function compare_texts + pipeline.process_with_diff(text) convenience returning (NormalizationResult, TextDiffReport).

## ROUND 16 FINAL STATE (19 Aug 2026)
- make verify GREEN: black+flake8+mypy clean (94 files); pytest 1478 passed / 0 failed / 6 skipped (env-dependent)
- Branch coverage TOTAL 99% (6298 stmts, 1816 branches, 46 partial) via coverage report --rcfile=/dev/null
- All WP done: WP1 cli 95%, WP2 integrations 98-100%, WP3 models 98-100%, WP4 residual gaps closed, WP5 features shipped (TextSimilarityMatrix + TextDiffReport/process_with_diff in analysis/)
- CHANGELOG.md updated with Round 16 section; ROUND16_RELEASE_REPORT.md written; archive/round16/evidence/round16_coverage_full.txt copied
- Remaining: copy docs to archive/round16/docs/, tar.gz + SHA256SUMS, git add/commit everything, deliver final message
