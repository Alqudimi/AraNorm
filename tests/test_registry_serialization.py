"""Serialization contracts for plugin discovery diagnostics."""

import pytest

from aranorm.core.registry import PluginDiscoveryFailure, PluginDiscoveryReport


def test_plugin_discovery_report_round_trips_without_plugin_objects() -> None:
    report = PluginDiscoveryReport(
        group="aranorm.processors",
        discovered=("alef", "hamza"),
        failures=(
            PluginDiscoveryFailure(
                name="broken",
                group="aranorm.processors",
                error_type="RuntimeError",
                message="dependency missing",
            ),
        ),
    )

    restored = PluginDiscoveryReport.from_dict(report.to_dict())

    assert restored == report
    assert restored.to_dict() == report.to_dict()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"group": "aranorm.processors", "discovered": [], "failures": "bad"},
        {"group": 42, "discovered": [], "failures": []},
        {"group": "aranorm.processors", "discovered": ["ok", 3], "failures": []},
        {
            "group": "aranorm.processors",
            "discovered": [],
            "failures": [{"name": "broken"}],
        },
    ],
)
def test_plugin_discovery_report_rejects_malformed_payloads(payload) -> None:
    with pytest.raises(ValueError):
        PluginDiscoveryReport.from_dict(payload)


def test_plugin_discovery_failure_rejects_unknown_fields() -> None:
    payload = {
        "name": "broken",
        "group": "aranorm.processors",
        "error_type": "RuntimeError",
        "message": "dependency missing",
        "secret": "must not be accepted",
    }

    with pytest.raises(ValueError, match="unknown fields"):
        PluginDiscoveryFailure.from_dict(payload)
