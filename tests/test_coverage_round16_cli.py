"""Round 16 P0 — CLI coverage hardening.

Closes the remaining untested output/error branches of ``aranorm.cli``:
keyword analysis, compare (both paths), tokenize modes, sentiment,
readability, summarize (empty input), detect, corpus, spec (validate /
no-subcommand), stream status (cancelled), and the ``serve`` sub-command
with its streaming flags — all invoked through the real ``main()`` so the
entire argparse-to-handler wiring is exercised end to end.
"""

from __future__ import annotations

import contextlib
import json
import sys
import typing
from unittest import mock

import pytest

from aranorm.cli import main


@contextlib.contextmanager
def _fake_server_module() -> "typing.Iterator[mock.MagicMock]":
    """Replace the ``aranorm.server`` module with a fake whose ``serve`` is mocked."""
    serve_mock = mock.MagicMock()
    fake_server = mock.MagicMock()
    fake_server.serve = serve_mock
    with mock.patch.dict(sys.modules, {"aranorm.server": fake_server}, clear=False):  # type: ignore[arg-type]
        yield serve_mock


TEXT_A = "هذه جملة أولى للتجربة والتجربة"
TEXT_B = "هذه جملة ثانية للتجربة أيضا"
LONG_TEXT = (
    "إنّ التطور التكنولوجي المعاصر يفرض تحديات جمة على منظومة التعليم في "
    "الدول النامية. فالمؤسسات الأكاديمية مطالبة بإعادة هندسة برامجها الدراسية "
    "بشكل جذري لتواكب مستجدات العصر الرقمي. ومع ذلك فإنّ الموارد المحدودة "
    "والفجوة الرقمية واسعة الانتشار تعيقان هذا التحول المنشود."
)


@pytest.fixture()
def corpus_file(tmp_path):
    path = tmp_path / "corpus.txt"
    path.write_text(
        "أحببت اللغة العربية كثيرا\n" "اللغة العربية لغة جميلة وسهلة\n" "في اللغة العربية قواعد نحوية مهمة\n",
        encoding="utf-8",
    )
    return path


# ── keywords ────────────────────────────────────────────────────────────────


def test_cli_keywords_prints_preview_and_keywords(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["keywords", "اللغة العربية هي لغة الحب والإبداع والإبداع"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Text    :" in out
    assert "Keywords:" in out


def test_cli_keywords_from_file(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "in.txt"
    path.write_text("التكنولوجيا تتطور والتطور يتسارع", encoding="utf-8")
    rc = main(["keywords", "--file", str(path)])
    assert rc == 0
    assert "Keywords:" in capsys.readouterr().out


# ── compare ─────────────────────────────────────────────────────────────────


def test_cli_compare_prints_verdict_and_shared_words(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["compare", TEXT_A, TEXT_B])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Text A    :" in out
    assert "Text B    :" in out
    assert "Verdict   :" in out
    assert "Overall   :" in out
    assert "Jaccard   :" in out
    assert "Content   :" in out


def test_cli_compare_from_files(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    fa = tmp_path / "a.txt"
    fb = tmp_path / "b.txt"
    fa.write_text(TEXT_A, encoding="utf-8")
    fb.write_text(TEXT_B, encoding="utf-8")
    rc = main(["compare", fa.read_text(encoding="utf-8"), fb.read_text(encoding="utf-8")])
    assert rc == 0
    assert "Shared KW :" in capsys.readouterr().out


def test_cli_compare_no_shared_content_words(capsys: pytest.CaptureFixture[str]) -> None:
    # Disjoint vocabularies exercise the branch that hides the shared-kw line.
    rc = main(["compare", "شمس قمر", "كرة قدم"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Verdict" in out
    assert "Shared KW" not in out


# ── tokenize ────────────────────────────────────────────────────────────────


def test_cli_tokenize_sentences(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["tokenize", "--sentences", "جملة أولى. جملة ثانية."])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[0]" in out
    assert "[1]" in out


def test_cli_tokenize_words_default(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["tokenize", "كلمة واحدة"])
    assert rc == 0
    out = capsys.readouterr().out
    assert " | " in out


# ── sentiment ───────────────────────────────────────────────────────────────


def test_cli_sentiment_prints_report(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["sentiment", "هذا المنتج رائع جدا وممتاز"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Sentiment :" in out
    assert "Score     :" in out


def test_cli_sentiment_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["sentiment", "--file", "/nonexistent/sent.txt"])
    assert rc == 1
    assert "file not found" in capsys.readouterr().err


def test_cli_sentiment_shows_words(capsys: pytest.CaptureFixture[str]) -> None:
    # A strongly polar text is likely to surface positive/negative word lists.
    rc = main(["sentiment", "جميل رائع ممتاز سيئ رديء فظيع"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Sentiment" in out


# ── readability ─────────────────────────────────────────────────────────────


def test_cli_readability_prints_scores(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["readability", LONG_TEXT])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Readability   :" in out
    assert "Avg sent len  :" in out
    assert "Complexity    :" in out


# ── summarize ───────────────────────────────────────────────────────────────


def test_cli_summarize_no_text_returns_error(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("   "))
    rc = main(["summarize"])
    assert rc == 1
    assert "no text provided" in capsys.readouterr().err


def test_cli_summarize_from_stdin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(LONG_TEXT + "\n" + TEXT_A))
    rc = main(["summarize"])
    assert rc == 0
    assert capsys.readouterr().out.strip() != ""


# ── detect ──────────────────────────────────────────────────────────────────


def test_cli_detect_prints_ratios(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["detect", "اللغة العربية جميلة"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Label     :" in out
    assert "Arabic    :" in out
    assert "Arabizi   :" in out


def test_cli_detect_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["detect", "--file", "/nonexistent/det.txt"])
    assert "file" in capsys.readouterr().err.lower()


# ── corpus ──────────────────────────────────────────────────────────────────


def test_cli_corpus_prints_summary(corpus_file, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["corpus", "--file", str(corpus_file)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Documents          :" in out
    assert "Stop-word ratio    :" in out
    assert "Lexical diversity  :" in out
    assert "Top 10 content words:" in out
    assert "Top stop words:" in out


def test_cli_corpus_json(corpus_file, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["corpus", "--json", "--file", str(corpus_file)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["document_count"] == 3


def test_cli_corpus_file_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["corpus", "--file", "/nonexistent/corpus.txt"])
    assert rc == 1
    assert "file not found" in capsys.readouterr().err


def test_cli_corpus_empty_file(tmp_path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    rc = main(["corpus", "--file", str(path)])
    assert rc == 1


# ── spec ────────────────────────────────────────────────────────────────────


def test_cli_spec_validate_prints_fingerprint(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_path = tmp_path / "spec.json"
    rc = main(["spec", "export", "--preset", "light", "--output", str(spec_path)])
    assert rc == 0
    rc = main(["spec", "validate", str(spec_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Valid PipelineSpec" in out
    assert "Schema version" in out
    assert "Config fingerprint" in out


def test_cli_spec_no_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["spec"])
    assert "spec_command" in capsys.readouterr().err


def test_cli_spec_validate_invalid_file(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "99.0"}', encoding="utf-8")
    rc = main(["spec", "validate", str(bad)])
    assert rc == 1


# ── serve ───────────────────────────────────────────────────────────────────


def test_cli_serve_streaming_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with _fake_server_module() as serve_mock:
        rc = main(["serve", "--streaming-enabled", "--streaming-root", "/tmp/aranorm-stream"])
        assert rc == 0
        assert serve_mock.call_args.kwargs.get("streaming_enabled") is True
        assert serve_mock.call_args.kwargs.get("streaming_root") == "/tmp/aranorm-stream"


def test_cli_serve_streaming_root_without_enabled(capsys: pytest.CaptureFixture[str]) -> None:
    with _fake_server_module():
        rc = main(["serve", "--streaming-root", "/tmp/x"])
        assert rc == 1
        assert "requires --streaming-enabled" in capsys.readouterr().err


def test_cli_serve_config_and_spec_exclusive(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    spec_path = tmp_path / "s.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "library_version": "1.0.0",
                "pipeline_class": "Aranorm",
                "config": {},
                "config_fingerprint": "a0",
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    with _fake_server_module():
        rc = main(["serve", "--config", "/tmp/x.yaml", "--spec", str(spec_path)])
        assert rc == 1
        assert "mutually exclusive" in capsys.readouterr().err


def test_cli_serve_with_spec_file(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    spec_path = tmp_path / "spec.json"
    rc_export = main(["spec", "export", "--preset", "standard", "--output", str(spec_path)])
    assert rc_export == 0
    with _fake_server_module() as serve_mock:
        rc = main(["serve", "--spec", str(spec_path)])
        assert rc == 0
        assert serve_mock.call_args.kwargs.get("spec_path") == str(spec_path)


def test_cli_serve_missing_config_file(capsys: pytest.CaptureFixture[str]) -> None:
    with _fake_server_module():
        rc = main(["serve", "--config", "/nonexistent.yaml"])
        assert rc == 1


# ── stream / status ─────────────────────────────────────────────────────────

HEX64 = "a" * 64


def _checkpoint_json(path, completed: bool = False, next_index: int = 0) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_path": "/tmp/in.txt",
                "output_path": "/tmp/out.txt",
                "source_fingerprint": HEX64,
                "pipeline_fingerprint": HEX64,
                "next_index": next_index,
                "output_bytes": 0,
                "input_count": 0,
                "completed": completed,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_cli_stream_status_prints_report(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    checkpoint = tmp_path / "ckpt.json"
    _checkpoint_json(checkpoint, completed=True, next_index=5)
    rc = main(["stream", "status", "--checkpoint", str(checkpoint)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Output     :" in out
    assert "Completed  : yes" in out


def test_cli_stream_status_json(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    checkpoint = tmp_path / "ckpt.json"
    _checkpoint_json(checkpoint, completed=False, next_index=0)
    rc = main(["stream", "status", "--checkpoint", str(checkpoint), "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["completed"] is False


def test_cli_stream_status_invalid_checkpoint(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")
    rc = main(["stream", "status", "--checkpoint", str(path)])
    assert rc == 1
    assert "checkpoint" in capsys.readouterr().err.lower()


# ── entry point / unknown command ───────────────────────────────────────────


def test_cli_normalize_from_stdin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(" نص تجريبي \n" + "   \n"))
    rc = main(["normalize"])
    assert rc == 0
    assert capsys.readouterr().out.strip()


def test_cli_normalize_json_with_steps_trace(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("نص تجريبي"))
    rc = main(["normalize", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)


def test_cli_normalize_to_output_file(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out.txt"
    rc = main(["normalize", "نص تجريبي", "--output", str(out)])
    assert rc == 0
    assert out.read_text(encoding="utf-8").strip()
    assert capsys.readouterr().out == ""


def test_cli_normalize_output_unwritable(tmp_path) -> None:
    rc = main(["normalize", "نص", "--output", str(tmp_path / "nope" / "x.txt")])
    assert rc == 1


def test_cli_keywords_from_stdin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("هذا نص طويل جداً عن موضوع معين يتضمن كلمات كثيرة جدا"))
    rc = main(["keywords"])
    assert rc == 0


def test_cli_sentiment_from_stdin(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("سعيد جدا اليوم"))
    rc = main(["sentiment"])
    assert rc == 0


def test_cli_stopwords_prints_list(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["stopwords", "اللغة العربية لغة جميلة في اليوم"])
    assert rc == 0
    assert capsys.readouterr().out.strip()


def test_cli_stopwords_export_to_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["stopwords", "اللغة العربية لغة جميلة", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)


def test_cli_batch_stream_file_not_found() -> None:
    rc = main(["batch", "--file", "/nonexistent/batch.txt", "--stream"])
    assert rc == 1


def test_cli_batch_stream_empty_file(tmp_path) -> None:
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    rc = main(["batch", "--file", str(f), "--stream"])
    assert rc == 1


def test_cli_batch_format_csv_to_stdout(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "in.txt"
    f.write_text("نص تجريبي أول\nنص تجريبي ثانٍ\n", encoding="utf-8")
    rc = main(["batch", "--file", str(f), "--format", "csv"])
    assert rc == 0
    content = capsys.readouterr().out
    assert "normalized" in content


def test_cli_batch_to_stdout_jsonl(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "in.txt"
    f.write_text("نص تجريبي\n", encoding="utf-8")
    rc = main(["batch", "--file", str(f)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert "normalized_text" in payload


def test_cli_batch_to_output_file(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "in.txt"
    out = tmp_path / "out.jsonl"
    f.write_text("نص تجريبي\n", encoding="utf-8")
    rc = main(["batch", "--file", str(f), "--output", str(out)])
    assert rc == 0
    assert out.exists()
    assert "Wrote 1 results" in capsys.readouterr().out


def test_cli_serve_without_server_module(capsys: pytest.CaptureFixture[str]) -> None:
    with mock.patch.dict(sys.modules, {"aranorm.server": None}):  # type: ignore[arg-type]
        rc = main(["serve"])
    assert rc == 1


def test_cli_main_module_entry_point() -> None:
    """``python -m aranorm.cli`` must invoke ``main()`` and exit with its code."""
    import subprocess
    from pathlib import Path

    src_dir = str(Path(__file__).resolve().parent.parent / "src")
    result = subprocess.run(
        ["python3", "-m", "aranorm.cli"],
        capture_output=True,
        text=True,
        cwd=src_dir,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_cli_unknown_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["normalize", "text", "--not-a-flag-xyz", "1"])
    assert capsys.readouterr().err
