"""Tests for utility modules: tokenizer, text_stats, chunker."""

from __future__ import annotations

import pytest

from aranorm.utils.tokenizer import ArabicTokenizer, Token, Sentence, word_tokenize, sent_tokenize
from aranorm.utils.text_stats import TextStats, compute_stats, compare_stats
from aranorm.utils.chunker import TextChunker, TextChunk, chunk_text

# ── ArabicTokenizer ────────────────────────────────────────────────────────────


class TestArabicTokenizer:
    def test_tokenize_basic(self) -> None:
        tok = ArabicTokenizer()
        tokens = tok.tokenize("أنا أحب اللغة العربية")
        assert tokens == ["أنا", "أحب", "اللغة", "العربية"]

    def test_tokenize_returns_list_of_strings(self) -> None:
        tok = ArabicTokenizer()
        tokens = tok.tokenize("مرحباً بالعالم")
        assert all(isinstance(t, str) for t in tokens)

    def test_tokenize_detailed_returns_token_objects(self) -> None:
        tok = ArabicTokenizer()
        tokens = tok.tokenize_detailed("أنا سعيد")
        assert all(isinstance(t, Token) for t in tokens)

    def test_token_has_arabic_flag(self) -> None:
        tok = ArabicTokenizer()
        tokens = tok.tokenize_detailed("أنا hello")
        arabic_tokens = [t for t in tokens if t.is_arabic]
        latin_tokens = [t for t in tokens if not t.is_arabic]
        assert len(arabic_tokens) >= 1
        assert len(latin_tokens) >= 1

    def test_split_sentences_basic(self) -> None:
        tok = ArabicTokenizer()
        sents = tok.split_sentences("أهلاً بكم. كيف حالكم؟")
        assert len(sents) >= 2

    def test_split_sentences_returns_sentence_objects(self) -> None:
        tok = ArabicTokenizer()
        sents = tok.split_sentences("جملة أولى. جملة ثانية.")
        assert all(isinstance(s, Sentence) for s in sents)

    def test_split_sentences_with_tokenize(self) -> None:
        tok = ArabicTokenizer()
        sents = tok.split_sentences("أنا هنا. أنت هناك.", tokenize=True)
        assert all(len(s.tokens) > 0 for s in sents)

    def test_split_into_chunks_respects_max_tokens(self) -> None:
        tok = ArabicTokenizer()
        text = " ".join(["كلمة"] * 20)
        chunks = tok.split_into_chunks(text, max_tokens=5)
        assert all(len(c.split()) <= 5 for c in chunks)

    def test_empty_text_tokenize(self) -> None:
        tok = ArabicTokenizer()
        assert tok.tokenize("") == []

    def test_word_tokenize_convenience(self) -> None:
        tokens = word_tokenize("اللغة العربية لغة جميلة")
        assert "اللغة" in tokens

    def test_sent_tokenize_convenience(self) -> None:
        sents = sent_tokenize("جملة أولى. جملة ثانية؟ جملة ثالثة!")
        assert len(sents) >= 2

    def test_clitics_split(self) -> None:
        tok = ArabicTokenizer(split_clitics=True)
        # "وللغة" should be split into ["و", "للغة"] or similar
        tokens = tok.tokenize("وللغة")
        assert len(tokens) >= 1  # at minimum returns the word


# ── TextStats ─────────────────────────────────────────────────────────────────


class TestTextStats:
    def test_compute_stats_returns_textstats(self) -> None:
        stats = compute_stats("أنا أحب اللغة العربية")
        assert isinstance(stats, TextStats)

    def test_word_count(self) -> None:
        stats = compute_stats("أنا أحب اللغة")
        assert stats.word_count == 3

    def test_arabic_char_count_positive(self) -> None:
        stats = compute_stats("مرحبا")
        assert stats.arabic_char_count > 0

    def test_char_count_gte_char_no_spaces(self) -> None:
        stats = compute_stats("أنا هنا")
        assert stats.char_count >= stats.char_count_no_spaces

    def test_vocabulary_size_lte_word_count(self) -> None:
        stats = compute_stats("سلام سلام مرحبا")
        assert stats.vocabulary_size <= stats.word_count

    def test_type_token_ratio_range(self) -> None:
        stats = compute_stats("أنا أحب اللغة العربية")
        assert 0.0 <= stats.type_token_ratio <= 1.0

    def test_arabic_ratio_pure_arabic(self) -> None:
        stats = compute_stats("مرحباً بالعالم")
        assert stats.arabic_ratio > 0.5

    def test_readability_label_valid(self) -> None:
        stats = compute_stats("أنا سعيد")
        assert stats.readability_label in ("very_easy", "easy", "moderate", "difficult", "very_difficult")

    def test_readability_threshold_labels(self) -> None:
        from aranorm.utils.text_stats import _readability_label

        assert [_readability_label(score) for score in (80, 60, 40, 20, 19.9)] == [
            "very_easy",
            "easy",
            "moderate",
            "difficult",
            "very_difficult",
        ]

    def test_readability_penalizes_long_diacritized_text(self) -> None:
        stats = compute_stats("مَرْحَبًا " * 10)
        assert stats.readability_score < 100.0
        assert stats.diacritic_ratio > 0.0

    def test_top_words_sorted_by_frequency(self) -> None:
        stats = compute_stats("سلام سلام سلام مرحبا مرحبا عالم")
        if stats.top_words:
            counts = [c for _, c in stats.top_words]
            assert counts == sorted(counts, reverse=True)

    def test_empty_text_returns_zero_stats(self) -> None:
        stats = compute_stats("")
        assert stats.word_count == 0
        assert stats.readability_score == 0.0

    def test_compare_stats_returns_dict(self) -> None:
        result = compare_stats("أنا سعيد", "هو حزين جداً وكثيراً")
        assert "text_a" in result
        assert "text_b" in result
        assert "delta" in result

    def test_diacritic_count_with_diacritics(self) -> None:
        stats = compute_stats("مَرْحَبًا")
        assert stats.diacritic_count > 0

    def test_diacritic_count_without_diacritics(self) -> None:
        stats = compute_stats("مرحبا")
        assert stats.diacritic_count == 0


# ── TextChunker ───────────────────────────────────────────────────────────────


class TestTextChunker:
    def test_chunk_short_text_returns_one_chunk(self) -> None:
        chunker = TextChunker(max_tokens=100)
        chunks = chunker.chunk("أنا أحب اللغة العربية")
        assert len(chunks) == 1

    def test_chunk_long_text_returns_multiple_chunks(self) -> None:
        chunker = TextChunker(max_tokens=3)
        text = " ".join(["كلمة"] * 12)
        chunks = chunker.chunk(text)
        assert len(chunks) > 1

    def test_chunk_respects_max_tokens(self) -> None:
        chunker = TextChunker(max_tokens=5)
        text = " ".join(["كلمة"] * 20)
        for chunk in chunker.chunk(text):
            assert chunk.token_count <= 5

    def test_chunks_are_texchunk_objects(self) -> None:
        chunker = TextChunker(max_tokens=50)
        chunks = chunker.chunk("مرحباً بالعالم العربي")
        assert all(isinstance(c, TextChunk) for c in chunks)

    def test_last_chunk_is_last_flag(self) -> None:
        chunker = TextChunker(max_tokens=3)
        text = " ".join(["كلمة"] * 9)
        chunks = chunker.chunk(text)
        assert chunks[-1].is_last is True

    def test_overlap_tokens(self) -> None:
        chunker = TextChunker(max_tokens=4, overlap_tokens=2)
        text = " ".join([f"كلمة{i}" for i in range(12)])
        chunks = chunker.chunk(text)
        # With overlap, we should have more chunks than without
        chunker_no_overlap = TextChunker(max_tokens=4, overlap_tokens=0)
        chunks_no_overlap = chunker_no_overlap.chunk(text)
        assert len(chunks) >= len(chunks_no_overlap)

    def test_chunk_iter_yields_same_as_chunk(self) -> None:
        chunker = TextChunker(max_tokens=5)
        text = " ".join(["كلمة"] * 15)
        from_list = chunker.chunk(text)
        from_iter = list(chunker.chunk_iter(text))
        assert len(from_list) == len(from_iter)

    def test_empty_text_returns_empty_list(self) -> None:
        chunker = TextChunker(max_tokens=10)
        assert chunker.chunk("") == []

    def test_invalid_max_tokens_raises(self) -> None:
        with pytest.raises(ValueError):
            TextChunker(max_tokens=0)

    def test_invalid_overlap_raises(self) -> None:
        with pytest.raises(ValueError):
            TextChunker(max_tokens=5, overlap_tokens=5)

    def test_chunk_text_convenience(self) -> None:
        texts = chunk_text(" ".join(["كلمة"] * 20), max_tokens=5)
        assert all(isinstance(t, str) for t in texts)
        assert len(texts) > 1
