import errno
import hashlib
import json

import pytest

import aranorm.core.streaming as streaming_module
from aranorm import (
    ArabicNormalizationPipeline,
    CancellationToken,
    CheckpointError,
    PipelineConfig,
    ProcessingCancelledError,
    StreamCheckpoint,
    StreamingSession,
    StreamingSessionError,
    StreamingSessionReport,
)


def _pipeline():
    return ArabicNormalizationPipeline(PipelineConfig(preset="standard"))


def _checkpoint(source, output, pipeline_fingerprint="b" * 64, **overrides):
    payload = {
        "schema_version": 1,
        "source_path": str(source.resolve()),
        "output_path": str(output.resolve()),
        "source_fingerprint": "a" * 64,
        "pipeline_fingerprint": pipeline_fingerprint,
        "next_index": 0,
        "output_bytes": 0,
        "input_count": 0,
        "completed": False,
    }
    payload.update(overrides)
    return StreamCheckpoint(**payload)


def test_private_validation_helpers_and_fingerprint_boundaries(tmp_path):
    source = tmp_path / "empty.txt"
    source.write_bytes(b"")

    assert streaming_module._canonical_json({"b": 1, "a": "ع"}) == '{"a":"ع","b":1}'
    assert streaming_module.fingerprint_file(str(source)) == hashlib.sha256(b"").hexdigest()

    with pytest.raises(CheckpointError, match="non-empty path"):
        streaming_module._validate_path("   ", "source_path")
    with pytest.raises(CheckpointError, match="non-negative integer"):
        streaming_module._validate_non_negative_int(True, "next_index")
    with pytest.raises(ValueError, match="chunk_bytes"):
        streaming_module.fingerprint_file(str(source), chunk_bytes=1023)
    with pytest.raises(ValueError, match="max_bytes"):
        StreamCheckpoint.load(str(source), max_bytes=255)


def test_checkpoint_load_rejects_oversized_and_malformed_payloads(tmp_path):
    oversized = tmp_path / "oversized.json"
    oversized.write_text("x" * 300, encoding="utf-8")
    with pytest.raises(CheckpointError, match="size limit"):
        StreamCheckpoint.load(str(oversized), max_bytes=256)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    with pytest.raises(CheckpointError, match="cannot load checkpoint"):
        StreamCheckpoint.load(str(malformed))

    with pytest.raises(CheckpointError, match="JSON object"):
        StreamCheckpoint.from_dict([])
    with pytest.raises(CheckpointError, match="hexadecimal"):
        _checkpoint(tmp_path / "source", tmp_path / "output", source_fingerprint="z" * 64)


def test_checkpoint_write_cleans_temporary_file_after_replace_failure(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    target = tmp_path / "state.json"
    source.write_text("نص\n", encoding="utf-8")
    checkpoint = _checkpoint(source, output)

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(streaming_module.os, "replace", fail_replace)
    with pytest.raises(CheckpointError, match="replace failed"):
        checkpoint.write_atomic(str(target))
    assert not list(tmp_path.glob(".aranorm-checkpoint-*.tmp"))


def test_session_constructor_rejects_invalid_operational_options(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "state.json"
    session_args = (_pipeline(), str(source), str(output), str(checkpoint))

    with pytest.raises(ValueError, match="batch_size"):
        StreamingSession(*session_args, batch_size=0)
    with pytest.raises(ValueError, match="n_workers"):
        StreamingSession(*session_args, n_workers=0)
    with pytest.raises(ValueError, match="max_input_bytes"):
        StreamingSession(*session_args, max_input_bytes=0)
    with pytest.raises(ValueError, match="lock_enabled"):
        StreamingSession(*session_args, lock_enabled="yes")


def test_session_rejects_missing_and_oversized_sources(tmp_path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(StreamingSessionError, match="does not exist"):
        StreamingSession(_pipeline(), str(missing), str(tmp_path / "out.jsonl"), str(tmp_path / "state.json")).run(
            resume=False
        )

    oversized = tmp_path / "oversized.txt"
    oversized.write_text("نص\n", encoding="utf-8")
    with pytest.raises(StreamingSessionError, match="size limit"):
        StreamingSession(
            _pipeline(), str(oversized), str(tmp_path / "out.jsonl"), str(tmp_path / "state.json"), max_input_bytes=1
        ).run(resume=False)


def test_completed_checkpoint_returns_without_reopening_output(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    checkpoint_path = tmp_path / "state.json"
    source.write_text("نص\n", encoding="utf-8")
    output.write_text("already committed\n", encoding="utf-8")
    pipeline = _pipeline()
    checkpoint = StreamCheckpoint(
        schema_version=1,
        source_path=str(source.resolve()),
        output_path=str(output.resolve()),
        source_fingerprint=streaming_module.fingerprint_file(str(source)),
        pipeline_fingerprint=pipeline.configuration_fingerprint(),
        next_index=1,
        output_bytes=output.stat().st_size,
        input_count=1,
        completed=True,
    )
    checkpoint.write_atomic(str(checkpoint_path))

    report = StreamingSession(pipeline, str(source), str(output), str(checkpoint_path)).run(resume=True)

    assert isinstance(report, StreamingSessionReport)
    assert report.completed is True
    assert report.resumed is True
    assert report.processed_count == 1


def test_resume_rejects_missing_or_too_short_output(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    checkpoint_path = tmp_path / "state.json"
    source.write_text("نص\n", encoding="utf-8")
    pipeline = _pipeline()

    checkpoint = StreamCheckpoint(
        schema_version=1,
        source_path=str(source.resolve()),
        output_path=str(output.resolve()),
        source_fingerprint=streaming_module.fingerprint_file(str(source)),
        pipeline_fingerprint=pipeline.configuration_fingerprint(),
        next_index=1,
        output_bytes=0,
        input_count=1,
        completed=False,
    )
    checkpoint.write_atomic(str(checkpoint_path))
    with pytest.raises(CheckpointError, match="does not exist"):
        StreamingSession(pipeline, str(source), str(output), str(checkpoint_path)).run(resume=True)

    output.write_text("x", encoding="utf-8")
    checkpoint = StreamCheckpoint(
        schema_version=1,
        source_path=str(source.resolve()),
        output_path=str(output.resolve()),
        source_fingerprint=streaming_module.fingerprint_file(str(source)),
        pipeline_fingerprint=pipeline.configuration_fingerprint(),
        next_index=1,
        output_bytes=2,
        input_count=1,
        completed=False,
    )
    checkpoint.write_atomic(str(checkpoint_path))
    with pytest.raises(CheckpointError, match="exceeds output size"):
        StreamingSession(pipeline, str(source), str(output), str(checkpoint_path)).run(resume=True)


def test_empty_source_and_pre_cancelled_session_are_durable(tmp_path):
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "state.json"
    completed = StreamingSession(_pipeline(), str(source), str(output), str(checkpoint)).run(resume=False)
    assert completed.completed is True
    assert completed.processed_count == 0
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["completed"] is True

    cancelled_source = tmp_path / "cancelled.txt"
    cancelled_source.write_text("نص\n", encoding="utf-8")
    token = CancellationToken()
    token.cancel()
    cancelled = StreamingSession(
        _pipeline(),
        str(cancelled_source),
        str(tmp_path / "cancelled.jsonl"),
        str(tmp_path / "cancelled.state"),
        cancellation_token=token,
    ).run(resume=False)
    assert cancelled.cancelled is True
    assert cancelled.completed is False
    assert cancelled.processed_count == 0


def test_processing_cancelled_error_is_re_raised(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text("نص\n", encoding="utf-8")
    session = StreamingSession(_pipeline(), str(source), str(tmp_path / "out.jsonl"), str(tmp_path / "state.json"))

    def cancel(*args, **kwargs):
        raise ProcessingCancelledError("cancelled by processor")

    monkeypatch.setattr(session.pipeline, "process_iter", cancel)
    with pytest.raises(ProcessingCancelledError, match="cancelled by processor"):
        session.run(resume=False)


def test_session_lock_error_paths_and_unlock_cleanup(tmp_path, monkeypatch):
    if streaming_module.fcntl is None:
        pytest.skip("advisory session locks are Unix-specific")
    checkpoint_path = str(tmp_path / "state.json")

    def fail_open(*args, **kwargs):
        raise OSError("lock open failed")

    monkeypatch.setattr(streaming_module, "open", fail_open, raising=False)
    with pytest.raises(StreamingSessionError, match="lock open failed"):
        with streaming_module._session_lock(checkpoint_path, True):
            pass

    monkeypatch.undo()

    def fail_flock(*args, **kwargs):
        raise OSError(errno.EBADF, "bad descriptor")

    monkeypatch.setattr(streaming_module.fcntl, "flock", fail_flock)
    with pytest.raises(StreamingSessionError, match="cannot acquire"):
        with streaming_module._session_lock(checkpoint_path, True):
            pass

    monkeypatch.undo()
    calls = []
    original_flock = streaming_module.fcntl.flock

    def release_failure(fd, operation):
        calls.append(operation)
        if len(calls) == 2:
            raise OSError("unlock failed")
        return original_flock(fd, operation)

    monkeypatch.setattr(streaming_module.fcntl, "flock", release_failure)
    with streaming_module._session_lock(checkpoint_path, True):
        pass
    assert len(calls) == 2


def test_session_lock_unavailable_is_typed(tmp_path, monkeypatch):
    monkeypatch.setattr(streaming_module, "fcntl", None)
    with pytest.raises(StreamingSessionError, match="unavailable"):
        with streaming_module._session_lock(str(tmp_path / "state.json"), True):
            pass


def test_source_unavailability_during_guard_is_fail_closed(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text("نص\n", encoding="utf-8")
    session = StreamingSession(_pipeline(), str(source), str(tmp_path / "out.jsonl"), str(tmp_path / "state.json"))
    original_signature = streaming_module._file_signature
    calls = {"count": 0}

    def unavailable(path):
        calls["count"] += 1
        if calls["count"] == 1:
            return original_signature(path)
        raise OSError("source disappeared")

    monkeypatch.setattr(streaming_module, "_file_signature", unavailable)
    with pytest.raises(streaming_module.StreamingSourceChangedError, match="unavailable"):
        session.run(resume=False)


def test_source_fingerprint_failure_during_guard_is_fail_closed(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text("نص\n", encoding="utf-8")
    session = StreamingSession(_pipeline(), str(source), str(tmp_path / "out.jsonl"), str(tmp_path / "state.json"))
    original_signature = streaming_module._file_signature
    original_fingerprint = streaming_module.fingerprint_file
    signature_calls = {"count": 0}
    fingerprint_calls = {"count": 0}

    def changed_signature(path):
        signature_calls["count"] += 1
        value = original_signature(path)
        if signature_calls["count"] == 1:
            return value
        return (value[0], value[1], value[2] + 1, value[3])

    def unavailable_fingerprint(path, **kwargs):
        fingerprint_calls["count"] += 1
        if fingerprint_calls["count"] == 1:
            return original_fingerprint(path, **kwargs)
        raise OSError("fingerprint unavailable")

    monkeypatch.setattr(streaming_module, "_file_signature", changed_signature)
    monkeypatch.setattr(streaming_module, "fingerprint_file", unavailable_fingerprint)
    with pytest.raises(streaming_module.StreamingSourceChangedError, match="unavailable"):
        session.run(resume=False)


def test_non_eagain_lock_failure_is_wrapped(tmp_path, monkeypatch):
    if streaming_module.fcntl is None:
        pytest.skip("advisory session locks are Unix-specific")

    def fail_flock(*args, **kwargs):
        raise OSError(errno.EBADF, "bad descriptor")

    monkeypatch.setattr(streaming_module.fcntl, "flock", fail_flock)
    with pytest.raises(StreamingSessionError, match="cannot acquire"):
        with streaming_module._session_lock(str(tmp_path / "state.json"), True):
            pass


def test_checkpoint_validation_rejects_invalid_hash_length_and_non_boolean_completed(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    with pytest.raises(CheckpointError, match="SHA-256 hex string"):
        _checkpoint(source, output, source_fingerprint="a")

    payload = _checkpoint(source, output).to_dict()
    payload["completed"] = 1
    with pytest.raises(CheckpointError, match="completed must be boolean"):
        StreamCheckpoint.from_dict(payload)


def test_checkpoint_from_dict_rejects_missing_fields(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    payload = _checkpoint(source, output).to_dict()
    payload.pop("output_bytes")
    with pytest.raises(CheckpointError, match="missing checkpoint fields"):
        StreamCheckpoint.from_dict(payload)


def test_checkpoint_cleanup_ignores_unlink_failure(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    target = tmp_path / "state.json"
    checkpoint = _checkpoint(source, output)

    def fail_replace(*args, **kwargs):
        raise OSError("replace failed")

    def fail_unlink(*args, **kwargs):
        raise OSError("unlink failed")

    monkeypatch.setattr(streaming_module.os, "replace", fail_replace)
    monkeypatch.setattr(streaming_module.os, "unlink", fail_unlink)
    with pytest.raises(CheckpointError, match="replace failed"):
        checkpoint.write_atomic(str(target))


def test_distinct_path_validation_handles_samefile_oserror(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    source.write_text("نص\n", encoding="utf-8")
    output.write_text("out\n", encoding="utf-8")

    def samefile_failure(*args, **kwargs):
        raise OSError("samefile unavailable")

    monkeypatch.setattr(streaming_module.os.path, "samefile", samefile_failure)
    session = StreamingSession(_pipeline(), str(source), str(output), str(tmp_path / "state.json"))
    assert session.source_path != session.output_path


def test_resume_rejects_checkpoint_path_and_pipeline_mismatches(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    checkpoint_path = tmp_path / "state.json"
    source.write_text("نص\n", encoding="utf-8")
    output.write_text("{}\n", encoding="utf-8")
    pipeline = _pipeline()

    path_mismatch = StreamCheckpoint(
        schema_version=1,
        source_path=str(source.resolve()),
        output_path=str((tmp_path / "other.jsonl").resolve()),
        source_fingerprint=streaming_module.fingerprint_file(str(source)),
        pipeline_fingerprint=pipeline.configuration_fingerprint(),
        next_index=0,
        output_bytes=0,
        input_count=0,
        completed=False,
    )
    path_mismatch.write_atomic(str(checkpoint_path))
    with pytest.raises(CheckpointError, match="paths do not match"):
        StreamingSession(pipeline, str(source), str(output), str(checkpoint_path)).run(resume=True)

    pipeline_mismatch = StreamCheckpoint(
        schema_version=1,
        source_path=str(source.resolve()),
        output_path=str(output.resolve()),
        source_fingerprint=streaming_module.fingerprint_file(str(source)),
        pipeline_fingerprint="b" * 64,
        next_index=0,
        output_bytes=0,
        input_count=0,
        completed=False,
    )
    pipeline_mismatch.write_atomic(str(checkpoint_path))
    with pytest.raises(CheckpointError, match="pipeline fingerprint"):
        StreamingSession(pipeline, str(source), str(output), str(checkpoint_path)).run(resume=True)


def test_cancellation_after_process_iter_keeps_last_checkpoint(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "state.json"
    source.write_text("نص\n", encoding="utf-8")
    token = CancellationToken()
    session = StreamingSession(
        _pipeline(), str(source), str(output), str(checkpoint), cancellation_token=token, batch_size=1
    )

    def process_and_cancel(*args, **kwargs):
        token.cancel()
        return []

    monkeypatch.setattr(session.pipeline, "process_iter", process_and_cancel)
    report = session.run(resume=False)
    assert report.cancelled is True
    assert report.completed is False
    assert StreamCheckpoint.load(str(checkpoint)).completed is False
