"""Contract tests for PipelineBuilder validation and aliases."""

from __future__ import annotations

import pytest

from aranorm.core.pipeline import PipelineBuilder


def test_cleaner_aliases_and_direct_removal_fields_are_applied() -> None:
    pipeline = (
        PipelineBuilder().add_cleaner(urls=False, html=False, remove_non_arabic=True, remove_english=True).build()
    )

    assert pipeline.config.clean_urls is False
    assert pipeline.config.clean_html is False
    assert pipeline.config.remove_non_arabic is True
    assert pipeline.config.remove_english is True


def test_normalizer_aliases_are_applied() -> None:
    pipeline = (
        PipelineBuilder()
        .add_normalizer(
            normalize_diacritics=False,
            normalize_hamza=False,
            normalize_unicode=False,
            handle_arabizi=True,
        )
        .build()
    )

    assert pipeline.config.remove_diacritics is False
    assert pipeline.config.normalize_hamza is False
    assert pipeline.config.normalize_unicode is False
    assert pipeline.config.handle_arabizi is True


@pytest.mark.parametrize(
    "method_name, option",
    [("add_cleaner", "typo"), ("add_normalizer", "typo")],
)
def test_unknown_builder_options_fail_loudly(method_name: str, option: str) -> None:
    builder = PipelineBuilder()
    method = getattr(builder, method_name)

    with pytest.raises(ValueError, match="Unknown"):
        method(**{option: True})


def test_unknown_option_validation_is_atomic() -> None:
    builder = PipelineBuilder().add_cleaner(urls=True)

    with pytest.raises(ValueError, match="Unknown"):
        builder.add_cleaner(urls=False, typo=True)

    assert builder.build().config.clean_urls is True


@pytest.mark.parametrize("method_name", ["add_cleaner", "add_normalizer"])
def test_builder_rejects_non_boolean_flags(method_name: str) -> None:
    builder = PipelineBuilder()
    method = getattr(builder, method_name)

    option = "urls" if method_name == "add_cleaner" else "normalize_hamza"
    with pytest.raises(TypeError, match="boolean"):
        method(**{option: "yes"})
