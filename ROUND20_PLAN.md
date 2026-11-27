# Round 20 — Analysis Depth Expansion & Cross-Module Intelligence

Version target: 1.11.0. Baseline (R19): 1.10.0, 1879 tests pass, stmt 99%, branch 96.88%.

## Gap analysis

The project now has mature single-axis analyzers (sentiment polarity, spelling, quality,
coherence, readability, topics, entities, idioms, pronouns, word-frequency, summarization,
similarity, corpus overlap) but lacks **integrated multi-analyzer intelligence** and a few
independent analytical dimensions:

1. **Style/Formality (WP1, NEW)** — register/register analysis: formal vs informal Arabic
   signals (MSA markers vs dialectal/colloquial markers, emoji density, elongation,
   internet slang). New module `src/aranorm/analysis/style_analyzer.py`.
2. **Text Profiler / Composite Report (WP2, NEW)** — single-pass orchestrator
   `AnalysisProfiler` producing one consolidated report merging sentiment, coherence,
   quality, readability, word-frequency, topics in a unified payload with cross-signal
   notes (e.g., "coherent but negative tone"). New module `src/aranorm/analysis/profiler.py`.
3. **Emotion detection (WP3, NEW)** — extend sentiment beyond polarity to Plutchik-style
   emotion buckets (فرح، حزن، غضب، خوف، مفاجأة، اشمئزاز، ثقة، توقع) via an emotion lexicon
   seeded from existing polarity lexicon categories. New module
   `src/aranorm/analysis/emotion_analyzer.py`.
4. **Spelling quality integration (WP4, expand)** — quality_score.py (95.2% branch) gains a
   spelling-severity weight from SpellingAnalyzer and tests close remaining branches in
   quality_score + batch_analysis + language_detector.
5. **CLI (WP5)** — new commands: `style`, `emotions`, `profile`. All three handlers follow
   the `_cmd_*` pattern with positional text / --file / --json.
6. **Exports (WP6)** — all new classes in `src/aranorm/analysis/__init__.py`, version bump
   to 1.11.0, CHANGELOG entry, test_installed_smoke updated.

## Test plan

- tests/test_round20_features.py (~120 tests) direct imports for WP1-4.
- tests/test_cli_handlers_r20.py (10+ tests) direct CLI handler imports.
- Close missing branches: quality_score (6), batch_analysis (5), language_detector (4),
  idiom_analyzer (3), word_frequency (3), coherence_score (3), pronoun (2),
  fuzzy_matcher (2).
- Targets: >=95% branch (project baseline 96.88% must not regress), mypy/lint/black clean,
  no rewriting existing code.

## Execution order

1. Style analyzer module + tests (WP1).
2. Emotion analyzer module + tests (WP3).
3. Composite profiler module + tests (WP2).
4. Quality spelling integration + branch-closing tests (WP4).
5. CLI commands + handler tests (WP5).
6. Exports/version/CHANGELOG (WP6).
7. Full verify: pytest, lint, type-check, coverage >= 95% branch.
8. ROUND20_RELEASE_REPORT.md + AraNorm_Round20_Release.tar.gz.
