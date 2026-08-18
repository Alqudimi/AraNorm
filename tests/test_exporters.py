"""Tests for ``aranorm.utils.exporters`` (BatchExporter / SingleResultExporter).

These utilities were previously untested; this module verifies all export
formats (CSV, JSON, JSONL, pandas) and edge cases.
"""
from __future__ import annotations

import csv
import io
import json

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig
from aranorm.utils.exporters import BatchExporter

_TEXTS = [
    "شلونك حبيبي؟",
    "أنا سعيد جداً اليوم",
]


def _pipeline() -> ArabicNormalizationPipeline:
    return ArabicNormalizationPipeline(PipelineConfig())


def _results():
    return _pipeline().process_batch(_TEXTS)


# ── BatchExporter ────────────────────────────────────────────────────────────


class TestBatchExporterCore:
    def setup_method(self):
        self.results = _results()
        self.exporter = BatchExporter(self.results)

    def test_len_and_repr(self):
        assert len(self.exporter) == 2
        assert "results=2" in repr(self.exporter)
        assert "original_text" in repr(self.exporter)

    def test_default_fields(self):
        assert "original_text" in self.exporter.fields
        assert "normalized_text" in self.exporter.fields

    def test_custom_fields(self):
        exporter = BatchExporter(self.results, fields=["original_text", "dialect"])
        assert exporter.fields == ["original_text", "dialect"]

    def test_empty_results(self):
        exporter = BatchExporter([])
        assert len(exporter) == 0
        assert exporter.to_csv_string()

    def test_custom_delimiter(self):
        out = self.exporter.to_csv_string(delimiter=";")
        assert ";" in out
        assert "," not in out.splitlines()[0]


class TestBatchExporterCsv:
    def setup_method(self):
        self.exporter = BatchExporter(_results())

    def test_to_csv_writes_file(self, tmp_path):
        path = tmp_path / "out.csv"
        self.exporter.to_csv(str(path))
        assert path.exists()
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        assert len(rows) == 2
        assert rows[0]["original_text"] in _TEXTS

    def test_csv_header_order(self, tmp_path):
        path = tmp_path / "out.csv"
        self.exporter.to_csv(str(path))
        header = path.open(encoding="utf-8-sig").readline().strip()
        fields = header.split(",")
        assert fields == self.exporter.fields

    def test_csv_quoting(self, tmp_path):
        path = tmp_path / "out.csv"
        self.exporter.to_csv(str(path), quoting=csv.QUOTE_ALL)
        lines = path.open(encoding="utf-8-sig").read().splitlines()
        assert len(lines) == 3  # header + 2 rows
        # QUOTE_ALL quotes every field
        assert all(field.startswith('"') for field in lines[0].split(","))

    def test_arabic_characters_preserved(self, tmp_path):
        path = tmp_path / "out.csv"
        self.exporter.to_csv(str(path))
        content = path.read_text(encoding="utf-8")
        for text in _TEXTS:
            assert text in content

    def test_csv_string_roundtrip(self):
        out = self.exporter.to_csv_string()
        rows = list(csv.DictReader(io.StringIO(out)))
        assert len(rows) == 2
        assert rows[0]["original_text"] in _TEXTS

    def test_set_fields_serialized(self):
        results = ArabicNormalizationPipeline(
            PipelineConfig(
                stop_words_config=StopWordsConfig(mode="remove", scope="universal")
            )
        ).process_batch(["أنا سعيد جداً اليوم"])
        exporter = BatchExporter(results)
        row = next(csv.DictReader(io.StringIO(exporter.to_csv_string())))
        # stop_words_found (a Python set) is exported as a pipe-joined string
        found = row["stop_words_found"]
        assert any(w in found for w in ("انا", "جدا"))
        # separator must be the ASCII pipe, never the RTL box character
        assert "\u2502" not in found


class TestBatchExporterJson:
    def setup_method(self):
        self.exporter = BatchExporter(_results())

    def test_to_json_writes_file(self, tmp_path):
        path = tmp_path / "out.json"
        self.exporter.to_json(str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 2

    def test_json_indent(self, tmp_path):
        path = tmp_path / "out.json"
        self.exporter.to_json(str(path), indent=4)
        assert "    " in path.read_text(encoding="utf-8")

    def test_json_string(self):
        out = self.exporter.to_json_string()
        data = json.loads(out)
        assert len(data) == 2
        assert "original_text" in data[0]

    def test_ensure_ascii_true(self):
        out = self.exporter.to_json_string(ensure_ascii=True)
        # Non-ASCII characters must be escaped
        assert "\\u" in out


class TestBatchExporterJsonl:
    def setup_method(self):
        self.exporter = BatchExporter(_results())

    def test_to_jsonl_writes_file(self, tmp_path):
        path = tmp_path / "out.jsonl"
        self.exporter.to_jsonl(str(path))
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        assert len(lines) == 2

    def test_jsonl_string(self):
        out = self.exporter.to_jsonl_string()
        lines = [json.loads(line) for line in out.splitlines() if line]
        assert len(lines) == 2
        assert "normalized_text" in lines[0]

    def test_jsonl_empty_results(self):
        out = BatchExporter([]).to_jsonl_string()
        assert out == ""  # empty results produce no lines


class TestBatchExporterPandas:
    def test_to_dataframe_requires_pandas(self, monkeypatch):
        exporter = BatchExporter([])
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pandas":
                raise ImportError("pandas not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ImportError, match="pandas"):
            exporter.to_dataframe()

    def test_to_dataframe(self):
        pytest.importorskip("pandas")
        exporter = BatchExporter(_results())
        df = exporter.to_dataframe()
        assert list(df.columns) == exporter.fields
        assert len(df) == 2

