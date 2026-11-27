import json

import pytest

from aranorm import (
    ArabicNormalizationPipeline,
    CheckpointError,
    PipelineConfig,
    StreamCheckpoint,
    StreamingSession,
    StreamingSessionConflictError,
    StreamingSessionError,
    StreamingSourceChangedError,
)
from aranorm.core.streaming import DEFAULT_SESSION_LOCK_SUFFIX, _session_lock, fcntl
from aranorm.utils.exporters import StreamingBatchExporter


def _pipeline():
    return ArabicNormalizationPipeline(PipelineConfig(preset="standard"))


def test_lock_enabled_rejects_an_existing_local_session_owner(tmp_path):
    if fcntl is None:
        pytest.skip("advisory session locks are Unix-specific")
    source = tmp_path / "source.txt"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("نص\n", encoding="utf-8")
    lock_path = tmp_path / (checkpoint.name + DEFAULT_SESSION_LOCK_SUFFIX)
    with open(lock_path, "a+", encoding="utf-8") as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(StreamingSessionConflictError, match="another process owns"):
            StreamingSession(
                _pipeline(),
                str(source),
                str(tmp_path / "output.jsonl"),
                str(checkpoint),
                lock_enabled=True,
            ).run(resume=False)


def test_session_lock_is_released_after_write_failure(tmp_path, monkeypatch):
    if fcntl is None:
        pytest.skip("advisory session locks are Unix-specific")
    source = tmp_path / "source.txt"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("نص\n", encoding="utf-8")

    def fail_write(*args, **kwargs):
        raise OSError("injected write failure")

    monkeypatch.setattr(StreamingBatchExporter, "write_jsonl", fail_write)
    session = StreamingSession(
        _pipeline(),
        str(source),
        str(tmp_path / "output.jsonl"),
        str(checkpoint),
        lock_enabled=True,
    )
    with pytest.raises(StreamingSessionError, match="injected write failure"):
        session.run(resume=False)

    with _session_lock(str(checkpoint), True):
        pass


def test_session_fails_closed_when_source_changes_after_a_committed_batch(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("الأول\nالثاني\n", encoding="utf-8")
    original_write = StreamingBatchExporter.write_jsonl

    def write_then_mutate(exporter, results, target, ensure_ascii=False):
        count = original_write(exporter, results, target, ensure_ascii=ensure_ascii)
        source.write_text("الأول\nتغير المصدر\n", encoding="utf-8")
        return count

    monkeypatch.setattr(StreamingBatchExporter, "write_jsonl", write_then_mutate)
    with pytest.raises(StreamingSourceChangedError, match="source file changed"):
        StreamingSession(
            _pipeline(),
            str(source),
            str(output),
            str(checkpoint),
            batch_size=1,
        ).run(resume=False)

    with pytest.raises(CheckpointError, match="source fingerprint"):
        StreamingSession(_pipeline(), str(source), str(output), str(checkpoint)).run(resume=True)


def test_resume_truncates_uncommitted_output_tail_before_appending(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("الأول\nالثاني\n", encoding="utf-8")
    first_result = _pipeline().process("الأول")
    first_line = json.dumps(first_result.to_dict(), ensure_ascii=False) + "\n"
    output.write_text(first_line + "garbage tail\n", encoding="utf-8")
    checkpoint_obj = StreamCheckpoint(
        schema_version=1,
        source_path=str(source.resolve()),
        output_path=str(output.resolve()),
        source_fingerprint=__import__("aranorm").fingerprint_file(str(source)),
        pipeline_fingerprint=_pipeline().configuration_fingerprint(),
        next_index=1,
        output_bytes=len(first_line.encode("utf-8")),
        input_count=1,
        completed=False,
    )
    checkpoint_obj.write_atomic(str(checkpoint))

    report = StreamingSession(_pipeline(), str(source), str(output), str(checkpoint)).run(resume=True)

    assert report.completed is True
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert all("garbage" not in line for line in output.read_text(encoding="utf-8").splitlines())


def test_session_rejects_identical_artifact_paths(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("نص\n", encoding="utf-8")
    with pytest.raises(ValueError, match="paths must be distinct"):
        StreamingSession(_pipeline(), str(source), str(source), str(tmp_path / "checkpoint.json"))


def test_session_rejects_existing_symlink_aliases(tmp_path):
    source = tmp_path / "source.txt"
    output_link = tmp_path / "output.txt"
    source.write_text("نص\n", encoding="utf-8")
    output_link.symlink_to(source)
    with pytest.raises(ValueError, match="must not alias"):
        StreamingSession(_pipeline(), str(source), str(output_link), str(tmp_path / "checkpoint.json"))
