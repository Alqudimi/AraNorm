# Round 10 Research Notes

## Scope

The proposed Round 10 scope extends the existing `process_iter` and `StreamingBatchExporter` boundaries with a durable file-processing session, checkpoint/resume metadata, and persisted benchmark comparison. It does not rewrite the normalization core or replace the existing exporters.

## Official Python references

1. **`itertools.islice` and iterator algebra**: Python documents `itertools` as memory-efficient iterator building blocks and describes `islice` as a lazy iterator slice. This supports bounded, incremental input consumption rather than materializing a complete corpus.
   Source: https://docs.python.org/3/library/itertools.html#itertools.islice

2. **`hashlib.sha256` and incremental updates**: Python documents hash objects whose `update()` calls are equivalent to hashing concatenated chunks, and identifies SHA-256 as a guaranteed constructor. Round 10 will use chunked SHA-256 for source identity without loading a large file into memory.
   Source: https://docs.python.org/3/library/hashlib.html

3. **`os.replace` and filesystem operations**: Python documents `os` filesystem operations and the use of `OSError` for invalid or inaccessible paths. The implementation will use a unique temporary file plus `os.replace` for checkpoint publication, with cleanup on failure.
   Source: https://docs.python.org/3/library/os.html#os.replace

## Design decisions

- The session API will be additive and will delegate text normalization to `ArabicNormalizationPipeline.process_iter`.
- Checkpoints will be versioned JSON metadata, not executable objects; they will include schema version, input fingerprint, next record index, output path, and counters.
- Resume will reject a changed source fingerprint, changed pipeline fingerprint, incompatible schema, or a checkpoint beyond the input contract.
- Output will use JSONL as the resumable format because it is append-friendly; existing `StreamingBatchExporter` remains the serialization boundary for individual normalization records.
- Atomic checkpoint publication and bounded iterators are portability and recovery mechanisms, not a claim of transactional durability across arbitrary filesystems.

## Benchmark extension

The existing `scripts/benchmark.py` already measures batch and streaming throughput but only prints transient summaries. Round 10 may add deterministic JSON artifact output and optional baseline comparison, preserving the current console interface and non-fatal light gate.

## Reference integrity

The sources above were retrieved from the official Python documentation and should be cited in `ROUND10_RELEASE_REPORT.md` if the design is implemented.
