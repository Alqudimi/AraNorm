"""Example 08: Batch processing — parallelism, retries, progress, and export.

Demonstrates the production batch patterns: worker pools, failure policies,
bounded retries, progress callbacks, and multi-format export.
"""

import tempfile
from pathlib import Path

from aranorm import (
    ArabicNormalizationPipeline,
    BatchRetryPolicy,
    PipelineConfig,
)
from aranorm.utils import ConsoleProgressCallback
from aranorm.utils import BatchExporter

# ── 1. A realistic mixed-quality corpus ───────────────────────────────────────
texts = [
    "أهلاً وسهلاً بكم",
    "شلونك اليوم؟",
    "إزيك عامل إيه؟",
    "The quick brown fox",
    "",                        # empty — handled gracefully
    "كيف حالك؟",
    "ودي أروح السوق",
    "٢٤٥ رقم عربي",
    "نحب نقعد في المقهى",
    "هذا نص طبيعي بالفصحى الجميلة",
] * 25  # 250 items

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))

# ── 2. Parallel batch with a progress bar ─────────────────────────────────────
progress = ConsoleProgressCallback(prefix="Normalizing", width=30)
results = pipeline.process_batch(
    texts,
    batch_size=64,
    n_workers=4,
    progress_callback=progress,
)
print(f"\nProcessed {len(results)} items")
print()

# ── 3. Export to every format ─────────────────────────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="aranorm-batch-"))
exporter = BatchExporter(results)

exporter.to_csv(tmp / "results.csv")        # utf-8-sig: opens cleanly in Excel
exporter.to_jsonl(tmp / "results.jsonl")    # one JSON object per line
exporter.to_json(tmp / "results.json")      # one JSON array

for path in sorted(tmp.iterdir()):
    print(f"  exported: {path.name} ({path.stat().st_size:,} bytes)")
print()

# ── 4. Batch with bounded retries ─────────────────────────────────────────────
retry_policy = BatchRetryPolicy(max_retries=3, batch_size=64, n_workers=2)
retry_report = pipeline.process_batch_retry(
    texts[:50],
    retry_policy=retry_policy,
)
print(f"Retry report: {len(retry_report.results)} succeeded, "
      f"{len(retry_report.failed_indices)} failed")
print(f"  attempts stats: {retry_report.retry_report}")
print()

# ── 5. Streaming iteration for huge corpora (constant memory) ─────────────────
count = 0
for result in pipeline.process_iter(texts, batch_size=100):
    count += 1
print(f"Streamed {count} items with constant memory")
print()

# ── 6. Metrics snapshot after all the work ────────────────────────────────────
snapshot = pipeline.metrics_snapshot()
print("Pipeline metrics:")
print(f"  total items:  {snapshot.total_items}")
print(f"  succeeded:    {snapshot.succeeded}")
print(f"  avg time:     {snapshot.average_time_ms:.2f} ms")
print(f"  throughput:   {snapshot.throughput_per_second:.0f} items/s")
