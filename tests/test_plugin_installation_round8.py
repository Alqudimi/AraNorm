"""Installed-style entry-point contracts for Round 8."""

import sys
from importlib import metadata
from pathlib import Path

import pytest

from aranorm import Processor, ProcessorRegistry


class BuiltinTestProcessor(Processor):
    name = "installed-demo"

    def process(self, text: str, context=None) -> str:
        return text


def _write_distribution(tmp_path: Path, *, entry_points: str, module_source: str) -> Path:
    sys.modules.pop("round8_plugin_module", None)
    module_path = tmp_path / "round8_plugin_module.py"
    module_path.write_text(module_source, encoding="utf-8")
    dist_info = tmp_path / "aranorm_round8_plugin-0.1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: aranorm-round8-plugin\nVersion: 0.1\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(entry_points, encoding="utf-8")
    return dist_info


def _patch_entry_points(monkeypatch: pytest.MonkeyPatch, dist_info: Path) -> None:
    distribution = metadata.PathDistribution(dist_info)
    entries = metadata.EntryPoints(list(distribution.entry_points))
    monkeypatch.setattr(metadata, "entry_points", lambda: entries)


def test_registry_discovers_real_dist_info_processor_entry_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist_info = _write_distribution(
        tmp_path,
        entry_points="[aranorm.processors]\ninstalled = round8_plugin_module:InstalledProcessor\n",
        module_source=(
            "from aranorm import Processor\n"
            "class InstalledProcessor(Processor):\n"
            "    name = 'installed'\n"
            "    def process(self, text, context=None):\n"
            "        return text + '!'\n"
        ),
    )
    sys.path.insert(0, str(tmp_path))
    _patch_entry_points(monkeypatch, dist_info)

    registry = ProcessorRegistry()
    report = registry.discover_report()

    assert report.ok is True
    assert report.discovered == ("installed",)
    assert registry.get("installed")().process("نص") == "نص!"


def test_registry_isolates_real_dist_info_invalid_processor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dist_info = _write_distribution(
        tmp_path,
        entry_points="[aranorm.processors]\ninvalid = round8_plugin_module:NotAProcessor\n",
        module_source="class NotAProcessor:\n    pass\n",
    )
    sys.path.insert(0, str(tmp_path))
    _patch_entry_points(monkeypatch, dist_info)

    report = ProcessorRegistry().discover_report()

    assert report.ok is False
    assert report.discovered == ()
    assert report.failures[0].name == "invalid"
    assert report.failures[0].error_type == "TypeError"


def test_registry_real_dist_info_strict_mode_raises_invalid_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist_info = _write_distribution(
        tmp_path,
        entry_points="[aranorm.processors]\ninvalid = round8_plugin_module:NotAProcessor\n",
        module_source="class NotAProcessor:\n    pass\n",
    )
    sys.path.insert(0, str(tmp_path))
    _patch_entry_points(monkeypatch, dist_info)

    with pytest.raises(TypeError, match="Processor subclass"):
        ProcessorRegistry().discover_report(strict=True)
