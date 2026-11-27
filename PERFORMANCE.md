# Performance Guide

This document covers profiling, benchmarking, and optimization tips for AraNorm.

---

## Benchmarks

Run the bundled benchmark script:

```bash
python scripts/benchmark.py
```

### Reference Numbers (Python 3.11, modern CPU, single thread)

| Configuration | texts/sec | ms/text |
|---------------|-----------|---------|
| `light` preset | ~50 000 | ~0.02 |
| `standard` preset | ~15 000 | ~0.07 |
| `deep` preset | ~8 000 | ~0.12 |
| `social_media` preset | ~6 000 | ~0.17 |
| `standard` + stop-words | ~12 000 | ~0.08 |
| `standard` + sentiment | ~5 000 | ~0.20 |

---

## Optimization Tips

### 1. Use the Lightest Preset That Meets Your Needs

```python
# If you only need alef/hamza/diacritics normalization:
config = PipelineConfig(preset="light")

# Only use "deep" when normalized-form quality is critical
```

### 2. Cache Repeated Texts

```python
from aranorm.utils.cache import NormalizationCache

cache = NormalizationCache(pipeline, maxsize=100_000)
# First call processes; subsequent identical texts return instantly
result = cache.process(text)

# For large files, keep memory bounded and preserve input order
with open("texts.txt", encoding="utf-8") as source:
    for result in cache.process_iter(source, batch_size=256, n_workers=4):
        consume(result)
```

`NormalizationCache.process_iter()` combines LRU reuse with bounded pipeline batches. Choose `maxsize` according to the expected repetition rate; a very large cache is counterproductive for mostly unique inputs.

### 3. Multi-Threaded Batch Processing

```python
# Use n_workers > 1 for I/O-bound workloads or when optional ML models are used
results = pipeline.process_batch(texts, n_workers=4, batch_size=64)

# Streaming equivalent for generators/files; does not materialize all results
for result in pipeline.process_iter(texts, n_workers=4, batch_size=64):
    consume(result)
```

`process_batch()` remains convenient when the result list is needed. Prefer `process_iter()` for unbounded iterables or large files because only the current bounded chunk is materialized. Due to the GIL, multi-threading benefits most when pipeline stages involve I/O or optional model inference; benchmark on the target workload before increasing workers.

### 4. Disable Unused Pipeline Stages

```python
config = PipelineConfig(
    preset="standard",
    # Disable what you don't need
    clean_html=False,
    clean_emails=False,
    normalize_digits=False,
)
```

### 5. Reuse the Pipeline Object

Constructing a pipeline loads data files and compiles regex patterns. Create it once:

```python
# ❌ Don't do this in a loop
for text in texts:
    pipeline = ArabicNormalizationPipeline()  # expensive!
    result = pipeline.process(text)

# ✅ Do this
pipeline = ArabicNormalizationPipeline()
for text in texts:
    result = pipeline.process(text)
```

### 6. Pre-compile Regex (Already Done)

All AraNorm processors compile their regex patterns at class instantiation time (not per-call). You get this for free by reusing processor instances.

### 7. Streaming Large Files

For newline-delimited input, use the CLI streaming path so the source and output are processed incrementally:

```bash
aranorm batch --file texts.txt --stream --batch-size 256 \\
  --workers 4 --format jsonl --output normalized.jsonl
```

`--skip-errors` is useful for noisy production corpora: failed records are reported and skipped while successful records continue. Use JSONL when downstream consumers can process one object at a time; use CSV for spreadsheet workflows and JSON when a single valid array is required.

### 8. Chunking for Large Documents

```python
from aranorm.utils.chunker import TextChunker

chunker = TextChunker(max_tokens=512, overlap_tokens=32)
for chunk in chunker.chunk(large_document):
    result = pipeline.process(chunk.text)
```

---

## Memory Usage

| Component | Memory footprint |
|-----------|-----------------|
| `ArabicNormalizationPipeline` (standard) | ~2–5 MB |
| `StopWordsRegistry` (all dialects) | ~5–10 MB |
| `NormalizationCache(maxsize=10000)` | ~50–100 MB |
| CAMeL Tools model | ~300–500 MB |
| Transformers model (CODA/MSA) | ~500 MB – 2 GB |

---

## Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

pipeline.process_batch(BATCH_1000)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats("cumulative")
stats.print_stats(20)
```

Common bottlenecks found in profiling:
1. Regex compilation (mitigated: compiled once at startup)
2. Trie lookup in `StopWordsRegistry` (O(k) where k = word length)
3. Dialect marker scanning (linear in text length)

---

## Async Usage

For integration with `asyncio` web servers (FastAPI, aiohttp):

```python
@app.post("/normalize")
async def normalize(request: NormalizeRequest):
    result = await pipeline.process_async(request.text)
    return result.to_dict()
```

`process_async()` runs the synchronous `process()` in a thread-pool executor, preventing event-loop blocking.
