# تقرير الجولة الثامنة — AraNorm Runtime & Service Boundary

**الحالة:** مكتملة على الفرع `professional-hardening`، مع إبقاء الإصدار الرسمي عند `1.8.0` إلى حين إصدار release مستقل.  
**التاريخ:** 17 أغسطس 2026  
**المؤلف:** Manus AI

## الملخص التنفيذي

نقلت الجولة الثامنة AraNorm من مكتبة تطبيع قوية ذات عقود تشغيلية متقدمة إلى مكوّن يمكن دمجه بأمان داخل خدمات طويلة العمر، دون إعادة كتابة النواة أو تغيير السلوك الافتراضي للواجهات السابقة. بُنيت الإضافات فوق `ArabicNormalizationPipeline` و`PipelineConfig` و`ProcessorRegistry` الحالية، مع الحفاظ على التبعيات الأساسية الصفرية والتشغيل الاختياري للخدمات.

أصبحت الحزمة توفر `PipelineRuntime` لإدارة snapshots مستقرة وإعادة تحميل ذرية للإعدادات، وعقود health/readiness منقحة، وHTTP adapter مبنيًا على مكتبة Python القياسية، ومراقب إعدادات اختياريًا، وعقدًا فعليًا لاكتشاف plugins من metadata مثبتة في `dist-info/entry_points.txt`. كما أضيفت بوابة packaging مستقلة إلى CI، وتوسعت اختبارات العقود والتكامل لتثبت السلوك عبر listener مؤقت، artifacts مبنية، ومسارات فشل واقعية.

> النتيجة: **799 اختبارًا ناجحًا، 5 تخطيات اختيارية موثقة، وتغطية إجمالية 94% عبر 4,899 سطرًا مقاسًا**. اجتازت `make verify`، و`make test-cov`، وأهداف عقود runtime/server/plugins، وinstalled smoke، وبناء wheel وsdist، و`twine check`.

## نطاق التغييرات

| المجال | التنفيذ | الأثر التشغيلي |
|---|---|---|
| Runtime | `PipelineRuntime` مع `get_pipeline()` و`reload()` و`reload_from_file()` و`describe()` و`health()` | نشر snapshot كامل بصورة ذرية، وعدم هدم الحالة الصالحة عند فشل reload |
| Health | `RuntimeHealth` مع `ready` و`degraded` وgeneration وبصمة الإعداد | readiness قابل للمراقبة دون تسريب نصوص المستخدم |
| Reload | `ConfigReloadWatcher` اختياري، debounce مبني على mtime، وdaemon قابل للإيقاف | تحديث إعدادات طويل التشغيل مع rollback منطقي إلى آخر snapshot صالح |
| HTTP | `aranorm.server` باستخدام `ThreadingHTTPServer` | endpoints JSON ثابتة للتطبيع، الدفعات، health، والوصف التشغيلي دون dependency إلزامي |
| CLI | الأمر `aranorm serve` مع host/port/preset/config/body limit/reload interval | تشغيل opt-in متسق مع parser الحالي وعدم بدء listener عند import |
| Plugins | contract مبني على `dist-info/entry_points.txt`، مع success/failure/strict | إثبات اكتشاف plugins من artifact مثبت بدل الاعتماد على mocks سطحية |
| CI وMakefile | job packaging في CI، و`server-contracts` و`plugin-contracts` و`installed-smoke` | فصل بوابات التشغيل والتوزيع وجعلها قابلة للتشخيص وإعادة التنفيذ |
| التوثيق | README وAPI_REFERENCE وARCHITECTURE وINSTALLATION وCHANGELOG وROUND8_ROADMAP | توضيح الحدود الأمنية ومسار الدمج والإنتاج والترحيل |

## القرارات المعمارية

تبقى النواة مسؤولة عن التطبيع والمعالجة فقط. تقع `PipelineRuntime` في طبقة orchestration اختيارية، وتمتلك snapshot الحالي وgeneration وحالة reload، لكنها لا تكرر منطق processors ولا تخزن النص الأصلي أو الناتج. عند reload، يُبنى pipeline المرشح ويُتحقق منه قبل أخذ القفل ونشره؛ لذلك لا يرى أي طلب pipeline نصف مهيأ، وتستمر الطلبات التي التقطت snapshot سابقًا على الكائن نفسه حتى تنتهي.

يُعامل HTTP adapter كحد خدمة محدود وليس كـ gateway أمني كامل. يفرض adapter نوع JSON، وحد body افتراضيًا مقداره 2,000,000 بايت، ويعزل أخطاء payload والمسارات غير المدعومة بعقود status/error ثابتة. أما TLS termination والمصادقة والتفويض وrate limiting والتسجيل المركزي فتظل مسؤولية reverse proxy أو gateway موثوق، كما هو موثق في `ARCHITECTURE.md` و`INSTALLATION.md`.

اعتمد عقد plugins على معيار entry points المثبت في توزيعات Python؛ وهو مناسب لاكتشاف مكونات لا يعرف المستهلك تنفيذها مسبقًا، مع عزل حالات الفشل وإتاحة strict mode لبوابات النشر [1] [2]. لم يتغير `ProcessorRegistry.discover()` القديم، بل أضيفت اختبارات distribution-style فوق آلية `discover_report()` الموجودة.

## الاختبارات وبوابات الجودة

| البوابة | النتيجة |
|---|---|
| `make verify` | ناجحة: 799 passed و5 skipped |
| `make test-cov` | ناجحة: 799 passed و5 skipped، coverage = 94% |
| `make server-contracts` | 44 passed |
| `make plugin-contracts` | 3 passed |
| `make installed-smoke` | 1 passed، مع اختبار wheel وsdist خارج شجرة المصدر |
| Black | ناجح دون تغييرات |
| flake8 | ناجح |
| mypy | ناجح على `src` |
| compileall | ناجح على Python 3.12.3 المتاح في البيئة |
| `python -m build` | wheel وsdist بُنيا بنجاح |
| `python -m twine check dist/*` | PASSED للـ wheel والـ sdist |
| CLI smoke | `aranorm serve --help` يعرض كل الخيارات الجديدة دون فتح listener |

التخطيات الخمسة اختيارية ومعلنة: PyYAML، datasets، spaCy، NLTK، وscikit-learn غير مثبتة في البيئة الحالية. لا تمثل هذه التخطيات فشلًا في المسار الأساسي، وتبقى التكاملات الاختيارية خارج التبعيات الإلزامية.

## التغطية

بلغت التغطية الإجمالية **94%**، بإجمالي 4,899 سطرًا مقاسًا و295 سطرًا غير منفذ. حققت الوحدات الجديدة نتائج أعلى من الحد الأدنى: `src/aranorm/core/runtime.py` عند **99%**، و`src/aranorm/server.py` عند **97%**. تغطي suites الجديدة snapshot identity، النسخ الدفاعي، generations، reload failure، watcher lifecycle، body limits، malformed JSON، batch validation، 404، readiness degradation، serve cleanup، وinstalled entry-point metadata.

## تدقيق الأداء والأمان

شُغلت أدوات التدقيق الموجودة في `scripts/` دون تغييرها، وحُفظت النتائج الخام في `performance_round8.json` و`security_round8.json`.

| القياس | النتيجة الجولة الثامنة |
|---|---:|
| تكرار cache | 1,000 عنصر، speedup = 411.09x، hits = 999، misses = 1 |
| single-flight | 16 caller متزامن، pipeline calls = 1 بدل 16 |
| streaming | 10,000 عنصر، 311.42 نص/ثانية، peak traced memory = 7,137,826 bytes |
| regex URL عند 20,000 حرف | 1.418 ms |
| regex email عند 20,000 حرف | 1.550 ms |
| regex mention عند 20,000 حرف | 1.748 ms |
| regex hashtag عند 20,000 حرف | 1.498 ms |
| regex HTML عند 20,000 حرف | 0.783 ms |
| regex Arabizi عند 20,000 حرف | 0.461 ms |

هذه الأرقام تدقيقات محلية قابلة لإعادة التشغيل وليست benchmark رسميًا عبر بيئات عتادية مختلفة. ولذلك تُستخدم لاكتشاف الانحدار النسبي داخل المشروع، لا كضمان latency مطلق في الإنتاج.

## Packaging وCI

أعيد بناء artifacts من الحالة الحالية، وتأكد أن كليهما يحتويان `aranorm/core/runtime.py` و`aranorm/server.py`، وأن metadata الداخلية تحمل `Version: 1.8.0`:

| Artifact | الحالة |
|---|---|
| `dist/aranorm-1.8.0-py3-none-any.whl` | مبني، نحو 199 KB، metadata صحيحة |
| `dist/aranorm-1.8.0.tar.gz` | مبني، نحو 223 KB، metadata صحيحة |
| `twine check` | PASSED للملفين |
| installed smoke | يثبت كل artifact في target معزول ويستورد runtime فعليًا |

أضيفت إلى `.github/workflows/quality.yml` job مستقلة باسم `Packaging and installed smoke` على Python 3.12، تبني الحزم، تفحص metadata، وتشغل installed smoke. بقيت مصفوفة الجودة الأساسية على Python 3.9–3.13 كما هي، لذلك لا تحل بوابة packaging محل اختبارات التوافق المتعددة.

## مسار الترحيل

لا يحتاج مستخدمو `ArabicNormalizationPipeline` أو `process()` أو `process_batch()` أو CLI الحالي إلى أي تعديل. يمكن إدخال `PipelineRuntime` تدريجيًا فقط للتطبيقات طويلة العمر التي تحتاج reload أو readiness، مع إبقاء pipeline السابق صالحًا أثناء الانتقال. ويمكن تشغيل `aranorm serve` على loopback للتجارب الداخلية، أو وضعه خلف gateway موثوق في بيئة مؤسسية.

يوصى بتثبيت `reload_interval` فقط عند الحاجة، وتقييد `max_body_bytes` بما يتناسب مع سياسة الخدمة، ومراقبة `/health/ready` بدل اعتبار liveness دليلًا على جاهزية pipeline. لا ينبغي تعريض adapter مباشرة للإنترنت، لأن TLS والمصادقة وrate limiting ليست جزءًا من نطاقه.

## الملفات الرئيسية المضافة أو المحدثة

| المسار | الوظيفة |
|---|---|
| `src/aranorm/core/runtime.py` | عقود runtime، snapshots، generations، reload، health، watcher |
| `src/aranorm/server.py` | HTTP adapter والعقود JSON والحدود التشغيلية |
| `tests/test_runtime_contracts.py` | اختبارات runtime والذرية والنسخ الدفاعي |
| `tests/test_server_contracts.py` | اختبارات HTTP والتكامل وlifecycle |
| `tests/test_cli_round8.py` | عقود parser وserve CLI |
| `tests/test_plugin_installation_round8.py` | installed-plugin contract مبني على dist-info |
| `ROUND8_ROADMAP.md` | النطاق ومعايير القبول وحالة التنفيذ |
| `performance_round8.json` | نتائج تدقيق الأداء الخام |
| `security_round8.json` | نتائج تدقيق regex security الخام |

## الحالة النهائية للجولة

الجولة الثامنة **مكتملة من ناحية التنفيذ والاختبارات والتوثيق والتحقق المحلي**. لم يُرفع رقم الإصدار إلى 1.9.0 عمدًا؛ بقي `1.8.0` ثابتًا لأن هذه الجولة ما تزال في قناة Unreleased، ولأن قرار الإصدار يجب أن يُتخذ بعد مراجعة مستقلة للـ changelog وقرار التوافق. لا توجد تغييرات على النواة من الصفر، ولا تبعية إلزامية جديدة، ولا listener يبدأ ضمن import.

## References

[1]: https://packaging.python.org/specifications/entry-points/ "PyPA Entry Points Specification"
[2]: https://setuptools.pypa.io/en/latest/userguide/entry_point.html "Setuptools Entry Points Guide"
[3]: https://willigottstein.medium.com/from-good-code-to-reliable-software-a-practical-guide-to-production-ready-python-packages-aa881c2c31e9 "A Practical Guide to Production-Ready Python Packages"

> **ملاحظة:** نتائج الأداء والأمان أعلاه مأخوذة مباشرة من artifacts المحلية للجولة، ويمكن إعادة إنتاجها عبر `python3 scripts/performance_audit.py` و`python3 scripts/security_audit.py`.

[4]: ROUND8_RESEARCH_NOTES.md "ملاحظات بحث الجولة الثامنة"
[5]: ROUND8_ROADMAP.md "خارطة الجولة الثامنة ومعايير القبول"

