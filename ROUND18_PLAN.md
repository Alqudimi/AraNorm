# Round 18 — Execution Plan (Internal Working Document)

Goal: genuine new capability expansion (features, not only tests), in line with roadmap items v1.3/v1.4, enterprise-grade, no rewrite, clean code, full test coverage.

## Gap analysis → selected feature set

1. **`EntityAnalyzer` (rule-based NER) — NEW `src/aranorm/analysis/entity_analyzer.py`**
   Roadmap v1.3 lists NamedEntityExtractor. Extract person/location/org markers (الأسماء، المدن، الدول، المنظمات) with regex + dictionary + context, returning EntityAnalyzerResult with typed spans. Integrates with TextAnalyzer-style API. CLI: `aranorm entities`.
2. **`TopicClassifier` (TF-IDF-like bag-of-features Arabic topic classification) — NEW `src/aranorm/analysis/topic_classifier.py`**
   Roadmap v1.3 lists TopicClassifier. Lexicon+feature-based classifier (news, social, legal, medical, religious, sport, tech, general) — deterministic, no external model. CLI: `aranorm topics`.
3. **`PronounResolver` — NEW `src/aranorm/analysis/pronoun_analyzer.py`**
   Arabic pronoun/person suffix analysis: decompose attached pronouns (ـه، ـها، ـنا، ـك، ـكم) and clitics from tokens; useful for downstream NLP. Adds clitic segmentation utility used by existing processors.
4. **`ArabicIdiomDetector` — NEW `src/aranorm/analysis/idiom_analyzer.py`**
   Detects common Arabic idioms/fixed expressions in normalized text with span info — differentiates from spelling errors (idiom words are NOT spelling errors). Integrates with SpellingReport to suppress false positives.
5. **`PipelineSnapshot` — NEW `src/aranorm/core/snapshot.py`**
   Roadmap v2.0 pipeline serialization: save/load configured pipeline state (config + version + stage order) as JSON; deterministic round-trip tests. No code rewrite — additive serializer over PipelineConfig.
6. **`BatchExporter` parquet-free `to_excel`? — skip (xlsx needs dep). Instead: `ExportProfile` presets** — small.
7. **CLI: `entities`, `topics`, `snapshot` commands**; snapshot save/load integrated.
8. Version bump 1.8.0 → 1.9.0; CHANGELOG entry; new release report.

## Execution order
- WP1: entity_analyzer + topic_classifier (core new features) + tests
- WP2: pronoun_analyzer + idiom_analyzer + snapshot + tests
- WP3: CLI integration + existing-tests updates (idioms integration w/ spelling) + full regression
- WP4: verify (black/flake8/mypy/pytest/coverage), docs (CHANGELOG), report

## Test budget: ~90+ new tests across 3-4 new test files.
