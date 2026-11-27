# تقرير إصدار AraNorm 1.6.0 — الجولة الخامسة

**تاريخ الإصدار:** 2026-08-16  
**الفرع:** `professional-hardening`  
**نطاق العمل:** بناء تزايدي فوق AraNorm 1.5.0 دون إعادة كتابة pipeline أو تغيير semantics التطبيع الأساسية.

## الملخص التنفيذي

اكتملت الجولة الخامسة بهدف رفع جاهزية AraNorm التشغيلية والمؤسسية. ركزت الجولة على **observability، introspection، عقود serialization، التشغيل الآلي عبر CLI، resilience للـ plugins، عزل التكاملات الاختيارية، hardening الأمني، واختبارات التوزيع**. بقيت التغييرات محافظة على الواجهات السابقة، ولم تُضف تبعية أساسية جديدة أو خدمة خارجية إلى مسار المعالجة.

> النتيجة: AraNorm 1.6.0 اجتاز بوابة الجودة الكاملة، وحقق تغطية إجمالية قدرها 92%، وبُنيت حزم wheel وsdist وفُحصت عبر twine، ثم اختُبرت عملية التثبيت والتشغيل خارج شجرة المصدر.

## التغييرات المنفذة

| المجال | النتيجة |
|---|---|
| Metrics | عقود JSON versioned لـ `ProcessingMetricsSnapshot`، round-trip آمن، رفض payloads التالفة، ودمج snapshots دون كشف الحالة الداخلية. |
| Pipeline introspection | fingerprint ثابت مبني على config، و`describe_operational()` versioned، مع الحفاظ على `describe()` القديم. |
| CLI | تثبيت مخرجات `version --json` و`plugins --json` وأوامر التشخيص، مع strict exit behavior لاكتشاف plugin failures. |
| Registry | تقارير `PluginDiscoveryReport` و`PluginDiscoveryFailure` قابلة للتحويل ذهابًا وإيابًا، مع ترتيب deterministic وعزل فشل plugin وتعارضاته. |
| Optional integrations | مصفوفة installed/absent للتكاملات pandas وHuggingFace Datasets وspaCy وNLTK، واختبار sklearn يثبت عدم الحاجة إلى import مباشر. |
| Serialization security | اختبارات malformed payloads وunknown fields والاتساق والنسخ الدفاعية لـ registry وconfig وresults. |
| Runtime security | اختبارات hostile source text، عدم تسرب النص إلى metrics أو operational telemetry، وحدود text length وnull bytes وbatch size وworker count والمسار async. |
| Packaging | إصلاح صيغة PEP 621 license metadata، وبناء wheel وsdist للإصدار 1.6.0، مع installed smoke خارج شجرة المصدر. |
| Configuration hardening | نسخ `supported_dialects` دفاعيًا عند إنشاء `PipelineConfig` لمنع aliasing مع قوائم يملكها المستدعي. |

## الملفات الجديدة والمعدلة المهمة

تمت إضافة `tests/test_integration_matrix.py` و`tests/test_operational_serialization.py` و`tests/test_round5_security.py` و`tests/test_installed_smoke.py`. كما حُدثت `README.md` و`CHANGELOG.md`، وجرى ضبط `pyproject.toml` و`src/aranorm/__init__.py` للإصدار 1.6.0، مع إنتاج `performance_round5.json` و`security_round5.json`.

## بوابة الجودة

| الفحص | النتيجة |
|---|---:|
| `make verify` | ناجح |
| الاختبارات | 660 ناجحًا |
| الاختبارات المتخطاة | 5، وكلها مرتبطة بتبعيات اختيارية غير مثبتة |
| التغطية | 92% — 4,387 سطرًا، 363 غير منفذة |
| Black | ناجح، 139 ملفًا دون مخالفات |
| flake8 | ناجح |
| mypy | ناجح على ملفات المصدر |
| compileall | ناجح على Python 3.10 و3.11 و3.12 |
| installed smoke | ناجح للـ wheel والـ sdist خارج شجرة المصدر |
| `twine check` | ناجح للـ wheel والـ sdist |

التخطيات الموثقة هي غياب PyYAML، HuggingFace Datasets، spaCy، NLTK، وscikit-learn. هذه التخطيات لا تمنع تشغيل core ولا تغيّر التبعيات الأساسية؛ أما عقود الغياب نفسها فمختبرة برسائل `IntegrationUnavailableError` واضحة.

## نتائج تدقيق الأداء والأمان

| القياس | النتيجة المسجلة |
|---|---:|
| Cache speedup على 1,000 عنصر متكرر | 522.45x |
| Cache hits / misses | 999 / 1 |
| Single-flight calls عند 16 مستدعيًا | 1 بدل 16 في المسار غير المحمي |
| Streaming throughput على 10,000 عنصر | 596.15 نص/ثانية |
| Streaming peak traced allocation | 5,950 bytes |
| Regex security audit عند 20,000 محرف | بقيت الأنماط المختبرة ضمن زمن منخفض وخطي عمليًا |

النتائج الخام محفوظة في `performance_round5.json` و`security_round5.json` كي يمكن إعادة القياس ومقارنة الجولة التالية بها. لا ينبغي تفسير أرقام الأداء كضمان hardware-independent؛ فهي baseline قابلة لإعادة التشغيل في بيئة المشروع.

## Artifacts وchecksums

تم إنشاء الحزم التالية:

| الملف | الحجم التقريبي | SHA-256 |
|---|---:|---|
| `dist/aranorm-1.6.0-py3-none-any.whl` | 188 KiB | `cb238ca0b435f4d21c5f68406b7c73850bcbb6cebc9aa09a6098e9cfa1b1f915` |
| `dist/aranorm-1.6.0.tar.gz` | 195 KiB | `857e9f53ffda0e47b5777e7ec4b00a57476346e2cf9bc359a81a371cf32791eb` |

يمكن التحقق من سلامة الملفات عبر:

```bash
sha256sum -c SHA256SUMS-1.6.0.txt
python3 -m twine check dist/*
```

## التحقق التشغيلي بعد التثبيت

يعمل probe التثبيت على استيراد `aranorm` من target مستقل، ينشئ `ArabicNormalizationPipeline`، يعالج نصًا عربيًا، ويتحقق من وجود `config_fingerprint` في الوصف التشغيلي ومن تطابق `__version__` مع 1.6.0. وقد نجح probe لكل من wheel وsdist مع إزالة `PYTHONPATH` الخاص بالمصدر.

## قواعد عدم الانحدار

بقيت واجهات `process()` و`process_batch()` و`process_iter()` و`process_batch_async()` متوافقة مع عقود الجولة السابقة. بقيت مخرجات `describe()` القديمة متاحة، وأضيفت المخرجات versioned بصورة اختيارية أو عبر أوامر جديدة. لا تسجل metrics أو operational descriptions النص الأصلي أو normalized text، وتظل التكاملات الخارجية اختيارية.

## التوصية

الإصدار **AraNorm 1.6.0 جاهز للتوزيع** ضمن نطاق الجولة الخامسة. تُحجز الجولة التالية لتوثيق migration أوسع عند الحاجة، ثم REST API أو Docker runtime أو GPU batching أو تكاملات السجلات الخارجية، وهي عناصر خارج نطاق هذه الجولة وفق `ROUND5_ROADMAP.md`.

## مراجع المشروع الداخلية

[1]: ROUND5_ROADMAP.md "خطة الجولة الخامسة ومعايير الخروج"
[2]: README.md "دليل الاستخدام والواجهات التشغيلية"
[3]: API_REFERENCE.md "مرجع API"
[4]: performance_round5.json "نتائج تدقيق الأداء"
[5]: security_round5.json "نتائج تدقيق regex والأمان"
[6]: CHANGELOG.md "سجل التغييرات"
