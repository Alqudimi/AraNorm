import hashlib
import json

import pytest

from aranorm import (
    ArabicNormalizationPipeline,
    CancellationToken,
    CheckpointError,
    PipelineConfig,
    StreamCheckpoint,
    StreamingSession,
    StreamingSessionError,
    fingerprint_file,
)
from aranorm.core.streaming import CHECKPOINT_SCHEMA_VERSION


def _pipeline():
    return ArabicNormalizationPipeline(PipelineConfig(preset="standard"))


def test_checkpoint_round_trip_and_unknown_field_rejection(tmp_path):
    checkpoint = StreamCheckpoint(
        schema_version=CHECKPOINT_SCHEMA_VERSION,
        source_path=str(tmp_path / "input.txt"),
        output_path=str(tmp_path / "output.jsonl"),
        source_fingerprint="a" * 64,
        pipeline_fingerprint="b" * 64,
        next_index=4,
        output_bytes=120,
        input_count=4,
        completed=False,
    )
    path = tmp_path / "checkpoint.json"
    checkpoint.write_atomic(str(path))
    assert StreamCheckpoint.load(str(path)) == checkpoint

    payload = checkpoint.to_dict()
    payload["unexpected"] = True
    with pytest.raises(CheckpointError, match="unknown checkpoint fields"):
        StreamCheckpoint.from_dict(payload)


def test_fingerprint_file_is_deterministic(tmp_path):
    path = tmp_path / "input.txt"
    path.write_text("ألف\nباء\n", encoding="utf-8")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert fingerprint_file(str(path)) == expected


def test_streaming_session_processes_jsonl_and_is_idempotent_on_resume(tmp_path):
    source = tmp_path / "input.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("النص الأول\nالنص الثاني\nالنص الثالث\n", encoding="utf-8")

    session = StreamingSession(_pipeline(), str(source), str(output), str(checkpoint), batch_size=2)
    first = session.run(resume=False)
    assert first.completed is True
    assert first.processed_count == 3
    assert first.next_index == 3
    assert first.resumed is False
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3
    assert StreamCheckpoint.load(str(checkpoint)).completed is True

    second = session.run(resume=True)
    assert second.completed is True
    assert second.resumed is True
    assert second.processed_count == 3
    assert len(output.read_text(encoding="utf-8").splitlines()) == 3


def test_streaming_session_resumes_from_durable_partial_checkpoint(tmp_path):
    source = tmp_path / "input.txt"
    output = tmp_path / "output.jsonl"
    checkpoint_path = tmp_path / "checkpoint.json"
    source.write_text("الأول\nالثاني\nالثالث\n", encoding="utf-8")
    pipeline = _pipeline()
    source_fingerprint = fingerprint_file(str(source))
    pipeline_fingerprint = pipeline.configuration_fingerprint()
    first_result = pipeline.process("الأول")
    first_line = json.dumps(first_result.to_dict(), ensure_ascii=False) + "\n"
    output.write_text(first_line, encoding="utf-8")
    StreamCheckpoint(
        schema_version=CHECKPOINT_SCHEMA_VERSION,
        source_path=str(source.resolve()),
        output_path=str(output.resolve()),
        source_fingerprint=source_fingerprint,
        pipeline_fingerprint=pipeline_fingerprint,
        next_index=1,
        output_bytes=len(first_line.encode("utf-8")),
        input_count=1,
        completed=False,
    ).write_atomic(str(checkpoint_path))

    report = StreamingSession(pipeline, str(source), str(output), str(checkpoint_path), batch_size=2).run()
    assert report.completed is True
    assert report.resumed is True
    assert report.processed_count == 3
    assert len(output.read_text(encoding="utf-8").splitlines()) == 3


def test_resume_rejects_changed_source(tmp_path):
    source = tmp_path / "input.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("ثابت\n", encoding="utf-8")
    session = StreamingSession(_pipeline(), str(source), str(output), str(checkpoint))
    session.run(resume=False)
    source.write_text("تغير\n", encoding="utf-8")
    with pytest.raises(CheckpointError, match="source fingerprint"):
        session.run(resume=True)


def test_cancelled_session_keeps_a_resumable_initial_checkpoint(tmp_path):
    source = tmp_path / "input.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("لن يبدأ\n", encoding="utf-8")
    token = CancellationToken()
    token.cancel()
    report = StreamingSession(_pipeline(), str(source), str(output), str(checkpoint), cancellation_token=token).run(
        resume=False
    )
    assert report.cancelled is True
    assert report.completed is False
    assert StreamCheckpoint.load(str(checkpoint)).next_index == 0
    assert output.read_text(encoding="utf-8") == ""


def test_session_enforces_input_size_limit(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("بيانات\n", encoding="utf-8")
    with pytest.raises(StreamingSessionError, match="size limit"):
        StreamingSession(
            _pipeline(),
            str(source),
            str(tmp_path / "out.jsonl"),
            str(tmp_path / "checkpoint.json"),
            max_input_bytes=1,
        ).run(resume=False)


def test_checkpoint_rejects_invalid_schema_and_invalid_offsets(tmp_path):
    with pytest.raises(CheckpointError, match="unsupported checkpoint schema"):
        StreamCheckpoint(
            schema_version=99,
            source_path="input.txt",
            output_path="output.jsonl",
            source_fingerprint="a" * 64,
            pipeline_fingerprint="b" * 64,
        )

    with pytest.raises(CheckpointError, match="next_index cannot"):
        StreamCheckpoint(
            schema_version=CHECKPOINT_SCHEMA_VERSION,
            source_path="input.txt",
            output_path="output.jsonl",
            source_fingerprint="a" * 64,
            pipeline_fingerprint="b" * 64,
            next_index=1,
            input_count=2,
        )
