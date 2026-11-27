# AraNorm Round 12 Roadmap — Coverage and Contract Hardening

## Goal

رفع درجة التحقق السلوكي في AraNorm عبر إغلاق الفجوات الحتمية في التغطية التي حددها تحليل `ROUND12_GAP_ANALYSIS.md`، دون تغيير منطق الإنتاج أو إضافة تبعيات إلزامية. الجولة تركّز على التأكد من أن كل فرع مهم في الوحدات الأساسية يعمل فعلًا كما يُفترض، لا مجرد اجتياز خط التغطية.

## Baseline

تبدأ الجولة من commit `76fbe49` على الفرع `professional-hardening`: `878 passed، 5 skipped`، تغطية إجمالية `94%` من 5,574 بيانًا، و`make verify` أخضر. التوثيق المبدئي في `ROUND12_GAP_ANALYSIS.md`.

## Design principles

| المبدأ | التطبيق |
|---|---|
| اختبارات فوق الكود القائم | لا يُعدَّل منطق الإنتاج إلا عند اكتشاف خلل فعلي مثبت باختبار، وبأقل تغيير ممكن |
| حتمية كاملة | لا اختبارات تعتمد على توقيت أو بيئة خارجية؛ الاستثناءات الاختيارية (CAMeL وغيرها) تُحقن عبر mocks |
| سلوك لا شكل | كل اختبار يتحقق من عقد السلوك (النتيجة، الاستثناء، الرسالة) وليس من مسار التنفيذ |
| ملف لكل حزمة وحدات | اختبارات موزعة حسب الوحدة تحت التسمية `tests/test_coverage_round12_*.py` |
| عدم التراجع | لا يجوز انخفاض إجمالي التغطية أو عدد الاختبارات الناجحة |

## Workstreams

### 1. ProcessorContext and base contracts

اختبارات للعقد الكامل في `src/aranorm/core/base.py`: `record_always` مع trace مفعل ومعطل، `set`/`get` مع default، `merge` في الحالات الأربع (trace on/off لكل طرف)، ومسارات التحقق في `Processor` الأساسي. استهداف رفع `core/base.py` من 74% إلى 100% وسلوك كامل موثق.

### 2. Registry and factory contracts

اختبارات `ProcessorRegistry` لمسات القيم الفارغة وأنواع غير صالحة، و`get` مع أسماء غير مسجلة ورسالتها، و`ProcessorFactory` مع kwargs وiteration وcontains. استهداف رفع `core/registry.py` إلى 100%.

### 3. Config typed contracts

اختبارات `PipelineConfig` لمسارات preset (LIGHT مقابل غير STANDARD)، وأنواع `resource_limits` غير الصالحة، و`from_dict` مع حقول غير معروفة وقيم trace غير bool. استهداف رفع `core/config.py` إلى 100%.

### 4. Dialect stage boundary paths

اختبار مسار heuristics بالكامل، ومسار CAMeL غير المثبت عبر تعطيل الاستيراد، ومسار فشل التنبؤ عبر mock يرفع استثناء. استهداف رفع `stages/dialect_id.py` إلى 100% دون كسر العقد القائم.

### 5. Analysis module boundaries

اختبارات حالة الحد لـreadability وkeyword_extractor وtext_analyzer وmetrics: نص فارغ، نص كامل stopwords، كلمة واحدة طويلة جدًا، أرقام درجات على الحدود، وسلوك `corpus_analyzer`/`summarizer`/`sentiment_analyzer` عند `text_comparator` بحالات فارغة.

### 6. CLI and server branch density

إضافة اختبارات للفروع الأعلى كثافة في cli.py (مسارات الأخطاء غير المختبرة) وserver.py (رسائل الخطأ للطلبات المشوهة خارج نطاق streaming). القياس هنا كمي (رفع النسبة) وليس شموليًا كاملًا.

## Acceptance criteria

- [ ] لا ينخفض إجمالي التغطية عن خط الأساس 94%، ويُغلق كل وحدات المرحلة 1-4 إلى 100% فعليًا.
- [ ] جميع الاختبارات الجديدة حتمية وتمر دون mocks هشة خارج الاستثناءات الاختيارية الموثقة.
- [ ] `make verify` و`make test-cov` و`make streaming-contracts` و`make installed-smoke` خضراء.
- [ ] أسطر الإنتاج لم تتغير إلا بإصلاح خلل فعلي مثبت باختبار، وكل إصلاح في ملف مستقل عن ملف الاختبار.
- [ ] توثيق القرارات في خارطة الجولة وتقرير الإصدار.

## Non-goals

لا تغيير للإصدار الرسمي، لا إعادة تصميم pipeline.py، لا تبعيات إلزامية، لا تغطية network أو distributed features، ولا ادعاء تغطية 100% كاملة لكل وحدة فرعية إذا كان فرعها غير قابل للإغلاق حتميًا (يُوثق السبب).
