# خارطة الجولة السادسة — AraNorm 1.7.0

## 1. الهدف التنفيذي

تهدف الجولة السادسة إلى رفع AraNorm من مكتبة جاهزة للتشغيل المؤسسي إلى مكتبة بمستوى **جودة هندسية مؤسسية كاملة**. ستُبنى جميع التغييرات فوق `src/aranorm` الحالي (بعد v1.6.0)، مع الحفاظ على واجهات v1.6.0 وعدم إعادة كتابة pipeline أو استبدال المعالجات القائمة أو تغيير semantics التطبيع.

المبدأ الحاكم: كل توسعة عامة يجب أن تكون **typed، موثقة، قابلة للاختبار، قابلة للتراجع، ولا تضيف تبعية أساسية جديدة**. لن تُضاف خدمة HTTP أو نماذج ثقيلة أو تغييرات في semantics التطبيع ضمن هذه الجولة.

## 2. خط أساس v1.6.0

| المؤشر | الحالة الحالية |
|---|---:|
| الإصدار | 1.6.0 |
| الاختبارات | 660 ناجحًا، 5 تخطيات اختيارية موثقة |
| التغطية | 92% |
| التحقق | `make verify` ناجح |
| التوزيع | wheel وsdist مع twine check وتثبيت معزول |

## 3. فجوات الجولة السادسة (مستخلصة من آخر تقارير التغطية والتدقيق)

### 3.1 فجوات تغطية مركزة

تُظهر آخر تقرير تغطية وحدات ذات فجوات حقيقية لا تزال مؤثرة: `domain_stop_processor` (40%)، `phrase_stop_processor` (84%)، `phone_processor` (82%)، `language_detector` (94%)، `cache.py` (82%)، `text_stats.py` (92%)، `chunker.py` (86%)، `stop_words_stage.py` (88%)، `dialect_id.py` (86%)، و`stemmer.py` (94%)، و`normalizer_utils.py` (90%).

### 3.2 عدم اكتمال عقدها المتقدمة في المعالجات

توجد معالجات إنتاجية بدون اختبارات property-based أو اختبار عدائي منظم (هجمات regex catastrophic backtracking، مدخلات Unicode حدودية، أوزان عريضة). كما لا يملك `NormalizerUtils` عقده الكامل اختبارات موحدة.

### 3.3 فجوة tracing في المسار السريع

`ProcessorContext.record()` يسجل خطوات المعالجة، لكن لا توجد آلية لربط سلسلة خطوات المعالجة بنتيجة نهائية قابلة للتدقيق (normalized steps trace). سيُضاف `steps_trace` اختياري ضمن `NormalizationResult` دون تغيير equality القديمة.

### 3.4 فجوة إعادة معالجة الدفعة الفاشلة

`BatchProcessingPolicy.collect` يجمع الاستثناءات في التقرير، لكن لا توجد آلية معيارية لإعادة محاولة العناصر الفاشلة بحدود معلنة. سيُضاف `process_batch_retry()` اختياري فوق `process_batch`.

### 3.5 فجوة property-based testing

اختباراتنا حتمية بالكامل، وهذا ممتاز، لكن فئات المدخلات الحدية (Unicode surrogate pairs، combining marks، RTL isolates، mixed scripts) يمكن تغطيتها بأوسع بعشوائية محدودة seed (من stdlib فقط، بدون تبعية).

### 3.6 فجوة عقدها dialect mappings

`dialect_mappings.json` و`arabizi_mappings.json` و`stopwords_categorized.json` بلا تحقق هيكلي آلي في CI سوى اختبارات runtime متفرقة. سيُضاف validator بنيوي للملفات JSON مع اختبارات حتمية.

### 3.7 فجوة عقدها CLI batch large-scale

CLI لم يُختبر ضد ملفات كبيرة (streaming عبر ملف) وعبر stdin، مع خيارات `--stream` و`--batch-size` في الإنتاج الفعلي.

## 4. مسارات التنفيذ ومعايير القبول

| المسار | العمل التزايدي | معيار القبول |
|---|---|---|
| A — Coverage gaps | اختبارات مركزة لكل وحدة تحت 95% | رفع التغطية إلى >=94% |
| B — Processor hardening | اختبارات عدائية للمعالجات النصية و`NormalizerUtils` | عدم انحدار regex، سلوك حدودي موثق |
| C — Steps trace | `steps_trace` اختياري ضمن `NormalizationResult` | قيمة ثابتة، لا تؤثر على equality القديمة |
| D — Batch retry | `process_batch_retry()` فوق `process_batch` | حدود معلنة، سياسة failure موثقة |
| E — Property tests | ملفات property-based بـ seed محدد | حتمية، stdlib فقط |
| F — Data validation | validator هيكلي لـ JSON data files | فحص تلقائي في verify |
| G — CLI E2E batch | اختبارات ملفات كبيرة وstdin | نجاح مع خيارات streaming |
| H — Release | تدقيق وbuild وinstall وreport وarchive | `make verify` وartifacts وchecksums |

## 5. قواعد عدم الانحدار

تبقى نتائج `process()` و`process_batch()` و`process_iter()` و`process_batch_async()` ثابتة للمدخلات نفسها. تبقى التبعيات الاختيارية خارج التثبيت الأساسي. لا تسجل النصوص الأصلية أو normalized text في telemetry. أي خطوة trace جديدة تكون opt-in عبر flag صريح. لا تُخفى أخطاء callbacks أو plugins. لا إلغاء threads قسرًا.

## 6. معايير الخروج

لا يعتبر v1.7.0 جاهزًا إلا عند: نجاح baseline وجميع الاختبارات الجديدة، تغطية >=94% أو تفسير موثق، نجاح Black وflake8 وmypy وcompileall، تحقق round-trip للحزم والتقارير، نجاح wheel وsdist و`twine check` والتثبيت المعزول، تطابق الوثائق مع الواجهات الفعلية، CHANGELOG وتقرير إصدار وchecksums وأرشيف نظيف وcommit مستقل.

## 7. خارج النطاق

REST API، Docker، GPU batching، diacritization، spell-checker، NER، وتكاملات السجلات الخارجية تبقى مؤجلة.
