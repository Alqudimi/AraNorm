import json
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Iterator, Tuple

from aranorm import PipelineRuntime
from aranorm.server import create_server


@contextmanager
def running_stream_server(*, streaming_enabled: bool, streaming_root=None) -> Iterator[str]:
    server = create_server(
        PipelineRuntime(),
        "127.0.0.1",
        0,
        streaming_enabled=streaming_enabled,
        streaming_root=streaming_root,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(base: str, path: str, payload: dict) -> Tuple[int, dict]:
    request_obj = urllib.request.Request(
        base + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request_obj, timeout=3)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))
    return response.status, json.loads(response.read().decode("utf-8"))


def test_stream_endpoint_is_opt_in(tmp_path):
    with running_stream_server(streaming_enabled=False) as base:
        status, payload = request(
            base,
            "/v1/stream",
            {
                "source_path": str(tmp_path / "source.txt"),
                "output_path": str(tmp_path / "out.jsonl"),
                "checkpoint_path": str(tmp_path / "state.json"),
            },
        )
    assert status == 404
    assert payload["error"]["code"] == "not_found"


def test_stream_endpoint_processes_and_resumes_local_files(tmp_path):
    source = tmp_path / "source.txt"
    output = tmp_path / "nested" / "out.jsonl"
    checkpoint = tmp_path / "state" / "checkpoint.json"
    source.write_text("الأول\nالثاني\n", encoding="utf-8")
    payload = {
        "source_path": str(source),
        "output_path": str(output),
        "checkpoint_path": str(checkpoint),
        "batch_size": 1,
        "workers": 1,
        "resume": False,
    }
    with running_stream_server(streaming_enabled=True) as base:
        first_status, first = request(base, "/v1/stream", payload)
        payload["resume"] = True
        second_status, second = request(base, "/v1/stream", payload)

    assert first_status == 200
    assert first["schema_version"] == 1
    assert first["report"]["completed"] is True
    assert first["report"]["processed_count"] == 2
    assert second_status == 200
    assert second["report"]["resumed"] is True
    assert second["report"]["completed"] is True
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2


def test_stream_endpoint_rejects_paths_outside_configured_root(tmp_path):
    root = tmp_path / "allowed"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    source = outside / "source.txt"
    source.write_text("خارج الجذر\n", encoding="utf-8")
    with running_stream_server(streaming_enabled=True, streaming_root=str(root)) as base:
        status, payload = request(
            base,
            "/v1/stream",
            {
                "source_path": str(source),
                "output_path": str(root / "output.jsonl"),
                "checkpoint_path": str(root / "checkpoint.json"),
                "resume": False,
            },
        )
    assert status == 403
    assert payload["error"]["code"] == "stream_path_forbidden"


def test_stream_endpoint_validates_paths_and_numeric_options(tmp_path):
    with running_stream_server(streaming_enabled=True) as base:
        missing_status, missing = request(base, "/v1/stream", {"resume": False})
        invalid_status, invalid = request(
            base,
            "/v1/stream",
            {
                "source_path": str(tmp_path / "source.txt"),
                "output_path": str(tmp_path / "out.jsonl"),
                "checkpoint_path": str(tmp_path / "state.json"),
                "batch_size": 0,
            },
        )

    assert missing_status == 400
    assert missing["error"]["code"] == "invalid_stream_paths"
    assert invalid_status == 422
    assert invalid["error"]["code"] == "invalid_request"
