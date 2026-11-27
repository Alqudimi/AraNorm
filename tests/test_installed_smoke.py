"""Packaging smoke tests for installed wheel and source distribution."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.slow
@pytest.mark.integration
def test_wheel_and_sdist_import_outside_source_tree(tmp_path: Path) -> None:
    """Both release artifacts must expose the public API in isolation."""
    project_root = Path(__file__).resolve().parents[1]
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--wheel",
            "--sdist",
            "--outdir",
            str(artifact_dir),
            str(project_root),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stdout + "\n" + build.stderr

    artifacts = sorted(artifact_dir.iterdir())
    wheel = next(path for path in artifacts if path.suffix == ".whl")
    sdist = next(path for path in artifacts if path.suffix == ".gz")
    probe = """
import json
import aranorm
from aranorm import ArabicNormalizationPipeline, BatchRetryReport, PipelineRuntime

pipeline = ArabicNormalizationPipeline.from_preset("light")
runtime = PipelineRuntime()
result = pipeline.process("أَنَا")
report = pipeline.process_batch_retry(["أَنَا"])
print(json.dumps({
    "version": aranorm.__version__,
    "normalized": result.normalized_text,
    "has_describe": "config_fingerprint" in pipeline.describe_operational(),
    "has_retry": isinstance(report, BatchRetryReport),
    "has_runtime": runtime.health().ready and runtime.generation == 0,
}, ensure_ascii=False, sort_keys=True))
"""

    for artifact in (wheel, sdist):
        target = tmp_path / artifact.stem.replace(".", "_")
        target.mkdir()
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                "--no-build-isolation",
                "--target",
                str(target),
                str(artifact),
            ],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": ""},
            capture_output=True,
            text=True,
            check=False,
        )
        assert install.returncode == 0, install.stdout + "\n" + install.stderr

        run = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=tmp_path,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(target)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 0, run.stdout + "\n" + run.stderr
        assert '"has_describe": true' in run.stdout
        assert '"has_retry": true' in run.stdout
        assert '"has_runtime": true' in run.stdout
        assert '"version": "1.15.0"' in run.stdout
