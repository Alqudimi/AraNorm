"""End-to-end CLI contracts for portable PipelineSpec operations."""

import json

from aranorm.cli import main


def test_spec_export_to_file_and_validate_json(tmp_path, capsys) -> None:
    path = tmp_path / "pipeline.spec.json"

    assert main(["spec", "export", "--preset", "deep", "--metadata-json", '{"team":"nlp"}', "--output", str(path)]) == 0
    exported_output = capsys.readouterr().out
    assert f"Wrote PipelineSpec to {path}" in exported_output

    assert main(["spec", "validate", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["schema_version"] == 1
    assert payload["metadata"] == {"team": "nlp"}


def test_spec_export_stdout_is_valid_json(capsys) -> None:
    assert main(["spec", "export", "--preset", "light"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["pipeline_class"] == "ArabicNormalizationPipeline"
    assert payload["config"]["preset"] == "light"
    assert len(payload["config_fingerprint"]) == 64


def test_spec_export_json_result_contains_output(tmp_path, capsys) -> None:
    path = tmp_path / "spec.json"

    assert main(["spec", "export", "--output", str(path), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["output"] == str(path)
    assert path.exists()


def test_spec_validate_invalid_file_returns_nonzero(tmp_path, capsys) -> None:
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version": 99}', encoding="utf-8")

    assert main(["spec", "validate", str(path)]) == 1
    assert "Error: invalid PipelineSpec" in capsys.readouterr().err


def test_spec_requires_subcommand() -> None:
    try:
        main(["spec"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("argparse should require a spec sub-command")


def test_spec_metadata_must_be_object(capsys) -> None:
    assert main(["spec", "export", "--metadata-json", "[]"]) == 1
    assert "metadata-json" in capsys.readouterr().err


def test_serve_parser_accepts_spec_without_starting_listener(monkeypatch, tmp_path) -> None:
    from aranorm import ArabicNormalizationPipeline, PipelineConfig
    from aranorm import cli

    spec_path = tmp_path / "serve.spec.json"
    ArabicNormalizationPipeline(PipelineConfig(preset="deep")).to_spec().write_file(spec_path)
    observed = {}

    def fake_serve(runtime, **kwargs):
        observed["fingerprint"] = runtime.health().config_fingerprint
        observed["spec_path"] = kwargs["spec_path"]

    monkeypatch.setattr(cli, "_cmd_serve", cli._cmd_serve)
    monkeypatch.setattr("aranorm.server.serve", fake_serve)

    assert cli.main(["serve", "--spec", str(spec_path)]) == 0
    assert observed["spec_path"] == str(spec_path)
    assert (
        observed["fingerprint"]
        == ArabicNormalizationPipeline(PipelineConfig(preset="deep")).configuration_fingerprint()
    )


def test_serve_rejects_config_and_spec_together(capsys) -> None:
    from aranorm import cli

    assert cli.main(["serve", "--config", "config.json", "--spec", "spec.json"]) == 1
    assert "mutually exclusive" in capsys.readouterr().err
