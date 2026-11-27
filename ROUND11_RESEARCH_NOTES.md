# AraNorm Round 11 Research Notes

## Research objective

Round 11 focuses on hardening the existing resumable local streaming boundary without rewriting the normalization pipeline. The research examined official guidance for atomic replacement, Unix file locking, and JSON Lines record semantics.

## Sources and decisions

### Python `os.replace`

Source: [Python `os.replace` documentation](https://docs.python.org/3/library/os.html#os.replace)

The current `StreamCheckpoint.write_atomic()` already uses a same-directory temporary file and `os.replace`. The next round should preserve that publication pattern, retain explicit `fsync` on the temporary file, and document that atomic name replacement is not equivalent to distributed coordination or a cross-filesystem transaction. Any directory durability enhancement must remain best-effort and platform-aware rather than changing the Python 3.9 compatibility contract.

### Python `fcntl`

Source: [Python `fcntl` documentation](https://docs.python.org/3/library/fcntl.html)

`fcntl.flock` and `lockf` are Unix facilities. The documentation states that the module is available on Unix and not WASI, and that non-blocking locking reports `EACCES` or `EAGAIN` depending on the operating system. Therefore, a portable public API must not silently make `fcntl` mandatory. The recommended design is an optional local lock strategy: a small lock abstraction with a documented Unix advisory implementation and a safe fallback or explicit unsupported error on platforms without `fcntl`. The lock must protect one source/output/checkpoint tuple against concurrent writers, not claim distributed locking.

### JSON Lines

Source: [JSON Lines specification](https://jsonlines.org/)

The format requires UTF-8, one valid JSON value per line, and `\n` line termination; a final terminator is recommended. The current streaming session follows these rules by serializing each normalization result as one UTF-8 JSON object followed by a newline and committing only after flushing the output batch. Future changes must continue to use the existing `StreamingBatchExporter` serialization contract or a shared serializer so resumable streaming does not maintain a second incompatible record format.

## Local gap inventory

The current implementation is production-oriented but intentionally minimal. The most valuable next improvements are: a concurrency guard for the session tuple; a shared export/serialization path instead of hand-written JSONL output; explicit source mutation detection during a run; richer checkpoint/status diagnostics without exposing text; strict path-safety controls for the optional HTTP endpoint; and tests for corruption, concurrent sessions, write failures, skipped records, and source changes after the initial fingerprint.

The implementation must preserve these boundaries: the existing processor loop remains the only normalization path; the default HTTP streaming endpoint remains disabled; local filesystem semantics are not promoted to distributed exactly-once guarantees; and older CLI, server, runtime, and PipelineSpec APIs remain backward-compatible.

## Proposed Round 11 workstreams

| Workstream | Proposed outcome | Primary acceptance signal |
|---|---|---|
| Session concurrency | Prevent two writers from processing the same tuple concurrently | Deterministic busy-lock error and no duplicate output |
| Output contract | Reuse shared exporter/serializer primitives where compatible | JSONL remains byte-valid and round-trip compatible |
| Source integrity | Detect source identity changes during long-running sessions | Session fails closed or reports a typed integrity error |
| HTTP path policy | Optional allowed-root boundary for `/v1/stream` | Requests outside the configured root are rejected safely |
| Operational status | Stable diagnostic fields and typed status errors | CLI/HTTP status remains machine-readable and text-free |
| Test matrix | Add failure-injection, concurrency, portability, and compatibility suites | New tests pass on supported Python versions without weakening old tests |
| Documentation | Document locks, path trust boundary, source mutation, and limitations | API/configuration/architecture docs match behavior |

## Non-goals

This round will not introduce a database queue, a cloud storage provider, a new normalization engine, mandatory third-party dependencies, or a distributed lock service. It will not rewrite `pipeline.py` or replace the existing runtime snapshot architecture.

## References

[1]: https://docs.python.org/3/library/os.html#os.replace "Python os.replace documentation"

[2]: https://docs.python.org/3/library/fcntl.html "Python fcntl documentation"

[3]: https://jsonlines.org/ "JSON Lines specification"
