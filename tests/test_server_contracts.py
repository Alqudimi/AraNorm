"""Integration contracts for the optional standard-library HTTP server."""

import json
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from typing import Iterator, Tuple

import pytest

from aranorm import PipelineRuntime
from aranorm.server import AraNormHTTPServer, ConfigReloadWatcher, create_server
from aranorm import server as server_module


@contextmanager
def running_server(max_body_bytes: int = 2_000_000) -> Iterator[str]:
    server = create_server(PipelineRuntime(), "127.0.0.1", 0, max_body_bytes=max_body_bytes)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(base: str, path: str, *, method: str = "GET", payload=None, headers=None) -> Tuple[int, dict]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_obj = urllib.request.Request(
        base + path,
        data=data,
        headers=headers or {},
        method=method,
    )
    try:
        response = urllib.request.urlopen(request_obj, timeout=3)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))
    return response.status, json.loads(response.read().decode("utf-8"))


def test_server_type_is_threaded() -> None:
    assert issubclass(AraNormHTTPServer, ThreadingHTTPServer)
    assert AraNormHTTPServer.daemon_threads is True
    assert AraNormHTTPServer.allow_reuse_address is True


def test_health_and_describe_endpoints() -> None:
    with running_server() as base:
        live_status, live = request(base, "/health/live")
        ready_status, ready = request(base, "/health/ready")
        describe_status, describe = request(base, "/v1/describe")

    assert live_status == 200
    assert live == {"schema_version": 1, "status": "live"}
    assert ready_status == 200
    assert ready["status"] == "ready"
    assert ready["ready"] is True
    assert describe_status == 200
    assert describe["schema_version"] == 1
    assert describe["runtime"]["generation"] == 0


def test_normalize_and_batch_endpoints_return_versioned_results() -> None:
    with running_server() as base:
        normalize_status, normalize = request(
            base,
            "/v1/normalize",
            method="POST",
            payload={"text": "مَرْحَبًا"},
            headers={"Content-Type": "application/json"},
        )
        batch_status, batch = request(
            base,
            "/v1/batch",
            method="POST",
            payload={"texts": ["الأول", "الثاني"], "batch_size": 2, "workers": 1},
            headers={"Content-Type": "application/json"},
        )

    assert normalize_status == 200
    assert normalize["schema_version"] == 1
    assert normalize["result"]["normalized_text"]
    assert batch_status == 200
    assert batch["schema_version"] == 1
    assert batch["count"] == 2
    assert len(batch["results"]) == 2


def test_json_validation_and_content_type_errors_are_structured() -> None:
    with running_server() as base:
        missing_content_status, missing_content = request(
            base,
            "/v1/normalize",
            method="POST",
            payload={"text": "نص"},
        )
        missing_text_status, missing_text = request(
            base,
            "/v1/normalize",
            method="POST",
            payload={},
            headers={"Content-Type": "application/json"},
        )
        bad_batch_status, bad_batch = request(
            base,
            "/v1/batch",
            method="POST",
            payload={"texts": "not-a-list"},
            headers={"Content-Type": "application/json"},
        )

    assert missing_content_status == 415
    assert missing_content["error"]["code"] == "unsupported_media_type"
    assert missing_text_status == 400
    assert missing_text["error"]["code"] == "missing_text"
    assert bad_batch_status == 400
    assert bad_batch["error"]["code"] == "invalid_texts"


def test_invalid_json_and_oversized_body_are_rejected() -> None:
    with running_server(max_body_bytes=16) as base:
        invalid_request = urllib.request.Request(
            base + "/v1/normalize",
            data=b"{not-json}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        invalid_status = 0
        invalid_body = {}
        try:
            urllib.request.urlopen(invalid_request, timeout=3)
        except urllib.error.HTTPError as error:
            invalid_status = error.code
            invalid_body = json.loads(error.read().decode("utf-8"))

        oversized_status, oversized = request(
            base,
            "/v1/normalize",
            method="POST",
            payload={"text": "هذا النص أطول من الحد"},
            headers={"Content-Type": "application/json"},
        )

    assert invalid_status == 400
    assert invalid_body["error"]["code"] == "invalid_json"
    assert oversized_status == 413
    assert oversized["error"]["code"] == "request_too_large"


def test_config_reload_watcher_publishes_changed_valid_config(tmp_path) -> None:
    config_path = tmp_path / "pipeline.json"
    config_path.write_text('{"preset": "standard"}', encoding="utf-8")
    runtime = PipelineRuntime()
    watcher = ConfigReloadWatcher(runtime, config_path, 0.02)
    watcher.start()
    try:
        config_path.write_text('{"preset": "light"}', encoding="utf-8")
        deadline = time.monotonic() + 2
        while runtime.generation == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        watcher.stop()

    assert runtime.generation == 1
    assert runtime.health().status == "ready"
    assert runtime.config.preset.value == "light"


def test_config_reload_watcher_keeps_snapshot_on_invalid_config(tmp_path) -> None:
    config_path = tmp_path / "pipeline.json"
    config_path.write_text('{"preset": "standard"}', encoding="utf-8")
    runtime = PipelineRuntime()
    before = runtime.health().config_fingerprint
    watcher = ConfigReloadWatcher(runtime, config_path, 0.02)
    watcher.start()
    try:
        config_path.write_text('{"preset":', encoding="utf-8")
        deadline = time.monotonic() + 2
        while runtime.health().status == "ready" and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        watcher.stop()

    assert runtime.generation == 0
    assert runtime.health().config_fingerprint == before
    assert runtime.health().status == "degraded"


def test_unknown_route_and_invalid_text_use_safe_error_envelopes() -> None:
    with running_server() as base:
        not_found_status, not_found = request(base, "/unknown")
        invalid_status, invalid = request(
            base,
            "/v1/normalize",
            method="POST",
            payload={"text": 123},
            headers={"Content-Type": "application/json"},
        )

    assert not_found_status == 404
    assert not_found["error"]["code"] == "not_found"
    assert invalid_status == 422
    assert invalid["error"]["code"] == "invalid_text"


def test_json_scalar_payload_is_rejected_as_object() -> None:
    with running_server() as base:
        status, body = request(
            base,
            "/v1/normalize",
            method="POST",
            payload=["not", "an", "object"],
            headers={"Content-Type": "application/json"},
        )

    assert status == 400
    assert body["error"]["code"] == "invalid_payload"


def test_empty_batch_is_rejected() -> None:
    with running_server() as base:
        status, body = request(
            base,
            "/v1/batch",
            method="POST",
            payload={"texts": []},
            headers={"Content-Type": "application/json"},
        )

    assert status == 400
    assert body["error"]["code"] == "empty_batch"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"texts": ["نص"], "batch_size": True}, "batch_size must be an integer"),
        ({"texts": ["نص"], "workers": True}, "workers must be an integer"),
    ],
)
def test_batch_integer_flags_reject_boolean_values(payload: dict, message: str) -> None:
    with running_server() as base:
        status, body = request(
            base,
            "/v1/batch",
            method="POST",
            payload=payload,
            headers={"Content-Type": "application/json"},
        )

    assert status == 422
    assert body["error"]["code"] == "invalid_request"
    assert message in body["error"]["message"]


def test_post_to_get_only_route_returns_not_found() -> None:
    with running_server() as base:
        status, body = request(
            base,
            "/health/live",
            method="POST",
            payload={},
            headers={"Content-Type": "application/json"},
        )

    assert status == 404
    assert body["error"]["code"] == "not_found"


def test_get_to_post_only_route_returns_not_found() -> None:
    with running_server() as base:
        status, body = request(base, "/v1/normalize")

    assert status == 404
    assert body["error"]["code"] == "not_found"


def test_server_rejects_invalid_body_limit() -> None:
    with pytest.raises(ValueError, match="max_body_bytes"):
        create_server(PipelineRuntime(), max_body_bytes=0)


def test_watcher_rejects_non_positive_interval(tmp_path) -> None:
    with pytest.raises(ValueError, match="reload interval"):
        ConfigReloadWatcher(PipelineRuntime(), tmp_path / "pipeline.json", 0)


def test_watcher_ignores_unchanged_and_missing_file(tmp_path) -> None:
    config_path = tmp_path / "pipeline.json"
    runtime = PipelineRuntime()
    watcher = ConfigReloadWatcher(runtime, config_path, 0.02)
    watcher.start()
    try:
        time.sleep(0.06)
    finally:
        watcher.stop()

    assert runtime.generation == 0


def test_server_returns_safe_internal_error_for_unexpected_processing_failure(monkeypatch) -> None:
    class ExplodingRuntime:
        def process(self, text):
            raise RuntimeError("secret internal detail")

    server = create_server(ExplodingRuntime(), "127.0.0.1", 0)  # type: ignore[arg-type]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        status, body = request(
            f"http://{host}:{port}",
            "/v1/normalize",
            method="POST",
            payload={"text": "نص"},
            headers={"Content-Type": "application/json"},
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 500
    assert body["error"] == {"code": "internal_error", "message": "internal server error"}
    assert "secret internal detail" not in json.dumps(body)


def test_serve_closes_server_when_interrupted(monkeypatch) -> None:
    events = []

    class FakeServer:
        def serve_forever(self):
            events.append("serve")
            raise KeyboardInterrupt

        def server_close(self):
            events.append("close")

    monkeypatch.setattr(server_module, "create_server", lambda *args, **kwargs: FakeServer())
    with pytest.raises(KeyboardInterrupt):
        server_module.serve(PipelineRuntime(), port=0)

    assert events == ["serve", "close"]


def test_serve_starts_and_stops_optional_watcher(monkeypatch) -> None:
    events = []

    class FakeServer:
        def serve_forever(self):
            events.append("serve")
            raise KeyboardInterrupt

        def server_close(self):
            events.append("close")

    class FakeWatcher:
        def __init__(self, runtime, path, interval):
            events.append(("watcher-init", path, interval))

        def start(self):
            events.append("watcher-start")

        def stop(self):
            events.append("watcher-stop")

    monkeypatch.setattr(server_module, "create_server", lambda *args, **kwargs: FakeServer())
    monkeypatch.setattr(server_module, "ConfigReloadWatcher", FakeWatcher)
    with pytest.raises(KeyboardInterrupt):
        server_module.serve(PipelineRuntime(), config_path="pipeline.json", reload_interval=0.5)

    assert events == [
        ("watcher-init", "pipeline.json", 0.5),
        "watcher-start",
        "serve",
        "watcher-stop",
        "close",
    ]
