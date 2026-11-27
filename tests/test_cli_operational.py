"""Operational CLI contracts."""

import json

from aranorm import __version__
from aranorm.cli import main


def test_describe_json_exposes_versioned_pipeline_metadata(capsys) -> None:
    assert main(["describe", "--preset", "deep", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == 1
    assert payload["pipeline_class"] == "ArabicNormalizationPipeline"
    assert len(payload["config_fingerprint"]) == 64
    assert payload["config"]["preset"] == "deep"


def test_describe_human_output_is_safe_and_readable(capsys) -> None:
    assert main(["describe", "--preset", "light"]) == 0

    output = capsys.readouterr().out

    assert "Pipeline: ArabicNormalizationPipeline" in output
    assert "Config fingerprint:" in output
    assert "light" in output


def test_plugins_json_reports_discovery_failures(monkeypatch, capsys) -> None:
    """The plugins command exposes deterministic, machine-readable diagnostics."""
    from aranorm import Processor
    from aranorm.core.registry import metadata

    class ValidProcessor(Processor):
        name = "valid"

        def process(self, text: str, context=None) -> str:
            return text

    class EntryPoint:
        def __init__(self, name, value, loaded):
            self.name = name
            self.value = value
            self._loaded = loaded

        def load(self):
            if isinstance(self._loaded, Exception):
                raise self._loaded
            return self._loaded

    class EntryPoints:
        def select(self, *, group):
            assert group == "test.plugins"
            return [
                EntryPoint("bad", "bad.mod:Processor", RuntimeError("not available")),
                EntryPoint("good", "good.mod:Processor", ValidProcessor),
            ]

    monkeypatch.setattr(metadata, "entry_points", lambda: EntryPoints())

    assert main(["plugins", "--group", "test.plugins", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "1"
    assert payload["group"] == "test.plugins"
    assert payload["ok"] is False
    assert payload["discovered"] == ["good"]
    assert payload["failures"][0]["name"] == "bad"


def test_plugins_strict_maps_discovery_error_to_cli_failure(monkeypatch, capsys) -> None:
    """Strict discovery remains a non-zero CLI operation when a plugin fails."""
    from aranorm.core.registry import ProcessorRegistry

    def fail_discovery(self, group="aranorm.processors", *, strict=False):
        raise RuntimeError("strict discovery failure")

    monkeypatch.setattr(ProcessorRegistry, "discover_report", fail_discovery)

    assert main(["plugins", "--strict"]) == 1
    assert "strict discovery failure" in capsys.readouterr().err


def test_public_api_exports_plugin_discovery_contracts() -> None:
    """The plugin discovery report types are available from the public package."""
    import aranorm
    from aranorm.core import PluginDiscoveryFailure, PluginDiscoveryReport

    failure = PluginDiscoveryFailure("demo", "group", "RuntimeError", "failed")
    report = PluginDiscoveryReport("group", ("demo",), (failure,))
    assert "PluginDiscoveryReport" in aranorm.__all__
    assert report.to_dict()["failures"] == [failure.to_dict()]
    assert aranorm.PluginDiscoveryFailure is PluginDiscoveryFailure
    assert aranorm.PluginDiscoveryReport is PluginDiscoveryReport


def test_plugins_human_output_is_readable(monkeypatch, capsys) -> None:
    """Human output exposes the operational status and failure summary."""
    from aranorm.core.registry import metadata

    class EntryPoint:
        name = "broken"
        value = "broken.mod:Processor"

        def load(self):
            raise RuntimeError("dependency missing")

    class EntryPoints:
        def select(self, *, group):
            return [EntryPoint()]

    monkeypatch.setattr(metadata, "entry_points", lambda: EntryPoints())

    assert main(["plugins"]) == 0
    output = capsys.readouterr().out
    assert "Plugin group" in output
    assert "Status       : degraded" in output
    assert "broken: RuntimeError: dependency missing" in output


def test_version_json_is_machine_readable(capsys) -> None:
    """The version command keeps a stable automation-friendly JSON mode."""
    assert main(["version", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "1"
    assert payload["package"] == "aranorm"
    assert payload["version"] == __version__
