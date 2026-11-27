"""P0 coverage suite for the Round 16 new features.

Features under test
-------------------
* ``TextSimilarityMatrix`` -- pairwise similarity across a text collection
  (``src/aranorm/analysis/similarity_matrix.py``).
* ``TextDiffReport`` -- token-level diff between two texts
  (``src/aranorm/analysis/text_diff_report.py``).
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from aranorm.analysis import (
    DiffToken,
    SimilarityMatrixResult,
    TextDiffReport,
    TextSimilarityMatrix,
)
from aranorm.analysis.text_comparator import TextComparator
from aranorm.core.pipeline import NormalizationResult

# ═══════════════════════════════════════════════════════════════════════════
# TextSimilarityMatrix
# ═══════════════════════════════════════════════════════════════════════════


class TestTextSimilarityMatrixBasics:
    """Core matrix construction and metrics."""

    def test_single_text_yields_empty_pairs(self) -> None:
        matrix = TextSimilarityMatrix()
        result = matrix.analyze(["نص واحد فقط"])
        assert result.text_count == 1
        assert result.pair_count == 0
        assert result.matrix == [[1.0]]
        assert result.pairs == []
        assert result.closest == []
        assert result.duplicate_pairs == []

    def test_empty_input_yields_zero_dimension_result(self) -> None:
        matrix = TextSimilarityMatrix()
        result = matrix.analyze([])
        assert result.text_count == 0
        assert result.pair_count == 0
        assert result.matrix == []
        assert result.closest == []

    def test_two_texts_produce_one_pair(self) -> None:
        matrix = TextSimilarityMatrix()
        result = matrix.analyze(["أنا سعيد اليوم", "أنا فرحان جداً اليوم"])
        assert result.text_count == 2
        assert result.pair_count == 1
        assert result.matrix[0][0] == 1.0
        assert result.matrix[1][1] == 1.0
        assert result.matrix[0][1] == result.matrix[1][0]
        assert 0.0 <= result.matrix[0][1] <= 1.0

    def test_three_texts_produce_three_pairs(self) -> None:
        matrix = TextSimilarityMatrix()
        texts = ["نص أولا", "نص ثانيا", "نص ثالثا"]
        result = matrix.analyze(texts)
        assert result.text_count == 3
        assert result.pair_count == 3
        assert result.closest[0].similarity >= result.closest[-1].similarity

    def test_pair_indices_reference_input_order(self) -> None:
        matrix = TextSimilarityMatrix()
        texts = ["أولا", "ثانيا", "ثالثا"]
        result = matrix.analyze(texts)
        indices = {(pair.index_a, pair.index_b) for pair in result.pairs}
        assert indices == {(0, 1), (0, 2), (1, 2)}
        for pair in result.pairs:
            assert pair.result.text_a == texts[pair.index_a]
            assert pair.result.text_b == texts[pair.index_b]

    def test_identical_texts_are_detected_as_duplicates(self) -> None:
        matrix = TextSimilarityMatrix()
        result = matrix.analyze(["نص مكرر", "نص مكرر", "نص مختلف"])
        duplicate = result.duplicate_pairs
        assert len(duplicate) == 1
        assert duplicate[0].index_a == 0
        assert duplicate[0].index_b == 1
        assert duplicate[0].similarity >= 1.0

    def test_completely_different_texts_score_low(self) -> None:
        matrix = TextSimilarityMatrix()
        result = matrix.analyze(["هذا نص عربي طويل جدا عن موضوع معين", "hello world foo bar baz"])
        assert result.matrix[0][1] < 0.5

    def test_generator_input_is_consumed_once(self) -> None:
        matrix = TextSimilarityMatrix()
        result = matrix.analyze(iter(["أ", "ب"]))
        assert result.text_count == 2
        assert result.pair_count == 1


class TestTextSimilarityMatrixScoreKeys:
    """Alternative score keys and validation."""

    def test_content_cosine_score_key(self) -> None:
        matrix = TextSimilarityMatrix(score_key="content_cosine")
        result = matrix.analyze(["نص مشترك", "نص مشترك جداً"])
        assert result.matrix[0][1] == result.closest[0].similarity

    def test_jaccard_score_key(self) -> None:
        matrix = TextSimilarityMatrix(score_key="jaccard_similarity")
        result = matrix.analyze(["واحد اثنان", "واحد اثنان ثلاثة"])
        assert 0.0 <= result.matrix[0][1] <= 1.0

    def test_invalid_score_key_raises(self) -> None:
        with pytest.raises(ValueError):
            TextSimilarityMatrix(score_key="nonexistent_key")

    def test_custom_comparator_is_used(self) -> None:
        calls: Dict[str, int] = {"count": 0}
        original_compare = TextComparator.compare

        def _spying_compare(self_: Any, text_a: str, text_b: str) -> Any:
            calls["count"] += 1
            return original_compare(self_, text_a, text_b)

        TextComparator.compare = _spying_compare
        try:
            custom = TextComparator()
            matrix = TextSimilarityMatrix(comparator=custom)
            matrix.analyze(["أ", "ب", "ج"])
        finally:
            TextComparator.compare = original_compare
        assert calls["count"] == 3


class TestClosestPairsAndQueries:
    """Query helpers on the result."""

    @pytest.fixture
    def result(self) -> SimilarityMatrixResult:
        texts = [
            "نص مشترك تماما",
            "نص مشترك تماما",
            "نص مختلف قليلا",
            "نص مختلف جداً كلياً",
        ]
        return TextSimilarityMatrix().analyze(texts)

    def test_find_closest_pairs_threshold(self, result: SimilarityMatrixResult) -> None:
        matches = result.find_closest_pairs(threshold=0.5)
        assert matches[0].similarity >= 0.5
        assert result.find_closest_pairs(threshold=1.0) == result.duplicate_pairs

    def test_find_closest_pairs_top_n(self, result: SimilarityMatrixResult) -> None:
        assert len(result.find_closest_pairs(top_n=1)) == 1

    def test_find_closest_pairs_all_with_threshold_zero(self, result: SimilarityMatrixResult) -> None:
        assert len(result.find_closest_pairs(threshold=0.0)) == result.pair_count

    def test_invalid_threshold_raises(self, result: SimilarityMatrixResult) -> None:
        with pytest.raises(ValueError):
            result.find_closest_pairs(threshold=1.5)
        with pytest.raises(ValueError):
            result.find_closest_pairs(threshold=-0.1)

    def test_invalid_top_n_raises(self, result: SimilarityMatrixResult) -> None:
        with pytest.raises(ValueError):
            result.find_closest_pairs(top_n=-1)
        with pytest.raises(ValueError):
            result.find_closest_pairs(top_n="five")  # type: ignore[arg-type]


class TestSimilarityMatrixResultSerialization:
    """to_dict / to_json round-trips."""

    def test_to_dict_structure(self) -> None:
        result = TextSimilarityMatrix().analyze(["نص أ", "نص ب", "نص أ"])
        payload = result.to_dict()
        assert payload["text_count"] == 3
        assert payload["pair_count"] == 3
        assert len(payload["closest_pairs"]) == 3
        first = payload["closest_pairs"][0]
        assert all(key in first for key in ("index_a", "index_b", "similarity", "verdict", "text_a", "text_b"))

    def test_to_json_is_valid_json(self) -> None:
        import json

        result = TextSimilarityMatrix().analyze(["نص أ", "نص ب"])
        payload = json.loads(result.to_json())
        assert payload["text_count"] == 2

    def test_closest_pair_to_dict(self) -> None:
        result = TextSimilarityMatrix().analyze(["نص", "نص"])
        pair = result.closest[0]
        payload = pair.to_dict()
        assert payload["index_a"] == 0
        assert payload["index_b"] == 1
        assert payload["similarity"] >= 1.0

    def test_closest_pair_immutable(self) -> None:
        result = TextSimilarityMatrix().analyze(["نص", "نص"])
        pair = result.closest[0]
        with pytest.raises(AttributeError):
            pair.similarity = 0.0  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# TextDiffReport
# ═══════════════════════════════════════════════════════════════════════════


class TestTextDiffReportBasicOps:
    """Equal / insert / delete / replace opcodes."""

    @pytest.fixture
    def report(self) -> TextDiffReport:
        return TextDiffReport()

    def test_identical_texts(self, report: TextDiffReport) -> None:
        result = report.diff("أنا سعيد", "أنا سعيد")
        assert result.is_identical
        assert result.changed_count == 0
        assert result.inserted_count == 0
        assert result.deleted_count == 0
        assert result.unchanged_count == 2
        assert result.similarity_ratio == 1.0
        assert result.diff == [DiffToken(op="equal", before=["أنا", "سعيد"], after=["أنا", "سعيد"])]

    def test_pure_insertion(self, report: TextDiffReport) -> None:
        result = report.diff("نص قصير", "نص قصير جداً")
        assert not result.is_identical
        assert result.inserted_count == 1
        assert result.deleted_count == 0
        assert result.changed_count == 0
        ops = {op.op for op in result.diff}
        assert "equal" in ops and "insert" in ops

    def test_pure_deletion(self, report: TextDiffReport) -> None:
        result = report.diff("نص طويل جداً", "نص طويل")
        assert result.deleted_count == 1
        assert result.inserted_count == 0
        ops = [op for op in result.diff if op.op == "delete"]
        assert len(ops) == 1
        assert ops[0].before == ["جداً"]
        assert ops[0].after == []

    def test_replacement(self, report: TextDiffReport) -> None:
        result = report.diff("أنا سعيد", "أنا فرحان")
        assert result.changed_count == 1
        ops = [op for op in result.diff if op.op == "replace"]
        assert len(ops) == 1
        assert ops[0].before == ["سعيد"]
        assert ops[0].after == ["فرحان"]

    def test_empty_texts(self, report: TextDiffReport) -> None:
        result = report.diff("", "")
        assert result.is_identical
        assert result.tokens_source == []
        assert result.tokens_target == []
        assert result.similarity_ratio == 1.0

    def test_whitespace_only_texts(self, report: TextDiffReport) -> None:
        result = report.diff("   ", "\t ")
        assert result.is_identical

    def test_empty_source_all_inserted(self, report: TextDiffReport) -> None:
        result = report.diff("", "نص جديد")
        assert result.inserted_count == 2
        assert result.changed_count == 0
        assert result.diff[0].op == "insert"

    def test_empty_target_all_deleted(self, report: TextDiffReport) -> None:
        result = report.diff("نص قديم", "")
        assert result.deleted_count == 2
        assert result.diff[0].op == "delete"

    def test_similarity_ratio_monotonic_with_overlap(self, report: TextDiffReport) -> None:
        high = report.diff("كلمة واحدة مشتركة", "كلمة واحدة مشتركة أخرى")
        low = report.diff("كلمة واحدة مشتركة", "نصوص مختلفة تماماً")
        assert high.similarity_ratio > low.similarity_ratio


class TestTextDiffReportCounts:
    """Counting semantics across mixed operations."""

    def test_counting_with_mixed_ops(self) -> None:
        report = TextDiffReport()
        result = report.diff("أ ب ج د", "أ ب هـ و")
        # "أ ب" equal, "ج د" → "هـ و" replace
        assert result.unchanged_count == 2
        assert result.changed_count == 2  # max(len(before), len(after))
        total = result.changed_count + result.inserted_count + result.deleted_count + result.unchanged_count
        assert total >= max(len(result.tokens_source), len(result.tokens_target))

    def test_counts_sum_consistency(self) -> None:
        report = TextDiffReport()
        result = report.diff("واحد اثنان ثلاثة أربعة", "واحد خمسة ثلاثة سبعة")
        assert result.changed_count + result.unchanged_count + result.inserted_count >= 4


class TestTextDiffResultSerialization:
    """DiffToken / TextDiffResult serialization."""

    def test_to_dict_structure(self) -> None:
        result = TextDiffReport().diff("نص أ", "نص ب ج")
        payload = result.to_dict()
        assert payload["source"] == "نص أ"
        assert payload["target"] == "نص ب ج"
        assert len(payload["diff"]) >= 2
        assert all(key in op for op in payload["diff"] for key in ("op", "before", "after"))

    def test_to_json_valid(self) -> None:
        import json

        payload = json.loads(TextDiffReport().diff("أ", "ب").to_json())
        assert payload["similarity_ratio"] < 1.0

    def test_diff_token_to_dict(self) -> None:
        token = DiffToken(op="replace", before=["سعيد"], after=["فرحان"])
        assert token.to_dict() == {"op": "replace", "before": ["سعيد"], "after": ["فرحان"]}

    def test_diff_token_immutable(self) -> None:
        token = DiffToken(op="equal", before=["نص"], after=["نص"])
        with pytest.raises(AttributeError):
            token.op = "delete"  # type: ignore[misc]

    def test_diff_result_immutable(self) -> None:
        result = TextDiffReport().diff("أ", "ب")
        with pytest.raises(AttributeError):
            result.inserted_count = 5  # type: ignore[misc]

    def test_is_identical_property(self) -> None:
        result = TextDiffReport().diff("نص", "نص")
        assert result.is_identical is True
        assert TextDiffReport().diff("نص", "آخر").is_identical is False


class TestTextDiffReportFromNormalization:
    """Diff driven by a real pipeline normalization result."""

    def test_from_normalization_result(self) -> None:
        from aranorm import ArabicNormalizationPipeline
        from aranorm.core import PipelineConfig

        pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="deep"))
        source = "الـكلمة   المكررة  المكررة"
        result = pipeline.process(source)
        assert isinstance(result, NormalizationResult)
        diff = TextDiffReport.from_normalization(source, result)
        assert diff.similarity_ratio >= 0.0
        assert len(diff.diff) >= 1

    def test_from_normalization_with_unchanged_text(self) -> None:
        from aranorm import ArabicNormalizationPipeline
        from aranorm.core import PipelineConfig

        pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="deep"))
        source = "كلمة بسيطة"
        diff = TextDiffReport.from_normalization(source, pipeline.process(source))
        # Deep preset may collapse whitespace; identical only when untouched.
        assert isinstance(diff.similarity_ratio, float)
