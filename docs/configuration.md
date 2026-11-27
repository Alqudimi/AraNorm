# Configuration — دليل الإعدادات الكامل

Every behavior of the AraNorm pipeline is controlled by one typed, validated dataclass: `PipelineConfig`. This guide documents **every field**, its type, default, and effect — plus the runtime `ResourceLimits`, validation rules, and serialization.

```python
from aranorm import PipelineConfig, ArabicNormalizationPipeline

config = PipelineConfig(preset="standard", remove_diacritics=True)
pipeline = ArabicNormalizationPipeline(config)
```

---

## Table of contents

1. [Construction patterns](#construction-patterns)
2. [Preset selection](#preset-selection)
3. [Orthographic normalization fields](#orthographic-normalization-fields)
4. [Content cleaning fields](#content-cleaning-fields)
5. [Spacing & structure fields](#spacing--structure-fields)
6. [Dialect fields](#dialect-fields)
7. [Stop-words field](#stop-words-field)
8. [ResourceLimits](#resourcelimits)
9. [Tracing & introspection](#tracing--introspection)
10. [Validation rules](#validation-rules)
11. [Serialization](#serialization)
12. [PipelineBuilder](#pipelinebuilder)

---

## Construction patterns

Four equivalent ways to build a config:

```python
from aranorm import PipelineConfig

# 1. Direct construction — full control
config = PipelineConfig(preset="deep", clean_emojis=True)

# 2. from_preset — same thing, plus overrides as kwargs
config = PipelineConfig.from_preset("deep", clean_emojis=True)

# 3. from_dict — from a plain mapping (e.g. loaded JSON)
config = PipelineConfig.from_dict({"preset": "deep", "clean_emojis": True})

# 4. from_json / from_file — straight from disk
config = PipelineConfig.from_json('{"preset": "deep"}')
config = PipelineConfig.from_file("config.json")     # also .yaml / .yml (needs PyYAML)
```

Unknown keys are **rejected** — typos fail loudly at construction instead of silently doing nothing:

```python
PipelineConfig.from_dict({"clean_emogs": True})
# ConfigurationError: unknown configuration key: 'clean_emogs'
```

## Preset selection

`preset: Union[Preset, str] = "standard"`

The preset applies a bundle of defaults; **any field you pass explicitly always wins** over the preset.

| Preset | What it changes vs. defaults |
|---|---|
| `light` | Turns URL/email/HTML cleaning **off** — pure orthography, nothing removed |
| `standard` | The dataclass defaults themselves (below) |
| `deep` | Everything standard, plus `normalize_repeated_chars=True` |
| `social_media` | Standard + mentions/emojis removed + repeated chars collapsed + **stop words auto-enabled** with `remove_filler=True, remove_internet=True, remove_arabizi=True` |

The `standard` baseline (i.e. the dataclass defaults): diacritics removed; hamza/unicode/alef/alef-maqsura/tatweel/digits/ligatures/punctuation/whitespace normalized; URLs/emails/HTML cleaned; spacing fixed. Mentions, hashtags, emojis, non-Arabic text, English text, repeated characters, and extra punctuation are **kept**. Arabizi and taa-marbuta normalization are **off**. Stop words are **disabled**.

## Orthographic normalization fields

These fields unify *spelling*, never removing words.

| Field | Type | Default | Effect when `True` |
|---|---|---|---|
| `remove_diacritics` | `bool` | `True` | Strip harakat, shadda, sukun, Quranic annotation signs |
| `normalize_hamza` | `bool` | `True` | Unify hamza carriers: ؤ، ئ → ء |
| `normalize_unicode` | `bool` | `True` | Apply Unicode NFKC compatibility normalization |
| `normalize_alef` | `bool` | `True` | Unify alef variants: أ إ آ ٱ → ا |
| `normalize_alef_maqsura` | `bool` | `True` | Map alef maqsura ى → ي |
| `normalize_taa_marbuta` | `bool` | `False` | Map ة → ه (dialect-friendly; **lossy** — off by default) |
| `normalize_tatweel` | `bool` | `True` | Remove tatweel/kashida (ـ) |
| `normalize_digits` | `bool` | `True` | Map Arabic-Indic (٠-٩) and Persian (۰-۹) digits → Western (0-9) |
| `normalize_ligatures` | `bool` | `True` | Expand lam-alef presentation ligatures (ﻻ ﻷ ﻹ ﻵ) to decomposed forms |
| `normalize_punctuation` | `bool` | `True` | Map ، → `,` ؛ → `;` ؟ → `?` ٪ → `%` «» → `"` and drop zero-width chars |
| `handle_arabizi` | `bool` | `False` | Transliterate Arabizi: `2na 3ndi` → أنا عندي |

**Conscious trade-offs:**

- `normalize_taa_marbuta` is off by default because ة→ه loses grammatical information (فاطمة/فاطمه) — enable it for dialect search/matching workloads.
- `normalize_alef_maqsura` (ى→ي) is on because in undiacritized text they are written interchangeably anyway.
- `normalize_hamza` unifies to ء but leaves أ in word-initial position intact (it is phonologically required there).

```python
config = PipelineConfig(preset="light", normalize_alef=True, remove_diacritics=True)
```

## Content cleaning fields

These fields **remove** content. All default to the safest useful value.

| Field | Default | Removes |
|---|---|---|
| `clean_urls` | `True` | `http(s)://...` and `www...` links |
| `clean_emails` | `True` | Email addresses |
| `clean_html` | `True` | HTML tags (contents preserved) |
| `clean_mentions` | `False` | `@username` mentions |
| `clean_hashtags` | `False` | Only the `#` marker — the hashtag **word stays** |
| `clean_emojis` | `False` | Emoji code points (dependency-free) |
| `remove_non_arabic` | `False` | Everything except Arabic letters (+ digits/punctuation if `keep_*`) |
| `remove_english` | `False` | Latin words and letters |

```python
# Typical social pipeline: strip the noise, keep the words
config = PipelineConfig(
    preset="social_media",
    clean_mentions=True,   # drop @user
    clean_hashtags=True,   # drop # too (word kept by default preset; here flag only strips marker)
)
```

## Spacing & structure fields

| Field | Default | Effect |
|---|---|---|
| `normalize_whitespace` | `True` | Collapse all whitespace runs to single spaces, trim |
| `fix_spacing` | `True` | No space before punctuation, exactly one after |
| `normalize_repeated_chars` | `False` | Collapse expressive runs, keep 2: ياااا → يا |
| `remove_extra_punctuation` | `False` | Collapse repeated punctuation: ؟؟؟ → ؟ |

## Dialect fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `dialect_target` | `str` | `"none"` | `"coda"` or `"msa"` enables a `DialectNormalizer` stage |
| `supported_dialects` | `Optional[List[str]]` | `None` | Restrict dialect-ID labels, e.g. `["EGY", "GLF"]` |

When `dialect_target` is set, the result gains `coda_text` or `msa_text` alongside `normalized_text`.

```python
config = PipelineConfig(
    preset="standard",
    dialect_target="msa",
    supported_dialects=["EGY", "GLF", "LEV", "MSA"],
)
```

## Stop-words field

`stop_words_config: Optional[StopWordsConfig] = None`

Setting this field **enables** the stop-words stage. `None` (default) keeps the stage off. See the [Stop Words guide](stopwords.md) for the full `StopWordsConfig` reference.

```python
from aranorm import PipelineConfig, StopWordsConfig

config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(mode="remove", scope="dialect_aware", dialects={"EGY"}),
)
```

## ResourceLimits

`resource_limits: ResourceLimits = ResourceLimits()` — defensive runtime limits (accepts a dict too).

| Field | Type | Default | Meaning |
|---|---|---|---|
| `max_text_length` | `Optional[int]` | `1_000_000` | Max Unicode code points per text (`None` = unlimited, trusted workloads) |
| `max_batch_size` | `int` | `10_000` | Max inputs in one batch call |
| `max_workers` | `int` | `64` | Max thread-pool workers |
| `reject_null_bytes` | `bool` | `True` | Reject inputs containing `\x00` |

```python
from aranorm import PipelineConfig, ResourceLimits

config = PipelineConfig(
    preset="standard",
    resource_limits=ResourceLimits(max_text_length=50_000, max_batch_size=1_000),
)
```

Inputs that violate a limit raise `InvalidTextError` before any processing happens — fail fast, never half-process.

## Tracing & introspection

`emit_steps_trace: bool = False`

When `True`, every result carries `steps_trace: List[Tuple[str, str]]` — the ordered `(processor, action)` pairs actually executed for that text. Invaluable for debugging and audits:

```python
config = PipelineConfig(preset="standard", emit_steps_trace=True)
result = ArabicNormalizationPipeline(config).process("أهلاً")
for step, action in result.steps_trace:
    print(f"{step:24s} {action}")
```

## Validation rules

`config.validate()` (also called automatically by the pipeline) enforces:

- `dialect_aware` stop-word scope **requires** non-empty `dialects` → `ConfigurationError`
- `custom` stop-word scope **requires** `custom_stop_words` → `ConfigurationError`
- `remove_non_arabic=True` together with `handle_arabizi=True` triggers a warning (the Arabizi output would be deleted immediately)

## Serialization

```python
config = PipelineConfig(preset="deep")

config.to_dict()                      # plain dict
config.to_json()                      # pretty JSON string
config.to_yaml()                      # YAML string (needs PyYAML)

PipelineConfig.from_json(json_str)    # round-trip
PipelineConfig.from_yaml(yaml_str)
PipelineConfig.from_file("p.json")    # .json / .yaml / .yml by extension

config.merge({"clean_emojis": True})  # new config with overrides (nested-aware)
config.copy_with(clean_emojis=True)   # shallow override, same as merge for flat fields
```

`merge()` is field-aware: nested `stop_words_config` and `resource_limits` merge per-field rather than being replaced wholesale.

## PipelineBuilder

For programmatic step-by-step construction, use the fluent builder (starts from an all-cleaning-off base):

```python
from aranorm import ArabicNormalizationPipeline

pipeline = (
    ArabicNormalizationPipeline.builder()
    .add_cleaner(clean_urls=True, clean_mentions=True)      # cleaning flags
    .add_normalizer(normalize_alef=True, normalize_tatweel=True)
    .add_dialect_processor(identify=True, normalize_to="msa")
    .add_stop_words(mode="remove", scope="universal")
    .build()
)
```

- `add_cleaner(**flags)` — accepts `clean_*` / `remove_*` boolean flags; unknown names raise
- `add_normalizer(**flags)` — orthography flags (`normalize_diacritics` is mapped to `remove_diacritics`)
- `add_dialect_processor(identify=True, normalize_to="none", supported_dialects=None)`
- `add_stop_words(mode="remove", scope="universal", **kwargs)`

---

## Next steps

- [Processors](processors.md) — what each normalization/cleaning step actually does
- [Stop Words](stopwords.md) — the full stop-word engine
- [API Reference](api.md) — exact signatures
