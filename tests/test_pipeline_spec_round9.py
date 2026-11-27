"""Contract tests for the round-nine portable PipelineSpec boundary."""

import json

import pytest

import aranorm.core.spec as spec_module
from aranorm import (
    DEFAULT_MAX_SPEC_BYTES,
    ArabicNormalizationPipeline,
    ConfigurationError,
    PipelineConfig,
    PipelineRuntime,
    PipelineSpec,
)


def make_pipeline() -> ArabicNormalizationPipeline:
    return ArabicNormalizationPipeline(PipelineConfig(preset="deep"))


def test_pipeline_spec_round_trip_preserves_configuration_and_metadata() -> None:
    pipeline = make_pipeline()
    spec = pipeline.to_spec(metadata={"owner": "quality", "labels": ["round9"]})

    restored = PipelineSpec.from_json(spec.to_json())

    assert restored.to_dict() == spec.to_dict()
    assert restored.to_pipeline().configuration_fingerprint() == pipeline.configuration_fingerprint()
    assert restored.metadata == {"owner": "quality", "labels": ["round9"]}


def test_pipeline_spec_uses_deterministic_json_and_fingerprint() -> None:
    pipeline = make_pipeline()
    first = pipeline.to_spec(metadata={"b": 2, "a": 1})
    second = pipeline.to_spec(metadata={"a": 1, "b": 2})

    assert first.config_fingerprint == second.config_fingerprint
    assert first.to_json() == second.to_json()


def test_pipeline_spec_to_dict_is_defensive() -> None:
    spec = make_pipeline().to_spec(metadata={"nested": {"enabled": True}})
    exported = spec.to_dict()
    exported["config"]["preset"] = "light"
    exported["metadata"]["nested"]["enabled"] = False

    assert spec.config["preset"] == "deep"
    assert spec.metadata["nested"]["enabled"] is True


def test_pipeline_spec_rejects_unknown_and_missing_fields() -> None:
    spec = make_pipeline().to_spec()
    payload = spec.to_dict()

    with pytest.raises(ConfigurationError, match="Unknown PipelineSpec field"):
        PipelineSpec.from_dict({**payload, "unexpected": True})

    payload.pop("metadata")
    with pytest.raises(ConfigurationError, match="Missing PipelineSpec field"):
        PipelineSpec.from_dict(payload)


def test_pipeline_spec_rejects_tampered_fingerprint() -> None:
    payload = make_pipeline().to_spec().to_dict()
    payload["config_fingerprint"] = "0" * 64

    with pytest.raises(ConfigurationError, match="does not match config"):
        PipelineSpec.from_dict(payload)


def test_pipeline_spec_rejects_unsupported_schema_and_pipeline_class() -> None:
    payload = make_pipeline().to_spec().to_dict()

    payload["schema_version"] = 99
    with pytest.raises(ConfigurationError, match="Unsupported PipelineSpec schema"):
        PipelineSpec.from_dict(payload)

    payload = make_pipeline().to_spec().to_dict()
    payload["pipeline_class"] = "CustomPipeline"
    with pytest.raises(ConfigurationError, match="Unsupported pipeline_class"):
        PipelineSpec.from_dict(payload)


def test_pipeline_spec_rejects_non_json_metadata_and_non_finite_numbers() -> None:
    with pytest.raises(ConfigurationError, match="metadata must be JSON-compatible"):
        make_pipeline().to_spec(metadata={"bad": object()})

    payload = make_pipeline().to_spec().to_dict()
    payload["metadata"] = {"bad": float("nan")}
    with pytest.raises(ConfigurationError, match="metadata must be JSON-compatible"):
        PipelineSpec.from_dict(payload)


def test_pipeline_spec_file_round_trip_and_size_limit(tmp_path) -> None:
    path = tmp_path / "pipeline.spec.json"
    spec = make_pipeline().to_spec(metadata={"source": "test"})
    spec.write_file(path)

    assert PipelineSpec.read_file(path).to_dict() == spec.to_dict()
    with pytest.raises(ConfigurationError, match="exceeds"):
        PipelineSpec.read_file(path, max_bytes=8)


def test_pipeline_spec_rejects_invalid_json_and_invalid_limits() -> None:
    with pytest.raises(ConfigurationError, match="Invalid PipelineSpec JSON"):
        PipelineSpec.from_json("{not-json")
    with pytest.raises(ValueError, match="max_bytes"):
        PipelineSpec.from_json("{}", max_bytes=0)
    with pytest.raises(ValueError, match="max_bytes"):
        PipelineSpec.from_json("{}", max_bytes=True)
    assert DEFAULT_MAX_SPEC_BYTES > 0


def test_runtime_spec_reload_is_atomic_and_advances_generation() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))
    before = runtime.health()
    spec = make_pipeline().to_spec()

    result = runtime.reload_from_spec(spec.to_dict())

    assert result.success is True
    assert result.generation == before.generation + 1
    assert runtime.health().config_fingerprint == spec.config_fingerprint


def test_runtime_spec_reload_rejects_tampering_without_publishing() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))
    before = runtime.health()
    payload = make_pipeline().to_spec().to_dict()
    payload["config_fingerprint"] = "f" * 64

    result = runtime.reload_from_spec(payload)

    assert result.success is False
    assert result.generation == before.generation
    assert runtime.health().config_fingerprint == before.config_fingerprint
    assert runtime.health().last_reload_error is not None


def test_runtime_spec_file_reload_and_pipeline_snapshot(tmp_path) -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))
    path = tmp_path / "spec.json"
    spec = make_pipeline().to_spec()
    spec.write_file(path)
    old_pipeline = runtime.get_pipeline()

    result = runtime.reload_from_spec_file(path)

    assert result.success is True
    assert runtime.get_pipeline() is not old_pipeline
    assert runtime.get_pipeline().configuration_fingerprint() == spec.config_fingerprint


def test_pipeline_from_spec_accepts_mapping() -> None:
    pipeline = make_pipeline()
    restored = ArabicNormalizationPipeline.from_spec(pipeline.to_spec().to_dict())

    assert restored.configuration_fingerprint() == pipeline.configuration_fingerprint()
    assert json.loads(pipeline.to_spec().to_json())["schema_version"] == 1


def test_pipeline_spec_rejects_constructor_type_contracts() -> None:
    payload = make_pipeline().to_spec().to_dict()

    with pytest.raises(ConfigurationError, match="library_version"):
        PipelineSpec(**{**payload, "library_version": ""})
    with pytest.raises(ConfigurationError, match="config must be a dictionary"):
        PipelineSpec(**{**payload, "config": []})
    with pytest.raises(ConfigurationError, match="metadata must be a dictionary"):
        PipelineSpec(**{**payload, "metadata": []})


def test_pipeline_spec_rejects_invalid_fingerprint_shapes() -> None:
    payload = make_pipeline().to_spec().to_dict()

    payload["config_fingerprint"] = "short"
    with pytest.raises(ConfigurationError, match="64-character"):
        PipelineSpec.from_dict(payload)

    payload = make_pipeline().to_spec().to_dict()
    payload["config_fingerprint"] = "g" * 64
    with pytest.raises(ConfigurationError, match="hexadecimal"):
        PipelineSpec.from_dict(payload)


def test_pipeline_spec_rejects_typed_field_contracts() -> None:
    cases = [
        ("schema_version", True, "schema_version must be an integer"),
        ("pipeline_class", 7, "pipeline_class must be a string"),
        ("library_version", 7, "library_version must be a string"),
        ("config", [], "config must be a mapping"),
        ("metadata", [], "metadata must be a mapping"),
    ]
    for key, value, message in cases:
        candidate = make_pipeline().to_spec().to_dict()
        candidate[key] = value
        with pytest.raises(ConfigurationError, match=message):
            PipelineSpec.from_dict(candidate)


def test_pipeline_spec_rejects_non_mapping_and_non_string_inputs() -> None:
    with pytest.raises(TypeError, match="expects a mapping"):
        PipelineSpec.from_dict([])
    with pytest.raises(TypeError, match="expects a string"):
        PipelineSpec.from_json(123)
    with pytest.raises(TypeError, match="expects a mapping"):
        PipelineSpec.from_json("[]")
    with pytest.raises(ValueError, match="max_bytes"):
        PipelineSpec.from_json("{}", max_bytes="1024")


def test_pipeline_spec_file_read_errors_are_safe(tmp_path) -> None:
    missing = tmp_path / "missing.spec.json"
    with pytest.raises(ConfigurationError, match="Cannot inspect"):
        PipelineSpec.read_file(missing)

    invalid = tmp_path / "invalid.spec.json"
    invalid.write_bytes(b"{\xff")
    with pytest.raises(ConfigurationError, match="Cannot read"):
        PipelineSpec.read_file(invalid)


def test_pipeline_spec_rejects_invalid_indent_and_write_target(tmp_path) -> None:
    spec = make_pipeline().to_spec()
    with pytest.raises(ValueError, match="indent"):
        spec.to_json(indent=-1)
    with pytest.raises(ValueError, match="indent"):
        spec.to_json(indent=True)

    target_directory = tmp_path / "target"
    target_directory.mkdir()
    with pytest.raises(ConfigurationError, match="Cannot write"):
        spec.write_file(target_directory)


def test_pipeline_spec_to_pipeline_detects_reconstruction_mismatch(monkeypatch) -> None:
    spec = make_pipeline().to_spec()
    monkeypatch.setattr(
        ArabicNormalizationPipeline,
        "configuration_fingerprint",
        lambda self: "0" * 64,
    )
    with pytest.raises(ConfigurationError, match="reconstructed pipeline fingerprint"):
        spec.to_pipeline()


def test_pipeline_spec_from_pipeline_rejects_incompatible_object() -> None:
    with pytest.raises(TypeError, match="must expose config"):
        PipelineSpec.from_pipeline(object())


def test_pipeline_spec_reload_file_missing_marks_runtime_degraded(tmp_path) -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))
    result = runtime.reload_from_spec_file(tmp_path / "does-not-exist.json")

    assert result.success is False
    assert result.error_type == "ConfigurationError"
    assert runtime.health().status == "degraded"
    assert runtime.health().last_reload_error is not None


def test_pipeline_spec_runtime_and_health_payloads_are_machine_readable() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))
    spec = runtime.spec(metadata={"service": "test"})
    health = runtime.health()
    reload_result = runtime.reload_from_spec(spec)

    assert spec.metadata == {"service": "test"}
    assert set(health.to_dict()) == {
        "schema_version",
        "status",
        "ready",
        "generation",
        "config_fingerprint",
        "last_reload_error",
    }
    assert set(reload_result.to_dict()) == {
        "schema_version",
        "success",
        "generation",
        "config_fingerprint",
        "error_type",
        "error_message",
    }
    assert health.ready is True
    assert reload_result.success is True


def test_pipeline_spec_from_json_rejects_oversized_payload() -> None:
    spec = make_pipeline().to_spec()
    with pytest.raises(ConfigurationError, match="exceeds"):
        PipelineSpec.from_json(spec.to_json(), max_bytes=1)


def test_pipeline_spec_write_file_swallows_cleanup_failure(monkeypatch, tmp_path) -> None:
    spec = make_pipeline().to_spec()

    def fail_replace(source: str, target: str) -> None:
        raise OSError("replace failed")

    def fail_unlink(path: str) -> None:
        raise OSError("unlink failed")

    monkeypatch.setattr(spec_module.os, "replace", fail_replace)
    monkeypatch.setattr(spec_module.os, "unlink", fail_unlink)

    with pytest.raises(ConfigurationError, match="Cannot write"):
        spec.write_file(tmp_path / "spec.json")


def test_pipeline_spec_write_file_cleans_temporary_file_after_replace_failure(monkeypatch, tmp_path) -> None:
    spec = make_pipeline().to_spec()
    removed = []

    def fail_replace(source: str, target: str) -> None:
        raise OSError("replace failed")

    def record_unlink(path: str) -> None:
        removed.append(path)

    monkeypatch.setattr(spec_module.os, "replace", fail_replace)
    monkeypatch.setattr(spec_module.os, "unlink", record_unlink)

    with pytest.raises(ConfigurationError, match="Cannot write"):
        spec.write_file(tmp_path / "spec.json")

    assert len(removed) == 1
    assert removed[0].startswith(str(tmp_path / ".aranorm-spec-"))
