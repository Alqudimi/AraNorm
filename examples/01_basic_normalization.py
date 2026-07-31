"""Example 01: Basic Arabic text normalization.

Demonstrates the core normalization features using different presets.
"""

from aranorm import ArabicNormalizationPipeline, PipelineConfig

# ── 1. Default (standard) preset ──────────────────────────────────────────────
pipeline = ArabicNormalizationPipeline()
result = pipeline.process("أهـلاً وَسَهـلاً بِكُم! https://example.com 😊")
print("Standard preset:")
print(f"  Input:    {result.original_text}")
print(f"  Output:   {result.normalized_text}")
print(f"  Dialect:  {result.dialect} ({result.dialect_confidence:.0%})")
print(f"  Steps:    {result.applied_steps}")
print()

# ── 2. Light preset (fastest, dependency-free) ────────────────────────────────
pipeline_light = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
texts = ["أحمد", "إبراهيم", "آمن", "مَرْحَبًا"]
results = pipeline_light.process_batch(texts)
print("Light preset (batch):")
for r in results:
    print(f"  {r.original_text!r:20} → {r.normalized_text!r}")
print()

# ── 3. Social media preset ────────────────────────────────────────────────────
pipeline_social = ArabicNormalizationPipeline(PipelineConfig(preset="social_media"))
tweet = "RT @user: شلونكم؟؟؟ #موضوع_مثير https://t.co/abc 😂😂😂"
result = pipeline_social.process(tweet)
print("Social media preset:")
print(f"  Input:  {tweet}")
print(f"  Output: {result.normalized_text}")
print()

# ── 4. Deep preset with dialect normalization ─────────────────────────────────
pipeline_deep = ArabicNormalizationPipeline(
    PipelineConfig(preset="deep", dialect_target="msa")
)
result = pipeline_deep.process("شلون الحين أبغى شيء يسوي")
print("Deep + MSA normalization:")
print(f"  Input:   {result.original_text}")
print(f"  Output:  {result.normalized_text}")
print(f"  MSA:     {result.msa_text}")
print(f"  Dialect: {result.dialect}")
