"""CLI tests for the Round-17 spelling / quality / profile sub-commands."""

from __future__ import annotations

import json
import sys

import pytest

sys.path.insert(0, "src")

from aranorm.cli import main  # noqa: E402


@pytest.fixture
def profile_file(tmp_path):
    file = tmp_path / "corpus.txt"
    file.write_text("نص عربي واضح.\nمسئول الاعلان عن الحدث\nAnother script entirely.\n", encoding="utf-8")
    return str(file)


# ── spelling ─────────────────────────────────────────────────────────────────


def test_spelling_inline_text(capsys: pytest.CaptureFixture) -> None:
    rc = main(["spelling", "مسئول الاعلان"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "مسؤول" in captured.out
    assert "الإعلان" in captured.out


def test_spelling_json_output(capsys: pytest.CaptureFixture) -> None:
    rc = main(["spelling", "مسئول", "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["spelling_issues_found"] >= 1


def test_spelling_file_not_found(capsys: pytest.CaptureFixture) -> None:
    rc = main(["spelling", "-f", "/nonexistent-r17.txt"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "file not found" in captured.err


def test_spelling_file_input(capsys: pytest.CaptureFixture, profile_file: str) -> None:
    rc = main(["spelling", "-f", profile_file])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Corrected" in captured.out


def test_spelling_clean_text(capsys: pytest.CaptureFixture) -> None:
    rc = main(["spelling", "هذا نص سليم تماما"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "No spelling issues" not in captured.out or "Issues" in captured.out
    assert "مسئول" not in captured.out


# ── quality ──────────────────────────────────────────────────────────────────


def test_quality_inline_text(capsys: pytest.CaptureFixture) -> None:
    rc = main(["quality", "هذا نص عربي واضح"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Quality score" in captured.out


def test_quality_json_output(capsys: pytest.CaptureFixture) -> None:
    rc = main(["quality", "نص عربي.", "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert 0.0 <= data["score"] <= 100.0
    assert data["label"] in ("excellent", "good", "fair", "poor")
    assert len(data["components"]) == 8


def test_quality_file_input(capsys: pytest.CaptureFixture, profile_file: str) -> None:
    rc = main(["quality", "-f", profile_file])
    captured = capsys.readouterr()
    assert rc == 0
    assert "/100" in captured.out


# ── profile ──────────────────────────────────────────────────────────────────


def test_profile_file_input(capsys: pytest.CaptureFixture, profile_file: str) -> None:
    rc = main(["profile", "-f", profile_file])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Texts" in captured.out
    assert "Recommendations" in captured.out


def test_profile_json_output(capsys: pytest.CaptureFixture, profile_file: str) -> None:
    rc = main(["profile", "-f", profile_file, "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["texts_count"] == 3
    assert "quality_distribution" in data


def test_profile_empty_file(capsys: pytest.CaptureFixture, tmp_path) -> None:
    file = tmp_path / "empty.txt"
    file.write_text("\n   \n\n", encoding="utf-8")
    rc = main(["profile", "-f", str(file)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "empty" in captured.err.lower()


def test_profile_file_not_found(capsys: pytest.CaptureFixture) -> None:
    rc = main(["profile", "-f", "/nonexistent-r17.txt"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "file not found" in captured.err


# ── Help / dispatch registration ─────────────────────────────────────────────


def test_spelling_help_available(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["spelling", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "spelling" in captured.out.lower()


def test_quality_help_available(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["quality", "--help"])
    assert exc_info.value.code == 0


def test_profile_help_available(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["profile", "--help"])
    assert exc_info.value.code == 0
