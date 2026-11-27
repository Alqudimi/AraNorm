# Round 16 Gap Analysis — measured 2026-08-18 with `coverage run --branch` (1,298 passed)

## Coverage table (worst files first)

| File | Stmts | Miss | Br | Par | Cover | Missing |
|------|------:|-----:|---:|----:|------:|---------|
| models/_transformers_model.py | 46 | 31 | 8 | 0 | 29.09% | 47-53, 79-97, 124-136, 148-155 (wrong file — see integrations) |
| models/coda_model.py | 10 | 10 | 0 | 0 | 0.00% | 18-66 |
| models/dialect_id_model.py | 20 | 20 | 4 | 0 | 0.00% | 3-31 |
| models/msa_model.py | 10 | 10 | 0 | 0 | 0.00% | 15-61 |
| models/__init__.py | 4 | 4 | 0 | 0 | 0.00% | 3-7 |
| integrations/huggingface_integration.py | 47 | 31 | 8 | 0 | 29.09% | 47-53, 79-97, 124-136, 148-155 |
| integrations/nltk_stopwords.py | 29 | 9 | 0 | 0 | 68.97% | 75, 136-143, 182-183 |
| integrations/spacy_stopwords.py | 24 | 10 | 4 | 0 | 50.00% | 57-67 |
| integrations/pandas_integration.py | 47 | 5 | 6 | 1 | 88.68% | 52->56, 155-160 |
| cli.py | 639 | 96 | 178 | 34 | 82.13% | 92, 98, 117-121, 134, 153, 156-160, 228->232, 269-271, 287, 292, 308-312, 326-333, 352, 357, 366-367, 373, 389, 394, 402-412, 469->473, 498-502, 520, 522-523, 571-574, 596-598, 610-613, 618-622, 680, 692, 694-698, 714-715, 735-743, 781-783, 786-787, 851, 885, 889, 1270-1271, 1283 |
| core/config.py | 238 | 6 | 88 | 4 | 95.71% | 155->exit, 314-319, 329->328, 335->334 |
| core/pipeline.py | 576 | 8 | 254 | 13 | 97.47% | 541->548, 644, 804, 809->816, 816->833, 1067, 1080, 1092, 1190, 1192->1199, 1199->1214, 1216, 1365 |
| core/spec.py | 155 | 1 | 48 | 2 | 98.52% | 111, 245->250 |
| core/contracts.py | 71 | 1 | 18 | 1 | 97.75% | 123 |
| core/runtime.py | 140 | 1 | 6 | 1 | 98.63% | 81 |
| utils/language_detector.py | 94 | 4 | 30 | 2 | 93.55% | 170, 301-303 |
| stages/normalizer.py | 46 | 2 | 32 | 2 | 94.87% | 47, 61 |
| utils/fuzzy_matcher.py | 123 | 2 | 50 | 3 | 97.11% | 76, 78, 181->183 |
| utils/exporters.py | 118 | 2 | 30 | 0 | 98.65% | 236-237 |
| utils/progress.py | 72 | 2 | 8 | 0 | 97.50% | 166-167 |
| analysis/text_analyzer.py | 97 | 0 | 16 | 2 | 98.23% | 125->124, 130->129 |
| utils/stemmer.py | 65 | 0 | 30 | 1 | 98.95% | 280->282 |
| utils/root_extractor.py | 32 | 0 | 8 | 1 | 97.50% | 120->115 |
| utils/text_stats.py | 84 | 0 | 14 | 1 | 98.98% | 143->142 |
| utils/keyboard_fixer.py | 79 | 0 | 22 | 1 | 99.01% | 165->162 |
| stages/dialect_norm.py | 80 | 0 | 20 | 1 | 99.00% | 184->186 |
| processors/number_words_processor.py | 65 | 0 | 22 | 1 | 98.85% | 234->239 |
| **TOTAL** | 6179 | 270 | 1796 | 72 | **95.08%** | |

## Interpretation and effort sizing

The project body (core, processors, stages, utils) is already near-complete: 40+ files at 97–100% with only isolated loopback or defensive-guard arcs. The three genuinely uncovered surfaces are **cli.py** (96 missed statements, mostly print/output branches of subcommands that were never invoked in tests), the **models/** package (entire lazy-transformers adapter, 0%), and the **integrations/** package (HuggingFace `datasets` paths, pandas `apply_stop_words`, NLTK/spaCy convenience methods).

| Gap surface | Missing statements | Effort | Approach |
|---|---:|---|---|
| CLI output/error branches | 96 | 3–4 h | real `main()` harness, fake stdin, tmp_path outputs |
| models lazy adapter | 90 | 1–2 h | `sys.modules` fake-transformers (existing pattern in `test_dialect_norm_contracts.py`) |
| integrations | 55 | 2–3 h | same fake-import pattern for `datasets`/`pandas`/`nltk`/`spacy` |
| config merge overrides | 6 | 0.5 h | `merge()` with preset/dialect/stop_words/resource_limits kwargs |
| spec/contracts/runtime/exporters/progress small gaps | 7 | 0.5 h | targeted negative-path tests |
| normalizer disabled flags | 2 | 0.25 h | `copy_with` all-off |
| language_detector fallbacks | 4 | 0.5 h | edge inputs |
| fuzzy loopback/dead guards | 2 + 3 par | 0.5 h | multi-element `add_many`; pragmas for unreachable guards |
| pipeline retry/stop_words/long-text arcs | 8 + 13 par | 1 h | stop_words-enabled run, retry collect-policy failure, long-text chunking branches |

Expected post-round coverage: CLI ≥ 95%, integrations ≥ 85%, overall ≥ 96% branch.
