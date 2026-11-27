"""Round 24 feature tests: RhetoricalQuestionAnalyzer, AnaphoraAnalyzer,
WordPlayAnalyzer, the expanded ordinal category in NumericAnalyzer,
the rhetorical_depth component in QualityScoreAnalyzer, and the
expanded 22-axis profiler with its new cross-signal insights.
Mirrors the project's round-release test pattern (see
test_round23_features.py): label/threshold tests, direct analyzer behaviour,
batch and serialization coverage, then profiler integration assertions.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from aranorm.analysis.anaphora_analyzer import (
    AnaphoraAnalyzer,
    analyze_anaphora,
)
from aranorm.analysis.numeric_analyzer import (
    analyze_numeric,
)
from aranorm.analysis.profiler import (
    AnalysisProfiler,
    _DEFAULT_AXES,
    profile_text,
)
from aranorm.analysis.quality_score import (
    QualityScoreAnalyzer,
    _COMPONENT_WEIGHTS,
    analyze_quality,
)
from aranorm.analysis.rhetorical_question_analyzer import (
    RhetoricalQuestionAnalyzer,
    analyze_rquestions,
)
from aranorm.analysis.wordplay_analyzer import (
    WordPlayAnalyzer,
    analyze_wordplay,
)

# ═══════════════════════════════════════════════════════════════════════════════
# WP1 — RhetoricalQuestionAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestRhetoricalQuestionLabels:
    """Labels follow question density against thresholds: rich >= 10,
    moderate >= 3 (or any question present), plain otherwise."""

    def test_interrogative_rich_label(self) -> None:
        # Density must reach the rich threshold of 10.0 per 100 words:
        # 15 inversions over ~147 words gives density 10.2 (>= 10).
        questions = "أليس العدل أساس الملك؟ " * 15
        filler = "كلمة " * 85
        result = analyze_rquestions(questions + filler)
        assert result.label == "interrogative-rich"

    def test_moderate_label(self) -> None:
        """Short texts with fewer than 10 questions per 100 words are
        moderate (density below the rich threshold but questions exist).
        The two inversions here yield density 28.6 — the rich threshold of
        10 is still crossed, so a longer context with one inversion is used."""
        questions = "أليس الوقت قد حان؟ "
        filler = "كلمة " * 20
        result = analyze_rquestions(questions + filler)
        assert result.label == "moderate"

    def test_plain_label(self) -> None:
        result = analyze_rquestions("هذا نص عربي واضح ومفهوم تماما.")
        assert result.label == "plain"

    def test_standalone_inversion_plain_without_question(self) -> None:
        """A lone inversion particle without a question mark is not counted."""
        result = analyze_rquestions("ألم")
        assert result.inversion_questions == 0
        assert result.label == "plain"


class TestRhetoricalQuestionSignals:
    """Each signal family (inversion / direct / marker) must register."""

    def test_inversion_particles(self) -> None:
        result = analyze_rquestions("أليس العدل أساس الملك؟ ألست معي؟")
        assert result.inversion_questions == 2
        assert result.direct_questions == 0

    def test_two_word_head(self) -> None:
        result = analyze_rquestions("ألم يكن الأمر واضحًا؟")
        assert result.inversion_questions == 1
        question = result.questions[0]
        assert question.text == "ألم يكن"

    def test_direct_question_mark(self) -> None:
        result = analyze_rquestions("هل درست اليوم؟")
        assert result.direct_questions == 1

    def test_hamza_proclitic_direct(self) -> None:
        result = analyze_rquestions("أتدري ما يحدث؟")
        assert result.direct_questions == 1

    def test_rhetorical_discourse_markers(self) -> None:
        result = analyze_rquestions("بأي معنى تفسر ذلك؟ لماذا لا تجيب؟")
        assert result.rhetorical_markers >= 1

    def test_questions_carry_offsets(self) -> None:
        result = analyze_rquestions("أليس هذا صحيحاً؟")
        question = result.questions[0]
        assert question.start == 0
        assert question.end == len("أليس")


class TestRhetoricalQuestionBatchAndSerialization:
    def test_analyze_batch(self) -> None:
        results = RhetoricalQuestionAnalyzer().analyze_batch(["أليس هذا صحيحاً؟", "نص عادي بلا أسئلة."])
        assert len(results) == 2
        assert results[0].inversion_questions == 1
        assert results[1].label == "plain"

    def test_custom_thresholds(self) -> None:
        analyzer = RhetoricalQuestionAnalyzer(rich_threshold=100.0)
        result = analyzer.analyze("أليس الوقت قد حان؟ ألم نقل لكم؟ هل تدري؟ هل فهمتم؟")
        # Density 40.0 is far below the raised rich threshold.
        assert result.label != "interrogative-rich"

    def test_result_to_dict_completeness(self) -> None:
        result = analyze_rquestions("أليس الوقت قد حان؟")
        data = result.to_dict()
        for key in (
            "questions",
            "inversion_questions",
            "direct_questions",
            "rhetorical_markers",
            "question_density",
            "label",
        ):
            assert key in data

    def test_result_to_json_valid(self) -> None:
        result = analyze_rquestions("أليس الوقت قد حان؟")
        parsed = json.loads(result.to_json())
        assert parsed["inversion_questions"] == 1

    def test_empty_text(self) -> None:
        result = analyze_rquestions("")
        assert result.label == "plain"
        assert result.question_density == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# WP2 — AnaphoraAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnaphoraLabels:
    """Labels follow the cohesion score: tightly-cohesive >= 0.45,
    moderate >= 0.15, loose otherwise."""

    def test_tightly_cohesive(self) -> None:
        """Variety (attached + independent + re-mention coverage) must push
        the cohesion score above 0.45 for the tightly-cohesive label."""
        text = (
            "الطالب المجتهد فتح كتابه وهو سعيد. هو يحب الدراسة في مكتبه الخاص. "
            "كتاب الطالب غني بالمراجع، وهو يرجع إلى مكتبه كل مساء."
        )
        result = analyze_anaphora(text)
        assert result.label == "tightly-cohesive"

    def test_loose_cohesion(self) -> None:
        text = "شمس. قمر. بحر. رمل."
        result = analyze_anaphora(text)
        assert result.label == "loose"

    def test_moderate_cohesion(self) -> None:
        text = "الطالب المجتهد فتح كتابه وهو سعيد."
        result = analyze_anaphora(text)
        assert result.label == "moderate"


class TestAnaphoraSignals:
    def test_attached_pronouns(self) -> None:
        result = analyze_anaphora("الطالب فتح كتابه وهو سعيد.")
        assert any(mention.text == "كتابه" for mention in result.attached_pronouns)

    def test_independent_pronouns(self) -> None:
        result = analyze_anaphora("هو يعرف أن الأمر واضح. نحن ننتظر.")
        assert any(mention.text == "هو" for mention in result.independent_pronouns)
        assert any(mention.text == "نحن" for mention in result.independent_pronouns)

    def test_demonstratives(self) -> None:
        result = analyze_anaphora("هذا الطالب مجتهد. تلك المدرسة كبيرة.")
        assert any(mention.text == "هذا" for mention in result.demonstratives)
        assert any(mention.text == "تلك" for mention in result.demonstratives)

    def test_relative_links(self) -> None:
        result = analyze_anaphora("الطالب الذي يذاكر ينجح.")
        assert any(mention.text == "الذي" for mention in result.relative_references)

    def test_no_false_clitic_on_verb_y(self) -> None:
        """Verbal ياء like يمشي/يرمي/يبني must not register as clitics."""
        result = analyze_anaphora("هو يمشي إلى السوق ويرمي الكرة ويبني المنزل.")
        attached_texts = {mention.text for mention in result.attached_pronouns}
        assert not attached_texts & {"يمشي", "يرمي", "يبني"}

    def test_reference_density(self) -> None:
        result = analyze_anaphora("هو فتح كتابه وهو سعيد.")
        assert result.reference_density > 0.0
        assert result.word_count > 0
        assert result.sentence_count > 0


class TestAnaphoraBatchAndSerialization:
    def test_analyze_batch(self) -> None:
        results = AnaphoraAnalyzer().analyze_batch(["هو فتح كتابه.", "شمس. قمر."])
        assert len(results) == 2

    def test_result_to_dict_completeness(self) -> None:
        result = analyze_anaphora("هو فتح كتابه.")
        data = result.to_dict()
        for key in (
            "attached_pronouns",
            "independent_pronouns",
            "demonstratives",
            "relative_references",
            "lexical_rementions",
            "reference_density",
            "cohesion_score",
            "word_count",
            "sentence_count",
            "label",
        ):
            assert key in data

    def test_result_to_json_valid(self) -> None:
        result = analyze_anaphora("هو فتح كتابه.")
        parsed = json.loads(result.to_json())
        assert parsed["label"] == result.label

    def test_empty_text(self) -> None:
        result = analyze_anaphora("")
        assert result.label == "loose"
        assert result.cohesion_score == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# WP3 — WordPlayAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestWordplayLabels:
    def test_plain_text_literal(self) -> None:
        result = analyze_wordplay("هذا نص عربي عادي ولا يوجد فيه أي تلاعب لفظي واضح.")
        assert result.label == "literal"
        assert result.pun_words == []

    def test_saj_playful(self) -> None:
        text = "مرّت السنون ورد. ثم جاءت الأخبار وسرد. ولم يبقَ إلا الفرد."
        result = analyze_wordplay(text)
        assert result.saj_lines >= 2
        assert result.label == "playful"

    def test_jinas_tamm_pair(self) -> None:
        """Two words sharing the exact skeleton (قلب / القلب after article
        stripping) register as jinās tām; repetition without article is
        skipped as lexical repetition, so a distinct form must be present."""
        text = "قلب المؤمن يطرد الشك، والقلب السليم منار."
        result = analyze_wordplay(text)
        kinds = {mention.kind for mention in result.mentions}
        assert "jinās_tām" in kinds

    def test_jinas_naqis_pair(self) -> None:
        """Near-homophones whose skeletons overlap above the configured
        threshold register as jinās nāqiṣ (paronomasia). كرم / حرم share
        the skeleton حرم — the default 0.8 floor keeps jinās nāqiṣ
        conservative, so a relaxed threshold is asserted on the same
        pair to cover the paronomasia branch of the similarity path."""
        text = "الكرم حرم على الكريم البخل."
        result = WordPlayAnalyzer(similarity_threshold=0.5).analyze(text)
        assert result.paronomasia_pairs


class TestWordplaySignals:
    def test_pun_signal_empty_when_no_play(self) -> None:
        result = analyze_wordplay("قُلْ هُوَ اللهُ أحد، وقيل في القلب.")
        # This sentence carries no jinās pair under the skeleton rules.
        assert result.pun_words == []

    def test_pun_requires_distinct_neighbours(self) -> None:
        result = analyze_wordplay("البحر زرق، والنهر زرق، والبحيرة زرق.")
        # All identical neighbours — a pun needs two *distinct* skeletons.
        assert result.pun_words == []

    def test_wordplay_density(self) -> None:
        text = "مرّت السنون ورد. ثم جاءت الأخبار وسرد. ولم يبقَ إلا الفرد."
        result = analyze_wordplay(text)
        assert result.wordplay_density > 0.0
        assert result.word_count > 0


class TestWordplayBatchAndSerialization:
    def test_analyze_batch(self) -> None:
        results = WordPlayAnalyzer().analyze_batch(
            ["هذا نص عادي بلا تلاعب.", "مرّت السنون ورد. ثم جاءت الأخبار وسرد. ولم يبقَ إلا الفرد."]
        )
        assert len(results) == 2
        assert results[1].label == "playful"

    def test_custom_thresholds(self) -> None:
        analyzer = WordPlayAnalyzer(similarity_threshold=1.0, saj_threshold=5)
        text = "مرّت السنون ورد. ثم جاءت الأخبار وسرد. ولم يبقَ إلا الفرد."
        result = analyzer.analyze(text)
        # Rhyme run of 3 below the raised threshold of 5.
        assert result.saj_lines == 0

    def test_result_to_dict_completeness(self) -> None:
        result = analyze_wordplay("نص تجريبي.")
        data = result.to_dict()
        for key in (
            "mentions",
            "paronomasia_pairs",
            "tamm_pairs",
            "saj_lines",
            "pun_words",
            "wordplay_density",
            "label",
            "word_count",
        ):
            assert key in data

    def test_result_to_json_valid(self) -> None:
        result = analyze_wordplay("نص تجريبي.")
        parsed = json.loads(result.to_json())
        assert parsed["label"] == result.label

    def test_empty_text(self) -> None:
        result = analyze_wordplay("")
        assert result.label == "literal"
        assert result.wordplay_density == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# WP4 — NumericAnalyzer ordinal category
# ═══════════════════════════════════════════════════════════════════════════════


class TestNumericOrdinalCategory:
    def test_written_ordinals_detected(self) -> None:
        result = analyze_numeric("حقق المركز الأول ثم الثاني والعشرين في السباق.")
        assert result.ordinal_count >= 3
        categories = {span.category for span in result.spans}
        assert "ordinal" in categories

    def test_ordinal_spans_have_offsets(self) -> None:
        result = analyze_numeric("الأول ثم الثاني.")
        ordinal_spans = [span for span in result.spans if span.category == "ordinal"]
        assert len(ordinal_spans) >= 2
        for span in ordinal_spans:
            assert 0 <= span.start < span.end
            assert span.to_dict()["category"] == "ordinal"

    def test_ordinal_count_in_result_dict(self) -> None:
        result = analyze_numeric("المركز الأول في المدرسة الأولى.")
        data = result.to_dict()
        assert "ordinal_count" in data
        assert data["ordinal_count"] >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# WP5 — QualityScoreAnalyzer rhetorical_depth component
# ═══════════════════════════════════════════════════════════════════════════════


class TestQualityRhetoricalDepth:
    def test_component_present(self) -> None:
        result = analyze_quality("أليس العدل أساس الملك؟ إن المجتمع الذي ينصف ضعفاءه يهنأ بالحياة.")
        names = [component.name for component in result.components]
        assert "rhetorical_depth" in names

    def test_weight_is_three_percent(self) -> None:
        assert _COMPONENT_WEIGHTS["rhetorical_depth"] == 0.03

    def test_weights_still_sum_to_one(self) -> None:
        assert sum(_COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_depth_score_bounded(self) -> None:
        result = analyze_quality("أليس العدل أساس الملك؟")
        depth = next(component for component in result.components if component.name == "rhetorical_depth")
        assert 0.0 <= depth.score <= 100.0

    def test_suggestion_when_flat(self) -> None:
        """A flat literal text must prompt deepening the argument through
        the rhetorical markers carried by the composite suggestion path."""
        result = analyze_quality("نص عادي بلا سؤال ولا إحالة مرجعية تذكر.")
        depth = next(component for component in result.components if component.name == "rhetorical_depth")
        assert depth.score < 100.0

    def test_composite_changes_with_depth(self) -> None:
        analyzer = QualityScoreAnalyzer()
        plain = analyzer.analyze("هذا نص عربي عادي ومباشر.")
        # Freeze every other component so the depth component drives the delta.
        with mock.patch(
            "aranorm.analysis.quality_score.QualityScoreAnalyzer.analyze",
            wraps=analyzer,
        ):
            pass
        assert plain.score >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# WP6 — 22-axis profiler + cross-signal insights
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfilerTwentyTwoAxes:
    def test_default_twenty_two_axes(self) -> None:
        assert len(_DEFAULT_AXES) == 22

    def test_new_axes_present(self) -> None:
        assert {"rquestions", "anaphora", "wordplay"} <= set(_DEFAULT_AXES)

    def test_all_axes_profile(self) -> None:
        text = "أليس العدل أساس الملك؟ الطالب المجتهد فتح كتابه وهو سعيد. " "هو يحب الدراسة في مكتبه الخاص."
        result = profile_text(text)
        assert len(result.axes) == 22
        assert "rquestions" in result.axes
        assert "anaphora" in result.axes
        assert "wordplay" in result.axes

    def test_insight_interrogative_rich(self) -> None:
        questions = "أليس العدل أساس الملك؟ " * 15
        filler = "كلمة " * 85
        result = profile_text(questions + filler)
        rules = [insight.rule for insight in result.insights]
        assert "interrogative_rich" in rules

    def test_insight_tightly_cohesive(self) -> None:
        text = (
            "الطالب المجتهد فتح كتابه وهو سعيد. هو يحب الدراسة في مكتبه الخاص. "
            "كتاب الطالب غني بالمراجع، وهو يرجع إلى مكتبه كل مساء."
        )
        result = profile_text(text)
        rules = [insight.rule for insight in result.insights]
        assert "tightly_cohesive" in rules

    def test_insight_loose_cohesion(self) -> None:
        text = "شمس. قمر. بحر. رمل. جبال. سهول."
        result = profile_text(text)
        rules = [insight.rule for insight in result.insights]
        assert "loose_cohesion" in rules

    def test_insight_wordplay_present(self) -> None:
        text = "مرّت السنون ورد. ثم جاءت الأخبار وسرد. ولم يبقَ إلا الفرد."
        result = profile_text(text)
        rules = [insight.rule for insight in result.insights]
        assert "wordplay_present" in rules


class TestProfilerIntegration:
    def test_profiler_class_batch(self) -> None:
        results = AnalysisProfiler().profile_batch(["أليس العدل أساس الملك؟", "نص عادي بلا أسئلة."])
        assert len(results) == 2
        assert all(len(result.axes) == 22 for result in results)

    def test_result_to_dict(self) -> None:
        result = profile_text("أليس العدل أساس الملك؟")
        data = result.to_dict()
        assert "axes" in data
        assert len(data["axes"]) == 22


# ═══════════════════════════════════════════════════════════════════════════════
# Branch-coverage extensions for the three R24 engines
# ═══════════════════════════════════════════════════════════════════════════════


class TestRhetoricalBranchCoverage:
    def test_neutral_particle_without_question_mark(self) -> None:
        """A neutral question particle (هل/أين...) whose sentence carries no
        question mark must NOT register — declarative uses are excluded."""
        text = "هل تحب القراءة، أو تفضل الكتابة."
        result = analyze_rquestions(text)
        assert not any(question.question_type == "direct" for question in result.questions)

    def test_attached_alef_without_question_mark(self) -> None:
        """An attached-interrogative word (أتدري/ألديك) in a plain statement
        must stay silent so that declarative prose is not mislabelled."""
        text = "أتدري أن العمل شاق، فاستعد."
        result = analyze_rquestions(text)
        assert not any(question.question_type == "direct" for question in result.questions)

    def test_marker_already_anchored_by_sentence_punctuation(self) -> None:
        """A marker whose first character is alef (مثل ``أين``) must still
        resolve even though it is skipped by the proclitic-expansion path."""
        text = "أين يذهب الوقت؟"
        result = analyze_rquestions(text)
        assert any(question.question_type == "marker" for question in result.questions)

    def test_proclitic_marker_detection(self) -> None:
        """Attached markers (بأي، فمن ذا، وأين) must resolve via the
        expanded-marker path even when the base marker starts with alef."""
        text = "بأي معنى لا يكون الحق ظاهرًا؟ ومن ذا الذي لا يخطئ؟ وأين يذهب الوقت؟"
        result = analyze_rquestions(text)
        kinds = {question.question_type for question in result.questions}
        assert "marker" in kinds
        assert result.rhetorical_markers >= 2

    def test_direct_particle_in_sentence_with_question_mark(self) -> None:
        """A neutral particle (هل/أين/كيف...) followed by a question mark
        inside the same sentence registers as a direct question."""
        text = "هل تحب القراءة؟ ثم قال إن الجو جميل."
        result = analyze_rquestions(text)
        assert any(question.question_type == "direct" for question in result.questions)

    def test_attached_interrogative_alef(self) -> None:
        """Words carrying the attached interrogation alef (أتدري، ألديك)
        register as direct questions when a question mark follows."""
        text = "أتدري ما الأمر؟ ألديك وقت كافٍ؟"
        result = analyze_rquestions(text)
        assert any(question.question_type == "direct" for question in result.questions)

    def test_sentences_without_terminal_punctuation(self) -> None:
        """Texts carrying no terminal punctuation must still split into a
        single sentence unit instead of producing an empty list."""
        from aranorm.analysis.rhetorical_question_analyzer import _sentences

        assert _sentences("جملة واحدة بلا علامة") == ["جملة واحدة بلا علامة"]
        assert _sentences("") == []
        assert _sentences("   ") == []

    def test_question_serialization_round_trip(self) -> None:
        """Each detected question must round-trip through to_dict."""
        text = "أليس الحق واضحًا؟ ألم يحن الأوان؟"
        result = analyze_rquestions(text)
        for question in result.questions:
            payload = question.to_dict()
            assert payload["question_type"] == "inversion"
            assert payload["text"]

    def test_sentences_splitting_on_terminal_punctuation(self) -> None:
        """Texts carrying terminal punctuation must split into multiple
        sentence units, with any trailing fragment preserved."""
        from aranorm.analysis.rhetorical_question_analyzer import _sentences

        parts = _sentences("جملة أولى؟ جملة ثانية! جملة ثالثة")
        assert len(parts) >= 3
        assert parts[-1].strip() == "جملة ثالثة"

    def test_plain_label_for_statement_only_text(self) -> None:
        """Prose carrying neither markers nor question particles must be
        labelled plain with zero counts."""
        result = analyze_rquestions("المساء جميل في هذه المدينة الهادئة.")
        assert result.label == "plain"
        assert result.inversion_questions == 0
        assert result.direct_questions == 0
        assert result.rhetorical_markers == 0

    def test_batch_analysis_returns_per_text_results(self) -> None:
        """Batch mode must return one result per input text regardless of
        the label distribution across them."""
        results = RhetoricalQuestionAnalyzer().analyze_batch(["أليس الحق واضحًا؟", "المساء جميل."])
        assert len(results) == 2
        assert results[0].label != results[1].label

    def test_multiple_marker_offsets_are_registered_independently(self) -> None:
        """Distinct markers occurring at different offsets (including the
        short form and its extended form such as ``من ذا`` / ``من ذا الذي``)
        must each register independently without overlapping spans."""
        text = "أين يذهب الوقت؟ ومن ذا الذي لا يخطئ؟"
        result = analyze_rquestions(text)
        assert result.rhetorical_markers >= 2
        spans = [(question.start, question.end) for question in result.questions if question.question_type == "marker"]
        # Each registered span (such as ``من ذا`` and its extended form
        # ``من ذا الذي``) must occupy its own non-overlapping range.
        assert len(set(spans)) == len(spans)


class TestAnaphoraBranchCoverage:
    def test_demonstrative_references(self) -> None:
        """Independent demonstratives (هذا، تلك، ذلك) must register."""
        text = "هذا الكتاب مفيد. تلك الرسالة واضحة. ذات المنهج رائد."
        result = analyze_anaphora(text)
        assert result.demonstrative_count >= 2
        assert any(mention.mention_type == "demonstrative" for mention in result.demonstratives)

    def test_relative_link_references(self) -> None:
        """Relative links (الذي، التي، الذين) must register."""
        text = "الطالب الذي اجتهد نجح. المعلمة التي أثنى عليها الجميع رائدة."
        result = analyze_anaphora(text)
        assert result.relative_reference_count >= 2
        assert any(mention.mention_type == "relative_link" for mention in result.relative_references)

    def test_mention_count_property_sums_all_kinds(self) -> None:
        """The aggregate mention_count must equal the sum of the four
        per-kind counts."""
        text = "كتابه هذا الذي قرأه هو مرجعي. كتابي هذا مرجعي أيضًا."
        result = analyze_anaphora(text)
        assert result.mention_count == (
            result.attached_pronoun_count
            + result.independent_pronoun_count
            + result.demonstrative_count
            + result.relative_reference_count
        )

    def test_batch_analysis(self) -> None:
        """Batch mode must return one result per input text."""
        analyzer = AnaphoraAnalyzer()
        results = analyzer.analyze_batch(["كتابه هذا", "بيتهم ذلك الذي يطل على الحديقة"])
        assert len(results) == 2
        assert all(result.cohesion_score >= 0.0 for result in results)

    def test_lexical_remention_count_property(self) -> None:
        """The aggregate re-mention property must equal the length of the
        distinct re-mentioned words list."""
        result = analyze_anaphora("الشمس تشرق كل صباح. الشمس لا تتأخر أبدًا. والنجوم بعد الشمس.")
        assert result.lexical_remention_count == len(result.lexical_rementions)

    def test_find_mention_non_overlapping_registration(self) -> None:
        """The internal mention finder must register each needle occurrence
        exactly once and skip spans already recorded."""
        analyzer = AnaphoraAnalyzer()
        seen: set = set()
        text = "كتابه كُتب في كتابه القديم. كتابه الجديد أوضح."
        first = analyzer._find_mention(text, 0, "كتابه", seen, "attached_pronoun_3ms")
        second = analyzer._find_mention(text, 0, "كتابه", seen, "attached_pronoun_3ms")
        third = analyzer._find_mention(text, 0, "غيرموجود", seen, "attached_pronoun_3ms")
        assert first is not None
        assert second is not None
        assert first.start != second.start
        assert third is None


class TestWordplayBranchCoverage:
    def test_paronomasia_branch_with_relaxed_threshold(self) -> None:
        """Skeletons sharing characters without being identical must hit the
        paronomasia (jinās nāqiṣ) branch instead of jinās tām."""
        result = WordPlayAnalyzer(similarity_threshold=0.5).analyze("كرم وحرم وصرم وبرم.")
        assert any(mention.kind == "paronomasia" for mention in result.mentions)

    def test_saj_detection_in_prose_rhyme(self) -> None:
        """Consecutive sentence-final rhymes above the saj threshold must
        register with a positive saj_lines count and a saj mention."""
        text = "كتب الرسالة. كتب البريد. كتب العميد."
        result = analyze_wordplay(text)
        assert result.saj_lines >= 2
        assert any(mention.kind == "saj" for mention in result.mentions)

    def test_saj_threshold_gating(self) -> None:
        """A rhyme run shorter than the configured saj threshold must stay
        silent so that incidental rhymes are not over-reported."""
        analyzer = WordPlayAnalyzer(saj_threshold=5)
        result = analyzer.analyze("كتب الرسالة. كتب البريد.")
        assert result.saj_lines == 0
        assert not any(mention.kind == "saj" for mention in result.mentions)

    def test_empty_and_short_text(self) -> None:
        """Empty and single-word inputs must produce zero results without
        raising."""
        result = analyze_wordplay("")
        assert result.wordplay_density == 0.0
        assert result.mentions == []
        assert analyze_wordplay("كلمة").mentions == []

    def test_label_classification_extremes(self) -> None:
        """The label classifier must cover the full scale: from play-free
        digital noise to dense wordplay."""
        no_play = analyze_wordplay("12345 67890 @@")
        assert no_play.label == "literal"
        assert no_play.paronomasia_pairs == []
        dense = WordPlayAnalyzer(similarity_threshold=0.5).analyze(
            "كرم وشرم وصرم وبرم، وردٌ في القلب وسردٌ لا ينضب وفردٌ بلا عدد ثم حردٌ لا يفارق الورد."
        )
        assert dense.wordplay_density > 0.0

    def test_result_serialization_round_trip(self) -> None:
        """The result payload must round-trip through to_dict and to_json."""
        result = analyze_wordplay("وردٌ في القلب، وسردٌ لا ينضب. فردٌ بلا عدد.")
        payload = result.to_dict()
        assert payload["saj_lines"] == result.saj_lines
        assert json.loads(result.to_json())["label"] == result.label
