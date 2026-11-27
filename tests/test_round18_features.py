"""Round 18 feature suite: entities, topics, pronouns, idioms, snapshots, and CLI.

Covers the five new capabilities shipped in Round 18:
EntityAnalyzer, TopicClassifier, PronounAnalyzer, IdiomAnalyzer,
PipelineSnapshot, plus the five new CLI commands and the spelling-report
idiom-exclusion integration. Deterministic and dependency-free where the
underlying features are.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from typing import List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
CLI = [sys.executable, "-m", "aranorm.cli"]


def _run_cli(args: List[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, capture_output=True, text=True, env=env)


# =====================================================================
# EntityAnalyzer
# =====================================================================


class TestEntityAnalyzer:
    @pytest.fixture(autouse=True)
    def setup(self):
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        self.analyzer = EntityAnalyzer()

    def test_person_with_title(self):
        result = self.analyzer.analyze("زار السيد محمد بن سلمان الرياض اليوم")
        names = {e.text for e in result.entities if e.entity_type == "person"}
        assert "محمد بن سلمان" in names
        assert result.person_count >= 1

    def test_person_title_stop_at_connective(self):
        result = self.analyzer.analyze("التقى الرئيس جو بايدن في القاهرة")
        texts = [e.text for e in result.entities if e.entity_type == "person"]
        assert any("جو بايدن" in t or t == "جو بايدن" for t in texts)
        for entity in result.entities:
            assert "التقى" not in entity.text

    def test_name_cluster_persons(self):
        result = self.analyzer.analyze("قابلنا محمد وخالد وعلي وحسين")
        person_texts = [e.text for e in result.entities if e.entity_type == "person"]
        assert any("محمد" in t for t in person_texts)

    def test_name_cluster_with_waw(self):
        result = self.analyzer.analyze("حضر محمد وخالد وعلي")
        person_texts = [e.text for e in result.entities if e.entity_type == "person"]
        assert any("خالد" in t and "علي" in t for t in person_texts)

    def test_location_dictionary(self):
        result = self.analyzer.analyze("سافرت إلى الرياض ثم القاهرة")
        types = [e.entity_type for e in result.entities]
        assert types.count("location") >= 2

    def test_location_prefix_absorption(self):
        result = self.analyzer.analyze("زرنا مدينة جدة وجبل طويق")
        prefixes = ("مدينة", "جبل")
        absorbed = [e.text for e in result.entities if e.entity_type == "location" and e.text.startswith(prefixes)]
        assert len(absorbed) >= 2

    def test_organization_dictionary(self):
        result = self.analyzer.analyze("أعلنت منظمة الصحة العالمية خطة جديدة")
        orgs = [e.text for e in result.entities if e.entity_type == "organization"]
        assert len(orgs) >= 1

    def test_organization_dictionary_override(self):
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        analyzer = EntityAnalyzer(organization_override=["شركة المنار"])
        result = analyzer.analyze("افتتحت شركة المنار فرعاً جديداً")
        orgs = [e.text for e in result.entities if e.entity_type == "organization"]
        assert "شركة المنار" in orgs

    def test_dictionary_entities_without_money(self):
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        analyzer = EntityAnalyzer(detect_types=["person"], name_threshold=1)
        result = analyzer.analyze("زار محمد وخالد الرياض بمبلغ 500 ريال")
        assert result.money_count == 0
        assert any(e.text == "محمد وخالد" for e in result.entities)

    def test_money_with_currency(self):
        result = self.analyzer.analyze("صفقة بقيمة 500 مليون دولار")
        moneys = [e.text for e in result.entities if e.entity_type == "money"]
        assert any("500" in m for m in moneys)

    def test_money_not_four_digit_year(self):
        result = self.analyzer.analyze("في عام 2025 ارتفعت الأسعار")
        moneys = [e.text for e in result.entities if e.entity_type == "money"]
        assert all(m != "2025" for m in moneys)

    def test_date_patterns(self):
        result = self.analyzer.analyze("عقد الاجتماع في 15 رمضان 1445هـ وبعده في 2026-08-19")
        dates = [e.text for e in result.entities if e.entity_type == "date"]
        assert any("15 رمضان 1445" in d or "15 رمضان" in d for d in dates)
        assert any("2026" in d for d in dates)

    def test_phone_number(self):
        result = self.analyzer.analyze("اتصل على الرقم 0501234567 للتواصل")
        phones = [e.text for e in result.entities if e.entity_type == "phone"]
        assert any("0501234567" in p for p in phones)

    def test_phone_not_plain_year(self):
        result = self.analyzer.analyze("ولادة 1990")
        phones = [e.text for e in result.entities if e.entity_type == "phone"]
        assert all(p != "1990" for p in phones)

    def test_exact_offsets(self):
        text = "ذهب محمد إلى الرياض"
        result = self.analyzer.analyze(text)
        for entity in result.entities:
            assert (
                text[entity.start : entity.end] == entity.text
            ), f"offset mismatch for {entity.text!r} at {entity.start}:{entity.end}"

    def test_empty_text(self):
        result = self.analyzer.analyze("")
        assert result.entity_count == 0
        assert result.entities == []

    def test_title_person_offset_valid(self):
        # title regex matches on cleaned text; offsets must stay inside bounds
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        analyzer = EntityAnalyzer()
        result = analyzer.analyze("زارَ السيدُ أحمدُ السوقَ")
        for entity in result.entities:
            assert 0 <= entity.start <= entity.end <= len(result.original_text)

    def test_name_cluster_split_by_common_word(self):
        # a cluster must only form across consecutive names
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        result = EntityAnalyzer().analyze("حضر محمد السوق وخالد")
        person_texts = " ".join(e.text for e in result.entities if e.entity_type == "person")
        assert "محمد السوق وخالد" not in person_texts

    def test_name_cluster_single_token_text(self):
        # text with only one token cannot form a cluster
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        result = EntityAnalyzer().analyze("محمد")
        assert result.person_count == 0

    def test_name_cluster_broken_by_non_name(self):
        # two names separated by a non-name word must NOT form a cluster
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        result = EntityAnalyzer().analyze("قابلنا محمد اليوم خالد")
        person_texts = [e.text for e in result.entities if e.entity_type == "person"]
        assert all("محمد" not in t or "اليوم" not in t for t in person_texts)

    def test_name_cluster_followed_by_stop_word(self):
        # cluster at end of tokens (no trailing else branch) still records
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        result = EntityAnalyzer().analyze("حضر محمد وخالد")
        person_texts = [e.text for e in result.entities if e.entity_type == "person"]
        assert any("خالد" in t for t in person_texts)

    def test_empty_after_strip(self):
        result = self.analyzer.analyze("   ")
        assert result.entity_count == 0

    def test_type_filtering(self):
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        limited = EntityAnalyzer(detect_types=["date"])
        result = limited.analyze("محمد زار الرياض يوم 2026-08-19")
        assert all(e.entity_type == "date" for e in result.entities)

    def test_name_threshold(self):
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        high = EntityAnalyzer(name_threshold=3)
        result = high.analyze("السيد محمد في السوق")
        titles = [e for e in result.entities if e.entity_type == "person"]
        assert len(titles) == 0

    def test_dictionary_override(self):
        from aranorm.analysis.entity_analyzer import EntityAnalyzer

        custom = EntityAnalyzer(location_override=["بوكارست"])
        result = custom.analyze("زرت بوكارست الجميلة")
        assert any(e.text == "بوكارست" and e.entity_type == "location" for e in result.entities)

    def test_batch_analysis(self):
        results = self.analyzer.analyze_batch(["السيد محمد في الرياض", "صفقة 500 مليون ريال"])
        assert len(results) == 2
        assert results[0].person_count >= 1
        assert results[1].money_count == 1

    def test_to_dict_roundtrip(self):
        result = self.analyzer.analyze("محمد 0501234567 2026-08-19")
        payload = result.to_dict()
        assert payload["entity_count"] == result.entity_count
        parsed = json.loads(result.to_json())
        assert parsed["entity_count"] == result.entity_count

    def test_coverage_ratio(self):
        result = self.analyzer.analyze("0501234567 2026-08-19")
        assert 0.0 <= result.coverage_ratio <= 1.0


# =====================================================================
# TopicClassifier
# =====================================================================


class TestTopicClassifier:
    @pytest.fixture(autouse=True)
    def setup(self):
        from aranorm.analysis.topic_classifier import TopicClassifier

        self.classifier = TopicClassifier()

    def test_medical_topic(self):
        result = self.classifier.classify("المريض يعاني من ضغط الدم ويتم علاجه في المستشفى")
        assert result.primary_topic == "medical"
        assert result.confidence > 0.5

    def test_sports_topic(self):
        result = self.classifier.classify("فاز الفريق بالكأس وسجل اللاعب ثلاثة أهداف في الملعب")
        assert result.primary_topic == "sport"

    def test_technical_topic(self):
        result = self.classifier.classify("البرنامج يحتاج تحديث الخادم وتثبيت البرمجيات على النظام")
        assert result.primary_topic == "technology"

    def test_general_unknown_text(self):
        result = self.classifier.classify("أبجد هوز حطي كلمن سعفص قرشت")
        assert result.primary_topic == "general"
        assert result.confidence == 0.0

    def test_empty_text(self):
        result = self.classifier.classify("")
        assert result.primary_topic == "general"
        assert result.primary_score == 0.0

    def test_whitespace_text(self):
        result = self.classifier.classify("   ")
        assert result.primary_topic == "general"

    def test_confidence_gap_semantics(self):
        result = self.classifier.classify("اللاعب هداف الفريق في البطولة")
        assert 0.0 <= result.confidence <= 1.0

    def test_top_topics_limited(self):
        result = self.classifier.classify("اللاعب هداف الفريق")
        assert len(result.top_topics) <= 3

    def test_batch_classification(self):
        results = self.classifier.classify_batch(["هدف رائع في المباراة", "الحكم أصدر قرار المحكمة"])
        topics = [r.primary_topic for r in results]
        assert "sport" in topics
        assert "legal" in topics

    def test_distribution(self):
        dist = self.classifier.distribution(["هدف في المباراة", "حكم المحكمة أصدر الحكم"])
        assert dist["sport"] >= 1
        assert dist["legal"] >= 1

    def test_add_terms_unknown_topic_raises(self):
        with pytest.raises(ValueError):
            self.classifier.add_terms("nonexistent_topic_xyz", ["term"])

    def test_add_terms_changes_classification(self):
        from aranorm.analysis.topic_classifier import TopicClassifier

        cls = TopicClassifier()
        cls.add_terms("legal", ["قلم", "دفتر"])
        result = cls.classify("اشتريت قلم ودفتر جديدين")
        assert result.primary_topic == "legal"

    def test_to_dict_json(self):
        result = self.classifier.classify("حكم المحكمة")
        payload = result.to_dict()
        assert "primary_topic" in payload
        assert isinstance(json.loads(result.to_json()), dict)


# =====================================================================
# PronounAnalyzer
# =====================================================================


class TestPronounAnalyzer:
    @pytest.fixture(autouse=True)
    def setup(self):
        from aranorm.analysis.pronoun_analyzer import PronounAnalyzer

        self.analyzer = PronounAnalyzer()

    def test_suffix_pronouns(self):
        result = self.analyzer.analyze("كتبناها")
        assert result.stem == "كتب"
        assert result.suffixes == ["ها", "نا"]
        assert result.has_pronoun is True
        assert result.is_simple is False

    def test_simple_word(self):
        result = self.analyzer.analyze("كتاب")
        assert result.has_pronoun is False
        assert result.is_simple is True

    def test_prefix_and_suffix(self):
        result = self.analyzer.analyze("فكتبوها")
        assert any(s.role == "prefix" for s in result.segments)
        assert any(s.role == "suffix" for s in result.segments)
        assert result.has_pronoun is True

    def test_segments_roles(self):
        result = self.analyzer.analyze("كتابها")
        roles = [s.role for s in result.segments]
        assert "stem" in roles

    def test_non_arabic_token(self):
        result = self.analyzer.analyze("hello123")
        assert not result.has_pronoun
        assert result.stem == "hello123"

    def test_prefix_bare_preposition_rejected(self):
        # bare ب attaches only to definite nouns; 'بكتب' (undefined) must keep ب as stem
        result = self.analyzer.analyze("بكتب")
        assert result.has_pronoun is False

    def test_prefix_definite_noun_recorded(self):
        # 'بالكتاب' records the definite ب+ال prefix segment even though it
        # is a preposition rather than a personal pronoun
        result = self.analyzer.analyze("بالكتاب")
        assert result.prefixes == ["بال"]
        assert result.stem == "كتاب"

    def test_has_pronoun_requires_pronoun_role(self):
        result = self.analyzer.analyze("كتبناها")
        assert result.has_pronoun is True
        assert result.pronoun_role != ""

    def test_definite_preposition_prefix(self):
        # prefixes in _DEFINITE_PREPOSITIONS attach to definite stems
        result = self.analyzer.analyze("للكتاب")
        assert result.prefixes == ["لل"]
        assert result.stem == "كتاب"

    def test_future_prefix_with_min_length(self):
        from aranorm.analysis.pronoun_analyzer import PronounAnalyzer

        result = PronounAnalyzer(min_stem_length=3).analyze("ستدرس")
        assert "ست" in result.prefixes
        assert result.stem == "درس"

    def test_future_prefix_rejected_short_stem(self):
        from aranorm.analysis.pronoun_analyzer import PronounAnalyzer

        result = PronounAnalyzer(min_stem_length=5).analyze("ستدرس")
        assert result.has_pronoun is False

    def test_prefix_bare_preposition_definite(self):
        result = self.analyzer.analyze("بالكتاب")
        assert result.prefixes == ["بال"]
        assert result.stem == "كتاب"

    def test_short_token_stops_decomposition(self):
        # 2-char tokens cannot split into prefix+stem with min length
        result = self.analyzer.analyze("في")
        assert isinstance(result.has_pronoun, bool)

    def test_pronoun_statistics_by_role(self):
        stats = self.analyzer.pronoun_statistics(["كتبناها", "أعطوني", "كتاب"])
        assert stats["tokens_with_pronouns"] >= 2
        assert stats["by_role"]

    def test_analyze_tokens(self):
        results = self.analyzer.analyze_tokens(["كتبناها", "كتاب"])
        assert len(results) == 2
        assert results[0].has_pronoun and not results[1].has_pronoun

    def test_pronoun_statistics(self):
        stats = self.analyzer.pronoun_statistics(["كتبناها", "كتاب", "قرأوها"])
        assert stats["total_tokens"] >= 2
        assert 0.0 <= stats["pronoun_ratio"] <= 1.0

    def test_pronoun_statistics_empty(self):
        stats = self.analyzer.pronoun_statistics([])
        assert stats["pronoun_ratio"] == 0.0

    def test_to_dict_json(self):
        result = self.analyzer.analyze("كتبناها")
        assert json.loads(result.to_json())["stem"] == "كتب"


# =====================================================================
# IdiomAnalyzer
# =====================================================================


class TestIdiomAnalyzer:
    @pytest.fixture(autouse=True)
    def setup(self):
        from aranorm.analysis.idiom_analyzer import IdiomAnalyzer

        self.analyzer = IdiomAnalyzer()

    def test_built_in_idiom_detected(self):
        result = self.analyzer.analyze("ان شاء الله ننجح")
        canonicals = {s.canonical for s in result.idioms}
        assert "إن شاء الله" in canonicals

    def test_idiom_without_hamza_misspelling(self):
        result = self.analyzer.analyze("الحمدلله على السلامة")
        canonicals = {s.canonical for s in result.idioms}
        assert "الحمد لله" in canonicals

    def test_multiple_idioms(self):
        result = self.analyzer.analyze("إن شاء الله سنجتمع في الحال لنناقش الأمر على أي حال")
        assert result.idiom_count >= 2
        assert len(result.unique_idioms) >= 2

    def test_exact_offsets(self):
        text = "سنجتمع في الحال"
        result = self.analyzer.analyze(text)
        for span in result.idioms:
            assert text[span.start : span.end] == span.text

    def test_offsets_ignore_diacritics(self):
        text = "إنْ شاءَ اللهُ نذهب"
        result = self.analyzer.analyze(text)
        # spans may span diacritics; the covered slice must contain the canonical
        assert result.idiom_count >= 1
        for span in result.idioms:
            covered = text[span.start : span.end]
            assert "شاء" in covered or "الله" in covered

    def test_by_category(self):
        result = self.analyzer.analyze("إن شاء الله ما شاء الله")
        assert "دعاء" in result.by_category
        assert "إعجاب" in result.by_category

    def test_empty_text(self):
        result = self.analyzer.analyze("")
        assert result.idiom_count == 0

    def test_empty_after_strip(self):
        result = self.analyzer.analyze("   ")
        assert result.idiom_count == 0

    def test_no_false_positive_regular_words(self):
        result = self.analyzer.analyze("ذهب الولد إلى السوق واشترى خبزا")
        assert result.idiom_count == 0

    def test_add_idiom_runtime(self):
        self.analyzer.add_idiom("على الخير", "تمني", ["على الخير"])
        result = self.analyzer.analyze("الله يوفقك على الخير")
        canonicals = {s.canonical for s in result.idioms}
        assert "على الخير" in canonicals

    def test_custom_idioms_via_constructor(self):
        from aranorm.analysis.idiom_analyzer import IdiomAnalyzer

        custom = IdiomAnalyzer(idioms={"تحت عينه": ("مراقبة", ["تحت عينه"])})
        result = custom.analyze("المدير يراقبنا تحت عينه")
        assert any(s.canonical == "تحت عينه" for s in result.idioms)

    def test_batch_analysis(self):
        results = self.analyzer.analyze_batch(["ان شاء الله", "لا سيما في الصيف"])
        assert len(results) == 2
        assert results[0].idiom_count == 1
        assert results[1].idiom_count == 1

    def test_idiom_result_to_dict_and_json(self):
        result = self.analyzer.analyze("في الحال ذهبت للعمل")
        payload = result.to_dict()
        assert payload["idiom_count"] >= 1
        assert payload["idioms"][0]["text"] == "في الحال"
        round_tripped = json.loads(result.to_json())
        assert round_tripped["by_category"] is not None

    def test_is_idiom_covered(self):
        text = "ان شاء الله ننجح"
        covered = self.analyzer.is_idiom_covered(0, 11, text)
        assert covered is True
        # a span outside the idiom should not be covered
        far = self.analyzer.is_idiom_covered(11, 20, text)
        assert far is False

    def test_idiom_words_suppression_set(self):
        text = "ان شاء الله"
        words = self.analyzer.idiom_words(text)
        assert len(words) == len(text)

    def test_canonical_forms_list(self):
        forms = self.analyzer.canonical_forms
        assert "إن شاء الله" in forms


# =====================================================================
# PipelineSnapshot
# =====================================================================


class TestPipelineSnapshot:
    def test_snapshot_roundtrip(self, tmp_path):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        config = PipelineConfig(preset="standard")
        snapshot = snapshot_pipeline(config, stage_order=["normalize", "diacritics"])
        path = str(tmp_path / "snap.json")
        saved = snapshot.save(path)
        assert os.path.isfile(saved)

        loaded = snapshot.__class__.load(path)
        assert loaded == snapshot
        assert loaded.aranorm_version == snapshot.aranorm_version

    def test_from_json(self):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        snapshot = snapshot_pipeline(PipelineConfig(preset="standard"))
        text = snapshot.to_json()
        parsed = snapshot.from_json(text)
        assert parsed.config == snapshot.config

    def test_from_dict_validation(self):
        from aranorm.core.snapshot import PipelineSnapshot

        with pytest.raises(TypeError):
            PipelineSnapshot.from_dict("not a dict")  # type: ignore[arg-type]

    def test_diff_different_presets(self):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        a = snapshot_pipeline(PipelineConfig(preset="standard"))
        b = snapshot_pipeline(PipelineConfig(preset="light"))
        diff = a.diff(b)
        assert "config_changes" in diff
        assert diff["config_changes"]
        assert diff["version_mismatch"] is False

    def test_diff_identical(self):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        a = snapshot_pipeline(PipelineConfig(preset="standard"))
        b = snapshot_pipeline(PipelineConfig(preset="standard"))
        diff = a.diff(b)
        assert not diff["config_changes"]

    def test_stage_order_changes(self):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        a = snapshot_pipeline(PipelineConfig(preset="standard"), stage_order=["a"])
        b = snapshot_pipeline(PipelineConfig(preset="standard"), stage_order=["b"])
        diff = a.diff(b)
        assert diff["stage_order_changes"] is not None

    def test_metadata(self):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        snapshot = snapshot_pipeline(PipelineConfig(preset="standard"), metadata={"author": "aranorm"})
        assert snapshot.metadata.get("author") == "aranorm"
        payload = snapshot.to_dict()
        assert payload["metadata"]["author"] == "aranorm"

    def test_load_missing_file(self):
        from aranorm.core.snapshot import PipelineSnapshot

        with pytest.raises(FileNotFoundError):
            PipelineSnapshot.load("/tmp/nonexistent_snapshot_xyz.json")

    def test_from_json_invalid(self):
        from aranorm.core.snapshot import PipelineSnapshot

        with pytest.raises(ValueError):
            PipelineSnapshot.from_json("{invalid json")

    def test_equality_non_snapshot(self):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        snapshot = snapshot_pipeline(PipelineConfig(preset="standard"))
        assert snapshot.__eq__("string") is NotImplemented


# =====================================================================
# Spelling idiom-exclusion integration
# =====================================================================


class TestSpellingIdiomExclusion:
    def _flagged_words(self, text: str) -> List[str]:
        from aranorm.analysis.spelling_report import SpellingAnalyzer

        report = SpellingAnalyzer().analyze(text)
        return [c.word for c in report.corrections]

    def test_idiom_words_not_flagged(self):
        flagged = self._flagged_words("ان شاء الله سنحقق الهدف ان شاء الله")
        assert "ان" not in flagged, "idiom words must be suppressed from spelling issues"

    def test_genuine_errors_still_flagged(self):
        flagged = self._flagged_words("الكلمة الاعلان خطأ")
        assert "الاعلان" in flagged

    def test_spelling_report_interface(self):
        from aranorm.analysis.spelling_report import SpellingAnalyzer

        report = SpellingAnalyzer().analyze("ان شاء الله")
        payload = report.to_dict()
        assert "corrections" in payload
        assert "correct_ratio" in payload


# =====================================================================
# CLI commands
# =====================================================================


class TestRound18CLI:
    def _run(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(CLI + args, capture_output=True, text=True)

    def test_entities_json(self):
        run = _run_cli(["entities", "--json", "زار محمد وخالد الرياض"])
        assert run.returncode == 0
        payload = json.loads(run.stdout)
        assert payload["entity_count"] >= 2

    def test_entities_file(self, tmp_path):
        file = tmp_path / "text.txt"
        file.write_text("محمد في القاهرة", encoding="utf-8")
        run = _run_cli(["entities", "--file", str(file)])
        assert run.returncode == 0
        assert "location" in run.stdout.lower() or "القاهرة" in run.stdout

    def test_entities_missing_file(self):
        run = _run_cli(["entities", "--file", "/tmp/missing_xyz.txt"])
        assert run.returncode == 1
        assert "Error" in run.stderr or "error" in run.stderr

    def test_topics_text(self):
        run = _run_cli(["topics", "حكم المحكمة اليوم"])
        assert run.returncode == 0
        assert "legal" in run.stdout

    def test_topics_json(self):
        run = _run_cli(["topics", "--json", "اللاعب سجل هدفا"])
        assert run.returncode == 0
        payload = json.loads(run.stdout)
        assert payload["primary_topic"] == "sport"

    def test_pronouns_word(self):
        run = _run_cli(["pronouns", "كتبناها"])
        assert run.returncode == 0
        assert "كتب" in run.stdout or "stem" in run.stdout

    def test_pronouns_json(self):
        run = _run_cli(["pronouns", "--json", "كتبناها"])
        assert run.returncode == 0
        payload = json.loads(run.stdout)
        assert payload[0]["stem"] == "كتب"

    def test_pronouns_file(self, tmp_path):
        file = tmp_path / "tokens.txt"
        file.write_text("كتبناها\nكتاب\n", encoding="utf-8")
        run = _run_cli(["pronouns", "--file", str(file)])
        assert run.returncode == 0
        assert run.stdout.count("stem") >= 2

    def test_idioms_text(self):
        run = _run_cli(["idioms", "ان شاء الله ما شاء الله"])
        assert run.returncode == 0
        assert "2" in run.stdout

    def test_idioms_json(self):
        run = _run_cli(["idioms", "--json", "في الحال سنذهب"])
        assert run.returncode == 0
        payload = json.loads(run.stdout)
        assert payload["idiom_count"] >= 1

    def test_snapshot_save_restore(self, tmp_path):
        path = str(tmp_path / "snap.json")
        save = _run_cli(["snapshot", "save", "--output", path])
        assert save.returncode == 0
        assert os.path.isfile(path)

        restore = _run_cli(["snapshot", "restore", "--input", path])
        assert restore.returncode == 0
        assert "standard" in restore.stdout

    def test_snapshot_save_json(self, tmp_path):
        path = str(tmp_path / "snap.json")
        save = _run_cli(["snapshot", "save", "--output", path, "--json"])
        assert save.returncode == 0
        assert "config" in save.stdout or os.path.isfile(path)

    def test_snapshot_restore_json(self, tmp_path):
        path = str(tmp_path / "snap.json")
        _run_cli(["snapshot", "save", "--output", path])
        restore = _run_cli(["snapshot", "restore", "--input", path, "--json"])
        assert restore.returncode == 0
        payload = json.loads(restore.stdout)
        assert "schema_version" in payload

    def test_snapshot_restore_missing(self):
        run = _run_cli(["snapshot", "restore", "--input", "/tmp/missing_xyz.json"])
        assert run.returncode == 1
        assert "Error" in run.stderr

    def test_snapshot_inferred_stage_order(self):
        from aranorm import PipelineConfig
        from aranorm.core.snapshot import snapshot_pipeline

        config = PipelineConfig(preset="standard")
        snap = snapshot_pipeline(config)
        assert isinstance(snap.stage_order, list)

    def test_snapshot_no_subcommand(self):
        run = _run_cli(["snapshot"])
        assert run.returncode >= 1

    def test_help_lists_new_commands(self):
        run = _run_cli(["--help"])
        assert run.returncode == 0
        for command in ("entities", "topics", "pronouns", "idioms", "snapshot"):
            assert command in run.stdout
