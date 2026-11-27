# AraNorm Round 9 Roadmap — Portable Pipeline Specifications

## الهدف

توسيع AraNorm 1.8.0 بإضافة مواصفة pipeline declarative، versioned، قابلة للتسلسل والتحقق وإعادة البناء الآمن، فوق `PipelineConfig` و`PipelineRuntime` الحاليين. لا تعيد الجولة كتابة النواة، ولا تسلسل كائنات Python تنفيذية، ولا تكسر واجهات الإصدارات السابقة.

## نطاق التنفيذ

### A. PipelineSpec contract

- إضافة `PipelineSpec` في طبقة `core` مع `schema_version` ثابت وقابل للتطور.
- حفظ `library_version` و`pipeline_class` و`config` و`config_fingerprint` وmetadata وصفية اختيارية.
- توفير `to_dict` و`from_dict` و`to_json` و`from_json` و`write_file` و`read_file`.
- رفض الحقول غير المعروفة، القيم غير القابلة للتسلسل، fingerprints غير المطابقة، وإصدارات schema غير المدعومة.
- استخدام canonical JSON مرتب المفاتيح لحساب fingerprint مستقل عن ترتيب المفاتيح.
- توفير حد أقصى دفاعي لحجم JSON عند القراءة من النص أو الملف.

### B. Integration

- إضافة `ArabicNormalizationPipeline.to_spec()` و`from_spec()` فوق config reconstruction القائم.
- إضافة `PipelineRuntime.spec()` و`reload_from_spec()` مع النشر الذري وrollback عند الفشل.
- عدم تسلسل custom processor instances أو plugin object references؛ تُرفض صراحة أو تُحفظ كبيانات وصفية غير تنفيذية فقط.

### C. CLI

- إضافة أمر `aranorm spec export` لتصدير preset/config إلى JSON.
- إضافة أمر `aranorm spec validate` للتحقق من الملف وإخراج fingerprint وschema.
- إضافة أمر `aranorm spec normalize` لمعالجة نص أو ملف باستخدام spec validated.
- الحفاظ على exit codes والمخرجات والأوامر الحالية.

### D. Quality

- اختبارات contract للـ round-trip والنسخ الدفاعي والحقول المجهولة والفشل malformed.
- اختبارات fingerprint stability وschema compatibility وsize limits وUnicode.
- اختبارات runtime atomic reload وfailure rollback من spec.
- اختبارات CLI E2E وinstalled smoke للحزمة المبنية.
- تشغيل الأداء والأمان، مع التأكد من عدم تنفيذ أي object reference من JSON.

## معايير القبول

- لا يقل إجمالي الاختبارات الناجحة عن baseline الجولة الثامنة `799` مع إضافة suite جديدة.
- التغطية الكلية لا تقل عن `94%`، وتغطية وحدة spec لا تقل عن `98%`.
- `make verify` وBlack وflake8 وmypy ناجحة.
- `make spec-contracts` و`make installed-smoke` ناجحتان.
- جميع round-trips detached ولا تعدّل مدخلاتها.
- fingerprint متطابق عند اختلاف ترتيب مفاتيح JSON، ومختلف عند اختلاف إعداد فعلي.
- spec malformed أو oversized يفشل برسالة typed دون تشغيل pipeline جزئي.
- reload الفاشل لا يغيّر generation أو pipeline المنشور.
- wheel وsdist يصدّران عقود spec وتعمل خارج شجرة المصدر.
- توثيق API وCLI وSECURITY وCHANGELOG وتقرير الجولة محدث.

## ما هو خارج النطاق

لا تشمل الجولة تدريب نماذج، GPU processing، أو خدمة HTTP جديدة، ولا تنفيذ plugin references من ملفات المواصفة، ولا رفع الإصدار إلى `1.9.0` قبل اجتياز بوابات الإصدار ومراجعة التوافق.

## مسار الترحيل

المستخدمون الحاليون لا يحتاجون إلى أي تغيير. `PipelineConfig` و`ArabicNormalizationPipeline.from_config_dict()` و`PipelineRuntime.reload_from_file()` تبقى مدعومة. `PipelineSpec` إضافة اختيارية، ويمكن اعتمادها تدريجيًا لحفظ إعدادات pipelines ونقلها بين البيئات.

## الحالة الفعلية للجولة

اكتمل التنفيذ الوظيفي والاختباري للجولة التاسعة فوق الإصدار 1.8.0. اجتازت بوابة `make verify` عدد **833 اختبارًا ناجحًا مع 5 تخطيات اختيارية**، وبلغت التغطية **94%** من 5,154 سطرًا، بينما بلغت وحدة `PipelineSpec` **99%**. وأكد قياس coverage المستقل النتيجة نفسها: **833 اختبارًا ناجحًا مع 5 تخطيات**. اجتازت اختبارات `PipelineSpec` المستهدفة 26 اختبارًا، كما اجتاز installed smoke للحزم المبنية اختبارًا واحدًا ناجحًا خارج شجرة المصدر.

اكتملت كذلك تدقيقات الأداء والأمان، وبناء wheel وsdist، وفحص `twine check`، و`compileall`، وSHA256 للحزم. تبقى قبل الإغلاق الإداري كتابة تقرير الجولة النهائي، إعادة إنشاء الأرشيف بعد آخر تعديل، ثم تسجيل commit نظيف قابل للتتبع. لا يرفع هذا المسار الإصدار إلى 1.9.0؛ الإصدار الرسمي يظل 1.8.0 حتى تُعتمد عملية release مستقلة.
