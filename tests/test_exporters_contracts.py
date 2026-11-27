"""Contract tests for batch and streaming exporters."""

import csv
import io
import json
from pathlib import Path

import pytest

from aranorm.core.pipeline import NormalizationResult
from aranorm.utils.exporters import BatchExporter, StreamingBatchExporter


def _results() -> list[NormalizationResult]:
    return [
        NormalizationResult(
            original_text="شلونك؟",
            normalized_text="شلونك",
            dialect="GLF",
            dialect_confidence=0.91,
            applied_steps=["cleaner", "dialect"],
            stop_words_removed="شلونك",
            stop_words_found={"من", "في"},
        ),
        NormalizationResult(
            original_text="أنا سعيد",
            normalized_text="انا سعيد",
            dialect="MSA",
            dialect_confidence=0.88,
            applied_steps=["unicode"],
            stop_words_found=frozenset(),
        ),
    ]


def test_batch_exporter_serializes_rows_and_custom_fields(tmp_path: Path) -> None:
    results = _results()
    fields = ["original_text", "normalized_text", "applied_steps", "stop_words_found", "missing"]
    exporter = BatchExporter(results, fields=fields)

    csv_text = exporter.to_csv_string()
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(exporter) == 2
    assert "شلونك" in csv_text
    assert rows[0]["applied_steps"] == "cleaner|dialect"
    assert rows[0]["stop_words_found"] == "في|من"
    assert rows[1]["stop_words_found"] == ""
    assert rows[0]["missing"] == ""
    assert "BatchExporter(results=2" in repr(exporter)


def test_batch_exporter_keeps_steps_trace_structured_in_json() -> None:
    result = NormalizationResult(
        original_text="نص",
        normalized_text="نص",
        dialect="MSA",
        steps_trace=[("cleaner", "applied"), ("dialect", "applied")],
    )
    payload = json.loads(BatchExporter([result], fields=["steps_trace"]).to_json_string())
    assert payload[0]["steps_trace"] == [["cleaner", "applied"], ["dialect", "applied"]]


def test_batch_exporter_writes_csv_json_and_jsonl_files(tmp_path: Path) -> None:
    exporter = BatchExporter(_results())
    csv_path = tmp_path / "results.csv"
    json_path = tmp_path / "results.json"
    jsonl_path = tmp_path / "results.jsonl"

    exporter.to_csv(str(csv_path))
    exporter.to_json(str(json_path))
    exporter.to_jsonl(str(jsonl_path))

    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    csv_rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    assert len(csv_rows) == 2
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload[0]["dialect"] == "GLF"
    assert "شلونك" in json_path.read_text(encoding="utf-8")
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["dialect"] == "MSA"


def test_batch_exporter_string_formats_handle_empty_results() -> None:
    exporter = BatchExporter([])

    assert exporter.to_json_string() == "[]"
    assert exporter.to_jsonl_string() == ""
    assert exporter.to_csv_string().splitlines()[0].startswith("original_text")


def test_batch_exporter_dataframe_is_optional() -> None:
    pandas = pytest.importorskip("pandas")
    frame = BatchExporter(_results(), fields=["dialect", "normalized_text"]).to_dataframe()

    assert isinstance(frame, pandas.DataFrame)
    assert list(frame.columns) == ["dialect", "normalized_text"]
    assert frame.to_dict("records")[0]["dialect"] == "GLF"


def test_streaming_exporter_writes_all_formats_to_memory() -> None:
    exporter = StreamingBatchExporter(fields=["original_text", "normalized_text", "dialect"])
    results = _results()

    jsonl = io.StringIO()
    csv_output = io.StringIO()
    json_output = io.StringIO()
    assert exporter.write_jsonl(iter(results), jsonl) == 2
    assert exporter.write_csv(iter(results), csv_output) == 2
    assert exporter.write_json(iter(results), json_output, indent=2) == 2

    assert [json.loads(line)["dialect"] for line in jsonl.getvalue().splitlines()] == ["GLF", "MSA"]
    assert len(list(csv.DictReader(io.StringIO(csv_output.getvalue())))) == 2
    assert json.loads(json_output.getvalue())[1]["normalized_text"] == "انا سعيد"
    assert "StreamingBatchExporter(fields=" in repr(exporter)


def test_streaming_exporter_dispatches_formats_and_supports_paths(tmp_path: Path) -> None:
    exporter = StreamingBatchExporter(fields=["dialect"])
    expected = {"csv": "csv", "json": "json", "jsonl": "jsonl"}

    for fmt, suffix in expected.items():
        path = tmp_path / f"out.{suffix}"
        count = exporter.write(iter(_results()), path, format=fmt)
        assert count == 2
        assert path.read_text(encoding="utf-8-sig" if fmt == "csv" else "utf-8")

    with pytest.raises(ValueError, match="format must be one of"):
        exporter.write(_results(), io.StringIO(), format="xml")  # type: ignore[arg-type]


def test_streaming_json_has_valid_empty_and_compact_shapes() -> None:
    exporter = StreamingBatchExporter(fields=["dialect"])
    pretty = io.StringIO()
    compact = io.StringIO()

    assert exporter.write_json([], pretty, indent=2) == 0
    assert exporter.write_json([], compact, indent=None) == 0
    assert json.loads(pretty.getvalue()) == []
    assert json.loads(compact.getvalue()) == []
