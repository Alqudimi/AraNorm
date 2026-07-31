"""Tests for new AraNorm features added in v1.2.0.

Covers:
- NumberWordsProcessor
- SentimentAnalyzer
- ArabicStemmer
- RootExtractor
- normalizer_utils helpers
- RedundancyProcessor / SentenceNormalizerProcessor
- PipelineConfig serialization (to_dict / from_dict / to_json / from_json)
- New CLI commands (dialect, keywords, compare, tokenize, sentiment)
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import List

import pytest

# ── NumberWordsProcessor ──────────────────────────────────────────────────────


class TestNumberWordsProcessor:
    def test_single_cardinal(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        assert proc.process("لدي ثلاثة كتب") == "لدي 3 كتب"

    def test_single_ten(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        assert proc.process("لدي عشرة أقلام") == "لدي 10 أقلام"

    def test_compound_number(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        result = proc.process("خمسة وعشرون طالباً")
        assert "25" in result

    def test_ordinal(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor(replace_ordinals=True)
        assert proc.process("جاء في المركز الثالث") == "جاء في المركز 3"

    def test_ordinal_disabled(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor(replace_ordinals=False)
        result = proc.process("الثالث")
        assert "الثالث" in result

    def test_zero(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        assert proc.process("صفر أخطاء") == "0 أخطاء"

    def test_hundred(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        assert proc.process("مئة طالب") == "100 طالب"

    def test_no_numbers(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        text = "أنا أحب العربية"
        assert proc.process(text) == text

    def test_empty_string(self):
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        assert proc.process("") == ""

    def test_process_with_context(self):
        from aranorm.core.base import ProcessorContext
        from aranorm.processors.number_words_processor import NumberWordsProcessor

        proc = NumberWordsProcessor()
        ctx = ProcessorContext()
        proc.process("ثلاثة كتب", ctx)
        assert "number_words" in ctx.applied_steps


# ── SentimentAnalyzer ─────────────────────────────────────────────────────────


class TestSentimentAnalyzer:
    def test_positive_text(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("أنا سعيد جداً بهذا النجاح الرائع")
        assert result.label == "positive"
        assert result.score > 0

    def test_negative_text(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("هذا فشل ذريع ومؤلم جداً")
        assert result.label == "negative"
        assert result.score < 0

    def test_neutral_text(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("أنا أذهب إلى المدرسة")
        assert result.label == "neutral"

    def test_negation_flips_polarity(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("هذا ليس جيداً")
        assert result.score < 0 or result.label in ("negative", "neutral")

    def test_empty_text(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("")
        assert result.label == "neutral"
        assert result.score == 0.0

    def test_result_has_words(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("أنا سعيد بنجاح صديقي الرائع")
        assert len(result.positive_words) > 0

    def test_batch_analysis(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        texts = ["أنا سعيد", "هذا سيء", "أذهب إلى البيت"]
        results = sa.analyze_batch(texts)
        assert len(results) == 3

    def test_confidence_range(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("هذا رائع جداً")
        assert 0.0 <= result.confidence <= 1.0

    def test_to_dict(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        result = sa.analyze("أنا سعيد")
        d = result.to_dict()
        assert "score" in d
        assert "label" in d
        assert "confidence" in d

    def test_lexicon_stats(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        stats = sa.get_lexicon_stats()
        assert stats["positive_words"] > 50
        assert stats["negative_words"] > 50

    def test_intensifier_boosts_score(self):
        from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

        sa = SentimentAnalyzer()
        base = sa.analyze("أنا سعيد").score
        intensified = sa.analyze("أنا سعيد جداً").score
        assert intensified >= base

    def test_analysis_exported_from_package(self):
        from aranorm.analysis import SentimentAnalyzer, SentimentResult
        assert SentimentAnalyzer is not None
        assert SentimentResult is not None


# ── ArabicStemmer ─────────────────────────────────────────────────────────────


class TestArabicStemmer:
    def test_strip_definite_article(self):
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        # Article is stripped; taa marbuta suffix is also removed by the stemmer
        assert stemmer.stem("المدرسة") == "مدرس"

    def test_strip_al(self):
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        # After stripping ال the prefix-stripper must not treat كـ as a particle
        assert stemmer.stem("الكتاب") == "كتاب"

    def test_strip_suffix_plural(self):
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        result = stemmer.stem("يكتبون")
        assert result in ("يكتب", "يكتبو", "كتبون")  # one valid strip

    def test_stem_sentence(self):
        from aranorm.utils.stemmer import stem_sentence

        result = stem_sentence("الطلاب يكتبون الدروس")
        assert "طلاب" in result or "الطلاب" in result

    def test_stem_function(self):
        from aranorm.utils.stemmer import stem

        result = stem("المدارس")
        assert result == "مدارس"

    def test_short_word_unchanged(self):
        from aranorm.utils.stemmer import stem

        assert stem("لا") == "لا"

    def test_stop_word_unchanged(self):
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        assert stemmer.stem("في") == "في"

    def test_batch(self):
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        results = stemmer.stem_batch(["الكتاب يتكلم", "المدرسة جميلة"])
        assert len(results) == 2

    def test_exported_from_utils(self):
        from aranorm.utils import ArabicStemmer, stem, stem_sentence
        assert ArabicStemmer is not None
        assert callable(stem)
        assert callable(stem_sentence)


# ── RootExtractor ─────────────────────────────────────────────────────────────


class TestRootExtractor:
    def test_basic_verb(self):
        from aranorm.utils.root_extractor import extract_root

        # كتب is a 3-letter root
        result = extract_root("كتب")
        assert result == "كتب"

    def test_none_for_unknown(self):
        from aranorm.utils.root_extractor import extract_root

        result = extract_root("xyz")
        assert result is None

    def test_empty_string(self):
        from aranorm.utils.root_extractor import extract_root

        assert extract_root("") is None

    def test_extractor_class(self):
        from aranorm.utils.root_extractor import RootExtractor

        extractor = RootExtractor()
        results = extractor.extract_batch(["كتب", "درس", "xyz"])
        assert len(results) == 3

    def test_exported_from_utils(self):
        from aranorm.utils import RootExtractor, extract_root
        assert callable(extract_root)
        assert RootExtractor is not None


# ── normalizer_utils ──────────────────────────────────────────────────────────


class TestNormalizerUtils:
    def test_normalize_alef(self):
        from aranorm.utils.normalizer_utils import normalize_alef

        assert normalize_alef("أحمد") == "احمد"
        assert normalize_alef("إبراهيم") == "ابراهيم"
        assert normalize_alef("آسيا") == "اسيا"  # آ → single ا (not doubled)

    def test_remove_diacritics(self):
        from aranorm.utils.normalizer_utils import remove_diacritics

        assert remove_diacritics("مَرْحَبًا") == "مرحبا"
        assert remove_diacritics("كِتَابٌ") == "كتاب"

    def test_normalize_unicode(self):
        from aranorm.utils.normalizer_utils import normalize_unicode

        # Should not corrupt Arabic text
        result = normalize_unicode("مرحبا")
        assert result == "مرحبا"

    def test_collapse_whitespace(self):
        from aranorm.utils.normalizer_utils import collapse_whitespace

        assert collapse_whitespace("أنا   طالب") == "أنا طالب"
        assert collapse_whitespace("  مرحبا  ") == "مرحبا"

    def test_is_arabic_text(self):
        from aranorm.utils.normalizer_utils import is_arabic_text

        assert is_arabic_text("مرحبا")
        assert not is_arabic_text("hello world")
        assert is_arabic_text("مرحبا hello")  # majority Arabic

    def test_count_arabic_words(self):
        from aranorm.utils.normalizer_utils import count_arabic_words

        assert count_arabic_words("مرحبا hello سلام") == 2
        assert count_arabic_words("hello world") == 0

    def test_extract_arabic_words(self):
        from aranorm.utils.normalizer_utils import extract_arabic_words

        result = extract_arabic_words("مرحبا hello سلام world")
        assert result == ["مرحبا", "سلام"]

    def test_char_ngrams(self):
        from aranorm.utils.normalizer_utils import char_ngrams

        result = char_ngrams("كتاب", n=3)
        assert "كتا" in result
        assert "تاب" in result

    def test_word_ngrams(self):
        from aranorm.utils.normalizer_utils import word_ngrams

        result = word_ngrams(["أنا", "أحب", "اللغة"], n=2)
        assert "أنا أحب" in result
        assert "أحب اللغة" in result

    def test_levenshtein(self):
        from aranorm.utils.normalizer_utils import levenshtein

        assert levenshtein("كتاب", "كتاب") == 0
        assert levenshtein("كتاب", "كتب") == 1
        assert levenshtein("", "أنا") == 3

    def test_fuzzy_match(self):
        from aranorm.utils.normalizer_utils import fuzzy_match

        results = fuzzy_match("كتاب", ["كتاب", "كتب", "مكتبة"])
        assert "كتاب" in results
        assert "كتب" in results

    def test_truncate_repeated_chars(self):
        from aranorm.utils.normalizer_utils import truncate_repeated_chars

        # max_run=2 keeps at most 2 consecutive identical chars
        assert truncate_repeated_chars("يااااا سلام", max_run=2) == "ياا سلام"
        assert truncate_repeated_chars("يااااا سلام", max_run=1) == "يا سلام"
        assert truncate_repeated_chars("جمييييل", max_run=2) == "جمييل"


# ── RedundancyProcessor & SentenceNormalizerProcessor ────────────────────────


class TestNormalizationProcessors:
    def test_redundancy_removes_invisible(self):
        from aranorm.processors.normalization_processor import RedundancyProcessor

        proc = RedundancyProcessor()
        text = "أنا\u200B طالب\u200D"
        assert proc.process(text) == "أنا طالب"

    def test_redundancy_collapses_spaces(self):
        from aranorm.processors.normalization_processor import RedundancyProcessor

        proc = RedundancyProcessor()
        assert proc.process("أنا   طالب") == "أنا طالب"

    def test_sentence_normalizer_removes_space_before_punc(self):
        from aranorm.processors.normalization_processor import SentenceNormalizerProcessor

        proc = SentenceNormalizerProcessor()
        result = proc.process("كيف حالك ؟ أنا بخير")
        assert "؟" in result
        # Space before ؟ should be removed
        assert " ؟" not in result

    def test_sentence_normalizer_removes_directional_marks(self):
        from aranorm.processors.normalization_processor import SentenceNormalizerProcessor

        proc = SentenceNormalizerProcessor()
        text = "أنا\u200E طالب"
        result = proc.process(text)
        assert "\u200E" not in result

    def test_exported_from_processors(self):
        from aranorm.processors import RedundancyProcessor, SentenceNormalizerProcessor
        assert RedundancyProcessor is not None
        assert SentenceNormalizerProcessor is not None


# ── PipelineConfig Serialization ──────────────────────────────────────────────


class TestPipelineConfigSerialization:
    def test_to_dict_has_all_keys(self):
        from aranorm import PipelineConfig

        cfg = PipelineConfig(preset="standard")
        d = cfg.to_dict()
        assert "preset" in d
        assert "remove_diacritics" in d
        assert "clean_urls" in d

    def test_to_dict_preset_value(self):
        from aranorm import PipelineConfig

        cfg = PipelineConfig(preset="deep")
        assert cfg.to_dict()["preset"] == "deep"

    def test_to_json_is_valid_json(self):
        from aranorm import PipelineConfig

        cfg = PipelineConfig(preset="standard")
        json_str = cfg.to_json()
        parsed = json.loads(json_str)
        assert parsed["preset"] == "standard"

    def test_from_json_roundtrip(self):
        from aranorm import PipelineConfig

        cfg = PipelineConfig(preset="light", remove_diacritics=False)
        json_str = cfg.to_json()
        cfg2 = PipelineConfig.from_json(json_str)
        assert cfg2.preset == cfg.preset
        assert cfg2.remove_diacritics == cfg.remove_diacritics

    def test_from_dict_partial(self):
        from aranorm import PipelineConfig

        cfg = PipelineConfig.from_dict({"preset": "deep"})
        assert cfg.preset.value == "deep"

    def test_from_dict_with_stop_words(self):
        from aranorm import PipelineConfig

        cfg = PipelineConfig.from_dict({
            "preset": "standard",
            "stop_words_config": {
                "mode": "remove",
                "scope": "universal",
                "remove_filler": True,
            }
        })
        assert cfg.stop_words_config is not None
        assert cfg.stop_words_config.mode == "remove"

    def test_to_dict_with_stop_words(self):
        from aranorm import PipelineConfig, StopWordsConfig

        cfg = PipelineConfig(
            preset="standard",
            stop_words_config=StopWordsConfig(mode="extract", scope="msa_only"),
        )
        d = cfg.to_dict()
        assert d["stop_words_config"]["mode"] == "extract"
        assert d["stop_words_config"]["scope"] == "msa_only"


# ── New CLI commands ──────────────────────────────────────────────────────────


class TestNewCLICommands:
    """Smoke-test the new CLI commands via the Python entrypoint."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "aranorm.cli"] + list(args),
            capture_output=True,
            text=True,
        )

    def test_dialect_command(self):
        result = self._run("dialect", "شلونك وايد زين")
        assert result.returncode == 0
        assert "GLF" in result.stdout or "Dialect" in result.stdout

    def test_dialect_json(self):
        result = self._run("dialect", "--json", "شلونك وايد زين")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "dialect" in data

    def test_keywords_command(self):
        result = self._run(
            "keywords",
            "الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات المتعاقبة"
        )
        assert result.returncode == 0

    def test_keywords_json(self):
        result = self._run(
            "keywords", "--json",
            "الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات المتعاقبة"
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "keywords" in data[0]

    def test_compare_command(self):
        result = self._run(
            "compare",
            "أنا أحب العربية",
            "أنا أعشق اللغة العربية",
        )
        assert result.returncode == 0
        assert "Verdict" in result.stdout or "verdict" in result.stdout.lower()

    def test_compare_json(self):
        result = self._run(
            "compare", "--json",
            "أنا أحب العربية",
            "أنا أعشق اللغة العربية",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "overall_similarity" in data
        assert "verdict" in data

    def test_tokenize_words(self):
        result = self._run("tokenize", "أهلاً بكم يا أصدقاء")
        assert result.returncode == 0

    def test_tokenize_sentences(self):
        result = self._run("tokenize", "--sentences", "أهلاً بكم. كيف حالكم؟")
        assert result.returncode == 0

    def test_tokenize_json(self):
        result = self._run("tokenize", "--json", "أهلاً بكم يا أصدقاء")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_sentiment_command(self):
        result = self._run("sentiment", "هذا المنتج رائع جداً")
        assert result.returncode == 0

    def test_sentiment_json(self):
        result = self._run("sentiment", "--json", "هذا المنتج رائع جداً")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert "label" in data[0]
        assert "score" in data[0]


# ── CorpusStopWordsBuilder extra tests ───────────────────────────────────────


class TestCorpusStopWordsBuilder:
    def test_builds_from_corpus(self):
        from aranorm.analysis.corpus_analyzer import CorpusStopWordsBuilder

        texts = [
            "الاقتصاد العالمي في تراجع مستمر",
            "الاقتصاد يعاني من أزمات متعاقبة",
            "التحولات الاقتصادية تؤثر على الجميع",
        ]
        builder = CorpusStopWordsBuilder(min_doc_frequency=2)
        result = builder.build(texts)
        assert result.corpus_size == 3
        assert isinstance(result.extracted_stop_words, frozenset)

    def test_empty_corpus(self):
        from aranorm.analysis.corpus_analyzer import CorpusStopWordsBuilder

        builder = CorpusStopWordsBuilder()
        result = builder.build([])
        assert result.corpus_size == 0
        assert len(result.extracted_stop_words) == 0


# ── TextComparator extra tests ────────────────────────────────────────────────


class TestTextComparatorExtra:
    def test_find_duplicates(self):
        from aranorm.analysis.text_comparator import TextComparator

        comparator = TextComparator()
        texts = [
            "أنا أحب اللغة العربية",
            "أنا أحب اللغة العربية",  # exact duplicate
            "الطقس جميل اليوم",
        ]
        duplicates = comparator.find_duplicates(texts, threshold=0.9)
        assert len(duplicates) >= 1
        assert duplicates[0][0] == 0
        assert duplicates[0][1] == 1

    def test_rank_by_similarity(self):
        from aranorm.analysis.text_comparator import TextComparator

        comparator = TextComparator()
        query = "أنا أحب العربية"
        candidates = [
            "أنا أحب العربية جداً",
            "الطقس جميل اليوم",
            "أنا أعشق اللغة العربية",
        ]
        ranked = comparator.rank_by_similarity(query, candidates, top_n=2)
        assert len(ranked) == 2
        # Most similar should be first
        assert ranked[0][1].overall_similarity >= ranked[1][1].overall_similarity
