"""Defensive tests for configuration contracts and persistence."""

from __future__ import annotations

import json

import pytest

from aranorm import PipelineConfig, StopWordsConfig
from aranorm.exceptions import ConfigurationError


def test_pipeline_presets_apply_expected_safe_defaults() -> None:
    light = PipelineConfig.from_preset("light")
    deep = PipelineConfig.from_preset("deep")
    social = PipelineConfig.from_preset("social_media")

    assert light.clean_urls is False
    assert light.clean_html is False
    assert deep.normalize_repeated_chars is True
    assert social.clean_mentions is True
    assert social.clean_emojis is True
    assert social.stop_words_config is not None
    assert social.stop_words_config.remove_arabizi is True


def test_copy_with_is_non_mutating_and_preserves_nested_config() -> None:
    base = PipelineConfig(
        supported_dialects=["GLF"],
        stop_words_config=StopWordsConfig.for_dialect("GLF"),
    )
    variant = base.copy_with(clean_emojis=True)

    assert variant is not base
    assert variant.clean_emojis is True
    assert base.clean_emojis is False
    assert variant.supported_dialects == ["GLF"]
    assert variant.stop_words_config == base.stop_words_config


def test_stop_words_config_helpers_and_immutability() -> None:
    social = StopWordsConfig.for_social_media()
    dialect = StopWordsConfig.for_dialect("glf", "EGY")
    count = StopWordsConfig.count_only()

    assert social.remove_filler is True
    assert social.remove_internet is True
    assert social.remove_numbers is True
    assert dialect.scope == "dialect_aware"
    assert dialect.dialects == frozenset({"GLF", "EGY"})
    assert count.mode == "count"
    with pytest.raises(AttributeError):
        count.mode = "remove"  # type: ignore[misc]


@pytest.mark.parametrize("field, value", [("mode", "invalid"), ("scope", "invalid")])
def test_stop_words_config_rejects_invalid_values(field: str, value: str) -> None:
    kwargs = {field: value}
    with pytest.raises(ValueError):
        StopWordsConfig(**kwargs)


def test_stop_words_config_rejects_unknown_dialect() -> None:
    with pytest.raises(ValueError, match="Unknown dialect"):
        StopWordsConfig(scope="dialect_aware", dialects=frozenset({"MARS"}))


def test_pipeline_validate_rejects_inconsistent_stop_words_scope() -> None:
    dialect_cfg = PipelineConfig(stop_words_config=StopWordsConfig(scope="dialect_aware"))
    with pytest.raises(ConfigurationError, match="dialect_aware"):
        dialect_cfg.validate()

    custom_cfg = PipelineConfig(stop_words_config=StopWordsConfig(scope="custom"))
    with pytest.raises(ConfigurationError, match="custom"):
        custom_cfg.validate()


def test_pipeline_validate_warns_for_conflicting_script_flags() -> None:
    config = PipelineConfig(remove_non_arabic=True, handle_arabizi=True)
    with pytest.warns(UserWarning, match="strip Arabizi"):
        assert config.validate() is config


def test_from_dict_rejects_unknown_and_malformed_nested_values() -> None:
    original = {"preset": "standard", "stop_words_config": {"mode": "count"}}
    with pytest.raises(ValueError, match="Unknown PipelineConfig field"):
        PipelineConfig.from_dict({"unexpected": True})
    assert original == {"preset": "standard", "stop_words_config": {"mode": "count"}}

    with pytest.raises(TypeError, match="stop_words_config must be a dictionary"):
        PipelineConfig.from_dict({"stop_words_config": "not-a-mapping"})


def test_yaml_and_file_round_trips(tmp_path) -> None:
    pytest.importorskip("yaml")
    config = PipelineConfig(
        preset="deep",
        supported_dialects=["GLF", "MSA"],
        stop_words_config=StopWordsConfig.for_social_media(),
    )
    json_path = tmp_path / "config.json"
    yaml_path = tmp_path / "config.yaml"
    json_path.write_text(config.to_json(), encoding="utf-8")
    yaml_path.write_text(config.to_yaml(), encoding="utf-8")

    from_json = PipelineConfig.from_file(json_path)
    from_yaml = PipelineConfig.from_file(yaml_path)
    assert from_json.to_dict() == config.to_dict()
    assert from_yaml.to_dict() == config.to_dict()


def test_from_file_rejects_unsupported_extension_and_missing_file(tmp_path) -> None:
    unsupported = tmp_path / "config.toml"
    unsupported.write_text("preset = 'standard'", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        PipelineConfig.from_file(unsupported)

    with pytest.raises(FileNotFoundError):
        PipelineConfig.from_file(tmp_path / "missing.json")


def test_json_round_trip_preserves_arabic_and_is_valid() -> None:
    config = PipelineConfig(supported_dialects=["GLF"])
    payload = config.to_json(ensure_ascii=False)
    assert json.loads(payload)["supported_dialects"] == ["GLF"]
    assert PipelineConfig.from_json(payload).to_dict() == config.to_dict()
