# تقرير تسليم الجولة الثانية — AraNorm 1.3.0

**المشروع:** AraNorm — مكتبة تطبيع النصوص العربية واللهجات

**نطاق الجولة:** توسيع المعالجة للملفات الكبيرة، تقوية الكاش والتوازي، تحسين CLI والتوثيق، وإضافة قياس أداء واختبارات حماية.

**الفرع:** `professional-hardening`

**الإصدار:** `1.3.0`

**التاريخ:** 16 أغسطس 2026

## الملخص التنفيذي

تم تنفيذ جولة تطوير ثانية مركزة على قابلية التشغيل الإنتاجي للمجموعات الكبيرة. أصبح المشروع يدعم الآن مسارًا متدفقًا bounded لا يحمّل كل المدخلات أو النتائج في الذاكرة، مع الحفاظ على ترتيب النتائج ودعم التوازي والتصدير التدريجي. كما تم تقوية `NormalizationCache`، وتوسيع واجهة CLI، وتحديث الوثائق المرجعية وأداة benchmark، ثم التحقق من النسخة عبر اختبارات كاملة وبناء حزم نشر وتجربة تثبيت معزولة.

> النتيجة الأساسية: يمكن الآن معالجة ملف نصي كبير سطرًا بسطر، وإخراج النتائج مباشرة إلى JSONL أو CSV أو JSON، مع تحديد حجم الدفعة وتجاوز السجلات الفاشلة عند الحاجة.

## ما تم تطويره

| المجال | التحسين المنفذ | الأثر العملي |
|---|---|---|
| Pipeline | إضافة `process_iter()` لمعالجة iterable على دفعات bounded | خفض الضغط على الذاكرة مع المحافظة على ترتيب الإدخال |
| Batch API | إعادة بناء `process_batch()` فوق مسار iteration المتدفق مع تحقق حدود `batch_size` و`n_workers` | سلوك موحد وتقليل تكرار المنطق |
| التوازي | دعم التوازي داخل الدفعات مع ترتيب نتائج ثابت وfallback لكل عنصر عند الخطأ | موثوقية أعلى في المعالجة المختلطة أو غير المنتظمة |
| التصدير | إضافة `StreamingBatchExporter` لصيغ CSV وJSON وJSONL، لمسارات أو file-like objects | إخراج تدريجي مناسب للملفات الكبيرة وخطوط البيانات |
| الكاش | إضافة `NormalizationCache.process_iter()` وتحسين حدود المعالجة المتزامنة | الجمع بين LRU وإعادة الاستخدام دون materialization كامل |
| CLI | إضافة `--stream` و`--batch-size` و`--skip-errors` إلى أمر `batch` | واجهة إنتاجية لمعالجة الملفات الكبيرة والبيانات noisy |
| Progress | حساب الأسطر غير الفارغة عند streaming للتحقق من الملفات الفارغة وتغذية progress | رسائل أوضح وتجربة تشغيل أفضل |
| Benchmark | إضافة خيار `--stream` إلى `scripts/benchmark.py` | مقارنة قابلة لإعادة الإنتاج بين `process_batch` و`process_iter` |
| الوثائق | تحديث README و`docs/API.md` و`API_REFERENCE.md` و`PERFORMANCE.md` | توثيق رسمي للواجهات الجديدة وأفضل ممارسات الذاكرة |
| الإصدار | رفع الإصدار إلى `1.3.0` وتحديث CHANGELOG | ميتاداتا نشر متسقة وقابلة للتتبع |

## واجهة الاستخدام الجديدة

### Python API

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

with open("texts.txt", encoding="utf-8") as source:
    for result in pipeline.process_iter(source, batch_size=256, n_workers=4):
        print(result.normalized_text)
```

### التصدير المتدفق

```python
from aranorm.utils import StreamingBatchExporter

exporter = StreamingBatchExporter(
    fields=["original_text", "normalized_text", "dialect"]
)

with open("texts.txt", encoding="utf-8") as source:
    count = exporter.write(
        pipeline.process_iter(source, batch_size=256, n_workers=4),
        "normalized.jsonl",
        format="jsonl",
    )

print(f"تم تصدير {count} سجلًا")
```

### CLI

```bash
aranorm batch \
  --file texts.txt \
  --output normalized.jsonl \
  --format jsonl \
  --stream \
  --batch-size 256 \
  --workers 4 \
  --skip-errors
```

`--stream` يجعل المعالجة والتصدير تدريجيين، و`--batch-size` يحدد الحد الأقصى للمدخلات الموجودة قيد المعالجة، بينما يسمح `--skip-errors` بمتابعة السجلات السليمة مع الإبلاغ عن السجلات التي فشلت بدل إيقاف المهمة كاملة.

## التحقق والاختبارات

تم تشغيل بوابة الجودة على النسخة الحالية، وكانت النتائج كما يلي:

| الفحص | النتيجة |
|---|---:|
| اختبارات pytest | **440 ناجحًا** |
| تكامل اختياري | **1 متخطى** لأن `scikit-learn` غير مثبت، وهو سلوك متوقع |
| flake8 | ناجح بلا أخطاء |
| mypy | ناجح بلا أخطاء على 84 ملف مصدر |
| Black | ناجح |
| `git diff --check` | ناجح |
| benchmark streaming | ناجح؛ light preset حقق 2,253 نصًا/ثانية في smoke test من 100 نص |
| بناء wheel وsdist | ناجح |
| تثبيت wheel في بيئة معزولة | ناجح، مع اختبار الاستيراد و`process_iter()` وJSONL |

> أرقام benchmark تعتمد على بيئة التشغيل الحالية وحجم الإدخال؛ لا ينبغي اعتبارها وعدًا ثابتًا للأجهزة أو النصوص الأخرى. استخدم `python scripts/benchmark.py` على بيئة الإنتاج للحصول على القياس المحلي.

## الملفات والواجهات الأهم

| الملف | الغرض |
|---|---|
| `src/aranorm/core/pipeline.py` | واجهات `process_batch()` و`process_iter()` والتوازي والتحقق |
| `src/aranorm/utils/cache.py` | الكاش المتزامن والمعالجة المتدفقة |
| `src/aranorm/utils/exporters.py` | `StreamingBatchExporter` والتصدير التدريجي |
| `src/aranorm/cli.py` | أعلام أمر `batch` الجديدة ومسار streaming |
| `tests/test_streaming.py` | اختبارات الترتيب، الحدود، التصدير، والكاش |
| `tests/test_cli.py` | اختبارات CLI الجديدة لصيغ streaming والتعامل مع الملف الفارغ |
| `scripts/benchmark.py` | قياس `process_batch` أو `process_iter` عبر `--stream` |
| `README.md` و`docs/API.md` و`API_REFERENCE.md` | توثيق API والاستخدام |
| `PERFORMANCE.md` | إرشادات الذاكرة والتوازي والملفات الكبيرة |
| `CHANGELOG.md` | سجل الإصدار 1.3.0 |

## إعادة التحقق محليًا

```bash
cd AraNorm
pip install -e ".[dev]"
make verify
python scripts/benchmark.py --quick --preset light --stream --batch-size 16
python -m build --wheel --sdist
```

للتثبيت من الحزمة المبنية:

```bash
python -m pip install --no-deps dist/aranorm-1.3.0-py3-none-any.whl
python -c "import aranorm; print(aranorm.__version__)"
```

## ملاحظات تشغيلية

يفضل استخدام JSONL عندما يكون المستهلك downstream قادرًا على قراءة السجلات واحدًا تلو الآخر، لأنه لا يتطلب انتظار اكتمال مصفوفة JSON كاملة. استخدم CSV للتكامل مع أدوات الجداول، وJSON عندما تكون الحاجة إلى مصفوفة واحدة صحيحة أهم من قابلية القراءة التدريجية. وينبغي اختيار `maxsize` في `NormalizationCache` بما يتناسب مع معدل تكرار النصوص؛ إذ لا يفيد الكاش كثيرًا عندما تكون جميع المدخلات فريدة.

تبقى التكاملات الثقيلة مثل CAMeL Tools وTransformers اختيارية، ولم تُجعل تبعيات إلزامية حتى يحافظ الإصدار الأساسي على خفة التثبيت وعدم الاعتماد على نماذج كبيرة.

## حالة التسليم

بعد إضافة التقرير، يجب تثبيت التغييرات في commit مستقل داخل الفرع `professional-hardening` وإنشاء أرشيف مصدر نظيف وملفات النشر الخاصة بالإصدار 1.3.0. لا يتضمن الأرشيف ملفات Git أو الكاشات أو مخرجات البيئة المؤقتة.
