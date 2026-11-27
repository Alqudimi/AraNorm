"""Resumable file-to-file streaming built on AraNorm's existing iterator APIs."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-Unix platforms
    fcntl = None  # type: ignore[assignment]

from aranorm.core.contracts import CancellationToken, ErrorHandler
from aranorm.core.pipeline import ArabicNormalizationPipeline
from aranorm.exceptions import (
    CheckpointError,
    ProcessingCancelledError,
    StreamingSessionConflictError,
    StreamingSessionError,
    StreamingSourceChangedError,
)
from aranorm.utils.exporters import StreamingBatchExporter

CHECKPOINT_SCHEMA_VERSION = 1
DEFAULT_CHECKPOINT_MAX_BYTES = 1024 * 1024
DEFAULT_FINGERPRINT_CHUNK_BYTES = 1024 * 1024
DEFAULT_SESSION_LOCK_SUFFIX = ".lock"


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckpointError(f"{field} must be a non-empty path")
    return value


def _validate_non_negative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CheckpointError(f"{field} must be a non-negative integer")
    return value


def fingerprint_file(path: str, *, chunk_bytes: int = DEFAULT_FINGERPRINT_CHUNK_BYTES) -> str:
    """Return a deterministic SHA-256 fingerprint of a UTF-8 input file."""
    if not isinstance(chunk_bytes, int) or isinstance(chunk_bytes, bool) or chunk_bytes < 1024:
        raise ValueError("chunk_bytes must be an integer >= 1024")
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(chunk_bytes)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _file_signature(path: str) -> Tuple[int, int, int, int]:
    """Return a lightweight identity signature for mutation checks."""
    stat = os.stat(path)
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


@contextmanager
def _session_lock(checkpoint_path: str, enabled: bool) -> Iterator[None]:
    """Guard one local session tuple with an optional Unix advisory lock."""
    if not enabled:
        yield
        return
    if fcntl is None:
        raise StreamingSessionError("session locking is unavailable on this platform")

    lock_path = os.path.abspath(checkpoint_path) + DEFAULT_SESSION_LOCK_SUFFIX
    os.makedirs(os.path.dirname(lock_path) or os.curdir, exist_ok=True)
    try:
        lock_stream = open(lock_path, "a+", encoding="utf-8")
    except OSError as exc:
        raise StreamingSessionError(f"cannot open streaming session lock: {exc}") from exc
    with lock_stream:
        try:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise StreamingSessionConflictError("another process owns this streaming session") from exc
            raise StreamingSessionError(f"cannot acquire streaming session lock: {exc}") from exc
        try:
            yield
        finally:
            try:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


@dataclass(frozen=True)
class StreamCheckpoint:
    """Durable progress marker for one input/output pair."""

    schema_version: int
    source_path: str
    output_path: str
    source_fingerprint: str
    pipeline_fingerprint: str
    next_index: int = 0
    output_bytes: int = 0
    input_count: int = 0
    completed: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise CheckpointError(f"unsupported checkpoint schema: {self.schema_version}")
        _validate_path(self.source_path, "source_path")
        _validate_path(self.output_path, "output_path")
        for field in ("source_fingerprint", "pipeline_fingerprint"):
            value = getattr(self, field)
            if not isinstance(value, str) or len(value) != 64:
                raise CheckpointError(f"{field} must be a SHA-256 hex string")
            try:
                int(value, 16)
            except ValueError as exc:
                raise CheckpointError(f"{field} must contain hexadecimal characters") from exc
        _validate_non_negative_int(self.next_index, "next_index")
        _validate_non_negative_int(self.output_bytes, "output_bytes")
        _validate_non_negative_int(self.input_count, "input_count")
        if self.next_index < self.input_count:
            raise CheckpointError("next_index cannot be smaller than input_count")
        if not isinstance(self.completed, bool):
            raise CheckpointError("completed must be boolean")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "source_fingerprint": self.source_fingerprint,
            "pipeline_fingerprint": self.pipeline_fingerprint,
            "next_index": self.next_index,
            "output_bytes": self.output_bytes,
            "input_count": self.input_count,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "StreamCheckpoint":
        if not isinstance(payload, dict):
            raise CheckpointError("checkpoint payload must be a JSON object")
        expected = set(cls.__dataclass_fields__)
        unknown = set(payload) - expected
        missing = expected - set(payload)
        if unknown:
            raise CheckpointError(f"unknown checkpoint fields: {sorted(unknown)}")
        if missing:
            raise CheckpointError(f"missing checkpoint fields: {sorted(missing)}")
        return cls(**payload)

    @classmethod
    def load(cls, path: str, *, max_bytes: int = DEFAULT_CHECKPOINT_MAX_BYTES) -> "StreamCheckpoint":
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 256:
            raise ValueError("max_bytes must be an integer >= 256")
        try:
            if os.path.getsize(path) > max_bytes:
                raise CheckpointError("checkpoint exceeds configured size limit")
            with open(path, "r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except CheckpointError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise CheckpointError(f"cannot load checkpoint: {exc}") from exc
        return cls.from_dict(payload)

    def write_atomic(self, path: str) -> None:
        """Write a checkpoint with a same-directory temporary file and replace."""
        target = os.path.abspath(path)
        directory = os.path.dirname(target) or os.curdir
        os.makedirs(directory, exist_ok=True)
        temporary: Optional[str] = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=".aranorm-checkpoint-", suffix=".tmp", dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.to_dict(), stream, ensure_ascii=False, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            temporary = None
        except OSError as exc:
            raise CheckpointError(f"cannot write checkpoint: {exc}") from exc
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass


@dataclass(frozen=True)
class StreamingSessionReport:
    """Outcome of one resumable streaming run."""

    source_path: str
    output_path: str
    checkpoint_path: str
    source_fingerprint: str
    pipeline_fingerprint: str
    processed_count: int
    next_index: int
    resumed: bool
    completed: bool
    cancelled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "output_path": self.output_path,
            "checkpoint_path": self.checkpoint_path,
            "source_fingerprint": self.source_fingerprint,
            "pipeline_fingerprint": self.pipeline_fingerprint,
            "processed_count": self.processed_count,
            "next_index": self.next_index,
            "resumed": self.resumed,
            "completed": self.completed,
            "cancelled": self.cancelled,
        }


class StreamingSession:
    """Process a UTF-8 JSONL/text input incrementally with safe resume semantics.

    The input is interpreted as one text item per line. The output is JSONL and
    each committed chunk is followed by an atomic checkpoint. A checkpoint is
    accepted only when source path, source SHA-256, output path, and pipeline
    configuration fingerprint all match the current invocation.
    """

    def __init__(
        self,
        pipeline: ArabicNormalizationPipeline,
        source_path: str,
        output_path: str,
        checkpoint_path: str,
        *,
        batch_size: int = 32,
        n_workers: int = 1,
        on_error: Optional[ErrorHandler] = None,
        cancellation_token: Optional[CancellationToken] = None,
        max_input_bytes: int = 1024 * 1024 * 1024,
        lock_enabled: bool = False,
    ) -> None:
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if not isinstance(n_workers, int) or isinstance(n_workers, bool) or n_workers < 1:
            raise ValueError("n_workers must be a positive integer")
        if not isinstance(max_input_bytes, int) or isinstance(max_input_bytes, bool) or max_input_bytes < 1:
            raise ValueError("max_input_bytes must be a positive integer")
        if not isinstance(lock_enabled, bool):
            raise ValueError("lock_enabled must be boolean")
        self.pipeline = pipeline
        self.source_path = os.path.abspath(source_path)
        self.output_path = os.path.abspath(output_path)
        self.checkpoint_path = os.path.abspath(checkpoint_path)
        self._validate_distinct_paths()
        self.batch_size = batch_size
        self.n_workers = n_workers
        self.on_error = on_error
        self.cancellation_token = cancellation_token
        self.max_input_bytes = max_input_bytes
        self.lock_enabled = lock_enabled

    def _validate_distinct_paths(self) -> None:
        """Reject direct or existing-file aliases between session artifacts."""
        paths = (self.source_path, self.output_path, self.checkpoint_path)
        if len(set(paths)) != len(paths):
            raise ValueError("source, output, and checkpoint paths must be distinct")
        existing = [(index, path) for index, path in enumerate(paths) if os.path.exists(path)]
        for left_index, left_path in existing:
            for right_index, right_path in existing:
                if left_index >= right_index:
                    continue
                try:
                    aliased = os.path.samefile(left_path, right_path)
                except OSError:
                    aliased = False
                if aliased:
                    raise ValueError("source, output, and checkpoint paths must not alias the same file")

    def _validate_checkpoint(
        self, checkpoint: StreamCheckpoint, source_fingerprint: str, pipeline_fingerprint: str
    ) -> None:
        if checkpoint.source_path != self.source_path or checkpoint.output_path != self.output_path:
            raise CheckpointError("checkpoint paths do not match this session")
        if checkpoint.source_fingerprint != source_fingerprint:
            raise CheckpointError("source fingerprint does not match checkpoint")
        if checkpoint.pipeline_fingerprint != pipeline_fingerprint:
            raise CheckpointError("pipeline fingerprint does not match checkpoint")
        try:
            output_size = os.path.getsize(self.output_path)
        except OSError as exc:
            raise CheckpointError("checkpoint output file does not exist") from exc
        if checkpoint.output_bytes > output_size:
            raise CheckpointError("checkpoint output offset exceeds output size")

    def _assert_source_unchanged(self, fingerprint: str, signature: Tuple[int, int, int, int]) -> None:
        """Fail closed when a source mutation is observed during a run."""
        try:
            current_signature = _file_signature(self.source_path)
        except OSError as exc:
            raise StreamingSourceChangedError("source file became unavailable during streaming") from exc
        if current_signature == signature:
            return
        try:
            current_fingerprint = fingerprint_file(self.source_path)
        except OSError as exc:
            raise StreamingSourceChangedError("source file became unavailable during streaming") from exc
        if current_fingerprint != fingerprint:
            raise StreamingSourceChangedError("source file changed during streaming")

    def _read_lines(self, start: int) -> Iterator[str]:
        with open(self.source_path, "r", encoding="utf-8") as stream:
            for index, line in enumerate(stream):
                if index < start:
                    continue
                yield line.rstrip("\r\n")

    def run(self, *, resume: bool = True) -> StreamingSessionReport:
        """Run or resume the session and return a durable progress report."""
        with _session_lock(self.checkpoint_path, self.lock_enabled):
            return self._run_unlocked(resume=resume)

    def _run_unlocked(self, *, resume: bool = True) -> StreamingSessionReport:
        """Execute one session after its optional concurrency guard is held."""
        if not os.path.isfile(self.source_path):
            raise StreamingSessionError(f"source file does not exist: {self.source_path}")
        if os.path.getsize(self.source_path) > self.max_input_bytes:
            raise StreamingSessionError("source file exceeds configured size limit")
        source_signature = _file_signature(self.source_path)
        source_fingerprint = fingerprint_file(self.source_path)
        self._assert_source_unchanged(source_fingerprint, source_signature)
        pipeline_fingerprint = self.pipeline.configuration_fingerprint()
        resumed = False
        checkpoint: Optional[StreamCheckpoint] = None
        if resume and os.path.exists(self.checkpoint_path):
            checkpoint = StreamCheckpoint.load(self.checkpoint_path)
            self._validate_checkpoint(checkpoint, source_fingerprint, pipeline_fingerprint)
            resumed = True
            if checkpoint.completed:
                return StreamingSessionReport(
                    self.source_path,
                    self.output_path,
                    self.checkpoint_path,
                    source_fingerprint,
                    pipeline_fingerprint,
                    checkpoint.input_count,
                    checkpoint.next_index,
                    True,
                    True,
                )
        output_dir = os.path.dirname(self.output_path) or os.curdir
        os.makedirs(output_dir, exist_ok=True)
        start = checkpoint.next_index if checkpoint else 0
        mode = "r+" if resumed else "w"
        try:
            with open(self.output_path, mode, encoding="utf-8") as output:
                if resumed and checkpoint is not None:
                    output.seek(checkpoint.output_bytes)
                    output.truncate()
                initial = checkpoint or StreamCheckpoint(
                    CHECKPOINT_SCHEMA_VERSION,
                    self.source_path,
                    self.output_path,
                    source_fingerprint,
                    pipeline_fingerprint,
                    next_index=0,
                    output_bytes=0,
                    input_count=0,
                    completed=False,
                )
                if checkpoint is None:
                    initial.write_atomic(self.checkpoint_path)
                processed = initial.input_count
                index = start
                lines = self._read_lines(start)
                exporter = StreamingBatchExporter()
                while True:
                    self._assert_source_unchanged(source_fingerprint, source_signature)
                    if self.cancellation_token is not None and self.cancellation_token.is_cancelled:
                        return StreamingSessionReport(
                            self.source_path,
                            self.output_path,
                            self.checkpoint_path,
                            source_fingerprint,
                            pipeline_fingerprint,
                            processed,
                            index,
                            resumed,
                            False,
                            True,
                        )
                    chunk: List[str] = []
                    for _ in range(self.batch_size):
                        try:
                            chunk.append(next(lines))
                        except StopIteration:
                            break
                    if not chunk:
                        final = StreamCheckpoint(
                            CHECKPOINT_SCHEMA_VERSION,
                            self.source_path,
                            self.output_path,
                            source_fingerprint,
                            pipeline_fingerprint,
                            next_index=index,
                            output_bytes=output.tell(),
                            input_count=processed,
                            completed=True,
                        )
                        final.write_atomic(self.checkpoint_path)
                        return StreamingSessionReport(
                            self.source_path,
                            self.output_path,
                            self.checkpoint_path,
                            source_fingerprint,
                            pipeline_fingerprint,
                            processed,
                            index,
                            resumed,
                            True,
                        )
                    results = list(
                        self.pipeline.process_iter(
                            chunk,
                            batch_size=self.batch_size,
                            n_workers=self.n_workers,
                            on_error=self.on_error,
                            cancellation_token=self.cancellation_token,
                        )
                    )
                    if self.cancellation_token is not None and self.cancellation_token.is_cancelled:
                        return StreamingSessionReport(
                            self.source_path,
                            self.output_path,
                            self.checkpoint_path,
                            source_fingerprint,
                            pipeline_fingerprint,
                            processed,
                            index,
                            resumed,
                            False,
                            True,
                        )
                    self._assert_source_unchanged(source_fingerprint, source_signature)
                    written_count = exporter.write_jsonl(results, output)
                    output.flush()
                    os.fsync(output.fileno())
                    index += len(chunk)
                    processed += written_count
                    committed = StreamCheckpoint(
                        CHECKPOINT_SCHEMA_VERSION,
                        self.source_path,
                        self.output_path,
                        source_fingerprint,
                        pipeline_fingerprint,
                        next_index=index,
                        output_bytes=output.tell(),
                        input_count=processed,
                        completed=False,
                    )
                    committed.write_atomic(self.checkpoint_path)
        except ProcessingCancelledError:
            raise
        except (OSError, UnicodeError) as exc:
            raise StreamingSessionError(f"streaming session failed: {exc}") from exc


__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "DEFAULT_CHECKPOINT_MAX_BYTES",
    "DEFAULT_FINGERPRINT_CHUNK_BYTES",
    "DEFAULT_SESSION_LOCK_SUFFIX",
    "StreamCheckpoint",
    "StreamingSession",
    "StreamingSessionReport",
    "fingerprint_file",
]
