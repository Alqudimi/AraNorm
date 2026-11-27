"""Contract tests for dialect normalization strategies."""

import json
import sys
import types
from pathlib import Path

import pytest

from aranorm.core.base import ProcessorContext
from aranorm.exceptions import IntegrationUnavailableError, NormalizationError
from aranorm.stages import dialect_norm
from aranorm.stages.dialect_norm import (
    DialectNormalizer,
    DialectStrategy,
    ModelDialectStrategy,
    RuleBasedCODAStrategy,
    RuleBasedMSAStrategy,
    _load_dialect_mappings,
    _whole_word_replace,
)


def test_whole_word_replace_does_not_change_embedded_terms() -> None:
    text = "هاذا هاذاك،هاذا"

    assert _whole_word_replace(text, "هاذا", "هذا") == "هذا هاذاك،هاذا"


def test_coda_strategy_applies_ordered_safe_replacements() -> None:
    strategy = RuleBasedCODAStrategy()

    normalized = strategy.normalize("هاذا هاذه انشالله ماشاءالله الاشياء اكل")

    assert normalized == "هذا هذه إن شاء الله ما شاء الله الأشياء أكل"
    assert strategy.normalize("هاذاك") == "هاذاك"


def test_msa_strategy_uses_bundled_mappings_and_whole_words() -> None:
    strategy = RuleBasedMSAStrategy()

    normalized = strategy.normalize("شلونك وايد زين شلونكم")

    assert normalized != "شلونك وايد زين شلونكم"
    assert "شلونكم" in normalized
    assert strategy.normalize("شلونكلام") == "شلونكلام"
    assert _load_dialect_mappings()


def test_normalizer_validates_target_and_records_context() -> None:
    with pytest.raises(ValueError, match="unsupported dialect target"):
        DialectNormalizer("unknown")

    context = ProcessorContext()
    normalizer = DialectNormalizer("coda")
    result = normalizer.process("هاذا", context)

    assert result == "هذا"
    assert context.applied_steps == ["normalize_to_coda"]


def test_normalizer_accepts_custom_strategy() -> None:
    class UpperStrategy(DialectStrategy):
        def normalize(self, text: str) -> str:
            return text.upper()

    normalizer = DialectNormalizer("msa", msa_strategy=UpperStrategy())

    assert normalizer.process("abc") == "ABC"


def test_model_strategy_reports_missing_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", None)
    strategy = ModelDialectStrategy("example/model")

    with pytest.raises(IntegrationUnavailableError, match="Transformers is required"):
        strategy.normalize("نص")


def test_model_strategy_loads_lazily_and_decodes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTokenizer:
        calls = 0

        @classmethod
        def from_pretrained(cls, model_name: str) -> "FakeTokenizer":
            cls.calls += 1
            assert model_name == "example/model"
            return cls()

        def __call__(self, text: str, return_tensors: str) -> dict:
            assert text == "نص"
            assert return_tensors == "pt"
            return {"input_ids": [1]}

        def decode(self, generated: object, skip_special_tokens: bool) -> str:
            assert generated == [2]
            assert skip_special_tokens is True
            return "نص موحد"

    class FakeModel:
        calls = 0
        devices: list[str] = []

        @classmethod
        def from_pretrained(cls, model_name: str) -> "FakeModel":
            cls.calls += 1
            assert model_name == "example/model"
            return cls()

        def to(self, device: str) -> None:
            self.devices.append(device)

        def generate(self, **encoded: object) -> list[list[int]]:
            assert encoded == {"input_ids": [1], "max_new_tokens": 32}
            return [[2]]

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = FakeTokenizer  # type: ignore[attr-defined]
    fake_transformers.AutoModelForSeq2SeqLM = FakeModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    strategy = ModelDialectStrategy("example/model", device="cpu", max_new_tokens=32)
    assert strategy.normalize("نص") == "نص موحد"
    assert strategy.normalize("نص") == "نص موحد"
    assert FakeTokenizer.calls == 1
    assert FakeModel.calls == 1
    assert FakeModel.devices == ["cpu"]


def test_model_strategy_wraps_runtime_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenTokenizer:
        @classmethod
        def from_pretrained(cls, model_name: str) -> "BrokenTokenizer":
            raise RuntimeError("broken model")

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = BrokenTokenizer  # type: ignore[attr-defined]
    fake_transformers.AutoModelForSeq2SeqLM = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    with pytest.raises(NormalizationError, match="model normalization failed"):
        ModelDialectStrategy("broken/model").normalize("نص")


def test_invalid_mapping_payload_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    invalid_path = tmp_path / "dialect_mappings.json"
    invalid_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    monkeypatch.setattr(dialect_norm, "_DATA_DIR", tmp_path)
    _load_dialect_mappings.cache_clear()

    with pytest.raises(ValueError, match="must be a JSON object"):
        _load_dialect_mappings()

    _load_dialect_mappings.cache_clear()
