"""End-to-end CLI tests for Round 6 operational commands.

Verifies that the round-6 interfaces (describe, plugins, version JSON
schemas, and the normalize JSON payload) surface correctly through the
CLI layer.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from aranorm import __version__
from aranorm.cli import main


@pytest.fixture(scope="module")
def cli_runner():
    """Run a CLI command and return (returncode, stdout)."""

    def run(argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            returncode = main(argv)
        return returncode, buffer.getvalue()

    return run


class TestCliDescribe:
    def test_describe_json_contains_config(self, cli_runner):
        _, output = cli_runner(["describe", "--json"])
        payload = json.loads(output)
        assert "config" in payload
        assert "normalization" in payload["config"]
        assert "cleaning" in payload["config"]

    def test_describe_text_mode_no_json(self, cli_runner):
        _, output = cli_runner(["describe"])
        assert output.strip()
        with pytest.raises(json.JSONDecodeError):
            json.loads(output)


class TestCliPlugins:
    def test_plugins_json_has_schema(self, cli_runner):
        _, output = cli_runner(["plugins", "--json"])
        payload = json.loads(output)
        assert "discovered" in payload
        assert "failures" in payload
        assert "schema_version" in payload
        assert payload["ok"] in (True, False)

    def test_plugins_strict_mode(self, cli_runner):
        _, output = cli_runner(["plugins", "--strict", "--json"])
        payload = json.loads(output)
        assert "discovered" in payload
        assert "failures" in payload

    def test_plugins_group_default(self, cli_runner):
        _, output = cli_runner(["plugins", "--json"])
        payload = json.loads(output)
        assert payload["group"] == "aranorm.processors"


class TestCliVersion:
    def test_version_json_schema(self, cli_runner):
        _, output = cli_runner(["version", "--json"])
        payload = json.loads(output)
        assert payload["version"] == __version__
        assert payload["package"] == "aranorm"
        assert payload["schema_version"] == "1"

    def test_version_plain(self, cli_runner):
        _, output = cli_runner(["version"])
        assert __version__ in output


class TestCliNormalizeJson:
    def test_normalize_json_round_trip(self, cli_runner):
        _, output = cli_runner(["normalize", "نص تجريبي", "--json"])
        payload = json.loads(output)
        assert isinstance(payload, list) and len(payload) == 1
        entry = payload[0]
        assert entry["original"] == "نص تجريبي"
        assert entry["normalized"]
        assert entry["dialect"]
