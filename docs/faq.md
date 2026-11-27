# FAQ — الأسئلة الأكثر شيوعاً

Practical answers to the questions we hear most. عقلية عملية: سؤال مباشر، جواب مباشر.

---

## General

### What is AraNorm?

AraNorm is a production-grade Python library for normalizing Arabic text. It supports Modern Standard Arabic (MSA) and 8+ dialects, provides a composable pipeline architecture, ships 45+ analyzers and a 48-command CLI, and has **zero mandatory runtime dependencies**.

### Why use AraNorm instead of PyArabic or CAMeL Tools?

| Feature | AraNorm | PyArabic | CAMeL Tools |
|---------|:-------:|:--------:|:-----------:|
| Unified pipeline API | ✅ | ❌ | ❌ |
| Zero mandatory deps | ✅ | ✅ | ❌ |
| Dialect normalization | ✅ | ❌ | ✅ |
| Social media cleaning | ✅ | ❌ | ❌ |
| Stop-words engine (8 dialects) | ✅ | ❌ | ❌ |
| Arabizi conversion | ✅ | ❌ | ❌ |
| Batch + async + streaming | ✅ | ❌ | ❌ |
| Analysis toolkit | ✅ 45+ | ❌ | ✅ (ML) |
| CLI | ✅ | ❌ | ✅ |

AraNorm complements rather than replaces ML toolkits: use the fast core everywhere, and pull in CAMeL Tools / Transformers through optional extras when you need model-grade accuracy. AraNorm is also fully type-annotated (PEP 561, `py.typed`).

### Which Python versions are supported?

Python 3.9, 3.10, 3.11, 3.12, and 3.13 — tested in CI on all five.

### Is AraNorm free? Can I use it commercially?

Yes. AraNorm is MIT-licensed — use it anywhere, including commercial products, with attribution preserved in the license file.

---

## Installation

### Do I need any other packages?

No. The core is dependency-free. Optional extras add CAMeL Tools (model dialect ID) or Transformers (neural normalization):

```bash
pip install "aranorm[camel]"   # CAMeL Tools
pip install "aranorm[ml]"      # Transformers + PyTorch
pip install "aranorm[full]"    # everything
```

### Why does `pip install "aranorm[ml]"` install PyTorch?

The `ml` extra enables neural CODA/MSA normalization via HuggingFace Transformers, which requires PyTorch. For CPU-only usage:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "aranorm[ml]"
```

### I got `IntegrationUnavailableError` — what does it mean?

You called a feature that needs an optional extra. The error message names the exact fix, e.g. `pip install aranorm[camel]`. The core never raises this — only explicitly requested integrations do.

---

## Usage

### What is the difference between the presets?

- `light` — orthography only (alef/hamza/diacritics/tatweel/digits); nothing is ever deleted.
- `standard` — adds URL/email/HTML cleaning and full punctuation/spacing normalization. Best default.
- `deep` — adds expressive-repeat collapsing (`ياااا` → `يا`). For noisy text, search indexing, deduplication.
- `social_media` — removes mentions/emojis, collapses repeats, and auto-enables stop-word removal (fillers, internet slang, Arabizi function words).

### How do I normalize without removing diacritics?

```python
config = PipelineConfig(preset="standard", remove_diacritics=False)
```

### How do I keep emojis while still cleaning social text?

```python
config = PipelineConfig(preset="social_media", clean_emojis=False)
```

### How do I remove everything except Arabic?

```python
config = PipelineConfig(
    preset="standard",
    remove_non_arabic=True,      # keeps digits & punctuation by default
)
```

Or strip to bare Arabic letters only using the processor directly:

```python
from aranorm.processors import NonArabicProcessor
bare = NonArabicProcessor(keep_digits=False, keep_punctuation=False)
```

### How accurate is dialect detection?

The built-in heuristic (no dependencies) gives fast, well-calibrated confidence scores, typically ~70–80% top-1 accuracy across the ten labels. For >90% accuracy, install CAMeL Tools and enable the model:

```python
from aranorm.stages.dialect_id import DialectIdentifier
identifier = DialectIdentifier(use_camel_tools=True)
```

### Why is my dialect `MSA` with confidence 0.40?

When no dialect markers are found, the identifier conservatively defaults to `MSA @ 0.40` instead of guessing. A 0.40 score means "looks neutral/Fus'ha-ish" — not a real detection.

### Does normalization change meaning?

The defaults are meaning-preserving by design. The one flag to be careful with is `normalize_taa_marbuta` (ة→ه), which erases a grammatical distinction — it is off by default and should only be enabled for matching/search workloads where it helps recall.

### Is `process()` thread-safe?

Yes — pipelines are immutable after construction; you can share one pipeline across threads freely. The batch APIs manage their own thread pools.

### How do I process a large file efficiently?

```bash
# Millions of lines, resumable if it crashes:
aranorm stream run --source corpus.jsonl --output clean.jsonl \
    --checkpoint ckpt.json --workers 4

# Or a simpler batch:
aranorm batch --file large.txt --format jsonl --output out.jsonl --workers 4
```

In Python, `process_iter()` streams with constant memory; `StreamingSession` adds crash-safety with atomic checkpoints (see the [Streaming guide](streaming.md)).

### Can I use AraNorm with pandas / scikit-learn / spaCy / HuggingFace?

Yes — first-class adapters exist for all four. See the [Integrations guide](integrations.md).

### How do I cite AraNorm in a paper?

Use the `CITATION.cff` file in the repository root (GitHub renders a "Cite this repository" button from it).

---

## Behavior details

### Why does ى become ي but ة does not become ه by default?

Arabic writers use ى/ي interchangeably in undiacritized text (عمري/عمرى), so unifying them is almost always safe. ة/ه carry real grammatical information (فاعلة vs فاعل), so unifying them is a deliberate, opt-in trade-off.

### Why did URLs disappear but `#hashtags` keep their word?

`clean_hashtags` strips only the `#` marker — the word is usually signal, not noise. `remove_hashtags` (in `remove_non_arabic`-style workflows) deletes the whole token.

### What does `steps_trace` show?

The exact `(processor, action)` pairs executed for one text, in order — the ground truth of what the pipeline did:

```python
config = PipelineConfig(preset="standard", emit_steps_trace=True)
result = pipeline.process(text)
result.steps_trace   # [("remove_urls", "cleaned"), ("normalize_alef", "normalized"), ...]
```

### Where do I report a bug or request a feature?

[GitHub Issues](https://github.com/Alqudimi/AraNorm/issues) — with your AraNorm version (`aranorm version`), Python version, and a minimal reproducible example. Security issues follow [SECURITY.md](../SECURITY.md) instead.
