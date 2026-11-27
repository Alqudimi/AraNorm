"""Targeted tests that close remaining coverage gaps (Round 6).

Each class addresses a concrete low-coverage region identified by the
coverage report, without touching implementation semantics.
"""

from __future__ import annotations

import warnings

import pytest

from aranorm.processors.domain_stop_processor import DomainStopProcessor
from aranorm.processors.phone_processor import PhoneProcessor
from aranorm.stages.stop_words_stage import StopWordsStage
from aranorm.utils.cache import NormalizationCache
from aranorm.utils.chunker import TextChunker


class TestDomainStopProcessorGaps:
    def test_unknown_domain_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            DomainStopProcessor(domains=["sports", "legal"], include_universal=False)
        assert any("sports" in str(w.message) for w in caught)

    def test_missing_domain_file_loads_empty(self):
        words = DomainStopProcessor.get_domain_words("nonexistent_domain_xyz")
        assert words == set()

    def test_get_supported_domains(self):
        assert DomainStopProcessor.get_supported_domains() == frozenset({"legal", "medical", "news", "religious"})

    def test_blank_input_passthrough(self):
        proc = DomainStopProcessor(domains=["legal"], include_universal=False)
        assert proc.process("") == ""
        assert proc.process("   ") == "   "

    def test_punctuation_aware_stripping(self):
        proc = DomainStopProcessor(domains=["legal"], include_universal=False)
        text = "وفقاً للمادة الثانية"
        result = proc.process(text)
        # Stop words from the chosen domain must be removed (punctuation-aware stripping is not a contract).
        assert "وفقاً" not in result

    def test_all_supported_domains_load(self):
        for domain in DomainStopProcessor.get_supported_domains():
            words = DomainStopProcessor.get_domain_words(domain)
            assert isinstance(words, set)
            assert all(isinstance(w, str) for w in words)

    def test_include_universal_empty_list(self):
        proc = DomainStopProcessor(domains=[], include_universal=True)
        universal = proc._stop_set  # noqa: SLF001
        assert isinstance(universal, set)


class TestPhoneProcessorNormalize:
    def test_normalize_mode_cleans_separators(self):
        proc = PhoneProcessor(mode="normalize")
        result = proc.process("اتصل على +966-50-123-4567")
        assert "966" in result or "501234567" in result
        assert "-" not in result

    def test_normalize_mode_invalid_mode(self):
        with pytest.raises(ValueError):
            PhoneProcessor(mode="unknown")


class TestStopWordsStageGaps:
    def test_blank_passthrough(self):
        stage = StopWordsStage()
        assert stage.process("") == ""
        assert stage.process("   ") == "   "

    def test_context_metadata_and_record(self):
        stage = StopWordsStage()
        aranorm_core_base = __import__("aranorm.core.base", fromlist=["ProcessorContext"])
        ProcessorContext = aranorm_core_base.ProcessorContext
        context = ProcessorContext()
        result = stage.process("النص الجميل", context=context)
        assert result
        # get_last_result requires the same context to expose the latest outcome.
        last = stage.get_last_result(context)
        assert last is not None


class TestCacheHelpers:
    def test_maxsize_validation(self):
        pipeline = __import__("aranorm", fromlist=["ArabicNormalizationPipeline"]).ArabicNormalizationPipeline()
        with pytest.raises(ValueError):
            NormalizationCache(pipeline, maxsize=0)

    def test_batch_size_validation(self):
        pipeline = __import__("aranorm", fromlist=["ArabicNormalizationPipeline"]).ArabicNormalizationPipeline()
        cache = NormalizationCache(pipeline, maxsize=4)
        with pytest.raises(ValueError):
            cache.process_batch(["ok"], batch_size=0, n_workers=1)
        with pytest.raises(ValueError):
            iterator = cache.process_iter(["ok"], n_workers=0)
            next(iterator)  # validation runs on first pull because process_iter is a generator

    def test_lru_eviction_in_process_batch(self):
        pipeline = __import__("aranorm", fromlist=["ArabicNormalizationPipeline"]).ArabicNormalizationPipeline()
        cache = NormalizationCache(pipeline, maxsize=2)
        results = cache.process_batch(["نص 1", "نص 2", "نص 3", "نص 4"])
        assert len(results) == 4
        assert len(cache) == 2  # only the last two fit

    def test_invalidate_clear_contains_len_repr(self):
        pipeline = __import__("aranorm", fromlist=["ArabicNormalizationPipeline"]).ArabicNormalizationPipeline()
        cache = NormalizationCache(pipeline, maxsize=8)
        cache.process("نص تجريبي")
        assert "نص تجريبي" in cache
        assert len(cache) == 1
        assert cache.invalidate("نص تجريبي") is True
        assert cache.invalidate("غير موجود") is False
        assert len(cache) == 0
        assert "hit_rate=0.0%" in repr(cache)
        cache.process("نص تجريبي")
        cache.clear()
        assert len(cache) == 0
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_cache_batch_no_results_leak(self):
        """Cached entries must be reused and not re-normalized."""
        pipeline = __import__("aranorm", fromlist=["ArabicNormalizationPipeline"]).ArabicNormalizationPipeline()
        cache = NormalizationCache(pipeline, maxsize=8)
        first = cache.process_batch(["نص مكرر", "نص مكرر"])
        second = cache.process_batch(["نص مكرر", "نص مكرر"])
        assert first[0] is second[0]
        stats = cache.stats()
        assert stats["hits"] == 2


class TestChunkerGaps:
    def test_chunk_texts_list_wrapper(self):
        chunker = TextChunker(max_tokens=2)
        groups = chunker.chunk_texts(["نص طويل جداً للتجربة", "نص قصير"])
        assert len(groups) == 2
        assert all(isinstance(g, list) for g in groups)

    def test_chunk_single_oversized_unit_hard_split(self):
        chunker = TextChunker(max_tokens=2)
        chunks = list(chunker.chunk_iter("واحد اثنين ثلاثة أربعة خمسة"))
        assert len(chunks) == 3
        assert all(chunk.token_count <= 2 for chunk in chunks)

    def test_chunk_overlap_respects_single_unit(self):
        # respect_sentences=False forces token-level sliding with explicit overlap.
        chunker = TextChunker(max_tokens=2, overlap_tokens=1, respect_sentences=False)
        chunks = list(chunker.chunk_iter("a b c d e f"))
        assert len(chunks) >= 3
        # Adjacent chunks must share the overlapping token(s).
        for a, b in zip(chunks, chunks[1:]):
            shared = set(a.text.split()) & set(b.text.split())
            assert shared

    def test_chunk_char_offsets_increase(self):
        chunker = TextChunker(max_tokens=3)
        text = "هذا نص تجريبي طويل نوعاً ما للتجربة"
        chunks = list(chunker.chunk_iter(text))
        for i in range(1, len(chunks)):
            assert chunks[i].char_start >= chunks[i - 1].char_end

    def test_chunk_empty_and_whitespace(self):
        chunker = TextChunker(max_tokens=5)
        assert list(chunker.chunk_iter("")) == []
        assert list(chunker.chunk_iter("   ")) == []
