# Getting Started — البدء مع AraNorm

**5 minutes from `pip install` to normalized Arabic text.**
**خمس دقائق من التثبيت إلى نص عربي نظيف.**

This guide takes you from zero to a working normalization pipeline, then tours the features you will use most. No NLP or ML background required — AraNorm's core is deterministic, instant, and dependency-free.

---

## Table of contents

1. [What is normalization?](#what-is-normalization)
2. [Installation](#installation)
3. [Your first pipeline](#your-first-pipeline)
4. [Presets: choosing a starting point](#presets-choosing-a-starting-point)
5. [Reading the result](#reading-the-result)
6. [Cleaning social media text](#cleaning-social-media-text)
7. [Removing stop words](#removing-stop-words)
8. [Identifying dialects](#identifying-dialects)
9. [Processing many texts](#processing-many-texts)
10. [Analyzing text quality](#analyzing-text-quality)
11. [Using the command line](#using-the-command-line)
12. [Where to go next](#where-to-go-next)

---

## What is normalization?

Arabic text in the wild is messy. The same word can be written a dozen ways:

| Problem | Example | Why it matters |
|---|---|---|
| Diacritics | مُحَمَّد vs محمد | Same word, different byte sequences |
| Alef variants | أحمد، إحمد، آحمد | Search misses matches |
| Hamza carriers | مؤمن، مومن | Inconsistent spelling |
| Tatweel (kashida) | ممـــتاز | Decorative stretching |
| Digit systems | ٢٠٢٥ vs 2025 | Two parallel systems |
| Arabic-Indic punctuation | ؟ ، ؛ | Breaks downstream tools |
| Social noise | URLs, @mentions, emojis | Pollutes analysis |
| Arabizi | 2na 3ndi 7aga | Latin-script Arabic |

**Normalization** maps all these variants to one predictable form, so that search, classification, deduplication, and ML pipelines see *one* word instead of many.

AraNorm does this with a **composable pipeline**: you enable the processors you want, and every text flows through them in a deterministic order.

## Installation

```bash
pip install aranorm
```

That is all — the entire core library works with **zero third-party dependencies**, on Python 3.9 through 3.13.

Optional extras (only if you need them):

```bash
pip install "aranorm[camel]"   # CAMeL Tools: model-based dialect ID (>90% accuracy)
pip install "aranorm[ml]"      # Transformers + PyTorch: neural CODA/MSA normalization
pip install "aranorm[full]"    # Everything
```

Verify the installation:

```bash
$ aranorm version
aranorm 1.15.0
```

## Your first pipeline

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

# 1. Describe what you want
config = PipelineConfig(preset="standard")

# 2. Build the pipeline once
pipeline = ArabicNormalizationPipeline(config)

# 3. Process as much text as you like
result = pipeline.process("أَهـــلاً وَسَهْلاً بِكُم فِي مَرَّاكُش")

print(result.normalized_text)
# اهلا وسهلا بكم في مراكش
```

Three things just happened:

1. **Diacritics were removed** — التشكيل اختفى
2. **Tatweel was stripped** — الكشيدة (ـ) اختفت
3. **Nothing else changed** — the `standard` preset is conservative by design

The pipeline is **reusable and fast**: build it once, call `process()` thousands of times (roughly 1,600 texts/second for the standard preset).

## Presets: choosing a starting point

A preset is a bundle of sensible defaults. Pick the closest one, then tweak individual flags as needed.

```python
from aranorm import ArabicNormalizationPipeline

# light: orthography only, nothing is ever removed
ArabicNormalizationPipeline.from_preset("light")

# standard: default balance — cleans URLs/emails/HTML, normalizes everything
ArabicNormalizationPipeline.from_preset("standard")

# deep: maximum cleaning + collapses expressive repeats (ياااا → يا)
ArabicNormalizationPipeline.from_preset("deep")

# social_media: built for X/WhatsApp/Instagram noise
ArabicNormalizationPipeline.from_preset("social_media")
```

| Preset | Removes | Best for |
|---|---|---|
| `light` | nothing | When you only want spelling unification |
| `standard` | URLs, emails, HTML tags | General purpose, news, documents |
| `deep` | + repeated characters, extra spacing | Search indexing, deduplication |
| `social_media` | + mentions, emojis, fillers, internet slang | X/Twitter, WhatsApp, comments |

Every preset's behavior can be overridden field by field:

```python
config = PipelineConfig(
    preset="social_media",
    clean_emojis=False,        # keep emojis after all
    normalize_taa_marbuta=True, # ة → ه (dialect-friendly)
)
```

## Reading the result

`process()` returns a `NormalizationResult` — much more than a string:

```python
result = pipeline.process("أهـــلاً شلونك حبيبي؟ https://t.co/abc 😊")

result.original_text       # the exact input
result.normalized_text     # the cleaned output
result.dialect             # "GLF" — detected dialect label
result.dialect_confidence  # 0.87 — confidence score
result.applied_steps       # ["remove_html", "remove_urls", ..., "normalize_alef"]
result.processing_time_ms  # 1.8
```

Serialize it anywhere:

```python
result.to_dict()          # JSON-ready Python dict
result.to_json()          # pretty JSON string
result.to_csv_row()       # flat dict for CSV export
```

## Cleaning social media text

Real posts contain URLs, mentions, hashtags, emojis, and Arabizi. Watch the `social_media` preset handle a real tweet:

```python
from aranorm import ArabicNormalizationPipeline

pipeline = ArabicNormalizationPipeline.from_preset("social_media")

tweet = "شفت هالفديو 😂😂 https://youtube.com/watch?v=xyz @user123 #جميل 2na mabsot"
result = pipeline.process(tweet)

print(result.normalized_text)
# شفت هالفديو جميل
```

What was removed: URL ✂️ mentions ✂️ emojis ✂️ Arabizi ✂️ — while the hashtag **word** was kept (`#جميل` → `جميل`).

Arabizi decoding (needs `handle_arabizi=True`):

```python
from aranorm import PipelineConfig, ArabicNormalizationPipeline

config = PipelineConfig(preset="standard", handle_arabizi=True)
pipeline = ArabicNormalizationPipeline(config)

print(pipeline.process("2na 3ndi 7aga gameda").normalized_text)
# انا عندي حاجه جديده
```

## Removing stop words

Stop words (أنا، في، على، الذي...) often need removing before search or ML. Enable the stop-words stage:

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
)
pipeline = ArabicNormalizationPipeline(config)

result = pipeline.process("أنا ذهبت إلى السوق لكي أشتري بعض الفواكه")

print(result.stop_words_removed)   # ذهبت السوق أشتري الفواكه
print(result.stop_words_found)     # {'أنا', 'إلى', 'لكي', 'بعض'}
print(result.stop_words_stats)     # counts, percentage, per-category breakdown
```

Four modes, one config field:

| Mode | Effect |
|---|---|
| `remove` | Strip stop words from the text |
| `extract` | Return **only** the stop words |
| `highlight` | Wrap them: `[[أنا]] ذهبت [[إلى]] السوق` |
| `count` | Text unchanged; stats only |

Dialect-aware removal adds regional stop words:

```python
StopWordsConfig(mode="remove", scope="dialect_aware", dialects={"EGY", "GLF"})
```

Full details in the [Stop Words guide](stopwords.md).

## Identifying dialects

Every pipeline can tell you which dialect a text is in:

```python
from aranorm.stages.dialect_id import DialectIdentifier

identifier = DialectIdentifier()

identification = identifier.identify("إزيك عامل إيه النهاردة؟")
print(identification.dialect_label)      # EGY
print(identification.confidence_score)   # 0.85
print(identification.is_msa)             # False
```

Ten labels are supported: `EGY, GLF, LEV, IRQ, NOR, TUN, YEM, SDN, MTN, MSA`. For model-based identification (>90% accuracy on MADAR), install `aranorm[camel]` and pass `use_camel_tools=True`.

You can also **convert** dialect text toward MSA or CODA with `dialect_target="msa"` or `"coda"`:

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard", dialect_target="msa"))
result = pipeline.process("شلونك وايد زين اليوم")

print(result.normalized_text)   # rule-based normalization
print(result.msa_text)          # كيف حالك كثير جيد اليوم (dialect → MSA mapping)
```

## Processing many texts

For more than a handful of texts, use the batch API:

```python
texts = [
    "النص الأول",
    "النص الثاني",
    "شلونك اليوم؟",   # dialect
    "أهلاً وسهلاً",    # MSA
] * 100

# Sequential — simple and predictable
results = pipeline.process_batch(texts)

# Parallel — uses threads, ~2-4x faster on multi-core
results = pipeline.process_batch(texts, n_workers=4, batch_size=64)

# Streaming — constant memory for millions of texts
for result in pipeline.process_iter(texts, batch_size=100):
    print(result.normalized_text)
```

Export to any format:

```python
from aranorm.utils import BatchExporter

exporter = BatchExporter(results)
exporter.to_csv("normalized.csv")      # opens cleanly in Excel (utf-8-sig)
exporter.to_jsonl("normalized.jsonl")  # one JSON object per line
exporter.to_json("normalized.json")    # one JSON array
```

## Analyzing text quality

AraNorm ships a full analysis toolkit — no extra installs:

```python
from aranorm.analysis.quality_score import analyze_quality
from aranorm.analysis import SentimentAnalyzer, KeywordExtractor

# Composite 0-100 quality score with 8 weighted components
quality = analyze_quality("النص العربي المراد تقييمه")
print(quality.score)         # 82.5
print(quality.label)         # "good"
print(quality.suggestions)   # actionable improvement hints

# Sentiment
sentiment = SentimentAnalyzer().analyze("هذا المنتج رائع جداً")
print(sentiment.label)       # positive

# Keywords
keywords = KeywordExtractor(top_n=5).extract("نص طويل عن موضوع معين...")
print(keywords.top_keywords)
```

45+ analyzers are available — quality, readability, coherence, emotions, entities, topics, rhetoric, and more. See the [Analysis Toolkit guide](analysis.md).

## Using the command line

The `aranorm` command does everything the Python API does:

```bash
# Normalize a single text
$ aranorm normalize "أهـــلاً شلونك؟" --preset social_media

# Normalize a file, one text per line
$ aranorm normalize --file posts.txt --output clean.txt --preset deep

# Sentiment from stdin
$ echo "هذا المنتج رائع" | aranorm sentiment --json

# Quality report
$ aranorm quality "النص المراد تقييمه" --json

# Bulk process with JSONL output and 8 workers
$ aranorm batch --file corpus.txt --output out.jsonl --workers 8 --progress
```

The full 48-command reference lives in the [CLI guide](cli.md).

## Where to go next

- **[Configuration](configuration.md)** — understand every option you can flip
- **[Processors](processors.md)** — see all 48 building blocks with examples
- **[Stop Words](stopwords.md)** — master the stop-word engine
- **[Analysis Toolkit](analysis.md)** — explore the 45+ analyzers
- **[Examples Gallery](examples.md)** — complete, runnable scripts
- **[Performance](performance.md)** — push more texts per second
- **[FAQ](faq.md)** — quick answers
