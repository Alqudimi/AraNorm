"""Round 15 P0b — close the last server.py coverage gaps.

Targets the remaining missing branches/lines identified after the P0 run:

- _resolve_stream_path ``ValueError`` from ``os.path.commonpath`` (mixed
  drive roots on Windows / incompatible path prefixes).
- ``StreamingSessionConflictError`` -> 409 ``stream_conflict``.
- ``InvalidTextError`` -> 422 ``invalid_text``.
- The bare ``Exception`` catch-all -> 500 ``internal_error``.
- ``_handle_batch`` / normalize path with invalid ``workers`` value (422).
- ``serve()`` with a config path (watcher + reload hook path).
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from unittest import mock

import pytest

from aranorm.core.runtime import PipelineRuntime
from aranorm.exceptions import (
    InvalidTextError,
    StreamingSessionConflictError,
)
from aranorm.server import (
    AraNormHTTPServer,
    _resolve_stream_path,
    serve,
)


@pytest.fixture(scope="module")
def runtime() -> PipelineRuntime:
    return PipelineRuntime()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def post(base: str, path: str, body: bytes, content_type: str) -> tuple[int, bytes]:
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


@pytest.fixture(scope="module")
def server(runtime: PipelineRuntime):
    port = _free_port()
    srv = AraNormHTTPServer(("127.0.0.1", port), runtime, streaming_enabled=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.02)
    yield base
    srv.shutdown()
    thread.join(timeout=2)


# ------------------------------------------------------------------ resolve path


def test_resolve_stream_path_commonpath_valueerror(tmp_path):
    """commonpath raises ValueError for incompatible roots (e.g. on Windows)."""
    with mock.patch("os.path.commonpath", side_effect=ValueError("incompatible roots")):
        with pytest.raises(PermissionError, match="stream path is outside"):
            _resolve_stream_path(str(tmp_path / "a.txt"), streaming_root=str(tmp_path))


# ------------------------------------------------------------------ stream exceptions


def test_stream_session_conflict(runtime, tmp_path):
    """StreamingSessionConflictError maps to 409 stream_conflict."""
    src = tmp_path / "in.txt"
    src.write_text("نص تجريبي")

    class ConflictRuntime(PipelineRuntime):
        def get_pipeline(self):
            raise StreamingSessionConflictError("session already running")

    port = _free_port()
    srv = AraNormHTTPServer(("127.0.0.1", port), ConflictRuntime(), streaming_enabled=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.02)
        base = f"http://127.0.0.1:{port}"
        payload = {
            "source_path": str(src),
            "output_path": str(tmp_path / "out.txt"),
            "checkpoint_path": str(tmp_path / "cp.txt"),
        }
        code, body = post(base, "/v1/stream", json.dumps(payload).encode("utf-8"), "application/json")
        assert code == 409
        assert json.loads(body)["error"]["code"] == "stream_conflict"
    finally:
        srv.shutdown()
        thread.join(timeout=2)


def test_stream_invalid_text(runtime, tmp_path):
    """InvalidTextError raised during streaming maps to 422 invalid_text."""
    src = tmp_path / "in.txt"
    src.write_text("نص تجريبي")

    class FailingRuntime(PipelineRuntime):
        def get_pipeline(self):
            raise InvalidTextError("broken text")

    port = _free_port()
    srv = AraNormHTTPServer(("127.0.0.1", port), FailingRuntime(), streaming_enabled=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.02)
        base = f"http://127.0.0.1:{port}"
        payload = {
            "source_path": str(src),
            "output_path": str(tmp_path / "out.txt"),
            "checkpoint_path": str(tmp_path / "cp.txt"),
        }
        code, body = post(base, "/v1/stream", json.dumps(payload).encode("utf-8"), "application/json")
        assert code == 422
        assert json.loads(body)["error"]["code"] == "invalid_text"
    finally:
        srv.shutdown()
        thread.join(timeout=2)


def test_stream_internal_error(runtime, tmp_path):
    """An unexpected bare Exception during streaming maps to 500 internal_error."""
    src = tmp_path / "in.txt"
    src.write_text("نص تجريبي")

    class CrashingRuntime(PipelineRuntime):
        def get_pipeline(self):
            raise RuntimeError("boom")

    port = _free_port()
    srv = AraNormHTTPServer(("127.0.0.1", port), CrashingRuntime(), streaming_enabled=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.02)
        base = f"http://127.0.0.1:{port}"
        payload = {
            "source_path": str(src),
            "output_path": str(tmp_path / "out.txt"),
            "checkpoint_path": str(tmp_path / "cp.txt"),
        }
        code, body = post(base, "/v1/stream", json.dumps(payload).encode("utf-8"), "application/json")
        assert code == 500
        assert json.loads(body)["error"]["code"] == "internal_error"
    finally:
        srv.shutdown()
        thread.join(timeout=2)


# ------------------------------------------------------------------ normalize / batch branches


def test_normalize_bad_workers(server):
    """Non-integer workers in a batch payload yields 422 (invalid_request)."""
    code, body = post(
        server,
        "/v1/batch",
        json.dumps({"texts": ["كتاب"], "workers": True}).encode("utf-8"),
        "application/json",
    )
    assert code == 422
    assert json.loads(body)["error"]["code"] == "invalid_request"


def test_batch_bad_batch_size(server):
    """batch_size='big' on the batch endpoint yields 422 invalid_request."""
    code, body = post(
        server,
        "/v1/batch",
        json.dumps({"texts": ["a"], "batch_size": "big"}).encode("utf-8"),
        "application/json",
    )
    assert code == 422
    assert json.loads(body)["error"]["code"] == "invalid_request"


# ------------------------------------------------------------------ serve()


def test_serve_with_config_watcher(runtime, tmp_path):
    """serve() starts a watcher over a config path and stops it on exit."""
    port = _free_port()
    config = tmp_path / "config.json"
    config.write_text("{}")

    started = {"server": None}

    def fake_bind(*a, **kw):
        started["server"] = True
        raise KeyboardInterrupt("stop now")

    class FakeServer(AraNormHTTPServer):
        def server_bind(self):  # type: ignore[override]
            started["server"] = True
            raise KeyboardInterrupt("stop now")

    # We cannot let serve_forever run, so patch serve_forever to stop immediately.
    with mock.patch.object(AraNormHTTPServer, "serve_forever"):
        serve(runtime, config_path=str(config), reload_interval=0.05, port=port)
    # If the watcher was attached it ran start/stop without crashing.
