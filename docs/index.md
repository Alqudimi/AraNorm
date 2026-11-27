# AraNorm Documentation — التوثيق

**AraNorm** — Production-grade Arabic text normalization for MSA, dialects, Arabizi, and social media.
**أرَنورم** — مكتبة احترافية لتطبيع النصوص العربية: الفصحى، اللهجات، العربيزي، ووسائل التواصل.

Version 1.15.0 · Python 3.9 – 3.13 · MIT License

---

## أين أبدأ؟ | Where do I start?

| أنت... | You are... | ابدأ هنا | Start here |
|---|---|---|---|
| مستخدم جديد أريد التجربة سريعاً | New — want results in 5 minutes | **[Getting Started](getting-started.md)** | Installation + first pipeline |
| أعرف ما أريد، أحتاج الإعدادات | Know the goal, need the knobs | **[Configuration](configuration.md)** | Every `PipelineConfig` field |
| أريد فهم المعالجات كلها | Want every processor explained | **[Processors](processors.md)** | All 48 processors |
| أعمل على الكلمات الوقفية | Working with stop words | **[Stop Words](stopwords.md)** | Modes, scopes, dialects |
| أحلل نصوصاً | Analyzing text | **[Analysis Toolkit](analysis.md)** | 45+ analyzers |
| أفضل سطر الأوامر | Prefer the terminal | **[CLI Reference](cli.md)** | All 48 commands |
| أعالج مليون مستند | Processing a million docs | **[Streaming](streaming.md)** | Resumable sessions |
| أنشر خدمة | Deploying a service | **[Deployment](deployment.md)** | HTTP server + hot reload |
| أدمج مع أدواتي | Integrating with my stack | **[Integrations](integrations.md)** | pandas/sklearn/spaCy/NLP/HF |
| أبحث عن دالة معينة | Looking for a specific symbol | **[API Reference](api.md)** | Complete API surface |

---

## الدليل الكامل | Full guide list

### البدء | Getting started

- **[Getting Started](getting-started.md)** — التثبيت، أول pipeline، المفاهيم الأساسية، أمثلة عملية كاملة / Installation, first pipeline, core concepts, complete walkthroughs
- **[Configuration](configuration.md)** — كل خيار في `PipelineConfig` و `ResourceLimits` موثقاً بالأمثلة / Every option in `PipelineConfig` and `ResourceLimits` with examples
- **[Processors](processors.md)** — المعالجات الـ 48: التنظيف، التطبيع الإملائي، المنصات، الكلمات الوقفية / All 48 processors: cleaning, orthography, platforms, stop words
- **[Stop Words](stopwords.md)** — محرك الكلمات الوقفية: الأوضاع الأربعة، النطاقات، 8 لهجات، المجالات، السياق / The stop-word engine: 4 modes, scopes, 8 dialects, domains, context

### الاستخدام المتقدم | Advanced usage

- **[Analysis Toolkit](analysis.md)** — 45+ محللاً لغوياً: الجودة، المشاعر، المقروئية، الترابط، البلاغة / 45+ analyzers: quality, sentiment, readability, coherence, rhetoric
- **[CLI Reference](cli.md)** — واجهة سطر الأوامر الكاملة بجميع الأوامر والأعلام / The complete command-line interface
- **[Streaming](streaming.md)** — جلسات معالجة قابلة للاستئناف بنقاط تفتيش ذرّية / Crash-safe resumable processing sessions
- **[Deployment](deployment.md)** — الخادم HTTP، إعادة التحميل الحي، Docker، الأمان / HTTP server, hot reload, Docker, security
- **[Integrations](integrations.md)** — pandas، scikit-learn، spaCy، NLTK، HuggingFace، النماذج العصبية / pandas, scikit-learn, spaCy, NLTK, HuggingFace, neural models
- **[Examples Gallery](examples.md)** — معرض أمثلة عملي / Practical, runnable example gallery

### المرجع | Reference

- **[API Reference](api.md)** — الواجهة البرمجية الكاملة / The complete API surface
- **[Architecture](architecture.md)** — تصميم المكتبة: المراحل، السجل، العقود، الأخطاء / Library design: stages, registry, contracts, errors
- **[Performance](performance.md)** — أرقام الأداء وممارسات التسريع / Throughput numbers and speed-up practices
- **[Migration Guide](migration.md)** — الترقية بين الإصدارات الكبرى / Upgrading between versions

### المساعدة | Getting help

- **[FAQ](faq.md)** — الأسئلة الأكثر شيوعاً / Frequently asked questions
- **[Troubleshooting](troubleshooting.md)** — تشخيص الأخطاء الشائعة وحلولها / Diagnosing and fixing common errors

### للمساهمين | For contributors

- **[Style Guide](style-guide.md)** — معايير الكود والتوثيق / Code and documentation standards
- [CONTRIBUTING.md](../CONTRIBUTING.md) — كيف تساهم / How to contribute
- [SECURITY.md](../SECURITY.md) — الإبلاغ عن الثغرات / Reporting vulnerabilities

---

## نظرة سريعة على المكتبة | Library at a glance

```
من نص عربي فوضوي                إلى نص نظيف موحد + معلومات غنية
From messy Arabic text           to clean unified text + rich signals

  "أهـــلاً شلونك حبيبي؟ 😊 https://t.co/abc 2na bsokra"
                    │
                    ▼
        ArabicNormalizationPipeline
                    │
                    ▼
  "اهلا كيف حالك حبيبي؟"  + dialect: GLF (0.87)
                         + applied_steps: [...]
                         + stop_words_found: {...}
```

- **صفر تبعيات إلزامية** | Zero mandatory dependencies — النواة بايثون قياسي فقط / pure standard library
- **48 معالجاً** | 48 processors — تنظيف وتطبيع لكل جانب من النص / cleaning & normalization for every text aspect
- **45+ محللاً** | 45+ analyzers — من المشاعر إلى البلاغة العربية / from sentiment to Arabic rhetoric
- **8 لهجات** | 8 dialects — كلمات وقفية محلية لكل لهجة / per-dialect stop-word lists
- **43 أمر CLI** | 43 CLI commands
- **اختبارات** | Tests — أكثر من 2300 اختبار / 2,300+ tests

## الروابط | Links

- **PyPI**: <https://pypi.org/project/aranorm/>
- **GitHub**: <https://github.com/Alqudimi/AraNorm>
- **Issues**: <https://github.com/Alqudimi/AraNorm/issues>
- **Changelog**: [CHANGELOG.md](../CHANGELOG.md)
