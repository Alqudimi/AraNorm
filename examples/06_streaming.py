"""Example 06: Resumable streaming sessions.

Demonstrates crash-safe processing of large line-per-item files with
atomic checkpoints — the pattern for normalizing millions of texts.
"""

import tempfile
from pathlib import Path

from aranorm import (
    ArabicNormalizationPipeline,
    PipelineConfig,
    StreamCheckpoint,
    StreamingSession,
)

# ── 1. Prepare a demo corpus: one text per line ────────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="aranorm-stream-"))
source = tmp / "corpus.jsonl"
output = tmp / "normalized.jsonl"
checkpoint_path = tmp / "checkpoint.json"

corpus = [
    "أهلاً وسهلاً بكم في المؤتمر السنوي",
    "شلونكم اليوم يا أهل الخليج؟",
    "إزيك عامل إيه النهاردة؟",
    "كيف حالك أخي الكريم؟",
    "ودي نروح السوق بس ما عندي سيارة",
    "خلينا نتعشى برة اليوم، شو رأيكم؟",
    "نحب نروح للمقهى و نتواجه مع الصحبة",
    "The quick brown fox jumps over the lazy dog",
]
source.write_text("\n".join(corpus), encoding="utf-8")

# ── 2. Build the pipeline (fingerprint is part of the checkpoint identity) ────
pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))

# ── 3. Run a streaming session ────────────────────────────────────────────────
session = StreamingSession(
    pipeline,
    source_path=str(source),
    output_path=str(output),
    checkpoint_path=str(checkpoint_path),
    batch_size=4,       # commit a checkpoint every 4 items
    n_workers=1,
    lock_enabled=True,  # prevent a second writer on the same checkpoint
)

report = session.run(resume=True)
print("First run:")
print(f"  processed:  {report.processed_count}")
print(f"  resumed:    {report.resumed}")
print(f"  completed:  {report.completed}")
print(f"  output:     {report.output_path}")
print()

# ── 4. Inspect the checkpoint ─────────────────────────────────────────────────
checkpoint = StreamCheckpoint.load(str(checkpoint_path))
print("Checkpoint after run:")
print(f"  next_index:         {checkpoint.next_index}")
print(f"  completed:          {checkpoint.completed}")
print(f"  source fingerprint: {checkpoint.source_fingerprint[:16]}...")
print()

# ── 5. Re-running is a no-op: fully processed sources are skipped ─────────────
report2 = session.run(resume=True)
print("Second run (already complete):")
print(f"  processed:  {report2.processed_count}")
print(f"  resumed:    {report2.resumed}")
print(f"  completed:  {report2.completed}")
print()

# ── 6. Show the output ────────────────────────────────────────────────────────
print("Normalized output (first 4 lines):")
for line in output.read_text(encoding="utf-8").splitlines()[:4]:
    print(f"  {line[:80]}")
print(f"... ({len(output.read_text(encoding='utf-8').splitlines())} lines total)")
