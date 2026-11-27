"""Round 21 feature-suite tests: rhythm, figurate, numeric, dialect-depth,
12-axis profiler and the rhetorical-richness quality component.

Mirrors the project's round-release test pattern (see test_round20_features.py):
label/threshold tests, direct analyzer behaviour, batch and serialization
coverage, then profiler/quality integration assertions.
"""

import json
from unittest import mock

from aranorm.analysis.figurate_analyzer import (
    FigurateAnalyzer,
    analyze_figurative,
)
from aranorm.analysis.numeric_analyzer import (
    NumericAnalyzer,
    analyze_numeric,
)
from aranorm.analysis.profiler import (
    AnalysisProfiler,
    _DEFAULT_AXES,
    profile_text,
)
from aranorm.analysis.quality_score import analyze_quality
from aranorm.analysis.rhythm_analyzer import (
    RhythmAnalyzer,
    analyze_rhythm,
)
from aranorm.utils.dialect_depth import (
    DialectAnalyzer,
    _REGION_MARKERS,
    _REGION_THRESHOLD,
    analyze_dialect,
)

# ═══════════════════════════════════════════════════════════════════════════════
# WP1 — RhythmAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestRhythmLabels:
    """Labels follow rhythmic>=0.35, semi_rhythmic>=0.18, else flat."""

    def test_rhythmic_label(self) -> None:
        result = analyze_rhythm("يعملون، ويكملون")
        assert result.label == "rhythmic"

    def test_flat_label(self) -> None:
        result = analyze_rhythm("هذا نص عربي عادي تماماً بلا أي تقسيم أو ترنيم")
        assert result.label == "flat"


class TestRhythmSaj:
    def test_saj_pair_detection(self) -> None:
        result = analyze_rhythm("يعملون، ويكملون")
        assert result.saj_signals >= 1
        assert len(result.saj_pairs) == 1
        assert result.saj_pairs[0].shared_stem == "مل"

    def test_saj_prefix_normalization(self) -> None:
        """Conjunctive و on the second clause must not break saj detection."""
        result = analyze_rhythm("يلحنون، ويلحنون")
        assert any(pair.shared_stem == "يلحن" for pair in result.saj_pairs)

    def test_saj_suffix_normalization(self) -> None:
        """Clitic suffixes (ون/ين/ات/ا) must peel off to expose the stem."""
        result = analyze_rhythm("يلحنون، يمتحنون")
        assert len(result.saj_pairs) >= 1

    def test_saj_i_suffix(self) -> None:
        """The ي ta' marbuta-free suffix exposes a matching stem."""
        from aranorm.analysis.rhythm_analyzer import _strip_trailing_suffixes

        assert _strip_trailing_suffixes("كلماتِي") == "كلمات"

    def test_balanced_all_empty_sentences(self) -> None:
        """All-zero sentence lengths must not break the balance coefficient."""
        from aranorm.analysis.rhythm_analyzer import _parallel_balance_coefficient

        assert _parallel_balance_coefficient(["،", "،،"]) == 0.0

    def test_quality_poor_label_and_diagnostic_suggestion(self) -> None:
        """The composite must clamp to the poor band when components collapse."""
        from aranorm.analysis.quality_score import _label_for

        assert _label_for(30.0) == "poor"

        from aranorm.analysis.quality_score import QualityScoreAnalyzer

        analyzer = QualityScoreAnalyzer()
        # A short non-Arabic-heavy fragment forces several components below 75.
        result = analyzer.analyze("!!!")
        assert result.issues

    def test_quality_mid_diacritics_band(self) -> None:
        """Partial vowelling (density between 0.05 and 0.15) scores 75."""
        from aranorm.analysis.quality_score import _score_diacritics

        # 1 diacritic over 10 letters = 0.10 density -> 75.0 band
        text = "الْكتا" + "ب" * 3
        assert _score_diacritics(text, []) == 75.0

    def test_quality_clean_text_outperforms_degraded_text(self) -> None:
        """A clean MSA sentence must score strictly higher than a degraded one."""
        from aranorm.analysis.quality_score import QualityScoreAnalyzer

        analyzer = QualityScoreAnalyzer()
        clean = analyzer.analyze("نصٌّ عربيٌّ واضحٌ ومفهومٌ تماماً.")
        degraded = analyzer.analyze("مسئول الاعلان")
        assert clean.score > degraded.score
        assert len(clean.components) == 8
        assert all(0.0 <= component.score <= 100.0 for component in clean.components)
        assert all(component.weight > 0.0 for component in clean.components)

    def test_quality_no_issue_note_when_components_healthy(self) -> None:
        """When every component stays above 75, no diagnostic issue is raised."""
        from aranorm.analysis import quality_score

        # Freeze every component scorer above the 75 floor so the
        # "components below 75" note can be exercised in isolation.
        with (
            mock.patch.object(quality_score, "_score_spelling", return_value=90.0),
            mock.patch.object(quality_score, "_score_consistency", return_value=90.0),
            mock.patch.object(quality_score, "_score_lexical_balance", return_value=90.0),
            mock.patch.object(quality_score, "_score_readability", return_value=90.0),
            mock.patch.object(quality_score, "_score_diacritics", return_value=90.0),
            mock.patch.object(quality_score, "_score_rhetorical_richness", return_value=90.0),
            mock.patch.object(quality_score, "_score_structural_balance", return_value=90.0),
            mock.patch.object(quality_score, "_score_rhetorical_depth", return_value=90.0),
        ):
            result = quality_score.QualityScoreAnalyzer().analyze("نصٌّ عربيٌّ واضحٌ ومفهومٌ تماماً.")
        assert not result.issues
        assert result.score == 90.0

    def test_quality_light_diacritics_band(self) -> None:
        """Sparse vowelling (density below 0.05) scores 50."""
        from aranorm.analysis.quality_score import _score_diacritics

        # Sparse vowelling below 0.05 density scores 50.0
        text = "نْ" + "ا" * 24
        assert _score_diacritics(text, []) == 50.0

    def test_simile_bridge_prefix(self) -> None:
        """Bridge prefixes (مثل→مثلما) must also trigger simile detection."""
        from aranorm.analysis.figurate_analyzer import analyze_figurative

        result = analyze_figurative("الصبر مثلما هو كنز")
        assert "tashbih" in result.figures

    def test_simile_bridge_without_content(self) -> None:
        """A bridge at the very end of the text yields no simile occurrence."""
        result = analyze_figurative("الحمد لله كما")
        assert result.simile_count == 0

    def test_synonym_pair_detection(self) -> None:
        """A synonym pair inside a sentence is classified as taraduf."""
        result = analyze_figurative("البيت منزل واسع")
        assert "taraduf" in result.figures

    def test_no_saj_on_different_endings(self) -> None:
        result = analyze_rhythm("العلم نور، والجهل ظلام")
        assert result.saj_signals == 0

    def test_short_clauses_below_saj_floor(self) -> None:
        """Clauses with a single word never pair into a saj signal."""
        result = analyze_rhythm("نعم، سلام، عمل")
        assert result.saj_signals == 0

    def test_empty_and_short_inputs(self) -> None:
        assert analyze_rhythm("").saj_signals == 0
        assert analyze_rhythm("كلمة").saj_signals == 0
        assert analyze_rhythm(" ").saj_signals == 0

    def test_repeated_phrase_rhythm(self) -> None:
        """Repetition density and balance contribute for mirrored clauses."""
        result = analyze_rhythm("النور يهدي والضمير يرتقي والنور يبقى والضمير يدق")
        assert result.repetition_density > 0.0
        assert result.parallel_balance >= 0.0


class TestRhythmAnalyzerApi:
    def test_batch(self) -> None:
        analyzer = RhythmAnalyzer()
        results = analyzer.analyze_batch(["يعملون، ويكملون", "نص عادي"])
        assert len(results) == 2
        assert results[0].saj_signals >= 1

    def test_to_dict_round_trip(self) -> None:
        result = analyze_rhythm("يعملون، ويكملون")
        payload = result.to_dict()
        assert payload["label"] == result.label
        assert payload["rhythm_index"] == result.rhythm_index
        assert len(payload["saj_pairs"]) == len(result.saj_pairs)

    def test_serializable_payload(self) -> None:
        payload = analyze_rhythm("يعملون، ويكملون").to_dict()
        assert json.dumps(payload, ensure_ascii=False)


class TestRhythmBalance:
    def test_balanced_sentences(self) -> None:
        text = "الشمس تشرق.\nالقمر يضيء.\nالنجوم تسطع."
        result = analyze_rhythm(text)
        assert result.parallel_balance > 0.0

    def test_unbalanced_sentences(self) -> None:
        text = "قصير.\nهذه جملة طويلة جداً تحتوي على كلمات كثيرة بلا داعٍ في هذا السياق التطويلي الممل."
        result = analyze_rhythm(text)
        assert result.parallel_balance < 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# WP2 — FigurateAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestFigurateLabels:
    """Labels follow rich>=0.35, moderate>=0.13, else plain."""

    def test_rich_label(self) -> None:
        result = analyze_figurative("النجاح كنز كما هو صبر")
        assert result.label in ("rich", "moderate")

    def test_plain_label(self) -> None:
        result = analyze_figurative("ذهبت إلى السوق واشتريت خضراوات")
        assert result.label == "plain"


class TestFigurateSimile:
    def test_kama_simile(self) -> None:
        result = analyze_figurative("الصبر كنز كما هو نور")
        assert result.simile_count >= 1
        assert "tashbih" in result.figures

    def test_mathal_simile(self) -> None:
        result = analyze_figurative("الوقت مثل السيف إن لم تقطعه قطعك")
        assert result.simile_count >= 1

    def test_no_simile_without_bridge(self) -> None:
        result = analyze_figurative("ذهب إلى السوق")
        assert result.simile_count == 0


class TestFigurateTibaq:
    def test_antonym_pair(self) -> None:
        result = analyze_figurative("الليل والنهار يختلفان في الضياء والظلام")
        assert result.tibaq_count >= 1
        assert "tibaq" in result.figures

    def test_no_tibaq(self) -> None:
        result = analyze_figurative("شربت القهوة صباحاً")
        assert result.tibaq_count == 0


class TestFigurateTakrir:
    def test_triple_repetition(self) -> None:
        result = analyze_figurative("الصبر الصبر الصبر مفتاح الفرج")
        assert result.takrir_count >= 1
        # The definite article is normalised away before repetition counting.
        assert "صبر" in result.takrir_words

    def test_double_repetition_no_takrir(self) -> None:
        result = analyze_figurative("الصبر جميل والصبر مفتاح")
        assert result.takrir_count == 0

    def test_short_words_ignored(self) -> None:
        result = analyze_figurative("في في في")
        assert result.takrir_count == 0


class TestFigurateAnalyzerApi:
    def test_batch(self) -> None:
        analyzer = FigurateAnalyzer()
        results = analyzer.analyze_batch(["مثل النهر الجاري", "نص عادي"])
        assert len(results) == 2
        assert results[0].simile_count >= 1

    def test_to_dict(self) -> None:
        result = analyze_figurative("الصبر كنز")
        payload = result.to_dict()
        for field in (
            "figure_index",
            "label",
            "figures",
            "occurrences",
            "simile_count",
            "takrir_words",
            "word_count",
        ):
            assert field in payload

    def test_figure_index_range(self) -> None:
        result = analyze_figurative("كنز كما هو نور مثل الجبل في قوة الصبر")
        assert 0.0 <= result.figure_index <= 1.0

    def test_occurrence_offsets(self) -> None:
        result = analyze_figurative("الصبر كنز")
        for occurrence in result.occurrences:
            assert occurrence.start >= 0
            assert occurrence.end > occurrence.start


# ═══════════════════════════════════════════════════════════════════════════════
# WP3 — NumericAnalyzer
# ═══════════════════════════════════════════════════════════════════════════════


class TestNumericWestern:
    def test_western_digits(self) -> None:
        result = analyze_numeric("حققنا نمواً 123 بالمئة")
        assert result.western_count >= 1

    def test_grouped_western(self) -> None:
        result = analyze_numeric("السكان 1,234 نسمة")
        assert result.western_count >= 1


class TestNumericIndic:
    def test_arabic_indic_digits(self) -> None:
        result = analyze_numeric("الحرارة ٢٥ درجة")
        assert result.arabic_indic_count >= 1

    def test_mixed_digit_system(self) -> None:
        result = analyze_numeric("حققنا 25% أي ٢٥ بالمئة")
        assert result.digit_system_mix is True
        assert result.western_count >= 1
        assert result.arabic_indic_count >= 1

    def test_no_mix_single_system(self) -> None:
        assert analyze_numeric("العدد ١٢٣").digit_system_mix is False
        assert analyze_numeric("العدد 123").digit_system_mix is False


class TestNumericWritten:
    def test_written_number_word(self) -> None:
        result = analyze_numeric("بلغ التعداد مليون مشارك")
        assert result.written_count >= 1

    def test_compound_written(self) -> None:
        result = analyze_numeric("التكلفة خمسمائة ريال")
        assert result.written_count >= 1

    def test_fraction_compound(self) -> None:
        result = analyze_numeric("نصف مليون نسمة")
        assert result.written_count >= 1


class TestNumericPercentageCurrency:
    def test_percentage(self) -> None:
        result = analyze_numeric("حققنا نمواً بنسبة 25% و٣٠٪")
        assert result.percentage_count >= 2

    def test_currency(self) -> None:
        result = analyze_numeric("المبلغ 500 ريال سعودي")
        assert result.currency_count >= 1
        assert any(span.category == "currency" for span in result.spans)

    def test_no_numeric_text(self) -> None:
        result = analyze_numeric("نص بلا أرقام أو نسب أو عملات")
        assert result.western_count == 0
        assert result.arabic_indic_count == 0
        assert result.written_count == 0
        assert result.percentage_count == 0
        assert result.currency_count == 0


class TestNumericAnalyzerApi:
    def test_batch(self) -> None:
        analyzer = NumericAnalyzer()
        results = analyzer.analyze_batch(["١٢٣", "لا شيء"])
        assert len(results) == 2
        assert results[0].arabic_indic_count >= 1

    def test_to_dict_fields(self) -> None:
        payload = analyze_numeric("٢٥٪").to_dict()
        for field in (
            "digit_system_mix",
            "western_count",
            "arabic_indic_count",
            "written_count",
            "percentage_count",
            "currency_count",
            "numeric_density",
            "spans",
            "word_count",
        ):
            assert field in payload

    def test_numeric_density(self) -> None:
        result = analyze_numeric("الحرارة ٢٥ والضغط ١٢ درجة")
        assert result.numeric_density > 0.0

    def test_empty_input(self) -> None:
        result = analyze_numeric("")
        assert result.numeric_density == 0.0

    def test_span_offsets(self) -> None:
        spans = analyze_numeric("السعر 99 و ٩٩").spans
        for span in spans:
            assert span.start >= 0
            assert span.end > span.start


# ═══════════════════════════════════════════════════════════════════════════════
# WP4 — dialect_depth
# ═══════════════════════════════════════════════════════════════════════════════


class TestDialectRegions:
    def test_all_four_regions_present(self) -> None:
        assert {"gulf", "levant", "egyptian", "maghrebi"}.issubset(set(_REGION_MARKERS))

    def test_gulf_detected(self) -> None:
        result = analyze_dialect("شلونك حبيبي ياهلا دحين")
        assert result.region_hits["gulf"] >= 1

    def test_levant_detected(self) -> None:
        result = analyze_dialect("كيفك شو بدك مين هيك")
        assert result.region_hits["levant"] >= 1

    def test_egyptian_detected(self) -> None:
        result = analyze_dialect("إزاي دلوقتي يعني إنت")
        assert result.region_hits["egyptian"] >= 1

    def test_maghrebi_detected(self) -> None:
        result = analyze_dialect("شنو دابا، بزاف مزيان ياك")
        assert result.dominant_region == "maghrebi"

    def test_msa_no_region(self) -> None:
        result = analyze_dialect("العلم نور يرفع الأمم حيثما وجد")
        assert result.dominant_region == "none"
        assert result.is_dialectal is False


class TestDialectAnalyzer:
    def test_threshold_parameter(self) -> None:
        """A threshold above the maximum achievable density yields no region."""
        analyzer = DialectAnalyzer(region_threshold=1.5)
        result = analyzer.analyze("شنو دابا بزاف")
        assert result.dominant_region == "none"

    def test_batch(self) -> None:
        analyzer = DialectAnalyzer()
        results = analyzer.analyze_batch(["شلونك", "نص فصيح"])
        assert len(results) == 2
        assert results[0].is_dialectal is True
        assert results[1].dominant_region == "none"

    def test_region_scores_density(self) -> None:
        result = analyze_dialect("شنو شنو")
        assert result.word_count > 0
        for score in result.region_scores.values():
            assert 0.0 <= score <= 1.0

    def test_strength_bounded(self) -> None:
        result = analyze_dialect("شنو دابا بزاف مزيان ياك")
        assert 0.0 <= result.dialect_strength <= 1.0

    def test_to_dict(self) -> None:
        payload = analyze_dialect("شنو دابا").to_dict()
        for field in (
            "dominant_region",
            "region_scores",
            "region_hits",
            "marker_words",
            "word_count",
            "is_dialectal",
            "dialect_strength",
            "traces",
        ):
            assert field in payload

    def test_empty_input(self) -> None:
        result = analyze_dialect("")
        assert result.word_count == 0
        assert result.dominant_region == "none"

    def test_default_threshold(self) -> None:
        assert _REGION_THRESHOLD == 0.06


# ═══════════════════════════════════════════════════════════════════════════════
# WP5 — 12-axis profiler & rhetorical-richness quality component
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfilerTwentyTwoAxes:
    def test_default_nineteen_axes(self) -> None:
        assert len(_DEFAULT_AXES) == 22

    def test_profile_all_axes(self) -> None:
        result = profile_text("يعملون، ويكملون حيثما اجتمعت الإرادة")
        expected = {
            "sentiment",
            "coherence",
            "quality",
            "readability",
            "style",
            "emotions",
            "word_frequency",
            "topics",
            "rhythm",
            "figurate",
            "numeric",
            "dialect",
            "entities",
            "quotation",
            "loanwords",
            "root_density",
            "contrast",
            "fillers",
            "complexity",
        } | {"wordplay", "rquestions", "anaphora"}
        assert expected == set(result.axes)

    def test_insight_rhetorically_rich(self) -> None:
        """A text combining simile, antithesis and refrain crosses the rich band."""
        result = profile_text("الصبر الصبر الصبر كنز كما هو نور، فالليل يقصر والنهار يطول")
        rules = [insight.rule for insight in result.insights]
        assert "rhetorically_rich" in rules

    def test_insight_formal_rhythmic(self) -> None:
        """A balanced rhythmic sentence in a formal register triggers the rule."""
        result = profile_text(
            "حيثما تعتمد المنظمة الاستراتيجيات، ينجح المديرون وفق التوصيات. "
            "حيثما تعتمدها المؤسسة الاستراتيجيات، ينجح المديرون بموجب التقارير. "
            "حيثما تعتمد الهيئة الاستراتيجيات، ينجح المديرون إذ تلزم المنظمة. "
            "علاوة على ذلك، تنهض المنظمة وفق التوصيات"
        )
        rules = [insight.rule for insight in result.insights]
        assert "formal_rhythmic" in rules

    def test_insight_mixed_digits(self) -> None:
        result = profile_text("حققنا 25% أي ٢٥ بالمئة")
        rules = [insight.rule for insight in result.insights]
        assert "mixed_digit_systems" in rules

    def test_insight_dialectal_regional(self) -> None:
        result = profile_text("شنو دابا بزاف مزيان ياك")
        rules = [insight.rule for insight in result.insights]
        assert "dialectal_regional" in rules

    def test_no_false_insights_plain_text(self) -> None:
        result = profile_text("نص عربي محايد قصير")
        rules = {insight.rule for insight in result.insights}
        assert not rules.intersection(
            {"formal_rhythmic", "rhetorically_rich", "mixed_digit_systems", "dialectal_regional"}
        )

    def test_profiler_custom_axes(self) -> None:
        result = AnalysisProfiler(axes=["rhythm", "figurate"]).profile("نص")
        assert set(result.axes) == {"rhythm", "figurate"}

    def test_profiler_batch(self) -> None:
        profiler = AnalysisProfiler()
        results = profiler.profile_batch(["يعملون، ويكملون", "شنو دابا"])
        assert len(results) == 2
        assert all(len(result.axes) == 22 for result in results)

    def test_profiler_to_json(self) -> None:
        payload = json.loads(profile_text("نص تجريبي").to_json())
        assert "axes" in payload
        assert "insights" in payload


class TestQualityRhetoricalRichness:
    def test_rhetorically_rich_text(self) -> None:
        result = analyze_quality("الصبر كنز كما هو نور، فالليل يقصر والنهار يطول")
        richness = next(component for component in result.components if component.name == "rhetorical_richness")
        assert richness.score > 50.0

    def test_plain_text_baseline(self) -> None:
        result = analyze_quality("ذهبت إلى السوق واشتريت خضراوات طازجة")
        richness = next(component for component in result.components if component.name == "rhetorical_richness")
        assert richness.score == 50.0

    def test_suggestion_for_plain_text(self) -> None:
        result = analyze_quality("ذهبت إلى السوق واشتريت خضراوات")
        assert any("rhetorical" in issue.lower() for issue in result.suggestions)

    def test_seven_components(self) -> None:
        result = analyze_quality("نص تجريبي قصير")
        names = [component.name for component in result.components]
        assert len(names) == 8
        assert "rhetorical_richness" in names
        assert "rhetorical_depth" in names
        assert "structural_balance" in names

    def test_component_weights_sum(self) -> None:
        from aranorm.analysis.quality_score import _COMPONENT_WEIGHTS

        assert abs(sum(_COMPONENT_WEIGHTS.values()) - 1.0) < 1e-9
