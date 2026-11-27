# Round 16 Roadmap — Full-Spectrum Hardening & Analytical Expansion

**AraNorm — 18 August 2026**

Round 16 builds on Round 15's 95.08% branch coverage baseline. The round closes the two largest remaining coverage gaps — the CLI (82.13%) and the optional-dependency integration layer (models at 0%, integrations at 29–89%) — and ships two analytical features (`TextSimilarityMatrix` and `TextDiffReport` with `process_with_diff`).

## Objectives and Acceptance Criteria

| Objective | Target | Acceptance |
|-----------|--------|------------|
| CLI coverage | 82.13% → ≥ 95% | branch coverage on `cli.py` ≥ 95%, ~15 new tests |
| Optional-integration layer | 0–69% → ≥ 85% | fake-import harness (`sys.modules`) tests for models, HuggingFace, pandas, NLTK, spaCy |
| Residual core gaps | 72 partials → ≤ 30 | targeted tests in config, spec, contracts, runtime, exporters, progress, normalizer, language_detector, fuzzy, pipeline |
| New features | 2 | `TextSimilarityMatrix` (fuzzy), `TextDiffReport` + `process_with_diff` (pipeline) — each with full doctest-style tests |
| Quality gate | `make verify` | 100% pass, black/flake8/mypy clean, black `--line-length=120` |
| Overall coverage | 95.08% → ≥ 96% | `coverage branch=True`, TOTAL row ≥ 96.00% |

## Work Packages

### WP1 — CLI harness (P0)
New file `tests/test_coverage_round16_cli.py`: command-subcommand combinations for the untested output paths (compare preview, text analysis print, sentiment report, corpus analysis summary, spec validation branch, serve streaming flag, `__main__` entry, stdin/no-file error paths, retry failure prints).

### WP2 — Optional-integration harness (P0)
New file `tests/test_coverage_round16_integrations.py`: `TransformersSeq2SeqModel` lazy load/predict/predict_batch/unload with a fake `transformers` in `sys.modules`; `HuggingFaceNormalizer` init default pipeline, `normalize_dataset` (Dataset + DatasetDict), `expand_dataset`; `PandasNormalizer.normalize_column/dataframe/apply_stop_words` with a fake `pandas`; `NLTKStopWordsAdapter` full paths (to_frozenset, filter_tokens, merge, register); `SpacyStopWordsAdapter.enrich_spacy`.

### WP3 — Residual core gaps (P1)
New file `tests/test_coverage_round16_residuals.py`: `PipelineConfig.merge` preset override + dialect_target + stop_words_config + resource_limits; `PipelineSpec` metadata non-dict + write OSError chain; `ResourceLimits` n_workers < 1; `runtime._safe_error` PermissionError path; `BatchExporter.to_dataframe` ImportError; `TqdmProgressCallback` ImportError; `OrthographicNormalizer` disabled flags (stmts 47, 61); `language_detector` fallbacks; `fuzzy.add_many` loopback + dead-guard pragmas only if unreachable.

### WP4 — Features (P2)
`src/aranorm/utils/fuzzy_matcher.py`: `TextSimilarityMatrix` — pairwise n-gram Jaccard similarity over a corpus with canonicalization, top-k neighbor retrieval, and threshold filtering.
`src/aranorm/core/pipeline.py`: `TextDiffReport` dataclass (word-level insertions/deletions/unchanged counts, changed positions) + `ArabicNormalizationPipeline.process_with_diff(text)` convenience method.

### WP5 — Verification & archive (P3)
`make verify` → green; coverage ≥ 96%; CHANGELOG + RELEASE_REPORT + GAP_ANALYSIS copy; `archive/round16/` with SHA256SUMS and tar.gz.

## Risk Notes
The optional-integration tests must never trigger real downloads; all adapters load lazily and the harness uses `monkeypatch.setitem(sys.modules, ...)` exactly as Round 10's `test_dialect_norm_contracts.py` does. The CLI tests run the real `main()` with isolated `tmp_path` and fake stdin, consistent with the existing `test_cli*.py` suite.
