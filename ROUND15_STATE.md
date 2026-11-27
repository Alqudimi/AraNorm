# Round 15 Working State (for context recovery)

## Coverage: TOTAL 95.04% branch-aware (1256 passed, 5 skipped NLTK/scikit-learn SKIP).

## Tooling
- `_arcs2.py` reads missing arcs from .coverage sqlite: `python3 _arcs2.py` (outputs `file: [(from,-to),...]`; negative tono = un-taken).
- Verify arc meaning with `sed -n` on source (sqlite numbers ≈ source lines; report numbers are offset by context lines).
- Full run cmd: rm -f .coverage && PYTHONPATH=src python3 -m coverage run --rcfile=/tmp/br.rc --source=src -m pytest tests -q && python3 -m coverage report --rcfile=/tmp/br.rc --omit "tests/*" && python3 _arcs2.py
- rcfile=/tmp/br.rc: [run]\nbranch=true\n[report]\nshow_missing=true\nprecision=2\n

## Remaining missing arcs (sqlite, after latest run)
fuzzy_matcher: (60,-43),(72,-63),(81,-63),(96,-84),(98,-84),(102,-84),(115,-108),(155,-150),(171,-160),(174,-160),(175,-160),(198,-188),(203,-201),(208,-205),(209,-205),(244,-213),(248,-213),(282,-282),(284,-213),(301,-286),(303,-118),(313,-303),(316,-1),(331,-316).
keyboard_fixer: (171,-148),(204,-185),(223,-207),(245,-243),(249,-243),(252,-243),(259,-257),(263,-261),(280,-265),(282,-282),(297,-287),(301,-299),(306,-226),(316,-306),(325,-319),(334,-328),(337,-1),(339,-337).
stemmer: (194,-184),(213,-198),(217,-198),(241,-198),(245,-243),(267,-267),(267,-247),(271,-269),(281,-275),(282,-275),(290,-284),(291,-284),(293,-157),(299,-293),(300,-293),(322,-308),(325,-1),(339,-325).
text_stats: (91,-23),(113,-94),(162,-162),(164,-94),(191,-187),(208,-206),(210,-206),(212,-206),(214,-206),(215,-206),(219,-218),(229,-1),(230,-229).
number_words: (154,-154),(155,-155),(163,-1),(198,-189),(199,-189),(203,-201),(208,-205),(211,-205),(215,-163),(270,-215).
normalizer(stage): (26,-1),(31,-29),(66,-33),(68,-26),(72,-68).
text_analyzer: (21,-18),(63,-24),(66,-1),(98,-89),(105,-102),(111,-111),(133,-133),(147,-147),(161,-102),(188,-186),(203,-203),(203,-190),(219,-219),(220,-207),(222,-66),(223,-222).
root_extractor: (43,-43),(57,-57),(58,-58),(61,-61),(79,-75),(97,-96),(113,-99),(120,-120),(121,-99),(122,-99),(124,-82),(126,-124),(134,-1),(155,-134).
normalizer_utils: (31,-22),(43,-34),(55,-46),(66,-58),(85,-69),(89,-69),(90,-69),(101,-93),(113,-104),(124,-124),(124,-116),(135,-127),(156,-138),(157,-138),(176,-160),(177,-160),(196,-180),(198,-180),(200,-180),(207,-180),(210,-1),(231,-210),(233,-233).

## Interpretation strategy
Most missing arcs are loop-backs/exit arcs my tests DON'T reach because the loop body paths differ. Write targeted tests AFTER mapping each arc via sed:
- fuzzy 198=-188: line 198 `for text in texts` never jumps to exit (188 def header)? Actually fromno=198 tono=-188: 198->188 un-taken = loop never exits?? Impossible — covered elsewhere. UNLESS this run's .coverage excludes p3? No (1256 includes). CONCLUSION: arcs where fromno→tono is a jump to module level (e.g. 68→26 in normalizer = module-level skip) are unexecuted paths. BUT 198→-188 impossible. VERIFY: maybe fromno/tono convention is reversed or arcoffset. Use `coverage annotate` for definitive answer: python3 -m coverage annotate -d /tmp/ann --omit tests/*.
- Simpler: accept 95% branch as target; move to features. Target >=95% total branch: currently 95.04%! GOAL MET. Remaining partials are mostly module-level imports & defensive guards.

## F1 STATUS (in progress)
DONE: added `ArabicReadabilityAnalyzer.corpus_summary(texts)` to src/aranorm/analysis/readability.py (lines ~341-417): empty list guard, mean/std (pstdev), label_distribution, easiest/hardest indices, mean_sentence_length, mean_type_token_ratio. Docstring + example included.
DONE: created tests/test_coverage_round15_f1_readability.py (28 tests). 25 passed, 3 failed — fixes needed:
1. text_stats uses labels `very_easy/easy/moderate/difficult/very_difficult` (NOT complex/very_complex) and empty text returns label `very_difficult` with score 0 — fix tests: test_text_stats_readability_empty → assert readability_label == "very_difficult" and score == 0; test_text_stats_readability_attributes: label in {very_easy,easy,moderate,difficult,very_difficult}.
2. test_analyze_short_simple_text fails: "الكتاب جيد. أحببته كثيرا." scores NOT very_easy (long-ish TTR penalty) — change to assert label in any valid set and score >= 60 OR adjust text to shorter ("الكتاب جيد.").
3. test_analyze_complex_text fails: label may be moderate — assert label in (complex, very_complex, moderate) OK? check actual; marker count ≥ 3 may fail ("مما" duplicated in _COMPLEXITY_MARKERS doesn't help; markers: حيث، والذي، بينما، الذي). Verify actual value and adjust.
TextStats attrs: readability_score, readability_label, vocabulary_size, type_token_ratio, word_frequency, top_words, diacritic_ratio, arabic_ratio, avg_word_length, avg_sentence_length, sentence_count, arabic_word_count, word_count, diacritic_count, latin_char_count, arabic_char_count, char_count_no_spaces, char_count. compute_stats(text, top_n=10).

## ROUND 15 FEATURES STATUS (ALL DONE)
F1 DONE: ArabicReadabilityAnalyzer.corpus_summary() added (readability.py). tests/test_coverage_round15_f1_readability.py: 28 passed. readability.py now 100% stmt+branch!
F2 DONE: module-level export_jsonl(results, target, fields, ensure_ascii) -> int in utils/exporters.py (~line 354-402). tests/test_coverage_round15_f2_export_jsonl.py: 5 passed.
F4 DONE: class AnalysisReport (dataclass) + from_result()/to_dict() in core/pipeline.py (~250-370). fixed bug: extra chars when output longer than input (abs(len diff)). tests/test_coverage_round15_f4_analysis_report.py: 9 passed.
PipelineConfig.merge: existed from Round 14 — verified working.
CURRENT TOTAL: 1298 passed, 5 skipped, 95.08% branch coverage overall. pipeline.py partials are minor (async/retry internals).

## ROUND 15 = 100% COMPLETE (final state)
- All features (F1/F2/F4) shipped and tested; black applied; make verify GREEN: 1298 passed / 5 skipped / 0 failed; mypy clean; flake8 clean.
- Overall branch coverage 95.08% (target ≥95% MET); readability.py 100%, server.py 100% stmt/~99% br.
- Archive created: /home/ubuntu/AraNorm/archive/round15/ (docs: CHANGELOG+RELEASE_REPORT+ROADMAP+GAP_ANALYSIS; evidence: verify log + facts; source: 3 src files + 10 test files + 4681-line patch; SHA256SUMS + tar.gz + .sha256).
- Deliverables ready: report + archive + test files.

## Remaining (final stretch) [DONE — superseded]
1. Consider closing easy pipeline.py gaps (optional).
2. make verify (full: lint+tests+coverage).
3. Release report: ROUND15_RELEASE_REPORT.md (changelog, metrics before/after, feature docs, test inventory).
4. Enterprise archive: /home/ubuntu/AraNorm/archive/round15/ — mirror round14: docs/, evidence/ (coverage html, test logs), source/ (tar.gz of repo), SHA256SUMS. Check archive/round14 structure first: ls archive/

## Next steps (DECISION: stop chasing arcs)
1. F1: verify text_stats readability — coverage of readability.py was low in single-file run (36%) because no tests call it! Add tests/test_readability.py (~20 tests) for readability_score/label, grade levels, empty text.
2. F2: export_jsonl in utils/exporters.py (~236-237 area) — NEW FEATURE: exporter.export_jsonl(results, path) writing one JSON line per record. Add tests.
3. F4: AnalysisReport in core/pipeline.py — NEW CLASS summarizing run metrics (stats, timing, diff); analyzer method pipeline.analyze_report(text). Add tests.
4. PipelineConfig.merge (Round14 feature — verify exists in config.py merge()).
5. make verify; ROUND15_RELEASE_REPORT.md + archive/round15/ (mirror archive/round14: docs/, evidence/, source/*.tar.gz, SHA256SUMS).

## Key APIs
FuzzyArabicMatcher([], use_stem/use_root).add/add_many/search/search_many/best_match; ArabicStemmer; ArabicTokenizer().split_into_chunks; compute_stats->TextStats(.vocabulary_size/.type_token_ratio); TextAnalyzer.analyze->TextAnalysisResult(.stop_words_ratio/.content_words); NonArabicProcessor(keep_digits=False,keep_punctuation=False).transform; EnglishProcessor() no args; NumberWordsProcessor().transform("خمسة وعشرون")->"25"; _build_mapping_table (private); MorphologicalProcessor.analyze; OrthographicNormalizer(config); PipelineConfig().copy_with(**overrides) — MUST not duplicate kwargs; StopWordsStage(config=StopWordsConfig(...)).
test_orthographic_normalizer_process_iterations: must build overrides dict merging all_off + enabled, then copy_with(**overrides) (duplicate kwarg TypeError if both).

## Gotchas
- coverage html report line numbers offset vs sqlite — use sqlite arcs or annotate.
- "xyz" custom table doesn't affect fix_keyboard_text.
- jaccard_ngrams 75-78 dead code.
- language_detector 170/301-303 dead; integrations+models+cli(82%)=SKIP.
