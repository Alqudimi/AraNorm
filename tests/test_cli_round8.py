"""CLI contracts for the optional runtime server."""

from argparse import Namespace

from aranorm.cli import _build_parser, _cmd_serve


def test_serve_parser_exposes_safe_defaults_and_reload_flags() -> None:
    args = _build_parser().parse_args(["serve"])

    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.preset == "standard"
    assert args.max_body_bytes == 2_000_000
    assert args.reload_interval == 0.0


def test_serve_parser_accepts_config_and_operational_overrides() -> None:
    args = _build_parser().parse_args(
        [
            "serve",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--config",
            "pipeline.json",
            "--max-body-bytes",
            "4096",
            "--reload-interval",
            "0.5",
        ]
    )

    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.config == "pipeline.json"
    assert args.max_body_bytes == 4096
    assert args.reload_interval == 0.5


def test_serve_returns_config_error_without_starting_listener(tmp_path, capsys) -> None:
    args = Namespace(
        config=str(tmp_path / "missing.json"),
        preset="standard",
        host="127.0.0.1",
        port=8765,
        max_body_bytes=2_000_000,
        reload_interval=0.0,
    )

    exit_code = _cmd_serve(args)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "could not load configuration" in captured.err


def test_serve_passes_runtime_and_options_to_service(monkeypatch, tmp_path, capsys) -> None:
    config_path = tmp_path / "pipeline.json"
    config_path.write_text('{"preset": "light"}', encoding="utf-8")
    calls = []

    def fake_serve(runtime, **kwargs):
        calls.append((runtime, kwargs))

    monkeypatch.setattr("aranorm.server.serve", fake_serve)
    args = Namespace(
        config=str(config_path),
        preset="standard",
        host="127.0.0.1",
        port=9123,
        max_body_bytes=8192,
        reload_interval=0.25,
    )

    exit_code = _cmd_serve(args)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert len(calls) == 1
    runtime, kwargs = calls[0]
    assert runtime.config.preset.value == "light"
    assert kwargs == {
        "host": "127.0.0.1",
        "port": 9123,
        "max_body_bytes": 8192,
        "config_path": str(config_path),
        "reload_interval": 0.25,
    }
    assert "listening" in captured.err
