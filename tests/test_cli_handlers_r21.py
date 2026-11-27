"""Round 21 CLI handler tests: rhythm, figurate, numbers sub-commands."""

import argparse
import json
from unittest import mock

import pytest

from aranorm.cli import _cmd_figurate, _cmd_numbers, _cmd_rhythm, main


def _namespace(**overrides):
    defaults = {
        "text": None,
        "file": None,
        "json": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestRhythmHandler:
    def test_saj_print(self, capsys) -> None:
        assert _cmd_rhythm(_namespace(text="يعملون، ويكملون")) == 0
        output = capsys.readouterr().out
        assert "saj" in output.lower() or "مل" in output

    def test_flat_print(self, capsys) -> None:
        assert _cmd_rhythm(_namespace(text="هذا نص عربي عادي بدون أي تقسيم")) == 0
        assert "flat" in capsys.readouterr().out

    def test_json_output(self, capsys) -> None:
        assert _cmd_rhythm(_namespace(text="يعملون، ويكملون", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["label"] == "rhythmic"
        assert payload["saj_signals"] >= 1
        assert "saj_pairs" in payload

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "rhythm.txt"
        file_path.write_text("يعملون، ويكملون", encoding="utf-8")
        assert _cmd_rhythm(_namespace(file=str(file_path))) == 0
        assert "rhythmic" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_rhythm(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err

    def test_stdin_fallback(self, capsys) -> None:
        with mock.patch("sys.stdin", mock.MagicMock(read=lambda: "يعملون، ويكملون")):
            assert _cmd_rhythm(_namespace(text="")) == 0
        assert "rhythmic" in capsys.readouterr().out

    def test_stdin_empty_line(self, capsys) -> None:
        """An empty stdin (no text at all) still yields a flat result without error."""
        with mock.patch("sys.stdin", mock.MagicMock(read=lambda: "")):
            assert _cmd_rhythm(_namespace(text="")) == 0
        assert "flat" in capsys.readouterr().out


class TestFigurateHandler:
    def test_simile_print(self, capsys) -> None:
        assert _cmd_figurate(_namespace(text="الصبر كنز كما هو نور")) == 0
        output = capsys.readouterr().out
        assert "tashbih" in output or "simile" in output.lower()

    def test_plain_print(self, capsys) -> None:
        assert _cmd_figurate(_namespace(text="ذهبت إلى السوق")) == 0
        assert "plain" in capsys.readouterr().out

    def test_json_output(self, capsys) -> None:
        assert _cmd_figurate(_namespace(text="الصبر كنز كما هو نور", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["label"] in ("rich", "moderate", "plain")
        assert payload["simile_count"] >= 1
        assert "occurrences" in payload

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "figurate.txt"
        file_path.write_text("الصبر الصبر الصبر مفتاح الفرج", encoding="utf-8")
        assert _cmd_figurate(_namespace(file=str(file_path))) == 0
        assert "takrir" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_figurate(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err


class TestNumbersHandler:
    def test_indic_print(self, capsys) -> None:
        assert _cmd_numbers(_namespace(text="الحرارة ٢٥ درجة")) == 0
        output = capsys.readouterr().out
        assert "٢٥" in output

    def test_mixed_system_print(self, capsys) -> None:
        assert _cmd_numbers(_namespace(text="حققنا 25% أي ٢٥ بالمئة")) == 0
        assert "True" in capsys.readouterr().out

    def test_json_output(self, capsys) -> None:
        assert _cmd_numbers(_namespace(text="١٢٣ ريال و 25%", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["arabic_indic_count"] >= 1
        assert payload["western_count"] >= 1
        assert payload["digit_system_mix"] is True
        assert "spans" in payload

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "numbers.txt"
        file_path.write_text("خمسمائة دولار و 50%", encoding="utf-8")
        assert _cmd_numbers(_namespace(file=str(file_path))) == 0
        assert "currency" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_numbers(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err

    def test_stdin_fallback(self, capsys) -> None:
        with mock.patch("sys.stdin", mock.MagicMock(read=lambda: "٩٩ بالمئة")):
            assert _cmd_numbers(_namespace(text="")) == 0
        assert "٩٩" in capsys.readouterr().out


class TestR21CommandDispatch:
    """Ensure the three new commands are reachable through the main dispatcher."""

    @pytest.mark.parametrize(
        ("command", "text", "expect"),
        [
            ("rhythm", "يعملون، ويكملون", "rhythmic"),
            ("figurate", "الصبر كنز كما هو نور", "tashbih"),
            ("numbers", "٢٥ بالمئة", "٢٥"),
        ],
    )
    def test_dispatch(self, capsys, command, text, expect) -> None:
        assert main([command, text]) == 0
        assert expect in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("command", "text"),
        [
            ("rhythm", "يعملون، ويكملون"),
            ("figurate", "الصبر كنز"),
            ("numbers", "٢٥"),
        ],
    )
    def test_dispatch_json(self, capsys, command, text) -> None:
        assert main([command, text, "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, dict)

    def test_help_lists_new_commands(self) -> None:
        """A top-level help failure must not happen (regression guard)."""
        with pytest.raises(SystemExit) as error:
            main(["--help"])
        assert error.value.code == 0
