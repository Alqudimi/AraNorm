# Resumable Streaming Sessions

**AraNorm v1.15.0** · Crash-safe, checkpointed file-to-file normalization

Batch normalization of large corpora has an unforgiving failure mode: a job
that dies at line 900,000 of 1,000,000 either restarts from zero or — worse —
restarts from zero *and* produces a partially duplicated output. AraNorm's
streaming layer removes that failure mode. A `StreamingSession` reads a UTF-8
source file one line at a time, appends normalized results to a JSONL output,
and writes a **durable checkpoint after every committed batch**. When the
process is killed — by a deploy, an OOM killer, a spot-instance reclaim, or a
plain `Ctrl-C` — the next run resumes from the exact line where the last
checkpoint was committed: **never duplicating a line, never skipping one**.
The layer is deliberately small — one class, two frozen dataclasses, one
helper, four exceptions — and runs entirely on the standard library: no
broker, no database, no external coordinator.

---

## Table of contents

1. [Quick start](#quick-start)
2. [How it works](#how-it-works)
   - [Checkpoint anatomy](#checkpoint-anatomy)
   - [Atomicity guarantees](#atomicity-guarantees)
   - [The three fingerprints](#the-three-fingerprints)
   - [The commit cycle](#the-commit-cycle)
3. [Resuming after a crash](#resuming-after-a-crash)
   - [What `resume=True` verifies](#what-resumetrue-verifies)
   - [Re-processing semantics](#re-processing-semantics)
4. [Failure modes and errors](#failure-modes-and-errors)
5. [Concurrency and locking](#concurrency-and-locking)
6. [Source integrity](#source-integrity)
7. [Cancellation](#cancellation)
8. [CLI workflow](#cli-workflow)
9. [HTTP-triggered sessions](#http-triggered-sessions)
10. [Limits and tuning](#limits-and-tuning)
11. [Best practices checklist](#best-practices-checklist)

---

## Quick start

A streaming session needs three distinct paths: a **source** (UTF-8 text, one
item per line), an **output** (JSONL), and a **checkpoint** (JSON). Given this
`corpus.txt`:

```text
السَّلامُ عَلَيْكُم وَرَحْمَةُ اللّٰهِ
كيف حالك يا صديقي؟
شلونك اخبارك؟
انا رايح للسوق اليوم
يوجد ١٢٣ طالب في المدرسة
هذا رابط https://example.com/article
ولكن، ماذا حدث بعد ذلك؟!
كتبتُ رسالةً طويلة جداً
```

…run the session:

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, StreamingSession

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))

session = StreamingSession(
    pipeline,
    source_path="corpus.txt",
    output_path="corpus.normalized.jsonl",
    checkpoint_path="corpus.checkpoint.json",
    batch_size=4,
)
report = session.run()
```

`run()` returns a frozen `StreamingSessionReport`. Its `to_dict()` for the file
above:

```json
{
  "cancelled": false,
  "checkpoint_path": "/srv/streaming/corpus.checkpoint.json",
  "completed": true,
  "next_index": 8,
  "output_path": "/srv/streaming/corpus.normalized.jsonl",
  "pipeline_fingerprint": "e5144fa23504f33e7cc430627ba0ac536ba70e8690787250a19763d51628b3ed",
  "processed_count": 8,
  "resumed": false,
  "source_fingerprint": "117a9a5858ccb8835efdd04dda8aded2c4978d903211f8c2c822d1589d96e738",
  "source_path": "/srv/streaming/corpus.txt"
}
```

The output is JSONL — one full `NormalizationResult` object per input line,
with the original text preserved alongside the normalization:

```json
{"original_text": "السَّلامُ عَلَيْكُم وَرَحْمَةُ اللّٰهِ", "normalized_text": "السلام عليكم ورحمة الله", "dialect": "MSA", "applied_steps": ["remove_urls", "…", "normalize_diacritics", "normalize_digits", "fix_spacing"], "processing_time_ms": 10.887, "...": "..."}
```

Everything else in this guide explains what the session does *for you* under
the hood, and which knobs change that behavior.

---

## How it works

`StreamingSession` interprets the source as **one text item per line** and the
output as **append-only JSONL**. Before any I/O happens, the constructor
validates its three paths: they must be *distinct* strings (`ValueError:
source, output, and checkpoint paths must be distinct`), must not alias the
same file through links if they already exist (`…must not alias the same
file`), and `batch_size` / `n_workers` / `max_input_bytes` must be positive
integers with `lock_enabled` a boolean. Paths are stored in absolute form and
recorded in the checkpoint — a checkpoint can only be resumed by a session
using the *same* file locations.

### Checkpoint anatomy

The checkpoint is a small, human-readable, strictly validated JSON document.
Every field:

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | `int` | Always `1` (`CHECKPOINT_SCHEMA_VERSION`). Loading a checkpoint with any other value raises `CheckpointError` — forward compatibility is explicit, not accidental. |
| `source_path` | `str` | Absolute path of the input file this checkpoint belongs to. |
| `output_path` | `str` | Absolute path of the JSONL output bound to this checkpoint. |
| `source_fingerprint` | `str` (64 hex) | SHA-256 of the source file's exact bytes. |
| `pipeline_fingerprint` | `str` (64 hex) | SHA-256 of the pipeline's canonical configuration (from `pipeline.configuration_fingerprint()`). |
| `next_index` | `int ≥ 0` | Zero-based index of the **next input line to read**. `0` means "nothing processed yet". |
| `output_bytes` | `int ≥ 0` | Byte offset within the output file through the last committed batch. Used to trim any uncommitted tail on resume. |
| `input_count` | `int ≥ 0` | Number of input lines fully processed and committed. |
| `completed` | `bool` | `True` once the source has been fully consumed. |

`StreamCheckpoint` is a frozen dataclass with strict validation in
`__post_init__`: fingerprints must be exactly 64 hexadecimal characters,
counters must be non-negative, `next_index` may not be smaller than
`input_count`, and `from_dict()` rejects both unknown and missing fields — a
hand-edited or truncated checkpoint fails loudly instead of resuming from
garbage:

```python
StreamCheckpoint.from_dict({"schema_version": 1, "surprise": True})
# CheckpointError: unknown checkpoint fields: ['surprise']
StreamCheckpoint.from_dict({"schema_version": 1})
# CheckpointError: missing checkpoint fields: ['completed', 'input_count', ...]
```

`StreamCheckpoint.load(path, *, max_bytes=...)` reads a checkpoint with a
size cap (default 1 MiB, minimum 256 bytes) — a multi-gigabyte "checkpoint"
is treated as corruption or abuse, not as state.

### Atomicity guarantees

Both durable artifacts are written so that a crash at *any* instruction leaves
a consistent predecessor on disk:

- **Checkpoint writes** (`write_atomic`) go to a temporary file in the *same
  directory* as the target, are `flush()` + `os.fsync()`-ed, then
  `os.replace()`-ed over the checkpoint path. `os.replace` is atomic, so
  readers see either the old checkpoint or the new one — never a partial one.
- **Output writes** are appended and fsynced *before* the checkpoint is
  written, so `output_bytes` never advertises bytes still in flight.
- On resume, the output is opened `r+`, seeked to `checkpoint.output_bytes`,
  and **truncated** — a batch appended but never checkpointed (crash between
  the output fsync and the checkpoint rename) is discarded and re-processed
  exactly once.

### The three fingerprints

A checkpoint binds three things together, each with its own SHA-256:

1. **Source fingerprint** — `fingerprint_file(path)` hashes the source's raw
   bytes in 1 MiB chunks (`DEFAULT_FINGERPRINT_CHUNK_BYTES`). Identical
   content yields identical fingerprints; any edit, even one byte, changes it.
2. **Pipeline fingerprint** — `pipeline.configuration_fingerprint()` hashes
   the canonical configuration only (input text and runtime state are
   excluded). One flipped flag — `remove_diacritics`, a different preset,
   stop-word settings — produces a different fingerprint.
3. **Output binding** — the checkpoint's `source_path`/`output_path` pair
   plus the `output_bytes` offset. A checkpoint refuses to be replayed
   against a different output file or one that has shrunk below the offset.

If any of the three disagree with the current invocation, the session raises
`CheckpointError` **before writing anything** — a checkpoint is never silently
reinterpreted.

### The commit cycle

For every batch of `batch_size` lines, the session performs one commit cycle.
A checkpoint exists on disk describing state *N*; the cycle atomically
advances it to state *N + batch_size*:

```text
   checkpoint (state N)                        source file
   next_index = i          ┌──────────────▶  line i, i+1, … i+b-1
   output_bytes = o        │                 (read from next_index)
   input_count  = n        │
        │                 │
        ▼                 │
   ┌──────────────────────────────────────────────────────────┐
   │  1. read next batch (≤ batch_size lines) from source     │
   │  2. pipeline.process_iter(batch)  → NormalizationResults │
   │  3. exporter.write_jsonl(results, output)  → append JSONL│
   │  4. output.flush() + os.fsync(output)                    │
   │  5. StreamCheckpoint(                                   │
   │        next_index  = i + len(batch),                    │
   │        output_bytes = output.tell(),                    │
   │        input_count  = n + len(batch))                   │
   │     .write_atomic(checkpoint)  → temp + fsync + replace │
   └──────────────────────────────────────────────────────────┘
        │
        ▼
   checkpoint (state N+1)  — steps 4 and 5 both durable before continuing
```

Two details make the cycle crash-safe. The output is fsynced *before* the
checkpoint is replaced, so the checkpoint never claims progress that is not on
disk; and the resume path truncates the output to `output_bytes`, so the
window between steps 4 and 5 costs at most one re-processed batch — never a
duplicated line in the committed output.

---

## Resuming after a crash

`run(resume=True)` is the default. The following transcript is real: a
20,000-line corpus was processed with `batch_size=32`, and the process was
`kill -9`-ed about three seconds in. The checkpoint left on disk:

```json
{
  "schema_version": 1,
  "source_path": "/srv/streaming/big-corpus.txt",
  "output_path": "/srv/streaming/big-corpus.normalized.jsonl",
  "source_fingerprint": "8863a9ec3e38b381d7bd1ec80deb76ec5bde8b5a2314e3f424d988c835cac14e",
  "pipeline_fingerprint": "e5144fa23504f33e7cc430627ba0ac536ba70e8690787250a19763d51628b3ed",
  "next_index": 7232,
  "output_bytes": 5652453,
  "input_count": 7232,
  "completed": false
}
```

7,232 of 20,000 lines survived the kill. Resuming with the same pipeline and
paths finishes the job:

```python
report = StreamingSession(
    pipeline, "big-corpus.txt", "big-corpus.normalized.jsonl",
    "big-corpus.checkpoint.json", batch_size=32,
).run(resume=True)

print(report.resumed, report.processed_count, report.completed)
# True 20000 True
```

A post-flight check confirms the guarantee: the output holds exactly 20,000
lines and every output line's `original_text` matches the source line at the
same position — order preserved, zero duplicates, zero skips.

### What `resume=True` verifies

Before appending a single byte, the session re-derives everything the
checkpoint claims and compares:

| Verification | Failure message (`CheckpointError`) | What it protects |
|--------------|--------------------------------------|------------------|
| `checkpoint.source_path` / `output_path` equal this session's paths | `checkpoint paths do not match this session` | Replaying a checkpoint against different files (even an identical copy of the source at a different path). |
| `fingerprint_file(source)` equals `source_fingerprint` | `source fingerprint does not match checkpoint` | The source changed after the checkpoint was written — resuming would silently skip or duplicate the changed region. |
| `pipeline.configuration_fingerprint()` equals `pipeline_fingerprint` | `pipeline fingerprint does not match checkpoint` | The pipeline configuration changed — the remaining lines would be normalized under different rules than the committed ones. |
| `os.path.getsize(output) >= checkpoint.output_bytes` | `checkpoint output offset exceeds output size` | The output was truncated or replaced; the recorded offset no longer points into a valid prefix. |
| Checkpoint parses strictly (`schema_version`, field set, types) | e.g. `unknown checkpoint fields: ['surprise']` | Hand-edited, corrupted, or foreign-version checkpoints. |

If the checkpoint is marked `completed`, the session returns immediately
with `resumed=True, completed=True` — re-running a finished session is a
cheap idempotent no-op, safe to wire into a retry loop.

### Re-processing semantics

The unit of exactly-once processing is the **committed batch**:

- Lines are read starting at `checkpoint.next_index`; everything before it
  is skipped without decoding or normalizing.
- Bytes appended beyond `checkpoint.output_bytes` are truncated away on
  resume, so a batch that crashed between the output fsync and the checkpoint
  rename is re-processed — its half-written output is discarded, not
  duplicated.
- `resume=False` (the CLI's `stream run`) ignores any existing checkpoint,
  truncates the output, and starts from line 0 — for deliberately redoing a
  job, never for continuing one.

---

## Failure modes and errors

All four streaming exceptions are exported from the top-level `aranorm`
package. `StreamingSessionError` subclasses both `AraNormError` and
`RuntimeError`; `CheckpointError` additionally subclasses `ValueError`, so
generic `except ValueError` handlers catch it.

| Exception | Raised when | Typical cause | Recovery |
|-----------|-------------|---------------|----------|
| `StreamingSessionError` | The session cannot run safely for a non-checkpoint reason. | Source missing (`source file does not exist: …`), source larger than `max_input_bytes`, output directory unwritable, I/O or decoding failure mid-run. | Fix the filesystem problem (restore the source, raise the limit, correct permissions), then re-run with `resume=True`. |
| `CheckpointError` | Checkpoint metadata is missing, malformed, or incompatible with this invocation. | Source or pipeline fingerprint mismatch, path mismatch, output shrunk, hand-edited JSON, unknown `schema_version`, checkpoint larger than the size cap. | Decide intent: restore the matching source/pipeline to resume, or delete the checkpoint (and output) to start over. Never edit a checkpoint by hand. |
| `StreamingSessionConflictError` | Another process holds the advisory lock for this checkpoint. | A second worker started with `lock_enabled=True` while a session is still running. | Wait for the owner to finish, or point the second worker at a different checkpoint tuple. The lock is released automatically when the owner exits. |
| `StreamingSourceChangedError` | The source mutated while the session was running. | A producer appended to or rewrote the source mid-run. | Treat the source as immutable: stage a new snapshot file, point a *new* session (new checkpoint) at it, and archive the old one. |

One related exception sits outside the streaming hierarchy: a
`CancellationToken` that fires *while a batch is mid-flight* makes
`process_iter()` raise `ProcessingCancelledError`, which the session re-raises
(see [Cancellation](#cancellation)).

---

## Concurrency and locking

By default a session takes no locks — a single-process job pays no overhead.
For shared storage (NFS-mounted scratch, a mounted volume where a cron job and
a manual repair might overlap), opt into a **Unix advisory lock**:

```python
session = StreamingSession(
    pipeline, "corpus.txt", "corpus.normalized.jsonl", "corpus.checkpoint.json",
    lock_enabled=True,   # flock on corpus.checkpoint.json.lock
)
```

Semantics:

- The lock file is `<checkpoint_path>` + `DEFAULT_SESSION_LOCK_SUFFIX`
  (`.lock`), created next to the checkpoint and held with
  `fcntl.flock(LOCK_EX | LOCK_NB)` for the *entire* `run()` — fingerprint
  pass and every commit cycle included.
- If the lock is already held, `run()` raises `StreamingSessionConflictError:
another process owns this streaming session` immediately, without touching
  the output or checkpoint.
- The lock is **advisory**: it coordinates processes that also opt in, does
  not protect against a writer with locking disabled, and is unavailable on
  non-Unix platforms (raising `StreamingSessionError` there when requested).
- Locks are released when `run()` returns or the process dies — `flock` is
  tied to the open file descriptor, so a killed owner never leaves a stale
  lock. The empty `.lock` file may remain; that is harmless.

The CLI exposes this as `--lock`, and the HTTP `/v1/stream` endpoint enables
locking **unconditionally** (see below).

---

## Source integrity

A streaming session assumes the source is an **immutable snapshot**, and
enforces the assumption actively: before the first read and before *every*
batch, the session compares the source's stat signature (device, inode, size,
mtime) with the signature captured at the start of the run. If the signature
changed, it re-fingerprints the file; if the SHA-256 also changed, the
session aborts with `StreamingSourceChangedError: source file changed during
streaming` (a vanished file yields `source file became unavailable during
streaming`).

This is a deliberate **fail-closed** design: a source that grows mid-run
would shift the line numbering that `next_index` depends on, silently
corrupting exactly-once semantics. The check costs one `stat()` per batch,
plus a full re-hash only when a change is actually detected. The practical
workflow for living data is dated snapshots — producers write to
`corpus-2025-01-08.txt`, the session consumes that file, and new data goes to
`corpus-2025-01-09.txt` with its own output/checkpoint pair. If you must
append to the same file name, finish the current session first, then start a
new one with a fresh checkpoint.

---

## Cancellation

`StreamingSession` accepts an optional `CancellationToken` for cooperative
graceful shutdown (for example, a signal handler in a worker process):

```python
import signal
from aranorm import CancellationToken, StreamingSession

token = CancellationToken()
signal.signal(signal.SIGTERM, lambda signum, frame: token.cancel())

report = StreamingSession(
    pipeline,
    source_path="big-corpus.txt",
    output_path="big-corpus.normalized.jsonl",
    checkpoint_path="big-corpus.checkpoint.json",
    cancellation_token=token,
).run()
```

Two outcomes are possible, and both are safe:

1. **Cancellation observed at a batch boundary** (checked before each batch
   and after each `process_iter`): `run()` returns a report with
   `cancelled=True, completed=False` and the counts of the last *committed*
   batch — e.g. `cancelled=True, processed=0, next_index=0` for a token
   cancelled before the run.
2. **Cancellation lands mid-batch**: the pipeline's cooperative checks raise
   `ProcessingCancelledError`, which the session re-raises rather than
   swallow. In a verified run the token fired at 0.35 s; the checkpoint on
   disk still described the last committed batch (`next_index: 928`), and a
   follow-up `run(resume=True)` finished all remaining lines.

In both cases the durable state is identical: the checkpoint reflects the
last fully committed batch, the output contains exactly that batch's lines,
and `resume=True` continues from there. Never treat `ProcessingCancelledError`
as data loss — check `aranorm stream status` and resume.

---

## CLI workflow

The `aranorm stream` command wraps the same session: `run` starts fresh
(`resume=False`), `resume` continues from the checkpoint, and `status`
inspects a checkpoint without running anything. `--json` switches any of
them to machine-readable output (`status --json` prints the checkpoint's
exact `to_dict()`; `run --json` prints `{"ok": true, "report": {...}}`):

```console
$ aranorm stream run --source sample.txt --output sample.normalized.jsonl \
                     --checkpoint sample.ckpt.json --preset standard --batch-size 2
Processed streaming session
Source     : /srv/streaming/sample.txt
Output     : /srv/streaming/sample.normalized.jsonl
Checkpoint : /srv/streaming/sample.ckpt.json
Processed  : 5
Next index : 5
Completed  : yes
```

```console
$ aranorm stream status --checkpoint sample.ckpt.json --json
{
  "completed": true,
  "input_count": 5,
  "next_index": 5,
  "output_bytes": 3900,
  "output_path": "/srv/streaming/sample.normalized.jsonl",
  "pipeline_fingerprint": "e5144fa23504f33e7cc430627ba0ac536ba70e8690787250a19763d51628b3ed",
  "schema_version": 1,
  "source_fingerprint": "19ba3484a5bd7092fc2ccf23d70e1c3e2f36e90a1c6cb529f8072d890787ef1c",
  "source_path": "/srv/streaming/sample.txt"
}
```

Failures print to stderr and exit with code `1`, so shell pipelines can
branch on them:

```console
$ aranorm stream resume --source mutated.txt --output r.normalized.jsonl \
                        --checkpoint r.ckpt.json
Error: streaming session failed: checkpoint paths do not match this session
```

The full flag reference lives in [cli.md](cli.md); the flags that matter
most here are `--preset` (must match the checkpoint on resume), `--lock`,
`--batch-size`, `--workers`, and `--max-input-bytes` (default 1 GiB). Note
that the CLI builds its pipeline from `--preset` only — jobs needing a
custom `PipelineConfig` (dialect targets, stop words, per-flag overrides)
should use the Python API or a small `PipelineConfig.from_file` wrapper,
since a mismatched configuration is rejected by the pipeline fingerprint
check on resume.

---

## HTTP-triggered sessions

When AraNorm runs as a service (`aranorm serve`), the `POST /v1/stream`
endpoint exposes streaming to orchestrators — **disabled by default**. Enable
it with `--streaming-enabled` and confine it with `--streaming-root`:

```console
$ aranorm serve --host 127.0.0.1 --port 8765 \
                --streaming-enabled \
                --streaming-root /srv/streaming
```

A request names the three session paths plus optional tuning; `resume`
defaults to `true`:

```console
$ curl -s -X POST http://127.0.0.1:8765/v1/stream -H "Content-Type: application/json" \
       -d '{"source_path": "/srv/streaming/job1.txt",
             "output_path": "/srv/streaming/job1.normalized.jsonl",
             "checkpoint_path": "/srv/streaming/job1.ckpt.json", "batch_size": 32}'
```

```json
{
  "schema_version": 1,
  "report": {
    "source_fingerprint": "19ba3484a5bd7092fc2ccf23d70e1c3e2f36e90a1c6cb529f8072d890787ef1c",
    "pipeline_fingerprint": "e5144fa23504f33e7cc430627ba0ac536ba70e8690787250a19763d51628b3ed",
    "processed_count": 5, "next_index": 5,
    "resumed": false, "completed": true, "cancelled": false
  }
}
```

Behavior that differs from the Python API:

- **Locking is forced on** — the handler builds the session with
  `lock_enabled=True`, so concurrent requests for the same checkpoint tuple
cannot interleave writes; the loser gets `409 {"code": "stream_conflict"}`.
- **Paths are confined.** With `--streaming-root` set, every path is
  resolved (`realpath`) and must live inside that directory, or the request
  fails with `403 {"code": "stream_path_forbidden"}`. Without a root the
  endpoint accepts any readable path — never run it that way outside a
  tightly controlled machine. Relative paths resolve against the *server's*
  working directory, so prefer absolute paths.
- `batch_size`, `workers`, `max_input_bytes` must be positive integers and
  `resume` a boolean; violations return `422 invalid_request`.
- The session runs synchronously — the response arrives when it finishes.
  Reserve the endpoint for orchestration triggers; drive large jobs through
  the CLI or Python API.

The [deployment guide](deployment.md) covers the full endpoint surface and
hardening checklist.

---

## Limits and tuning

| Parameter | Default | Guidance |
|-----------|---------|----------|
| `max_input_bytes` | `1024**3` (1 GiB) | Hard ceiling on the source file size, checked before processing. Raise it deliberately for large snapshots; keep it tight when requests come from HTTP clients. |
| `batch_size` | `32` | Commit granularity. Larger batches amortize checkpoint fsyncs (faster) but lose more work on crash and block longer between cancellation checks. 32–256 is a sensible range for line-per-item corpora. |
| `n_workers` | `1` | Threads used by `process_iter` per batch. Normalization is regex/CPU-bound Python, so gains are modest and plateau quickly; measure before scaling. |
| `DEFAULT_CHECKPOINT_MAX_BYTES` | `1024**2` (1 MiB) | Cap enforced by `StreamCheckpoint.load`. Checkpoints are a few hundred bytes; hitting this cap means the file is not a checkpoint. |
| `DEFAULT_FINGERPRINT_CHUNK_BYTES` | `1024**2` (1 MiB) | Read-allocation size for SHA-256 passes (`fingerprint_file(..., chunk_bytes=...)`, minimum 1024). |
| `CHECKPOINT_SCHEMA_VERSION` | `1` | Bump this if you ever hand-craft future checkpoint formats; loaders reject other values. |

Throughput reference point: a 20,000-line corpus of short social-media-style
sentences (standard preset, `batch_size=32`, one worker) completed in ≈7.6 s
on a single container core — roughly 2,600 lines/s, dominated by the
normalization work itself rather than by checkpoint I/O. Fingerprinting the
same file costs one streaming pass over its bytes.

---

## Best practices checklist

- [ ] **Treat the source as immutable** — stage dated snapshot files; never
  append to a file an active session is reading.
- [ ] **One checkpoint tuple per (source, pipeline) pair** — the checkpoint
  name is the job identity; include the snapshot date if sources rotate.
- [ ] **Keep the three paths on one durable filesystem** (not ephemeral
  `/tmp` on runners) — atomicity assumes real fsync semantics.
- [ ] **Enable `--lock` whenever a second process could touch the
  checkpoint** — cron, CI retries, and humans all count.
- [ ] **Wrap jobs in a retry loop** — a completed session is an idempotent
  no-op; a crashed one resumes in seconds.
- [ ] **Handle the four exceptions distinctly** — conflict: wait;
  checkpoint: decide; source changed: re-stage; session error: investigate.
- [ ] **Prefer `resume=True`** — `resume=False` is only for deliberately
  redoing a job from scratch.
- [ ] **Judge completion by `report.completed` / `report.cancelled`**, not
  just the absence of exceptions.
- [ ] **Keep `batch_size` modest (32–256)** so crash losses and cancellation
  latency stay small relative to job length.
- [ ] **After a pipeline change, start a new checkpoint** and diff outputs
  rather than fighting the fingerprint guard.

---

*See also: [deployment.md](deployment.md) for serving AraNorm in production
(including HTTP-triggered sessions), and [cli.md](cli.md) for the full
command-line reference.*
