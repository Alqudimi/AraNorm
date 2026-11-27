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

# Optional operational trace; omitted by default for backward compatibility
traced = ArabicNormalizationPipeline(
    PipelineConfig(preset="standard", emit_steps_trace=True)
).process("أهلاً وسهلاً")
print(traced.steps_trace)           # → [('ContentCleaner', '...'), ...]
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

### إعادة معالجة الدفعات الفاشلة

يوفر المسار `process_batch_retry()` تقريرًا typed ومحدودًا لإعادة معالجة العناصر الفاشلة فقط، مع الحفاظ على ترتيب الإدخال وتسجيل الفشل النهائي دون تسريب النصوص داخل ملخص التقرير. ويكافئه المسار `process_batch_retry_async()` في التطبيقات غير المتزامنة.

```python
from aranorm import BatchRetryPolicy

report = pipeline.process_batch_retry(
    texts,
    retry_policy=BatchRetryPolicy(max_retries=2, backoff_seconds=0.0),
)
print(report.results)
print(report.failed_indices, report.recovered_count)

async_report = await pipeline.process_batch_retry_async(
    texts,
    retry_policy=BatchRetryPolicy(max_retries=2),
)
```

القيمة `max_retries=0` صالحة ومفيدة للتشغيل التشخيصي؛ فهي تسجل الإخفاقات الأولية دون إعادة محاولة. أما في CLI، فخيار `--retry` متاح للدفعات المحدودة، بينما يبقى غير متوافق مع `--stream` لتجنب فقدان envelope التقرير.

### معالجة متدفقة للملفات الكبيرة

عند التعامل مع ملفات ضخمة، استخدم `process_iter()` أو خيار `--stream` حتى تُعالج المدخلات على دفعات محدودة بدل تحميل الملف كاملًا في الذاكرة. يحافظ المسار المتدفق على ترتيب السجلات ويدعم التوازي والتصدير التدريجي إلى JSONL أو JSON أو CSV.

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
with open("texts.txt", encoding="utf-8") as source:
    results = pipeline.process_iter(source, batch_size=256, n_workers=4)
    for result in results:
        print(result.normalized_text)
```

ومن الطرفية:

```bash
aranorm batch --file texts.txt --output normalized.jsonl \\
  --stream --batch-size 256 --workers 4 --format jsonl
```

يحسب أمر CLI عدد الأسطر غير الفارغة للتحقق من الملف الفارغ وتغذية مؤشر التقدم، مع بقاء استهلاك الذاكرة متناسبًا مع حجم الدفعة لا حجم الملف. ويمكن استخدام `--skip-errors` لتجاوز السجلات الفاشلة مع إصدار تحذير لكل سجل بدل إيقاف العملية كاملة.

### جلسة متدفقة قابلة للاستئناف

للمعالجة التشغيلية التي تحتاج إلى استئناف آمن بعد انقطاع العملية، توفر AraNorm عقد `StreamingSession`. يقرأ العقد ملف UTF-8 كسجل واحد في كل سطر، ويكتب نتائج JSONL تدريجيًا، ثم يحفظ `StreamCheckpoint` ذريًا بعد كل دفعة. لا يعيد الاستئناف قبول checkpoint إلا إذا تطابقت مسارات المصدر والخرج، وبصمة SHA-256 للمصدر، وبصمة إعداد pipeline.

```python
from aranorm import ArabicNormalizationPipeline, StreamingSession

pipeline = ArabicNormalizationPipeline.from_preset("light")
session = StreamingSession(
    pipeline,
    "texts.txt",
    "normalized.jsonl",
    "normalized.checkpoint.json",
    batch_size=256,
    n_workers=4,
    lock_enabled=True,  # optional local advisory lock; useful for schedulers
)
report = session.run(resume=True)
print(report.completed, report.processed_count, report.next_index)
```

يُنشئ العقد مجلدات الخرج والـcheckpoint عند الحاجة، ويمنع تجاوز حجم المصدر المحدد في `max_input_bytes`. يتحقق أيضًا من أن المصدر والخرج والـcheckpoint مسارات مختلفة وليست aliases أو symlinks للملف نفسه. عند تفعيل `lock_enabled=True` يُنشأ قفل advisory محلي بجانب checkpoint، ويُرفض التشغيل المتوازي بعقد `StreamingSessionConflictError` بدل الكتابة المتنافسة. كما يراقب العقد هوية المصدر أثناء التشغيل ويرفع `StreamingSourceChangedError` إذا تغيّر المصدر، ويترك checkpoint السابق صالحًا للاستئناف الآمن. ويمكن تمرير `CancellationToken` للإلغاء التعاوني؛ عندها يحفظ التقرير والـcheckpoint تقدّمًا قابلًا للاستئناف بدل حذف النتائج السابقة. ومن الطرفية:

```bash
aranorm stream run --source texts.txt --output normalized.jsonl \\
  --checkpoint normalized.checkpoint.json --batch-size 256 --workers 4 --json
aranorm stream resume --source texts.txt --output normalized.jsonl \\
  --checkpoint normalized.checkpoint.json --lock --json
aranorm stream status --checkpoint normalized.checkpoint.json --json
```

يحتوي checkpoint على `schema_version` و`next_index` و`output_bytes` و`input_count` وحالتي `completed` والبصمتين. لا تعدّل هذا الملف يدويًا؛ فالتحميل والتحقق يرفضان الحقول الزائدة، الإصدارات غير المدعومة، البصمات غير الصحيحة، والملفات التي تتجاوز الحد الدفاعي. يضيف خيار CLI `--lock` قفلًا محليًا اختياريًا، بينما يبقي API الافتراضي القفل معطلًا للتوافق الخلفي؛ استخدمه مع scheduler أو worker واحد لكل tuple من الملفات.

### الإلغاء التعاوني وحماية الموارد

للتطبيقات طويلة التشغيل، توفر AraNorm عقد `CancellationToken` آمنًا للتزامن. الإلغاء تعاوني: لا تُلغى خيوط العمل قسرًا، بل يتوقف إدخال العمل الجديد واستهلاك النتائج عند أقرب حد آمن مع رفع `ProcessingCancelledError`.

```python
from aranorm import (
    ArabicNormalizationPipeline,
    CancellationToken,
    PipelineConfig,
    ResourceLimits,
)

pipeline = ArabicNormalizationPipeline(
    PipelineConfig(
        resource_limits=ResourceLimits(
            max_text_length=1_000_000,
            max_batch_size=10_000,
            max_workers=8,
        )
    )
)
token = CancellationToken()

for result in pipeline.process_iter(texts, batch_size=256, cancellation_token=token):
    if shutdown_requested():
        token.cancel()
    consume(result)
```

يمكن استخدام `BatchProcessingPolicy("collect")` لجمع أخطاء الدفعة، و`BatchRetryPolicy` لإعادة المحاولة بحدود معلنة، و`PipelineHooks` لمراقبة دورة الحياة، و`ProcessingMetrics` للحصول على counters آمنة للتزامن. تبقى جميع هذه العقود اختيارية، ويحافظ الاستخدام الافتراضي على السلوك السابق.

### التشخيص التشغيلي وبصمة الإعداد

لإدراج pipeline في سجلات النشر أو فحوص الجاهزية دون كشف النصوص المعالجة، توفر AraNorm بصمة ثابتة للإعداد ووصفًا تشغيليًا versioned:

```python
pipeline = ArabicNormalizationPipeline.from_preset("deep")
print(pipeline.configuration_fingerprint())
print(pipeline.describe_operational())
```

تُحسب البصمة من الإعداد الفعلي بصيغة JSON canonical وSHA-256، بينما يحتوي `describe_operational()` على اسم الفئة وإصدار الحزمة ونسخة schema وmetadata منقّحة. كما يمكن الحصول على نفس البيانات من الطرفية:

```bash
aranorm describe --preset deep --json
aranorm normalize "نص تجريبي" --json --emit-steps-trace
aranorm batch --file texts.txt --format json --output results.json --retry --max-retries 3 --emit-steps-trace
```

لا تتضمن هذه الواجهات النص الأصلي أو الناتج أو أي محتوى مستخدم، ولذلك تصلح للتشخيص ومقارنة إعدادات البيئات بأمان.

### PipelineSpec وإعادة البناء الآمن

توفر AraNorm عقد `PipelineSpec` بصيغة JSON versioned لحفظ إعدادات pipeline القابلة لإعادة البناء، مع `config_fingerprint` حتمي والتحقق من schema والحقول والحد الأقصى لحجم الملف. تكتب المواصفة الملفات ذريًا، وتبقي metadata التشخيصية منفصلة عن إعدادات التشغيل.

```python
from aranorm import ArabicNormalizationPipeline
from aranorm.core.spec import PipelineSpec

pipeline = ArabicNormalizationPipeline.from_preset("deep")
spec = pipeline.to_spec(metadata={"owner": "nlp-platform"})
spec.write_file("pipeline.spec.json")
restored = PipelineSpec.read_file("pipeline.spec.json").to_pipeline()
assert restored.configuration_fingerprint() == pipeline.configuration_fingerprint()
```

```bash
aranorm spec export --preset deep --output pipeline.spec.json
aranorm spec validate pipeline.spec.json --json
aranorm serve --spec pipeline.spec.json --reload-interval 1.0
```

المواصفة تعيد بناء `PipelineConfig` فقط؛ لا تُسلسل المعالجات المخصصة أو الحالة التنفيذية تلقائيًا. عند الحاجة إلى مكونات إضافية يجب تسجيلها كـplugin وإعادة حقنها صراحة في طبقة التطبيق. يدعم `PipelineRuntime.reload_from_spec_file()` النشر الذري ويحافظ على snapshot السابق عند فشل التحقق.

### تشخيص Plugins

يمكن فحص معالجات plugins المسجلة عبر entry points دون إيقاف الخدمة عند فشل plugin منفرد. يعيد التقرير أسماء plugins المكتشفة وأخطاء قابلة للتسلسل، مع ترتيب حتمي؛ أما `--strict` فيحوّل أول فشل إلى عملية غير ناجحة لاستخدامه في بوابات النشر:

```bash
aranorm version --json
aranorm plugins --json
aranorm plugins --group aranorm.processors --strict
```

وللاستخدام البرمجي:

```python
from aranorm import ProcessorRegistry

report = ProcessorRegistry().discover_report()
if not report.ok:
    for failure in report.failures:
        print(failure.name, failure.error_type, failure.message)
```

تتعامل AraNorm مع فشل الاكتشاف كحالة diagnostics غير قاتلة افتراضيًا، ولا تستبدل plugin صالحًا بآخر مكرر؛ ويمكن استخدام `report.to_dict()` لإرساله إلى أنظمة المراقبة دون تضمين نصوص المستخدم. تضيف مخرجات CLI بصيغة JSON الحقل `schema_version` لتسهيل التطوير المتوافق، بينما يبقى تمثيل التقرير البرمجي كما هو.

يعيد `aranorm version --json` كائنًا ثابتًا يتضمن `schema_version` و`package` و`version`، ويعيد `aranorm plugins --json` تقرير الاكتشاف مع `schema_version` وحالة `ok` وقوائم الاكتشاف والفشل. يعتمد العقد على مجموعة `aranorm.processors` القياسية في `dist-info/entry_points.txt`؛ وتثبت `tests/test_plugin_installation_round8.py` حالات التوزيع المثبت الناجح، والمعالج غير الصالح، ووضع `--strict`. يمكن تشغيلها منفردة عبر `make plugin-contracts`.

### Runtime وخدمة HTTP اختيارية

للتطبيقات طويلة التشغيل، توفر AraNorm طبقة `PipelineRuntime` فوق الـ pipeline القائم. تبني الطبقة snapshot جديدًا كاملًا قبل نشره، وتبقي snapshot السابق فعالًا إذا فشل reload. لا يبدأ أي listener عند استيراد الحزمة، وتبقى التبعيات الأساسية صفرًا.

```python
from aranorm import PipelineConfig, PipelineRuntime

runtime = PipelineRuntime(PipelineConfig(preset="standard"))
old_pipeline = runtime.get_pipeline()
reload_result = runtime.reload(PipelineConfig(preset="deep"))

print(reload_result.to_dict())
print(runtime.health().to_dict())
assert old_pipeline is not runtime.get_pipeline()
```

تتضمن `RuntimeHealth` الحالة `ready` أو `degraded`، وgeneration، وبصمة الإعداد، وسبب آخر فشل reload بعد تنقيحه. لا تتضمن health أو reload reports نصوص المستخدم أو نتائج التطبيع.

يمكن تشغيل adapter HTTP اختياري مبني على مكتبة Python القياسية:

```bash
aranorm serve --host 127.0.0.1 --port 8765 --preset standard
aranorm serve --config pipeline.json --reload-interval 1.0
aranorm serve --spec pipeline.spec.json --reload-interval 1.0
aranorm serve --host 127.0.0.1 --port 8765 --streaming-enabled --streaming-root ./data
aranorm spec export --preset deep --output pipeline.spec.json
aranorm spec validate pipeline.spec.json --json
```

| المسار | الطريقة | الاستخدام |
|---|---|---|
| `/health/live` | `GET` | فحص liveness سريع |
| `/health/ready` | `GET` | readiness وgeneration وحالة degraded |
| `/v1/normalize` | `POST` | `{"text": "نص عربي"}` |
| `/v1/batch` | `POST` | `{"texts": ["نص 1", "نص 2"], "batch_size": 32, "workers": 1}` |
| `/v1/describe` | `GET` | metadata تشغيلية منزوعة الحساسية |
| `/v1/stream` | `POST`، عند تفعيل `--streaming-enabled` | تشغيل جلسة ملفات محلية عبر `source_path` و`output_path` و`checkpoint_path` |

يفرض الخادم JSON صحيحًا و`Content-Type: application/json` وحدًا افتراضيًا لحجم body مقداره 2,000,000 بايت. يبقى `/v1/stream` معطلاً افتراضيًا، وعند تفعيله يمكن تقييد كل المسارات إلى مجلد قائم عبر `--streaming-root`؛ تُرفض المسارات الخارجة عن الجذر أو التي تعبر symlink بصفحة `403`. يفرض endpoint قفل الجلسة محليًا، ويرجع `409` عند تعارض جلسة أو تغير المصدر أثناء التشغيل. يجب تشغيله خلف تفويض موثوق وعدم تعريضه مباشرةً لطلبات غير موثوقة. هذا adapter مناسب للتشغيل المحلي أو خلف reverse proxy موثوق؛ أما TLS والمصادقة والتفويض وrate limiting فتظل مسؤولية gateway الإنتاجي.

### كاش LRU متدفق

للنصوص المتكررة، يمكن تغليف الـ pipeline بكاش LRU آمن للاستخدام المتزامن. يدعم الكاش الآن المعالجة الدفعية والمتدفقة مع حد أقصى للحجم وإحصاءات hits/misses قابلة للرصد.

```python
from aranorm import ArabicNormalizationPipeline
from aranorm.utils.cache import NormalizationCache

cache = NormalizationCache(ArabicNormalizationPipeline.from_preset("light"), maxsize=8192)
with open("texts.txt", encoding="utf-8") as source:
    for result in cache.process_iter(source, batch_size=256, n_workers=4):
        print(result.normalized_text)

print(cache.stats())
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

# بوابة الجودة غير المغيرة
make verify            # format-check + lint + type-check + test

# تشغيل الفحوص منفردة
make lint              # flake8
make format            # black
make format-check      # تحقق Black دون تعديل الملفات
make type-check        # mypy

# بنشمارك
make benchmark         # 1000 نص
make benchmark-quick   # 100 نص فقط
```

---

### عقود الثبات في الإصدارات الحديثة

يضمن `PipelineConfig.from_dict()` عدم تعديل القاموس الذي يمرره المستهلك، ويرفض مفاتيح الإعدادات غير المعروفة مبكرًا برسالة واضحة. كما تحافظ `process_batch()` و`process_batch_async()` و`process_iter()` على ترتيب النتائج المطابق لترتيب الإدخال، وتحتفظ `NormalizationResult` ببياناتها عند التحويل ذهابًا وإيابًا عبر `to_dict()` و`from_dict()`. ويستخدم `process_iter()` دفعات bounded، بينما يوفر `StreamingBatchExporter` تصديرًا تدريجيًا إلى file-like objects أو مسارات الملفات.

للمساهمة، شغّل `make verify` قبل فتح طلب دمج. ويغطي سير CI الرسمي الاختبارات و`flake8` و`mypy` وBlack على Python 3.10–3.13.

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
