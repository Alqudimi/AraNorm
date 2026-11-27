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
    emit_steps_trace=False,      # opt-in ordered processor/action trace
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
from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.core.spec import PipelineSpec

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

# Versioned deployment specification for declarative configuration
spec = ArabicNormalizationPipeline(config).to_spec(metadata={"owner": "nlp-platform"})
spec.write_file("pipeline.spec.json")
restored = PipelineSpec.read_file("pipeline.spec.json").to_pipeline()
assert restored.configuration_fingerprint() == ArabicNormalizationPipeline(config).configuration_fingerprint()

# Opt-in operational trace; the default remains backward-compatible
traced = config.copy_with(emit_steps_trace=True)
assert traced.to_dict()["emit_steps_trace"] is True
```

### StreamingSession parameters

`StreamingSession` لا يضيف حقولًا إلى `PipelineConfig`؛ فهو boundary تشغيلي يلتف حول pipeline موجود ويعيد استخدام `process_iter()`. يقرأ المصدر كسطر UTF-8 لكل عنصر ويكتب JSONL، بينما يحفظ `StreamCheckpoint` تقدّمًا قابلًا للاستئناف.

| Parameter | Type | Default | Description |
|---|---|---:|---|
| `source_path` | `str` | required | ملف المصدر UTF-8؛ يُتحقق من وجوده وبصمته قبل التشغيل |
| `output_path` | `str` | required | ملف JSONL؛ تُنشأ المجلدات الأب عند الحاجة |
| `checkpoint_path` | `str` | required | ملف تقدم JSON؛ يُكتب ذريًا عبر ملف مؤقت و`os.replace` |
| `batch_size` | `int` | `32` | عدد السجلات في كل دفعة؛ يجب أن يكون موجبًا |
| `n_workers` | `int` | `1` | عدد العمال الممرر إلى `process_iter()`؛ يجب أن يكون موجبًا |
| `max_input_bytes` | `int` | `1 GiB` | الحد الدفاعي لحجم المصدر |
| `resume` | `bool` في `run()` | `True` | تحميل checkpoint الموجود والتحقق منه قبل الاستئناف |
| `cancellation_token` | `CancellationToken \| None` | `None` | إلغاء تعاوني عند حد دفعة آمن |
| `lock_enabled` | `bool` | `False` | قفل advisory محلي غير حاجب بجانب checkpoint لمنع الجلسات المتنافسة |

يُقبل checkpoint فقط عند تطابق `source_path` و`output_path` وبصمة المصدر SHA-256 وبصمة pipeline. وترفض الجلسة تطابق source/output/checkpoint أو aliases وsymlinks للملف نفسه قبل فتح الخرج. الحد الافتراضي لقراءة checkpoint هو `DEFAULT_CHECKPOINT_MAX_BYTES`، أي 1 MiB، وتُرفض الـschema والحقول والبصمات غير الصحيحة عبر `CheckpointError`. عند تفعيل `lock_enabled` يرفع التعارض `StreamingSessionConflictError`، ويؤدي تغير المصدر أثناء التشغيل إلى `StreamingSourceChangedError` مع بقاء آخر checkpoint ذري صالحًا للاستئناف. تغيير الإعداد أو المصدر يتطلب checkpoint جديدًا.

---

## CLI Configuration

The CLI accepts preset flags and output options:

```bash
aranorm normalize "نص" --preset deep
aranorm normalize "نص" --preset standard --remove-diacritics --no-urls
aranorm batch --file texts.txt --format csv --output results.csv --workers 4
aranorm normalize "نص" --json --emit-steps-trace
aranorm batch --file texts.txt --format json --output results.json --retry --max-retries 3 --emit-steps-trace
```

The retry flags are bounded and opt-in. `--retry` is intentionally incompatible with `--stream`, because retry reports require a finite batch result envelope. `--emit-steps-trace` is also opt-in and does not alter legacy output when omitted.

For resumable file processing, use the dedicated commands:

```bash
aranorm stream run --source texts.txt --output out.jsonl --checkpoint out.checkpoint.json --batch-size 256 --workers 4 --json
aranorm stream resume --source texts.txt --output out.jsonl --checkpoint out.checkpoint.json --lock --json
aranorm stream status --checkpoint out.checkpoint.json --json
```

`stream run` starts a fresh session, `stream resume` validates and continues an existing checkpoint, and `stream status` reads the checkpoint without touching the source or output. The commands return a machine-readable report with `--json`; invalid or missing files return a non-zero exit code and a bounded error message.

For a bounded, versioned deployment file, use:

```bash
aranorm spec export --preset deep --output pipeline.spec.json
aranorm spec validate pipeline.spec.json --json
aranorm serve --spec pipeline.spec.json --reload-interval 1.0
```

`PipelineSpec` rejects unknown fields, unsupported schema versions, invalid fingerprints, oversized files, and non-JSON metadata. It serializes `PipelineConfig` only; custom processors and runtime state must be supplied explicitly by the application or a discovered plugin.

The optional HTTP adapter keeps `/v1/stream` disabled by default. Enable it explicitly with `aranorm serve --streaming-enabled`. Use `--streaming-root ./data` to confine all three artifact paths to an existing directory; traversal and symlink escapes return `403`. The endpoint always enables the local session lock and maps conflicts or source mutation to bounded `409` responses. Because the endpoint accepts local `source_path`, `output_path`, and `checkpoint_path` values, it must still be protected by an external authentication and authorization boundary.

See `aranorm --help` and `aranorm <command> --help` for full options.
