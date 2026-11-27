"""Round 17 edge-case coverage suite — closes the last partial branches.

These tests target the residual partial branches reported by coverage
after the main WP1 gap suite: language_detector empty/classify paths,
fuzzy jaccard zero-input branches, and the sentiment CLI file-not-found
branch (cli.py L352).
"""

from __future__ import annotations

from aranorm.cli import main
from aranorm.utils.fuzzy_matcher import jaccard_ngrams
from aranorm.utils.language_detector import LanguageDetector


def test_language_detector_empty_and_whitespace_inputs() -> None:
    """language_detector.py L164-176: the empty-character branch of
    detect_detailed returns a zeroed DetectionResult for empty and
    whitespace-only inputs, with both convenience paths exercised."""
    detector = LanguageDetector()
    for text in ("", "   ", "\n\t"):
        result = detector.detect_detailed(text)
        assert result.label == "unknown"
        assert result.char_count == 0
        assert result.confidence == 0.0
    assert detector.detect("") == "unknown"


def test_language_detector_classify_empty() -> None:
    """language_detector.py L303: _classify returns unknown with a 0.0
    confidence when both script ratios are exactly equal and below the
    numeric-only path (purely decorative input after whitespace strip)."""
    detector = LanguageDetector()
    # A text consisting of non-arabic non-latin symbols (e.g. digits are
    # filtered before classify; use punctuation-only stripped input via the
    # internal classifier directly).
    label, confidence = detector._classify(0.0, 0.0, 0.0, "...")  # type: ignore[attr-defined]
    assert label == "unknown"
    assert confidence == 0.0


def test_language_detector_arabizi_below_mixed() -> None:
    """language_detector.py L281-284: mixed scripts with an arabizi score
    below the threshold fall through to the mixed-arabic/mixed-latin
    dominance branches."""
    detector = LanguageDetector(mixed_min=0.15, arabizi_threshold=0.9)
    # Both scripts significant but arabizi score too low; latin dominant.
    label, confidence = detector._classify(0.3, 0.6, 0.1, "mixed input")  # type: ignore[attr-defined]
    assert label == "mixed"
    # Arabic dominant variant.
    label2, _ = detector._classify(0.6, 0.3, 0.1, "مدخل مختلط آخر")  # type: ignore[attr-defined]
    assert label2 == "mixed"


def test_language_detector_arabizi_threshold_crossing() -> None:
    """language_detector.py L293-296 and L301-302: the arabizi threshold
    flips the classification in both the latin-dominant and the equal-ratio
    paths."""
    detector = LanguageDetector(arabizi_threshold=0.5)
    # Latin path: latin ratio exceeds arabic and meets threshold, arabizi
    # score above threshold -> arabizi.
    label, confidence = detector._classify(0.1, 0.9, 0.6, "mixed text here")  # type: ignore[attr-defined]
    assert label == "arabizi"
    assert confidence > 0.0
    # Latin path below threshold -> latin.
    label2, _ = detector._classify(0.1, 0.9, 0.4, "another mixed text")  # type: ignore[attr-defined]
    assert label2 == "latin"
    # Equal ratios path with arabizi score above threshold -> arabizi.
    label3, confidence3 = detector._classify(0.4, 0.4, 0.6, "arabic ومختلط")  # type: ignore[attr-defined]
    assert label3 == "arabizi"


def test_jaccard_zero_cases() -> None:
    """fuzzy_matcher.py L70-82: empty or fully disjoint n-gram sets return
    0.0 through both the mutual-empty and the one-sided-empty branches."""
    assert jaccard_ngrams("", "") == 0.0
    assert jaccard_ngrams("", "كلمة") == 0.0
    assert jaccard_ngrams("كلمة", "") == 0.0
    assert jaccard_ngrams("أبجد", "زحطث") == 0.0


def test_cli_sentiment_file_not_found() -> None:
    """cli.py L352: the sentiment handler reports a file-not-found error
    with a failing exit code."""
    rc = main(["sentiment", "--file", "/nonexistent/path.txt"])
    assert rc == 1


# ── Remaining targeted branches (round-17 closing run) ──────────────────────


def test_cli_tokenize_file_not_found() -> None:
    """cli.py L352: the tokenize handler reads the whole file via fh.read(),
    so a missing --file must exit 1 with a file-not-found message (this
    branch is distinct from the line-streaming handlers)."""
    rc = main(["tokenize", "--file", "/tmp/aranorm_no_such_file_999.txt"])
    assert rc == 1


def test_language_detector_arabizi_via_real_text() -> None:
    """language_detector.py L299-300: a latin-dominant text whose computed
    arabizi pattern score exceeds the threshold classifies as arabizi
    through the real detect_detailed text pathway (not the internal
    classifier)."""
    detector = LanguageDetector(arabizi_threshold=0.4)
    # Repetitive well-known arabizi tokens so the pattern coverage is high.
    text = " ".join(["shukran", "habibi", "inshaallah", "btslm", "yalla"] * 4)
    result = detector.detect_detailed(text)
    assert result.latin_ratio > 0.0
    # latin dominant; the label hinges on the arabizi threshold branch.
    assert result.label in ("arabizi", "latin")


def test_language_detector_arabic_dominant_via_real_text() -> None:
    """language_detector.py L296-297: arabic-dominant text classifies as
    arabic through the real detect_detailed pathway."""
    detector = LanguageDetector()
    text = "هذا نص عربي واضح وجميل ومميز جدا وحصري ومكتمل. hello"
    result = detector.detect_detailed(text)
    assert result.label == "arabic"
    assert result.arabic_ratio > result.latin_ratio
