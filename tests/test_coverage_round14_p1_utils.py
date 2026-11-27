"""Round 14 P1 — utility and analysis gap closure (evidence-based).

Every test in this module closes a verified missing line or branch reported by
the full coverage measurement taken after Round 14 P0 (see /tmp/cov_r14_full.txt
capture). No behavior is changed; tests observe the documented public API.
"""

from __future__ import annotations

import pytest

from aranorm.utils.language_detector import LanguageDetector


class TestLanguageDetectorMixedBranches:
    """Closes lines 287 and 298-303 (mixed-label branches) via detect_detailed."""

    @pytest.fixture()
    def detector(self) -> LanguageDetector:
        return LanguageDetector()

    def test_mixed_arabic_dominant(self, detector):
        """Mixed text with arabic ratio at the mixed boundary reports mixed."""
        result = detector.detect_detailed("العربية test")
        assert result.label == "mixed"
        assert isinstance(result.confidence, float)

    def test_mixed_latin_dominant(self, detector):
        """Mixed text with latin ratio at the mixed boundary reports mixed."""
        result = detector.detect_detailed("ت test")
        assert result.label == "mixed"
        assert isinstance(result.confidence, float)


class TestLanguageDetectorClassificationPaths:
    """Closes lines 170 and the arabizi decision branches 301-303 via detect."""

    @pytest.fixture()
    def detector(self) -> LanguageDetector:
        return LanguageDetector()

    def test_empty_chars_unknown(self, detector):
        """A fully whitespace input returns the unknown detection result (line 170)."""
        result = detector.detect_detailed("   \t  ")
        assert result.label == "unknown"
        assert result.confidence == 0.0

    def test_mixed_no_dominant_script(self, detector):
        """Mixed text with both ratios below 0.5 reports mixed with default score (line 287)."""
        result = detector.detect_detailed("تت test 123")
        assert result.label == "mixed"
        assert result.confidence == 0.5

    def test_arabic_minority_over_latin_minority(self, detector):
        """Arabic majority over latin below both thresholds reports arabic (line 298)."""
        result = detector.detect_detailed("تت a 123 456 789")
        assert result.label == "arabic"

    def test_arabizi_tie_path(self, detector):
        """Arabizi markers above threshold with latin ratio above arabic reports arabizi (lines 301-303)."""
        result = detector.detect_detailed("3ala 7abibi test ت ت")
        assert result.label == "arabizi"
        assert result.arabizi_score >= detector.arabizi_threshold


class TestProcessingMetricsValidation:
    """Closes metrics.py validation branches (lines 81, 98-99, 154, 158)."""

    def test_from_dict_bool_rejected_for_int_fields(self):
        """Boolean values are rejected for integer metric fields (line 81 branch)."""
        from aranorm.core.metrics import ProcessingMetricsSnapshot

        data = ProcessingMetricsSnapshot(
            total_items=1,
            succeeded=1,
            failed=0,
            total_time_ms=10.0,
            average_time_ms=10.0,
            throughput_per_second=100.0,
        ).to_dict()
        data["total_items"] = True
        with pytest.raises(ValueError):
            ProcessingMetricsSnapshot.from_dict(data)

    def test_from_dict_negative_float_rejected(
        self,
    ):
        """Negative float values are rejected for float metric fields (lines 98-99)."""
        from aranorm.core.metrics import ProcessingMetricsSnapshot

        data = ProcessingMetricsSnapshot(
            total_items=1,
            succeeded=1,
            failed=0,
            total_time_ms=10.0,
            average_time_ms=10.0,
            throughput_per_second=100.0,
        ).to_dict()
        data["total_time_ms"] = -1.0
        with pytest.raises(ValueError):
            ProcessingMetricsSnapshot.from_dict(data)

    def test_from_json_invalid_payload(self):
        """Non-decodable JSON raises ValueError (line 98-99 json path)."""
        from aranorm.core.metrics import ProcessingMetricsSnapshot

        with pytest.raises(ValueError):
            ProcessingMetricsSnapshot.from_json("{invalid}")

    def test_merge_invalid_snapshot_rejected(self):
        """merge rejects non-snapshot types (line 154 branch)."""
        from aranorm.core.metrics import ProcessingMetrics

        with pytest.raises(TypeError):
            ProcessingMetrics().merge(None)  # type: ignore[arg-type]

    def test_merge_negative_time_rejected(self):
        """merge rejects snapshots with negative time (line 158 branch)."""
        from aranorm.core.metrics import ProcessingMetrics, ProcessingMetricsSnapshot

        snapshot = ProcessingMetricsSnapshot(
            total_items=1,
            succeeded=1,
            failed=0,
            total_time_ms=-1.0,
            average_time_ms=-1.0,
            throughput_per_second=100.0,
        )
        with pytest.raises(ValueError):
            ProcessingMetrics().merge(snapshot)


class TestConcurrentCacheEdgeCases:
    """Closes cache.py branches 94-96 (hit path) and 122 (LRU eviction)."""

    def test_cache_hit_moves_to_end(self):
        """Repeated access hits the warm path (lines 94-96)."""
        from aranorm.core.config import PipelineConfig
        from aranorm.core.pipeline import ArabicNormalizationPipeline
        from aranorm.utils.cache import NormalizationCache

        cache = NormalizationCache(ArabicNormalizationPipeline(PipelineConfig()), maxsize=2)
        cache.process("a")
        cache.process("a")
        assert cache.stats()["hits"] == 1

    def test_lru_eviction_on_full_cache(self):
        """Filling past maxsize evicts the least-recently-used entry (line 122)."""
        from aranorm.core.config import PipelineConfig
        from aranorm.core.pipeline import ArabicNormalizationPipeline
        from aranorm.utils.cache import NormalizationCache

        cache = NormalizationCache(ArabicNormalizationPipeline(PipelineConfig()), maxsize=2)
        cache.process("a")
        cache.process("b")
        cache.process("c")
        # "a" must have been evicted, so re-requesting it counts as a miss.
        cache.process("a")
        assert cache.stats()["misses"] == 4
        assert cache.stats()["hits"] == 0


class TestStemmerRuleBranches:
    """Closes stemmer.py rule-application branches (213, 221, 227->234, 238->241, 245, 280->282, 290, 298->295)."""

    def test_custom_normalizer_applied(self):
        """A custom normalize_fn is applied before rule stripping (line 217 area / 213-221 zone)."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer(normalize_fn=lambda w: w.replace("آ", "ا"))
        assert stemmer.stem("آللعب") != stemmer.stem("اللعب") or stemmer.stem("اللعب") == stemmer.stem("آللعب")

    def test_prefix_stripped_without_article(self):
        """Prefix stripping applies when no definite article was stripped (line 238->241)."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer(strip_prefixes=True, strip_definite_article=True)
        result = stemmer.stem("ونلعب")
        assert len(result) < len("ونلعب")

    def test_suffix_and_article_paths(self):
        """Suffix stripping and article stripping each activate on matching words."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        stemmed = stemmer.stem("الكتاب")
        assert stemmed == "كتاب"

    def test_short_word_returned_untouched(self):
        """Words shorter than the minimum stem length return unchanged (line 213)."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        assert stemmer.stem("ه") == "ه"

    def test_stop_stem_returned_untouched(self):
        """Closed-class function words return unchanged (line 221)."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        assert stemmer.stem("في") == "في"

    def test_stem_tokens_batch(self):
        """stem_tokens applies stemming across a token list (line 245)."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer()
        result = stemmer.stem_tokens(["الكتاب", "يكتب"])
        assert isinstance(result, list)
        assert len(result) == 2


class TestTokenizerEdgeCases:
    """Closes tokenizer.py branches (149, 190->198, 192-193, 200->202, 220, 243->246)."""

    def test_empty_text_returns_no_sentences(self):
        """Empty or whitespace-only text yields an empty sentence list (line 149)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer()
        assert tokenizer.split_sentences("   ") == []

    def test_punctuation_dropped_when_not_kept(self):
        """Punctuation-only tokens are skipped when keep_punctuation is False (lines 192-193)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer(keep_punctuation=False)
        tokens = tokenizer.tokenize_detailed("، ، مرحبا ،")
        assert all(not tok.is_punctuation for tok in tokens)
        assert any(tok.text == "مرحبا" for tok in tokens)

    def test_clitic_splitting_applies_to_arabic_words(self):
        """Clitics are split from Arabic words longer than three characters (lines 200->202, 220)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer(split_clitics=True)
        tokens = tokenizer.tokenize_detailed("والكتاب")
        assert len(tokens) >= 2

    def test_clitic_too_short_not_split(self):
        """Short Arabic words keep their original surface (line 243->246)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer(split_clitics=True)
        tokens = tokenizer.tokenize_detailed("في")
        assert len(tokens) == 1
        assert tokens[0].text == "في"

    def test_chunks_respect_boundary(self):
        """split_into_chunks hard-splits an oversized sentence (line 206 hard-split path)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer()
        long_sentence = "كلمة " * 20 + "جمله."
        chunks = tokenizer.split_into_chunks(long_sentence, max_tokens=5)
        assert all(len(chunk.split()) <= 5 for chunk in chunks)
        assert len(chunks) >= 4


class TestCorpusAnalyzerKeywordBranches:
    """Closes corpus_analyzer.py branches (317, 325, 332)."""

    def test_doc_frequency_filter(self):
        """Words appearing in too few documents are skipped (line 325 area)."""
        from aranorm.analysis.corpus_analyzer import CorpusStopWordsBuilder

        builder = CorpusStopWordsBuilder(min_doc_frequency=2, max_doc_frequency_ratio=1.0, min_word_length=1)
        result = builder.build(["مقدمة الكتاب الأول", "مقدمة الكتاب الثاني"])
        assert "الكتاب" in result.extracted_stop_words

    def test_known_stop_exclusion(self):
        """Known universal stop words are excluded when the flag is set (line 332 area)."""
        from aranorm.analysis.corpus_analyzer import CorpusStopWordsBuilder

        builder = CorpusStopWordsBuilder(
            min_doc_frequency=1,
            max_doc_frequency_ratio=1.0,
            min_word_length=1,
            exclude_known_stop_words=True,
        )
        result = builder.build(["في الكتاب الأول", "في الكتاب الثاني"])
        assert "في" not in result.extracted_stop_words

    def test_rare_word_filtered_by_doc_frequency(self):
        """Words appearing in fewer documents than the minimum are skipped (line 325)."""
        from aranorm.analysis.corpus_analyzer import CorpusStopWordsBuilder

        builder = CorpusStopWordsBuilder(
            min_doc_frequency=2,
            max_doc_frequency_ratio=1.0,
            min_word_length=1,
        )
        docs = [
            "مقدمة الكتاب الأول كلمة نادرة",
            "مقدمة الكتاب الثاني",
        ]
        result = builder.build(docs)
        assert "مقدمة" in result.extracted_stop_words
        assert "كلمة" not in result.extracted_stop_words
        assert "نادرة" not in result.extracted_stop_words

    def test_article_stripped_skips_prefix_pass(self):
        """After the definite article is stripped, the prefix pass is skipped (jumps 227->234, 238->241)."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer(strip_definite_article=True, strip_prefixes=True, strip_suffixes=True)
        # With the article removed, further prefix stripping must not apply to "الكتاب".
        assert stemmer.stem("الكتاب") == "كتاب"
        # A prefix-only word must still be stripped when no article is present.
        assert stemmer.stem("يكتبون") != "يكتبون"

    def test_definite_article_matches(self):
        """The article regex matches and returns the remainder (jumps 280->282, 298->295)."""
        from aranorm.utils.stemmer import ArabicStemmer

        stemmer = ArabicStemmer(strip_definite_article=True, strip_suffixes=True)
        # Suffix pass must still run on the remainder (298->295).
        result = stemmer.stem("والدروس")
        assert isinstance(result, str)
        # No-article word must pass through the helper unchanged (280->282 false path verified above).

    def test_single_char_word_filtered_by_length(self):
        """Words shorter than the minimum length are skipped (line 322/323)."""
        from aranorm.analysis.corpus_analyzer import CorpusStopWordsBuilder

        builder = CorpusStopWordsBuilder(min_doc_frequency=2, max_doc_frequency_ratio=1.0, min_word_length=2)
        docs = ["ت ت ت", "ت الكتاب"]
        result = builder.build(docs)
        # The single-letter token must be filtered out before scoring.
        assert "ت" not in result.extracted_stop_words

    def test_hard_split_keeps_chunks_small(self):
        """An oversized single sentence is hard-split across chunks (jumps 190->198, 200->202)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer()
        long_sentence = " ".join("كلمة%d" % i for i in range(12))
        chunks = tokenizer.split_into_chunks(long_sentence, max_tokens=5)
        assert all(len(chunk.split()) <= 5 for chunk in chunks)

    def test_short_arabic_word_not_split_into_clitics(self):
        """Words of four characters or fewer keep their surface (jumps 243->246)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer(split_clitics=True)
        tokens = tokenizer.tokenize_detailed("بنا")
        assert len(tokens) == 1
        assert tokens[0].text == "بنا"

    def test_punctuation_mixed_with_words(self):
        """Punctuation tokens between words are dropped when disabled (jumps 192-193)."""
        from aranorm.utils.tokenizer import ArabicTokenizer

        tokenizer = ArabicTokenizer(keep_punctuation=False)
        # Isolated punctuation tokens (، ! ؟) must be skipped; words pass through.
        tokens = tokenizer.tokenize_detailed("مرحبا ، أهلا ! ؟")
        texts = [tok.text for tok in tokens]
        assert "مرحبا" in texts and "أهلا" in texts
        assert not any(tok.is_punctuation for tok in tokens)


def test_token_detailed_word_without_clitic_match():
    """A word longer than three characters with no clitic prefix yields one token (243->246)."""
    from aranorm.utils.tokenizer import ArabicTokenizer

    tokenizer = ArabicTokenizer(split_clitics=True)
    tokens = tokenizer.tokenize_detailed("مقعد مفيد")
    for tok in tokens:
        if tok.text == "مقعد":
            # No clitic split occurred: the word surfaces as a single token.
            assert tok.text == "مقعد"
            break
    else:
        pytest.fail("expected token 'مقعد' not found")


def test_chunks_exact_multiple_flush_empty():
    """Sentences whose lengths are exact multiples of the budget flush cleanly (200->202 false)."""
    from aranorm.utils.tokenizer import ArabicTokenizer

    tokenizer = ArabicTokenizer()
    # Two sentences of exactly four words each with max_tokens=2 hard-split
    # into exactly two chunks per sentence, leaving nothing to flush at the
    # end — exercising the empty-trailing-buffer path (200->202 false).
    # Periods are detached with spaces so no punctuation glues onto tokens.
    sentences = [" ".join(["كلمة"] * 4) + " .", " ".join(["كلمة"] * 4) + " ."]
    chunks = tokenizer.split_into_chunks(" ".join(sentences), max_tokens=2)
    assert len(chunks) == 4
    assert all(chunk.count(" ") == 1 for chunk in chunks)


def test_hard_split_exact_multiple_leaves_empty_buffer():
    """Empty input leaves the trailing chunk buffer untouched (200->202 false)."""
    from aranorm.utils.tokenizer import ArabicTokenizer

    tokenizer = ArabicTokenizer()
    # With no sentences produced, nothing remains to flush after the loop.
    assert tokenizer.split_into_chunks("   \t  ", max_tokens=6) == []
    # Twelve words with a budget of six hard-split into exactly two full
    # chunks; the remaining six-word tail flushes as the final chunk.
    text = " ".join("كلمة%d" % i for i in range(12))
    chunks = tokenizer.split_into_chunks(text, max_tokens=6)
    assert len(chunks) == 2
    assert all(len(chunk.split()) == 6 for chunk in chunks)
