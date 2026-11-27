"""Property-based tests for the normalization pipeline (Round 6).

These assert invariants that must hold for *any* input, regardless of the
specific alphabet or content: idempotence, Latin preservation, and
bounded behaviour under adversarial whitespace.
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from aranorm import ArabicNormalizationPipeline

_arabic_codepoints = st.text(
    st.sampled_from("أإآاؤئءىةبتثجحخدذرزسشصضطظعغفقكهلمنوي"),
    min_size=0,
    max_size=12,
)

_whitespace_junk = st.text(
    st.sampled_from(" \t\n\r\u00a0\u2002\u2003\u3000"),
    min_size=0,
    max_size=6,
)


class TestNormalizationInvariants:
    @given(_arabic_codepoints)
    @settings(max_examples=200, deadline=None)
    def test_idempotence(self, text: str) -> None:
        pipeline = ArabicNormalizationPipeline()
        first = pipeline.process(text)
        second = pipeline.process(first.normalized_text)
        assert first.normalized_text == second.normalized_text

    @given(_arabic_codepoints, _whitespace_junk)
    @settings(max_examples=200, deadline=None)
    def test_whitespace_squeezed(self, text: str, junk: str) -> None:
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process(junk + text + junk)
        # Multiple whitespace characters must never survive normalization.
        assert re.search(r"\s{2,}", result.normalized_text) is None

    @given(st.text(st.sampled_from("abc123.,;:!?()-\"'"), min_size=0, max_size=20))
    @settings(max_examples=200, deadline=None)
    def test_latin_and_punctuation_preserved(self, text: str) -> None:
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process(text)
        # Pure Latin/punctuation text keeps the same characters in the same
        # order (typographic spacing is applied, so compare character sets).
        assert re.sub(r"\s", "", result.normalized_text) == re.sub(r"\s", "", text)

    @given(_arabic_codepoints, _whitespace_junk)
    @settings(max_examples=200, deadline=None)
    def test_dialect_robust_under_junk(self, text: str, junk: str) -> None:
        pipeline = ArabicNormalizationPipeline()
        clean = pipeline.process(text).dialect
        dirty = pipeline.process(junk + text + junk).dialect
        assert clean == dirty

    @given(st.just(""))
    @settings(max_examples=5)
    def test_empty_input_unchanged(self, text: str) -> None:
        pipeline = ArabicNormalizationPipeline()
        result = pipeline.process(text)
        assert result.normalized_text == ""
        assert result.dialect == "UNK"
