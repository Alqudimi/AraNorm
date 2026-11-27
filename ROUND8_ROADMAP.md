# خارطة الجولة الثامنة — AraNorm 1.9.0

**Baseline:** AraNorm 1.8.0  
**Branch:** `professional-hardening`  
**Author:** Manus AI  
**Date:** 16 أغسطس 2026

## 1. الهدف

نقل AraNorm من مكتبة قوية لمعالجة النصوص إلى مكوّن يمكن تشغيله بأمان داخل خدمات طويلة العمر، مع إضافة واجهة HTTP اختيارية من المكتبة القياسية، وإدارة إعدادات قابلة لإعادة التحميل الذري، وفحوص readiness/health قابلة للمراقبة، وتكامل plugins مثبت فعليًا عبر entry points. ستُنفذ الجولة فوق `ArabicNormalizationPipeline` و`PipelineConfig` و`ProcessorRegistry` الحالية، دون إعادة كتابة أي مكوّن قائم أو تغيير السلوك الافتراضي للأوامر الحالية.

## 2. baseline المثبت

| المعيار | الحالة |
|---|---|
| الإصدار | 1.8.0 |
| الاختبارات | 752 ناجحًا، 5 تخطيات اختيارية موثقة |
| التغطية | 94% من 4,599 سطرًا |
| الجودة | Black وflake8 وmypy و`make verify` ناجحة |
| التبعيات الأساسية | صفر؛ التنفيذ الجديد يعتمد على Python standard library |
| plugins | `ProcessorRegistry.discover_report()` موجود، لكن لا يوجد installed-plugin fixture أو contract موحد لواجهة runtime |
| HTTP server | غير موجود |
| config reload | `PipelineConfig.from_file()` موجود، لكن لا توجد إدارة snapshot/reload ذرية أو readiness state |

## 3. نطاق التنفيذ

### المسار A — Runtime manager

إضافة مكوّن داخلي صغير مثل `PipelineRuntime` يدير snapshotًا قابلًا للقراءة من عدة threads، ويعرض `get_pipeline()` و`reload(config)` و`reload_from_file(path)` و`describe()` و`health()`. يجب أن تكون عملية reload ذرية: إما أن يصبح config/pipeline الجديدان متاحين بالكامل، أو يبقى snapshot السابق دون تغيير. لا يجوز أن يرى الطلب pipeline نصف مهيأ.

يجب أن تكون أخطاء reload غير هادمة؛ تعاد نتيجة typed تتضمن النجاح، الإصدار المتزايد للـ generation، وسبب الفشل المنظف دون تسريب النصوص. يبقى التشغيل الافتراضي ثابتًا عند فشل reload، مع إمكانية جعل الفشل fatal في طبقة الخدمة.

### المسار B — Health and readiness contract

إضافة typed result قابل للتسلسل يفرق بين `liveness` و`readiness`: liveness يثبت أن runtime حي، readiness يثبت أن pipeline صالح ومهيأ، وdegraded يصف آخر فشل reload مع بقاء snapshot صالح. يجب ألا تتضمن المخرجات أي نص إدخال أو ناتج تطبيع.

### المسار C — Standard-library HTTP service

إضافة وحدة `aranorm.server` وأمر CLI اختياري `aranorm serve` باستخدام `http.server.ThreadingHTTPServer`. العقود الأولى ستكون:

| المسار | الطريقة | الغرض |
|---|---|---|
| `/health/live` | GET | liveness سريع |
| `/health/ready` | GET | readiness مع status 200 أو 503 |
| `/v1/normalize` | POST | تطبيع نص واحد وإعادة `NormalizationResult.to_dict()` |
| `/v1/batch` | POST | معالجة دفعة محدودة عبر عقد JSON واضح |
| `/v1/describe` | GET | metadata تشغيلية منزوعة الحساسية |

يجب فرض `Content-Type: application/json`، ورفض JSON غير الصحيح، وتطبيق حدود `ResourceLimits` قبل المعالجة، واستخدام status codes ثابتة، وتعطيل تفاصيل الاستثناءات في response مع تسجيل error type آمن فقط. لا يُضاف dependency إلزامي.

### المسار D — Atomic config reload

يتيح `aranorm serve --config path.json --reload-interval N` مراقبة mtime اختياريًا، مع debounce بسيط وعدم إعادة تحميل الملف إذا لم يتغير. يبقى endpoint reload خارج النطاق الأول لتقليل سطح الهجوم؛ reload file watcher سيكون اختياريًا ومغلقًا افتراضيًا. تُختبر القراءة المتزامنة أثناء reload، وفشل الملف، والعودة إلى آخر snapshot صالح.

### المسار E — Installed plugin contract

توسيع `ProcessorRegistry` فوق `discover_report()` الحالية لإضافة contract موثق لاسم group، مع اختبار entry point فعلي داخل distribution مؤقتة أو metadata mock مطابق لـ PyPA. يظل legacy `discover()` كما هو، وتبقى failures معزولة، ويُمنع تسجيل plugin غير subclass لـ `Processor`.

### المسار F — CLI and release quality

إضافة اختبارات E2E لـ `serve` عبر خادم مؤقت، واختبارات malformed JSON وoversized inputs وreadiness degradation، وتحديث Makefile ليشمل server contract وartifact smoke. تُحدّث API_REFERENCE وARCHITECTURE وREADME وINSTALLATION وROADMAP وCHANGELOG، مع تقرير إصدار مستقل.

## 4. قرارات عدم الانحدار

تبقى جميع أوامر CLI الحالية وعقودها دون تغيير. تبقى التبعيات الأساسية صفرًا. لا تُخزّن النصوص الأصلية أو النصوص الناتجة في health أو metrics أو reload reports. لا يوقف reload طلبًا جاريًا ولا يستبدل pipeline جزئيًا. لا يُفعل HTTP server عند import. تبقى `PipelineConfig` و`ArabicNormalizationPipeline` و`ProcessorRegistry.discover()` متوافقة مع الاستخدامات الحالية.

## 5. معايير القبول

| المعيار | الهدف |
|---|---|
| Runtime snapshot | قراءة thread-safe وreload ذري مع فشل غير هادم |
| Health contract | JSON typed لـ liveness/readiness/degraded دون تسريب نصوص |
| HTTP server | normalize/batch/health/describe مع status codes وحماية الحدود |
| Config reload | reload يدوي/مراقبة mtime اختيارية، rollback إلى snapshot صالح |
| Plugins | installed entry-point contract واختبارات success/failure/duplicate/strict |
| الاختبارات | جميع الاختبارات الحالية ناجحة مع مجموعة عقود جديدة لا تقل عن 35 حالة |
| التغطية | لا تقل عن 94%، ويفضل رفع الوحدات الجديدة إلى 95%+ |
| الجودة | Black وflake8 وmypy و`make verify` ناجحة |
| CI | مصفوفة Python 3.9–3.13 مستمرة، مع job packaging على Python 3.12 لبناء الحزم وفحص metadata وinstalled smoke |
| الحزم | wheel وsdist، installed smoke، twine check، compileall |
| التوثيق | API وarchitecture وCLI وinstallation وsecurity وrelease notes محدثة |

## 6. ما هو خارج النطاق

يبقى TLS termination، authentication/authorization، rate limiting الموزع، metrics backend خارجي، Docker/GPU، وFastAPI خارج التنفيذ الأساسي. سيُوثق أن خادم standard library نقطة تشغيل محلية أو خلف reverse proxy موثوق، وليس بديلًا عن gateway إنتاجي كامل.

## 7. ترتيب التنفيذ

يبدأ التنفيذ بالعقود typed وruntime manager، ثم health، ثم server handlers، ثم config reload، ثم installed-plugin tests، وبعدها CLI والتوثيق وبوابات الجودة. لا تُقبل إضافة endpoint قبل وجود اختبار malformed input وحدود الحجم ومسار الفشل.

## 8. حالة التنفيذ الحالية

| المجال | النتيجة الفعلية |
|---|---|
| Runtime وhealth | مكتملان عبر `PipelineRuntime` و`RuntimeHealth` و`ReloadResult` مع snapshot ذري وgeneration وrollback غير هادم |
| HTTP adapter | مكتمل عبر `ThreadingHTTPServer` ومسارات live/ready/normalize/batch/describe مع envelopes وbody limits |
| Config watcher | مكتمل اختياريًا، مع فشل غير هادم وإيقاف daemon آمن |
| CLI | أمر `serve` مكتمل مع preset/config وbody limit وreload interval |
| Installed plugins | contract فعلي مبني على `dist-info/entry_points.txt` يغطي success وfailure وstrict |
| الاختبارات | `799 passed, 5 skipped`؛ أضيفت 35 حالة جديدة على baseline الجولة |
| التغطية | `94%`؛ المصدر الجديد: runtime `99%` وserver `97%` |
| الجودة | Black وflake8 وmypy و`make verify` ناجحة، و`make test-cov` يثبت `799 passed, 5 skipped` و`94%` |
| CI | أضيفت job packaging على Python 3.12 لبناء wheel وsdist و`twine check` وتشغيل installed smoke، مع بقاء مصفوفة 3.9–3.13 |
| التدقيقات | `performance_round8.json` و`security_round8.json` محفوظان وصالحا JSON |
| التوثيق | README وAPI_REFERENCE وARCHITECTURE وINSTALLATION وCHANGELOG محدثة |

تُعد الجولة جاهزة لمرحلة التحقق النهائي وبناء artifacts بعد تثبيت أي تغييرات توثيقية متبقية، مع إبقاء إصدار الحزمة الرسمي عند `1.8.0` إلى حين قرار release مستقل للجولة الثامنة.

## 9. مراجع التصميم

[1]: ROUND8_RESEARCH_NOTES.md "نتائج البحث الخارجي للجولة الثامنة"
[2]: https://packaging.python.org/specifications/entry-points/ "PyPA Entry Points Specification"
[3]: https://setuptools.pypa.io/en/latest/userguide/entry_point.html "Setuptools Entry Points Guide"
