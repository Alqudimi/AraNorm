<div align="center">

# AraNorm

**مكتبة بايثون احترافية شاملة لتطبيع النصوص العربية — فصحى ولهجات وعربيزي**
**Production-grade Arabic text normalization — MSA, dialects, Arabizi & 45+ analyzers**

[![PyPI version](https://img.shields.io/pypi/v/aranorm.svg)](https://pypi.org/project/aranorm/)
[![Python versions](https://img.shields.io/pypi/pyversions/aranorm.svg)](https://pypi.org/project/aranorm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-2300%2B-passing.svg)](tests/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[التثبيت](#-التثبيت--installation) · [البدء السريع](#-البدء السريع--quick-start) · [التوثيق](docs/) · [CLI](#-واجهة-السطر-الأوامر--command-line) · [المساهمة](CONTRIBUTING.md)

</div>

---

**English** — AraNorm is a production-grade, dependency-free Arabic text normalization library for Python. It unifies orthographic normalization, dialect handling, Arabizi transliteration, stop-word processing, and 45+ linguistic analyzers behind one clean, typed, thoroughly tested API — replacing the usual pile of incompatible tools (PyArabic + CAMeL Tools + tnkeeh + custom regexes) with a single import.

**العربية** — AraNorm مكتبة بايثون احترافية لتطبيع النصوص العربية بلا أي تبعيات إلزامية. توحّد المكتبة التطبيع الإملائي، ومعالجة اللهجات، وتحويل العربيزي، ومعالجة الكلمات الوقفية، وأكثر من 45 محللاً لغوياً — خلف واجهة برمجية واحدة نظيفة ومُوثّقة الأنواع ومختبَرة باختبارات تتجاوز 2300 اختبار، لتستغني عن عدة مكتبات متفرقة وغير متوافقة.

```
┌────────────────────────────────────────────────────────────────┐
│                  ArabicNormalizationPipeline                   │
├────────────────────────────────────────────────────────────────┤
│  ContentCleaner   →   OrthographicNormalizer   →  DialectProc  │
│  (URLs, HTML,         (alef, hamza, diacritics,   (identify,   │
│   emojis, mentions,    tatweel, digits,            CODA, MSA)  │
│   hashtags, ...)       punctuation, ...)                       │
├────────────────────────────────────────────────────────────────┤
│            StopWordsStage  ·  45+ Analyzers  ·  CLI            │
└────────────────────────────────────────────────────────────────┘
```

## ✨ المزايا الرئيسية | Key Features

| | الميزة | Feature |
|---|---|---|
| 🚀 | **صفر تبعيات إلزامية** — النواة تعمل ببايثون القياسي فقط | **Zero mandatory dependencies** — pure standard-library core |
| 🔤 | تطبيع إملائي كامل: الألف، الهمزة، التاء المربوطة، التشكيل، الكشيدة، الأرقام، الترقيم | Full orthographic normalization: alef, hamza, taa marbuta, diacritics, tatweel, digits, punctuation |
| 🗣️ | تحديد اللهجة heuristically لعشر مناطق (مصر، خليج، شام، عراق، مغارب، يمن، سودان...) | Heuristic dialect identification for 10 regions |
| 🔄 | تحويل العربيزي إلى عربية (2na → أنا، 3nd → عند) | Arabizi → Arabic transliteration |
| 🛑 | منظومة كلمات وقفية متقدمة: 8 لهجات + نطاقات + سياق + مجالات | Advanced stop-words engine: 8 dialects + scopes + context + domains |
| 📊 | 45+ محللاً: مشاعر، مشاعر ثمانية، جودة، مقروئية، ترابط، أسلوب، جناس، سجع، طباق... | 45+ analyzers: sentiment, emotions, quality, readability, coherence, style, wordplay... |
| ⚡ | معالجة دفعات متوازية + بث تدفقي قابل للاستئناف بنقاط تفتيش | Parallel batch processing + resumable streaming with checkpoints |
| 🖥️ | واجهة سطر أوامر بـ 43 أمراً + خادم HTTP مدمج | 43-command CLI + built-in HTTP server |
| 🧩 | تكاملات جاهزة: pandas، scikit-learn، spaCy، NLTK، HuggingFace | Ready integrations: pandas, scikit-learn, spaCy, NLTK, HuggingFace |
| 🔒 | شامل الأنواع (`py.typed`) + اختبارات عقود صارمة | Fully typed (`py.typed`) + strict contract testing |

## 📦 التثبيت | Installation

```bash
pip install aranorm
```

التبعيات الاختيارية | Optional extras:

```bash
pip install "aranorm[camel]"   # CAMeL Tools — تحديد لهجة بالنموذج (دقة >90%) على MADAR
pip install "aranorm[ml]"      # Transformers + PyTorch — تطبيع CODA/MSA عصبي
pip install "aranorm[full]"    # كل شيء | everything
```

> **ملاحظة | Note** — النواة الكاملة (جميع الـ presets، الكلمات الوقفية، المحللات، الـ CLI، الخادم) تعمل بدون أي تبعية خارجية. التبعيات الاختيارية فقط لقدرات إضافية متخصصة.
> The complete core (all presets, stop words, analyzers, CLI, server) works with **zero** third-party dependencies. Extras only unlock specialized capabilities.

## 🚀 البدء السريع | Quick Start

### 1) التطبيع الأساسي | Basic normalization

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

config = PipelineConfig(
    preset="standard",        # "light" | "standard" | "deep" | "social_media"
    dialect_target="coda",    # "none" | "coda" | "msa"
    remove_diacritics=True,
    normalize_hamza=True,
    handle_arabizi=True,
)

pipeline = ArabicNormalizationPipeline(config)
result = pipeline.process("أهـــلاً شلونك حبيبي؟ https://t.co/abc 😊")

print(result.normalized_text)   # اهلا شلونك حبيبي?
print(result.dialect)           # GLF
print(result.dialect_confidence)
print(result.applied_steps)     # every applied processor, in order
```

### 2) الكلمات الوقفية | Stop words

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(
        mode="remove",          # "remove" | "extract" | "highlight" | "count"
        scope="dialect_aware",  # "universal" | "msa_only" | "dialect_aware" | "custom"
        dialects={"EGY", "GLF"},
        preserve_negation=True, # keep لا، لم، لن
        remove_filler=True,     # strip يعني، والله، خلاص...
    ),
)
pipeline = ArabicNormalizationPipeline(config)
result = pipeline.process("أنا سعيد جداً اليوم")

print(result.stop_words_removed)   # سعيد اليوم
print(result.stop_words_found)     # {'أنا', 'جداً'}
print(result.stop_words_stats)     # counts, ratio, per-category breakdown
```

### 3) التحليل اللغوي | Linguistic analysis

```python
from aranorm.analysis import (
    SentimentAnalyzer, KeywordExtractor, ArabicTextSummarizer,
    ArabicReadabilityAnalyzer, EmotionAnalyzer, StyleAnalyzer,
)
from aranorm.analysis.quality_score import analyze_quality

sentiment = SentimentAnalyzer().analyze("هذا المنتج رائع جداً")
print(sentiment.label, sentiment.score)          # positive 0.75

keywords = KeywordExtractor(top_n=5).extract("...")
print(keywords.top_keywords)

quality = analyze_quality("نص عربي للتحليل")
print(quality.score, quality.label, quality.suggestions)
```

### 4) الدفعات والتصدير | Batches & export

```python
from aranorm.utils import BatchExporter

results = pipeline.process_batch(["نص أول", "نص ثاني"], n_workers=4)

exporter = BatchExporter(results)
exporter.to_csv("output.csv")
exporter.to_jsonl("output.jsonl")
exporter.to_json("output.json")
```

### 5) سطر الأوامر | Command line

```bash
$ aranorm normalize "أهـــلاً شلونك؟" --preset social_media
$ echo "نص للتحليل" | aranorm sentiment --json
$ aranorm batch --file input.txt --output out.jsonl --preset deep --workers 8
$ aranorm quality "النص العربي" --json
$ aranorm serve --port 8765        # HTTP normalization service
```

## 🎛️ الإعدادات المسبقة | Presets

| Preset | الاستخدام | Use case |
|---|---|---|
| `light` | تطبيع إملائي فقط دون حذف أي محتوى | Orthographic pass only; nothing removed |
| `standard` | التوازن الافتراضي: تنظيف روابط/بريد/HTML + تطبيع كامل | Default balance: clean URLs/emails/HTML + full normalization |
| `deep` | أقصى تنظيف + تقليص التكرارات الإنتاجية (ياااا → يا) | Maximum cleaning + expressive repetition collapse |
| `social_media` | للمنصات الاجتماعية: إزالة منشنات/إيموجي + كلمات وقفية تلقائية | Social platforms: strip mentions/emojis + auto stop-words |

كل خيار متاح كحقل مستقل في `PipelineConfig` — عدّل ما تشاء فوق أي preset. | Every option is an independent `PipelineConfig` field — override anything on top of any preset.

## 🆚 المقارنة مع المكتبات الأخرى | Comparison

| Capability | **AraNorm** | CAMeL Tools | PyArabic | tnkeeh |
|---|:---:|:---:|:---:|:---:|
| Unified pipeline | ✅ | ❌ | ❌ | ❌ |
| Dialect-aware | ✅ 10 regions | ✅ 5 (MADAR) | ❌ | ❌ |
| Arabizi conversion | ✅ | ❌ | ❌ | ❌ |
| Platform normalizers (X/WhatsApp) | ✅ | ❌ | ❌ | ❌ |
| Stop-word engine | ✅ 8 dialects + domains | ❌ | ❌ | ❌ |
| Analysis toolkit | ✅ 45+ analyzers | ✅ (ML) | ❌ | ❌ |
| Batch + streaming | ✅ resumable | ❌ | ❌ | ❌ |
| CLI | ✅ 43 commands | ✅ | ❌ | ❌ |
| Zero mandatory deps | ✅ | ❌ (requires CAMeL) | ✅ | ✅ |

AraNorm لا تستبدل أدوات التعلم الآلي — بل تكمّلها: استخدم CAMeL Tools أو Transformers عبر التبعيات الاختيارية عندما تحتاج دقة النماذج، واستخدم نواة AraNorm السريعة دائماً.

AraNorm does not replace ML tooling — it complements it: use CAMeL Tools or Transformers through the optional extras when you need model accuracy, and use the fast AraNorm core everywhere else.

## 📚 التوثيق | Documentation

| الدليل | Guide | المحتوى | Contents |
|---|---|---|---|
| [Getting Started](docs/getting-started.md) | البدء | التثبيت، أول pipeline، الأساسيات | Install, first pipeline, basics |
| [Configuration](docs/configuration.md) | الإعدادات | كل حقول `PipelineConfig` موثقة | Every `PipelineConfig` field |
| [Presets & Processors](docs/processors.md) | المعالجات | 48 معالجاً مشروحاً بالأمثلة | All 48 processors explained |
| [Stop Words](docs/stopwords.md) | الكلمات الوقفية | الأوضاع، النطاقات، اللهجات، المجالات | Modes, scopes, dialects, domains |
| [Analysis Toolkit](docs/analysis.md) | التحليل | 45+ محللاً بالتفصيل | All 45+ analyzers in depth |
| [CLI Reference](docs/cli.md) | سطر الأوامر | 43 أمراً بكل الخيارات | All 43 commands |
| [Streaming & Server](docs/streaming.md) | البث والخادم | جلسات قابلة للاستئناف + HTTP | Resumable sessions + HTTP |
| [Integrations](docs/integrations.md) | التكاملات | pandas، sklearn، spaCy، NLTK، HF | pandas, sklearn, spaCy, NLTK, HF |
| [API Reference](docs/api.md) | المرجع | الواجهة البرمجية الكاملة | Complete API surface |
| [Architecture](docs/architecture.md) | المعمارية | المراحل، السجل، العقود | Stages, registry, contracts |
| [Performance](docs/performance.md) | الأداء | أرقام الإنتاجية والممارسات | Throughput numbers & practices |
| [FAQ](docs/faq.md) | أسئلة شائعة | إجابات عملية | Practical answers |
| [Troubleshooting](docs/troubleshooting.md) | حل المشاكل | تشخيص الأخطاء الشائعة | Diagnosing common errors |
| [Migration](docs/migration.md) | الترقية | التغييرات بين الإصدارات | Changes between versions |

## ⚡ الأداء | Performance

أرقام مرجعية على جهاز محمول (Core i7، معالجة متتابعة) | Reference numbers on a laptop (Core i7, sequential):

| Preset | Throughput |
|---|---|
| `light` | ~2,400 texts/s |
| `standard` | ~1,650 texts/s |
| `deep` | ~1,350 texts/s |
| `social_media` | ~1,430 texts/s |

شغّل القياس بنفسك | Run the benchmark yourself:

```bash
pip install -e ".[dev]" && python scripts/benchmark.py
```

## 🤝 المساهمة | Contributing

المساهمات مرحب بها! | Contributions are welcome!

```bash
git clone https://github.com/Alqudimi/AraNorm.git
cd AraNorm
pip install -e ".[dev]"
make verify     # format-check + lint + type-check + tests
```

انظر [CONTRIBUTING.md](CONTRIBUTING.md) للتفاصيل، و[SECURITY.md](SECURITY.md) لسياسة الإبلاغ عن الثغرات.
See [CONTRIBUTING.md](CONTRIBUTING.md) for details and [SECURITY.md](SECURITY.md) for the vulnerability disclosure policy.

## 📄 الترخيص | License

MIT © 2024-2026 [Abdulaziz Mohammed Alqudimi](https://github.com/Alqudimi) — انظر | see [LICENSE](LICENSE).

## 📖 الاقتباس | Citation

إذا استخدمت AraNorm في بحث علمي، اقتبسها عبر ملف `CITATION.cff`:
If you use AraNorm in academic work, please cite it via the `CITATION.cff` file:

```bibtex
@software{alqudimi_aranorm_2026,
  author  = {Alqudimi, Abdulaziz Mohammed},
  title   = {AraNorm: Production-grade Arabic Text Normalization},
  year    = {2026},
  url     = {https://github.com/Alqudimi/AraNorm},
  version = {1.15.0}
}
```

---

<div align="center">

**صُنع بعناية للغة العربية** 🌙
*Crafted with care for the Arabic language*

</div>
