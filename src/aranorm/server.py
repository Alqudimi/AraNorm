"""Small standard-library HTTP service for AraNorm.

This module is opt-in: importing AraNorm never starts a listener.  It is suited
for local services or deployment behind a production reverse proxy that owns
TLS, authentication, and rate limiting.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Type, Union

from aranorm.core.runtime import PipelineRuntime
from aranorm.core.streaming import StreamingSession
from aranorm.exceptions import (
    AraNormError,
    InvalidTextError,
    StreamingSessionConflictError,
    StreamingSourceChangedError,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_MAX_BODY_BYTES = 2_000_000


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _error_payload(code: str, message: str) -> Dict[str, Any]:
    return {"schema_version": 1, "error": {"code": code, "message": message}}


def _resolve_stream_path(path: str, streaming_root: Optional[str]) -> str:
    """Resolve a stream path and enforce an optional local root boundary."""
    candidate = os.path.realpath(path)
    if streaming_root is None:
        return candidate
    try:
        inside = os.path.commonpath((candidate, streaming_root)) == streaming_root
    except ValueError as exc:
        raise PermissionError("stream path is outside the configured streaming root") from exc
    if not inside:
        raise PermissionError("stream path is outside the configured streaming root")
    return candidate


class AraNormRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler with an injected :class:`PipelineRuntime`."""

    runtime: PipelineRuntime
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    streaming_enabled: bool = False
    streaming_root: Optional[str] = None
    server_version = "AraNormHTTP/1.0"

    def log_message(self, format: str, *args: object) -> None:
        """Use the application logger instead of writing directly to stderr."""
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Optional[Dict[str, Any]]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                _error_payload("unsupported_media_type", "Content-Type must be application/json"),
            )
            return None
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "-1")
        except ValueError:
            length = -1
        if length < 0:
            self._send_json(
                HTTPStatus.LENGTH_REQUIRED,
                _error_payload("length_required", "Content-Length is required"),
            )
            return None
        if length > self.max_body_bytes:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                _error_payload("request_too_large", "request body exceeds the configured limit"),
            )
            return None
        try:
            decoded = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                _error_payload("invalid_json", "request body is not valid UTF-8 JSON"),
            )
            return None
        if not isinstance(decoded, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                _error_payload("invalid_payload", "request body must be a JSON object"),
            )
            return None
        return decoded

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health/live":
            self._send_json(HTTPStatus.OK, {"schema_version": 1, "status": "live"})
            return
        if self.path == "/health/ready":
            health = self.runtime.health()
            self._send_json(HTTPStatus.OK if health.ready else HTTPStatus.SERVICE_UNAVAILABLE, health.to_dict())
            return
        if self.path == "/v1/describe":
            self._send_json(HTTPStatus.OK, self.runtime.describe())
            return
        self._send_json(HTTPStatus.NOT_FOUND, _error_payload("not_found", "endpoint not found"))

    def do_POST(self) -> None:  # noqa: N802
        allowed_paths = {"/v1/normalize", "/v1/batch"}
        if self.streaming_enabled:
            allowed_paths.add("/v1/stream")
        if self.path not in allowed_paths:
            self._send_json(HTTPStatus.NOT_FOUND, _error_payload("not_found", "endpoint not found"))
            return
        payload = self._read_json()
        if payload is None:
            return
        try:
            if self.path == "/v1/normalize":
                self._handle_normalize(payload)
            elif self.path == "/v1/batch":
                self._handle_batch(payload)
            else:
                self._handle_stream(payload)
        except PermissionError as error:
            self._send_json(HTTPStatus.FORBIDDEN, _error_payload("stream_path_forbidden", str(error)))
        except StreamingSessionConflictError as error:
            self._send_json(HTTPStatus.CONFLICT, _error_payload("stream_conflict", str(error)))
        except StreamingSourceChangedError as error:
            self._send_json(HTTPStatus.CONFLICT, _error_payload("stream_source_changed", str(error)))
        except InvalidTextError as error:
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, _error_payload("invalid_text", str(error)))
        except (AraNormError, ValueError, TypeError) as error:
            LOGGER.warning("request rejected: %s", type(error).__name__)
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, _error_payload("invalid_request", str(error)))
        except Exception:  # noqa: BLE001
            LOGGER.exception("unexpected request failure")
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, _error_payload("internal_error", "internal server error"))

    def _handle_normalize(self, payload: Mapping[str, Any]) -> None:
        if "text" not in payload:
            self._send_json(HTTPStatus.BAD_REQUEST, _error_payload("missing_text", "field 'text' is required"))
            return
        result = self.runtime.process(payload["text"])  # type: ignore[arg-type]
        self._send_json(HTTPStatus.OK, {"schema_version": 1, "result": result.to_dict()})

    def _handle_stream(self, payload: Mapping[str, Any]) -> None:
        source_path = payload.get("source_path")
        output_path = payload.get("output_path")
        checkpoint_path = payload.get("checkpoint_path")
        if not (
            isinstance(source_path, str)
            and source_path.strip()
            and isinstance(output_path, str)
            and output_path.strip()
            and isinstance(checkpoint_path, str)
            and checkpoint_path.strip()
        ):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                _error_payload(
                    "invalid_stream_paths", "source_path, output_path, and checkpoint_path are required strings"
                ),
            )
            return
        assert isinstance(source_path, str)
        assert isinstance(output_path, str)
        assert isinstance(checkpoint_path, str)
        source_path = _resolve_stream_path(source_path, self.streaming_root)
        output_path = _resolve_stream_path(output_path, self.streaming_root)
        checkpoint_path = _resolve_stream_path(checkpoint_path, self.streaming_root)
        resume = payload.get("resume", True)
        batch_size = payload.get("batch_size", 32)
        workers = payload.get("workers", 1)
        max_input_bytes = payload.get("max_input_bytes", 1024 * 1024 * 1024)
        if not isinstance(resume, bool):
            raise ValueError("resume must be boolean")
        for name, value in (("batch_size", batch_size), ("workers", workers), ("max_input_bytes", max_input_bytes)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        report = StreamingSession(
            self.runtime.get_pipeline(),
            source_path,
            output_path,
            checkpoint_path,
            batch_size=batch_size,
            n_workers=workers,
            max_input_bytes=max_input_bytes,
            lock_enabled=True,
        ).run(resume=resume)
        self._send_json(HTTPStatus.OK, {"schema_version": 1, "report": report.to_dict()})

    def _handle_batch(self, payload: Mapping[str, Any]) -> None:
        texts = payload.get("texts")
        if not isinstance(texts, list) or not all(isinstance(item, str) for item in texts):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                _error_payload("invalid_texts", "field 'texts' must be a list of strings"),
            )
            return
        if not texts:
            self._send_json(HTTPStatus.BAD_REQUEST, _error_payload("empty_batch", "field 'texts' cannot be empty"))
            return
        batch_size = payload.get("batch_size", 32)
        workers = payload.get("workers", 1)
        if isinstance(batch_size, bool) or not isinstance(batch_size, int):
            raise ValueError("batch_size must be an integer")
        if isinstance(workers, bool) or not isinstance(workers, int):
            raise ValueError("workers must be an integer")
        results = self.runtime.process_batch(texts, batch_size=batch_size, n_workers=workers)
        self._send_json(
            HTTPStatus.OK,
            {"schema_version": 1, "count": len(results), "results": [result.to_dict() for result in results]},
        )


class ConfigReloadWatcher:
    """Poll a config file and publish successful changes atomically."""

    def __init__(
        self,
        runtime: PipelineRuntime,
        path: Union[str, os.PathLike[str]],
        interval: float,
        *,
        reload: Optional[Callable[[Union[str, os.PathLike[str]]], Any]] = None,
    ) -> None:
        if interval <= 0:
            raise ValueError("reload interval must be positive")
        self.runtime = runtime
        self.path = os.fspath(path)
        self.interval = interval
        self._reload = reload or runtime.reload_from_file
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="aranorm-config-reloader", daemon=True)
        self._last_mtime: Optional[int]
        try:
            self._last_mtime = os.stat(self.path).st_mtime_ns
        except OSError:
            self._last_mtime = None

    def start(self) -> None:
        """Start the daemon watcher."""
        self._thread.start()

    def stop(self) -> None:
        """Stop the watcher and wait briefly for its thread."""
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval + 0.5))

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                mtime = os.stat(self.path).st_mtime_ns
            except OSError:
                continue
            if mtime == self._last_mtime:
                continue
            self._last_mtime = mtime
            outcome = self._reload(self.path)
            if not outcome.success:
                LOGGER.error("configuration reload failed: %s", outcome.error_message or "unknown error")
            else:
                LOGGER.info("configuration reloaded at generation %s", outcome.generation)


class AraNormHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server carrying a shared pipeline runtime."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: Tuple[str, int],
        runtime: PipelineRuntime,
        *,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        streaming_enabled: bool = False,
        streaming_root: Optional[Union[str, os.PathLike[str]]] = None,
        handler_class: Type[AraNormRequestHandler] = AraNormRequestHandler,
    ) -> None:
        if isinstance(max_body_bytes, bool) or not isinstance(max_body_bytes, int) or max_body_bytes < 1:
            raise ValueError("max_body_bytes must be a positive integer")
        if not isinstance(streaming_enabled, bool):
            raise ValueError("streaming_enabled must be boolean")
        normalized_root: Optional[str] = None
        if streaming_root is not None:
            normalized_root = os.path.realpath(os.fspath(streaming_root))
            if not os.path.isdir(normalized_root):
                raise ValueError("streaming_root must be an existing directory")
        bound_handler = type(
            "BoundAraNormRequestHandler",
            (handler_class,),
            {
                "runtime": runtime,
                "max_body_bytes": max_body_bytes,
                "streaming_enabled": streaming_enabled,
                "streaming_root": normalized_root,
            },
        )
        super().__init__(server_address, bound_handler)
        self.runtime = runtime


def create_server(
    runtime: PipelineRuntime,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    streaming_enabled: bool = False,
    streaming_root: Optional[Union[str, os.PathLike[str]]] = None,
) -> AraNormHTTPServer:
    """Create, but do not start, an AraNorm HTTP server."""
    return AraNormHTTPServer(
        (host, port),
        runtime,
        max_body_bytes=max_body_bytes,
        streaming_enabled=streaming_enabled,
        streaming_root=streaming_root,
    )


def serve(
    runtime: PipelineRuntime,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    config_path: Optional[Union[str, os.PathLike[str]]] = None,
    reload_interval: float = 0.0,
    spec_path: Optional[Union[str, os.PathLike[str]]] = None,
    streaming_enabled: bool = False,
    streaming_root: Optional[Union[str, os.PathLike[str]]] = None,
) -> None:
    """Run the opt-in HTTP server until interrupted.

    When a config or spec path and a positive ``reload_interval`` are supplied,
    a daemon watcher reloads changed files without interrupting requests that
    are already using the previous snapshot. The two path modes are mutually
    exclusive.
    """
    if config_path is not None and spec_path is not None:
        raise ValueError("config_path and spec_path are mutually exclusive")
    server = create_server(
        runtime,
        host,
        port,
        max_body_bytes=max_body_bytes,
        streaming_enabled=streaming_enabled,
        streaming_root=streaming_root,
    )
    watcher: Optional[ConfigReloadWatcher] = None
    watched_path = spec_path or config_path
    reload = runtime.reload_from_spec_file if spec_path is not None else runtime.reload_from_file
    if watched_path is not None and reload_interval > 0:
        if spec_path is not None:
            watcher = ConfigReloadWatcher(runtime, watched_path, reload_interval, reload=reload)
        else:
            watcher = ConfigReloadWatcher(runtime, watched_path, reload_interval)
        watcher.start()
    try:
        server.serve_forever()
    finally:
        if watcher is not None:
            watcher.stop()
        server.server_close()
