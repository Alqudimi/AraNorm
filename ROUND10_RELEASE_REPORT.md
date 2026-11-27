# AraNorm Round 10 Release Report

**Project:** AraNorm

**Release line:** `1.8.0` (round 10 remains documented under `Unreleased` by design)

**Branch:** `professional-hardening`

**Round theme:** Resumable, production-oriented local file streaming

## Executive summary

Round 10 extends AraNorm without rewriting the normalization engine or duplicating its processor loop. The new `StreamingSession` adapter delegates normalization to the existing `ArabicNormalizationPipeline.process_iter()` contract, writes bounded JSONL output, and publishes a versioned checkpoint after committed batches. Resume is fail-closed: source path, output path, source SHA-256, pipeline configuration fingerprint, schema, and output offset must all be valid before prior progress is reused.

The round also adds additive CLI commands, an optional HTTP endpoint disabled by default, contract-focused tests, dedicated CI/Makefile gates, and documentation for operational limits and filesystem security. The official package version remains `1.8.0`; the work is recorded under `CHANGELOG.md` `Unreleased` rather than changing the public release number.

## Delivered scope

| Area | Delivered contract | Compatibility outcome |
|---|---|---|
| Durable streaming | `StreamingSession`, `StreamingSessionReport`, and `fingerprint_file()` | Uses the existing `process_iter()` path; no normalization logic was duplicated |
| Checkpointing | Frozen `StreamCheckpoint` with schema validation, bounded loading, atomic write, and SHA-256 identity | Rejects unknown fields, invalid fingerprints, unsupported schemas, and impossible offsets |
| Recovery | Resume truncates to the committed `output_bytes` offset before continuing | Prevents duplicate records and partially written JSONL tails |
| CLI | `stream run`, `stream resume`, and `stream status`, each with human and JSON output | Existing commands remain additive and backward-compatible |
| HTTP | Optional `/v1/stream` endpoint | Disabled by default; explicitly enabled with `--streaming-enabled` |
| Quality gates | `streaming-contracts`, server/CLI/session suites, full verify and coverage | Static checks and regression suite remain green |
| Documentation | API reference, README, architecture, configuration, changelog, and roadmap | Documents limits, recovery guarantees, and the local-filesystem trust boundary |

## Public contract details

`StreamingSession` accepts a UTF-8 source file with one text item per line, an output JSONL path, and a checkpoint path. `batch_size`, `n_workers`, `on_error`, `cancellation_token`, and `max_input_bytes` preserve the existing processing contracts and are validated defensively. `StreamCheckpoint.write_atomic()` uses a same-directory temporary file, flushes and fsyncs it, and publishes with `os.replace`.

The checkpoint stores `schema_version`, source and output paths, source and pipeline fingerprints, `next_index`, `output_bytes`, `input_count`, and `completed`. `StreamingSessionReport` returns the corresponding operational outcome, including `processed_count`, `resumed`, `completed`, and `cancelled`. `CheckpointError` represents checkpoint contract failures, while `StreamingSessionError` represents session-level failures.

> The optional HTTP endpoint accepts local filesystem paths. It is an administrator-controlled adapter, not an authentication or authorization layer, and must not be exposed to untrusted callers without an external security boundary.

## Verification results

The complete verification gate passed with **849 tests passed** and **5 documented optional-dependency skips**. The skips are limited to unavailable optional integrations (`PyYAML`, `datasets`, spaCy, NLTK, and scikit-learn) and do not indicate failures.

`make test-cov` passed with **94% total coverage**, covering 5,462 measured statements and 338 missed statements. The new `src/aranorm/core/streaming.py` has 86% direct line coverage; the HTTP adapter is at 95%, and the existing runtime remains at 99%. The lower direct percentage for the new module is concentrated in defensive error branches and filesystem-failure paths, while the targeted round 10 suite exercises its public recovery invariants.

| Gate | Result |
|---|---|
| `make verify` | Passed: 849 passed, 5 skipped |
| `make test-cov` | Passed: 849 passed, 5 skipped; 94% total |
| `make streaming-contracts` | Passed during the round 10 integration gate |
| Black / flake8 / mypy | Passed for the final source changes |
| `python3 -m compileall -q src/aranorm` | Passed |
| `python3 -m build` | Passed; wheel and sdist created |
| `python3 -m twine check dist/*` | Passed for wheel and sdist |

## Audit artifacts

The reproducible JSON artifacts are committed alongside the source. `performance_round10.json` records cache and single-flight baselines plus streaming throughput and traced memory. The observed streaming benchmark processed 10,000 items at approximately 302.96 texts/second with a 7,137,826-byte traced peak. `security_round10.json` records regex timing for increasing hostile-input sizes through 20,000 characters; the measured timings remain sub-millisecond to low-millisecond and scale approximately linearly in the recorded sample.

These are local observational audits, not a claim of distributed exactly-once processing or a substitute for production load testing on the target filesystem and hardware.

## Package artifacts

The build produced the following version-preserving artifacts:

| Artifact | Validation |
|---|---|
| `dist/aranorm-1.8.0-py3-none-any.whl` | `twine check` passed |
| `dist/aranorm-1.8.0.tar.gz` | `twine check` passed |
| `dist/SHA256SUMS-1.8.0-round10.txt` | SHA-256 checksums for both distributions |

The enterprise archive is generated outside the repository after the final commit and is validated with `unzip -tq`. Its detached checksum is stored as `AraNorm-1.8.0-round10-enterprise.zip.sha256`.

## Security and operational limitations

The checkpoint contains paths and fingerprints but no input text, executable state, pickle, or traceback. Atomic replacement protects the checkpoint publication boundary, but it does not provide distributed locking or exactly-once semantics across arbitrary filesystems. Operators must use filesystem permissions, controlled directories, quotas, and an external gateway when exposing the HTTP adapter.

The session is intentionally a local durable adapter. It does not introduce a database queue, distributed workers, cloud storage dependency, or a new normalization engine. Those capabilities remain future adapters around the stable local contract.

## Final release disposition

The round 10 implementation commit is `f4faaf12620c2816ca3cc441b9c955c408b98102` with message `feat: round 10 resumable streaming session v1.8.0`. The release report is finalized in the subsequent metadata commit. The Enterprise archive is generated from the resulting committed tree outside the repository; its detached SHA-256 checksum is recorded in `AraNorm-1.8.0-round10-enterprise.zip.sha256`.

## References

[1]: https://docs.python.org/3/library/hashlib.html "Python hashlib documentation"

[2]: https://docs.python.org/3/library/os.html#os.replace "Python os.replace documentation"

[3]: https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/ "Python Packaging User Guide"
