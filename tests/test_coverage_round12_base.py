"""Round 12 coverage hardening: ProcessorContext trace/merge contracts and Processor base.

Behavior-verifying tests for the previously uncovered branches in
``src/aranorm/core/base.py``. Pure unit tests; deterministic; no I/O.
"""

from __future__ import annotations

import pytest

from aranorm.core.base import Processor, ProcessorContext


class _ProbeProcessor(Processor):
    name = "probe"

    def process(self, text: str, context: ProcessorContext = None) -> str:  # noqa: D401
        return text


class _FailingProcessor(Processor):
    name = "failing"

    def process(self, text: str, context: ProcessorContext = None) -> str:
        raise RuntimeError("boom")


# --------------------------------------------------------------------------
# record / record_always with tracing enabled and disabled
# --------------------------------------------------------------------------


def test_record_avoids_duplicates_without_trace() -> None:
    ctx = ProcessorContext()
    ctx.record("a")
    ctx.record("a")
    assert ctx.applied_steps == ["a"]
    assert ctx.steps_trace() == []


def test_record_appends_trace_when_enabled() -> None:
    ctx = ProcessorContext()
    ctx.enable_trace()
    ctx.record("a")
    ctx.record("a")  # trace still records even on duplicates
    assert ctx.applied_steps == ["a"]
    assert ctx.steps_trace() == [("a", "record"), ("a", "record")]


def test_record_always_appends_unconditionally() -> None:
    ctx = ProcessorContext()
    ctx.record_always("a")
    ctx.record_always("a")
    assert ctx.applied_steps == ["a", "a"]


def test_record_always_records_trace_action() -> None:
    ctx = ProcessorContext()
    ctx.enable_trace()
    ctx.record("a")
    ctx.record_always("b")
    assert ctx.steps_trace() == [("a", "record"), ("b", "record_always")]


def test_record_always_without_trace_keeps_context_clean() -> None:
    ctx = ProcessorContext()
    ctx.record_always("a")
    ctx.record_always("a")
    assert ctx.applied_steps == ["a", "a"]
    assert ctx.steps_trace() == []


# --------------------------------------------------------------------------
# set / get metadata
# --------------------------------------------------------------------------


def test_set_get_round_trip() -> None:
    ctx = ProcessorContext()
    ctx.set("k", 42)
    assert ctx.get("k") == 42


def test_get_missing_key_returns_default() -> None:
    ctx = ProcessorContext()
    assert ctx.get("missing") is None
    assert ctx.get("missing", default="fallback") == "fallback"


# --------------------------------------------------------------------------
# merge semantics
# --------------------------------------------------------------------------


def test_merge_appends_unique_steps_and_overwrites_metadata() -> None:
    a = ProcessorContext()
    a.record("x")
    a.set("k", 1)
    b = ProcessorContext()
    b.record("x")  # duplicate across contexts
    b.record("y")
    b.set("k", 2)
    b.set("m", 9)
    a.merge(b)
    assert a.applied_steps == ["x", "y"]
    assert a.get("k") == 2
    assert a.get("m") == 9


def test_merge_without_tracing_on_either_side() -> None:
    a = ProcessorContext()
    a.record("x")
    b = ProcessorContext()
    b.record("y")
    a.merge(b)
    assert a.steps_trace() == []


def test_merge_with_tracing_on_target_only() -> None:
    a = ProcessorContext()
    a.enable_trace()
    a.record("x")
    b = ProcessorContext()
    b.record("y")
    b.set("k", 7)
    a.merge(b)
    # target traced, source not traced: merge replays source steps through record()
    assert a.steps_trace() == [("x", "record"), ("y", "record")]
    assert a.get("k") == 7


def test_merge_with_tracing_on_source_only() -> None:
    a = ProcessorContext()
    b = ProcessorContext()
    b.enable_trace()
    b.record("y")
    a.merge(b)
    assert a.steps_trace() == []


def test_merge_with_tracing_on_both_records_merge_actions() -> None:
    a = ProcessorContext()
    a.enable_trace()
    a.record("x")
    b = ProcessorContext()
    b.enable_trace()
    b.record("y")
    a.merge(b)
    # source step is recorded via record() ("record"), then annotated as merge
    trace = a.steps_trace()
    assert trace == [("x", "record"), ("y", "record"), ("y", "merge")]


def test_merge_with_empty_source() -> None:
    a = ProcessorContext()
    a.enable_trace()
    a.record("x")
    a.merge(ProcessorContext())
    assert a.applied_steps == ["x"]
    assert a.steps_trace() == [("x", "record")]


# --------------------------------------------------------------------------
# Processor base class
# --------------------------------------------------------------------------


def test_processor_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        Processor()  # type: ignore[abstract]


def test_processor_subclass_is_callable() -> None:
    probe = _ProbeProcessor()
    assert probe.process("سلام") == "سلام"
    assert probe.name == "probe"


def test_processor_exception_propagates_to_pipeline_error_paths() -> None:
    proc = _FailingProcessor()
    with pytest.raises(RuntimeError, match="boom"):
        proc.process("anything")


def test_processor_records_into_provided_context() -> None:
    """``Processor._record`` must append the processor name when context is given."""
    probe = _ProbeProcessor()
    ctx = ProcessorContext()
    probe._record(ctx)
    assert ctx.applied_steps == ["probe"]


def test_processor_record_with_none_context_is_noop() -> None:
    """Passing ``None`` must be silently ignored, keeping contracts stable."""
    probe = _ProbeProcessor()
    probe._record(None)
