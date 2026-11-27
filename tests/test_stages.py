"""Integration tests for pipeline stages."""

import pytest

from aranorm.core.base import ProcessorContext
from aranorm.stages import (
    ContentCleaner,
    DialectIdentification,
    DialectIdentifier,
    DialectNormalizer,
    MorphologicalProcessor,
    OrthographicNormalizer,
    RuleBasedCODAStrategy,
    RuleBasedMSAStrategy,
)
from tests.fixtures.sample_texts import DIALECT_MARKERS

# ────────────────────────────────────────────────────────────────────────────
# DialectIdentifier
# ────────────────────────────────────────────────────────────────────────────


def test_dialect_identifier_fallback_returns_structured_result():
    result = DialectIdentifier().identify("شلونك شخبارك اليوم")
    assert result.dialect_label == "GLF"
    assert result.confidence_score > 0
    assert result.is_msa is False


def test_dialect_identifier_returns_msa_for_formal_text():
    result = DialectIdentifier().identify("أعلن الرئيس عن خطة لتطوير القطاع الاقتصادي وبالتالي")
    assert result.dialect_label == "MSA"
    assert result.is_msa is True


@pytest.mark.parametrize(
    "dialect,samples",
    [
        ("EGY", DIALECT_MARKERS["EGY"]),
        ("GLF", DIALECT_MARKERS["GLF"]),
        ("LEV", DIALECT_MARKERS["LEV"]),
    ],
)
def test_dialect_identifier_recognizes_major_dialects(dialect, samples):
    identifier = DialectIdentifier()
    for sample in samples:
        result = identifier.identify(sample)
        assert result.dialect_label == dialect, f"Expected {dialect}, got {result.dialect_label} for: {sample!r}"


def test_dialect_identifier_unknown_text_returns_unk_or_msa():
    result = DialectIdentifier().identify("123 hello world")
    assert result.dialect_label in ("UNK", "MSA")


def test_dialect_identifier_empty_string_returns_unk():
    result = DialectIdentifier().identify("")
    assert result.dialect_label in ("UNK", "MSA")


def test_dialect_identifier_camel_raises_without_package():
    from aranorm.exceptions import IntegrationUnavailableError

    identifier = DialectIdentifier(use_camel_tools=True)
    with pytest.raises(IntegrationUnavailableError):
        identifier.identify("نص عربي")


def test_dialect_identifier_returns_frozen_dataclass():
    result = DialectIdentifier().identify("شو أخبارك")
    assert isinstance(result, DialectIdentification)
    with pytest.raises(Exception):  # frozen dataclass
        result.dialect_label = "EGY"  # type: ignore[misc]


def test_dialect_identifier_supported_dialects_filter():
    identifier = DialectIdentifier(supported_dialects=["EGY"])
    result = identifier.identify("عايز أروح دلوقتي")
    assert result.dialect_label == "EGY"


# ────────────────────────────────────────────────────────────────────────────
# DialectNormalizer
# ────────────────────────────────────────────────────────────────────────────


def test_dialect_normalizer_coda_fixes_common_errors():
    normalizer = DialectNormalizer("coda")
    result = normalizer.process("هاذا الاشياء انشاءالله")
    assert "هذا" in result
    assert "الأشياء" in result
    assert "إن شاء الله" in result


def test_dialect_normalizer_msa_maps_gulf_words():
    normalizer = DialectNormalizer("msa")
    text = "شلون الحين أبغى شيء"
    result = normalizer.process(text)
    assert "كيف" in result
    assert "الآن" in result
    assert "أريد" in result


def test_dialect_normalizer_msa_maps_egyptian_words():
    normalizer = DialectNormalizer("msa")
    text = "ليه مش بتيجي دلوقتي"
    result = normalizer.process(text)
    assert "لماذا" in result
    assert "الآن" in result


def test_dialect_normalizer_msa_maps_levantine_words():
    normalizer = DialectNormalizer("msa")
    text = "شو بدي أعمل هلق"
    result = normalizer.process(text)
    assert "ماذا" in result
    assert "أريد" in result
    assert "الآن" in result


def test_dialect_normalizer_records_step_in_context():
    context = ProcessorContext()
    DialectNormalizer("msa").process("نص", context)
    assert "normalize_to_msa" in context.applied_steps


def test_dialect_normalizer_invalid_target_raises():
    with pytest.raises(ValueError, match="unsupported"):
        DialectNormalizer("unknown_target")


def test_rule_based_coda_strategy_direct():
    strategy = RuleBasedCODAStrategy()
    assert strategy.normalize("هاذا") == "هذا"
    assert strategy.normalize("هاذه") == "هذه"
    assert strategy.normalize("الاشياء") == "الأشياء"


def test_rule_based_msa_strategy_direct():
    strategy = RuleBasedMSAStrategy()
    result = strategy.normalize("شلون الحين وايد كتير")
    assert "كيف" in result
    assert "الآن" in result


# ────────────────────────────────────────────────────────────────────────────
# OrthographicNormalizer
# ────────────────────────────────────────────────────────────────────────────


def test_orthographic_normalizer_default_config():
    from aranorm.core.config import PipelineConfig

    normalizer = OrthographicNormalizer(PipelineConfig())
    result = normalizer.process("أحمَدُ إبراهيمـ آمنَ ٱللهُ")
    assert "أ" not in result
    assert "إ" not in result
    assert "ـ" not in result


def test_orthographic_normalizer_records_steps():
    from aranorm.core.config import PipelineConfig

    context = ProcessorContext()
    OrthographicNormalizer(PipelineConfig()).process("أ", context)
    assert len(context.applied_steps) > 0


# ────────────────────────────────────────────────────────────────────────────
# ContentCleaner
# ────────────────────────────────────────────────────────────────────────────


def test_content_cleaner_removes_configured_content():
    from aranorm.core.config import PipelineConfig

    config = PipelineConfig(clean_urls=True, clean_html=True, clean_emails=True)
    cleaner = ContentCleaner(config)
    text = "<p>زوروا</p> https://example.com راسلنا a@b.com"
    result = cleaner.process(text)
    assert "https://" not in result
    assert "<p>" not in result
    assert "a@b.com" not in result


# ────────────────────────────────────────────────────────────────────────────
# MorphologicalProcessor
# ────────────────────────────────────────────────────────────────────────────


def test_morphological_processor_accepts_injected_callable():
    processor = MorphologicalProcessor(lambda text: [{"token": text}])
    assert processor.analyze("لغة") == [{"token": "لغة"}]


def test_morphological_processor_accepts_injected_object():
    class FakeAnalyzer:
        def analyze(self, text):
            return [{"lemma": text}]

    processor = MorphologicalProcessor(FakeAnalyzer())
    assert processor.analyze("كتب") == [{"lemma": "كتب"}]


def test_morphological_processor_raises_without_analyzer():
    from aranorm.exceptions import IntegrationUnavailableError

    processor = MorphologicalProcessor()
    with pytest.raises(IntegrationUnavailableError):
        processor.analyze("نص")


# ────────────────────────────────────────────────────────────────────────────
# ProcessorContext
# ────────────────────────────────────────────────────────────────────────────


def test_processor_context_records_steps():
    context = ProcessorContext()
    from aranorm.processors import ALEFProcessor

    ALEFProcessor().process("أ", context)
    ALEFProcessor().process("أ", context)
    assert context.applied_steps == ["normalize_alef"]


def test_processor_context_records_multiple_different_steps():
    from aranorm.processors import ALEFProcessor, DiacriticsProcessor

    context = ProcessorContext()
    ALEFProcessor().process("أحمد", context)
    DiacriticsProcessor().process("مَرْحَبًا", context)
    assert "normalize_alef" in context.applied_steps
    assert "normalize_diacritics" in context.applied_steps
    assert len(context.applied_steps) == 2
