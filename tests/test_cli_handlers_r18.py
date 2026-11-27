"""Direct invocation tests for the Round 18 CLI handlers.

The subprocess-based CLI tests prove end-to-end correctness, but their
handlers run in a child process and are invisible to coverage. This module
calls the handler functions in-process with real ``argparse.Namespace``
objects so the exact same code paths are measured by coverage.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aranorm.cli import (  # noqa: E402
    _cmd_entities,
    _cmd_idioms,
    _cmd_pronouns,
    _cmd_snapshot,
    _cmd_topics,
)


def _namespace(**kwargs):
    defaults = {
        "file": None,
        "text": None,
        "json": False,
        "output": None,
        "input": None,
        "preset": "standard",
        "snapshot_command": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCliHandlerEntities:
    def test_text_mode(self, capsys):
        rc = _cmd_entities(_namespace(text="زار محمد الرياض اليوم"))
        assert rc == 0
        assert "محمد" in capsys.readouterr().out

    def test_json_mode(self, capsys):
        rc = _cmd_entities(_namespace(text="زرنا جدة والرياض", json=True))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["entity_count"] >= 2

    def test_file_mode(self, tmp_path, capsys):
        file = tmp_path / "t.txt"
        file.write_text("في القاهرة يوم الثلاثاء دفعنا 100 جنيه", encoding="utf-8")
        rc = _cmd_entities(_namespace(file=str(file)))
        assert rc == 0
        assert "القاهرة" in capsys.readouterr().out

    def test_missing_file(self, capsys):
        rc = _cmd_entities(_namespace(file="/tmp/missing_xyz_r18.txt"))
        assert rc == 1
        assert "Error" in capsys.readouterr().err

    def test_stdin_mode(self, capsys):
        with unittest.mock.patch.object(sys, "stdin", io.StringIO("هاتفه 0551234567")):
            rc = _cmd_entities(_namespace())
        assert rc == 0
        assert "0551234567" in capsys.readouterr().out


class TestCliHandlerTopics:
    def test_text_mode(self, capsys):
        rc = _cmd_topics(_namespace(text="حكم المحكمة في القضية"))
        assert rc == 0
        assert "legal" in capsys.readouterr().out

    def test_json_mode(self, capsys):
        rc = _cmd_topics(_namespace(text="اللاعب سجل هدفاً رائعاً", json=True))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["primary_topic"] == "sport"

    def test_file_mode(self, tmp_path, capsys):
        file = tmp_path / "t.txt"
        file.write_text("الطبيب وصف الدواء للمريض", encoding="utf-8")
        rc = _cmd_topics(_namespace(file=str(file)))
        assert rc == 0
        assert "medical" in capsys.readouterr().out

    def test_stdin_mode(self, capsys):
        with unittest.mock.patch.object(sys, "stdin", io.StringIO("الذكاء الاصطناعي يغير الصناعة التقنية")):
            rc = _cmd_topics(_namespace())
        assert rc == 0


class TestCliHandlerPronouns:
    def test_word_mode(self, capsys):
        rc = _cmd_pronouns(_namespace(text="كتبناها"))
        assert rc == 0
        assert "كتب" in capsys.readouterr().out

    def test_json_mode(self, capsys):
        rc = _cmd_pronouns(_namespace(text="كتابها", json=True))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        tokens = payload if isinstance(payload, list) else payload.get("tokens", [])
        assert tokens and any("كتاب" in str(t) for t in tokens)

    def test_file_mode(self, tmp_path, capsys):
        file = tmp_path / "t.txt"
        file.write_text("أعطوني\nكتبناها", encoding="utf-8")
        rc = _cmd_pronouns(_namespace(file=str(file)))
        assert rc == 0
        out = capsys.readouterr().out
        assert "أعطوني" in out and "كتبناها" in out

    def test_stdin_mode(self, capsys):
        with unittest.mock.patch.object(sys, "stdin", io.StringIO("سيذهبون")):
            rc = _cmd_pronouns(_namespace())
        assert rc == 0
        assert "سيذهبون" in capsys.readouterr().out


class TestCliHandlerIdioms:
    def test_text_mode(self, capsys):
        rc = _cmd_idioms(_namespace(text="سنذهب في الحال بإذن الله"))
        assert rc == 0
        assert "في الحال" in capsys.readouterr().out

    def test_json_mode(self, capsys):
        rc = _cmd_idioms(_namespace(text="لا سيما في الصيف", json=True))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["idiom_count"] >= 1

    def test_file_mode(self, tmp_path, capsys):
        file = tmp_path / "t.txt"
        file.write_text("ان شاء الله نحقق النجاح", encoding="utf-8")
        rc = _cmd_idioms(_namespace(file=str(file)))
        assert rc == 0
        assert "إن شاء الله" in capsys.readouterr().out or "ان شاء الله" in capsys.readouterr().out


class TestCliHandlerSnapshot:
    def test_save_and_restore(self, tmp_path, capsys):
        path = str(tmp_path / "snap.json")
        rc = _cmd_snapshot(_namespace(snapshot_command="save", output=path))
        assert rc == 0
        assert os.path.isfile(path)

        rc = _cmd_snapshot(_namespace(snapshot_command="restore", input=path))
        assert rc == 0
        assert "standard" in capsys.readouterr().out

    def test_save_json(self, tmp_path, capsys):
        path = str(tmp_path / "snap2.json")
        rc = _cmd_snapshot(_namespace(snapshot_command="save", output=path, json=True))
        assert rc == 0
        capsys.readouterr()
        # The snapshot file itself contains the JSON config object
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        assert "config" in payload

    def test_restore_missing_file(self, capsys):
        rc = _cmd_snapshot(_namespace(snapshot_command="restore", input="/tmp/missing_xyz_r18.json"))
        assert rc == 1
        assert "Error" in capsys.readouterr().err
