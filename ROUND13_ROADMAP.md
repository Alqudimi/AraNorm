# AraNorm Round 13 Roadmap — Analysis, Reliability & Operational Contracts

**التاريخ:** 2026-08-18  
**الإصدار الحالي:** 1.8.0  
**الفرع:** `professional-hardening`  
**المؤلف:** Manus AI

## الهدف

توسيع AraNorm فوق الجولة الثانية عشرة دون إعادة كتابة البنية القائمة، مع نقل الجودة من إغلاق فجوات المعالجات إلى **تغطية عقود التحليل والتشخيص والتكاملات الاختيارية والمسارات التشغيلية**. يجب أن تكون كل إضافة اختبارًا لسلوك يمكن للمستخدم الاعتماد عليه، لا مجرد تنفيذ اصطناعي لأسطر غير مغطاة.

## خط الأساس المثبت

| المؤشر | القيمة المثبتة |
|---|---:|
| الالتزام المرجعي | `76fbe49` على `professional-hardening` |
| الاختبارات | 966 ناجحة، 5 متخطاة اختياريًا |
| التغطية الإجمالية | 95% من 5,574 بيانًا |
| الوحدات المستهدفة في Round 12 | 8 وحدات عند 100% سطور وفروع |
| Python المعلن | `>=3.9` |
| الإصدار | `1.8.0` |
| بوابة `make verify` | ناجحة |

الاختبارات المتخطاة مرتبطة فقط بغياب تبعيات اختيارية: PyYAML وdatasets وspaCy وNLTK وscikit-learn. لا يجوز تحويلها إلى تبعيات إلزامية في هذه الجولة.

## تحليل الفجوات وترتيب الأولويات

أظهر تقرير التغطية الحالي أن أكبر قيمة هندسية لا تأتي من إعادة اختبار المعالجات التي وصلت إلى 100%، بل من حماية الحدود التي تمس دقة التحليل أو فشل التكاملات أو عقود الإدخال. رُتبت المسارات وفق أربعة عوامل: أثرها على المستخدم، احتمال حدوث الفشل في الإنتاج، حتمية الاختبار دون شبكة أو تبعيات جديدة، وقابلية التغيير المحدود.

| الأولوية | المسار | خط الأساس | الفجوات المركزية | الإجراء المقترح |
|---|---|---:|---|---|
| P0 | `processors/_base.py` | 88% | أخطاء التحقق ومسار regex العام | عقود إدخال نوعية واختبارات `TextProcessor` و`RegexProcessor` و`processor_transform` |
| P0 | `stages/dialect_id.py` | 86% | CAMeL unavailable/failure، حدود heuristic | اختبار عزل كامل عبر import/model mocks، مع حماية رسائل الاستثناء |
| P0 | `core/config.py` | 90% | أنواع حدود الموارد، preset overrides، unknown fields | اختبارات round-trip ورفض الأنواع والحدود مع عدم تغيير التهيئة جزئيًا |
| P1 | `core/stop_words_registry.py` | 94% | ملفات التصنيفات المفقودة، dialect keys، cache invalidation | اختبارات filesystem isolation، dialect fallback، `add_custom` وstats |
| P1 | `analysis/keyword_extractor.py` | 87% | `min_freq`، IDF، corpus empty، common keywords | عقود TF/IDF حتمية ونواتج مرتبة وثابتة |
| P1 | `analysis/readability.py` | 85% | empty/no-Arabic/long-word/sentence boundaries | اختبارات عددية حدية مع الحفاظ على النتائج القابلة للتفسير |
| P1 | `analysis/text_analyzer.py` و`core/metrics.py` | 95% | الحالات الفارغة والحدود والتسلسل | إغلاق فروع النتائج الصفرية وserialization/aggregation |
| P2 | `utils/stemmer.py` و`utils/language_detector.py` | 94% | نصوص قصيرة، رموز، mixed-script thresholds | اختبار invariants وحالات اللغة غير الحاسمة دون إدخال نموذج خارجي |
| P2 | `server.py` | 93% | malformed JSON، method/status errors، limits | توسيع عقود HTTP خارج streaming مع بقاء الخدمة opt-in |
| P2 | `cli.py` | 85% | مسارات validation/error في subcommands | اختبارات CLI مركزة على أعلى كثافة فقط، لا إعادة اختبار كل happy path |

## مراحل التنفيذ

### المرحلة A — Core contracts and optional integrations

نضيف ملفات اختبار مستقلة تحت `tests/test_coverage_round13_*.py` لـ`processors/_base.py` و`stages/dialect_id.py` و`core/config.py`. كل اختبار يجب أن يثبت النتيجة أو نوع الاستثناء ورسالة bounded، وأن يعزل CAMeL أو filesystem عبر mocks محلية.

### المرحلة B — Analysis correctness

نغطي `keyword_extractor.py` و`readability.py` و`text_analyzer.py` و`metrics.py` من خلال نصوص عربية قصيرة وطويلة وفارغة ومختلطة. نثبت عدم الانهيار، الترتيب الحتمي، حدود النسب، وأن النتائج لا تتسرب إليها حالة كائن سابقة.

### المرحلة C — Registry, language and stemmer reliability

نختبر `StopWordsRegistry` في حال فقدان ملف التصنيف، dialect غير معروف، cache invalidation بعد `add_custom`، واستخراج الإحصاءات. ثم نضيف حدودًا لـ`stemmer` و`language_detector` دون الاعتماد على نماذج اختيارية.

### المرحلة D — Operational contracts

بعد استقرار الوحدات، نغطي أخطاء الطلبات في server وCLI بأقل عدد من الاختبارات عالية القيمة: JSON malformed، content type/size، method غير مدعوم، وexit codes. لا يتغير boundary الأمني ولا يتم تشغيل listener أثناء import.

### المرحلة E — Verification and release evidence

نشغّل `make verify`، `make test-cov`، audits الأداء والأمان، `make installed-smoke`، `compileall`، وبناء wheel/sdist و`twine check`. ثم نحدّث CHANGELOG والتقرير النهائي وننشئ أرشيفًا مؤسسيًا مستقلًا للجولة.

## معايير القبول

| المعيار | الحد الأدنى |
|---|---|
| عدم كسر السلوك القائم | جميع الاختبارات الحالية ناجحة، ولا تغيير غير مبرر في API أو spec format |
| الاختبارات الجديدة | ملف اختبار مستقل لكل مسار رئيسي، مع عقود سلوكية لا اختبارات شكلية |
| التغطية | عدم الانخفاض عن 95% إجمالًا، ورفع P0 إلى 100% أو توثيق سبب غير قابل للوصول |
| الجودة الساكنة | Black وflake8 وmypy بلا أخطاء |
| الاعتمادية | لا network tests ولا تبعيات إلزامية جديدة |
| الأداء | عدم انخفاض بوابة benchmark الحالية (>=500 نص/ث للـlight preset) |
| الأمان | اجتياز security audit وعدم توسيع surface غير opt-in |
| التوزيع | wheel/sdist صالحان و`twine check` ناجح وSHA-256 موثق |
| التوثيق | تقرير نهائي يذكر ما تغير، الأدلة، المتبقي، وحدود القياس |

## Non-goals

لا تشمل الجولة إعادة كتابة pipeline engine، أو تغيير صيغة `PipelineSpec`، أو إدخال نموذج لهجات إلزامي، أو بناء واجهة شبكة جديدة، أو رفع الإصدار الرسمي دون قرار إصدار مستقل. كما لا تُقاس جودة اللغة العربية بادعاءات غير مدعومة ببيانات مرجعية؛ التركيز هنا على العقود الحتمية والموثوقية الهندسية.

## المخاطر وضوابطها

| الخطر | الضابط |
|---|---|
| اختلاف سلوك الاختبارات بسبب optional dependencies | mocks محلية واختبارات skip موثقة؛ لا import فعلي مطلوب |
| تضخم الجولة بسبب CLI/server | تطبيق بوابة P0/P1 أولًا، ثم P2 إذا بقيت البوابات مستقرة |
| اختبار فروع لا يمكن الوصول إليها | توثيق الفرع كغير قابل للوصول بدل تعديل الإنتاج اصطناعيًا |
| تسرب حالة cache بين الاختبارات | fixtures مستقلة ومسح caches بعد الاختبارات التي تغيّر registry |
| خفض الأداء بسبب أدوات التحقق | benchmark قبل/بعد وتسجيل المتوسط والحد الأدنى |

## قرار الجولة

النطاق المعتمد هو **Round 13 — Analysis, Reliability & Operational Contracts**. يبدأ التنفيذ بـP0، ثم ينتقل إلى P1، ولا يُسمح بإضافة ميزة عامة جديدة قبل استقرار العقود والبوابات. أي إصلاح إنتاجي يجب أن يكون أصغر تغيير ممكن، ومثبتًا باختبار فاشل قبل الإصلاح ثم ناجح بعده.

> مبدأ الجولة: لا نزيد السطح قبل أن نرفع الثقة في السطح الموجود.

## مراجع داخلية

- `ROUND12_RELEASE_REPORT.md`
- `ROUND12_GAP_ANALYSIS.md`
- `ROUND12_EXECUTION_NOTES.md`
- `TESTING.md`
- `RELEASE_PROCESS.md`
- `SECURITY.md`
- `Makefile`
