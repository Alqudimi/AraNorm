# خطة Round 19 — AraNorm

**التاريخ:** 19 أغسطس 2026 | **الحالة الحالية:** إصدار 1.9.0، تغطية 99.17% تعابير / 97.01% فروع، 1754 اختبارًا، 102 ملف mypy.

## فلسفة الجولة

استكمال نهج R17/R18: ميزات جوهرية حقيقية (ليست اختبارات فقط) مبنية على المعمارية الحالية، مدمجة في CLI، مغطاة اختبارات، وموثقة تقارير.

## المحاور الخمسة

### WP1 — وحدة جديدة: WordFrequencyProfiler (تحليل تكرار المفردات العميق)
- ملف جديد `src/aranorm/analysis/word_frequency.py`
- حساب type-token ratio (TTR) المصحح (Corrected TTR، Root TTR)، تنوع المفردات، تكرارات القاموس
- Zipf distribution diagnostics (أس تقريبي للتوزيع)، تكرارات الألفاظ الأعلى مع مواقعها
- Lexical density (كثافة المفردات المفتوحة)
- تكامل: CLI أمر `freqprofile`

### WP2 — توسيع: SpellingReport بخاصية اقتراح التصحيح (corrections)
- توسيع وحدة R17 الموجودة `spelling_report.py`
- اقتراحات تصحيح مبنية على: قواعد التصحيح العكسية (من قواعد processor الحالية)، المسافة التحريرية (FuzzyMatcher الموجودة)، وأولوية القواعد على الفوضى
- حقل جديد `corrections` في SpellingCorrection مع confidence
- يجب أن يبقى متكاملاً مع idiom exclusion

### WP3 — وحدة جديدة: SentimentReport موسع (تعزيز وحدة المشاعر)
- الوحدة موجودة في R16 بدرجة 100% — لا نعيد بنائها، نضيف طبقة `DialectSentimentEnhancer`؟ الأفضل: وحدة جديدة `TextCoherenceScore`؟
- **القرار:** وحدة `TextCoherenceScore` (مؤشر تماسك النص): تكرار المفردات المفتوحة، ترابط الجمل عبر المعاجم الرابطة (ثم، لذلك، بالإضافة)، تنوع الروابط، طول الجمل المتوازن — نمط يضاف إلى عائلة QualityScore
- + وحدة `ReadabilityEnhancer`؟ لا — تبقى واحدة. WP3 = TextCoherenceScore فقط مع CLI `coherence`

### WP4 — توسيع: TopicClassifier بإضافة 4 مواضيع (مجموع 14)
- topics: history, environment, culture, sports... اختيار 4 منطقية: التاريخ، البيئة، الثقافة، الرياضة الرياضية موجودة (sport) — إضافة: history, environment, culture, religion موجودة. إذن: history, environment, culture, social (اجتماعي)
- فحص الأسماء الحالية أولاً: القانوني، الطبي، الرياضي، الديني، التعليمي، الاقتصادي، التقني، الإعلامي، السياسي، العام → إضافات: التاريخ، البيئة، الثقافة، الاجتماعي
- توسيع قاموس المكونات لكل موضوع + دمج في CLI موجود

### WP5 — توسيع: CorpusAnalyzer بإضافة تحليلات جديدة
- وحدة موجودة وناضجة — إضافة: `CorpusOverlapAnalysis` (التشابك المفرداتي بين نصوص)، + `CorpusKeywordExtractor`؟
- الأفضل: دالة جديدة `corpus_overlap` في CorpusAnalyzer تعيد مصفوفة تداخل المفردات بين الوثائق + مؤشر التمييز المفرداتي per-doc (distinctiveness)
- CLI: أمر `corpus-overlap`؟ قد يكون معقدًا — دمج في `corpus` command إن وجد، وإلا skip CLI مع وثائق API كاملة

## ترتيب التنفيذ
1. WP1 WordFrequencyProfiler (مع CLI + 40+ اختبارًا)
2. WP2 Spelling corrections (مع CLI + 40+ اختبارًا)
3. WP3 TextCoherenceScore (مع CLI + 35+ اختبارًا)
4. WP4 TopicClassifier expansion (مع 30+ اختبارًا)
5. WP5 Corpus overlap (مع 20+ اختبارًا)
6. ربط CLI + exports + CHANGELOG + version 2.0.0 (أو 1.10.0 — الأفضل 1.10.0 لتجنب breaking changes المذكورة في roadmap لـ v2.0)
7. اختبار نهائي + coverage + تقرير ROUND19_RELEASE_REPORT.md + أرشيف

## معايير القبول
- >=95% branch coverage (مستمر من R17/R18)
- make verify نظيف: black + flake8 + mypy
- >=95% من الاختبارات تمر (0 failures)
- كل ميزة جديدة: وحدة + اختبارات + CLI (إن أمكن) + CHANGELOG
