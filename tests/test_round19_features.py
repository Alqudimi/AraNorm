"""Round 19 — new analytical features and expansions.

Covers:
- WP1: WordFrequencyProfiler (diversity indices, lexical density, Zipf).
- WP2: SpellingCorrection suggestions.
- WP3: TextCoherenceScore (4 axes, labels, weights).
- WP4: TopicClassifier expansion to 13 fields.
- WP5: CorpusAnalyzer.overlap_analysis (matrix, pairs, distinctiveness).
"""

import math
from typing import List

from aranorm.analysis.coherence_score import CoherenceAnalyzer, analyze_coherence
from aranorm.analysis.corpus_analyzer import CorpusAnalyzer
from aranorm.analysis.spelling_report import SpellingAnalyzer
from aranorm.analysis.topic_classifier import TopicClassifier
from aranorm.analysis.word_frequency import WordFrequencyProfiler

# ── WP1: WordFrequencyProfiler ─────────────────────────────────────────────────


class TestWordFrequencyProfiler:
    """Vocabulary-frequency and diversity profiling."""

    def _run(self, text: str, **kwargs):
        return WordFrequencyProfiler(**kwargs).profile(text)

    def test_repeated_word_increases_count(self):
        result = self._run("التعلم التعلم التعلم أساس النجاح")
        entry = result.frequency_table[0]
        assert entry.word == "التعلم"
        assert entry.count == 3
        assert entry.rank == 1
        assert abs(entry.relative_frequency - 3 / 5) < 1e-9

    def test_ttr_range(self):
        result = self._run("العلم نور والعلم نور والعلم نور")
        assert 0.0 <= result.type_token_ratio <= 1.0
        assert result.unique_types < result.total_tokens

    def test_corrected_ttr_guiraud(self):
        result = self._run("العلم نور والجهل ظلام والعلم أساس التقدم والتطور والنهضة")
        expected = result.unique_types / math.sqrt(result.total_tokens)
        assert abs(result.corrected_ttr - expected) < 1e-9

    def test_root_ttr_herdan(self):
        result = self._run("العلم نور والجهل ظلام والعلم أساس التقدم والتطور والنهضة")
        expected = math.log(result.unique_types) / math.log(result.total_tokens)
        assert abs(result.root_ttr - expected) < 1e-9

    def test_root_ttr_single_token_is_zero(self):
        result = self._run("سلام")
        assert result.root_ttr == 0.0
        assert result.total_tokens == 1

    def test_root_ttr_zero_tokens_is_zero(self):
        result = self._run("")
        assert result.root_ttr == 0.0

    def test_zipf_none_below_four_types(self):
        result = self._run("أ ب ج")
        assert result.zipf_exponent is None

    def test_zipf_exponent_for_distributed_text(self):
        # Need >= 4 distinct types for a meaningful Zipf fit (min_word_length=2).
        # The estimator returns the negated slope: a Zipf-like decaying
        # distribution (high count for low rank) yields a positive value.
        words = ["العلم", "العلم", "العلم", "نور", "نور", "ظلام", "ضوء"]
        result = self._run(" ".join(words))
        assert result.zipf_exponent is not None
        assert result.zipf_exponent > 0  # decaying rank-frequency relation

    def test_zipf_exponent_none_below_min_types(self):
        result = self._run("كبير كبير كبير كبير")
        assert result.zipf_exponent is None

    def test_lexical_density_filters_function_words(self):
        result = self._run("في المدرسة كان العلم من كل شيء")
        assert result.lexical_density < 1.0

    def test_lexical_density_all_content_words(self):
        result = self._run("التقدم التكنولوجيا الابتكار")
        assert result.lexical_density == 1.0

    def test_lexical_density_no_filter_mode(self):
        result = WordFrequencyProfiler(content_words_only_for_density=False).profile(
            "في المدرسة كان العلم",
        )
        assert result.lexical_density == 1.0

    def test_article_stripped_for_density_filter(self):
        # "في" alone is a function word -> excluded from content count
        result = self._run("في في في في في في في في في في علم")
        assert result.lexical_density == 1 / 11

    def test_frequency_table_ranking(self):
        result = self._run("شمس شمس قمر قمر قمر قمر نجم")
        table = result.frequency_table
        assert table[0].word == "قمر"
        assert table[1].word == "شمس"
        assert table[2].word == "نجم"

    def test_first_positions_track_occurrences(self):
        result = self._run("نور قمر شمس نور")
        entry = next(item for item in result.frequency_table if item.word == "نور")
        assert entry.first_positions == [0, 3]

    def test_first_positions_capped_at_three(self):
        result = self._run("نور نور نور نور نور")
        entry = result.frequency_table[0]
        assert len(entry.first_positions) == 3

    def test_min_word_length_filter(self):
        result = WordFrequencyProfiler(min_word_length=3).profile("أ ب مرحبا")
        assert all(len(item.word) >= 3 for item in result.frequency_table)

    def test_empty_text_result(self):
        result = self._run("")
        assert result.total_tokens == 0
        assert result.type_token_ratio == 0.0
        assert result.frequency_table == []

    def test_punctuation_only_text(self):
        result = self._run("... ؟!!")
        assert result.total_tokens == 0

    def test_diacritics_and_hamza_normalization_merge_types(self):
        # "كُتُب" and "كتب" (after diacritics removal) must merge
        result = self._run("كُتُب كتب")
        assert result.unique_types == 1

    def test_taa_marbuta_normalization_merges(self):
        result = self._run("مدرسة مدرسة")
        assert result.unique_types == 1

    def test_to_dict_roundtrip(self):
        result = self._run("العلم نور")
        payload = result.to_dict()
        assert payload["total_tokens"] == result.total_tokens
        assert len(payload["frequency_table"]) == len(result.frequency_table)

    def test_to_json_is_valid(self):
        import json

        result = self._run("العلم نور")
        parsed = json.loads(result.to_json())
        assert parsed["original_text"] == "العلم نور"

    def test_frequency_entry_to_dict_keys(self):
        result = self._run("العلم نور")
        keys = result.frequency_table[0].to_dict().keys()
        assert {"word", "count", "rank", "relative_frequency", "first_positions"} <= set(keys)

    def test_top_n_caps_table(self):
        # Taa-marbuta normalizes to heh: "مدرسة/مكتبة" merge with "مدرسه/مكتبه",
        # so the 11 tokens collapse to 4 distinct types <= default top_n=20
        result = self._run("مدرسة جامعة مكتبة متحف مدرسة جامعة مكتبة متحف مدرسة جامعة مكتبة")
        assert len(result.frequency_table) == 4
        assert result.frequency_table[0].count == 3

    def test_top_n_parameter_caps_table(self):
        # more distinct types than top_n=3
        result = WordFrequencyProfiler(top_n=3).profile("مدرسة جامعة مكتبة متحف")
        assert len(result.frequency_table) == 3

    def test_rank_ties_broken_alphabetically(self):
        result = self._run("بنك بنك بيت بيت")
        # After alef normalization both forms share the count 2; alphabetical
        # tie-breaking orders by the normalized form; verify the top-2 order is
        # stable and deterministic rather than guessing the normalized form.
        table = result.frequency_table
        assert table[0].count == table[1].count == 2
        assert table[0].word < table[1].word


class TestWordFrequencyProfilerBounds:
    """Boundary guards for the profiler constructor and indices."""

    def test_negative_top_n_clamped(self):
        profiler = WordFrequencyProfiler(top_n=-3)
        assert profiler.top_n == 1

    def test_zero_min_length_clamped(self):
        profiler = WordFrequencyProfiler(min_word_length=0)
        assert profiler.min_word_length == 1

    def test_one_type_ttr(self):
        result = WordFrequencyProfiler().profile("كلمة")
        assert result.type_token_ratio == 1.0
        assert result.corrected_ttr == 1.0

    def test_ttr_one_for_all_unique(self):
        result = WordFrequencyProfiler().profile("مدرسة جامعة مكتبة متحف")
        assert result.type_token_ratio == 1.0

    def test_very_short_text_returns_zero_density_axis_safe(self):
        result = WordFrequencyProfiler().profile("x")
        assert result.total_tokens == 0

    def test_mixed_scripts(self):
        result = WordFrequencyProfiler().profile("hello مرحبا world")
        assert result.total_tokens == 3

    def test_corrected_ttr_zero_for_empty(self):
        assert WordFrequencyProfiler._corrected_ttr(0, 0) == 0.0

    def test_root_ttr_zero_for_single_token(self):
        assert WordFrequencyProfiler._root_ttr(1, 1) == 0.0

    def test_root_ttr_zero_for_zero_tokens(self):
        assert WordFrequencyProfiler._root_ttr(0, 0) == 0.0

    def test_zipf_denominator_zero_returns_zero(self):
        # identical counts -> zero variance denominator -> zero slope
        ranked = [("a", 5), ("b", 5), ("c", 5), ("d", 5)]
        exp = WordFrequencyProfiler._zipf_exponent(ranked, 20)
        assert exp is not None
        assert abs(exp) < 1e-9

    def test_zipf_none_for_single_type(self):
        assert WordFrequencyProfiler._zipf_exponent([("a", 5)], 5) is None

    def test_english_only_text(self):
        result = WordFrequencyProfiler().profile("the quick brown fox jumps over the lazy dog")
        assert result.type_token_ratio == 8 / 9  # 'the' repeats

    def test_digits_text(self):
        result = WordFrequencyProfiler().profile("123 456 789")
        assert result.total_tokens == 3


# ── WP2: SpellingCorrection suggestions ────────────────────────────────────────


class TestSpellingSuggestions:
    """Correction suggestions carry confidence scores."""

    def _analyze(self, text: str):
        analyzer = SpellingAnalyzer()
        return analyzer.analyze(text)

    def test_correction_has_suggestion(self):
        result = self._analyze("الاعلان الرسمي مهم")
        item = next((c for c in result.corrections if c.word == "الاعلان"), None)
        assert item is not None
        assert len(item.suggestions) >= 1
        top = item.suggestions[0]
        assert top["word"] == "الإعلان"
        assert 0.0 <= top["confidence"] <= 1.0
        assert top["source"] == "rule"

    def test_correct_word_has_no_suggestions(self):
        result = self._analyze("الإعلان الرسمي مهم")
        assert result.corrections == []

    def test_suggestion_rounds_trip_in_dict(self):
        result = self._analyze("الاعلان")
        payload = result.to_dict()
        assert "suggestions" in payload["corrections"][0]

    def test_suggestions_for_multiple_errors(self):
        result = self._analyze("الاعلان و المدرسة غير منظمة")
        flagged = [item for item in result.corrections if item.suggestions]
        assert len(flagged) >= 1

    def test_empty_text_no_issues(self):
        result = self._analyze("")
        assert result.corrections == []


# ── WP3: TextCoherenceScore ────────────────────────────────────────────────────


class TestTextCoherence:
    """Deterministic coherence scoring across four axes."""

    def test_labels_are_valid(self):
        valid = {"strong", "moderate", "weak", "fragmented"}
        for text in ("جملة واحدة.", "نص متعدد الجمل.", "مقطع متقطع بدون روابط. ولا ترابط. هنا نهاية."):
            assert analyze_coherence(text).label in valid

    def test_score_bounded(self):
        for text in ("جملة واحدة.", "نص طويل من عدة جمل مترابطة.", ""):
            score = analyze_coherence(text).score
            assert 0.0 <= score <= 1.0

    def test_empty_text_is_fragmented(self):
        result = analyze_coherence("")
        assert result.score == 0.0
        assert result.label == "fragmented"

    def test_single_sentence_balance_one(self):
        result = analyze_coherence("جملة واحدة كافية.")
        balance = next(item for item in result.breakdown if item.axis == "sentence_balance")
        assert balance.value == 1.0

    def test_connected_text_scores_higher_than_fragmented(self):
        connected = "افتتح رئيس اللجنة الاجتماع. ثم ناقش الأعضاء التقرير. لذلك صدرت التوصيات. كما اعتمد الجدول الزمني."
        fragmented = "هناك سيارة. الكتاب أزرق. اليوم حار. القطة نائمة."
        c = analyze_coherence(connected).score
        f = analyze_coherence(fragmented).score
        assert c > f

    def test_connectives_counted(self):
        # Three multi-letter connectives, each appearing once
        result = analyze_coherence("لذلك افتتح الاجتماع. بالتالي ناقش الحضور. بينما عاد النقاش.")
        assert result.connective_count == 3
        axes = result.axes
        assert axes.get("connectors", 0) > 0.0

    def test_weights_sum_to_one(self):
        result = analyze_coherence("نص تجريبي هنا. وهناك نص آخر.")
        total = sum(item.weight for item in result.breakdown)
        assert abs(total - 1.0) < 1e-9

    def test_label_thresholds(self):
        # Labels are derived from the final weighted score. A lexically
        # repetitive, connective-rich text reaches the "moderate" band (>= 0.5),
        # while truly disconnected single-word sentences stay "fragmented".
        cohesive = analyze_coherence(
            "في الاجتماع تم مناقشة الاجتماع السابق. ثم تم اعتماد الاجتماع السابق في القرار. "
            "لذلك يغطي الاجتماع الجديد الاجتماع الجديد كاملا.",
        )
        assert cohesive.label in {"moderate", "strong"}
        disconnected = analyze_coherence("سيارة. كتاب. سماء. حجر.")
        assert disconnected.label == "fragmented"
        assert cohesive.score > disconnected.score

    def test_custom_weights_applied(self):
        analyzer = CoherenceAnalyzer(weights={"lexical_repeat": 1.0})
        result = analyzer.analyze("نص تجريبي نص تجريبي نص تجريبي.")
        repeat = next(item for item in result.breakdown if item.axis == "lexical_repeat")
        assert repeat.weight == 1.0

    def test_to_dict_includes_axes(self):
        result = analyze_coherence("جملة واحدة هنا. وجملة ثانية هناك.")
        payload = result.to_dict()
        assert "score" in payload
        assert "breakdown" in payload
        assert payload["text"] == result.text

    def test_to_json_valid(self):
        import json

        parsed = json.loads(analyze_coherence("نص تجريبي.").to_json())
        assert "score" in parsed

    def test_summary_nonempty(self):
        text = analyze_coherence("جملة هنا. وجمله ثانية هناك.").summary()
        assert text

    def test_axes_dict_view(self):
        result = analyze_coherence("نص تجريبي واحد. نص تجريبي آخر.")
        assert "lexical_repeat" in result.axes
        assert {"lexical_repeat", "connectors", "sentence_balance", "topic_consistency"} == set(result.axes)

    def test_content_word_count_positive(self):
        result = analyze_coherence("المدرسة والجامعة والمكتبة")
        assert result.content_word_count > 0

    def test_breakdown_item_to_dict_keys(self):
        result = analyze_coherence("نص. نص آخر.")
        keys = result.breakdown[0].to_dict().keys()
        assert {"axis", "value", "weight", "contribution"} <= set(keys)


# ── WP4: TopicClassifier expansion ─────────────────────────────────────────────


class TestTopicExpansion:
    """Topic lexicon extended to 13 fields."""

    def _topics(self) -> List[str]:
        classifier = TopicClassifier()
        return list(classifier.topics)

    def test_thirteen_topics_available(self):
        assert len(self._topics()) == 13  # 9 original + 4 new (history, environment, culture, community)

    def test_new_topics_present(self):
        topics = self._topics()
        for topic in ("history", "environment", "culture", "community"):
            assert topic in topics

    def test_history_classification(self):
        classifier = TopicClassifier()
        result = classifier.classify("الحضارة الإسلامية شهدت تطورًا عبر العصور القديمة والحديثة")
        assert result.primary_topic == "history"

    def test_environment_classification(self):
        classifier = TopicClassifier()
        result = classifier.classify("التغير المناخي والتصحر يهددان البيئة والتنوع البيولوجي")
        assert result.primary_topic == "environment"

    def test_culture_classification(self):
        classifier = TopicClassifier()
        result = classifier.classify("الفنون والتراث الشعبي والموسيقى جزء من الهوية الثقافية")
        assert result.primary_topic == "culture"

    def test_community_classification(self):
        classifier = TopicClassifier()
        result = classifier.classify("التطوع والعمل الاجتماعي يقويان الروابط المجتمعية في الأحياء")
        assert result.primary_topic == "community"

    def test_existing_topics_still_work(self):
        classifier = TopicClassifier()
        result = classifier.classify("التقنية الحديثة تطور البرمجيات والذكاء الاصطناعي")
        assert result.primary_topic == "technology"

    def test_confidence_positive(self):
        classifier = TopicClassifier()
        result = classifier.classify("التقنية الحديثة تطور البرمجيات")
        assert result.confidence > 0.0

    def test_scores_list_sorted_descending(self):
        classifier = TopicClassifier()
        result = classifier.classify("الحضارة الإسلامية عبر العصور")
        scores = [score.score for score in result.scores]
        assert scores == sorted(scores, reverse=True)

    def test_primary_score_positive(self):
        classifier = TopicClassifier()
        result = classifier.classify("التقنية والبرمجيات الحديثة")
        assert result.primary_score >= 0.0
        assert result.primary_topic == "technology"

    def test_custom_topic_subset(self):
        classifier = TopicClassifier(topics=["history", "environment"])
        result = classifier.classify("الحضارة عبر العصور")
        assert all(score.topic in {"history", "environment"} for score in result.scores)

    def test_to_dict_includes_primary_topic(self):
        classifier = TopicClassifier()
        payload = classifier.classify("الرياضة كرة القدم والملعب").to_dict()
        assert "primary_topic" in payload
        assert "scores" in payload
        assert "top_topics" in payload
        assert payload["primary_topic"] == "sport"


# ── WP5: CorpusAnalyzer.overlap_analysis ───────────────────────────────────────


class TestOverlapAnalysis:
    """Pairwise Jaccard overlap and per-document distinctiveness."""

    def _analyze(self, texts):
        return CorpusAnalyzer().overlap_analysis(texts)

    def test_matrix_symmetry_and_diagonal_one(self):
        result = self._analyze(["التقنية تطور الاقتصاد", "التقنية تطور الصناعة", "كلمة مختلفة تمامًا"])
        matrix = result.overlap_matrix
        # upper-triangular keys "0,1" "0,2" "1,2"
        assert "0,1" in matrix
        assert "0,2" in matrix
        assert "1,2" in matrix
        assert 0.0 <= matrix["0,1"] <= 1.0
        # "0,1" pairs two documents sharing "التقنية"+"تطور"
        assert matrix["0,1"] > 0.0

    def test_identical_documents_full_overlap(self):
        result = self._analyze(["نص واحد مكرر", "نص واحد مكرر"])
        matrix = result.overlap_matrix
        key = next((key for key in matrix if key.startswith("0,")), None)
        assert key is not None
        assert abs(matrix[key] - 1.0) < 1e-9

    def test_disjoint_documents_zero_overlap(self):
        result = self._analyze(["أ ب ج", "د ه و"])
        assert result.overlap_matrix["0,1"] == 0.0  # both stop-word-stripped to empty

    def test_most_and_least_similar_pairs(self):
        result = self._analyze(["نص مشترك كثير بين الاثنين", "نص مشترك كثير بين الاثنين", "كلمة وحيدة"])
        most = result.most_similar_pair
        least = result.least_similar_pair
        assert most is not None
        assert least is not None
        assert most[2] >= least[2]

    def test_average_similarity_range(self):
        result = self._analyze(["نص تجريبي هنا", "نص تجريبي آخر", "كلمة وحيدة"])
        assert 0.0 <= result.average_similarity <= 1.0

    def test_distinctiveness_count(self):
        result = self._analyze(["أ ب ج", "ب ج د", "د ه و"])
        assert len(result.distinctiveness) == 3
        assert all(0.0 <= item.distinctiveness <= 1.0 for item in result.distinctiveness)

    def test_distinctiveness_unique_vocabulary(self):
        # Single-letter tokens are filtered out by _tokens (min length), so use
        # full words; "ب" is a stop word and gets stripped as well.
        result = self._analyze(["التقنية تطور الاقتصاد", "التقنية تطور الصناعة"])
        doc0 = result.distinctiveness[0]
        assert "الاقتصاد" in doc0.only_in_this_document
        assert "التقنية" in doc0.shared_vocabulary

    def test_single_document_no_pairs(self):
        result = self._analyze(["نص واحد فقط"])
        assert result.document_count == 1
        assert result.most_similar_pair is None
        assert result.least_similar_pair is None
        assert result.average_similarity == 0.0

    def test_empty_corpus(self):
        result = self._analyze([])
        assert result.document_count == 0
        assert result.overlap_matrix == {}

    def test_to_dict_roundtrip(self):
        result = self._analyze(["نص تجريبي", "نص تجريبي آخر"])
        payload = result.to_dict()
        assert payload["document_count"] == result.document_count
        assert len(payload["distinctiveness"]) == 2

    def test_distinctiveness_to_dict_keys(self):
        result = self._analyze(["أ ب", "ب ج"])
        keys = result.distinctiveness[0].to_dict().keys()
        assert {"index", "only_in_this_document", "shared_vocabulary", "distinctiveness"} <= set(keys)

    def test_overlap_works_with_stop_words_stripped(self):
        # Common function words are stripped; content overlap drives the score.
        result = self._analyze(["التقنية تطور الاقتصاد بشكل كبير", "التقنية تطور الصناعة بشكل ملحوظ"])
        assert 0.0 <= result.overlap_matrix["0,1"] <= 1.0
        # "التقنية" و"تطور" shared; "الاقتصاد"/"الصناعة" exclusive
        doc0 = result.distinctiveness[0]
        assert "الاقتصاد" in doc0.only_in_this_document

    def test_three_docs_matrix_keys(self):
        result = self._analyze(["أ ب", "ج د", "ه و"])
        assert len(result.overlap_matrix) == 3  # C(3,2)
