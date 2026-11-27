"""Contract tests for the post-1.8 runtime snapshot layer."""

from concurrent.futures import ThreadPoolExecutor

from aranorm import PipelineConfig, PipelineRuntime, Preset
from aranorm.core.pipeline import ArabicNormalizationPipeline


def test_runtime_starts_ready_at_generation_zero() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))

    health = runtime.health()

    assert runtime.generation == 0
    assert health.ready is True
    assert health.status == "ready"
    assert health.generation == 0
    assert isinstance(health.config_fingerprint, str)
    assert health.last_reload_error is None


def test_get_pipeline_returns_stable_snapshot_across_reload() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))
    old_pipeline = runtime.get_pipeline()

    outcome = runtime.reload(PipelineConfig(preset="light"))

    assert outcome.success is True
    assert runtime.get_pipeline() is not old_pipeline
    assert old_pipeline.configuration_fingerprint() != runtime.get_pipeline().configuration_fingerprint()


def test_runtime_process_and_config_are_defensive() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))

    config = runtime.config
    config.clean_urls = False
    result = runtime.process("زر https://example.com")

    assert result.normalized_text
    assert runtime.config.clean_urls is True


def test_successful_reload_publishes_one_new_generation() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))
    old_fingerprint = runtime.health().config_fingerprint

    outcome = runtime.reload(PipelineConfig(preset=Preset.DEEP))

    assert outcome.success is True
    assert outcome.generation == 1
    assert outcome.error_type is None
    assert outcome.error_message is None
    assert outcome.config_fingerprint != old_fingerprint
    assert runtime.generation == 1
    assert runtime.health().status == "ready"


def test_failed_reload_preserves_snapshot_and_marks_degraded() -> None:
    def factory(config: PipelineConfig) -> ArabicNormalizationPipeline:
        if config.preset == Preset.DEEP:
            raise RuntimeError("synthetic construction failure")
        return ArabicNormalizationPipeline(config)

    runtime = PipelineRuntime(PipelineConfig(preset="standard"), factory=factory)
    before = runtime.health().config_fingerprint

    outcome = runtime.reload(PipelineConfig(preset="deep"))

    assert outcome.success is False
    assert outcome.generation == 0
    assert outcome.error_type == "RuntimeError"
    assert outcome.error_message == "runtime reload failed"
    assert runtime.generation == 0
    assert runtime.health().config_fingerprint == before
    assert runtime.health().status == "degraded"
    assert runtime.process("مَرْحَبًا").normalized_text


def test_reload_from_missing_file_is_non_destructive(tmp_path) -> None:
    runtime = PipelineRuntime()
    before = runtime.generation

    outcome = runtime.reload_from_file(tmp_path / "missing.json")

    assert outcome.success is False
    assert outcome.generation == before
    assert outcome.error_type == "FileNotFoundError"
    assert outcome.error_message == "configuration file was not found"
    assert runtime.health().status == "degraded"


def test_runtime_describe_contains_generation_and_pipeline_contract() -> None:
    runtime = PipelineRuntime()

    description = runtime.describe()

    assert description["schema_version"] == 1
    assert description["pipeline_class"] == "ArabicNormalizationPipeline"
    assert description["runtime"] == {"generation": 0, "status": "ready"}
    assert description["config_fingerprint"] == runtime.health().config_fingerprint


def test_runtime_snapshot_is_safe_for_concurrent_readers() -> None:
    runtime = PipelineRuntime()

    def read_one(_: int) -> str:
        return runtime.process("النص العربي").normalized_text

    with ThreadPoolExecutor(max_workers=4) as executor:
        values = list(executor.map(read_one, range(12)))

    assert len(values) == 12
    assert all(isinstance(value, str) for value in values)


def test_reload_result_and_health_are_json_compatible() -> None:
    runtime = PipelineRuntime()

    outcome = runtime.reload(PipelineConfig(preset="light"))
    health = runtime.health()

    outcome_payload = outcome.to_dict()
    health_payload = health.to_dict()
    assert outcome_payload["schema_version"] == 1
    assert outcome_payload["success"] is True
    assert outcome_payload["generation"] == 1
    assert health_payload["schema_version"] == 1
    assert health_payload["status"] == "ready"
    assert "original_text" not in str(health_payload)


def test_reload_from_json_file_publishes_new_snapshot(tmp_path) -> None:
    config_path = tmp_path / "pipeline.json"
    config_path.write_text('{"preset": "light"}', encoding="utf-8")
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))

    outcome = runtime.reload_from_file(config_path)

    assert outcome.success is True
    assert runtime.generation == 1
    assert runtime.config.preset == Preset.LIGHT


def test_reload_from_invalid_json_is_non_destructive(tmp_path) -> None:
    config_path = tmp_path / "invalid.json"
    config_path.write_text('{"preset":', encoding="utf-8")
    runtime = PipelineRuntime()
    before = runtime.health().config_fingerprint

    outcome = runtime.reload_from_file(config_path)

    assert outcome.success is False
    assert outcome.generation == 0
    assert outcome.error_type == "JSONDecodeError"
    assert runtime.health().config_fingerprint == before


def test_successive_reloads_increment_generation_monotonically() -> None:
    runtime = PipelineRuntime()

    first = runtime.reload(PipelineConfig(preset="light"))
    second = runtime.reload(PipelineConfig(preset="deep"))

    assert (first.generation, second.generation, runtime.generation) == (1, 2, 2)


def test_runtime_process_batch_preserves_input_order() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="light"))

    results = runtime.process_batch(["الأول", "الثاني", "الثالث"], batch_size=2, n_workers=2)

    assert [result.original_text for result in results] == ["الأول", "الثاني", "الثالث"]


def test_runtime_description_is_sanitized() -> None:
    runtime = PipelineRuntime()

    description = runtime.describe()

    assert "original_text" not in description
    assert "normalized_text" not in description
    assert description["runtime"]["generation"] == 0


def test_runtime_config_returns_independent_nested_snapshot() -> None:
    runtime = PipelineRuntime(PipelineConfig(preset="standard"))

    first = runtime.config
    second = runtime.config

    assert first is not second
    assert first.resource_limits is not second.resource_limits
    assert first.resource_limits.max_batch_size == second.resource_limits.max_batch_size


def test_failed_reload_error_does_not_include_candidate_text() -> None:
    def factory(config: PipelineConfig) -> ArabicNormalizationPipeline:
        if config.preset == Preset.DEEP:
            raise RuntimeError("candidate text must not be exposed")
        return ArabicNormalizationPipeline(config)

    runtime = PipelineRuntime(factory=factory)
    outcome = runtime.reload(PipelineConfig(preset=Preset.DEEP))

    assert outcome.success is False
    assert "candidate text" not in (outcome.error_message or "")


def test_runtime_concurrent_reads_remain_successful_during_reload() -> None:
    runtime = PipelineRuntime()

    def read_one(_: int) -> str:
        return runtime.process("نص متزامن").normalized_text

    with ThreadPoolExecutor(max_workers=4) as executor:
        before = list(executor.map(read_one, range(8)))
        outcome = runtime.reload(PipelineConfig(preset="light"))
        after = list(executor.map(read_one, range(8)))

    assert outcome.success is True
    assert len(before) == len(after) == 8
    assert all(isinstance(value, str) for value in before + after)


def test_runtime_accepts_pipeline_factory_with_config_snapshot() -> None:
    seen = []

    def factory(config: PipelineConfig) -> ArabicNormalizationPipeline:
        seen.append(config.preset)
        return ArabicNormalizationPipeline(config)

    runtime = PipelineRuntime(PipelineConfig(preset="light"), factory=factory)
    runtime.reload(PipelineConfig(preset="deep"))

    assert seen == [Preset.LIGHT, Preset.DEEP]


def test_runtime_reload_rejects_non_config_without_mutating_state() -> None:
    runtime = PipelineRuntime()
    before = runtime.generation

    outcome = runtime.reload(object())  # type: ignore[arg-type]

    assert outcome.success is False
    assert outcome.generation == before
    assert runtime.generation == before


def test_runtime_file_reload_accepts_string_path(tmp_path) -> None:
    config_path = tmp_path / "pipeline.json"
    config_path.write_text('{"preset": "light"}', encoding="utf-8")
    runtime = PipelineRuntime()

    outcome = runtime.reload_from_file(str(config_path))

    assert outcome.success is True
    assert runtime.config.preset == Preset.LIGHT
