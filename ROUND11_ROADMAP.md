# AraNorm Round 11 Roadmap

## Goal

تقوية حدود التشغيل المحلية في AraNorm، وخصوصًا `StreamingSession` وendpoint `/v1/stream`، عبر تحسين الاتساق، منع التشغيل المتوازي غير الآمن، تشديد حدود المسارات، وتوسيع الاختبارات والتوثيق دون إعادة كتابة محرك التطبيع أو إضافة تبعيات إلزامية.

## Baseline

بدأ العمل من الفرع `professional-hardening` بعد الجولة العاشرة الخضراء. خط الأساس الموثق هو `849 passed، 5 skipped` مع تغطية إجمالية قدرها `94%`، ونجاح `make verify` و`make installed-smoke`. انتهت الجولة عند `878 passed، 5 skipped` مع تغطية إجمالية قدرها `94%` وتغطية `streaming.py` قدرها `100%`، دون تراجع في بوابات الجودة.

## Design principles

| المبدأ | التطبيق |
|---|---|
| البناء فوق القائم | الحفاظ على `ArabicNormalizationPipeline` و`PipelineRuntime` و`PipelineSpec` ومسارات CLI/HTTP الحالية |
| مصدر تطبيع واحد | استمرار اعتماد streaming على `process_iter` وعدم نسخ منطق التطبيع |
| توافق خلفي | إبقاء الخيارات الحالية وقيمها الافتراضية، وتعطيل HTTP streaming افتراضيًا |
| فشل آمن | رفض checkpoint أو المسار أو التشغيل المتوازي غير الآمن برسائل typed دون إنتاج duplicate output |
| تبعيات صفرية | الاعتماد على المكتبة القياسية فقط، مع جعل قفل Unix اختياريًا وواضح الحدود |
| قابلية القياس | تقارير status machine-readable واختبارات فشل حتمية وأدلة أداء قابلة للمقارنة |

## Workstreams

### 1. Durable session guard

إضافة قفل محلي اختياري ومحدد النطاق لجلسة source/output/checkpoint، مع abstraction صغيرة لا تسرّب تفاصيل `fcntl` إلى API العام. يجب أن يرفض التشغيل المتوازي برسالة typed واضحة، وأن يحرر القفل في حالات النجاح والفشل والإلغاء. لا يُدّعى أن القفل موزع أو يعمل خارج حدود نظام الملفات المحلي.

### 2. Source and output integrity

توسيع metadata الداخلية أو التحقق التشغيلي لاكتشاف تغير المصدر بعد fingerprint الأول، والتحقق من أن offset المحفوظ يظل ضمن حدود output مع التمييز بين checkpoint malformed وsession conflict. يجب ألا يغير ذلك شكل checkpoint v1 إلا عند الحاجة؛ وإذا احتاج schema إلى تعديل فسيكون إصدارًا صريحًا مع migration أو رفض آمن، لا تغييرًا صامتًا.

### 3. Shared JSONL serialization

توحيد serialization مع contract `StreamingBatchExporter` أو helper داخلي مشترك، مع الحفاظ على JSONL UTF-8 وnewline لكل record. لا يُسمح بإعادة كتابة exporter أو تغيير شكل `NormalizationResult.to_dict()`.

### 4. HTTP path safety

إضافة `streaming_root` اختياري إلى `create_server` و`serve`. عند تفعيله، يجب أن تكون source/output/checkpoint داخل الجذر بعد `resolve()`، مع رفض traversal والروابط الرمزية الخارجة من الجذر وفق سياسة موثقة. يبقى endpoint معطلًا افتراضيًا، ولا تُضاف مصادقة بديلة إلى خادم المكتبة القياسي.

### 5. CLI and status diagnostics

توسيع `stream status` و`serve` فقط عند الحاجة لعرض سياسة القفل والجذر والحدود، مع إبقاء المخرجات الحالية متوافقة. أي حقل جديد سيكون additive وقابلًا للقراءة الآلية.

### 6. Test matrix

إضافة اختبارات unit/integration تغطي: lock acquisition/release، conflict، cleanup on exception، source mutation، symlink/traversal policy، malformed and oversized checkpoints، output offset boundaries، empty input، skipped results، CLI/HTTP compatibility، Python 3.9 behavior، وfailure injection للكتابة الذرية.

### 7. Quality and delivery

تشغيل `make verify` و`make test-cov` و`make streaming-contracts`، وإنتاج benchmark/security artifacts، وبناء wheel وsdist وفحصهما، وتحديث README وAPI_REFERENCE وARCHITECTURE وCONFIGURATION وCHANGELOG، ثم كتابة `ROUND11_RELEASE_REPORT.md` وإنشاء أرشيف Enterprise بعد commit نظيف.

## Acceptance criteria

- [x] كل اختبارات baseline والجولة الجديدة ناجحة، ولا توجد regression في CLI أو server أو runtime.
- [x] `StreamingSession` لا يسمح بكتابين متزامنين على نفس tuple عندما تكون الحماية مفعلة، ويحرر القفل دائمًا.
- [x] تغير المصدر أو عدم تطابق output/checkpoint يؤدي إلى فشل typed واضح قبل استئناف قد ينتج duplicate data.
- [x] endpoint `/v1/stream` يظل opt-in، ويرفض المسارات الخارجة عن `streaming_root` عند ضبطه.
- [x] JSONL الناتج يبقى UTF-8، record-per-line، وقابلًا للقراءة بالأدوات الحالية.
- [x] التغطية الإجمالية لا تقل عن خط الأساس المعلن، وتوثق التقارير أي حدود منصة أو قياس.
- [x] لا تبعية خارجية إلزامية ولا تعديل جوهري لمحرك التطبيع الداخلي.

## Evidence

| البوابة | النتيجة |
|---|---|
| `make verify` | 878 passed، 5 skipped |
| `make test-cov` | 94% إجماليًا، و100% لـ`src/aranorm/core/streaming.py` |
| `make streaming-contracts` | 19 passed |
| `make installed-smoke` | 1 passed |
| `twine check` و`compileall` | ناجحان |
| الأداء والأمان | `performance_round11.json` و`security_round11.json` |

توثق ملفات التقرير والأدلة حدود الاختبارات الاختيارية التي بقيت skipped لغياب PyYAML وdatasets وspaCy وNLTK وscikit-learn.

## Non-goals

لا تتضمن الجولة قاعدة بيانات، queue موزعة، object storage، distributed lock، exactly-once عبر عمليات متعددة، تغيير الإصدار الرسمي، أو إعادة تصميم pipeline.py.

## References

لأساسيات atomic replacement وقيود القفل وJSON Lines، راجع [ROUND11_RESEARCH_NOTES.md](ROUND11_RESEARCH_NOTES.md).
