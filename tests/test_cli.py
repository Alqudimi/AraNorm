"""Tests for the command-line interface."""

from __future__ import annotations

import json


from aranorm.cli import main


class TestCLIInfo:
    def test_info_runs_successfully(self, capsys) -> None:
        rc = main(["info"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "AraNorm" in out

    def test_info_json_output(self, capsys) -> None:
        rc = main(["info", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "version" in data
        assert "stop_words" in data


class TestCLINormalize:
    def test_normalize_basic_text(self, capsys) -> None:
        rc = main(["normalize", "أنا أحب العربية"])
        assert rc == 0
        out = capsys.readouterr().out
        assert len(out.strip()) > 0

    def test_normalize_removes_diacritics_by_default(self, capsys) -> None:
        rc = main(["normalize", "مَرْحَبًا"])
        assert rc == 0
        out = capsys.readouterr().out
        # diacritics should be removed
        assert "َ" not in out
        assert "ْ" not in out

    def test_normalize_preset_light(self, capsys) -> None:
        rc = main(["normalize", "--preset", "light", "أنا هنا"])
        assert rc == 0

    def test_normalize_preset_deep(self, capsys) -> None:
        rc = main(["normalize", "--preset", "deep", "أهلاً وسهلاً"])
        assert rc == 0

    def test_normalize_json_output(self, capsys) -> None:
        rc = main(["normalize", "--json", "أنا سعيد"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert "normalized" in data[0]
        assert "original" in data[0]

    def test_normalize_with_stop_words(self, capsys) -> None:
        rc = main(["normalize", "--stop-words", "أنا سعيد جداً اليوم"])
        assert rc == 0

    def test_normalize_keep_diacritics(self, capsys) -> None:
        rc = main(["normalize", "--keep-diacritics", "مَرْحَبًا"])
        assert rc == 0
        out = capsys.readouterr().out
        # with keep-diacritics, diacritics should remain
        assert "مرحبا" in out or "مَ" in out

    def test_normalize_missing_file_returns_error(self) -> None:
        rc = main(["normalize", "--file", "/nonexistent/path/file.txt"])
        assert rc == 1


class TestCLIStopWords:
    def test_stopwords_basic(self, capsys) -> None:
        rc = main(["stopwords", "أنا سعيد جداً اليوم"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "أنا" in out or "Cleaned" in out

    def test_stopwords_json_output(self, capsys) -> None:
        rc = main(["stopwords", "--json", "أنا سعيد من"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "stop_words_found" in data
        assert "original" in data

    def test_stopwords_highlight_mode(self, capsys) -> None:
        rc = main(["stopwords", "--mode", "highlight", "أنا سعيد"])
        assert rc == 0

    def test_stopwords_count_mode(self, capsys) -> None:
        rc = main(["stopwords", "--mode", "count", "أنا في البيت"])
        assert rc == 0


class TestCLIAnalyze:
    def test_analyze_basic(self, capsys) -> None:
        rc = main(["analyze", "أنا أحب اللغة العربية"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Word count" in out

    def test_analyze_json_output(self, capsys) -> None:
        rc = main(["analyze", "--json", "أنا أحب اللغة"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "word_count" in data
        assert "readability_score" in data
        assert "arabic_ratio" in data

    def test_analyze_top_words(self, capsys) -> None:
        rc = main(["analyze", "--json", "اللغة اللغة اللغة العربية"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "top_words" in data


class TestCLIBatchStreaming:
    def test_batch_streaming_jsonl_to_output_file(self, tmp_path, capsys) -> None:
        input_path = tmp_path / "input.txt"
        output_path = tmp_path / "output.jsonl"
        input_path.write_text("أحمد\n\nإبراهيم\n", encoding="utf-8")

        rc = main(
            [
                "batch",
                "--file",
                str(input_path),
                "--output",
                str(output_path),
                "--stream",
                "--batch-size",
                "1",
                "--format",
                "jsonl",
            ]
        )

        assert rc == 0
        assert "Wrote 2 results" in capsys.readouterr().out
        rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 2
        assert rows[0]["original_text"] == "أحمد"

    def test_batch_streaming_json_to_stdout(self, tmp_path, capsys) -> None:
        input_path = tmp_path / "input.txt"
        input_path.write_text("أحمد\nإبراهيم\n", encoding="utf-8")

        rc = main(["batch", "--file", str(input_path), "--stream", "--format", "json"])

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload) == 2

    def test_batch_streaming_csv_to_output_file(self, tmp_path) -> None:
        input_path = tmp_path / "input.txt"
        output_path = tmp_path / "output.csv"
        input_path.write_text("أحمد\nإبراهيم\n", encoding="utf-8")

        rc = main(
            [
                "batch",
                "--file",
                str(input_path),
                "--output",
                str(output_path),
                "--stream",
                "--format",
                "csv",
            ]
        )

        assert rc == 0
        assert "normalized_text" in output_path.read_text(encoding="utf-8-sig")

    def test_batch_empty_file_returns_error(self, tmp_path) -> None:
        input_path = tmp_path / "empty.txt"
        input_path.write_text("\n", encoding="utf-8")

        assert main(["batch", "--file", str(input_path), "--stream"]) == 1

    def test_batch_rejects_excessive_worker_count(self, tmp_path, capsys) -> None:
        input_path = tmp_path / "input.txt"
        input_path.write_text("أحمد\n", encoding="utf-8")

        rc = main(["batch", "--file", str(input_path), "--workers", "65"])

        assert rc == 1
        assert "n_workers cannot exceed configured maximum" in capsys.readouterr().err

    def test_batch_rejects_excessive_batch_size(self, tmp_path, capsys) -> None:
        input_path = tmp_path / "input.txt"
        input_path.write_text("أحمد\n", encoding="utf-8")

        rc = main(["batch", "--file", str(input_path), "--batch-size", "10001"])

        assert rc == 1
        assert "batch_size cannot exceed configured maximum" in capsys.readouterr().err
