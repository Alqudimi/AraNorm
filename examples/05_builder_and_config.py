"""Example 05: Builder pattern and config serialization.

Demonstrates the fluent builder API and JSON/YAML config serialization.
"""

import json

from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

# ── 1. Builder pattern ────────────────────────────────────────────────────────
pipeline = (
    ArabicNormalizationPipeline.builder()
    .add_cleaner(urls=True, html=True, emojis=True)
    .add_normalizer(
        normalize_alef=True,
        normalize_hamza=True,
        normalize_diacritics=True,
        normalize_tatweel=True,
    )
    .add_dialect_processor(
        normalize_to="msa",
        supported_dialects=["EGY", "GLF", "LEV"],
    )
    .build()
)

result = pipeline.process("شو أخبارك؟ عم بعمل شي وايد مهم")
print("Builder pipeline:")
print(f"  Input:   {result.original_text}")
print(f"  Output:  {result.normalized_text}")
print(f"  MSA:     {result.msa_text}")
print(f"  Dialect: {result.dialect}")
print()

# ── 2. Config serialization (JSON) ────────────────────────────────────────────
config = PipelineConfig(
    preset="deep",
    dialect_target="coda",
    clean_emojis=True,
    stop_words_config=StopWordsConfig(
        mode="remove",
        scope="universal",
        preserve_negation=True,
    ),
)

# Serialize to JSON
json_str = config.to_json()
print("Config as JSON (first 200 chars):")
print(f"  {json_str[:200]}...")
print()

# Round-trip: JSON → Config
config2 = PipelineConfig.from_json(json_str)
print("Round-trip verification:")
print(f"  preset:          {config2.preset.value}")
print(f"  dialect_target:  {config2.dialect_target.value}")
print(f"  stop_words mode: {config2.stop_words_config.mode}")
print(f"  Match:           {config.to_dict() == config2.to_dict()}")
print()

# ── 3. Config derivation ──────────────────────────────────────────────────────
base = PipelineConfig(preset="standard")
social = base.copy_with(preset="social_media", clean_emojis=True)
print("Config derivation (copy_with):")
print(f"  base.preset:    {base.preset.value}")
print(f"  social.preset:  {social.preset.value}")
print(f"  Same object?    {base is social}")
print()

# ── 4. Config validation ──────────────────────────────────────────────────────
try:
    bad_config = PipelineConfig(
        stop_words_config=StopWordsConfig(
            scope="dialect_aware",
            dialects=frozenset(),  # ← requires at least one dialect
        )
    )
    bad_config.validate()
except Exception as e:
    print(f"Validation caught: {type(e).__name__}: {e}")

# ── 5. Pipeline describe() ────────────────────────────────────────────────────
desc = pipeline.describe()
print("\nPipeline description:")
print(json.dumps(desc, ensure_ascii=False, indent=2))
