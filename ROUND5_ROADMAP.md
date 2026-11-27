# خارطة الجولة الخامسة — AraNorm 1.6.0

## 1. الهدف التنفيذي

تهدف الجولة الخامسة إلى رفع AraNorm من مكتبة ناضجة ذات عقود معالجة قوية إلى مكوّن أكثر جاهزية للتشغيل المؤسسي والمراقبة والدمج الآلي. ستُبنى جميع التغييرات فوق `src/aranorm` الحالي، مع الحفاظ على واجهات v1.5.0 وعدم إعادة كتابة pipeline أو استبدال المعالجات القائمة.

المبدأ الحاكم هو أن كل توسعة عامة يجب أن تكون **typed، موثقة، قابلة للاختبار، قابلة للتراجع، ولا تضيف تبعية أساسية جديدة**. لن تُضاف خدمة HTTP أو نماذج ثقيلة أو تغييرات في semantics التطبيع ضمن هذه الجولة؛ الأولوية هي قابلية التشغيل والوضوح والتكامل الآمن.

## 2. خط أساس v1.5.0

| المؤشر | الحالة الحالية |
|---|---:|
| الإصدار | 1.5.0 |
| الفرع | `professional-hardening` |
| الاختبارات | 595 ناجحًا، مع تخطيين اختياريين موثقين |
| التغطية | 91% إجماليًا في تقرير الجولة الرابعة |
| التحقق | `make verify` ناجح |
| التوافق المعلن | Python >= 3.9 |
| التوافق المتحقق | Python 3.9 و3.10 و3.11 و3.12 |
| التوزيع | wheel وsdist مع `twine check` وتثبيت معزول ناجح |
| الأمان التشغيلي | ResourceLimits، null-byte guard، regex audit، single-flight |
| الإلغاء | `CancellationToken` تعاوني في sync وstreaming وasync |

## 3. نتائج التدقيق وفجوات الجولة الخامسة

### 3.1 Observability غير مكتملة

تملك `ProcessingMetrics` counters وsnapshot آمنًا للتزامن، لكن عقد التشغيل ما زال يقتصر على dict بسيط. لا توجد واجهة موحدة لحفظ snapshot كـ JSON، أو دمج snapshots من workers، أو مقارنة snapshot قبل/بعد تشغيل دفعة ضمن أدوات المراقبة. المطلوب توسعة صغيرة لا تغيّر كلفة المعالجة الافتراضية ولا تجعل telemetry تبعية إجبارية.

### 3.2 قابلية التتبع والتشخيص

تعرض `describe()` إعدادات pipeline، لكنها لا توفر fingerprint ثابتًا أو schema version يمكن استخدامه في logs وcache keys والتقارير. كما أن نتائج المعالجة لا تحمل معرف تشغيل اختياريًا يربط callbacks والmetrics بالدفعة. ستُدرس إضافة metadata تشغيلية اختيارية فقط، مع عدم تغيير نصوص التطبيع أو equality semantics القديمة.

### 3.3 عقود serialization والتوافق

توجد عدة نتائج وعقود قابلة للتحويل إلى dict، لكن الاختبارات لا تغطي بصورة موحدة JSON round-trip للـ metrics والوصف وملفات التقارير، ولا تثبت رفض البيانات التالفة برسائل واضحة. ينبغي توحيد الاختبارات وإضافة schema identifiers حيث يكون ذلك غير كاسر.

### 3.4 CLI وواجهات التشغيل الآلي

يحتوي CLI على أوضاع batch وstreaming، لكن التشغيل الآلي يحتاج مخرجات machine-readable ثابتة للحالة والmetrics وversion، مع المحافظة على المخرجات النصية الحالية. ستُضاف خيارات محدودة ومثبتة باختبارات end-to-end بدل تغيير السلوك الافتراضي.

### 3.5 التوافق مع plugins والتكاملات

يوجد entry-point discovery وoptional integrations، لكن الجولة التالية تحتاج اختبارات أقوى للتعارضات، الترتيب الحتمي، فشل plugin المعزول، وإعادة المحاولة أو الرسالة القابلة للتشخيص. لا يُسمح لـ plugin واحد غير صالح بأن يفسد تسجيل المعالجات الأساسية دون خطأ صريح قابل للتتبع.

### 3.6 فجوات الاختبارات والوثائق

تحتاج وحدات metrics وregistry وCLI والتقارير إلى اختبارات عقود إضافية، كما يجب تحديث README وAPI_REFERENCE وCONFIGURATION وTESTING بوصف versioned schemas وoperational usage. كل مثال جديد يجب أن يكون قابلًا للتشغيل أو مرتبطًا باختبار يثبت توقيعه.

## 4. مسارات التنفيذ ومعايير القبول

| المسار | العمل التزايدي | معيار القبول |
|---|---|---|
| A — Metrics | serialization، JSON، reset/merge أو بديل موثق، schema ثابت | round-trip آمن، thread-safety محفوظة، ولا تتغير نتائج process |
| B — Introspection | fingerprint وschema version وdescribe موسع بصورة backward-compatible | قيمة ثابتة لنفس config، اختلاف واضح عند اختلاف config، واختبارات regression |
| C — CLI | version/status أو مخرجات JSON محدودة للـ metrics والتشخيص | مخرجات قابلة للتحليل، exit codes واضحة، ولا ينكسر النص الحالي |
| D — Registry | deterministic discovery، duplicate handling، وعزل فشل plugin | ترتيب ثابت، خطأ تشخيصي، وعدم تلوث registry الأساسي |
| E — Integrations | تثبيت مصفوفة optional dependency failures وinstalled smoke | core يعمل بلا extras، ورسائل مفقودات ثابتة |
| F — Testing | عقود round-trip، hostile payloads، concurrency، CLI E2E، compatibility | تغطية إجمالية >=92% أو تفسير موثق، ولا flaky tests |
| G — Documentation | تحديث الوثائق وخطة migration وإضافة أمثلة قابلة للتحقق | لا توجد واجهة عامة جديدة غير موثقة |
| H — Release | تدقيق performance/security/compatibility، build، install، report، archive | `make verify` وbuild وsmoke وchecksums ناجحة |

## 5. ترتيب التنفيذ

### المرحلة الأولى — baseline وتصميم العقود

يُعاد تشغيل الاختبارات والتغطية والفحوص الساكنة، ثم تُثبت العقود الجديدة باختبارات فاشلة أو محددة قبل تعديل الإنتاج. تُراجع تكلفة أي telemetry في المسار الساخن، ويُحافظ على default behavior الحالي.

### المرحلة الثانية — observability وintrospection

تُضاف واجهات serialization والتقارير التشغيلية فقط إذا أمكن تنفيذها دون تبعية أساسية أو coupling مع logger خارجي. يُصمم fingerprint من representation مستقرة للإعدادات، ويُختبر ضد ترتيب القواميس والقوائم والحالات الاختيارية.

### المرحلة الثالثة — CLI وregistry/integrations

تُضاف المخرجات الآلية والاختبارات end-to-end، ثم تُقوى discovery بحالات duplicate وbroken entry point مع رسائل صريحة. لا تُخفي أخطاء plugin؛ إما أن تُجمع في تقرير معلن أو تُرفع وفق سياسة موثقة.

### المرحلة الرابعة — الاختبارات والوثائق

تُضاف ملفات اختبار مستقلة للـ metrics، introspection، CLI automation، registry isolation، serialization failures، والتوافق. تُحدّث الوثائق بالتزامن مع code changes، وتُراجع جميع الأمثلة عبر الاختبارات أو smoke scripts.

### المرحلة الخامسة — التدقيق والإصدار

تُقارن النتائج مع baseline v1.5.0، وتُشغل security/performance audits، وتُختبر Python 3.9–3.12، ثم يُرفع الإصدار إلى 1.6.0 فقط بعد اكتمال بوابة الجودة وبناء artifacts وتقرير الإصدار والأرشيف.

## 6. مصفوفة الاختبارات المقترحة

| الطبقة | الملف المقترح | الغرض |
|---|---|---|
| Metrics | `tests/test_metrics_serialization.py` | JSON round-trip، schema، reset، snapshots immutable |
| Introspection | `tests/test_pipeline_introspection.py` | fingerprint، describe، config determinism |
| CLI | `tests/test_cli_machine_output.py` | version/status/JSON، exit codes، stdout stability |
| Registry | `tests/test_registry_resilience.py` | duplicate entry points، broken plugins، deterministic order |
| Integrations | `tests/test_integration_matrix.py` | optional dependency isolation والرسائل |
| Serialization | `tests/test_operational_serialization.py` | malformed payloads، unknown fields، defensive copies |
| Security | `tests/test_round5_security.py` | hostile metadata وlimits وعدم تسرب أسرار |
| Packaging | `tests/test_installed_smoke.py` | wheel وsdist خارج شجرة المصدر |

## 7. قواعد عدم الانحدار

تبقى نتائج `process()` و`process_batch()` و`process_iter()` ثابتة للمدخلات نفسها ما لم يُوثق إصلاح أمني أو bug واضح. تبقى التبعيات الاختيارية خارج التثبيت الأساسي. لا تُسجل النصوص الأصلية أو normalized text في telemetry افتراضيًا. لا يُسمح لأي fingerprint أو schema جديد بتغيير cache behavior دون خيار صريح. لا تُخفى أخطاء callbacks أو plugins، ولا يتم إلغاء threads قسرًا.

## 8. معايير الخروج

لا يعتبر v1.6.0 جاهزًا إلا عند نجاح baseline وجميع الاختبارات الجديدة، وصول التغطية إلى 92% أو وجود تفسير موثق للفجوات، نجاح Black وflake8 وmypy وcompileall، نجاح اختبارات التوافق، تحقق round-trip للحزم والتقارير، نجاح wheel وsdist و`twine check` والتثبيت المعزول، تطابق الوثائق مع الواجهات الفعلية، وجود CHANGELOG وتقرير إصدار وchecksums وأرشيف نظيف وcommit مستقل.

## 9. خارج النطاق

تُؤجل REST API server mode، Docker runtime، GPU batching، diacritization، spell-checker، NER، وتكاملات السجلات الخارجية إلى جولات مستقلة بعد تثبيت عقود المراقبة والسياسات الأمنية ودورة الإصدارات الخاصة بها.

## 10. مراجع المعايير

[1]: https://keepachangelog.com/en/1.0.0/ "Keep a Changelog"
[2]: https://packaging.python.org/en/latest/specifications/core-metadata/ "Python Core Metadata Specification"
[3]: https://docs.python.org/3/library/json.html "Python JSON documentation"
[4]: https://docs.python.org/3/library/importlib.metadata.html "Python importlib.metadata documentation"
