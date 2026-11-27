"""Round 20 CLI handler tests: style, emotions, textprofile sub-commands."""

import argparse
import json
from unittest import mock


from aranorm.cli import _cmd_emotions, _cmd_style, _cmd_textprofile


def _namespace(**overrides):
    defaults = {
        "text": None,
        "file": None,
        "json": False,
        "axes": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestStyleHandler:
    def test_informal_print(self, capsys) -> None:
        assert _cmd_style(_namespace(text="يلا حبيبي شو الجديد")) == 0
        output = capsys.readouterr().out
        assert "informal" in output
        assert "Style index" in output

    def test_json_output(self, capsys) -> None:
        assert _cmd_style(_namespace(text="يلا", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "label" in payload

    def test_formal_print(self, capsys) -> None:
        assert _cmd_style(_namespace(text="حيثما اجتمعت الإرادة")) == 0
        output = capsys.readouterr().out
        assert "style_index" in capsys.readouterr().out or "Formal" in output

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "style.txt"
        file_path.write_text("يلا حبيبي", encoding="utf-8")
        assert _cmd_style(_namespace(file=str(file_path))) == 0
        assert "informal" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_style(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err

    def test_stdin_input(self, capsys) -> None:
        with mock.patch("sys.stdin", mock.MagicMock(read=lambda: "يلا حبيبي")):
            assert _cmd_style(_namespace(text="")) == 0
        assert "informal" in capsys.readouterr().out

    def test_elongation_printed(self, capsys) -> None:
        assert _cmd_style(_namespace(text="ممتااااااز")) == 0
        assert "Elongations" in capsys.readouterr().out


class TestEmotionsHandler:
    def test_joy_print(self, capsys) -> None:
        assert _cmd_emotions(_namespace(text="سعادة كبيرة بفرحة النجاح")) == 0
        output = capsys.readouterr().out
        assert "joy" in output

    def test_fear_print(self, capsys) -> None:
        assert _cmd_emotions(_namespace(text="خوف وذعر ورهبة")) == 0
        assert "fear" in capsys.readouterr().out

    def test_json_output(self, capsys) -> None:
        assert _cmd_emotions(_namespace(text="حزن وبكاء", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["dominant_emotion"] == "sadness"

    def test_matched_words_printed(self, capsys) -> None:
        assert _cmd_emotions(_namespace(text="سعادة")) == 0
        assert "Matched words" in capsys.readouterr().out

    def test_neutral_print(self, capsys) -> None:
        assert _cmd_emotions(_namespace(text="نص محايد")) == 0
        assert "neutral" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_emotions(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err


class TestTextProfileHandler:
    def test_default_axes_print(self, capsys) -> None:
        assert _cmd_textprofile(_namespace(text="حيثما اجتمعت الإرادة")) == 0
        output = capsys.readouterr().out
        assert "sentiment" in output
        assert "style" in output

    def test_json_output(self, capsys) -> None:
        assert _cmd_textprofile(_namespace(text="نص تجريبي", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload["axes"]) == {
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
            "rquestions",
            "anaphora",
            "wordplay",
        }

    def test_custom_axes(self, capsys) -> None:
        assert _cmd_textprofile(_namespace(text="نص تجريبي", axes=["sentiment"], json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload["axes"]) == {"sentiment"}

    def test_insights_printed(self, capsys) -> None:
        assert _cmd_textprofile(_namespace(text="خوف وذعر ورهبة من الموقف")) == 0
        output = capsys.readouterr().out
        assert "Insights" in output

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "profile.txt"
        file_path.write_text("حيثما اجتمعت الإرادة", encoding="utf-8")
        assert _cmd_textprofile(_namespace(file=str(file_path))) == 0
        assert "sentiment" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_textprofile(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err

    def test_original_profile_command_still_works(self, tmp_path, capsys) -> None:
        """Ensure the original corpus-level ``profile`` command is unaffected."""
        from aranorm.cli import main

        file_path = tmp_path / "corpus.txt"
        file_path.write_text("نص تجريبي قصير\nحيثما اجتمعت الإرادة\n", encoding="utf-8")
        result = main(["profile", "--file", str(file_path)])
        assert result == 0
        assert "Texts" in capsys.readouterr().out
