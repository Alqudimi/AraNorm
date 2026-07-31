"""Example 02: Stop-word removal and analysis.

Demonstrates the stop-words subsystem with different modes and scopes.
"""

from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

# ── 1. Remove mode (universal scope) ─────────────────────────────────────────
config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
)
pipeline = ArabicNormalizationPipeline(config)
result = pipeline.process("أنا سعيد جداً اليوم في المدرسة")
print("Mode=remove, scope=universal:")
print(f"  Original: {result.original_text}")
print(f"  Cleaned:  {result.stop_words_removed}")
print(f"  Removed:  {result.stop_words_found}")
print()

# ── 2. Count mode ─────────────────────────────────────────────────────────────
config_count = PipelineConfig(
    stop_words_config=StopWordsConfig(mode="count", scope="universal"),
)
pipeline_count = ArabicNormalizationPipeline(config_count)
result = pipeline_count.process("الرجل الذي كان في المدينة لأنه أراد أن يرى ما هناك")
print("Mode=count:")
print(f"  Stats: {result.stop_words_stats}")
print()

# ── 3. Dialect-aware scope ────────────────────────────────────────────────────
config_dialect = PipelineConfig(
    stop_words_config=StopWordsConfig(
        mode="remove",
        scope="dialect_aware",
        dialects=frozenset({"EGY", "GLF"}),
    ),
)
pipeline_dialect = ArabicNormalizationPipeline(config_dialect)
result = pipeline_dialect.process("عايز أروح بس مش عارف ليه")
print("Mode=remove, scope=dialect_aware (EGY+GLF):")
print(f"  Original: {result.original_text}")
print(f"  Cleaned:  {result.stop_words_removed}")
print()

# ── 4. Preserve negation ─────────────────────────────────────────────────────
config_neg = PipelineConfig(
    stop_words_config=StopWordsConfig(
        mode="remove",
        scope="universal",
        preserve_negation=True,  # keeps لا، لم، لن، ما
    ),
)
pipeline_neg = ArabicNormalizationPipeline(config_neg)
result = pipeline_neg.process("أنا لا أحب هذا الطقس في اليوم")
print("Preserve negation:")
print(f"  Original: {result.original_text}")
print(f"  Cleaned:  {result.stop_words_removed}")

# ── 5. Custom stop words ──────────────────────────────────────────────────────
config_custom = PipelineConfig(
    stop_words_config=StopWordsConfig(
        mode="remove",
        scope="custom",
        custom_stop_words=frozenset({"هذا", "هذه", "ذلك", "تلك", "الذي", "التي"}),
    ),
)
pipeline_custom = ArabicNormalizationPipeline(config_custom)
result = pipeline_custom.process("هذا الكتاب الذي اشتريته أمس")
print("\nCustom stop words:")
print(f"  Original: {result.original_text}")
print(f"  Cleaned:  {result.stop_words_removed}")
