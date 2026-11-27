"""Public API and import-surface contracts."""

from __future__ import annotations

import json

import aranorm
from aranorm import (
    ArabicNormalizationPipeline,
    BatchProcessingPolicy,
    CancellationToken,
    PipelineHooks,
    ProcessingMetrics,
    ProcessingMetricsSnapshot,
    ResourceLimits,
)
from aranorm.exceptions import ProcessingCancelledError


def test_public_exports_include_round4_operational_contracts() -> None:
    expected = {
        "ArabicNormalizationPipeline",
        "BatchProcessingPolicy",
        "CancellationToken",
        "PipelineHooks",
        "ProcessingMetrics",
        "ProcessingMetricsSnapshot",
        "ResourceLimits",
        "ProcessingCancelledError",
    }

    assert expected.issubset(set(aranorm.__all__))
    for name in expected:
        assert hasattr(aranorm, name)


def test_version_is_semver_and_matches_supported_release_shape() -> None:
    parts = aranorm.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_describe_is_json_serializable_and_contains_operational_fields() -> None:
    description = ArabicNormalizationPipeline().describe()

    json.dumps(description, ensure_ascii=False)
    assert description["preset"] == "standard"
    assert "cleaning" in description
    assert "normalization" in description
    assert "stop_words_enabled" in description
    assert "supported_dialects" in description


def test_public_contracts_construct_without_optional_dependencies() -> None:
    token = CancellationToken()
    assert token.is_cancelled is False
    assert BatchProcessingPolicy().mode == "fail_fast"
    assert isinstance(ResourceLimits(), ResourceLimits)
    assert isinstance(PipelineHooks(), PipelineHooks)
    metrics = ProcessingMetrics()
    assert isinstance(metrics, ProcessingMetrics)
    assert isinstance(metrics.snapshot(), ProcessingMetricsSnapshot)
    assert issubclass(ProcessingCancelledError, Exception)
