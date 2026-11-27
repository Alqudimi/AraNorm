# Migration Guide

This guide describes how to migrate between AraNorm versions — what changed, what stays compatible, and what to adopt.

**General policy**: minor releases (1.x) are backwards-compatible. New fields on result dataclasses are additive; new methods are additive; nothing you rely on disappears without a major version.

---

## Staying current (1.9 → 1.15)

Nothing breaks across these releases — they are additive. Highlights worth adopting:

### Operational infrastructure (1.9.0)

- `PipelineSpec` — portable, fingerprinted pipeline configuration for deployment (`to_spec()` / `from_spec()`, `aranorm spec export|validate`).
- `PipelineRuntime` — atomic config reloads for long-lived services with generation tracking and health.
- HTTP server — `aranorm serve` with `/v1/normalize`, `/v1/batch`, health endpoints.
- Resumable streaming — `StreamingSession` with atomic checkpoints (`aranorm stream run|resume|status`).
- New analyzers: `EntityAnalyzer`, `TopicClassifier`, `PronounAnalyzer`, `IdiomAnalyzer`, `PipelineSnapshot`.

### Batch reliability (1.7–1.8)

- `process_batch_retry()` / `process_batch_retry_async()` — bounded per-item retries with `BatchRetryReport`.
- `BatchProcessingError.results` — successful partial results are preserved on failure.
- `emit_steps_trace=True` — per-text `(processor, action)` audit trail.

### Analysis expansion (1.10–1.15)

- 20+ new analyzers: coherence, style, emotions, word frequency, rhythm, figurative rhetoric, quotations, loanwords, roots, contrast, fillers, complexity, rhetorical questions, anaphora, wordplay.
- `AnalysisProfiler` grew from 8 → **22 axes** — check any `axes=` selections you pass to `textprofile`.
- `TextQualityScore` gained components (now 8) — component weights were rebalanced in 1.15.0; if you threshold on `quality.score`, re-validate your cutoffs.

---

## Migrating from 1.1.x to 1.2.x

Version 1.2.0 is **backwards-compatible** with 1.1.x. No breaking changes were introduced.

### New features to adopt

#### Stop-words

```python
# Before (1.1.x — no stop-words support)
pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
result = pipeline.process("أنا سعيد جداً اليوم")
# result.normalized_text == "أنا سعيد جداً اليوم"

# After (1.2.x — opt-in stop-word removal)
from aranorm import PipelineConfig, StopWordsConfig

config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
)
pipeline = ArabicNormalizationPipeline(config)
result = pipeline.process("أنا سعيد جداً اليوم")
# result.stop_words_removed == "سعيد جداً"
# result.stop_words_found == {"أنا", "اليوم"}
```

#### Config serialization

```python
# New in 1.2.x
cfg = PipelineConfig(preset="deep")
json_str = cfg.to_json()       # serialize
cfg2 = PipelineConfig.from_json(json_str)  # deserialize
```

#### Async processing

```python
# New in 1.2.x
import asyncio

async def process():
    result = await pipeline.process_async("مرحبا")
    return result

asyncio.run(process())
```

---

## Migrating from 1.0.x to 1.1.x

### Dialect identification return type

`DialectIdentifier.identify()` now returns a `DialectIdentification` dataclass instead of a plain tuple.

```python
# Before (1.0.x)
label, confidence = identifier.identify(text)

# After (1.1.x+)
result = identifier.identify(text)
label = result.dialect_label
confidence = result.confidence_score
is_msa = result.is_msa
```

### `NormalizationResult` fields

New fields added in 1.1.x:
- `processing_time_ms` — processing duration in milliseconds
- `is_msa` — property: `True` when `dialect == "MSA"`
- `dialect_label` — alias for `dialect`
- `confidence_score` — alias for `dialect_confidence`

These are additive and do not break existing code.

---

## Planned Breaking Changes (v2.0.0)

The following changes are planned for v2.0.0 and will be announced 6 months in advance:

1. **Drop Python 3.9**: Minimum Python will become 3.10.
2. **Strict `Preset` enum**: `PipelineConfig(preset="standard")` will continue to work, but `PipelineConfig.preset` will always be a `Preset` enum, not `Union[Preset, str]`.
3. **Rename `handle_arabizi`**: Will become `convert_arabizi`.
4. **`NormalizationResult` immutable**: The result dataclass may become frozen.

To prepare for v2.0.0, you can:
- Avoid relying on `config.preset` being a string after construction
- Use `config.preset.value` instead of `str(config.preset)`
