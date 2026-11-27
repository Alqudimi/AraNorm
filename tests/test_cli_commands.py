"""End-to-end coverage for the remaining CLI commands."""

from __future__ import annotations

import json

import aranorm.cli as cli
from aranorm.cli import main


def _json_output(capsys):
    return json.loads(capsys.readouterr().out)


def test_dialect_json_output(capsys) -> None:
    assert main(["dialect", "--json", "شلونك وايد زين"]) == 0
    payload = _json_output(capsys)
    assert {"dialect", "confidence", "is_msa"} <= payload.keys()


def test_keywords_json_output(capsys) -> None:
    assert main(["keywords", "--json", "الاقتصاد العالمي الاقتصاد العربي", "--top-n", "2"]) == 0
    payload = _json_output(capsys)
    assert len(payload) == 1
    assert payload[0]["keyword_count"] <= 2


def test_compare_json_output(capsys) -> None:
    assert main(["compare", "--json", "أنا أحب العربية", "أنا أعشق العربية"]) == 0
    payload = _json_output(capsys)
    assert "overall_similarity" in payload
    assert 0.0 <= payload["overall_similarity"] <= 1.0


def test_tokenize_words_and_sentences_json(capsys) -> None:
    assert main(["tokenize", "--json", "أهلاً بكم. كيف حالكم؟"]) == 0
    words = _json_output(capsys)
    assert isinstance(words, list)
    assert words

    assert main(["tokenize", "--sentences", "--json", "أهلاً بكم. كيف حالكم؟"]) == 0
    sentences = _json_output(capsys)
    assert sentences[0]["index"] == 0
    assert len(sentences) == 2


def test_sentiment_json_output(capsys) -> None:
    assert main(["sentiment", "--json", "هذا المنتج رائع وممتاز"]) == 0
    payload = _json_output(capsys)
    assert len(payload) == 1
    assert {"label", "score", "confidence"} <= payload[0].keys()


def test_version_readability_and_detect(capsys) -> None:
    assert main(["version"]) == 0
    assert "aranorm" in capsys.readouterr().out

    assert main(["readability", "--json", "هذا نص عربي واضح ومفيد"]) == 0
    readability = _json_output(capsys)
    assert "long_word_ratio" in readability

    assert main(["detect", "--json", "hello world"]) == 0
    detected = _json_output(capsys)
    assert detected["label"]


def test_summarize_json_and_file_input(tmp_path, capsys) -> None:
    text = "الجامعة تطلق برنامجاً جديداً. يركز البرنامج على البحث العلمي. تبدأ المرحلة الأولى قريباً."
    assert main(["summarize", "--json", "--max-sentences", "2", text]) == 0
    payload = _json_output(capsys)
    assert payload["summary_sentences"] <= 2
    assert payload["summary"]

    input_path = tmp_path / "article.txt"
    input_path.write_text(text, encoding="utf-8")
    assert main(["summarize", "--file", str(input_path), "--max-sentences", "1"]) == 0
    assert "Summary:" in capsys.readouterr().out


def test_corpus_json_output(tmp_path, capsys) -> None:
    input_path = tmp_path / "corpus.txt"
    input_path.write_text("هذا نص أول\nوهذا نص ثانٍ عن البحث\n", encoding="utf-8")

    assert main(["corpus", "--file", str(input_path), "--json", "--top-n", "3"]) == 0
    payload = _json_output(capsys)
    assert payload["document_count"] == 2
    assert "top_content_words" in payload


def test_file_based_commands_report_missing_files(capsys) -> None:
    missing = "/tmp/aranorm-definitely-missing-input.txt"
    assert main(["keywords", "--file", missing]) == 1
    assert main(["tokenize", "--file", missing]) == 1
    assert main(["sentiment", "--file", missing]) == 1
    assert main(["summarize", "--file", missing]) == 1
    assert main(["corpus", "--file", missing]) == 1
    assert capsys.readouterr().err.count("file not found") >= 5


def test_main_maps_unexpected_exception_to_error(monkeypatch, capsys) -> None:
    def fail(_args):
        raise RuntimeError("intentional test failure")

    monkeypatch.setattr(cli, "_cmd_info", fail)
    assert main(["info"]) == 1
    assert "intentional test failure" in capsys.readouterr().err


def test_main_maps_keyboard_interrupt_to_130(monkeypatch) -> None:
    def interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_cmd_info", interrupt)
    assert main(["info"]) == 130
