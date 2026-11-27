# خارطة الجولة الرابعة — AraNorm 1.5.0

## 1. الهدف التنفيذي

تهدف الجولة الرابعة إلى نقل AraNorm من إصدار hardened موثوق إلى مكتبة أكثر نضجًا من ناحية **اتساق الواجهة العامة، قابلية التشغيل، اكتمال منظومة stop-words، ووضوح دورة التطوير**. ستُنفذ جميع التغييرات فوق بنية `src/aranorm` الحالية، مع الحفاظ على السلوك المتوافق في v1.4.0 وعدم إعادة كتابة pipeline أو استبدال المعالجات القائمة.

سيكون المبدأ الحاكم هو: **كل توسعة عامة يجب أن تكون typed، موثقة، قابلة للاختبار، قابلة للتراجع، ولا تضيف تبعية أساسية جديدة**.

## 2. خط أساس v1.4.0

| المؤشر | الحالة الحالية |
|---|---:|
| الإصدار | 1.4.0 |
| الفرع | `professional-hardening` |
| الاختبارات | 554 ناجحًا، مع تخطيات اختيارية موثقة |
| التغطية | 89% إجماليًا |
| التحقق | `make verify` ناجح |
| التوافق المعلن | Python >= 3.9 |
| التوافق المتحقق | Python 3.9 و3.10 و3.11 و3.12 |
| التوزيع | wheel وsdist مع تثبيت معزول ناجح |
| الأمان التشغيلي | ResourceLimits، رفض null bytes، وتدقيق regex |

## 3. نتائج التدقيق بعد الإصدار

### 3.1 فجوات الواجهة والتوثيق

تحتوي الواجهة البرمجية على عقود v1.4.0 مثل `BatchProcessingPolicy` و`PipelineHooks` و`ResourceLimits` و`ProcessingMetrics`، بينما لا تعكس `API_REFERENCE.md` كل هذه الصادرات والتوقيعات الحالية. كما أن `describe()` و`metrics_snapshot()` ومسارات policy لا تظهر بصورة كاملة في المرجع العام. هذه فجوة تعاقدية عالية الأولوية لأنها قد تؤدي إلى استخدام خاطئ رغم أن التنفيذ نفسه سليم.

### 3.2 فجوات semantics التشغيلية

تملك المعالجة المتزامنة والمتدفقة سياسات فشل، لكن `process_batch_async()` لا يقدم بعد كل أدوات parity الموجودة في المسار المتزامن، كما أن semantics الإلغاء والتوقف المبكر ليست عقدًا عامًا واضحًا. ستُدرس إضافة عقد إلغاء تعاوني خفيف، مع عدم الادعاء بإلغاء thread قيد التنفيذ قسرًا؛ الإلغاء سيكون بين العناصر وعند نقاط آمنة فقط.

### 3.3 فجوات الاختبارات اللغوية

توجد معالجات stop-word ذات منطق غير تافه، وعلى رأسها `PhraseStopProcessor` و`MorphologicalStopProcessor`، دون عقود اختبار مستقلة كافية. سيتم اختبار greedy longest-match، علامات الترقيم، modes، registries، صيغ اللواصق والتصريف، العزل بين instances، وسلامة `ProcessorContext`.

### 3.4 فجوات builder والتهيئة

يقبل `PipelineBuilder` بعض الخيارات بصمت عند عدم تطابق الاسم مع حقل config. هذا السلوك يخفي الأخطاء الإملائية ويضعف قابلية التشخيص. سيتم إدخال validation صريح للخيارات الجديدة مع الحفاظ على aliases المعلنة والتوافق مع الاستخدامات الصحيحة، وإضافة اختبارات regression للخيارات غير المعروفة.

### 3.5 فجوات التكامل والتوزيع

تحتاج الاختبارات الاختيارية إلى مصفوفة أوضح لمسارات غياب PyYAML وpandas وtqdm وCAMeL Tools وTransformers، كما تحتاج الوثائق إلى فصل واضح بين core الخفيف والتكاملات التي تتطلب extras. سيتم تحسين smoke tests المثبتة من wheel مع إبقاء التبعيات الاختيارية خارج التثبيت الأساسي.

## 4. مسارات التنفيذ

| المسار | العمل التزايدي | معيار القبول |
|---|---|---|
| A — API | مزامنة API_REFERENCE، توثيق hooks/metrics/policies/limits، وتثبيت exports | لا توجد واجهة عامة مطبقة غير موثقة، وتنجح أمثلة API |
| B — Contracts | إضافة عقد إلغاء تعاوني أو رفضه بتوثيق صريح بعد الاختبار، وتحسين parity للمسار async | semantics موحدة، ترتيب ثابت، وإغلاق executor في النجاح والفشل والإلغاء |
| C — Builder/Config | رفض الخيارات غير المعروفة برسالة تشخيصية، واختبار aliases وround-trip | لا يمر typo صامتًا، ولا ينكسر config v1.4.0 |
| D — Stop Words | اختبارات phrase/morphological ودعم context وpunctuation والحدود | تغطية الوحدات المستهدفة >= 90%، مع regression tests لكل سلوك |
| E — Integrations | اختبارات optional isolation وCLI/reporting للمفقودات | import core بلا optional deps، ورسائل تثبيت واضحة |
| F — Performance | قياس تكلفة validation وstreaming وphrase indexing، دون micro-optimization غير مقاس | لا تراجع أكبر من 5% في baseline المعتمد، أو تفسير موثق |
| G — Documentation | تحديث README/API/CONFIGURATION/TESTING وكتابة migration notes | الأمثلة قابلة للتنفيذ وتطابق التوقيعات الحالية |
| H — Release | CI، changelog، build، isolated install، تقرير وأرشيف | `make verify`، build، smoke، وartifact checksums ناجحة |

## 5. ترتيب التنفيذ

### المرحلة A — تثبيت baseline والcontracts

يُعاد تشغيل الاختبارات والتغطية والـ static checks قبل أي تعديل، ثم تُثبت الاختبارات التي تصف السلوك الحالي للـ builder والـ async والـ stop-word processors. لا يُسمح بتعديل إنتاجي قبل وجود اختبار يحدد العقد المراد تحسينه.

### المرحلة B — تحسينات API والتشغيل

تُضاف التغييرات الصغيرة ذات القيمة العالية: parity موثق للمسارات، validation واضح، وعقد إلغاء تعاوني إن أثبتت المراجعة أنه لا يسبب تعقيدًا أو كسرًا. تُحافظ الدوال القديمة على توقيعاتها عبر معاملات اختيارية وقيم افتراضية متوافقة.

### المرحلة C — توسيع المعالجات والاختبارات

تُستكمل اختبارات phrase/morphological، ثم تُضاف regression tests للـ Unicode والترقيم والفراغات والـ context والـ registry injection. أي إصلاح سلوكي يجب أن يذكر سبب التغيير ويثبت عدم الانحدار في الحالات السابقة.

### المرحلة D — التوثيق والتكاملات

تُزامن الوثائق مع exports الفعلية، وتُراجع أمثلة CLI وPython، وتُختبر رسائل غياب التبعيات الاختيارية. تُحفظ الوثائق العربية أو الإنجليزية الحالية دون حذف، مع إضافة ملاحظات انتقالية عند تغير سلوك معلن.

### المرحلة E — التدقيق النهائي والإصدار

تُقاس الأداءات قبل وبعد، وتُجرى اختبارات الأمان والتوافق والبناء والتثبيت المعزول، ثم يُرفع الإصدار إلى 1.5.0 فقط إذا تحققت بوابة الجودة الكاملة. يُنشأ تقرير إصدار وأرشيف مصدر نظيف مع checksums.

## 6. مصفوفة الاختبارات الجديدة

| الطبقة | الملف المقترح | الغرض |
|---|---|---|
| Stop Words | `tests/test_phrase_stop_processor.py` | greedy matching، modes، registry، punctuation |
| Stop Words | `tests/test_morphological_stop_processor.py` | clitics، verb forms، definite article، flags |
| Builder | `tests/test_builder_contracts.py` | aliases، unknown options، chaining، immutability |
| Async | `tests/test_async_contracts.py` | ordering، skip/collect/fail-fast، cancellation semantics |
| Integrations | `tests/test_optional_dependency_contracts.py` | lazy import ورسائل التثبيت |
| API | `tests/test_public_api_exports.py` | exports وversion وserializable descriptions |
| Regression | `tests/test_round4_regressions.py` | كل إصلاح مرتبط بعطل أو فجوة محددة |
| Packaging | `tests/test_installed_smoke.py` | wheel وsdist خارج شجرة المصدر |

## 7. قواعد عدم الانحدار

تبقى نتائج `process()` الحالية ثابتة للحالات نفسها. تبقى `process_batch()` مادية ومحافظة على الترتيب، وتبقى `process_iter()` متدفقة ومحدودة الذاكرة. لا تُفرض تبعية تشغيلية جديدة على المستخدم الأساسي. لا يُستخدم الإلغاء القسري لخيوط Python، ولا تُخفى أخطاء callback أو hook دون تسجيل واضح وإعادة الخطأ الأصلي.

## 8. معايير الخروج للإصدار

لا يُعتبر الإصدار جاهزًا إلا عند تحقق الشروط الآتية:

1. نجاح baseline وجميع الاختبارات الجديدة دون flaky tests.
2. تغطية إجمالية لا تقل عن 90% أو تفسير موثق لكل فجوة اختيارية، وتغطية >=90% للوحدات المستهدفة.
3. نجاح Black وflake8 وmypy وcompileall على source وscripts.
4. نجاح الاختبارات على Python 3.9–3.12، مع إبقاء Python 3.13 في CI إن كانت التبعيات متاحة.
5. نجاح wheel وsdist و`twine check` والتثبيت المعزول وsmoke للواجهة وCLI.
6. تطابق API_REFERENCE وREADME وCONFIGURATION مع الكود الفعلي.
7. وجود CHANGELOG وتقرير إصدار وchecksums وأرشيف نظيف وcommit مستقل.

## 9. قرارات خارج النطاق لهذه الجولة

تُؤجل ميزات النماذج الثقيلة مثل GPU batching وdiacritization وspelling correction وNER إلى جولة مستقلة بعد تثبيت عقود التشغيل. كما لا تُضاف خدمة HTTP أو Docker كجزء تلقائي من المكتبة الأساسية قبل وجود قرار منتج منفصل حول دورة النشر والاعتماديات.

## 10. مراجع المعايير

[1]: https://packaging.python.org/en/latest/tutorials/packaging-projects/ "Python Packaging User Guide — Packaging Python Projects"
[2]: https://docs.pytest.org/en/stable/explanation/goodpractices.html "pytest — Good Integration Practices"
[3]: https://docs.python.org/3/library/asyncio-task.html "Python Documentation — Coroutines and Tasks"
[4]: https://peps.python.org/pep-0544/ "PEP 544 — Protocols: Structural subtyping"
