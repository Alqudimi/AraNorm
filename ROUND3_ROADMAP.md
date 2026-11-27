# خارطة الطريق التنفيذية — AraNorm 1.4.0

## 1. الهدف والنطاق

تهدف الجولة الثالثة إلى نقل AraNorm من حزمة قوية وظيفيًا إلى مكتبة عربية قابلة للتوسع المؤسسي: عقود عامة واضحة، سياسات تشغيل قابلة للضبط، أخطاء قابلة للتعامل، قابلية رصد، اختبارات دفاعية، وتوزيع موثوق. ستُنفذ التغييرات فوق الكود الحالي بصورة تزايدية؛ لا توجد إعادة كتابة شاملة ولا تغيير غير مبرر في السلوك القائم.

## 2. خط الأساس المقاس

| المؤشر | خط الأساس |
|---|---:|
| الإصدار | 1.3.0 |
| الاختبارات | 440 ناجحًا، اختبار اختياري واحد متخطى |
| التغطية | 79% إجماليًا، 3860 سطرًا مقاسًا |
| mypy | ناجح على 84 ملف مصدر |
| flake8 | ناجح |
| Black | ناجح على 105 ملفات |
| compileall | ناجح |
| التوزيع | wheel وsdist ناجحان في الجولة السابقة |

## 3. نتائج التدقيق المعماري

### نقاط القوة

تستخدم الحزمة `src/` layout، وتفصل pipeline عن stages/processors/utils، وتملك نموذج إعدادات typed مع serialization، وواجهة streaming، وواجهة cache، وCLI، وتكاملات اختيارية لا تُحمّل وقت الاستيراد. كما أن الاختبارات الحالية تغطي السلوك الأساسي والتغييرات السابقة بصورة جيدة.

### المخاطر ذات الأولوية

| الأولوية | الملاحظة | المعالجة المقترحة | معيار القبول |
|---|---|---|---|
| P0 | `process_iter` و`process_batch_async` لا يقدمان سياسة فشل موحدة ولا cancellation واضحة | إضافة `BatchProcessingPolicy`/خيارات متوافقة، وتوثيق semantics، واختبارها دون كسر المسار الحالي | أخطاء قابلة للتوقع، ترتيب ثابت، وإغلاق الموارد دائمًا |
| P0 | pipeline يقبل `progress_callback: Any` رغم وجود عقد واضح | استخدام Protocol/نوع مشترك مع توافق callbacks القديمة | mypy ناجح واختبارات lifecycle وexception paths |
| P0 | `NormalizationResult` يستخدم `Dict[str, Any]` وmutable collections في واجهة عامة | إضافة validation/serialization دفاعي ونسخ آمن عند الحاجة دون تغيير المفاتيح الحالية | round-trip ثابت وعدم تسريب mutation |
| P1 | cache يحسب نفس المفتاح أكثر من مرة تحت race ويخلط cache misses بالنتائج المحذوفة | توضيح سياسة concurrent single-flight أو توثيقها، وإضافة metrics وinvalidate predicates اختيارية | اختبارات تزامن حتمية وعدم فساد counters |
| P1 | BatchProcessingError موجود لكنه غير مستعمل في المسارات التي قد تفشل جزئيًا | إضافة نمط strict/collect متوافق، مع إبقاء skip/fallback الحاليين | اختبار failed_indices/errors وتوافق CLI |
| P1 | فجوات التغطية تتركز في integrations/language_detector/cache/exporters/progress والـ stop-word processors | تقسيم الاختبارات إلى unit/contract/integration/optional وتغطية حدود الفشل | رفع التغطية إلى 85% على الأقل دون اختبارات شكلية |
| P2 | لا توجد طبقة تشغيلية موحدة للـ logging/metrics وhealth/introspection | إضافة `ProcessingMetrics` أو snapshot خفيف غير إلزامي مع hooks اختيارية | قياس زمن/نجاح/فشل بدون تغيير النص الناتج |
| P2 | إعدادات pipeline كثيرة وممتدة ويمكن أن تتوسع بلا schema واضح | إضافة grouping/validation ورسائل خطأ دقيقة مع الحفاظ على الحقول الحالية | unknown fields مرفوضة، round-trip، backward compatibility |
| P2 | التوثيق يحتاج مرجعًا معماريًا وأمثلة سياسات الخطأ والتثبيت المعزول | إضافة ARCHITECTURE وTESTING/OPERATIONS وتحديث API/CLI | أمثلة قابلة للنسخ وتطابق السلوك الفعلي |

## 4. ترتيب التنفيذ

### المرحلة A — العقود والبنية المشتركة

تثبيت Protocols للـ progress والنتائج، أنواع aliases، وسياسة batch/error مستقلة. إضافة `PipelineMetrics` أو واجهة snapshot صغيرة، مع الحفاظ على signatures الحالية عبر قيم افتراضية متوافقة.

### المرحلة B — الاعتمادية والتشغيل

توحيد lifecycle للـ callbacks، ضمان shutdown في كل المسارات، إضافة cancellation/timeout حيث يمكن تطبيقها بأمان، تحسين cache concurrency semantics، وإدخال BatchProcessingError في نمط collect دون تغيير default behavior.

### المرحلة C — القدرات المتقدمة

إضافة hooks اختيارية قبل/بعد المعالجة، مرشح نتيجة/validator قابل للحقن، وإمكانية إرجاع تقارير تشغيلية. لا تضاف أي ميزة ما لم تكن مستقلة، typed، موثقة، وقابلة للاختبار.

### المرحلة D — منظومة الاختبارات

إنشاء ملفات اختبار مستقلة للعقود، السياسات، serialization، التزامن، cancellation، CLI، تثبيت wheel، التكاملات الاختيارية، property-style invariants المحدودة، واختبارات regression لكل عيب.

### المرحلة E — الأداء والأمان والنشر

قياس throughput/latency/peak memory على corpus اصطناعي ثابت، فحص مدخلات الملفات وJSON/YAML، منع تسريب mutable state، تشغيل build/install smoke في venv نظيف، وتحديث CI وmetadata وCHANGELOG.

## 5. مصفوفة الاختبارات المطلوبة

| الطبقة | الملفات المقترحة | الهدف |
|---|---|---|
| Unit | `test_contracts.py`, `test_metrics.py`, `test_policies.py` | اختبار الأنواع والعقود والسياسات بلا تبعيات اختيارية |
| Pipeline | `test_pipeline_error_modes.py`, `test_pipeline_async.py` | ترتيب النتائج، fallback، strict/collect، lifecycle |
| Cache | `test_cache_concurrency.py`, `test_cache_invalidation.py` | race، counters، LRU، invalidate/clear |
| Serialization | `test_result_roundtrip.py`, `test_config_roundtrip.py` | JSON/YAML/CSV، mutation safety، backward payloads |
| CLI | `test_cli_streaming.py`, `test_cli_failures.py` | خيارات التشغيل والمخرجات ورسائل الأخطاء |
| Integration | `test_optional_integrations.py` | skip واضح عند غياب التبعيات ورسائل صحيحة عند الطلب |
| Packaging | `test_installed_smoke.py` | اختبار النسخة المثبتة بدل شجرة المصدر |
| Regression | `test_round3_regressions.py` | كل إصلاح جديد مرتبط بعطل أو عقد محدد |

## 6. قواعد عدم الانحدار

لا يُسمح بتغيير ناتج `process()` للحالات الحالية إلا إذا كان إصلاحًا موثقًا ومختبرًا. تبقى الحقول الحالية في `NormalizationResult` و`PipelineConfig` متاحة. تبقى `process_batch` مادية ومحتفظة بالترتيب، وتبقى `process_iter` متدفقة ومحدودة الذاكرة. أي واجهة جديدة تُضاف بطريقة اختيارية، ولا تُفرض تبعية ثقيلة جديدة على التثبيت الأساسي.

## 7. معايير الخروج

يُعتبر الإصدار جاهزًا فقط عند تحقق الآتي: نجاح الاختبارات الكاملة والاختبارات الاختيارية المتاحة، عدم وجود أخطاء mypy/flake8/Black/compileall، تغطية لا تقل عن 85% أو تفسير موثق للفجوات الاختيارية، نجاح wheel وsdist، نجاح تثبيت wheel في بيئة معزولة، نجاح smoke للـ CLI، تحديث الوثائق وCHANGELOG، ووجود commit مستقل ورسالة تسليم قابلة للمراجعة.

## 8. مصادر المعايير

[1]: https://packaging.python.org/en/latest/tutorials/packaging-projects/ "Python Packaging User Guide — Packaging Python Projects"
[2]: https://docs.pytest.org/en/stable/explanation/goodpractices.html "pytest — Good Integration Practices"
[3]: https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html "pyOpenSci — Python Package Structure & Layout"
