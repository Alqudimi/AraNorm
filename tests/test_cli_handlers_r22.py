"""Round 22 CLI handler tests: quotation, loans, roots sub-commands."""

import argparse
import json
from unittest import mock

import pytest

from aranorm.cli import _cmd_loans, _cmd_quotation, _cmd_roots, main


def _namespace(**overrides):
    defaults = {
        "text": None,
        "file": None,
        "json": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestQuotationHandler:
    def test_quoted_print(self, capsys) -> None:
        assert _cmd_quotation(_namespace(text="قال «النصر قريب»")) == 0
        output = capsys.readouterr().out
        assert "quoted" in output or "angle" in output

    def test_plain_print(self, capsys) -> None:
        assert _cmd_quotation(_namespace(text="نص عربي عادي بلا أي اقتباس")) == 0
        assert "plain" in capsys.readouterr().out

    def test_json_output(self, capsys) -> None:
        assert _cmd_quotation(_namespace(text="قال «النصر قريب»", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["label"] in ("quoted", "partially_quoted", "plain")
        assert "quotation_types" in payload
        assert "spans" in payload

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "quotation.txt"
        file_path.write_text('قال: "العمل شرف" ثم أغلق', encoding="utf-8")
        assert _cmd_quotation(_namespace(file=str(file_path))) == 0
        assert "quotes" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_quotation(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err

    def test_stdin_fallback(self, capsys) -> None:
        with mock.patch("sys.stdin", mock.MagicMock(read=lambda: "قال «نعم»")):
            assert _cmd_quotation(_namespace(text="")) == 0
        assert "quoted" in capsys.readouterr().out


class TestLoansHandler:
    def test_loanword_print(self, capsys) -> None:
        assert _cmd_loans(_namespace(text="الجو نورمال والشغل عادي")) == 0
        output = capsys.readouterr().out
        assert "loanwords" in output or "نورمال" in output

    def test_pure_arabic_print(self, capsys) -> None:
        assert _cmd_loans(_namespace(text="العلم نور والجهل ظلام")) == 0
        assert "pure_arabic" in capsys.readouterr().out

    def test_json_output(self, capsys) -> None:
        assert _cmd_loans(_namespace(text="الجو نورمال online", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["label"] in ("pure_arabic", "loanwords", "mixed")
        assert payload["loanword_count"] >= 1
        assert payload["latin_count"] >= 1
        assert "spans" in payload

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "loans.txt"
        file_path.write_text("الجو نورمال جدا", encoding="utf-8")
        assert _cmd_loans(_namespace(file=str(file_path))) == 0
        assert "loanwords" in capsys.readouterr().out

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_loans(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err

    def test_stdin_fallback(self, capsys) -> None:
        with mock.patch("sys.stdin", mock.MagicMock(read=lambda: "internet مهم")):
            assert _cmd_loans(_namespace(text="")) == 0
        assert "latin" in capsys.readouterr().out.lower()


class TestRootsHandler:
    def test_root_rich_print(self, capsys) -> None:
        assert _cmd_roots(_namespace(text="يكتب، فيقرأ، فيشرح، فيحل")) == 0
        output = capsys.readouterr().out
        assert "root_rich" in output or "diversity" in output.lower()

    def test_sparse_print(self, capsys) -> None:
        assert _cmd_roots(_namespace(text="عمل عمل عمل عمل عمل عمل عمل عمل عمل عمل")) == 0
        assert "sparse" in capsys.readouterr().out

    def test_json_output(self, capsys) -> None:
        assert _cmd_roots(_namespace(text="يكتب ويقرأ ويشرح ويحل", json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["label"] in ("root_rich", "moderate", "sparse")
        assert payload["unique_roots"] >= 1
        assert "diversity_index" in payload
        assert "top_root" in payload

    def test_file_input(self, tmp_path, capsys) -> None:
        file_path = tmp_path / "roots.txt"
        file_path.write_text("يكتب ويقرأ ويشرح", encoding="utf-8")
        assert _cmd_roots(_namespace(file=str(file_path))) == 0
        assert "root" in capsys.readouterr().out.lower()

    def test_file_not_found(self, capsys) -> None:
        assert _cmd_roots(_namespace(file="/missing/file.txt")) == 1
        assert "file not found" in capsys.readouterr().err

    def test_stdin_fallback(self, capsys) -> None:
        with mock.patch("sys.stdin", mock.MagicMock(read=lambda: "يكتب ويقرأ ويحل")):
            assert _cmd_roots(_namespace(text="")) == 0
        assert "root_rich" in capsys.readouterr().out


class TestR22CommandDispatch:
    """Ensure the three new commands are reachable through the main dispatcher."""

    @pytest.mark.parametrize(
        ("command", "text", "expect"),
        [
            ("quotation", "قال «النصر قريب»", "quoted"),
            ("loans", "الجو نورمال", "loanwords"),
            ("roots", "يكتب ويقرأ ويشرح ويحل", "root_rich"),
        ],
    )
    def test_dispatch(self, capsys, command, text, expect) -> None:
        assert main([command, text]) == 0
        assert expect in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("command", "text"),
        [
            ("quotation", "نص عادي"),
            ("loans", "نص عادي"),
            ("roots", "نص عادي"),
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
