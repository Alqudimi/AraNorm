# ROUND 17 API FACTS (discovered during WP1 test writing)

## Correct coverage measurement
`python3 -m pytest tests --cov=src/aranorm --cov-report=term-missing --cov-branch`
(pyproject.toml source=src/aranorm, omit models/integrations). NEVER use `--rcfile=/dev/null`.

## NormalizationResult (core/pipeline.py, dataclass)
Fields: original_text, normalized_text, dialect=None, dialect_confidence=None,
coda_text=None, msa_text=None, processing_metadata (dict), applied_steps (list),
processing_time_ms=None, stop_words_removed/found/stats/by_category/by_dialect/
applied_stop_words_steps (all Optional), steps_trace (Optional List[Tuple[str,str]]).
Props: dialect_label, confidence_score, is_msa (bool only if dialect=="MSA", else None).

## CancellationToken (core/contracts.py)
cancel(); is_cancelled property; raise_if_cancelled raises ProcessingCancelledError.

## PipelineBuilder (pipeline.py 1323)
builder() classmethod; add_cleaner(**bool), add_normalizer(**bool) via
_resolve_boolean_options (cleaner op: remove_non_arabic/remove_english literal;
prefix remove_ -> clean_X; else clean_X). Line 1365 TypeError = target field not bool.
add_dialect_processor(identify, normalize_to, supported_dialects), add_stop_words(mode,scope), build().

## StreamingSession (core/streaming.py)
class StreamingSession(pipeline, source_path, output_path, checkpoint_path, ...)
_method: _assert_source_unchanged(self, fingerprint, signature) where
signature = Tuple[int,int,int,int] = _file_signature(path).
StreamingSessionReport dataclass has cancelled=False field.
fingerprint_file(path) exported.

## language_detector._classify(self, arabic_ratio, latin_ratio, arabizi_score, text)
returns (label, confidence). Note: takes text arg.

## jaccard_ngrams(a, b, n=2) in utils/fuzzy_matcher.py (NOT jaccard_ngram!)

## keyboard_fixer: class ArabicKeyboardFixer(); methods: fix_text (returns KeyboardFixerReport),
fix_arabic_layout_text. No build_keyboard_fixer. FixerReport at line 187.

## NumberWordsProcessor(Processor): name="number_words", process(text) (TextProcessor contract),
replace_ordinals=True default, min_word_length. Example: "لدي ثلاثة كتب وعشرون قلماً" -> 'لدي 3 كتب 20 قلماً'.
Compound و- logic: suffix stripped of ".,،؟!؛:" then looked in _lookup; tok + suffix combined.
L234->239 = fallback when suffix not in lookup (continue without combining?). Need exact check.

## root_extractor: extract_root(word) module func; ArabicRootExtractor.extract(word).

## text_analyzer: class TextAnalyzer(config=None, registry=None, top_n=10).analyze(text) -> TextAnalysisResult
(fields: content_words, stop_words_ratio, ...). TextAnalysisResult at line 25, top_n default 10.
Report fields at text_analyzer.py 25-64 (stop_words_ratio, content_words, etc.)

## text_stats: class TextStats(dataclass) at line 24; compute_stats(text, top_n=10) -> TextStats;
compare_stats(text_a, text_b) -> Dict. vocabulary_size is in TextStats.

## stemmer: ArabicStemmer class, stem() method. L280-282: definite article + remainder < min -> return word.

## DialectNormalizerStage (stages/dialect_norm.py): __init__ has self.device=device (166),
load() lazily inits _tokenizer/_model (L182-186) with self._model.to(self.device) when device set.
Fake transformers pattern works (see ROUND16 notes for _make_fake_hf).

## registry: discover_report(group, strict=False) -> PluginDiscoveryReport(group, discovered, failures(ok=not failures)).
PluginDiscoveryFailure(name, group, error_type, message).

## Pipeline hooks: pipeline constructor (config, cleaner?, normalizer?, ..., hooks=None).
hooks=PipelineHooks(before_process=None, after_process=fn, on_error=None).

## pipeline.process_batch_with_retry(values, policy=BatchRetryPolicy(max_retries=1)) -> BatchRetryReport(results, failed_indices, retry_report dict).
process_batch_async(values, policy=BatchProcessingPolicy(mode=...), cancellation_token, on_error).

## CLI facts
main(argv) -> rc. commands incl: info, normalize, stopwords, analyze, dialect, keywords,
compare, tokenize, sentiment, version, describe, plugins, readability, summarize, detect,
batch, corpus, serve, stream, spec. _handlers dict at cli ~1250+.
spec: `spec` alone via argparse required subparser -> SystemExit(2); _cmd_spec(ns with subcommand=None) -> prints error rc=2 (L786-787).
unknown handler None -> print_help rc=1 (L1270-1271).
sentiment --file nonexistent -> rc 1. normalize/tokenize/detect same pattern (FileNotFoundError -> rc 1).
CLI progress: batch --progress uses TqdmProgressCallback (ImportError fallback ConsoleProgressCallback, L610-613).
batch --skip-errors installs on_error warning callback (L618-622).
batch retry failures: _cmd_batch prints "Error: N item(s) failed after retries." rc=2 (L156-160; also L694-698 in another handler - check which).
stream --status checkpoint.json prints "Cancelled  : yes" if report.cancelled (L851).
dialect non-json: "Dialect    : X / Confidence : X% / Is MSA     : Yes|No" (L269-271).
plugins text mode: "Plugin group :", "Status       : ok|degraded", "Failures:" rows (L469-473).

## Residual gaps to close (44 partial branches)
cli.py 13 partial; pipeline.py 12; normalizer.py 2; language_detector 2; fuzzy_matcher 3;
streaming 1; number_words 1; text_analyzer/stemmer/root_extractor/text_stats/keyboard/dialect_norm 1 each.
Details in ROUND17_GAP_ANALYSIS.md.

## WP2 planned features
F1 SpellingReport (analysis/spelling_report.py) + pipeline.process_with_spelling(text)
F2 TextQualityScore (analysis/text_quality.py) composite 0-100 with factors + label
F3 BatchAnalysisReport + pipeline.process_batch_with_report(values)

## WP2 API hooks
- SpellingProcessor exists at processors/spelling_processor.py (transform(text)), _WORD_CORRECTIONS,
  _COMPILED patterns, get_correction_count().
- TextDiffReport style: analysis/text_diff_report.py, pipeline.process_with_diff(text) pattern to mirror.
- AnalysisReport exists (pipeline.py 251) with from_result.
- BatchRetryReport (pipeline ~700+).
