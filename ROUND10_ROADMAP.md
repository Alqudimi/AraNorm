# AraNorm Round 10 Roadmap — Durable Streaming Operations

## Goal

Extend AraNorm 1.8.0 with a production-oriented, resumable file-processing boundary and reproducible benchmark artifacts while preserving the existing normalization pipeline, `process_iter`, `StreamingBatchExporter`, `PipelineRuntime`, and `PipelineSpec` APIs.

## Scope

| Workstream | Planned outcome | Compatibility rule |
|---|---|---|
| Durable streaming | Add a bounded file session for one-text-per-line inputs | Delegate normalization to existing `process_iter`; no duplicate processor loop |
| Checkpoint contract | Add versioned typed JSON checkpoint metadata | No executable state, no pickle, atomic publication with unique temporary files |
| Resume safety | Verify source and pipeline fingerprints before resuming | Reject changed input, changed pipeline, invalid schema, and impossible offsets |
| Output semantics | Append-friendly JSONL output with deterministic record order | Existing `StreamingBatchExporter` remains the record serializer |
| CLI | Add an additive `stream` command with checkpoint/resume flags | Existing `batch --stream` and all older commands remain unchanged |
| Benchmark artifacts | Produce reproducible JSON performance and security audit artifacts | Existing audit scripts remain deterministic and non-fatal outside explicit CI gates |
| Quality | Add contract, crash/recovery, CLI, compatibility, performance, and security tests | Target at least 94% total coverage and no static-quality regressions |

## Proposed public contracts

### `StreamCheckpoint`

A frozen, JSON-serializable typed contract with:

- `schema_version`.
- `source_fingerprint` computed with chunked SHA-256.
- `pipeline_fingerprint` from the existing pipeline configuration fingerprint.
- `next_index` representing the next physical input line to process.
- `output_bytes` and `input_count` counters sufficient to truncate a partial tail safely.
- `source_path` and `output_path` identity metadata that do not expose input content.

The contract will use strict field validation, defensive `to_dict`/`from_dict`, bounded integer checks, and atomic file writes. Unknown fields and unsupported schema versions will be rejected explicitly.

### `StreamingSessionReport`

A frozen summary returned by a completed or partially cancelled session, including source identity, output path, checkpoint path, counts, resumed status, and completion status. It will not include source text or exception tracebacks in persisted metadata.

### `StreamingSession`

A small orchestration adapter that accepts an existing `ArabicNormalizationPipeline`, reads UTF-8 lines lazily, processes bounded batches through `process_iter`, writes JSONL records incrementally, and publishes a checkpoint only after a committed output chunk. It supports cancellation at safe record boundaries and never silently resumes against a changed source or pipeline.

## Recovery and failure policy

A resume operation will fail closed for a missing or malformed checkpoint, an input fingerprint mismatch, a pipeline fingerprint mismatch, a negative or out-of-range index, or an output that cannot be opened consistently. A failed checkpoint write must not corrupt the previous checkpoint. A normal completion removes or marks the checkpoint according to an explicit policy; no implicit deletion will occur on a failed run.

The initial implementation uses a one-text-per-line input contract. The checkpoint index refers to the physical line sequence consumed by the session, including empty lines, so recovery can reopen the source deterministically. The output contract is JSONL only for resumable sessions, avoiding invalid partial JSON arrays.

## Benchmark artifact contract

The round produces `performance_round10.json` and `security_round10.json`. The performance artifact records cache and single-flight baselines plus streaming throughput and peak traced memory; the security artifact records regex timing across increasing hostile-input sizes. These artifacts are observational and do not claim distributed or exactly-once guarantees.

## Acceptance criteria

1. Existing test suite and all previous public APIs remain green: 849 passed and 5 documented optional-dependency skips.
2. Streaming session tests cover normal completion, empty input, cancellation, checkpoint round-trip, resume, source mismatch, pipeline mismatch, malformed checkpoint, and checkpoint size safety; targeted CLI and HTTP suites cover the additive adapters.
3. CLI tests cover fresh execution, resume, status, missing files, stable exit codes, human-readable output, JSON output, and nested path creation.
4. JSONL output is valid, ordered, append-safe, and does not duplicate records after resume; HTTP streaming remains disabled by default.
5. `make verify` and `make test-cov` pass with 94% total coverage; audit scripts, build, `twine check`, and compileall pass.
6. API, README, architecture, configuration, and changelog documentation cover the input/output contract, recovery guarantees, security boundaries, and operational limitations.
7. A release report, checksums, clean archive, and final commit are produced only after all gates pass.

## Explicit non-goals

This round will not introduce a database queue, distributed workers, exactly-once claims across arbitrary filesystems, a new normalization engine, or a cloud-specific storage dependency. Those concerns remain future adapters around the durable local contract.

## References

- [1] Python `itertools` documentation: https://docs.python.org/3/library/itertools.html#itertools.islice
- [2] Python `hashlib` documentation: https://docs.python.org/3/library/hashlib.html
- [3] Python `os.replace` documentation: https://docs.python.org/3/library/os.html#os.replace
