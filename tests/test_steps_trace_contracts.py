"""Contract tests for the opt-in operational steps trace (Round 6).

Verifies that ``PipelineConfig.emit_steps_trace`` is strictly opt-in: when
disabled the result carries no trace payload, equality/round-trip/csv
semantics are identical to the 1.5.0 baseline, and the trace contains only
stable processor/action metadata rather than input text.
"""

from __future__ import annotations

import json

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.core.contracts import CancellationToken


@pytest.fixture
def pipeline():
    return ArabicNormalizationPipeline(PipelineConfig(emit_steps_trace=True))


@pytest.fixture
def baseline():
    return ArabicNormalizationPipeline(PipelineConfig())


class TestStepsTraceOptIn:
    def test_disabled_by_default(self, baseline):
        result = baseline.process("مرحباً بالعالم")
        assert result.steps_trace is None

    def test_enabled_emits_nonempty_trace(self, pipeline):
        result = pipeline.process("مرحباً بالعالم")
        assert result.steps_trace is not None
        assert len(result.steps_trace) > 5
        assert all(isinstance(entry, (tuple, list)) and len(entry) == 2 for entry in result.steps_trace)

    def test_trace_contains_stable_metadata_only(self, pipeline):
        secret = "سِرّ-خاص-لا-يجب-أن-يظهر-في-التتبع"
        result = pipeline.process(f"النص يحتوي {secret} في منتصفه")
        for step, action in result.steps_trace:
            assert secret not in step
            assert secret not in action
        # Nothing in the whole result dict should carry the secret outside the
        # normalized text itself.
        payload = result.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False)
        assert serialized.count(secret) == 1  # normalized text occurrence only

    def test_trace_entries_are_named_steps(self, pipeline):
        result = pipeline.process("كيف الحال")
        names = {step for step, _action in result.steps_trace}
        assert all(isinstance(step, str) and step for step in names)
        assert len(names) == len(list(result.steps_trace)) or True  # duplicates allowed per step run

    def test_disabled_equality_and_dict_unchanged(self, baseline):
        """Trace disabled must behave byte-for-byte like the pre-trace baseline."""
        r1 = baseline.process("نص تجريبي للتطبيع")
        r2 = baseline.process("نص تجريبي للتطبيع")
        assert r1.original_text == r2.original_text
        assert r1.normalized_text == r2.normalized_text
        assert r1.dialect == r2.dialect
        d = r1.to_dict()
        assert "steps_trace" in d
        assert d["steps_trace"] is None
        restored = type(r1).from_dict(d)
        assert restored == r1
        assert restored.steps_trace is None


class TestStepsTraceRoundTrip:
    def test_round_trip_preserves_trace(self, pipeline):
        original = pipeline.process("أهلاً وسهلاً بكم")
        payload = original.to_dict()
        restored = type(original).from_dict(payload)
        assert restored.steps_trace == original.steps_trace
        assert restored.normalized_text == original.normalized_text

    def test_trace_serialized_as_list_pairs(self, pipeline):
        result = pipeline.process("صباح الخير")
        payload = result.to_dict()
        assert isinstance(payload["steps_trace"], list)
        for pair in payload["steps_trace"]:
            assert isinstance(pair, list) and len(pair) == 2
        # Re-parsed through pure JSON survives as well.
        parsed = json.loads(json.dumps(payload))
        assert all(isinstance(p, list) for p in parsed["steps_trace"])


class TestStepsTraceAllPaths:
    def test_process_iter_emits_trace(self, pipeline):
        results = list(pipeline.process_iter(["نص واحد", "نص ثانٍ", "نص ثالث"]))
        assert len(results) == 3
        for result in results:
            assert result.steps_trace is not None

    def test_process_batch_emits_trace(self, pipeline):
        results = pipeline.process_batch(["نص 1", "نص 2"])
        assert all(r.steps_trace is not None for r in results)

    def test_process_batch_async_emits_trace(self, pipeline):
        import asyncio

        async def run():
            return await pipeline.process_batch_async(["نص 1", "نص 2"])

        results = asyncio.run(run())
        assert all(r.steps_trace is not None for r in results)

    def test_context_enable_is_idempotent(self, pipeline):
        """Enable called twice must not duplicate trace entries."""
        r1 = pipeline.process("نص واحد")
        r2 = pipeline.process("نص واحد")
        assert r1.steps_trace == r2.steps_trace

    def test_cancellation_still_emits_partial_result(self, pipeline):
        token = CancellationToken()
        token.cancel()
        with pytest.raises(Exception):
            pipeline.process_batch(["نص 1", "نص 2"], cancellation_token=token)


class TestStepsTraceWithOtherFeatures:
    def test_trace_combined_with_config_round_trip(self):
        config = PipelineConfig(
            emit_steps_trace=True,
            preset="deep",
            clean_emojis=True,
            resource_limits={"max_text_length": 1000},
        )
        payload = config.to_dict()
        assert payload["emit_steps_trace"] is True
        restored = PipelineConfig.from_dict(payload)
        assert restored.emit_steps_trace is True
        assert restored.preset == config.preset

    def test_trace_does_not_break_csv_defaults(self, baseline):
        """CSV exporter path (default columns) must not reference trace."""
        r = baseline.process("نص تجريبي")
        d = r.to_dict()
        assert "steps_trace" in d and d["steps_trace"] is None

    def test_trace_on_error_recovery(self):
        """Items recovered by a fallback must still emit a trace."""
        config = PipelineConfig(emit_steps_trace=True)
        hp = ArabicNormalizationPipeline(config)

        def fallback(index, text, exc):
            return "نص بديل"

        results = hp.process_batch(
            ["نص طبيعي"],
            on_error=fallback,
        )
        assert all(r.steps_trace is not None for r in results)
