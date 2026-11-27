# ROUND 17 WP1 — test fix notes (round 2 diagnostics)

22 passing, 12 failing. Fixes per failure:

1. test_cli_detect_file_not_found_missing_branch: detect --file does NOT have its own
   FileNotFoundError branch (389 is sentiment handler). REMOVE this test OR retarget.
   Gap L389 maps to sentiment handler per file: sed 380-393 shows _cmd_sentiment.
   => test_cli_sentiment_file_not_found (rename from previous attempt; file-not-found for sentiment).

2. test_cli_dialect_text_output: input returns MSA/Yes. Use dialect text clearly non-MSA:
   "واش كتقول شنو" (Moroccan) or adjust assertion to check either Yes/No format exists
   and verify is_msa flag branch by checking format + is_msa property.
   Actually branch L268-271 = is_msa print ("Yes" if is_msa else "No") — both sub-branches
   partial. Use clearly-dialect text: "واش كتب محمد شنو" -> Moroccan.

3. test_cli_batch_skip_errors_callback: prints to stderr via _skip_error; BUT the mocked
   process_batch_retry returns report with failed_indices=[] so on_error never called.
   Need real failure: mock process_batch_retry to call on_error... Simpler: use process_batch
   directly? CLI uses process_batch_retry. Instead: skip mock; make pipeline process raise
   for second item: mock ArabicNormalizationPipeline.process to raise on index 1.
   But CLI constructs pipeline fresh each time. => patch process returning NormalizationResult
   for text1, raising RuntimeError for text2, and process_batch_retry default implementation
   collects via collect policy -> failed_indices=[1] -> prints summary rc=2. For skip errors
   we need on_error fired. Better: patch process with side_effect raising for text2; then
   on_error is called with the exc; assert "Warning: skipped item" in err; rc should be 0
   (failed item replaced by None).

4. test_cli_stream_cancelled_print: rc=1 (assert 1==0): checkpoint load works but
   StreamCheckpoint __post_init__ validates paths (source must exist?) — likely
   source_path doesn't exist -> ValueError. => also create source file and output file,
   or use tmp paths that exist. Actually _validate_path may require existing dir. Create
   tmp_path/src.txt too.

5. test_cli_unknown_command_prints_help: module attribute is "_handlers"? grep showed
   "_handlers = {" at cli 1245, but maybe local to main()? 1268 `handler = _handlers.get(...)`
   inside main scope? => find where _handlers defined (inside main? inside _build_parser?).
   If inside main(), patch via `aranorm.cli.main` redefining — instead test via SystemExit
   for invalid command. If _handlers is nested, retarget test: use unknown command via
   argparse invalid choice -> SystemExit 2 (already covered?). Find exact location.

6. test_pipeline_hooks_after_process_merged: (2 == 1) -> hooks.after_process called twice:
   per-chunk + merged. Adjust: assert len(seen) == 2 (chunk result + merged).

7. test_pipeline_collect_no_result_runtime_error: failed_indices=[] -> retry succeeded!
   Because real process_batch_retry default on_error=None + policy=collect re-raises?
   Need process to return None AND policy fail_fast? Actually retry loop processes failed
   items and None remains... The None item should stay failed. But we got failed_indices=[].
   => process_batch_retry retry re-runs item and our mock returns None again; but result
   filter maybe drops. Check process_batch_retry retry loop (after L804 block) to see
   how None retry result treated. Probably retry also records but filter excludes None?
   Investigate ~L820-860.

8. test_pipeline_async_on_error_inner_failure: failure variable not reassigned (line says
   fallback = on_error(...) result; if on_error raises? No — on_error returns "نص بديل",
   then run_in_executor raises primary again -> `failure = inner_exc`? Actually code shows:
   except Exception as inner_exc: failure = inner_exc. But test got primary failure.
   The executor side_effect raises RuntimeError("primary async failure") both times
   (patch on loop.run_in_executor affects retry path too!). Our mock raises same primary
   failure on retry => failure = primary again, not inner. Fix: make mock track calls; first
   call raises primary, subsequent calls raise inner? But code passes `self.process` as fn.
   Actually `await loop.run_in_executor(executor, self.process, fallback)` — mock side_effect
   raises regardless. So change: first call raises primary, second call raises inner (fallback's
   process raises inner). => track call order.

9. test_pipeline_builder_enable_option_type_error: 'must target a boolean field' regex
   didn't match — actual message? remove_non_arabic may not exist -> Unknown option first.
   Try option that exists but field is not bool: e.g. add_cleaner(preset=...) no...
   add_normalizer(remove_diacritics=1.5)? field normalize_taa_marbuta? Check _resolve_boolean_options:
   cleaner op: remove_non_arabic/remove_english literal (exist?), prefix remove_ -> clean_X;
   clean_{name} must be bool on config. Which config fields are not bool? preset.
   Try add_cleaner(preset=2)? operation cleaner, name not startswith remove_/clean_ ->
   field_name=clean_preset -> hasattr False -> Unknown cleaner option.
   Hmm need name where field exists but not bool. check config bool fields vs non-bool:
   clean_urls etc bool; normalize flags bool; dialect_target not bool but goes through
   add_dialect_processor. What about clean_stop_words? bool? Try add_cleaner(clean_urls="no")
   non-bool value -> TypeError "must be boolean" at L1347 (first check), not L1365.
   L1365 = target field not bool. Options map remove_ -> clean_X; "clean_urls" name:
   not remove_/clean_ -> field clean_clean_urls -> unknown. So use name "remove_urls":
   field_name = clean_urls which is bool -> no error. Need non-bool target field name.
   Config non-bool string fields with bool-check targetable: e.g. "remove_preset"? ->
   clean_preset unknown. Hmm. Maybe field: "dialect" -> clean_dialect unknown.
   => check config fields: find a bool-checkable non-bool field via builder ops.
   If none exists, this branch may be dead code OR reachable via add_normalizer with
   name mapping to non-bool: normalize op: name=="normalize_diacritics"->remove_diacritics (bool);
   else: if name starts clean_ -> field_name=name (clean_*) ; else raise? re-read
   _resolve_boolean_options: only cleaner has prefix mapping; normalizer op: only
   normalize_diacritics special, else field_name=name raw. So add_normalizer(preset=1.5)
   -> field_name=preset -> hasattr True -> not bool -> L1365 TypeError! Use that.

10. test_fuzzy_matcher_stem_and_root_index: _stem_index {'مدرس': ['مدرسه']} expected root
    index empty. Root extraction of 'مدرسة' -> None? Maybe root index populates differently
    or requires match. Adjust: assert _root_index is dict (exists) and contains canon if
    root known; relax to check add() path entered root branch (use word with known root
    like 'كتب' -> root كتب).

11. test_number_words_compound_waw_suffix: "عشرون وكلمة" -> '20 وكلمة'. Pass-1b treats
    'عشرون' tok in lookup + next_tok 'وكلمة' startswith و -> suffix 'كلمة' not in lookup
    -> falls to rebuilt.append(tokens_temp[i]) => '20'?? NO: rebuilt.append(tokens_temp[i])
    appends 'عشرون'?? i not in lookup branch... Wait: if branch entered and suffix not in
    lookup, execution falls through to `rebuilt.append(tokens_temp[i])` i+=1 -> original
    'عشرون'. But output was '20 وكلمة' meaning pass-1 phrase replacement? _ALL_MULTI? Or
    Pass2? Output '20' means عشرون converted. So pass-1b suffix-miss branch: 'عشرون' kept.
    Actually output '20 وكلمة' implies pass-1b DID combine? No combined->20+nothing.
    العشرون=20. '20 وكلمة' means عشرون -> 20 (by pass2? no, و word not number).
    Pass2: i=0 tok 'عشرون' in lookup, next not و. -> single-token -> 20. Good.
    'وكلمة' kept as-is. So expected '20 وكلمة' — our test assertion wrong. Fix: check
    output == '20 وكلمة' and verify suffix-miss branch: pass a known number followed by
    attached و + unknown: "عشرون وكلمة" single combined token 'وعشرون' style:
    proc.process("خمسة وعشرون") -> 25 (combined). For suffix-miss: "خمسة وغربة" -> expect
    '5 وغربة'? tok 'خمسة' in lookup, next 'وغربة' startswith و suffix 'غربة' not in lookup ->
    rebuilt.append('خمسة'), output '5 وغربة'? BUT 'خمسة' in lookup -> pass-1b keeps 5! Then
    pass2: '5' not in lookup (lookup strings), 'وغربة' ... hmm output should be '5 وغربة'.
    Use that: assert "5 وغربة" in out and 'خمسة' not in out.

12. test_dialect_norm_device_branch: DialectNormalizer.__init__(normalize_to, model_name=None?)
    grep showed `__init__` at 159 (DialectStrategy) and 221 (DialectNormalizer).
    Fix: use correct kwargs: DialectNormalizer(normalize_to="msa", device="cpu") probably.

## Verified APIs (do not re-grep)
- CLI: sentiment handler has file-not-found branch (L389), handlers dict = _handlers at 1245
  inside main() scope?; _cmd_spec args.spec_command; stream status uses StreamCheckpoint.load
  with __post_init__ validating source_path (must exist!); batch --retry uses process_batch_retry;
  skip_errors prints "Warning: skipped item {index}: {exc}" stderr.
- pipeline: process_long_text calls after_process per chunk AND merged (2 calls).
  process_batch_retry max_retries; async: loop.run_in_executor(executor, self.process, fallback);
  inner failure stored in failure variable; fail_fast re-raise when on_error is None.
- fuzzy: _stem_index Dict[str,List[str]] values=canonical strings; _root_index similar.
  root of مدرسه maybe not extracted ('مدرس' -> مدرسه stem). Word 'يكتبون' root كتب.
- DialectNormalizer(model_name or signature at 221): check kwargs before final write.

## Round 2 remaining fixes (3 failing)

13. test_cli_batch_skip_errors_callback: args.skip_errors only wired when
    args.retry is True (on_error passed only to process_batch_retry branch;
    non-retry branch passes on_error=None always per 654-663). So batch
    --skip-errors without --retry ignores callback? grep showed --skip-errors
    at 1103 under p_norm parser (normalize subcommand!) NOT batch. So
    test must use `normalize --skip-errors --file ...` and patch
    ArabicNormalizationPipeline.process to raise for a line.

14. test_cli_unknown_command_prints_help: patched parser: _build_parser returns
    parser where subparsers dest="command" already exists; adding another
    subparsers raises? SystemExit 2 -> patching failed (multiple subparsers
    on same parser = argparse error SystemExit 2). Fix: patch parser.parse_args
    to return Namespace(command="_test_unknown") directly instead of
    patching _build_parser. But main() parses and passes args.command to
    _handlers map. If we patch parse_args, the None-handler branch fires.
    rc from main when handler None: `parser.print_help()` -> rc=1.

15. test_dialect_norm_device_branch: DialectNormalizer has NO device/normalize;
    the fake-transformers device branch (L284-286) belongs to a different
    class: probably DialectStrategy subclasses? grep showed __init__ 159
    (DialectStrategy with model_name, device, max_new_tokens, load(),
    normalize()). So: import DialectStrategy from aranorm.stages.dialect_norm,
    instantiate with model_name=..., device="cpu", call load() then
    normalize("x"), assert _model.device=="cpu".

16. Confirmed CLI: batch --skip-errors + --retry combo works via process_batch_retry
    on_error param (653-655). normalize --skip-errors also exists (1103) wired to
    normalize handler process.

17. NumberWords compound test: "خمسة وغربة" -> '5 وغربة' verified (both branches ok now).

## WP1 STATE (before compaction) — tests/test_coverage_round17_gaps.py complete

- All 35 gap tests PASS when run alone. Fixed asyncio via asyncio.run +
  patching get_running_loop().run_in_executor inside coroutine (process_batch_async
  uses asyncio.get_running_loop()).
- Full-suite run previously had 2 failures (asyncio.get_event_loop removed in 3.12
  for main thread) — NOW FIXED in latest edit.
- Next: run full suite `python3 -m pytest tests --cov=src/aranorm --cov-branch` and
  measure remaining branch gaps per ROUND17_GAP_ANALYSIS.md baseline (97.42%).
- WP1 targets (from ROUND17_GAP_ANALYSIS.md): cli 95→100, pipeline 98→100,
  language_detector 94, fuzzy_matcher, streaming, number_words, normalizer flags,
  stemmer/root_extractor/keyboard/text_stats/text_analyzer/dialect_norm loopbacks.
- After WP1: WP2 features (SpellingReport/process_with_spelling, TextQualityScore,
  BatchAnalysisReport per ROUND17_ROADMAP.md), WP3 docs/verify, then archive + report.
- Base branch coverage before R17: 97.42% (ROUND16: 99% was statement-based claim;
  branch total 97.42 per analysis). Target: ≥99.5% branches.

## WP1 STATUS (2nd compaction save)

Coverage after round17_gaps suite (35 tests, all passing, full suite 1513 passed):
TOTAL stmt=99.685% branch=98.202% (branches=1780, partial=30, missing=32).
Baseline before R17: 97.42% branch.

Modules still <100% branch: text_analyzer(87.5,p2), cli(97.16,p5, missing=[92,134,156,160,352,389]),
config(96.59,p3), pipeline(95.67,p11, missing=[804,1067,1080,1092,1190,1216,1365]),
streaming(98.89,p1,322), dialect_norm(95,p1,180-184), fuzzy_matcher(94,p3,76,78),
keyboard_fixer(95.45,p1,165/245/249), language_detector(86.67,p2,170,301-303),
root_extractor(87.5,p1,120-126).

Key facts (see _r17_cli_diag.md for details):
- cli 92 = normalize handler file-not-found (no test!), 134 = stop_words_removed
  entry assembly, 156/160 = retry_report failed print/return 2, 352 = tokenize
  args.text branch, 389 = sentiment --file valid read.
- fuzzy 76/78 = jaccard_ngrams zero returns; language_detector 170 = arabizi
  threshold detection branch, 301-303 = latin classification; streaming 322 =
  fingerprint mismatch; root 120-126 = root validation loopback; keyboard 245/249
  = preserve_numbers TypeError/preserve branch; dialect_norm 180-184 = lazy
  tokenizer/model load; text_analyzer 125/130 = word-skip branches; config
  155/329/335 = SOCIAL_MEDIA preset + stop_words/limits merge branches.
- pipeline: 804 = no-result initial pass failure msg; 1067/1080/1092 = async
  cancelled/retry paths (covered async fail_fast via asyncio.run patch in gaps
  suite — verify!); 1190/1216 = async no-result + builder; 1365 = builder
  option TypeError.
- pipeline async tests now use asyncio.run + patch get_running_loop().run_in_executor.

Next: add tests to tests/test_coverage_round17_gaps.py for remaining gaps,
re-run _r17_coverage.py, target >=99.5% branch. Then WP2 (3 features), WP3
(verify+docs), archive+ROUND17 release report.
