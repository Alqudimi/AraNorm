"""Operational introspection contracts for normalization pipelines."""

from aranorm import ArabicNormalizationPipeline


def test_configuration_fingerprint_is_stable_for_equivalent_configs() -> None:
    first = ArabicNormalizationPipeline.from_preset("standard")
    second = ArabicNormalizationPipeline.from_config_dict(first.config.to_dict())

    assert first.configuration_fingerprint() == second.configuration_fingerprint()


def test_configuration_fingerprint_changes_when_config_changes() -> None:
    first = ArabicNormalizationPipeline.from_preset("standard")
    second = ArabicNormalizationPipeline.from_preset("standard")
    second.config.clean_urls = not second.config.clean_urls

    assert first.configuration_fingerprint() != second.configuration_fingerprint()


def test_operational_description_is_versioned_and_contains_no_source_text() -> None:
    pipeline = ArabicNormalizationPipeline.from_preset("standard")

    description = pipeline.describe_operational()

    assert description["schema_version"] == 1
    assert description["config_fingerprint"] == pipeline.configuration_fingerprint()
    assert description["pipeline_class"] == "ArabicNormalizationPipeline"
    assert "config" in description
    assert "أحمد" not in repr(description)


def test_legacy_describe_shape_remains_available() -> None:
    pipeline = ArabicNormalizationPipeline.from_preset("light")

    description = pipeline.describe()

    assert description["preset"] == "light"
    assert "schema_version" not in description
    assert "config_fingerprint" not in description
