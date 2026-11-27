"""Round 13 P0 contract coverage for core boundaries and optional integrations."""

from __future__ import annotations

import sys
import types

import pytest

from aranorm.core.config import PipelineConfig, ResourceLimits
from aranorm.exceptions import (
    DialectDetectionError,
    IntegrationUnavailableError,
    InvalidTextError,
)
from aranorm.processors._base import RegexProcessor, TextProcessor, processor_transform
from aranorm.stages.dialect_id import DialectIdentifier


class UpperProcessor(TextProcessor):
    """Minimal concrete processor used to exercise the base contract."""

    def transform(self, text: str) -> str:
        return text.upper()


class LiteralRegexProcessor(RegexProcessor):
    pattern = __import__("re").compile(r"\d+")
    replacement = "#"


def test_text_processor_validates_transforms_and_records_context() -> None:
    from aranorm.core.base import ProcessorContext

    processor = UpperProcessor()
    context = ProcessorContext()

    assert processor.process("نص", context) == "نص"
    assert context.applied_steps == ["processor"]
    assert processor_transform(processor, "abc", None) == "ABC"


def test_text_processor_rejects_non_string_input() -> None:
    with pytest.raises(InvalidTextError, match="text must be str"):
        UpperProcessor().process(123)  # type: ignore[arg-type]


def test_text_processor_base_transform_is_abstract_by_contract() -> None:
    with pytest.raises(NotImplementedError):
        TextProcessor().transform("نص")


def test_regex_processor_replaces_all_matches() -> None:
    assert LiteralRegexProcessor().process("رقم 12 ثم 345") == "رقم # ثم #"


def test_dialect_identifier_handles_empty_non_arabic_and_msa_text() -> None:
    identifier = DialectIdentifier()

    assert identifier.identify("").dialect_label == "UNK"
    assert identifier.identify("plain english").confidence_score == 0.0
    msa = identifier.identify("نص تجريبي جميل")
    assert msa.dialect_label == "MSA"
    assert msa.is_msa is True
    assert msa.confidence_score == 0.40


def test_dialect_identifier_respects_supported_dialects_and_boundaries() -> None:
    identifier = DialectIdentifier(supported_dialects=["EGY"])

    result = identifier.identify("دلوقتي عايز أروح")
    assert result.dialect_label == "EGY"
    assert result.is_msa is False
    assert result.confidence_score > 0.55
    assert DialectIdentifier._count_marker("شلونك شلون", "شلون") == 1
    assert DialectIdentifier._count_marker("شلونك شلون", "شلونك") == 1


def test_dialect_identifier_reports_missing_camel_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "camel_tools", None)
    monkeypatch.setitem(sys.modules, "camel_tools.dialectid", None)

    with pytest.raises(IntegrationUnavailableError, match="CAMeL Tools is required"):
        DialectIdentifier(use_camel_tools=True).identify("نص عربي")


def test_dialect_identifier_wraps_camel_model_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenModel:
        @classmethod
        def pretrained(cls) -> "BrokenModel":
            raise RuntimeError("model unavailable")

    camel_tools = types.ModuleType("camel_tools")
    dialectid = types.ModuleType("camel_tools.dialectid")
    dialectid.DialectIdentifier = BrokenModel  # type: ignore[attr-defined]
    camel_tools.dialectid = dialectid  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "camel_tools", camel_tools)
    monkeypatch.setitem(sys.modules, "camel_tools.dialectid", dialectid)

    with pytest.raises(DialectDetectionError, match="could not identify"):
        DialectIdentifier(use_camel_tools=True).identify("نص عربي")


def test_dialect_identifier_normalizes_camel_label_and_reuses_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModel:
        calls = 0

        @classmethod
        def pretrained(cls) -> "FakeModel":
            cls.calls += 1
            return cls()

        def predict(self, texts: list[str]) -> list[tuple[str, float]]:
            assert texts == ["نص عربي"]
            return [("msa", 0.87)]

    camel_tools = types.ModuleType("camel_tools")
    dialectid = types.ModuleType("camel_tools.dialectid")
    dialectid.DialectIdentifier = FakeModel  # type: ignore[attr-defined]
    camel_tools.dialectid = dialectid  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "camel_tools", camel_tools)
    monkeypatch.setitem(sys.modules, "camel_tools.dialectid", dialectid)

    identifier = DialectIdentifier(use_camel_tools=True)
    first = identifier.identify("نص عربي")
    second = identifier.identify("نص عربي")

    assert first.dialect_label == "MSA"
    assert first.confidence_score == 0.87
    assert first.is_msa is True
    assert second == first
    assert FakeModel.calls == 1


def test_resource_limits_reject_invalid_shapes_and_round_trip() -> None:
    assert ResourceLimits.from_dict({"max_text_length": None}).max_text_length is None
    assert ResourceLimits(max_batch_size=2, max_workers=3).to_dict()["max_workers"] == 3

    with pytest.raises(TypeError, match="must be a dictionary"):
        ResourceLimits.from_dict([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unknown ResourceLimits"):
        ResourceLimits.from_dict({"unknown": 1})
    with pytest.raises(ValueError, match="positive integer"):
        ResourceLimits(max_text_length=0)
    with pytest.raises(ValueError, match="boolean"):
        ResourceLimits(reject_null_bytes=1)  # type: ignore[arg-type]


def test_pipeline_config_validates_dict_inputs_and_preserves_round_trip() -> None:
    config = PipelineConfig.from_dict(
        {
            "preset": "light",
            "resource_limits": {"max_batch_size": 4},
            "emit_steps_trace": True,
        }
    )
    assert config.preset.value == "light"
    assert config.resource_limits.max_batch_size == 4
    assert config.emit_steps_trace is True
    assert PipelineConfig.from_json(config.to_json()).to_dict() == config.to_dict()

    with pytest.raises(TypeError, match="expects a dictionary"):
        PipelineConfig.from_dict([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="emit_steps_trace"):
        PipelineConfig.from_dict({"emit_steps_trace": "yes"})
    with pytest.raises(ValueError, match="Unknown PipelineConfig"):
        PipelineConfig.from_dict({"typoed_field": True})
    with pytest.raises(TypeError, match="resource_limits"):
        PipelineConfig(resource_limits=object())  # type: ignore[arg-type]


def test_light_preset_applies_its_explicit_profile() -> None:
    config = PipelineConfig.from_preset("light", clean_urls=True, clean_emails=True)

    assert config.clean_urls is False
    assert config.clean_emails is False
    assert config.clean_html is False
