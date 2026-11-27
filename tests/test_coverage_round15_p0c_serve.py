"""Round 15 P0c — serve() lifecycle coverage without hanging.

Patches ``serve_forever`` / ``server_close`` so the real ``serve()``
function body (including watcher start/stop and the spec_path reload
branch) executes without blocking, while still constructing a real
``AraNormHTTPServer`` bound to a socket.
"""

from __future__ import annotations

import pathlib
from unittest import mock

from aranorm.core.runtime import PipelineRuntime
from aranorm.server import serve


def test_serve_with_live_watcher():
    """serve() with a config_path builds a watcher, starts it, stops it,
    and closes the server in the finally block."""
    runtime = PipelineRuntime()
    config = pathlib.Path("/tmp/aranorm_r15_cfg.json")
    config.write_text("{}")
    port = 0

    with (
        mock.patch("aranorm.server.ConfigReloadWatcher") as watcher_cls,
        mock.patch("aranorm.server.AraNormHTTPServer.serve_forever"),
        mock.patch("aranorm.server.AraNormHTTPServer.server_close"),
    ):
        serve(runtime, config_path=str(config), reload_interval=0.05, port=port)
        watcher_cls.assert_called_once()
        watcher_cls.return_value.start.assert_called_once()
        watcher_cls.return_value.stop.assert_called_once()


def test_serve_spec_path_reload():
    """serve() with a spec_path wires reload_from_spec_file into the
    watcher and still performs the stop/close lifecycle."""
    runtime = PipelineRuntime()
    tmp = pathlib.Path("/tmp/aranorm_r15_spec")
    tmp.mkdir(exist_ok=True)
    spec = tmp / "spec.json"
    spec.write_text("{}")

    with (
        mock.patch("aranorm.server.ConfigReloadWatcher") as watcher_cls,
        mock.patch("aranorm.server.AraNormHTTPServer.serve_forever"),
        mock.patch("aranorm.server.AraNormHTTPServer.server_close"),
    ):
        serve(runtime, spec_path=str(spec), reload_interval=0.05)
        watcher_cls.assert_called_once()
        # reload is passed as the fourth positional argument (keyword-only
        # ``reload`` in ConfigReloadWatcher.__init__)
        call_args = watcher_cls.call_args
        passed_reload = call_args.args[3] if len(call_args.args) > 3 else call_args.kwargs.get("reload")
        assert passed_reload.__func__ is runtime.reload_from_spec_file.__func__
        watcher_cls.return_value.start.assert_called_once()
        watcher_cls.return_value.stop.assert_called_once()
