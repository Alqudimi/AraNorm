# خارطة الجولة السابعة — AraNorm 1.8.0

## 1. الهدف

توسيع AraNorm فوق الإصدار 1.7.0 بإغلاق فجوة التكافؤ بين retry المتزامن وغير المتزامن، وتحسين قابلية تشغيل الخدمة والمراقبة، ورفع صلابة العقود العامة والاختبارات، دون إعادة كتابة أي مكوّن قائم أو كسر واجهات الإصدارات السابقة.

## 2. خط الأساس المثبت

| المعيار | الحالة |
|---|---|
| الإصدار | 1.7.0 |
| الاختبارات | 731 ناجحًا، 5 تخطيات اختيارية موثقة |
| التغطية | 93% من 4,477 سطرًا |
| الجودة | Black وflake8 وmypy ناجحة |
| التوافق المثبت | Python 3.10 و3.11 و3.12؛ الحد الأدنى المعلن Python 3.9 |
| آخر commit | `b130212` — round 6 architectural hardening |

## 3. الفجوات المقاسة

أظهر تقرير التغطية أن أضعف المناطق الحالية هي `core.base` (74%)، و`cli` (80%)، و`helpers` (80%)، و`phrase_stop_processor` (84%)، و`readability` (85%)، و`dialect_id` (86%)، و`config` (89%)، و`number_words_processor` (89%). كما أن `process_batch_retry()` متاح في المسار المتزامن فقط، بينما يوجد `process_batch_async()` مستقل، وهو يترك تكافؤًا وظيفيًا مهمًا غير مكتمل. وتبقى أوامر CLI التشغيلية الحالية غير موحدة في تفعيل trace أو إعادة المحاولة.

## 4. مسارات التنفيذ

### المسار A — Async retry parity

إضافة `process_batch_retry_async()` فوق `process_batch_async()` مع نفس عقد `BatchRetryReport`، وترتيب النتائج، وحد `max_retries`، ومعالجة `max_retries=0`، والإلغاء التعاوني، ومسارات catastrophic failure. يجب ألا يتغير سلوك `process_batch_retry()` أو `process_batch_async()` الحالي عند عدم استخدام الواجهة الجديدة.

### المسار B — Retry policy contract

إضافة عقد typed اختياري `BatchRetryPolicy` قابل للتحقق والتسلسل، يضم الحدود المعلنة لإعادة المحاولة، وحجم الدفعة، وعدد العمال، وسلوك الفشل. يُستخدم كواجهة مستقبلية قابلة للتوسع، مع إبقاء المعاملات القديمة في `process_batch_retry()` متوافقة backward-compatible. يمنع العقد القيم المنطقية المتخفية كأعداد، والقيم السالبة، والحدود التي تتجاوز `ResourceLimits`.

### المسار C — Operational CLI and diagnostics

توسيع CLI دون تغيير الأوامر الحالية بإضافة flags اختيارية لتفعيل `steps_trace` وإعادة المحاولة في مسارات normalize/batch، مع مخرجات JSON ذات schema ثابتة، وإخفاء النصوص الحساسة من التشخيص والـ telemetry. يضاف اختبار E2E لكل flag مع التحقق من رسائل الأخطاء وقابلية التشغيل خارج شجرة المصدر.

### المسار D — Coverage and hostile-contract hardening

إضافة اختبارات مكثفة للأجزاء منخفضة التغطية: `ProcessorContext` lifecycle وmerge، حدود `PipelineConfig`، مسارات registry الفاشلة، CLI errors، readability edge cases، dialect ambiguity، phrase stop-word boundaries، number words، والـ helpers. تضاف اختبارات property-based جديدة لثبات الترتيب، parity بين sync/async، وعدم تسرب النصوص في التقارير.

### المسار E — Documentation and release readiness

تحديث `API_REFERENCE.md` و`README.md` و`CHANGELOG.md` بعقود retry async وpolicy وCLI، وإنشاء تقرير `ROUND7_RELEASE_REPORT.md`، ثم تشغيل بوابة الجودة، وتدقيق الأداء والأمان، وبناء wheel وsdist وtwine check، وcompile عبر المفسرات المتاحة، وإنشاء checksums وأرشيف نظيف.

## 5. قواعد عدم الانحدار

تبقى جميع الاختبارات الحالية ناجحة. تبقى التبعيات الاختيارية خارج التثبيت الأساسي. لا تُخزَّن النصوص الأصلية أو النصوص المطَبَّعة في metrics أو retry reports أو fingerprints. لا يُفرض إلغاء قسري على thread عامل. تبقى `process_batch_retry()` و`process_batch_async()` و`NormalizationResult` و`BatchProcessingError` متوافقة مع الاستدعاءات القديمة. أي flag جديد في CLI يكون opt-in، وأي trace جديد لا يعمل افتراضيًا.

## 6. معايير القبول

| المعيار | الهدف |
|---|---|
| اختبار كامل | لا يقل عن 800 اختبار ناجح أو يعادل ذلك بعد توحيد اختبارات property-based |
| التغطية | 94% على الأقل، مع رفع الملفات الحرجة منخفضة التغطية بوضوح |
| الجودة الساكنة | Black وflake8 وmypy بلا أخطاء |
| async parity | حالات success/failure/recovery/order/cancellation/catastrophic موثقة ومختبرة |
| serialization | round-trip وmalformed وunknown fields وdefensive copy لـ policy وreport |
| الأمان | لا تسرب نصوص، وحدود retry وbatch/workers مرفوضة مبكرًا |
| الحزم | wheel وsdist وtwine check وinstalled smoke خارج المصدر |
| الإصدار | 1.8.0 مع CHANGELOG وتقرير وأرشيف وSHA256SUMS |

## 7. ما يبقى خارج نطاق الجولة

يبقى خادم REST مستقل، وتكامل المصحح الإملائي العربي، وDocker/GPU batching، وNER، وتكاملات السجلات الخارجية خارج نطاق هذه الجولة ما لم تكشف الاختبارات ضرورة مباشرة لها؛ ستوثق كمسارات مستقبلية بدل إدخال تبعيات ثقيلة أو تغيير طبيعة الحزمة الأساسية.

## 8. ترتيب التنفيذ

يبدأ التنفيذ بالعقد `BatchRetryPolicy` ثم async retry parity، وبعد تثبيت semantics تُكتب اختبارات العقد والتسلسل. بعد ذلك تُوسّع CLI، ثم تُغلق فجوات التغطية وتُحدّث الوثائق، وأخيرًا تُنفّذ بوابة الجودة والتدقيق والبناء والإصدار.

## 9. تاريخ الوثيقة

- 16 أغسطس 2026: إنشاء خارطة الجولة السابعة بعد تثبيت baseline 1.7.0.
- المؤلف: Manus AI.

---

## ROUND7_RELEASE_CHECKLIST

- [x] `BatchRetryPolicy` typed contract and exports
- [x] `process_batch_retry_async()` with cancellation and ordering
- [x] CLI opt-in trace/retry flags and JSON schemas
- [x] Coverage-gap and hostile-contract tests
- [x] API/README/CHANGELOG updates
- [x] `make verify` and coverage >= 94%
- [x] performance/security round 7 audits
- [x] wheel/sdist/twine/installed smoke/compile checks
- [x] 1.8.0 report, checksums, archive, clean commit
