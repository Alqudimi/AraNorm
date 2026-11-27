"""Round-7 CLI contracts for opt-in tracing and bounded retries."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout

from aranorm.cli import main


def _run(argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def test_normalize_trace_is_opt_in_and_additive():
    code, output, _ = _run(["normalize", "نص تجريبي", "--json"])
    assert code == 0
    legacy = json.loads(output)
    assert isinstance(legacy, list)
    assert "steps_trace" not in legacy[0]

    code, output, _ = _run(["normalize", "نص تجريبي", "--json", "--emit-steps-trace"])
    assert code == 0
    payload = json.loads(output)
    assert isinstance(payload, list)
    assert isinstance(payload[0]["steps_trace"], list)


def test_normalize_retry_uses_versioned_envelope():
    code, output, _ = _run(["normalize", "نص تجريبي", "--json", "--retry", "--max-retries", "0"])
    assert code == 0
    payload = json.loads(output)
    assert payload["schema_version"] == "1.0"
    assert len(payload["results"]) == 1
    assert payload["retry"]["retry_report"]["total_inputs"] == 1
    assert payload["retry"]["retry_report"]["max_retries"] == 0


def test_batch_json_trace_export(tmp_path):
    source = tmp_path / "input.txt"
    destination = tmp_path / "output.json"
    source.write_text("نص أول\nنص ثان\n", encoding="utf-8")

    code, output, error = _run(
        [
            "batch",
            "--file",
            str(source),
            "--output",
            str(destination),
            "--format",
            "json",
            "--emit-steps-trace",
        ]
    )
    assert code == 0, error
    assert "Wrote 2 results" in output
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert len(payload) == 2
    assert "steps_trace" in payload[0]


def test_batch_retry_and_trace_jsonl(tmp_path):
    source = tmp_path / "input.txt"
    destination = tmp_path / "output.jsonl"
    source.write_text("نص أول\nنص ثان\n", encoding="utf-8")

    code, _, error = _run(
        [
            "batch",
            "--file",
            str(source),
            "--output",
            str(destination),
            "--format",
            "jsonl",
            "--emit-steps-trace",
            "--retry",
            "--max-retries",
            "1",
        ]
    )
    assert code == 0, error
    rows = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert isinstance(rows[0].get("steps_trace"), list)


def test_batch_rejects_retry_stream_combination(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("نص\n", encoding="utf-8")

    code, _, error = _run(["batch", "--file", str(source), "--stream", "--retry"])
    assert code == 2
    assert "cannot be combined" in error
