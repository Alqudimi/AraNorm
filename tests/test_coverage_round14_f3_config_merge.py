"""Round 14 F3 — ``PipelineConfig.merge`` composition tests.

Covers the new composition API that builds a new configuration by
combining an existing :class:`PipelineConfig` with either a plain
dictionary or another configuration instance, without mutating either
input.
"""

from __future__ import annotations

import pytest

from aranorm.core.config import PipelineConfig, Preset, StopWordsConfig


class TestPipelineConfigMerge:
    """Merge behaviour with dictionary and config overrides."""

    def test_merge_with_dict_boolean_flag(self):
        """A dictionary override replaces the matching boolean flag."""
        base = PipelineConfig(preset="light", remove_diacritics=False)
        merged = base.merge({"remove_diacritics": True})
        assert merged.remove_diacritics is True
        assert merged.preset == Preset.LIGHT

    def test_merge_with_config_instance(self):
        """Merging with another config keeps untouched fields from the base."""
        base = PipelineConfig(preset="standard", clean_html=False)
        other = PipelineConfig(preset="standard", clean_emails=False)
        merged = base.merge(other)
        assert merged.preset == Preset.STANDARD
        assert merged.clean_html is True
        assert merged.clean_emails is False

    def test_merge_leaves_inputs_untouched(self):
        """Neither the base nor the overrides are mutated by merge."""
        base = PipelineConfig(remove_diacritics=False)
        overrides = PipelineConfig(remove_diacritics=True)
        base.merge(overrides)
        assert base.remove_diacritics is False
        assert overrides.remove_diacritics is True

    def test_merge_nested_stop_words(self):
        """Stop-words settings are merged field-by-field, not replaced."""
        base = PipelineConfig(
            stop_words_config=StopWordsConfig(mode="extract", remove_filler=True, remove_internet=False)
        )
        merged = base.merge({"stop_words_config": {"remove_internet": True}})
        sw = merged.stop_words_config
        assert sw is not None
        assert sw.mode == "extract"
        assert sw.remove_filler is True
        assert sw.remove_internet is True

    def test_merge_nested_resource_limits(self):
        """Resource limits are merged field-by-field."""
        base = PipelineConfig()
        merged = base.merge({"resource_limits": {"max_batch_size": 256}})
        assert merged.resource_limits.max_batch_size == 256

    def test_merge_supported_dialects_replaces(self):
        """The dialect list is replaced wholesale when overridden."""
        base = PipelineConfig(supported_dialects=["egyptian"])
        merged = base.merge({"supported_dialects": ["gulf", "levantine"]})
        assert merged.supported_dialects == ["gulf", "levantine"]

    def test_merge_unknown_keys_ignored(self):
        """Unknown override keys do not break the merge operation."""
        base = PipelineConfig()
        merged = base.merge({"remove_diacritics": True, "bogus_option": 42})
        assert merged.remove_diacritics is True

    def test_merge_invalid_overrides_type(self):
        """A non-config/non-dict override raises TypeError."""
        base = PipelineConfig()
        with pytest.raises(TypeError):
            base.merge(123)  # type: ignore[arg-type]

    def test_merge_returns_new_instance(self):
        """Merge produces a distinct object instead of reusing inputs."""
        base = PipelineConfig()
        merged = base.merge({})
        assert merged is not base

    def test_merge_roundtrip_with_to_dict(self):
        """A merged configuration serialises to a complete dictionary."""
        base = PipelineConfig(preset="light", clean_urls=False)
        merged = base.merge({"clean_urls": True, "handle_arabizi": True})
        data = merged.to_dict()
        assert data["clean_urls"] is True
        assert data["handle_arabizi"] is True
        assert data["preset"] == "light"
