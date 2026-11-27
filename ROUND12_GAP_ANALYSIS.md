# Round 12 Gap Analysis

## Baseline (verified)

| Metric | Value |
|---|---|
| Commit | 76fbe49 (professional-hardening) |
| Tests | 878 passed، 5 skipped |
| Coverage | 94% of 5,574 statements |
| Makefile verify | passes |

## Lowest-coverage modules (from coverage report)

| Module | Coverage | Missed lines (summary) |
|---|---|---|
| core/base.py | 74% | 77-79, 91, 103, 116-120 (ProcessorContext.record_always/set/get/merge traces) |
| analysis/readability.py | 85% | 247, 258, 339, 355-358, 365, 368-372, 375 |
| cli.py | 85% | many branch lines across subcommands |
| stages/dialect_id.py | 86% | 304-316 (CAMeL unavailable/failure path) |
| analysis/keyword_extractor.py | 87% | 114, 117-118, 161-167 |
| processors/_base.py | 88% | 32, 37 (Processor base error paths) |
| core/config.py | 90% | 134, 139, 281, 288, 436-440, 470-475, 507, 511-516 |
| core/pipeline.py | 90% | scattered branch lines incl. 229-246, 614-616, 737-739 |
| core/registry.py | 92% | 146, 168-170, 207-208, 264-265, 281, 293, 305, 309 |
| server.py | 93% | 46-47, 50, 86-93, 149, 151, 198, 279, 307, 312, 366, 380 |
| utils/stemmer.py | 94% | 213, 221, 245, 290 |
| utils/language_detector.py | 94% | 170, 287, 298, 301-303 |
| core/stop_words_registry.py | 94% | 84, 188, 222, 256, 263, 293-297, 301 |
| analysis/text_analyzer.py | 95% | 156, 188, 192-203 |
| core/metrics.py | 95% | 81, 98-99, 154, 158 |

## Deterministic closeable gaps (testable without new dependencies)

1. **core/base.py** — ProcessorContext tracing API (record_always with trace, merge with/without trace, set/get defaults): pure unit tests.
2. **processors/_base.py** — Processor base validation error paths.
3. **stages/dialect_id.py** — heuristics branch fully; ImportError path via mocked import guard, failure path via mocked CamelDI.predict raising.
4. **registry.py** — empty name, non-subclass, ProcessorFactory kwargs, iteration/contains/iter semantics.
5. **config.py** — preset LIGHT override, invalid resource_limits type, from_dict unknown fields, emit_steps_trace typed checks.
6. **server.py** — error handler branches for malformed requests outside streaming; verify which lines are reachable testably.
7. **analysis/readability.py / keyword_extractor.py / text_analyzer.py / metrics.py** — boundary numeric cases (empty tokens, all-stopwords text, long single word).
8. **utils/stemmer.py / language_detector.py** — boundary language scoring cases.
9. **cli.py** — error path branches already partially covered; focus on highest-density missed blocks.
10. **stop_words_registry.py** — missing dialect key, invalid config shapes.

## Non-goals for round 12

No pipeline engine rewrite, no new mandatory dependency, no change to official version (1.8.0), no spec format change, no network-based tests in CI path.

## Decision

Focus round 12 on closing deterministic coverage gaps with behavior-verifying tests, plus strengthening the highest-value unit (pipeline.py config/async branches) — a "coverage hardening" round that raises verified correctness rather than adding surface area.
