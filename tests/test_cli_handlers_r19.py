"""Round 19 — direct CLI handler tests for `freqprofile` and `coherence`.

Handlers are invoked in-process (like the Round 18 suite) so their code
runs inside the coverage collector. A matching subprocess pass exercises
the full argparse plumbing in a separate test module.
"""

import argparse
import io
import json
import sys
from unittest import mock

from aranorm.cli import _cmd_coherence, _cmd_freqprofile


def _namespace(**overrides):
    defaults = {
        "text": None,
        "file": None,
        "json": False,
        "top_n": 10,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ── freqprofile ───────────────────────────────────────────────────────────────


class TestFreqprofileHandler:
    """freqprofile command handler."""

    def test_freqprofile_text_mode(self, capsys):
        exit_code = _cmd_freqprofile(_namespace(text="العلم نور والعلم نور"))
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "total_tokens" in out or "العلم" in out

    def test_freqprofile_json_mode(self, capsys):
        exit_code = _cmd_freqprofile(
            _namespace(text="العلم نور والعلم نور", json=True),
        )
        assert exit_code == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["total_tokens"] == 4
        assert parsed["unique_types"] == 3  # "العلم", "نور", and the waw-clitic token

    def test_freqprofile_custom_top_n(self, capsys):
        exit_code = _cmd_freqprofile(
            _namespace(text="مدرسة جامعة مكتبة متحف حديقة", json=True, top_n=2),
        )
        assert exit_code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed["frequency_table"]) == 2
        assert parsed["top_n"] == 2

    def test_freqprofile_file_mode(self, tmp_path, capsys):
        path = tmp_path / "input.txt"
        path.write_text("التقنية تطور الاقتصاد")
        exit_code = _cmd_freqprofile(_namespace(file=str(path), json=True))
        assert exit_code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["total_tokens"] >= 1

    def test_freqprofile_missing_file(self, capsys):
        exit_code = _cmd_freqprofile(_namespace(file="/no/such/file.txt"))
        assert exit_code == 1

    def test_freqprofile_stdin_fallback(self, capsys):
        stdin = io.StringIO("نص من المدخل القياسي")
        with mock.patch.object(sys, "stdin", stdin):
            exit_code = _cmd_freqprofile(_namespace(text=None, file=None, json=True))
        assert exit_code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["total_tokens"] >= 1


# ── coherence ─────────────────────────────────────────────────────────────────


class TestCoherenceHandler:
    """coherence command handler."""

    def test_coherence_text_mode(self, capsys):
        exit_code = _cmd_coherence(_namespace(text="جملة واحدة هنا."))
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "score" in out or "fragmented" in out or "1" in out

    def test_coherence_json_mode(self, capsys):
        exit_code = _cmd_coherence(
            _namespace(
                text="افتتح الاجتماع. ثم ناقش الحضور. لذلك صدر القرار.",
                json=True,
            ),
        )
        assert exit_code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert 0.0 <= parsed["score"] <= 1.0
        assert parsed["label"] in {"strong", "moderate", "weak", "fragmented"}

    def test_coherence_file_mode(self, tmp_path, capsys):
        path = tmp_path / "doc.txt"
        path.write_text("جملة واحدة من ملف.")
        exit_code = _cmd_coherence(_namespace(file=str(path), json=True))
        assert exit_code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert "score" in parsed

    def test_coherence_missing_file(self, capsys):
        exit_code = _cmd_coherence(_namespace(file="/no/such/file.txt"))
        assert exit_code == 1

    def test_coherence_short_input(self, capsys):
        # An empty ``text`` falls through to the stdin branch, which would hang
        # under pytest capture; short non-empty input keeps the test in-process.
        exit_code = _cmd_coherence(_namespace(text=".", json=True))
        assert exit_code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert 0.0 <= parsed["score"] <= 1.0
