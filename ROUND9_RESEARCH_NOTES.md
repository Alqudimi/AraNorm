# Round 9 Research Notes

## هدف المراجعة

تستهدف الجولة التاسعة إضافة عقد **PipelineSpec** قابلًا للتسلسل والتحقق وإعادة البناء فوق `PipelineConfig` و`PipelineRuntime` القائمين، دون إدخال آلية تحميل تنفيذية غير آمنة أو كسر التوافق الرجعي.

## المراجع الخارجية والقرارات

### 1. PyPA Entry Points Specification

تعرّف مواصفة PyPA نقاط الدخول على أنها metadata تعلن بها الحزمة المثبتة مكونات يمكن اكتشافها واستخدامها، وتحدد group وname وobject reference كخصائص أساسية.[1] كما تنص المواصفة على أن metadata تُسجل في `entry_points.txt` داخل `*.dist-info`، وهو ما ينسجم مع contract الجولة الثامنة الذي يختبر `ProcessorRegistry` عبر distribution metadata فعلية.

**قرار التصميم:** لا يكرر `PipelineSpec` تحميل plugins أو تنفيذ object references. سيحفظ فقط configuration declarative، ويترك discovery والتحميل لـ`ProcessorRegistry` القائم، حتى يبقى ملف المواصفة آمنًا وقابلًا للمراجعة.

### 2. `importlib.metadata`

توثق Python أن `importlib.metadata` تقرأ metadata الخاصة بالتوزيعات المثبتة، بما فيها entry points، وأن entry points تُنتقى بواسطة `group` و`name` وتُحل عبر `load()`.[2]

**قرار التصميم:** يظل `PipelineSpec` محايدًا عن runtime environment؛ لا يُضمن فيه إصدار توزيعة plugin أو كائن Python قابل للاستدعاء. عند الحاجة إلى توسعة لاحقة، يمكن إضافة قسم metadata وصفي strict دون تحويل JSON إلى تعليمات تنفيذ.

### 3. Python `json`

توثق Python أن JSON صيغة تبادل خفيفة، وأن `json.dumps(..., sort_keys=True)` مناسب للإخراج الحتمي، مع تحذير من استهلاك CPU والذاكرة عند تحليل JSON غير موثوق وضرورة وضع حدود لحجم البيانات.[3]

**قرار التصميم:** يطبق `PipelineSpec` parsing محدودًا على مستوى النص والحقول، ويرفض الحقول غير المعروفة، ويستخدم canonical JSON مرتّب المفاتيح لحساب fingerprint، ولا يستخدم `pickle` أو أي deserialization تنفيذي.

## نطاق الجولة التاسعة

1. إضافة `PipelineSpec` versioned schema مع `to_dict` و`from_dict` و`to_json` و`from_json` وقراءة/كتابة ملف UTF-8.
2. ربط المواصفة بـ`ArabicNormalizationPipeline` و`PipelineRuntime` عبر factories آمنة تعتمد على `PipelineConfig` فقط.
3. إضافة CLI للتحقق والتصدير والاستيراد التشغيلي دون تغيير أوامر normalize وbatch وserve.
4. إضافة اختبارات strict schema، round-trip، fingerprint stability، malformed input، size limits، compatibility، runtime snapshot، installed smoke.
5. توثيق الحدود: custom processor instances لا تُسلسل تلقائيًا، وplugin object references لا تُنفذ من ملفات المواصفات.

## المراجع

[1]: https://packaging.python.org/specifications/entry-points/ "PyPA Entry Points Specification"
[2]: https://docs.python.org/3/library/importlib.metadata.html "Python importlib.metadata documentation"
[3]: https://docs.python.org/3/library/json.html "Python json documentation"
