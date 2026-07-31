# AraNorm

**مكتبة Python الاحترافية لتطبيع النصوص العربية بجميع لهجاتها**

> Production-grade Arabic text normalization for MSA, dialects, social media, and Arabizi.

```
┌─────────────────────────────────────────────────────────────┐
│                ArabicNormalizationPipeline                   │
├─────────────────────────────────────────────────────────────┤
│  ContentCleaner  →  OrthographicNormalizer  →  DialectProc  │
│  (URLs, HTML,       (alef, hamza, diacritics,  (identify,   │
│   emojis, ...)       tatweel, digits, ...)      CODA, MSA)  │
└─────────────────────────────────────────────────────────────┘
```

---

## لماذا AraNorm؟

يعاني كل مشروع عربي NLP من نفس المشكلة: تجميع مكتبات متعددة (CAMeL Tools + PyArabic + tnkeeh...) بواجهات مختلفة ونتائج متناقضة. AraNorm تحل هذه المشكلة بواجهة برمجية واحدة نظيفة.

| الميزة                                        | AraNorm core | Optional Extra              |
|-----------------------------------------------|-----------|-----------------------------|
| Unicode + alef + hamza + taa marbuta + digits | ✅        | —                           |
| تشكيل + كشيدة + تطويل + ترقيم + مسافات        | ✅        | —                           |
| URLs + emails + mentions + hashtags + HTML    | ✅        | —                           |
| Emoji removal                                 | ✅        | —                           |
| Twitter / WhatsApp / Chat normalizers         | ✅        | —                           |
| Arabizi → Arabic conversion                   | ✅        | —                           |
| Repeated chars reduction (يااا→يا)            | ✅        | —                           |
| تحديد اللهجة (heuristic)                      | ✅        | CAMeL Tools (`[camel]`)     |
| تحديد اللهجة >90% (MADAR corpus)              | —         | CAMeL Tools                 |
| CODA/MSA تطبيع عصبي                           | —         | Transformers (`[ml]`)        |
| التحليل الصرفي                                | Adapter   | Farasa / Qalsadi / CAMeL    |

### مقارنة مع المكتبات الأخرى

| المكتبة      | Pipeline | لهجات | Arabizi | Platform | Batch | No-ML core |
|-------------|:--------:|:------:|:--------:|:--------:|:-----:|:----------:|
| **AraNorm** | ✅       | ✅ 8+  | ✅       | ✅       | ✅    | ✅         |
| CAMeL Tools | ❌       | ✅     | ❌       | ❌       | ❌    | ❌         |
| PyArabic    | ❌       | ❌     | ❌       | ❌       | ❌    | ✅         |
| tnkeeh      | ❌       | ❌     | ❌       | ❌       | ❌    | ✅         |

---

## التثبيت

```bash
pip install aranorm
```

تبعيات اختيارية:

```bash
pip install "aranorm[camel]"   # CAMeL Tools — dialect ID بدقة >90%
pip install "aranorm[ml]"      # Transformers + PyTorch — نماذج CODA/MSA
pip install "aranorm[full]"    # كل شيء
```

---

## الاستخدام السريع

### Preset جاهز

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

config = PipelineConfig(
    preset="standard",       # "light" | "standard" | "deep" | "social_media"
    dialect_target="coda",   # "none"  | "coda"    | "msa"
    remove_diacritics=True,
    normalize_hamza=True,
    handle_arabizi=True,
)

pipeline = ArabicNormalizationPipeline(config)
result = pipeline.process("أهـــلاً شلونك؟ https://t.co/abc 😊")

print(result.normalized_text)      # → "اهلا شلونك؟"
print(result.dialect)              # → "GLF"
print(result.dialect_confidence)   # → 0.75
print(result.coda_text)            # → "أهلاً كيف حالك؟"
print(result.is_msa)               # → False
print(result.applied_steps)        # → ['remove_urls', 'normalize_alef', ...]
```

### Builder Pattern (مخصص بالكامل)

```python
pipeline = (
    ArabicNormalizationPipeline.builder()
    .add_cleaner(remove_urls=True, remove_emojis=True)
    .add_normalizer(
        normalize_alef=True,
        normalize_hamza=True,
        normalize_diacritics=True,
        normalize_tatweel=True,
    )
    .add_dialect_processor(
        identify=True,
        normalize_to="coda",
        supported_dialects=["EGY", "GLF", "LEV", "NOR"],
    )
    .build()
)
```

### معالجة دفعية

```python
texts = ["نص1", "نص2", "نص3"]
results = pipeline.process_batch(texts, batch_size=32, n_workers=4)
for r in results:
    print(r.normalized_text, r.dialect)
```

### Processors منفردة

```python
from aranorm.processors import ALEFProcessor, HamzaProcessor, DiacriticsProcessor

ALEFProcessor().process("أحمد إبراهيم آمن ٱلله")
# → "احمد ابراهيم امن الله"

HamzaProcessor().process("سؤال شيئ")
# → "سءال شيء"

DiacriticsProcessor().process("مَرْحَبًا بِكُمْ")
# → "مرحبا بكم"
```

### معالجات المنصات

```python
from aranorm.processors import TwitterNormalizer, WhatsAppNormalizer, ChatNormalizer

# تويتر
TwitterNormalizer().process("RT @user: شلونك؟ #موضوع https://t.co/x")
# → "شلونك؟ موضوع"

# واتساب
WhatsAppNormalizer().process("انشالله الشغل يخلص بكره 🙏 *مهم*: اجتماع")
# → "إن شاء الله الشغل يخلص بكره 🙏 مهم: اجتماع"

# دردشة
ChatNormalizer().process("هههههههههه مضحك جداً")
# → "هه مضحك جداً"
```

---

## الـ Presets

| Preset         | الوصف                                                        |
|----------------|--------------------------------------------------------------|
| `light`        | تطبيع أساسي فقط. لا حاجة لأي تبعيات خارجية. أسرع preset.    |
| `standard`     | الافتراضي. alef + hamza + diacritics + urls + whitespace.    |
| `deep`         | كل شيء. + تكرار الحروف + تصحيح الترقيم.                      |
| `social_media` | مثالي لتويتر/إنستاغرام. URLs + mentions + emojis.            |

---

## اللهجات المدعومة

| الرمز | اللهجة                               |
|-------|--------------------------------------|
| `EGY` | مصرية                                |
| `GLF` | خليجية (السعودية، الإمارات، الكويت)   |
| `LEV` | شامية (سوريا، لبنان، فلسطين، الأردن) |
| `IRQ` | عراقية                               |
| `NOR` | مغاربية (المغرب، الجزائر، ليبيا)     |
| `TUN` | تونسية                               |
| `YEM` | يمنية                                |
| `MSA` | الفصحى                               |

---

## الأداء

| Preset         | النصوص/الثانية |
|----------------|---------------|
| `light`        | ~17,000       |
| `standard`     | ~15,000       |
| `deep`         | ~13,000       |
| `social_media` | ~12,000       |

*مقاس على Python 3.11 — جهاز واحد، خيط واحد.*

---

## المعمارية

```
aranorm/
├── core/           # Pipeline, Config (dataclass), Base ABC, Registry
├── stages/         # ContentCleaner, OrthographicNormalizer, DialectIdentifier,
│                   # DialectNormalizer, MorphologicalProcessor
├── processors/     # 20+ processors منفردون (Processor interface)
├── models/         # Lazy wrappers: CODAModel, MSAModel, DialectIDModel
├── utils/          # Constants, patterns (regex), validators, helpers
├── data/           # dialect_mappings.json, arabizi_mappings.json,
│                   # chat_abbreviations.json
└── exceptions/     # AraNormError hierarchy
```

---

## التطوير

```bash
git clone <repo>
cd aranorm
pip install -e ".[dev]"

# تشغيل الاختبارات
make test              # كل الاختبارات مع تفاصيل
make test-fast         # سريع بدون verbose

# جودة الكود
make lint              # flake8
make format            # black
make type-check        # mypy

# بنشمارك
make benchmark         # 1000 نص
make benchmark-quick   # 100 نص فقط
```

---

---

## Stop Words Support (جديد — v1.1)

نظام متكامل لكلمات التوقف العربية يدعم الفصحى (MSA) و8 لهجات والمحتوى العصري.

### Quick Start

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(
        mode="remove",
        scope="dialect_aware",
        dialects=frozenset(["EGY", "GLF"]),
        preserve_negation=True,
        remove_filler=True,
    ),
)
pipeline = ArabicNormalizationPipeline(config)
result = pipeline.process("أنا والله يعني سعيد جداً اليوم")

print(result.stop_words_removed)      # → "سعيد"
print(result.stop_words_found)        # → {"أنا", "والله", "يعني", "جداً", "اليوم"}
print(result.stop_words_stats)        # → {count: 5, percentage: 71.4, by_category: {...}}
```

### Modes

| Mode        | الوصف                                          |
|-------------|------------------------------------------------|
| `remove`    | إزالة stop words من النص (الافتراضي)            |
| `extract`   | استخراج stop words فقط                         |
| `highlight` | وضع علامة `[[…]]` على stop words               |
| `count`     | إحصاء فقط بدون تعديل النص                      |

### Scopes

| Scope            | الوصف                                     |
|------------------|-------------------------------------------|
| `universal`      | كل stop words (MSA + لهجات + عصرية)       |
| `msa_only`       | الفصحى فقط                               |
| `dialect_aware`  | MSA + لهجات محددة                         |
| `custom`         | قائمة مخصصة فقط                           |

### اللهجات المدعومة

`EGY` (مصرية) · `GLF` (خليجية) · `LEV` (شامية) · `IRQ` (عراقية) ·
`NOR` (مغاربية) · `TUN` (تونسية) · `YEM` (يمنية) · `MSA` (فصحى)

### المعالجات المنفردة

```python
from aranorm.processors import (
    StopWordsProcessor,     # المعالج الرئيسي (remove/extract/highlight/count)
    ContextAwareProcessor,  # إزالة ذكية حسب السياق (لا النافية / إن التوكيدية)
    DialectStopProcessor,   # إزالة لهجية
    ArabiziStopProcessor,   # إزالة Arabizi (2na، 3nd …)
    InternetStopProcessor,  # إزالة رموز الإنترنت (lol، www …)
)

# Context-aware: احتفظ بـ "لا" النافية
from aranorm.processors import ContextAwareProcessor
proc = ContextAwareProcessor(preserve_negation=True)
proc.process("لا أحب هذا")   # → "لا أحب هذا"  (لا محفوظة)
proc.process("لا شك في ذلك") # → "شك"           (لا شك = مصطلح → أزلت)

# Dialect-aware
from aranorm.processors import DialectStopProcessor
proc = DialectStopProcessor(dialects=["EGY", "GLF"])
proc.process("أنا كده الحين سعيد")  # → "سعيد"
```

### StopWordsRegistry — البحث O(m) بالـ Trie

```python
from aranorm import StopWordsRegistry

registry = StopWordsRegistry()

registry.is_stop("من")                     # True  (MSA)
registry.is_stop("كده", dialect="EGY")    # True  (مصرية)
registry.is_stop("كده", dialect="GLF")    # False (ليست خليجية)
registry.is_stop("2na", is_arabizi=True)  # True  (Arabizi)

registry.get_by_category("prepositions")  # {"في", "من", "إلى", ...}
registry.get_by_category("filler")        # {"يعني", "والله", ...}
registry.get_stats()                      # {total_universal: 2449, msa: 715, egy: 65, ...}
```

### التكاملات مع مكتبات NLP

```python
from aranorm.integrations import (
    NLTKStopWordsAdapter,    # توافق NLTK
    SpacyStopWordsAdapter,   # توافق spaCy
    SklearnStopWordsAdapter, # توافق scikit-learn
)

# scikit-learn
from sklearn.feature_extraction.text import TfidfVectorizer
adapter = SklearnStopWordsAdapter()
vectorizer = TfidfVectorizer(stop_words=list(adapter.to_sklearn_set()))

# NLTK
adapter = NLTKStopWordsAdapter()
nltk_words = adapter.to_nltk_list()   # قائمة مرتبة

# spaCy
adapter = SpacyStopWordsAdapter()
nlp = adapter.enrich_spacy(nlp)       # يضيف كلمات التوقف لنموذج spaCy
```

### الـ Presets الجاهزة

```python
from aranorm import StopWordsConfig

# سوشيال ميديا: يزيل filler + internet + arabizi
cfg = StopWordsConfig.for_social_media()

# لهجة محددة
cfg = StopWordsConfig.for_dialect("EGY", "GLF")

# إحصاء فقط بدون تعديل
cfg = StopWordsConfig.count_only()
```

> **ملاحظة:** الـ preset `social_media` يفعّل إزالة filler + internet + Arabizi تلقائياً.

---

## الرخصة

[MIT](LICENSE) — AraNorm Contributors, 2024
