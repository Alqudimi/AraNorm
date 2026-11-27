import json

from aranorm.cli import _build_parser, main


def test_stream_parser_exposes_run_resume_and_status_commands():
    parser = _build_parser()
    run = parser.parse_args(
        [
            "stream",
            "run",
            "--source",
            "input.txt",
            "--output",
            "output.jsonl",
            "--checkpoint",
            "checkpoint.json",
            "--batch-size",
            "3",
            "--workers",
            "2",
            "--json",
        ]
    )
    assert run.command == "stream"
    assert run.stream_command == "run"
    assert run.batch_size == 3
    assert run.workers == 2
    assert run.json is True

    resume = parser.parse_args(
        ["stream", "resume", "--source", "input.txt", "--output", "output.jsonl", "--checkpoint", "checkpoint.json"]
    )
    assert resume.stream_command == "resume"
    assert resume.batch_size == 32

    status = parser.parse_args(["stream", "status", "--checkpoint", "checkpoint.json", "--json"])
    assert status.stream_command == "status"
    assert status.json is True


def test_stream_run_resume_and_status_json(tmp_path, capsys):
    source = tmp_path / "input.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("الأول\nالثاني\n", encoding="utf-8")
    common = ["--source", str(source), "--output", str(output), "--checkpoint", str(checkpoint), "--json"]

    assert main(["stream", "run", *common, "--batch-size", "1"]) == 0
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["ok"] is True
    assert run_payload["report"]["completed"] is True
    assert run_payload["report"]["processed_count"] == 2

    assert main(["stream", "resume", *common]) == 0
    resume_payload = json.loads(capsys.readouterr().out)
    assert resume_payload["ok"] is True
    assert resume_payload["report"]["resumed"] is True
    assert resume_payload["report"]["processed_count"] == 2

    assert main(["stream", "status", "--checkpoint", str(checkpoint), "--json"]) == 0
    status_payload = json.loads(capsys.readouterr().out)
    assert status_payload["completed"] is True
    assert status_payload["input_count"] == 2


def test_stream_run_creates_nested_output_and_checkpoint_paths(tmp_path, capsys):
    source = tmp_path / "input.txt"
    output = tmp_path / "nested" / "result.jsonl"
    checkpoint = tmp_path / "state" / "checkpoint.json"
    source.write_text("نص واحد\n", encoding="utf-8")

    assert (
        main(
            [
                "stream",
                "run",
                "--source",
                str(source),
                "--output",
                str(output),
                "--checkpoint",
                str(checkpoint),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "Completed  : yes" in captured.out
    assert output.exists()
    assert checkpoint.exists()


def test_stream_commands_report_missing_source_or_checkpoint(tmp_path, capsys):
    missing_source = main(
        [
            "stream",
            "run",
            "--source",
            str(tmp_path / "missing.txt"),
            "--output",
            str(tmp_path / "out.jsonl"),
            "--checkpoint",
            str(tmp_path / "checkpoint.json"),
        ]
    )
    assert missing_source == 1
    assert "streaming session failed" in capsys.readouterr().err

    missing_checkpoint = main(["stream", "status", "--checkpoint", str(tmp_path / "missing.json"), "--json"])
    assert missing_checkpoint == 1
    assert "could not load streaming checkpoint" in capsys.readouterr().err


def test_stream_status_human_output(tmp_path, capsys):
    source = tmp_path / "input.txt"
    output = tmp_path / "output.jsonl"
    checkpoint = tmp_path / "checkpoint.json"
    source.write_text("نص\n", encoding="utf-8")
    assert (
        main(
            [
                "stream",
                "run",
                "--source",
                str(source),
                "--output",
                str(output),
                "--checkpoint",
                str(checkpoint),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["stream", "status", "--checkpoint", str(checkpoint)]) == 0
    output_text = capsys.readouterr().out
    assert "Checkpoint" in output_text
    assert "Completed  : yes" in output_text


def test_stream_parser_exposes_lock_option_and_serve_root():
    parser = _build_parser()
    run = parser.parse_args(
        [
            "stream",
            "run",
            "--source",
            "input.txt",
            "--output",
            "output.jsonl",
            "--checkpoint",
            "checkpoint.json",
            "--lock",
        ]
    )
    assert run.lock_enabled is True

    serve = parser.parse_args(["serve", "--streaming-enabled", "--streaming-root", "/srv/aranorm"])
    assert serve.streaming_enabled is True
    assert serve.streaming_root == "/srv/aranorm"


def test_serve_rejects_streaming_root_without_opt_in(tmp_path, capsys):
    result = main(["serve", "--streaming-root", str(tmp_path)])
    assert result == 1
    assert "requires --streaming-enabled" in capsys.readouterr().err
