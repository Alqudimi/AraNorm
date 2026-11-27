# تقرير إصدار الجولة التاسعة — AraNorm 1.8.0

## الملخص التنفيذي

أضافت الجولة التاسعة إلى AraNorm 1.8.0 عقدًا portable وقابلًا للمراجعة باسم `PipelineSpec`. يصف هذا العقد إعدادات pipeline declarative بصورة versioned، ويتيح تصديرها والتحقق منها وإعادة بنائها بأمان، مع الحفاظ على `PipelineConfig` و`PipelineRuntime` وواجهات الإصدارات السابقة دون إعادة كتابة النواة أو تغيير الإصدار الرسمي.

يركز التصميم على الفصل بين **البيانات الوصفية القابلة للنقل** وبين **الكائنات التنفيذية**. لذلك لا يقوم `PipelineSpec` بتسلسل كائنات Python أو instances مخصصة من processors، ولا ينفذ object references أو plugin references واردة من JSON. هذا القرار متسق مع طبيعة metadata ونقاط الدخول في منظومة Python، حيث تُكتشف المكونات المثبتة عبر distribution metadata وentry points، بينما تبقى المواصفة declarative ومحايدة عن بيئة التنفيذ [1] [2].

اكتملت بوابة الجودة الأساسية بنجاح، وبلغت التغطية الكلية 94%، بينما بلغت وحدة `PipelineSpec` 99%. أُعيد بناء wheel وsdist، وفُحصت metadata، وشُغّل installed smoke خارج شجرة المصدر، وحُفظت نتائج تدقيق الأداء والأمان في artifacts مستقلة. الإصدار الرسمي ما زال `1.8.0`؛ الجولة مسجلة في `Unreleased` ولم تُرفع إلى `1.9.0` قبل قرار release مستقل.

## نطاق الجولة وقراراتها

كان الهدف هو توفير تمثيل مستقر وقابل للنقل لإعدادات pipeline فوق البنية القائمة، مع حدود واضحة للتوافق والأمان. شمل النطاق إضافة schema version ثابت، وحقول `library_version` و`pipeline_class` و`config` و`config_fingerprint` و`metadata`، ومسارات JSON والنص والملف، إضافة إلى تكامل runtime وCLI واختبارات العقود والتوافق.

| المجال | القرار المنفذ | الأثر التشغيلي |
|---|---|---|
| تمثيل pipeline | `PipelineSpec` declarative وversioned | نقل الإعدادات بين البيئات دون نقل الحالة التنفيذية |
| التحقق | رفض الحقول المجهولة، schema غير المدعوم، fingerprints غير المطابقة، والبيانات غير القابلة للتسلسل | فشل typed ومبكر قبل تشغيل pipeline جزئي |
| الحتمية | canonical JSON بترتيب مفاتيح ثابت وبصمة configuration واحدة | نتائج قابلة للمقارنة والمراجعة |
| الأمان | عدم استخدام `pickle` وعدم تنفيذ object references من JSON | تقليل سطح deserialization غير الموثوق |
| الملفات | قراءة UTF-8 وحد أقصى دفاعي للحجم وكتابة ذرية | حماية من الملفات الكبيرة والكتابات الجزئية |
| التوافق | إعادة استخدام `PipelineConfig.from_dict()` وfingerprint القائمة | عدم كسر الإعدادات وواجهات 1.8.0 |

## التغييرات المعمارية

أضيفت وحدة `src/aranorm/core/spec.py` كطبقة عقد مستقلة، ولم تُنقل إليها مسؤوليات المعالجة أو اكتشاف plugins. توفر الطبقة تحويلات `to_dict` و`from_dict` و`to_json` و`from_json` و`write_file` و`read_file`، مع نسخ دفاعي للمدخلات والـ metadata. يعتمد fingerprint على configuration canonical نفسها المستخدمة في pipeline، ولذلك لا توجد بصمتان متنافستان داخل النظام.

أضيفت إلى `ArabicNormalizationPipeline` طريقتا `to_spec()` و`from_spec()`، وإلى `PipelineRuntime` مسارات `spec()` و`reload_from_spec()` و`reload_from_spec_file()`. يعيد runtime استخدام آلية النشر الذري القائمة؛ عند فشل التحقق أو إعادة البناء تبقى snapshot المنشورة وgeneration السابقة دون تغيير، بينما يسجل runtime حالة degraded وخطأً sanitized للمشغل.

أضيفت أوامر CLI لتصدير المواصفة والتحقق منها، كما أصبح `serve` قادرًا على تشغيل runtime من spec اختيارية مع الحفاظ على المسار التقليدي القائم على config. يدعم parser namespaces القديمة التي لا تحتوي `--spec`، ولا يمرر وسيط spec watcher إلا عند استخدامه فعليًا، وهو ما يحافظ على backward compatibility للمستهلكين والاختبارات السابقة.

## حدود التوافق والأمان

> `PipelineSpec` يحفظ إعدادات `PipelineConfig` فقط؛ لا يُعد وسيلة لتسلسل كائنات Python أو تنفيذ تعليمات من ملف JSON.

يُرفض أي schema version غير مدعوم، وأي field غير معروف، وأي config fingerprint لا يطابق configuration canonical. كما توجد حدود لحجم النص والملف قبل تحليل JSON، لأن تحليل بيانات JSON غير موثوقة دون حدود قد يؤدي إلى استهلاك غير متناسب للذاكرة أو CPU [3]. تُكتب الملفات عبر ملف مؤقت فريد ثم `os.replace`، مع تنظيف آمن عند الفشل.

لا تُحمّل المواصفة plugins تلقائيًا ولا تحتوي object references تنفيذية. يظل اكتشاف processors المثبتة مسؤولية `ProcessorRegistry` القائم، الذي اختُبر في الجولة السابقة عبر `dist-info` وentry-point metadata الفعلية. هذا الفصل يمنع تحويل ملف إعداد قابل للمراجعة إلى قناة تنفيذ غير مقصودة.

## الاختبارات وبوابات الجودة

| البوابة | النتيجة |
|---|---|
| `make verify` | ناجحة: 833 اختبارًا ناجحًا و5 تخطيات اختيارية |
| `make test-cov` | ناجحة: 833 اختبارًا ناجحًا و5 تخطيات، مع 94% تغطية كلية |
| وحدة `PipelineSpec` | 99% تغطية؛ 26 اختبارًا مستهدفًا ناجحًا |
| اختبارات runtime وserver وCLI | ناجحة ضمن البوابة الموحدة |
| installed smoke | ناجح خارج شجرة المصدر على wheel وsdist مبنيين فعليًا |
| Black | ناجح على المصدر والاختبارات والسكريبتات |
| flake8 | ناجح على المصدر والاختبارات |
| mypy | ناجح على ملفات المصدر الخاضعة للفحص |
| compileall | ناجح على `src/aranorm` |
| تدقيق الأداء | ناجح، والنتيجة محفوظة في `performance_round9.json` |
| تدقيق الأمان | ناجح، والنتيجة محفوظة في `security_round9.json` |

التخطيات الخمسة اختيارية وموثقة ضمن إعدادات الاختبار الحالية، ولا تمثل فشلًا في عقود الجولة. لم تُستخدم اختبارات شكلية لتغطية المواصفة؛ الحالات المضافة تغطي round-trip، fingerprints، JSON malformed، size limits، القراءة والكتابة الذرية، rollback، snapshots، CLI، والتشغيل من artifacts المثبتة.

## الحزم وإعادة الإنتاج

بُنيت الحزمتان التاليتان من شجرة المصدر الحالية:

| artifact | الوصف |
|---|---|
| `dist/aranorm-1.8.0-py3-none-any.whl` | wheel مستقل للمنصة |
| `dist/aranorm-1.8.0.tar.gz` | source distribution |
| `dist/SHA256SUMS-1.8.0-round9.txt` | checksums للحزمتين |
| `performance_round9.json` | قياسات الأداء القابلة لإعادة التشغيل |
| `security_round9.json` | نتائج تدقيق الأنماط الأمنية القابلة لإعادة التشغيل |

نجح `python3 -m twine check dist/*`، ونجح `compileall`، كما تحقق installed smoke من أن artifacts تصدر `PipelineRuntime` وتعمل من خارج شجرة المصدر وأن الإصدار المعلن هو `1.8.0`. يُعاد إنشاء artifacts والأرشيف بعد آخر commit لضمان أن checksums لا تشير إلى نسخة أقدم من المستودع.

## التوافق ومسار الترحيل

لا يحتاج المستخدم الحالي إلى أي تعديل. تبقى المسارات التالية مدعومة كما هي: `PipelineConfig`، و`ArabicNormalizationPipeline.from_config_dict()`، و`PipelineRuntime.reload_from_file()`، وكل أوامر normalize وbatch وserve السابقة. يمكن اعتماد `PipelineSpec` تدريجيًا عبر تصدير إعداد قائم ثم التحقق منه في بيئة أخرى قبل تمريره إلى runtime.

لا توفر المواصفة في هذه الجولة طريقة تلقائية لحفظ custom processor instances أو plugin object references. إذا احتاج المشروع مستقبلًا إلى وصف plugins، فيجب أن يكون ذلك metadata strict وقابلًا للتحقق، مع إبقاء التحميل والتنفيذ ضمن registry وسياسة تشغيل صريحة، لا ضمن parser JSON.

## الملفات الرئيسية المتغيرة

تتمثل الإضافة الأساسية في `src/aranorm/core/spec.py`، مع تكامل في `core/pipeline.py` و`core/runtime.py` وواجهات exports في `aranorm.__init__` و`aranorm.core.__init__`. أضيفت اختبارات `tests/test_pipeline_spec_round9.py` و`tests/test_cli_round9.py`، وحُدثت README وAPI_REFERENCE وARCHITECTURE وCONFIGURATION وCHANGELOG وROUND9_ROADMAP.

## التوصية وحالة الإغلاق

الجولة التاسعة جاهزة للإغلاق الفني بعد نجاح الاختبارات والتدقيقات وبناء الحزم. الخطوات الإدارية الأخيرة هي تثبيت التقرير وخارطة الطريق في commit، إعادة بناء الأرشيف النهائي بعد commit، إنشاء checksum للأرشيف، ثم تسليم artifacts. لا يُنصح برفع رقم الإصدار قبل مراجعة مستقلة للتوافق وقرار release صريح؛ لذلك يظل `1.8.0` هو الإصدار الرسمي الحالي.

## المراجع

[1]: https://packaging.python.org/specifications/entry-points/ "PyPA Entry Points Specification"

[2]: https://docs.python.org/3/library/importlib.metadata.html "Python importlib.metadata documentation"

[3]: https://docs.python.org/3/library/json.html "Python json documentation"

## مراجع المشروع وإعادة الإنتاج

يمكن إعادة إنتاج النتائج من جذر المشروع بالأوامر التالية:

```bash
make verify
make test-cov
python3 scripts/performance_audit.py > performance_round9.json
python3 scripts/security_audit.py > security_round9.json
python3 -m build
python3 -m twine check dist/*
python3 -m compileall -q src/aranorm
python3 -m pytest -q tests/test_installed_smoke.py -m 'slow and integration'
```

المرجع التنفيذي للجولة هو `ROUND9_ROADMAP.md`، أما ملاحظات قرارات التصميم والمصادر الخارجية فمحفوظة في `ROUND9_RESEARCH_NOTES.md`.
