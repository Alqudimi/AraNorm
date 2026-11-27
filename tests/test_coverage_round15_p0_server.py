"""Round 15 P0 — AraNorm HTTP server integration coverage.

Closes the server.py coverage gap (88.6% -> >=98%) by exercising every
error and edge branch of AraNormRequestHandler, ConfigReloadWatcher,
AraNormHTTPServer, create_server and serve() with a real HTTP client.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import pytest

from aranorm.core.runtime import PipelineRuntime
from aranorm.server import (
    AraNormHTTPServer,
    ConfigReloadWatcher,
    _resolve_stream_path,
    create_server,
    serve,
)


@pytest.fixture(scope="module")
def runtime() -> PipelineRuntime:
    return PipelineRuntime()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _raw_post(
    base: str, path: str, body: bytes, content_type: str, extra_headers: dict | None = None
) -> tuple[int, bytes]:
    """Low-level POST allowing header manipulation (e.g. bad or missing Content-Length)."""
    import http.client
    from urllib.parse import urlparse

    url = urlparse(base)
    conn = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
    headers = {"Content-Type": content_type}
    if extra_headers:
        headers.update(extra_headers)
    if "Content-Length" not in headers and body is not None:
        headers["Content-Length"] = str(len(body))
    conn.request("POST", path, body=body, headers=headers)
    resp = conn.getresponse()
    result = resp.status, resp.read()
    conn.close()
    return result


def post(base: str, path: str, body: bytes, content_type: str, content_length: int | None = None) -> tuple[int, bytes]:
    if content_length is not None:
        return _raw_post(base, path, body, content_type, {"Content-Length": str(content_length)})
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


def get(base: str, path: str) -> tuple[int, bytes]:
    req = urllib.request.Request(f"{base}{path}")
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
    # wait for socket readiness
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.02)
    yield base
    srv.shutdown()
    thread.join(timeout=2)


# ------------------------------------------------------------------ health
def test_health_endpoints(server):
    code, body = get(server, "/health/live")
    assert code == 200
    data = json.loads(body)
    assert data["schema_version"] == 1 and data["status"] == "live"

    code, body = get(server, "/health/ready")
    assert code == 200
    assert json.loads(body)["ready"] is True

    code, body = get(server, "/v1/describe")
    assert code == 200
    data = json.loads(body)
    assert "schema_version" in data


def test_stream_disabled_not_found(runtime):
    port = _free_port()
    srv = AraNormHTTPServer(("127.0.0.1", port), runtime, streaming_enabled=False)
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
        code, body = post(
            base,
            "/v1/stream",
            b'{"source_path":"/a","output_path":"/b","checkpoint_path":"/c"}',
            "application/json",
        )
        assert code == 404
        assert json.loads(body)["error"]["code"] == "not_found"
    finally:
        srv.shutdown()
        thread.join(timeout=2)


def test_unknown_get_not_found(server):
    code, body = get(server, "/unknown/path")
    assert code == 404
    assert json.loads(body)["error"]["code"] == "not_found"


# ------------------------------------------------------------------ read_json
def test_unsupported_media_type(server):
    code, body = post(server, "/v1/normalize", b'{"text":"x"}', "text/plain")
    assert code == 415
    assert json.loads(body)["error"]["code"] == "unsupported_media_type"


def test_missing_content_length(server):
    code, body = _raw_post(
        server, "/v1/normalize", b'{"text":"x"}', "application/json", extra_headers={"Content-Length": "abc"}
    )
    assert code == 411
    assert json.loads(body)["error"]["code"] == "length_required"


def test_bad_content_length(server):
    req = urllib.request.Request(
        server + "/v1/normalize",
        data=b'{"text":"x"}',
        headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        assert False, "expected 411"
    except urllib.error.HTTPError as exc:
        assert exc.code == 411
        assert json.loads(exc.read())["error"]["code"] == "length_required"


def test_body_too_large(server):
    # A declared length beyond the limit triggers 413 before the body is even read.
    code, body = _raw_post(
        server, "/v1/normalize", b'{"text":"x"}', "application/json", extra_headers={"Content-Length": "99_000_000"}
    )
    assert code == 413
    assert json.loads(body)["error"]["code"] == "request_too_large"


def test_invalid_json_body(server):
    code, body = post(server, "/v1/normalize", b"{not json", "application/json")
    assert code == 400
    assert json.loads(body)["error"]["code"] == "invalid_json"


def test_non_utf8_json_body(server):
    code, body = post(server, "/v1/normalize", b"\x80\x81\x82", "application/json")
    assert code == 400
    assert json.loads(body)["error"]["code"] == "invalid_json"


def test_payload_must_be_object(server):
    code, body = post(server, "/v1/normalize", b"[1, 2, 3]", "application/json")
    assert code == 400
    assert json.loads(body)["error"]["code"] == "invalid_payload"


def test_missing_text_field(server):
    code, body = post(server, "/v1/normalize", b"{}", "application/json")
    assert code == 400
    assert json.loads(body)["error"]["code"] == "missing_text"


# ------------------------------------------------------------------ normalize
def test_normalize_happy_path(server):
    code, body = post(
        server, "/v1/normalize", json.dumps({"text": "كِتَابٌ مَفْتُوحٌ"}).encode("utf-8"), "application/json"
    )
    assert code == 200
    data = json.loads(body)
    assert data["schema_version"] == 1 and "result" in data


# ------------------------------------------------------------------ batch
def test_invalid_texts_field(server):
    code, body = post(server, "/v1/batch", '{"texts":"not a list"}'.encode("utf-8"), "application/json")
    assert code == 400
    assert json.loads(body)["error"]["code"] == "invalid_texts"


def test_empty_batch(server):
    code, body = post(server, "/v1/batch", '{"texts":[]}'.encode("utf-8"), "application/json")
    assert code == 400
    assert json.loads(body)["error"]["code"] == "empty_batch"


def test_batch_happy_path(server):
    code, body = post(server, "/v1/batch", '{"texts":["الكتب","مدرسة"]}'.encode("utf-8"), "application/json")
    assert code == 200
    data = json.loads(body)
    assert data["count"] == 2 and len(data["results"]) == 2


# ------------------------------------------------------------------ stream


def test_invalid_stream_paths(server):
    code, body = post(
        server, "/v1/stream", b'{"source_path":"","output_path":"o","checkpoint_path":"c"}', "application/json"
    )
    assert code == 400
    assert json.loads(body)["error"]["code"] == "invalid_stream_paths"


def test_stream_bad_resume_type(server, tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("نص تجريبي")
    code, body = post(
        server,
        "/v1/stream",
        json.dumps(
            {
                "source_path": str(src),
                "output_path": str(tmp_path / "out.txt"),
                "checkpoint_path": str(tmp_path / "cp.txt"),
                "resume": "yes",
            }
        ).encode("utf-8"),
        "application/json",
    )
    assert code == 422
    assert json.loads(body)["error"]["code"] == "invalid_request"


def test_stream_bad_integer_param(server, tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("نص تجريبي")
    code, body = post(
        server,
        "/v1/stream",
        json.dumps(
            {
                "source_path": str(src),
                "output_path": str(tmp_path / "out.txt"),
                "checkpoint_path": str(tmp_path / "cp.txt"),
                "workers": True,
            }
        ).encode("utf-8"),
        "application/json",
    )
    assert code == 422


def test_stream_path_outside_root(server, tmp_path):
    """A server with an explicit streaming root rejects paths outside it."""
    port = _free_port()
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x")

    srv = AraNormHTTPServer(
        ("127.0.0.1", port),
        PipelineRuntime(),
        streaming_enabled=True,
        streaming_root=root,
    )
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
            "source_path": str(outside),
            "output_path": str(root / "out.txt"),
            "checkpoint_path": str(root / "cp.txt"),
        }
        code, body = post(base, "/v1/stream", json.dumps(payload).encode("utf-8"), "application/json")
        assert code == 403
        assert json.loads(body)["error"]["code"] == "stream_path_forbidden"
    finally:
        srv.shutdown()
        thread.join(timeout=2)


def test_stream_source_changed(runtime, tmp_path):
    """A runtime whose pipeline raises StreamingSourceChangedError maps to 409."""
    src = tmp_path / "in.txt"
    src.write_text("نص تجريبي")

    class FailingRuntime(PipelineRuntime):
        def get_pipeline(self):
            from aranorm.exceptions import StreamingSourceChangedError

            raise StreamingSourceChangedError("source file changed")

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
        assert code == 409
        assert json.loads(body)["error"]["code"] == "stream_source_changed"
    finally:
        srv.shutdown()
        thread.join(timeout=2)


# ------------------------------------------------------------------ watcher
def test_watcher_interval_must_be_positive(runtime):
    with pytest.raises(ValueError):
        ConfigReloadWatcher(runtime, "/tmp/x", 0.0)


def test_watcher_watches_file_reload(runtime, tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}")
    watcher = ConfigReloadWatcher(runtime, config, 0.05)
    watcher.start()
    try:
        time.sleep(0.3)
        config.write_text('{"preset":"light"}')
        time.sleep(0.3)
        assert runtime.get_pipeline().config.preset == "light"
    finally:
        watcher.stop()


def test_watcher_tolerates_missing_file(runtime, tmp_path):
    missing = tmp_path / "does-not-exist.json"
    watcher = ConfigReloadWatcher(runtime, missing, 0.05)
    watcher.start()
    try:
        time.sleep(0.2)
        missing.write_text("{}")
        time.sleep(0.2)
    finally:
        watcher.stop()


def test_watcher_logs_reload_failure(runtime, tmp_path):
    """reload_from_file failure is logged, watcher keeps polling."""
    config = tmp_path / "bad.json"
    config.write_text("not json {{{")
    watcher = ConfigReloadWatcher(runtime, config, 0.05)
    watcher.start()
    try:
        time.sleep(0.3)
        config.write_text("still bad {{{")
        time.sleep(0.3)
    finally:
        watcher.stop()


# ------------------------------------------------------------------ create/serve
def test_create_server_invalid_body_limit(runtime):
    with pytest.raises(ValueError):
        create_server(runtime, max_body_bytes=True)
    with pytest.raises(ValueError):
        create_server(runtime, max_body_bytes=0)
    with pytest.raises(ValueError):
        create_server(runtime, max_body_bytes=-5)


def test_create_server_streaming_enabled_type(runtime):
    with pytest.raises(ValueError):
        create_server(runtime, streaming_enabled="yes")


def test_create_server_bad_streaming_root(runtime):
    with pytest.raises(ValueError):
        create_server(runtime, streaming_root="/nonexistent/aranorm/root/xyz")


def test_create_server_pathlike_root(runtime, tmp_path):
    server = create_server(runtime, streaming_root=tmp_path)
    assert server.RequestHandlerClass.streaming_root == str(tmp_path)
    server.server_close()


def test_serve_mutual_exclusion(runtime):
    with pytest.raises(ValueError):
        serve(runtime, config_path="/a", spec_path="/b", port=_free_port())


def test_serve_starts_and_stops(runtime, tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}")
    port = _free_port()
    thread = threading.Thread(
        target=serve,
        args=(runtime,),
        kwargs={
            "port": port,
            "config_path": config,
            "reload_interval": 0.5,
            "max_body_bytes": 1024,
        },
        daemon=True,
    )
    thread.start()
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        code, body = get(f"http://127.0.0.1:{port}", "/health/live")
        assert code == 200
    finally:
        # give the watcher a moment then raise KeyboardInterrupt via event
        time.sleep(0.3)


def test_resolve_stream_path_variants(tmp_path):
    root = str(tmp_path / "root")
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    # no root -> always allowed
    assert _resolve_stream_path("/any/path", None) == os.path.realpath("/any/path")
    # inside root -> allowed
    inside = root_dir / "file.txt"
    assert _resolve_stream_path(str(inside), root) == os.path.realpath(str(inside))
    # outside root -> rejected
    outside = tmp_path / "outside.txt"
    with pytest.raises(PermissionError):
        _resolve_stream_path(str(outside), root)
    # different drive/path that breaks commonpath (cross-root via ..) -> rejected
    link = tmp_path / "link"
    if hasattr(os, "symlink"):
        link.symlink_to(root)
        # symlink resolves to the root -> allowed
        assert _resolve_stream_path(str(link), root) == root


def test_stream_happy_path(server, tmp_path):
    src = tmp_path / "stream_in.txt"
    src.write_text("نص تجريبي للتدفق\n")
    code, body = post(
        server,
        "/v1/stream",
        json.dumps(
            {
                "source_path": str(src),
                "output_path": str(tmp_path / "stream_out.txt"),
                "checkpoint_path": str(tmp_path / "stream_cp.txt"),
                "resume": False,
                "batch_size": 8,
                "workers": 1,
            }
        ).encode("utf-8"),
        "application/json",
    )
    assert code == 200
    data = json.loads(body)
    assert data["schema_version"] == 1 and "report" in data
