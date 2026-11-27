"""Regression tests for bounded streaming processing and exports."""

import csv
import io
import json

import pytest

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.utils.cache import NormalizationCache
from aranorm.utils.exporters import StreamingBatchExporter


def test_process_iter_consumes_generator_in_order_with_workers():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    source = (f"نص {index}" for index in range(17))

    results = list(pipeline.process_iter(source, batch_size=3, n_workers=3))

    assert [result.original_text for result in results] == [f"نص {index}" for index in range(17)]


def test_process_iter_rejects_invalid_bounds():
    pipeline = ArabicNormalizationPipeline()
    with pytest.raises(ValueError, match="batch_size"):
        list(pipeline.process_iter([], batch_size=0))
    with pytest.raises(ValueError, match="n_workers"):
        list(pipeline.process_iter([], n_workers=0))
    with pytest.raises(ValueError, match="total"):
        list(pipeline.process_iter([], total=-1))


def test_streaming_exporter_writes_jsonl_without_materializing_results():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    exporter = StreamingBatchExporter()
    output = io.StringIO()

    count = exporter.write_jsonl(
        pipeline.process_iter(("أحمد", "إبراهيم"), batch_size=1),
        output,
    )

    assert count == 2
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [row["original_text"] for row in rows] == ["أحمد", "إبراهيم"]


def test_streaming_exporter_writes_valid_csv_and_json():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    exporter = StreamingBatchExporter(fields=["original_text", "normalized_text"])
    results = pipeline.process_iter(("أحمد", "إبراهيم"), batch_size=1)

    csv_output = io.StringIO()
    assert exporter.write_csv(results, csv_output, encoding="utf-8") == 2
    csv_output.seek(0)
    rows = list(csv.DictReader(csv_output))
    assert rows[0]["normalized_text"] == "احمد"

    json_output = io.StringIO()
    assert (
        exporter.write_json(
            pipeline.process_iter(("أحمد", "إبراهيم"), batch_size=1),
            json_output,
        )
        == 2
    )
    assert len(json.loads(json_output.getvalue())) == 2


def test_streaming_exporter_rejects_unknown_format():
    with pytest.raises(ValueError, match="format"):
        StreamingBatchExporter().write([], io.StringIO(), format="xml")  # type: ignore[arg-type]


def test_cache_process_iter_is_bounded_and_reuses_results():
    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
    cache = NormalizationCache(pipeline, maxsize=8)

    first = list(cache.process_iter(("أحمد", "إبراهيم", "أحمد"), batch_size=2, n_workers=2))
    second = list(cache.process_iter(("أحمد", "إبراهيم"), batch_size=1))

    assert [result.original_text for result in first] == ["أحمد", "إبراهيم", "أحمد"]
    assert [result.normalized_text for result in second] == ["احمد", "ابراهيم"]
    stats = cache.stats()
    assert stats["hits"] >= 2
    assert stats["misses"] >= 2


def test_cache_rejects_invalid_streaming_options():
    cache = NormalizationCache(ArabicNormalizationPipeline(), maxsize=2)
    with pytest.raises(ValueError, match="batch_size"):
        list(cache.process_iter([], batch_size=0))
    with pytest.raises(ValueError, match="n_workers"):
        cache.process_batch([], n_workers=0)


def test_config_factory_keeps_strict_validation_for_nested_options():
    with pytest.raises(ValueError, match="Unknown PipelineConfig field"):
        ArabicNormalizationPipeline.from_config_dict({"presett": "light"})

    pipeline = ArabicNormalizationPipeline.from_config_dict(
        {
            "preset": "social_media",
            "stop_words_config": {
                "mode": "remove",
                "scope": "universal",
                "remove_filler": True,
            },
        }
    )
    assert pipeline.config.preset.value == "social_media"
    assert pipeline.config.stop_words_config is not None
