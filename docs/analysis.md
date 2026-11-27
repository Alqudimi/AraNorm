# Analysis Toolkit — The Complete Guide

**AraNorm v1.15.0** · 45+ analyzers · 100% dependency-free · MSA + dialects

The `aranorm.analysis` package is AraNorm's measurement layer. While the
[processors](processors.md) and the [stop-words system](stopwords.md) *change*
text, the analyzers *understand* it: they quantify quality, polarity,
readability, rhetoric, structure, similarity, and corpus-level statistics for
Arabic text — with zero external dependencies, no model downloads, and no GPU.

Every analyzer in this guide follows three conventions:

1. **Constructor takes thresholds** — everything works out of the box with
   `ClassName()`, and every tunable knob (windows, thresholds, weights,
   top-N) is a constructor argument with a sensible default.
2. **One main method** — `analyze(text)` for most analyzers, or `extract`,
   `summarize`, `profile`, `compare`, `classify`, `diff` for specialists.
3. **Dataclass results** — output is a documented dataclass, with
   `to_dict()` / `to_json()` on most modern analyzers.

## Analysis and normalization: how they fit together

The analyzers are built on top of the same stop-words registry and
normalization rules that power the pipeline, so:

- **Analyzers accept raw or normalized text.** They clean internally (strip
  diacritics, ignore punctuation, normalize alef forms) — point them at noisy
  social-media text or clean MSA prose without preprocessing.
- **Normalization is measurable.** Run an analyzer before and after a
  pipeline to quantify what changed — readability gained, dialect markers
  removed, spelling issues fixed. `TextDiffReport.from_normalization()` is
  purpose-built for this.

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.analysis import ArabicReadabilityAnalyzer, TextDiffReport

raw = "هذا النص يحتوى على اخطاء املئية كثيرة  !!!!"
pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
norm = pipeline.process(raw)

# Diff: what did normalization change, token by token?
diff = TextDiffReport.from_normalization(raw, norm)
print(diff.similarity_ratio, diff.changed_count)

# Measure: did readability improve?
read = ArabicReadabilityAnalyzer()
print(read.analyze(raw).score)                  # before
print(read.analyze(norm.normalized_text).score) # after
```

The typical workflow is **normalize → analyze** for clean metrics, or
**analyze raw** when you want to measure source noise (dialect markers,
elongations, mixed digit systems). Both are first-class use cases.

---

## Table of contents

1. [Quick tour](#1-quick-tour)
2. [Core text analysis](#2-core-text-analysis) — `TextAnalyzer`, `WordFrequencyProfiler`, `ComplexityAnalyzer`
3. [Quality & correctness](#3-quality--correctness) — `QualityScoreAnalyzer`, `SpellingAnalyzer`, `ArabicReadabilityAnalyzer`
4. [Sentiment & emotion](#4-sentiment--emotion) — `SentimentAnalyzer`, `EmotionAnalyzer`
5. [Content extraction](#5-content-extraction) — `KeywordExtractor`, `ArabicTextSummarizer`, `EntityAnalyzer`, `TopicClassifier`, `NumericAnalyzer`
6. [Comparison & diff](#6-comparison--diff) — `TextComparator`, `TextSimilarityMatrix`, `TextDiffReport`
7. [Corpus analysis](#7-corpus-analysis) — `CorpusAnalyzer`, `CorpusStopWordsBuilder`, `BatchAnalyzer`
8. [Linguistic structure](#8-linguistic-structure) — `PronounAnalyzer`, `IdiomAnalyzer`, `CoherenceAnalyzer`
9. [Style & register](#9-style--register) — `StyleAnalyzer`, `LoanwordAnalyzer`, `QuotationAnalyzer`
10. [Rhetorical analysis](#10-rhetorical-analysis) — 8 axis analyzers (rhetorical questions, anaphora, wordplay, contrast, fillers, rhythm, figures, roots)
11. [The unified profiler](#11-the-unified-profiler) — `AnalysisProfiler`, `profile_text` (22 axes)
12. [Choosing the right analyzer](#12-choosing-the-right-analyzer)
13. [CLI equivalents](#13-cli-equivalents)
14. [Where to go next](#14-where-to-go-next)

---

## 1. Quick tour

Four examples that cover 90% of day-one needs. All run as-is.

### 1.1 Score text quality (0–100, with component breakdown)

```python
from aranorm.analysis.quality_score import analyze_quality

result = analyze_quality("هذا نص عربي واضح ومفهوم.")
print(result.score)                  # e.g. 84.1
print(result.label)                  # excellent | good | fair | poor
print(result.summary())              # one-line human summary

for component in result.components:  # 8 weighted components
    print(f"{component.name:22} {component.score:6.1f} (weight {component.weight})")
```

### 1.2 Sentiment with negation handling

```python
from aranorm.analysis import SentimentAnalyzer

result = SentimentAnalyzer().analyze("هذا الفيلم ليس جيد")
print(result.label)            # negative — negation flipped "جيد"
print(result.score)            # e.g. -0.56
print(result.negated_words)    # words whose polarity was inverted
```

### 1.3 One-pass full profile (22 axes)

```python
from aranorm.analysis import profile_text

profile = profile_text("أليس العلم نوراً يهدي العقول؟ نعم، وهو سلاح الأمم في صعودها.")
print(profile.axes["sentiment"]["label"])
print(profile.axes["rquestions"]["label"])
print(profile.axes["coherence"]["score"])

for insight in profile.insights:      # cross-signal notes
    print(f"[{insight.rule}] {insight.message}")
```

### 1.4 Corpus-level report

```python
from aranorm.analysis.batch_analysis import analyze_batch

texts = [
    "أعلنت الشركة عن أرباح قياسية هذا الربع.",
    "شو هالزحمة بالشارع اليوم، مو معقول!",
    "The quarterly report is attached.",
]
report = analyze_batch(texts)
print(report.summary())
print(report.quality_distribution.to_dict())   # {"excellent": 1, ...}
print(report.language_distribution)            # {"arabic": 2, "latin": 1}
print(report.recommendations)
```

---

## 2. Core text analysis

### 2.1 TextAnalyzer — full linguistic breakdown

The workhorse. Runs a complete stop-word analysis and returns 27 fields:
counts, ratios, frequencies, complexity, and a dialect hint.

```python
from aranorm.analysis import TextAnalyzer
```

**Constructor:** `TextAnalyzer(config=None, registry=None, top_n=10)` —
`config` is a `StopWordsConfig` (which words count as stop words), `registry`
a shared `StopWordsRegistry`, `top_n` how many top content words to keep.

**Methods:** `analyze(text) -> TextAnalysisResult`, `analyze_batch(texts)`,
`compare_complexity(texts)` (summaries sorted by lexical diversity,
most diverse first).

**`TextAnalysisResult` fields:**

| Field | Meaning | Field | Meaning |
|---|---|---|---|
| `total_tokens` / `total_words` / `total_chars` | Raw, Arabic-only, character counts | `stop_words_count` / `stop_words_ratio` | Distinct stop words / their share |
| `unique_words` | Vocabulary size | `content_words_count` / `content_words_ratio` | Non-stop-word tokens / share |
| `content_words` | Content tokens in order | `stop_words_found` | Set of stop words present |
| `stop_words_by_category` | Registry categories | `word_frequency` / `content_word_frequency` | Frequency dicts |
| `top_content_words` | Top `(word, count)` pairs | `avg_word_length` | Mean chars per word |
| `lexical_diversity` | unique / total words | `stop_word_density` | Stop words per sentence |
| `estimated_complexity` | `simple` \| `moderate` \| `complex` | `sentence_count` / `avg_sentence_length` | Sentence stats |
| `dialect_hint` | `EGY`/`GLF`/`LEV`/`IRQ`/`NOR` or `None` | `extra` | Reserved metadata |

```python
from aranorm.analysis import TextAnalyzer

analyzer = TextAnalyzer(top_n=5)
result = analyzer.analyze("أنا والله سعيد جداً بهذا النتيجة الرائعة")

print(result.total_words)          # 7
print(result.content_words)        # content tokens, order preserved
print(result.stop_words_ratio)
print(result.estimated_complexity) # 'simple' | 'moderate' | 'complex'
print(result.top_content_words)

# Compare several texts by complexity
for s in analyzer.compare_complexity([
    "الكتاب جيد.",
    "أعلن الرئيس عن خطة اقتصادية شاملة تستهدف تحقيق نمو مستدام.",
]):
    print(s["complexity"], s["lexical_diversity"], s["text_preview"])
```

**Dialect hints.** Stop words found are matched against dialect indicator
sets: Egyptian (كده، إيه، بقى), Gulf (الحين، شلون، وايد), Levantine (هيك،
شو، هلق), Iraqi (هسة، شنو، مو), North African (بزاف، مزيان، دابا). No
match → `None`.

### 2.2 WordFrequencyProfiler — vocabulary and Zipf statistics

A corpus-linguistics-grade frequency profiler: ranked table, TTR variants
that correct for text length, lexical density, and a fitted Zipf exponent.

```python
from aranorm.analysis import WordFrequencyProfiler
```

**Constructor:** `WordFrequencyProfiler(top_n=20, min_word_length=2)`.

**Method:** `profile(text) -> WordFrequencyResult`.

**`WordFrequencyResult` fields:** `total_tokens`, `unique_types`,
`frequency_table` (a list of `FrequencyEntry(word, count, rank,
relative_frequency, first_positions)`), `type_token_ratio`, `corrected_ttr`
(size-corrected), `root_ttr` (unique/√total — length-robust),
`lexical_density` (content words / total), `zipf_exponent` (fitted power-law
slope, `None` for tiny inputs), `top_n`.

```python
from aranorm.analysis import WordFrequencyProfiler

result = WordFrequencyProfiler(top_n=5).profile(
    "التعليم التعليم أساس النهضة، والتعليم يحتاج استثماراً كبيراً وصبراً طويلاً"
)
print(result.total_tokens, result.unique_types)
print(result.type_token_ratio)   # shrinks as text repeats vocabulary
print(result.root_ttr)           # comparable across different text lengths
print(result.zipf_exponent)      # ~1.0 → classic Zipfian decay

for entry in result.frequency_table:
    print(f"#{entry.rank} {entry.word} ×{entry.count} ({entry.relative_frequency:.3f})")
```

**Which diversity measure?** Plain `type_token_ratio` grows with text
length — use `corrected_ttr` or `root_ttr` when comparing texts of
different sizes.

### 2.3 ComplexityAnalyzer — word-length and fusion profile

A focused morphological-complexity probe: how long are the words, and how
much of the text is "fused" (long, clitic-heavy tokens typical of
undiacritized written Arabic)?

```python
from aranorm.analysis.complexity_analyzer import ComplexityAnalyzer, analyze_complexity
```

**Constructor:** `ComplexityAnalyzer(complex_threshold=5.0,
simple_threshold=4.0, fused_length=6)` — average word length above 5.0 →
`complex`, below 4.0 → `simple`; tokens of `fused_length`+ characters count
as fused.

**Methods:** `analyze(text) -> ComplexityResult`, `analyze_batch(texts)`,
shortcut `analyze_complexity(text)`.

**`ComplexityResult` fields:** `avg_word_length`, `max_word_length`,
`fused_ratio`, `length_distribution` (word-length → count histogram),
`word_count`, `label` (`simple` | `moderate` | `complex`).

```python
from aranorm.analysis.complexity_analyzer import analyze_complexity

result = analyze_complexity("وبالرغم من الصعوبات، استطاعت المؤسسات تحقيق أهدافها")
print(result.avg_word_length)      # e.g. 6.3
print(result.fused_ratio)          # share of 6+ character tokens
print(result.label)                # 'complex'
print(result.length_distribution)
```

---

## 3. Quality & correctness

### 3.1 QualityScoreAnalyzer — composite 0–100 quality score

Combines eight orthogonal signals into one weighted score — the analyzer
behind the `quality` CLI command and the headline metric in `BatchAnalyzer`
reports.

```python
from aranorm.analysis.quality_score import QualityScoreAnalyzer, analyze_quality
```

**Constructor:** `QualityScoreAnalyzer()` — no options; the weighting is
fixed and calibrated.

**Method:** `analyze(text) -> TextQualityScore` (shortcut:
`analyze_quality(text)`).

**The eight components** — `spelling` 0.26, `consistency` 0.22,
`lexical_balance` 0.19, `readability` 0.10, `rhetorical_richness` 0.08,
`structural_balance` 0.07, `diacritics` 0.05, `rhetorical_depth` 0.03.

**`TextQualityScore` fields:** `score` (0–100), `label` (`excellent` ≥ 90,
`good` ≥ 75, `fair` ≥ 55, else `poor`), `components` — each a
`ComponentScore(name, score, weight, issues)` — plus aggregated `issues`,
`suggestions`, and `analyzed_text_length`. `to_dict()`, `to_json()`,
`summary()` available.

```python
from aranorm.analysis.quality_score import QualityScoreAnalyzer

result = QualityScoreAnalyzer().analyze(
    "هذا تقرير رسمي واضح، يعرض النتائج بدقة ويختم بتوصيات محددة."
)
print(f"{result.score:.1f}/100 — {result.label}")

weakest = min(result.components, key=lambda c: c.score)
print(f"weakest: {weakest.name} = {weakest.score}")
for issue in weakest.issues:
    print(" -", issue)
for suggestion in result.suggestions:
    print("→", suggestion)
```

### 3.2 SpellingAnalyzer — per-word spelling report

Wraps the deterministic `SpellingProcessor` rule engine (hamza forms, final
alef maqsura, common typos) and turns its output into an inspectable report.

```python
from aranorm.analysis.spelling_report import SpellingAnalyzer, analyze_spelling
```

**Constructor:** `SpellingAnalyzer(processor=None, idiom_exclusion=True)`.
Idiom exclusion matters: "انشاء الله" inside a recognized idiom span is a
fixed expression, not a spelling error, so it is not flagged by default.

**Method:** `analyze(text) -> SpellingReport` (shortcut:
`analyze_spelling(text)`).

**`SpellingReport` fields:** `original_text`, `corrected_text`,
`total_words`, `spelling_issues_found` (all corrections including repeats),
`unique_issues`, `correct_ratio` (0–1), `corrections` — each a
`SpellingCorrection(word, replacement, count, category, suggestions)` with
category `hamza` | `waw` | `alef` | `typo` — `category_distribution`,
`confidence`. `to_dict()` / `to_json()` / `summary()` available.

```python
from aranorm.analysis.spelling_report import analyze_spelling

report = analyze_spelling("مسئول الاعلان عن الحدث الاهمية سيتولى المهام")
print(report.summary())
print(report.correct_ratio)

for correction in report.corrections:
    print(f"{correction.word} → {correction.replacement}  "
          f"(×{correction.count}, {correction.category})")

print(report.corrected_text)   # corrected text, ready to use
```

### 3.3 ArabicReadabilityAnalyzer — Flesch-inspired Arabic score

A 0–100 composite readability score calibrated for Arabic, **higher =
easier**. Blends five components: sentence length (30%), word length (20%),
vocabulary richness (20%), subordinate-clause markers (20%), diacritic
density (10%).

```python
from aranorm.analysis import ArabicReadabilityAnalyzer
```

**Constructor:** `ArabicReadabilityAnalyzer(max_easy_sentence=10,
max_easy_word=5)` — sentences ≤ 10 words and words ≤ 5 chars score full
marks on their component.

**Methods:** `analyze(text) -> ReadabilityResult`, `analyze_batch(texts)`,
`corpus_summary(texts)` (dict with `text_count`, `mean_score`, `score_std`,
`label_distribution`, `easiest_index`, `hardest_index`,
`mean_sentence_length`, `mean_type_token_ratio`), and
`compare(texts, sort_by='score')` — `(text, result)` pairs, easiest first
(`"score_desc"` for hardest first).

**`ReadabilityResult` fields:** `score`, `readability_label`
(`very_easy` ≥ 80, `easy` ≥ 60, `moderate` ≥ 40, `complex` ≥ 20,
`very_complex`), `sentence_count`, `word_count`, `unique_words`,
`avg_sentence_length`, `max_sentence_length`, `sentence_length_variance`,
`avg_word_length`, `long_word_ratio`, `type_token_ratio`, `hapax_ratio`
(words appearing exactly once), `diacritic_ratio`, `complexity_marker_count`
(subordinators like الذي، حيث، لأن), `connector_count`, `detail`
(component sub-scores). `to_dict()` available.

```python
from aranorm.analysis import ArabicReadabilityAnalyzer

analyzer = ArabicReadabilityAnalyzer()
simple = analyzer.analyze("الكتاب جيد. أحببته كثيراً.")
formal = analyzer.analyze(
    "أعلن الرئيس عن خطة اقتصادية شاملة تستهدف تطوير البنية التحتية وتحسين مستوى المعيشة "
    "للمواطنين في ظل التحولات العالمية التي تشهدها الأسواق، حيث تشير التوقعات إلى أن "
    "الإصلاحات الهيكلية ستساهم في تعزيز النمو المستدام."
)
print(simple.readability_label)   # 'easy'
print(formal.readability_label)   # 'complex'
print(formal.score)               # e.g. 20.15
print(formal.detail)              # component sub-scores

summary = analyzer.corpus_summary([
    "الكتاب جيد. أحببته كثيراً.",
    "أعلن الرئيس عن خطة اقتصادية شاملة.",
])
print(summary["hardest_index"], summary["label_distribution"])
```

---

## 4. Sentiment & emotion

### 4.1 SentimentAnalyzer — polarity with negation windows

Scores text from **−1.0 (very negative) to +1.0 (very positive)** using a
curated lexicon covering MSA and the major dialects. The distinctive feature
is the **negation window**: a negation word (ليس، لا، ما، لم…) flips the
polarity of the next *N* tokens, so "ليس جيداً" correctly scores negative.

```python
from aranorm.analysis import SentimentAnalyzer
```

**Constructor:** `SentimentAnalyzer(negation_window=3,
neutral_threshold=0.05, sentence_level=True)` — how many tokens after a
negator flip; the |score| below which the label is `neutral`; and whether to
populate `sentence_scores`.

**Methods:** `analyze(text) -> SentimentResult`, `analyze_batch(texts)`,
`get_lexicon_stats()` (positive/negative/intensifier/negation lexicon sizes).

**`SentimentResult` fields:**

| Field | Meaning |
|---|---|
| `score` | −1.0 … +1.0 |
| `label` | `positive` \| `negative` \| `neutral` |
| `confidence` | 0–1, derived from evidence strength |
| `positive_words` / `negative_words` | Matched polarity vocabulary |
| `intensifiers_found` | e.g. جداً، للغاية |
| `negated_words` | Words flipped by negation |
| `sentence_scores` | `(sentence, score)` per sentence |

`to_dict()` available.

```python
from aranorm.analysis import SentimentAnalyzer

analyzer = SentimentAnalyzer()
print(analyzer.analyze("هذا الفيلم ليس جيد").label)    # negative
print(analyzer.analyze("هذا الفيلم جيد جداً").label)    # positive
print(analyzer.analyze("الطقس اليوم معتدل").label)      # neutral

result = analyzer.analyze("الخدمة ممتاز والأسعار سيئة")
print(f"{result.score:+.2f} ({result.label})")
print("positive:", result.positive_words)
print("negative:", result.negative_words)
print("intensifiers:", result.intensifiers_found)

for sentence, score in result.sentence_scores:
    print(f"  {score:+.2f}  {sentence}")

print(analyzer.get_lexicon_stats())
```

**Tuning tips.** Widen `negation_window` for verbose MSA ("ليس من المستغرب
أن يكون الأمر جيداً"), narrow it for terse social posts. Raise
`neutral_threshold` (e.g. 0.1) if borderline texts get mislabeled. Note that
the lexicons match exact surface forms after diacritic/hamza normalization —
inflected variants (ممتازة vs ممتاز) or proclitic-attached forms (ونجاح)
may not match, so near-balanced texts yield low-magnitude scores. Run a
normalization pass first if you need wider coverage.

### 4.2 EmotionAnalyzer — eight Plutchik-style buckets

Where sentiment collapses everything onto one axis, `EmotionAnalyzer` answers
*which* emotion: **joy, sadness, anger, fear, surprise, disgust, trust,
hope**. The dominant emotion is the bucket with the most matches; ties break
in lexical order; empty text returns `"neutral"` with a zeroed distribution.

```python
from aranorm.analysis import EmotionAnalyzer, EmotionCounts, analyze_emotions
```

**Constructor:** `EmotionAnalyzer()` — no options.

**Methods:** `analyze(text) -> EmotionAnalysisResult`,
`analyze_batch(texts)`, shortcut `analyze_emotions(text)`.

**`EmotionAnalysisResult` fields:** `text`, `dominant_emotion` (bucket name
or `"neutral"`), `counts` — an `EmotionCounts` with one integer per bucket
(`joy`, `sadness`, `anger`, `fear`, `surprise`, `disgust`, `trust`, `hope`)
plus `total()` — `matched_words` (`{bucket: [words]}`), and the `confidence`
**property** (dominant bucket's share of all matches). `to_dict()` /
`to_json()` available.

```python
from aranorm.analysis import analyze_emotions

result = analyze_emotions("حضرت فرحة كبيرة ونجاح رائع")
print(result.dominant_emotion)   # 'joy'
print(result.confidence)         # dominant bucket's share of all matches
print(result.matched_words["joy"])

mixed = analyze_emotions("فرحة عارمة ثم خوف شديد")
print(mixed.counts.joy, mixed.counts.fear)   # 1 1
print(mixed.counts.total())
```

---

## 5. Content extraction

### 5.1 KeywordExtractor — TF and TF-IDF keywords

Scores content words (stop words removed) by term frequency with a length
bonus — or by true **TF-IDF** when you supply a reference corpus.

```python
from aranorm.analysis import KeywordExtractor
```

**Constructor:** `KeywordExtractor(config=None, registry=None, top_n=10,
min_freq=1, min_word_length=3, reference_corpus=None)` — `reference_corpus`
(a list of texts) switches the scorer from TF to TF-IDF.

**Methods:** `extract(text) -> KeywordResult`, `extract_batch(texts)`, and
`extract_common_keywords(texts, min_text_occurrences=2)` — `(word, count)`
pairs for keywords appearing in at least N texts.

**`KeywordResult` fields:** `original_text`, `keywords`
(`[(word, score)]` sorted by score), `top_keywords` (words only),
`keyword_count`, `content_word_count`, `stop_word_count`, `coverage_ratio`
(keywords / total words).

```python
from aranorm.analysis import KeywordExtractor

extractor = KeywordExtractor(top_n=5)
result = extractor.extract(
    "الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات، والاقتصاد الرقمي يتصدر التحولات"
)
print(result.top_keywords)
for word, score in result.keywords:
    print(f"{word:12} {score:.4f}")

# TF-IDF: penalize words common across a reference corpus
background = [
    "قال المسؤول إن الحكومة تدرس الخطة",
    "أعلنت الحكومة عن خطة تنموية جديدة",
    "درس المجلس الخطة ووافق عليها",
]
tfidf = KeywordExtractor(top_n=5, reference_corpus=background)
print(tfidf.extract("أعلنت الحكومة عن خطة اقتصادية").top_keywords)

# Across documents: which keywords keep coming back?
docs = ["الذكاء الاصطناعي يغير الصناعة", "تطبيقات الذكاء الاصطناعي في الطب"]
print(extractor.extract_common_keywords(docs, min_text_occurrences=2))
```

### 5.2 ArabicTextSummarizer — extractive TF-IDF summarization

Selects the most salient sentences using TF-IDF sentence scoring with a
**position bonus**: sentences in the first ~20% of the document get a
`position_weight` boost, mirroring Arabic journalistic conventions.

```python
from aranorm.analysis import ArabicTextSummarizer
```

**Constructor:** `ArabicTextSummarizer(ratio=0.3, max_sentences=None,
min_sentences=1, position_weight=1.2)` — `max_sentences` takes priority over
`ratio` when set; `min_sentences` is the floor for very short documents.

**Methods:** `summarize(text) -> SummaryResult`, `summarize_batch(texts)`.

**`SummaryResult` fields:** `original_text` (first 200 chars),
`summary_text`, `summary_sentences` (extracted sentences in document order),
`sentence_scores` (`{sentence: score}` for all candidates),
`original_sentence_count`, `summary_sentence_count`, `compression_ratio`
(summary words / original words), `top_keywords` (words that drove the
selection). `to_dict()` / `from_dict()` available.

```python
from aranorm.analysis import ArabicTextSummarizer

article = (
    "أعلن الرئيس عن خطة اقتصادية شاملة تستهدف تطوير البنية التحتية. "
    "وتشمل الخطة الاستثمار في قطاعات التعليم والصحة والتكنولوجيا. "
    "وقال المسؤولون إن الإصلاحات ستساهم في تعزيز النمو الاقتصادي. "
    "يذكر أن الخطة واجهت انتقادات من بعض الخبراء الاقتصاديين. "
    "وتبدأ الحكومة تنفيذ المرحلة الأولى مطلع العام القادم."
)

result = ArabicTextSummarizer(max_sentences=2).summarize(article)
print(result.summary_text)
print(f"{result.summary_sentence_count}/{result.original_sentence_count} sentences, "
      f"compression {result.compression_ratio:.0%}")
print("driven by:", result.top_keywords)
```

### 5.3 EntityAnalyzer — rule-based NER with offsets

Detects six entity classes with character offsets — no models, no
downloads: `person` (title markers like السيد and الدكتور, plus frequent
names), `location` (built-in dictionary plus geo-prefixes like مدينة and
جبل), `organization` (ministries, universities, companies), `money`
(amounts with currency words), `date` (Gregorian and Hijri), and `phone`
(international and national patterns).

```python
from aranorm.analysis import EntityAnalyzer
```

**Constructor:** `EntityAnalyzer(detect_types=None, name_threshold=1,
location_override=None, organization_override=None)` — restrict to a subset
of the six types, or extend the location/organization dictionaries.

**Methods:** `analyze(text) -> EntityAnalysisResult`, `analyze_batch(texts)`.

**`EntityAnalysisResult` fields:** `original_text`, `entities` — each an
`EntitySpan(text, start, end, entity_type, confidence)`; use the offsets to
highlight or redact — `by_type`, `entity_count`, `person_count`,
`location_count`, `organization_count`, `money_count`, `date_count`,
`phone_count`, `coverage_ratio` (entity words / total words).
`to_dict()` / `to_json()` available.

```python
from aranorm.analysis import EntityAnalyzer

analyzer = EntityAnalyzer()
result = analyzer.analyze(
    "قال الدكتور أحمد حسن إن شركة أرامكو ستستثمر 5 مليارات ريال في الرياض عام 2025."
)
print(result.entity_count)
for entity in result.entities:
    print(f"{entity.entity_type:12} {entity.text!r} [{entity.start}:{entity.end}]")
print(result.person_count, result.location_count, result.money_count)

# Restrict detection, extend the dictionary
only_places = EntityAnalyzer(detect_types=["location"])
custom = EntityAnalyzer(location_override=["الخرطوم", "تونس العاصمة"])
```

### 5.4 TopicClassifier — lexicon-based topic tagging

Scores text against **13 seeded topic lexicons**: `news`, `social`, `legal`,
`medical`, `religious`, `sport`, `technology`, `economy`, `education`,
`history`, `environment`, `culture`, `community`. Confidence is the
normalized gap between the best and runner-up scores — decisive texts yield
high confidence, ambiguous ones low confidence.

```python
from aranorm.analysis import TopicClassifier
```

**Constructor:** `TopicClassifier(topics=None, min_word_length=3)` — restrict
to a subset of the 13 built-ins; words shorter than `min_word_length` never
count as evidence.

**Methods:** `classify(text) -> TopicClassificationResult`,
`classify_batch(texts)`, `distribution(texts)` (topic → document count),
`add_terms(topic, terms)` (extend a lexicon at runtime).

**`TopicClassificationResult` fields:** `original_text`, `primary_topic`,
`primary_score`, `confidence`, `scores` — each a `TopicScore(topic, score,
matched_terms, coverage)` — `top_topics` (top-3 names), `word_count`,
`topic_word_count`. `to_dict()` / `to_json()` available.

```python
from aranorm.analysis import TopicClassifier

classifier = TopicClassifier()
result = classifier.classify("المحامي حضر جلسة المحكمة بعد الاطلاع على القانون")
print(result.primary_topic)   # 'legal'
print(result.confidence)

for topic_score in result.scores[:3]:
    print(f"{topic_score.topic:12} {topic_score.score:.2f}  matched: {topic_score.matched_terms}")

# Adapt to your domain, then profile a corpus
classifier.add_terms("medical", ["الأشعة المقطعية", "الجراحة الدقيقة"])
docs = ["فاز المنتخب بالمباراة", "ارتفعت أسعار النفط", "صدور أحكام قضائية جديدة"]
print(classifier.distribution(docs))
```

### 5.5 NumericAnalyzer — digits, currencies, dates, ordinals

Finds every numeric expression and classifies it — including the classic
Arabic data-cleaning trap: **mixed digit systems** (Western `123` vs
Arabic-Indic `١٢٣` in the same document).

```python
from aranorm.analysis.numeric_analyzer import NumericAnalyzer, analyze_numeric
```

**Constructor:** `NumericAnalyzer()` — no options.

**Methods:** `analyze(text) -> NumericResult`, `analyze_batch(texts)`,
shortcut `analyze_numeric(text)`.

**`NumericResult` fields:** `digit_system_mix` (`True` when both digit
systems appear), `western_count`, `arabic_indic_count`, `written_count`
(spelled-out numbers), `percentage_count`, `currency_count`, `time_count`,
`ordinal_count`, `numeric_density` (numeric tokens / words), `spans` — each
a `NumericSpan(text, category, start, end)` — `word_count`, `traces`.
`to_dict()` available.

```python
from aranorm.analysis.numeric_analyzer import analyze_numeric

result = analyze_numeric(
    "بلغت الأرباح 1.5 مليون دولار أي ٢٥٪ من الإيرادات، ويعمل بالشركة 300 موظف منذ 2010."
)
print(result.digit_system_mix)   # True → a normalization candidate
print(result.currency_count, result.percentage_count)

for span in result.spans:
    print(f"{span.category:12} {span.text!r}")
```

Pair this with the digits normalizer when `digit_system_mix` is `True` — see
[processors.md](processors.md).

---

## 6. Comparison & diff

### 6.1 TextComparator — multi-dimensional similarity

Compares two texts across **four similarity dimensions** — whole-text Jaccard
and cosine, plus the same two metrics on content words only (stop words
excluded) — folded into one `overall_similarity`
(`0.50 × content_cosine + 0.30 × content_jaccard + 0.20 × jaccard`) with a
verbal verdict.

```python
from aranorm.analysis import TextComparator
```

**Constructor:** `TextComparator(config=None, registry=None)` — control what
counts as a stop word via `StopWordsConfig`.

**Methods:** `compare(text_a, text_b) -> SimilarityResult`,
`compare_batch(pairs)`, `rank_by_similarity(query, candidates, top_n=None)`
(search-style ranking), `find_duplicates(texts, threshold=0.8)`.

**`SimilarityResult` fields:** `text_a`, `text_b`, `jaccard_similarity`,
`cosine_similarity`, `content_jaccard`, `content_cosine`,
`stop_word_overlap`, `shared_stop_words`, `shared_tokens`,
`shared_content_words`, `unique_to_a`, `unique_to_b`,
`overall_similarity`, `verdict`, `token_count_a`/`token_count_b`,
`content_word_count_a`/`content_word_count_b`. `to_dict()` available.

```python
from aranorm.analysis import TextComparator

comparator = TextComparator()
result = comparator.compare(
    "أنا أحب اللغة العربية وأدرسها كل يوم",
    "أنا أعشق اللغة العربية وأتعلمها باستمرار",
)
print(f"{result.overall_similarity:.2f} — {result.verdict}")
print("shared content:", sorted(result.shared_content_words))
print("unique to A:", sorted(result.unique_to_a))

# Ranking: which candidate best matches a query?
query = "خطة التنمية الاقتصادية"
candidates = [
    "الخطة الاقتصادية الجديدة",
    "مباراة كرة قدم ممتعة",
    "التنمية الاقتصادية في الخطة",
]
for text, similarity in comparator.rank_by_similarity(query, candidates, top_n=2):
    print(f"{similarity.overall_similarity:.2f}  {text}")

# Deduplication
dupes = comparator.find_duplicates(
    ["نص متطابق تماماً", "نص متطابق تماماً", "نص مختلف"], threshold=0.8
)
```

### 6.2 TextSimilarityMatrix — all-pairs similarity

Runs `TextComparator` over every pair in a collection and returns the full
similarity matrix with the closest pairs ranked.

```python
from aranorm.analysis import TextSimilarityMatrix
```

**Constructor:** `TextSimilarityMatrix(comparator=None,
score_key='overall_similarity')` — `score_key` may be any similarity field
(`jaccard_similarity`, `cosine_similarity`, `content_jaccard`,
`content_cosine`, …).

**Method:** `analyze(texts) -> SimilarityMatrixResult`.

**`SimilarityMatrixResult` fields:** `text_count`, `pair_count`, `matrix`
(`n × n` list of lists, 1.0 on the diagonal), `pairs` — every
`ClosestPair(index_a, index_b, similarity, verdict, result)` — `closest`
(sorted by similarity, descending), `duplicate_pairs` (similarity ≥ 1.0).
The result itself offers `find_closest_pairs(threshold=0.8, top_n=None)`.

```python
from aranorm.analysis import TextSimilarityMatrix

result = TextSimilarityMatrix().analyze([
    "أعلنت الوزارة عن خطة إسكانية جديدة",
    "الخطة الإسكانية أعلنت عنها الوزارة",
    "فاز الفريق بالبطولة بعد مباراة قوية",
])

print(result.matrix)
for pair in result.closest:
    print(f"({pair.index_a}, {pair.index_b}) → {pair.similarity:.2f} [{pair.verdict}]")

near = result.find_closest_pairs(threshold=0.3, top_n=2)
print(f"{len(near)} pair(s) above 0.3")
```

### 6.3 TextDiffReport — token-level diff

A `difflib`-powered token diff between two texts — designed primarily for
**auditing normalization**: pass the original text and a
`NormalizationResult` and see exactly what the pipeline changed.

```python
from aranorm.analysis import TextDiffReport
```

**Constructor:** `TextDiffReport()` — no options.

**Methods:** `diff(source, target) -> TextDiffResult`, and the classmethod
`from_normalization(source, result)` where `result` is a
`NormalizationResult` from a pipeline.

**`TextDiffResult` fields:** `source`, `target`, `tokens_source`,
`tokens_target`, `diff` — each a `DiffToken(op, before, after)` with `op` ∈
`equal | insert | delete | replace` — `similarity_ratio` (0–1),
`inserted_count`, `deleted_count`, `changed_count`, `unchanged_count`, plus
the `is_identical` property (`True` when both texts tokenize to the same
sequence). `to_dict()` / `to_json()` available.

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.analysis import TextDiffReport

report = TextDiffReport()
result = report.diff("الاله الجديده تعمل بشكل ممتاز", "الآلة الجديدة تعمل بشكل ممتاز")
print(f"similarity {result.similarity_ratio:.2f}, changed {result.changed_count}")
for token in result.diff:
    if token.op != "equal":
        print(f"{token.op:8} {token.before} → {token.after}")

# The normalization-audit form
pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
original = "مسئول الاعلان سيتولى المهام"
audit = TextDiffReport.from_normalization(original, pipeline.process(original))
print(audit.is_identical, audit.changed_count)
```

---

## 7. Corpus analysis

### 7.1 CorpusAnalyzer — aggregate stop-word/content-word statistics

Aggregates the per-text stop-word analysis across a whole corpus:
frequencies, document frequencies, per-document stats, and vocabulary
diversity.

```python
from aranorm.analysis import CorpusAnalyzer
```

**Constructor:** `CorpusAnalyzer(config=None, registry=None, top_n=20)`.

**Methods:**

| Method | Returns |
|---|---|
| `analyze(texts)` | `CorpusAnalysisResult` — full corpus statistics |
| `overlap_analysis(texts)` | `OverlapAnalysisResult` — pairwise overlap + distinctiveness |
| `compare(corpus_a, corpus_b)` | `dict` — stop-word profile comparison of two corpora |

**`CorpusAnalysisResult` fields:** `document_count`, `total_tokens`,
`total_stop_words`, `total_content_words`, `corpus_stop_word_ratio`,
`stop_word_frequency`, `content_word_frequency`, `document_frequency`
(word → number of documents containing it), `top_stop_words`,
`top_content_words`, `documents` (per-text `DocumentStats`),
`stop_word_vocabulary_size`, `content_word_vocabulary_size`,
`average_stop_word_ratio`, `lexical_diversity`.

**`OverlapAnalysisResult` fields:** `document_count`, `overlap_matrix`
(`{"i-j": score}`), `most_similar_pair` / `least_similar_pair`
(`(i, j, score)`), `average_similarity`, `distinctiveness` — per-document
`DocumentDistinctiveness(index, only_in_this_document, shared_vocabulary,
distinctiveness)`.

```python
from aranorm.analysis import CorpusAnalyzer

corpus = [
    "أعلنت الوزارة عن نتائج الامتحانات اليوم",
    "أعلنت الشركة عن نتائج الأعمال الربعية",
    "ناقش المجلس نتائج اللجنة أمس",
]

analyzer = CorpusAnalyzer(top_n=5)
result = analyzer.analyze(corpus)
print(result.document_count, result.total_tokens)
print("top content words:", result.top_content_words)
print("corpus lexical diversity:", result.lexical_diversity)

overlap = analyzer.overlap_analysis(corpus)
print("most similar pair:", overlap.most_similar_pair)
for doc in overlap.distinctiveness:
    print(f"doc {doc.index}: distinctiveness {doc.distinctiveness:.2f}, "
          f"unique words: {doc.only_in_this_document}")

comparison = analyzer.compare(corpus[:2], corpus[2:])
print("shared stop words:", comparison["shared_stop_words"])
```

### 7.2 CorpusStopWordsBuilder — learn domain stop words

Not every frequent word is in the universal list. `CorpusStopWordsBuilder`
mines your corpus for high-document-frequency, low-information words and
proposes them as **domain stop words**.

```python
from aranorm.analysis import CorpusStopWordsBuilder
```

**Constructor:** `CorpusStopWordsBuilder(min_doc_frequency=2,
max_doc_frequency_ratio=0.85, min_word_length=2, top_n=100,
exclude_known_stop_words=False, registry=None)` — a word must appear in at
least `min_doc_frequency` documents but no more than `max_doc_frequency_ratio`
of them; `exclude_known_stop_words` skips words already in the universal
list.

**Method:** `build(texts) -> CorpusStopWordsResult` with
`extracted_stop_words` (a `frozenset`), `candidate_scores`
(`(word, score)` sorted descending), `corpus_size`, `vocabulary_size`,
`threshold_used`.

```python
from aranorm.analysis import CorpusStopWordsBuilder

corpus = [
    "أعلنت الوزارة عن نتائج الامتحانات اليوم",
    "أعلنت الشركة عن نتائج الأعمال الربعية",
    "ناقش المجلس نتائج اللجنة أمس",
]

builder = CorpusStopWordsBuilder(min_doc_frequency=3, top_n=25)
result = builder.build(corpus + corpus)   # doubled so words reach doc-frequency 3

print(len(result.extracted_stop_words), "proposed domain stop words")
for word, score in result.candidate_scores[:5]:
    print(f"{word:12} {score:.3f}")
```

Feed the resulting set into `StopWordsConfig` custom lists — see
[stopwords.md](stopwords.md).

### 7.3 BatchAnalyzer — the one-call corpus report

The executive summary. Runs language detection, dialect profiling, quality
scoring, spelling analysis, and corpus statistics over a collection and fuses
everything into one report with recommendations.

```python
from aranorm.analysis.batch_analysis import BatchAnalyzer, analyze_batch
```

**Constructor:** `BatchAnalyzer()` — no options.

**Method:** `analyze(texts) -> BatchAnalysisReport` (shortcut:
`analyze_batch(texts)`).

**`BatchAnalysisReport` fields:**

| Field | Meaning |
|---|---|
| `texts_count` / `total_tokens` / `total_chars` | Corpus size |
| `avg_quality_score` | Mean composite quality (0–100) |
| `quality_distribution` | `QualityDistribution(excellent, good, fair, poor)` counts |
| `language_distribution` | e.g. `{"arabic": 8, "mixed": 2, "latin": 1}` |
| `dialect_distribution` | e.g. `{"MSA": 5, "GLF": 3}` |
| `avg_readability` | Mean readability component |
| `spelling_issues_total` | All spelling corrections applied |
| `unique_words` | Union vocabulary size |
| `top_issues` | Most frequent corrections corpus-wide |
| `recommendations` | Actionable corpus-level advice |
| `corpus_lexical_diversity` | Unique / total words |

`to_dict()`, `to_json()`, `summary()` available.

```python
from aranorm.analysis.batch_analysis import BatchAnalyzer

texts = [
    "أعلنت الشركة عن أرباح قياسية هذا الربع بفضل نمو المبيعات.",
    "شو هالزحمة بالشارع اليوم، مو معقول!",
    "شكرا جزيلا على المجهود الرائع، ما شاء الله",
]

report = BatchAnalyzer().analyze(texts)
print(report.summary())
print("quality:", report.quality_distribution.to_dict())
print("dialects:", report.dialect_distribution)
print("languages:", report.language_distribution)

for issue in report.top_issues:
    print(f"  {issue['correction']} ×{issue['count']}")
for recommendation in report.recommendations:
    print("→", recommendation)
```

---

## 8. Linguistic structure

### 8.1 PronounAnalyzer — clitic decomposition

Arabic packs prepositions, conjunctions, and pronouns onto words as clitics.
`PronounAnalyzer` decomposes **one token** into prefix / stem / suffix
segments by greedy longest-match in both directions, never collapsing the
stem below the configured minimum length.

```python
from aranorm.analysis import PronounAnalyzer
```

**Constructor:** `PronounAnalyzer(min_stem_length=2)`.

**Methods:** `analyze(token)` — note: a **single token**, not a text —
`analyze_tokens(tokens)`, and `pronoun_statistics(texts)` (aggregate dict:
`total_tokens`, `tokens_with_pronouns`, `pronoun_ratio`, `by_role`).

**`PronounAnalysisResult` fields:** `original_token`, `segments` — each a
`CliticSegment(text, role, grammar)` with `role` ∈ `prefix | stem | suffix`
and an Arabic grammatical label — `stem`, `prefixes`, `suffixes`,
`has_pronoun` (True when suffixes attached), `pronoun_role` (grammar of the
outermost suffix), plus `is_simple()`.

```python
from aranorm.analysis import PronounAnalyzer

analyzer = PronounAnalyzer()
result = analyzer.analyze("وكتابهم")

print(result.prefixes)     # ['و']
print(result.stem)         # 'كتاب'
print(result.suffixes)     # ['هم']
print(result.has_pronoun)  # True

for segment in result.segments:
    print(f"{segment.role:7} {segment.text:6} {segment.grammar}")

# Corpus-wide: how pronoun-heavy is the writing?
stats = analyzer.pronoun_statistics(["كتابهم كبير", "قرأت كتبهم الجديدة"])
print(stats["pronoun_ratio"], stats["by_role"])
```

### 8.2 IdiomAnalyzer — fixed expressions

Detects **35 built-in Arabic fixed expressions** together with their common
spelling variants — including variants a spelling checker would "correct" —
each tagged with a category (دعاء، توكيد، استدراك، زمن…). Span offsets let
downstream tools protect idioms from aggressive normalization.

```python
from aranorm.analysis import IdiomAnalyzer
```

**Constructor:** `IdiomAnalyzer(idioms=None)` — pass a custom
`{canonical: (category, [variants])}` dict to replace the built-ins.

**Methods:** `analyze(text) -> IdiomAnalysisResult`, `analyze_batch(texts)`,
`add_idiom(canonical, category, variants)` (register your own at runtime),
plus helpers `canonical_forms`, `is_idiom_covered(...)`, `idiom_words(text)`
(used by the spelling analyzer).

**`IdiomAnalysisResult` fields:** `original_text`, `idioms` — each an
`IdiomSpan(text, canonical, category, start, end)` — `idiom_count`,
`by_category`, `unique_idioms` (canonical forms). `to_dict()` / `to_json()`
available.

```python
from aranorm.analysis import IdiomAnalyzer

analyzer = IdiomAnalyzer()
result = analyzer.analyze("انشاء الله سنتقابل مرة أخرى على أي حال")

print(result.idiom_count)
for idiom in result.idioms:
    print(f"{idiom.text!r} → canonical {idiom.canonical!r} ({idiom.category})")

print(result.unique_idioms)
print(result.by_category.keys())

# Register a domain expression
analyzer.add_idiom("في حدود العلم", "تخصيص", ["في حدود علمي"])
```

**Why this matters for normalization:** `SpellingAnalyzer` excludes idiom
spans by default (`idiom_exclusion=True`) so that "انشاء الله" — a fixed
expression — is not flagged as a misspelling of "إن شاء الله".

### 8.3 CoherenceAnalyzer — four-axis text coherence

Scores how *coherent* a text reads (0.0–1.0) along four weighted axes:

| Axis | Weight | Signal |
|---|---|---|
| `lexical_repeat` | 0.35 | Adjacent sentences sharing content vocabulary (topic chains) |
| `connectors` | 0.25 | Discourse connectives (ثم، لذلك، بالإضافة…) per content word |
| `topic_consistency` | 0.25 | Content words recurring across sentences |
| `sentence_balance` | 0.15 | 1 − normalized sentence-length spread |

```python
from aranorm.analysis import CoherenceAnalyzer, analyze_coherence
```

**Constructor:** `CoherenceAnalyzer(weights=None)` — override the axis
weights with a `dict` (e.g. poetry: balance matters more).

**Method:** `analyze(text) -> CoherenceScore` (shortcut:
`analyze_coherence(text)`).

**`CoherenceScore` fields:** `text`, `score` (0–1), `label` (`strong` ≥ 0.7,
`moderate` ≥ 0.5, `weak` ≥ 0.3, else `fragmented`), `sentence_count`,
`content_word_count`, `breakdown` — each a `CoherenceBreakdown(axis, value,
weight, contribution)` — `connective_count`, and `axes` (flat
`{axis: value}` dict). `to_dict()` / `to_json()` / `summary()` available.

```python
from aranorm.analysis import analyze_coherence

coherent = analyze_coherence(
    "افتتح الاجتماع رئيس اللجنة التحضيرية. ثم ناقش الاجتماع تقرير اللجنة المالي. "
    "لذلك اعتمد الاجتماع توصيات اللجنة النهائية."
)
fragmented = analyze_coherence("الجو جميل. اشتريت سيارة. الرياضة مفيدة.")

print(coherent.label)      # 'moderate' — chained vocabulary + connectors
print(coherent.connective_count)
for part in coherent.breakdown:
    print(f"{part.axis:18} value={part.value:.2f} × weight={part.weight} = {part.contribution:.2f}")
print(fragmented.label)    # 'fragmented'
```

---

## 9. Style & register

### 9.1 StyleAnalyzer — formal / colloquial / digital register

Computes a signed `style_index`: formal markers push it up; colloquial
markers and digital signals (emoji, elongations, chat slang) push it down.
The label is read off the index.

```python
from aranorm.analysis import StyleAnalyzer, analyze_style
```

**Constructor:** `StyleAnalyzer(formal_weight=0.45,
colloquial_weight=0.40, digital_weight=0.35)` — the three signal weights.

**Methods:** `analyze(text) -> StyleAnalysisResult`, `analyze_batch(texts)`,
shortcut `analyze_style(text)`.

**`StyleAnalysisResult` fields:** `text`, `style_index` (positive → formal),
`label` ∈ `formal` | `semi_formal` | `mixed` | `digital` | `informal`,
`signals` — a `StyleSignals(formal_markers, colloquial_markers,
digital_signals)` of 0–1 densities — `formal_words`, `colloquial_words`
(the matched vocabulary), `elongations` (matched strings), `emoji_count`.
`to_dict()` / `to_json()` available.

```python
from aranorm.analysis import analyze_style

result = analyze_style("علاوة على ذلك فإن النتائج مؤكدة، حيثما نظرت، لذا كي نستنتج")
print(result.label)          # 'formal'
print(result.formal_words)

casual = analyze_style("يلا حبيبي شو الجديد 😍👍")
print(casual.label)          # 'informal'
print(casual.emoji_count, casual.elongations)
print(casual.signals.colloquial_markers)
```

### 9.2 LoanwordAnalyzer — Arabicised and Latin-script fragments

Detects Arabicised loanwords (تلفزيون، إنترنت، كمبيوتر…) and raw Latin
fragments, reporting counts and a combined `foreign_density`.

```python
from aranorm.analysis.loanword_analyzer import LoanwordAnalyzer, analyze_loanwords
```

**Constructor:** `LoanwordAnalyzer(loanword_label_threshold=0.1,
latin_label_threshold=0.05, mixed_label_threshold=0.15)` — ratio cutoffs for
the labels.

**Methods:** `analyze(text) -> LoanwordResult`, `analyze_batch(texts)`,
shortcut `analyze_loanwords(text)`.

**`LoanwordResult` fields:** `loanword_count`, `loanword_ratio`,
`latin_count`, `latin_ratio`, `foreign_density`, `spans` — each a
`LoanwordSpan(text, category, start, end)` — `samples` (the matched words),
`word_count`, `label` ∈ `mixed` | `loanwords` | `pure_arabic`.
`to_dict()` / `to_json()` available.

```python
from aranorm.analysis.loanword_analyzer import analyze_loanwords

result = analyze_loanwords("شاهدت المباراة في تلفزيون قديم ثم ركبت باص وفتحت الـ laptop")
print(result.loanword_count, result.latin_count)   # 2 1
print(result.label)                                # 'mixed'
print(result.samples)                              # ['تلفزيون', 'باص']
for span in result.spans:
    print(f"{span.category:10} {span.text!r}")
```

### 9.3 QuotationAnalyzer — direct speech and reporting environments

Finds quoted spans — «guillemets», straight/curly quotes — counts reporting
verbs (قال، ذكر، أكد…), and computes what fraction of the text lives inside
quotation.

```python
from aranorm.analysis.quotation_analyzer import QuotationAnalyzer, analyze_quotations
```

**Constructor:** `QuotationAnalyzer(quoted_label_threshold=0.5,
partially_quoted_label_threshold=0.1)` — ratio cutoffs for `quoted` and
`partially_quoted`.

**Methods:** `analyze(text) -> QuotationResult`, `analyze_batch(texts)`,
shortcut `analyze_quotations(text)`.

**`QuotationResult` fields:** `quotation_ratio` (quoted words / total),
`quotation_types` (`{category: count}`), `spans` — each a
`QuotationSpan(text, category, start, end)` — `partial_count` (unbalanced
quotes), `word_count`, `label` ∈ `quoted` | `partially_quoted` | `plain`.
`to_dict()` / `to_json()` available.

```python
from aranorm.analysis.quotation_analyzer import analyze_quotations

result = analyze_quotations(
    'قال المتحدث: «سنعلن عن النتائج قريباً»، وأضاف أن "التأخير غير مبرر".'
)
print(result.quotation_ratio)
print(result.quotation_types)
print(result.label)
for span in result.spans:
    print(f"{span.category:10} {span.text!r} [{span.start}:{span.end}]")
print("unbalanced:", result.partial_count)
```

---

## 10. Rhetorical analysis

The axis family: uniform analyzers for classical Arabic rhetoric (balāgha)
and modern style signals. **All of them share the same pattern:**

```python
from aranorm.analysis.<module> import <AnalyzerClass>, analyze_<axis>

analyzer = <AnalyzerClass>()              # thresholds in the constructor
result = analyzer.analyze(text)           # or analyze_<axis>(text) one-shot
results = analyzer.analyze_batch(texts)    # batch form on every analyzer
result.to_dict()                           # JSON-serializable
result.to_json()                           # ready to write to disk
```

Every result is a dataclass whose fields end with a human-readable `label`.
Import from the specific submodule (e.g.
`from aranorm.analysis.contrast_analyzer import ContrastAnalyzer,
analyze_contrast`) or run them all at once via `profile_text` (§11).

### 10.1 RhetoricalQuestionAnalyzer

Detects rhetorical questions: **inversion forms** (أليس، ألم، ألست…) that
assert rather than ask, **direct questions** with interrogative particles
(هل، ماذا، كيف…), and **rhetorical markers** (من ذا، بأي معنى، أفلا، وهل…).
`question_density` is per 100 words.

Constructor: `RhetoricalQuestionAnalyzer(rich_threshold=10.0,
moderate_threshold=3.0)` — density cutoffs. Result
`RhetoricalQuestionsResult` fields: `questions` — each a
`RhetoricalQuestion(text, question_type, start, end)` with `question_type` ∈
`inversion | direct | marker` — `inversion_questions`, `direct_questions`,
`rhetorical_markers`, `question_density`, `label` ∈ `interrogative-rich` |
`moderate` | `plain`.

```python
from aranorm.analysis.rhetorical_question_analyzer import analyze_rquestions

result = analyze_rquestions("أليس الوقت قد حان؟ أليست الحقيقة واضحة؟")
print(result.inversion_questions)   # 2
print(result.question_density)
print(result.label)                 # 'interrogative-rich'

for question in result.questions:
    print(f"{question.question_type:9} {question.text!r}")
```

### 10.2 AnaphoraAnalyzer

Measures reference density and cross-sentence cohesion: **attached pronouns**
(ـه، ـهم، ـها…), **independent pronouns** (هو، هم…), **demonstratives**
(هذا، تلك…), **relative references** (الذي، التي…), and **lexical
rementions** (content words repeated across sentences).

Constructor: `AnaphoraAnalyzer(dense_threshold=0.45,
moderate_threshold=0.15)`. Result `AnaphoraResult` fields:
`attached_pronouns`, `independent_pronouns`, `demonstratives`,
`relative_references` — each a list of `AnaphoraMention(text, mention_type,
start, end)` — `lexical_rementions`, `reference_density`, `cohesion_score`,
`word_count`, `sentence_count`, `label` ∈ `tightly-cohesive` | `moderate` |
`loose`. Count properties: `attached_pronoun_count`,
`independent_pronoun_count`, `demonstrative_count`,
`relative_reference_count`, `lexical_remention_count`, `mention_count`.

```python
from aranorm.analysis.anaphora_analyzer import analyze_anaphora

result = analyze_anaphora("كتب محمد رسالته، وأرسلها إلى صديقه الذي ساعده.")
print(result.reference_density)
print(result.label)
print(result.attached_pronoun_count, "attached pronouns")

for mention in result.relative_references:
    print(mention.mention_type, mention.text)
```

### 10.3 WordPlayAnalyzer — jinās and sajʿ

Detects **jinās** (paronomasia): word pairs differing by one letter
(`paronomasia_pairs`, similarity ≥ threshold) or identical in form
(`tamm_pairs`, perfect jinās), plus **sajʿ** (rhymed clause endings) and
**puns**.

Constructor: `WordPlayAnalyzer(similarity_threshold=0.8, saj_threshold=2)`.
Result `WordplayResult` fields: `mentions` — each a `WordplayMention(text,
kind, pair, start, end)` with `kind` ∈ `paronomasia | jinās_tām | saj | pun`
— `paronomasia_pairs`, `tamm_pairs`, `saj_lines`, `pun_words`,
`wordplay_density`, `word_count`, `label` ∈ `playful` | `moderate` |
`literal`.

```python
from aranorm.analysis.wordplay_analyzer import analyze_wordplay

result = analyze_wordplay("العلم يبني صاحبه، والعمل يرفع صاحبه")
print(result.label)                  # 'moderate'
print("perfect jinās:", result.tamm_pairs)   # [('العلم', 'والعمل')]
print("jinās pairs:", result.paronomasia_pairs)

for mention in result.mentions:
    print(f"{mention.kind:12} {mention.pair}")
```

### 10.4 ContrastAnalyzer — antonym pairs (ṭibāq / taḍād)

Detects opposition structure through a built-in lexicon of **158 antonym
pairs** (الليل/النهار، الحياة/الموت، الخير/الشر…). The classical figure
**ṭibāq** (antithesis) is contrast deployed deliberately.

Constructor: `ContrastAnalyzer(contrastive_threshold=0.05,
moderate_threshold=0.01)` — density cutoffs. Result `ContrastResult` fields:
`contrast_pairs` — each a `ContrastPair(member_a, member_b, second_start,
second_end, normalised_key)` — `contrast_density`, `unique_pairs`,
`word_count`, `label` ∈ `contrastive` | `moderate` | `neutral`. Also
`contrast_pairs_count()`.

```python
from aranorm.analysis.contrast_analyzer import analyze_contrast

result = analyze_contrast(
    "يأخذ الخير من الحياة ويرفض الشر، يفرح بالنهار ويتأمل الليل"
)
print(result.label)               # 'contrastive'
print(result.contrast_density)

for pair in result.contrast_pairs:
    print(f"{pair.member_a} ↔ {pair.member_b}")
```

### 10.5 FillerAnalyzer — filler phrases and repetition

Flags discourse fillers (في الحقيقة، بصراحة، جدير بالذكر، لا شك أن…) and
**immediate word repetition** (within a small window) — the two habits that
inflate text without adding content.

Constructor: `FillerAnalyzer(filler_threshold=0.10,
repetition_threshold=0.05, repetition_window=5)`. Result `FillerResult`
fields: `filler_spans` — each a `FillerSpan(text, start, end)` —
`repetition_spans` — each a `RepetitionSpan(word, first_start, second_start,
second_end)` — `filler_count`, `repetition_count`, `filler_density`,
`repetition_density`, `word_count`, `label` ∈ `filler_heavy` | `repetitive`
| `clean`.

```python
from aranorm.analysis.filler_analyzer import analyze_fillers

result = analyze_fillers("في الحقيقة الأمر صعب صعب جداً في الواقع")
print(result.label)               # 'filler_heavy'
print(result.filler_count, result.repetition_count)

for span in result.filler_spans:
    print("filler:", span.text)
for span in result.repetition_spans:
    print("repeated:", span.word)
```

### 10.6 RhythmAnalyzer — sajʿ, balance, and poetic line structure

Scores prosodic feel: **sajʿ pairs** (clause endings sharing a stem — weight
0.40), **parallel balance** between clause halves (0.25), **repetition
density** (0.20), and **poetic line ratio** (0.15).

Constructor: `RhythmAnalyzer(saj_weight=0.40, balance_weight=0.25,
repetition_weight=0.20, line_weight=0.15)`. Result `RhythmResult` fields:
`rhythm_index`, `label` ∈ `rhythmic` | `semi_rhythmic` | `flat`,
`saj_signals`, `saj_pairs` — each a `SajPair(clause_a, clause_b, shared_stem,
start, end)` — `parallel_balance`, `repetition_density`, `poetic_line_ratio`,
`sentence_count`, `word_count`, `traces`.

```python
from aranorm.analysis.rhythm_analyzer import analyze_rhythm

result = analyze_rhythm("فأما اليتيم فلا تقهر، وأما السائل فلا تنهر")
print(result.rhythm_index)         # e.g. 0.5
print(result.label)                # 'rhythmic'
for pair in result.saj_pairs:
    print(f"{pair.clause_a} ~ {pair.clause_b} (shared stem: {pair.shared_stem})")
```

### 10.7 FigurateAnalyzer — tashbīh, ṭibāq, tarāduf, takrīr

Detects four classical figures of speech: **tashbīh** (simile — بكى كالغيث)،
**ṭibāq** (antithesis), **tarāduf** (synonymy variation), and **takrīr**
(deliberate repetition for emphasis).

Constructor: `FigurateAnalyzer(simile_weight=0.35, tibaq_weight=0.35,
taraduf_weight=0.35, takrir_weight=0.35)`. Result `FigurativeResult` fields:
`figure_index`, `label` ∈ `rich` | `moderate` | `plain`, `figures` (figure
names found), `occurrences` — each a `FigureOccurrence(figure, words, start,
end)` — `simile_count`, `tibaq_count`, `taraduf_count`, `takrir_count`,
`takrir_words`, `word_count`, `traces`.

```python
from aranorm.analysis.figurate_analyzer import analyze_figurative

result = analyze_figurative("الطفل بكى كالغيث، والعلم نور والحياة ظلام لمن هجره")
print(result.figure_index)
print(result.label)               # 'moderate'
print(result.simile_count, result.tibaq_count)   # 1 1

for occurrence in result.occurrences:
    print(f"{occurrence.figure:8} {occurrence.words}")
```

### 10.8 RootDensityAnalyzer — trilateral-root derivation density

Extracts the trilateral root of each content word (via AraNorm's root
extractor) and profiles how vocabulary distributes over roots: distinct root
count, hapax share, the dominant root, and a diversity index.

Constructor: `RootDensityAnalyzer(root_diversity_threshold=0.6,
root_sparse_threshold=0.3, minimum_words=3)` — texts shorter than
`minimum_words` words are skipped. Result `RootDensityResult` fields:
`root_count` (root tokens), `unique_roots`, `hapax_ratio` (roots seen once),
`top_root` (dominant root as a dict), `diversity_index`, `label` ∈
`root_rich` | `moderate` | `sparse`.

```python
from aranorm.analysis.root_density_analyzer import analyze_root_density

result = analyze_root_density("الكاتب كتب كتاباً عن الكتابة، والقارئ يقرأ قراءة متأنية")
print(result.unique_roots)
print(result.top_root)
print(result.label)
# Classical texts cluster on few roots (low diversity); technical prose spreads out.
```

---

## 11. The unified profiler

`AnalysisProfiler` runs **22 analysis axes in a single pass** and returns one
consolidated payload plus *cross-signal insights* — short notes connecting
signals from different analyzers (e.g. a coherent text carrying a negative
tone).

**The 22 default axes**

| Group | Axes |
|---|---|
| Tone | `sentiment`, `emotions` |
| Structure | `coherence`, `readability`, `complexity`, `rquestions`, `anaphora` |
| Quality | `quality`, `fillers` |
| Vocabulary | `word_frequency`, `root_density`, `loanwords` |
| Style | `style`, `dialect`, `quotation`, `wordplay` |
| Rhetoric | `rhythm`, `figurate`, `contrast` |
| Content | `topics`, `entities`, `numeric` |

```python
from aranorm.analysis import AnalysisProfiler, profile_text
```

**Constructor:** `AnalysisProfiler(axes=None, topic_fields=None)` — `axes`
limits the run to a subset (default: all 22); `topic_fields` restricts the
topics axis to specific topics.

**Methods:** `profile(text) -> ProfilerResult`, `profile_batch(texts)`,
shortcut `profile_text(text)`.

**`ProfilerResult` fields:** `text`, `axes` (`{axis_name: dict}` — each
value is the underlying result's `to_dict()`), `insights` — each a
`ProfilerInsight(rule, message)`. `to_dict()` / `to_json()` available.

```python
from aranorm.analysis import profile_text

result = profile_text("أليس العلم نوراً يهدي العقول؟ نعم، والجهل ظلام يعمي البصائر.")

# Every axis, as a plain dict
print(result.axes["sentiment"]["label"])
print(result.axes["rquestions"]["label"])
print(result.axes["contrast"]["label"])
print(result.axes["coherence"]["score"])

# Cross-signal insights
for insight in result.insights:
    print(f"[{insight.rule}] {insight.message}")
```

```python
from aranorm.analysis import AnalysisProfiler

# Only the axes you need — faster, smaller payload; restrict topics too
profiler = AnalysisProfiler(axes=["sentiment", "quality", "topics"],
                            topic_fields=["legal", "news"])
result = profiler.profile("خدمة العملاء ممتازة والأسعار مناسبة")
print(result.axes["quality"]["score"])
```

**Profiler vs. individual analyzers.** Use the profiler when you need many
signals at once (dashboards, corpus triage, writing assistants) — it avoids
redundant tokenization and adds cross-signal insights for free. Use
individual analyzers when you need richly-typed results (dataclass objects,
not dicts), custom thresholds, or maximum speed on a single axis.

---

## 12. Choosing the right analyzer

| Use case | Start with | Also consider |
|---|---|---|
| "Is this text any good?" | `QualityScoreAnalyzer` | `SpellingAnalyzer` (detail), `BatchAnalyzer` (corpus) |
| User feedback / review polarity | `SentimentAnalyzer` | `EmotionAnalyzer` (which feeling) |
| Tag support tickets | `TopicClassifier` | `KeywordExtractor` (free-form tags) |
| Deduplicate a dataset | `TextComparator.find_duplicates` | `TextSimilarityMatrix` (all pairs) |
| Audit what normalization changed | `TextDiffReport.from_normalization` | `ArabicReadabilityAnalyzer` (before/after) |
| Summarize long articles | `ArabicTextSummarizer` | `KeywordExtractor` (tags for the summary) |
| Extract names/places/money/dates | `EntityAnalyzer` | `NumericAnalyzer` (numeric detail) |
| Find domain stop words | `CorpusStopWordsBuilder` | `CorpusAnalyzer` (general corpus stats) |
| Corpus health report | `BatchAnalyzer` | `CorpusAnalyzer.overlap_analysis` |
| Chat-speak vs formal detection | `StyleAnalyzer` | `LoanwordAnalyzer`, `TextAnalyzer.dialect_hint` |
| Is this text coherent? | `CoherenceAnalyzer` | `AnaphoraAnalyzer` (reference detail) |
| Literariness / rhetoric scoring | `FigurateAnalyzer` + `RhythmAnalyzer` | `WordPlayAnalyzer`, `ContrastAnalyzer` |
| Editing assistance (trim the fluff) | `FillerAnalyzer` | `ComplexityAnalyzer`, `WordFrequencyProfiler` |
| Prepare text for ML features | `WordFrequencyProfiler` | `TextAnalyzer`, `PronounAnalyzer` |
| One-shot full picture | `AnalysisProfiler` / `profile_text` | — |

**Performance notes.** All analyzers are pure-Python and dependency-free;
most operate in a single pass over tokens. For large corpora, reuse one
analyzer instance across texts (they are stateless per call), share a
`StopWordsRegistry` between stop-word-aware analyzers, and prefer
`AnalysisProfiler` when you need most axes at once.

---

## 13. CLI equivalents

Most analyzers are exposed as CLI subcommands of `aranorm`, taking text or a
file and printing a formatted report (add `--json` for machine output). The
[CLI reference](cli.md) documents every flag; the mapping:

| Python analyzer | CLI command |
|---|---|
| `QualityScoreAnalyzer` / `analyze_quality` | `aranorm quality` |
| `SpellingAnalyzer` / `analyze_spelling` | `aranorm spelling` |
| `SentimentAnalyzer` | `aranorm sentiment` |
| `EmotionAnalyzer` / `analyze_emotions` | `aranorm emotions` |
| `KeywordExtractor` | `aranorm keywords` |
| `ArabicTextSummarizer` | `aranorm summarize` |
| `EntityAnalyzer` | `aranorm entities` |
| `TopicClassifier` | `aranorm topics` |
| `NumericAnalyzer` / `analyze_numeric` | `aranorm numbers` |
| `CoherenceAnalyzer` / `analyze_coherence` | `aranorm coherence` |
| `StyleAnalyzer` / `analyze_style` | `aranorm style` |
| `RhythmAnalyzer` / `analyze_rhythm` | `aranorm rhythm` |
| `FigurateAnalyzer` / `analyze_figurative` | `aranorm figurate` |
| `QuotationAnalyzer` / `analyze_quotations` | `aranorm quotation` |
| `LoanwordAnalyzer` / `analyze_loanwords` | `aranorm loans` |
| `RootDensityAnalyzer` / `analyze_root_density` | `aranorm roots` |
| `ContrastAnalyzer` / `analyze_contrast` | `aranorm contrast` |
| `FillerAnalyzer` / `analyze_fillers` | `aranorm fillers` |
| `ComplexityAnalyzer` / `analyze_complexity` | `aranorm complexity` |
| `RhetoricalQuestionAnalyzer` / `analyze_rquestions` | `aranorm rquestions` |
| `AnaphoraAnalyzer` / `analyze_anaphora` | `aranorm anaphora` |
| `AnalysisProfiler` / `profile_text` | `aranorm textprofile` |
| `WordFrequencyProfiler` | `aranorm freqprofile` |
| `BatchAnalyzer` / `analyze_batch` | `aranorm profile` |

Related commands: `aranorm analyze` (text statistics),
`aranorm readability`, `aranorm corpus` (corpus statistics),
`aranorm compare` (similarity), `aranorm dialect`, `aranorm pronouns`,
`aranorm idioms`, `aranorm detect`.

```bash
# Quality score of a file, as JSON
aranorm quality --file article.txt --json

# Sentiment of a string
aranorm sentiment "الخدمة ممتازة والأسعار مناسبة"

# Full 22-axis profile
aranorm textprofile --file essay.txt

# Corpus-level batch report
aranorm profile --file corpus.jsonl
```

---

## 14. Where to go next

- [Getting started](getting-started.md) — install and first pipeline
- [Configuration](configuration.md) — every `PipelineConfig` field
- [Presets & processors](processors.md) — the 48 normalization processors
- [Stop words](stopwords.md) — modes, scopes, dialects, and domain lists
- [CLI reference](cli.md) — all 43 commands and their flags
- [Integrations](integrations.md) — pandas, scikit-learn, spaCy, NLTK, HF
- [API reference](api.md) — the complete programmatic surface
- [Architecture](architecture.md) — stages, registry, contracts
- [Performance](performance.md) — throughput numbers and practices

Happy analyzing — تحليلاً موفقاً!
