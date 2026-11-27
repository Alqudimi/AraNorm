"""Round 15 F2 — ``export_jsonl`` module-level convenience tests."""

from __future__ import annotations

import json

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.utils.exporters import _DEFAULT_FIELDS, export_jsonl


@pytest.fixture
def results():
    pipeline = ArabicNormalizationPipeline(PipelineConfig())
    return pipeline.process_batch(
        [
            "شلونك؟",
            "الحمد لله، شلونك انت؟",
        ],
    )


def test_export_jsonl_to_path_default_fields(results, tmp_path):
    path = tmp_path / "out.jsonl"
    count = export_jsonl(results, str(path))
    assert count == 2
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert set(first) == set(_DEFAULT_FIELDS)
    assert "شلونك؟" in str(first.get("original_text", ""))


def test_export_jsonl_field_projection(results, tmp_path):
    path = tmp_path / "proj.jsonl"
    fields = ["original_text", "normalized_text", "dialect"]
    count = export_jsonl(results, str(path), fields=fields)
    assert count == 2
    for line in path.read_text(encoding="utf-8").splitlines():
        assert list(json.loads(line).keys()) == fields


def test_export_jsonl_arabic_preserved(results, tmp_path):
    """ensure_ascii=False keeps Arabic characters literal."""
    path = tmp_path / "ar.jsonl"
    export_jsonl(results, str(path), ensure_ascii=False)
    raw = path.read_text(encoding="utf-8")
    assert "شلونك" in raw
    for line in raw.splitlines():
        obj = json.loads(line)
        assert obj["original_text"] == obj["original_text"].encode("utf-8").decode("utf-8")


def test_export_jsonl_to_stream(results):
    """Write into an already-open stream instead of a path."""
    import io

    buf = io.StringIO()
    count = export_jsonl(results, buf)
    assert count == 2
    lines = buf.getvalue().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["original_text"] == "الحمد لله، شلونك انت؟"


def test_export_jsonl_empty_results(tmp_path):
    path = tmp_path / "empty.jsonl"
    count = export_jsonl([], str(path))
    assert count == 0
    assert path.read_text(encoding="utf-8") == ""
