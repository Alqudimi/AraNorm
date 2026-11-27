"""Round 13 P1 coverage for analysis, registry, and configuration boundaries."""

from __future__ import annotations

import json
import sys
import types

import pytest

from aranorm.analysis.keyword_extractor import KeywordExtractor
from aranorm.analysis.readability import ArabicReadabilityAnalyzer, ReadabilityResult
from aranorm.core.config import PipelineConfig
from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry, _Trie, _read_txt


def test_readability_handles_empty_and_non_arabic_inputs() -> None:
    analyzer = ArabicReadabilityAnalyzer()

    for text in ("", "   ", "123 !!!"):
        result = analyzer.analyze(text)
        assert result.readability_label == "unknown"
        assert result.score == 0.0
        assert result.word_count == 0


def test_readability_reports_metrics_and_serializes_result() -> None:
    result = ArabicReadabilityAnalyzer().analyze("هذا كتاب جيد. الكتاب مفيد!")

    assert isinstance(result, ReadabilityResult)
    assert result.sentence_count == 2
    assert result.word_count == 5
    assert 0.0 <= result.score <= 100.0
    assert result.to_dict()["word_count"] == result.word_count


def test_readability_batch_compare_and_label_boundaries() -> None:
    analyzer = ArabicReadabilityAnalyzer()
    batch = analyzer.analyze_batch(["نص قصير", "نص أطول قليلاً"])
    assert len(batch) == 2

    ascending = analyzer.compare(["هذا نص", "هذا نص طويل جداً للغاية"], sort_by="score")
    descending = analyzer.compare(["هذا نص", "هذا نص طويل جداً للغاية"], sort_by="score_desc")
    assert ascending[0][1].score <= ascending[1][1].score
    assert descending[0][1].score >= descending[1][1].score

    assert [analyzer._label(score) for score in (80, 60, 40, 20, 19.99)] == [
        "very_easy",
        "easy",
        "moderate",
        "complex",
        "very_complex",
    ]


def test_keyword_extractor_handles_empty_and_frequency_threshold() -> None:
    extractor = KeywordExtractor(min_freq=2, top_n=5)

    empty = extractor.extract("   ")
    assert empty.top_keywords == []
    assert empty.coverage_ratio == 0.0

    result = extractor.extract("اقتصاد اقتصاد سياسة")
    assert result.top_keywords == ["اقتصاد"]
    assert result.keyword_count == 1
    assert result.content_word_count == 2


def test_keyword_extractor_supports_idf_and_common_keywords() -> None:
    extractor = KeywordExtractor(
        top_n=4,
        reference_corpus=["اقتصاد عالمي", "اقتصاد محلي"],
    )

    result = extractor.extract("اقتصاد عالمي جديد")
    assert result.top_keywords
    assert all(isinstance(score, float) for _, score in result.keywords)
    assert extractor.extract_batch(["اقتصاد عالمي", "اقتصاد محلي"])
    common = extractor.extract_common_keywords(["اقتصاد عالمي", "اقتصاد محلي"], min_text_occurrences=2)
    assert common == [("اقتصاد", 2)]


def test_keyword_extractor_idf_build_is_document_frequency_based() -> None:
    extractor = KeywordExtractor(reference_corpus=["ألف باء", "ألف جيم"])

    assert extractor._idf is not None
    assert extractor._idf["ألف"] < extractor._idf["باء"]


def test_stop_words_registry_covers_fallbacks_and_custom_cache(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    words_file = tmp_path / "words.txt"
    words_file.write_text("# comment\n\nألف\n باء \n", encoding="utf-8")
    assert _read_txt(str(words_file)) == {"ألف", "باء"}
    assert _read_txt(str(tmp_path / "missing.txt")) == set()

    registry = StopWordsRegistry()
    custom = "__round13_custom_word__"
    assert registry.is_stop(custom) is False
    registry.add_custom({custom})
    assert registry.is_stop(custom) is True
    assert registry.is_stop("من", dialect="EGY") is True
    assert registry.get_words("unknown-scope") == set()
    assert registry.get_words("all")
    assert registry.get_words("social")
    assert registry.get_words("social")
    assert registry.get_words("numbers")
    assert registry.get_words("numbers")
    assert registry.get_words("dialect_aware", frozenset({"EGY", "UNKNOWN"}))
    assert registry.get_all_dialects()["EGY"]

    monkeypatch.setattr("aranorm.core.stop_words_registry._CAT_FILE", str(tmp_path / "missing.json"))
    fallback_registry = StopWordsRegistry()
    assert fallback_registry.get_by_category("anything") == set()
    assert fallback_registry._load_dialect("UNKNOWN").words() == set()


def test_trie_words_and_membership_contract() -> None:
    trie = _Trie()
    trie.insert("ألف")
    trie.insert("ألفا")

    assert "ألف" in trie
    assert "ألفا" in trie
    assert "ألفين" not in trie
    assert trie.words() == {"ألف", "ألفا"}


def test_config_repr_and_optional_yaml_error_paths(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config = PipelineConfig()
    assert "PipelineConfig(" in repr(config)
    assert "stop_words=disabled" in repr(config)

    with pytest.raises(TypeError, match="emit_steps_trace must be a boolean"):
        PipelineConfig(emit_steps_trace=1)  # type: ignore[arg-type]

    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(ImportError, match="PyYAML is required"):
        config.to_yaml()
    with pytest.raises(ImportError, match="PyYAML is required"):
        PipelineConfig.from_yaml("preset: light")

    fake_yaml = types.ModuleType("yaml")
    fake_yaml.dump = lambda data, **kwargs: "preset: light\\n"  # type: ignore[attr-defined]
    fake_yaml.safe_load = lambda value: None if not value.strip() else {"preset": "light"}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yaml", fake_yaml)
    assert "preset: light" in config.to_yaml()
    assert PipelineConfig.from_yaml("preset: light").preset.value == "light"
    assert PipelineConfig.from_yaml("").preset.value == "standard"

    json_path = tmp_path / "config.json"
    json_path.write_text(json.dumps({"preset": "light"}), encoding="utf-8")
    assert PipelineConfig.from_file(json_path).preset.value == "light"
    toml_path = tmp_path / "config.toml"
    toml_path.write_text("preset = 'light'", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported config file extension"):
        PipelineConfig.from_file(toml_path)
    with pytest.raises(ValueError, match="Unsupported config file extension"):
        PipelineConfig.from_file(tmp_path / "missing.toml")
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text("preset: light", encoding="utf-8")
    assert PipelineConfig.from_file(yaml_path).preset.value == "light"


def test_social_media_preset_applies_social_defaults() -> None:
    config = PipelineConfig.from_preset("social_media")

    assert config.clean_mentions is True
    assert config.clean_emojis is True
    assert config.clean_hashtags is False
    assert config.stop_words_config is not None

    custom = StopWordsConfig(mode="extract", scope="universal")
    preserved = PipelineConfig(preset="social_media", stop_words_config=custom)
    assert preserved.stop_words_config is custom


def test_config_validate_warns_for_conflicting_arabizi_flags() -> None:
    config = PipelineConfig(remove_non_arabic=True, handle_arabizi=True)
    with pytest.warns(UserWarning, match="will strip Arabizi"):
        assert config.validate() is config
