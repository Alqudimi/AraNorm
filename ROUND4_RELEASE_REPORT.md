# تقرير إصدار AraNorm v1.5.0 — الجولة الرابعة

**المشروع:** AraNorm — مكتبة Python لتطبيع النصوص العربية

**الإصدار:** 1.5.0

**تاريخ الإصدار:** 16 أغسطس 2026

**نطاق التقرير:** الجولة الرابعة من التطوير بعد الإصدار v1.4.0

> هذا الإصدار توسعة تزايدية فوق المعمارية القائمة. لم تتم إعادة كتابة المشروع؛ أضيفت العقود والقدرات الجديدة إلى المسارات الحالية مع الحفاظ على التوافق الخلفي للاستخدامات المعتمدة في v1.4.0.

## 1. الملخص التنفيذي

يركز الإصدار v1.5.0 على رفع نضج AraNorm من مكتبة تطبيع قوية إلى مكوّن تشغيلي أكثر قابلية للدمج في الخدمات طويلة التشغيل والأنظمة المتوازية. تم توسيع pipeline المتزامن والمتدفق وغير المتزامن بعقد إلغاء تعاوني آمن للتزامن، كما تمت مطابقة semantics المسار غير المتزامن مع المسار المتزامن في حدود الدفعات، ترتيب النتائج، callbacks، fallback، وسياسات الفشل.

شملت الجولة كذلك تقوية `PipelineBuilder` ضد الحقول المجهولة والقيم غير الصالحة مع ضمان atomicity، وعزل registries المحقونة في معالجات stop-word، وتحسين اكتشاف اللواصق الشائعة في المعالجة الصرفية، وإضافة اختبارات عقود مستقلة للتكاملات الاختيارية. تم تحديث README وAPI_REFERENCE وCHANGELOG لتوثيق السطح العام الجديد بدل ترك السلوك التشغيلي في الكود وحده.

## 2. التغييرات الرئيسية

| المجال | التغيير | الأثر التشغيلي |
|---|---|---|
| الإلغاء | إضافة `CancellationToken` و`ProcessingCancelledError` | إيقاف تعاوني آمن دون إلغاء قسري للخيوط النشطة |
| المعالجة غير المتزامنة | توحيد bounded submission وstable ordering وcallbacks وسياسات الفشل | تقليل الفروق بين sync وasync وتحسين قابلية التنبؤ |
| Builder | resolver للـ aliases ورفض unknown options وقيم غير منطقية atomically | منع الإعدادات الصامتة والـ partial mutation |
| Stop-word processors | عزل registry والتحقق المبكر من mode ودعم clitic conjunctions | تقليل تسرب الحالة وتحسين التغطية العربية العملية |
| التكاملات الاختيارية | اختبارات deterministic لغياب pandas وdatasets وspaCy وNLTK | رسائل فشل واضحة دون تحميل تبعيات إضافية أساسية |
| التوثيق | تحديث README وAPI_REFERENCE وإضافة خارطة الجولة | سهولة الاكتشاف والاستخدام والمراجعة المستقبلية |
| إصدار الحزمة | ترقية metadata إلى 1.5.0 وبناء wheel وsdist | artifacts قابلة للتثبيت والتحقق عبر `twine check` |

## 3. التفاصيل المعمارية

### 3.1 الإلغاء التعاوني

`CancellationToken` مبني على `threading.Event` ويعرض واجهة صغيرة مستقرة: `cancel()` و`is_cancelled` و`raise_if_cancelled()`. يفحص pipeline الإشارة قبل بدء المعالجة، وعند حدود الدفعات، وبين العناصر، وقبل استهلاك النتائج. إذا كان هناك worker ينفذ processor بالفعل، فلا تتم محاولة إيقافه قسرًا؛ يضمن ذلك سلوكًا أكثر أمانًا مع processors غير القابلة للإلغاء.

تمت إضافة المعامل في نهاية توقيعات `process_batch()` و`process_iter()` للحفاظ على الاستدعاءات الموضعية القديمة. أما `process_batch_async()` فاحتفظ بموضع `policy` المستخدم في v1.4.0 وأضاف الخيارات الجديدة بصيغة keyword-only حيث يلزم.

### 3.2 parity في المسار غير المتزامن

أصبح المسار async يطبق حدود `batch_size` و`n_workers` قبل إنشاء executor، ويرسل دفعة محدودة في كل مرة، ويحافظ على ترتيب الإدخال، ويمرر `on_error` و`progress_callback` و`BatchProcessingPolicy`، ويغلق executor عبر `finally`. الإلغاء يوقف إرسال العمل الجديد واستهلاك النتائج عند أقرب حد آمن، مع الحفاظ على lifecycle الخاص بـ `on_start` و`on_item` و`on_finish`.

### 3.3 صرامة PipelineBuilder

ينفذ builder الآن عملية resolve كاملة للخيارات قبل تعديل configuration. تُقبل aliases المعلنة فقط، وتُرفض الحقول المجهولة والقيم غير المنطقية برسالة تشخيصية، ولا تبقى أي mutation جزئية إذا فشل أحد الخيارات اللاحقة. هذا يرفع وضوح API ويمنع أخطاء typo الصامتة في البيئات الإنتاجية.

### 3.4 معالجات stop-word

تتحقق `PhraseStopProcessor` من mode مبكرًا وتعزل registry المحقون بدل الاحتفاظ بحالة خارجية قابلة للتلوث بين instances. كما أصبح `MorphologicalStopProcessor` يلتقط الواو والفاء العاطفتين في مواضع محدودة قبل المقالة التعريفية أو صيغ الوقف، مع حماية الكلمات العربية العادية من الإزالة الزائدة.

## 4. نتائج الاختبارات والجودة

| الفحص | النتيجة |
|---|---:|
| الاختبارات الكاملة | 595 ناجحًا |
| الاختبارات المتخطاة | 2 اختياريان: PyYAML وscikit-learn غير مثبتين |
| إجمالي التغطية | 91% من مصدر الحزمة |
| Black | ناجح |
| flake8 | ناجح |
| mypy | ناجح بلا أخطاء في 86 ملف مصدر |
| `make verify` | ناجح |
| compile على Python 3.9 | ناجح |
| compile على Python 3.10 | ناجح |
| compile على Python 3.11 | ناجح |
| compile على Python 3.12 | ناجح |
| `twine check` | ناجح لكل من wheel وsdist |
| تثبيت wheel في بيئة Python 3.12 معزولة | ناجح |
| smoke test للواجهة العامة والإصدار | ناجح |

توجد تفاصيل التغطية الكاملة في `coverage_round4.xml`. وتثبت suites الجديدة عقود الإلغاء، parity async، builder، stop-word processors، exports العامة، التكاملات الاختيارية، والأمن. بقي التخطي محصورًا في تبعيات اختيارية غير مطلوبة للتثبيت الأساسي.

## 5. نتائج الأداء

تم تشغيل `scripts/performance_audit.py` على بيئة الإصدار وحفظ الناتج في `performance_round4.json`.

| القياس | النتيجة المرصودة |
|---|---:|
| عناصر الإدخال المتكرر | 1,000 |
| cache hits بعد أول miss | 999 |
| التسريع التسلسلي المقاس | نحو 473x |
| concurrent callers في single-flight | 16 |
| استدعاءات pipeline الفعلية مع single-flight | 1 |
| الاستدعاءات في baseline غير المخزّن | 16 |
| عناصر streaming المقاسة | 10,000 |
| throughput streaming المقاس | نحو 590 نصًا/ثانية |
| peak allocations المرصودة عبر tracemalloc | نحو 6 KB |

الأرقام benchmarks إرشادية وتتأثر ببيئة التشغيل، لكنها تثبت الاتجاه التشغيلي المطلوب: عدم تكرار العمل المتزامن للنص نفسه، ومعالجة streaming بذاكرة محدودة نسبيًا، وعدم تحويل corpus كامل إلى قائمة في المسارات المتدفقة.

## 6. نتائج الأمان

تم تشغيل `scripts/security_audit.py` على الأنماط المحلية المستخدمة في URL وemail وmention وhashtag وHTML وArabizi، مع أحجام adversarial متدرجة حتى 20,000 حرف. بقيت جميع القياسات في نطاق دون ميلي ثانية تقريبًا عند الحجم الأعلى في العينة، ولم يظهر نمو كارثي في backtracking.

كما تثبت `tests/test_security_hardening.py` رفض النصوص التي تتجاوز `ResourceLimits.max_text_length`، ورفض null bytes عند تفعيل السياسة، والتحقق المبكر من `batch_size` و`n_workers` قبل إنشاء executor. تم حفظ النتائج الخام في `security_round4.json`.

> لا تعني نتائج regex audit أن كل نمط مستقبلي سيكون آمنًا تلقائيًا؛ يجب إعادة تشغيل التدقيق عند إضافة patterns جديدة أو تغيير patterns الحالية.

## 7. التوافق والتعبئة

يحافظ المشروع على `requires-python = ">=3.9"`. نجحت اختبارات compile على Python 3.9 و3.10 و3.11 و3.12، كما اجتازت بوابة الجودة على البيئة الحالية. لم تتم إضافة تبعية أساسية جديدة؛ ظلت pandas وHuggingFace وspaCy وNLTK وscikit-learn وPyYAML اختيارية.

تم بناء artifactين نهائيين:

| الملف | الوصف | SHA-256 |
|---|---|---|
| `dist/aranorm-1.5.0-py3-none-any.whl` | wheel universal pure-Python | `c6a4acda04267dea237987e57294f49a3cd026125a7081e0032fccf010a6211f` |
| `dist/aranorm-1.5.0.tar.gz` | source distribution | `d6eb87d88dcb68e60f557139b6599973317e6ec45e9eb456ad30910307cde48a` |

نجح `twine check` للحزمتين، ونجح تثبيت wheel في بيئة Python 3.12 معزولة مع تحقق `aranorm.__version__ == "1.5.0"` وتشغيل pipeline فعلي.

## 8. الملفات والـ artifacts

| الملف | الغرض |
|---|---|
| `ROUND4_ROADMAP.md` | خارطة الجولة الرابعة ومعايير القبول |
| `ROUND4_RELEASE_REPORT.md` | هذا التقرير |
| `performance_round4.json` | نتائج benchmark للكاش وsingle-flight وstreaming |
| `security_round4.json` | نتائج قياس الأنماط adversarial |
| `coverage_round4.xml` | تقرير تغطية XML قابل للمعالجة آليًا |
| `dist/aranorm-1.5.0-py3-none-any.whl` | حزمة wheel |
| `dist/aranorm-1.5.0.tar.gz` | حزمة المصدر |
| `tests/test_cancellation_contracts.py` | عقود CancellationToken وstreaming |
| `tests/test_async_contracts.py` | تكامل parity للمسار async |
| `tests/test_builder_contracts.py` | عقود PipelineBuilder |
| `tests/test_phrase_stop_processor.py` | عقود PhraseStopProcessor |
| `tests/test_morphological_stop_processor.py` | عقود MorphologicalStopProcessor |
| `tests/test_optional_dependency_contracts.py` | اختبارات غياب التبعيات الاختيارية |
| `tests/test_public_api_exports.py` | اختبارات الواجهة العامة |

## 9. المخاطر المتبقية وخارطة العمل التالية

لا يزال إلغاء processor الجاري تنفيذُه إلغاءً تعاونيًا على مستوى pipeline، وليس interrupt قسريًا داخل thread. هذا مقصود لأسباب السلامة، لكنه يعني أن زمن التوقف الأعلى قد يساوي زمن أطول processor نشط.

لم تُنفذ في هذه الجولة REST API server mode أو spell-checker أو نماذج ML جديدة؛ بقيت هذه العناصر في قسم Planned لأنها تحتاج عقودًا منفصلة للأداء، وإدارة الموارد، وإصدارات النماذج، وأمن الشبكة. كما أن الاختبارات التي تتطلب PyYAML وscikit-learn تستمر في التخطي عندما لا تكون التبعيات الاختيارية مثبتة، بينما يظل core قابلًا للتثبيت والعمل دونها.

الأولوية المنطقية للجولة التالية هي إضافة observability قابلة للتصدير، واختبارات compatibility كاملة داخل CI لكل نسخ Python المعلنة، وتحسين التوثيق التفاعلي، ثم دراسة server mode بعد تثبيت عقود المصادقة والحدود ومراقبة الموارد.

## 10. معايير قبول الإصدار

يُعد الإصدار v1.5.0 مقبولًا للإطلاق وفق المعايير التالية: نجاح `make verify`، بقاء التغطية فوق خط v1.4.0، نجاح mypy وflake8 وBlack، نجاح compile على نسخ Python المدعومة، نجاح بناء wheel وsdist، نجاح `twine check`، نجاح تثبيت wheel في بيئة معزولة، وتوافر تقارير الأداء والأمان والتغطية كملفات قابلة للمراجعة. تحققت جميع هذه المعايير.

## المراجع

[1]: https://keepachangelog.com/en/1.0.0/ "Keep a Changelog"

[2]: https://packaging.python.org/en/latest/specifications/core-metadata/ "Python Core Metadata Specification"

[3]: https://docs.python.org/3/library/concurrent.futures.html "Python concurrent.futures documentation"

[4]: https://docs.python.org/3/library/threading.html#threading.Event "Python threading.Event documentation"
