# Configuration Reference

This document covers every configuration option in `PipelineConfig` and `StopWordsConfig`.

---

## PipelineConfig

```python
from aranorm import PipelineConfig

config = PipelineConfig(
    preset="standard",           # "light" | "standard" | "deep" | "social_media"
    dialect_target="none",       # "none" | "coda" | "msa"
    remove_diacritics=True,
    normalize_hamza=True,
    normalize_alef=True,
    normalize_tatweel=True,
    normalize_unicode=True,
    normalize_digits=True,
    normalize_taa_marbuta=False,
    normalize_alef_maqsura=True,
    normalize_ligatures=True,
    normalize_punctuation=True,
    normalize_whitespace=True,
    normalize_repeated_chars=False,
    remove_extra_punctuation=False,
    clean_urls=True,
    clean_emails=True,
    clean_html=True,
    clean_mentions=False,
    clean_hashtags=False,
    clean_emojis=False,
    remove_non_arabic=False,
    remove_english=False,
    fix_spacing=True,
    handle_arabizi=False,
    supported_dialects=[],       # [] = all dialects
    stop_words_config=None,      # StopWordsConfig or None
)
```

### Preset Profiles

| Flag | `light` | `standard` | `deep` | `social_media` |
|------|:-------:|:----------:|:------:|:--------------:|
| `clean_urls` | ❌ | ✅ | ✅ | ✅ |
| `clean_emails` | ❌ | ✅ | ✅ | ✅ |
| `clean_html` | ❌ | ✅ | ✅ | ✅ |
| `clean_mentions` | ❌ | ❌ | ❌ | ✅ |
| `clean_emojis` | ❌ | ❌ | ❌ | ✅ |
| `normalize_alef` | ✅ | ✅ | ✅ | ✅ |
| `normalize_hamza` | ✅ | ✅ | ✅ | ✅ |
| `remove_diacritics` | ✅ | ✅ | ✅ | ✅ |
| `normalize_repeated_chars` | ❌ | ❌ | ✅ | ✅ |
| `fix_spacing` | ✅ | ✅ | ✅ | ✅ |

---

## StopWordsConfig

```python
from aranorm import StopWordsConfig

sw_config = StopWordsConfig(
    mode="remove",               # "remove" | "extract" | "highlight" | "count"
    scope="universal",           # "universal" | "msa_only" | "dialect_aware" | "custom"
    dialects=frozenset(),        # Dialect codes for "dialect_aware" scope
    preserve_negation=True,      # Keep negation particles (لا، لم، لن، ما)
    preserve_emphasis=False,     # Keep emphasis particles (جداً، كثيراً)
    preserve_prepositions=False, # Keep common prepositions
    remove_filler=True,          # Remove filler words (مش، بس، يعني…)
    remove_arabizi=False,        # Remove Arabizi filler words
    remove_internet=False,       # Remove internet/social-media noise
    remove_numbers=False,        # Remove Arabic numerals
    custom_stop_words=None,      # frozenset of custom stop words
    excluded_stop_words=None,    # frozenset of words to never remove
)
```

### Mode Descriptions

| Mode | Description | Populates |
|------|-------------|-----------|
| `remove` | Remove stop words from text | `stop_words_removed`, `stop_words_found` |
| `extract` | Return only the stop words found | `stop_words_found` |
| `highlight` | Wrap stop words in `[[...]]` markers | `stop_words_removed` |
| `count` | Count stop words by category | `stop_words_stats` |

### Scope Descriptions

| Scope | Description |
|-------|-------------|
| `universal` | All stop words (MSA + all dialects) |
| `msa_only` | Modern Standard Arabic stop words only |
| `dialect_aware` | MSA + stop words for specified dialects |
| `custom` | Only the words in `custom_stop_words` |

---

## Serialization

```python
# To / from JSON
json_str = config.to_json()
config2 = PipelineConfig.from_json(json_str)

# To / from YAML (requires PyYAML)
yaml_str = config.to_yaml()
config3 = PipelineConfig.from_yaml(yaml_str)

# From file (.json, .yaml, .yml)
config4 = PipelineConfig.from_file("pipeline.json")

# Immutable derivation
social = config.copy_with(preset="social_media", clean_emojis=True)

# Validation (raises ConfigurationError on bad config)
config.validate()
```

---

## CLI Configuration

The CLI accepts preset flags and output options:

```bash
aranorm normalize "نص" --preset deep
aranorm normalize "نص" --preset standard --remove-diacritics --no-urls
aranorm batch --file texts.txt --format csv --output results.csv --workers 4
```

See `aranorm --help` and `aranorm <command> --help` for full options.
