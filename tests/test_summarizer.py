"""Defensive tests for extractive Arabic summarization."""

import pytest

from aranorm.analysis.summarizer import ArabicTextSummarizer, SummaryResult


def test_summarizer_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="ratio"):
        ArabicTextSummarizer(ratio=0)
    with pytest.raises(ValueError, match="ratio"):
        ArabicTextSummarizer(ratio=1.1)
    with pytest.raises(ValueError, match="max_sentences"):
        ArabicTextSummarizer(max_sentences=0)


def test_empty_input_returns_stable_empty_result() -> None:
    result = ArabicTextSummarizer().summarize("   ")

    assert result.original_text == "   "
    assert result.summary_text == ""
    assert result.summary_sentences == []
    assert result.original_sentence_count == 0
    assert result.compression_ratio == 0.0


def test_no_content_words_keeps_first_requested_sentences() -> None:
    result = ArabicTextSummarizer(max_sentences=2).summarize("هو في البيت. من في الطريق؟ ثم في العمل!")

    assert result.original_sentence_count == 3
    assert result.summary_sentence_count == 2
    assert result.summary_sentences == ["هو في البيت.", "من في الطريق؟"]
    assert result.summary_text.endswith("الطريق؟")


def test_max_sentences_preserves_source_order_and_keywords() -> None:
    text = (
        "تعلن الجامعة إطلاق برنامج بحثي جديد. "
        "يركز البرنامج على الذكاء الاصطناعي وتحليل البيانات. "
        "يشارك الباحثون في مختبرات متخصصة لدراسة النتائج. "
        "تبدأ المرحلة الأولى خلال شهر سبتمبر."
    )
    result = ArabicTextSummarizer(max_sentences=2).summarize(text)

    assert result.summary_sentence_count == 2
    positions = [text.index(sentence) for sentence in result.summary_sentences]
    assert positions == sorted(positions)
    assert result.top_keywords
    assert all(0.0 <= score <= 1.0 for score in result.sentence_scores.values())
    assert 0.0 < result.compression_ratio <= 1.0


def test_summary_result_round_trip_is_complete_and_defensive() -> None:
    result = ArabicTextSummarizer(max_sentences=1).summarize(
        "هذا نص تجريبي عن البحث العلمي. هذه جملة ثانية عن النتائج المهمة."
    )
    payload = result.to_dict()
    restored = SummaryResult.from_dict(payload)
    payload["summary_sentences"].append("تغيير خارجي")
    payload["sentence_scores"]["خارجي"] = 1.0

    assert restored.to_dict() == result.to_dict()
    assert "original_text" in payload
    assert "sentence_scores" in payload


def test_summarize_batch_handles_mixed_inputs() -> None:
    summarizer = ArabicTextSummarizer(max_sentences=1)
    results = summarizer.summarize_batch(["النص الأول واضح.", "", "النص الثالث."])

    assert len(results) == 3
    assert results[0].summary_sentence_count == 1
    assert results[1].summary_text == ""
    assert results[2].summary_sentence_count == 1
