"""Cross-cutting serialization contracts for operational payloads."""

from __future__ import annotations

import copy
import json

import pytest

from aranorm import NormalizationResult, PipelineConfig, ResourceLimits
from aranorm.core.registry import PluginDiscoveryFailure, PluginDiscoveryReport


def _valid_failure() -> dict[str, str]:
    return {
        "name": "broken-plugin",
        "group": "aranorm.processors",
        "error_type": "RuntimeError",
        "message": "load failed",
    }


def _valid_report() -> dict[str, object]:
    return {
        "group": "aranorm.processors",
        "ok": False,
        "discovered": ["valid-plugin"],
        "failures": [_valid_failure()],
    }


@pytest.mark.parametrize(
    "payload, expected",
    [
        (None, "payload must be an object"),
        ([], "payload must be an object"),
        ({"group": "x"}, "missing fields"),
        ({**_valid_report(), "unexpected": True}, "unknown fields"),
        ({**_valid_report(), "ok": "false"}, "ok must be boolean"),
        ({**_valid_report(), "discovered": [1]}, "discovered must be a list of strings"),
        ({**_valid_report(), "failures": "bad"}, "failures must be a list"),
        ({**_valid_report(), "ok": True}, "ok flag is inconsistent"),
        ({**_valid_report(), "failures": [{"name": "broken"}]}, "invalid plugin discovery failure"),
    ],
)
def test_plugin_report_rejects_malformed_payloads(payload: object, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        PluginDiscoveryReport.from_dict(payload)


@pytest.mark.parametrize(
    "payload, expected",
    [
        (None, "payload must be an object"),
        ({"name": "x"}, "missing fields"),
        ({**_valid_failure(), "extra": True}, "unknown fields"),
        ({**_valid_failure(), "message": 7}, "fields must all be strings"),
    ],
)
def test_plugin_failure_rejects_malformed_payloads(payload: object, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        PluginDiscoveryFailure.from_dict(payload)


def test_plugin_report_round_trip_is_detached() -> None:
    payload = _valid_report()
    report = PluginDiscoveryReport.from_dict(payload)

    payload["discovered"].append("later")  # type: ignore[union-attr]
    payload["failures"][0]["message"] = "mutated"  # type: ignore[index]
    restored = PluginDiscoveryReport.from_dict(report.to_dict())

    assert report.discovered == ("valid-plugin",)
    assert report.failures[0].message == "load failed"
    assert restored == report


def test_pipeline_config_json_round_trip_and_input_is_not_mutated() -> None:
    payload = {
        "preset": "standard",
        "supported_dialects": ["msa", "egyptian"],
        "resource_limits": {
            "max_text_length": 256,
            "max_batch_size": 8,
            "max_workers": 2,
            "reject_null_bytes": True,
        },
        "stop_words_config": {
            "mode": "remove",
            "scope": "universal",
            "dialects": ["EGY"],
            "custom_stop_words": ["كلمة"],
        },
    }
    original = copy.deepcopy(payload)

    config = PipelineConfig.from_json(json.dumps(payload, ensure_ascii=False))
    payload["supported_dialects"].append("levantine")
    payload["stop_words_config"]["custom_stop_words"].append("أخرى")

    assert payload != original
    assert config.supported_dialects == ["msa", "egyptian"]
    assert config.stop_words_config is not None
    assert config.stop_words_config.custom_stop_words == frozenset({"كلمة"})
    assert PipelineConfig.from_json(config.to_json()).to_dict() == config.to_dict()


def test_config_rejects_unknown_nested_and_top_level_fields() -> None:
    with pytest.raises(ValueError, match=r"Unknown PipelineConfig field\(s\): typo"):
        PipelineConfig.from_dict({"typo": True})
    with pytest.raises(ValueError, match=r"Unknown ResourceLimits field\(s\): typo"):
        PipelineConfig.from_dict({"resource_limits": {"typo": 1}})


def test_resource_limits_rejects_boolean_as_integer_and_bad_shapes() -> None:
    with pytest.raises(ValueError, match="max_batch_size must be a positive integer"):
        ResourceLimits(max_batch_size=True)
    with pytest.raises(ValueError, match="max_text_length must be a positive integer"):
        ResourceLimits(max_text_length=0)
    with pytest.raises(TypeError, match="resource_limits must be a dictionary"):
        ResourceLimits.from_dict([])  # type: ignore[arg-type]


def test_normalization_result_serialization_detaches_nested_payloads() -> None:
    result = NormalizationResult(
        original_text="أصل",
        normalized_text="نص",
        applied_steps=["unicode"],
        processing_metadata={"nested": {"secret": "value"}},
        stop_words_removed="من",
    )
    encoded = result.to_dict()
    restored = NormalizationResult.from_dict(encoded)

    encoded["applied_steps"].append("later")  # type: ignore[union-attr]
    encoded["processing_metadata"]["nested"]["secret"] = "changed"  # type: ignore[index]
    encoded["stop_words_removed"] = "في"

    assert result.applied_steps == ["unicode"]
    assert result.processing_metadata["nested"]["secret"] == "value"
    assert result.stop_words_removed == "من"
    assert restored.normalized_text == "نص"
    assert restored.processing_metadata["nested"]["secret"] == "value"
