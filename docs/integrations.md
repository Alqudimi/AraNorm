# Integrations & Optional ML Models — The Complete Guide

**AraNorm v1.15.0** · zero-mandatory-dependency core · every integration is opt-in

AraNorm's core — the pipeline, 40+ processors, the stop-words engine, 45+ analyzers, the CLI, and the HTTP server — runs on the **Python standard library alone** (`dependencies = []` in `pyproject.toml`). Third-party libraries are never imported at package load time. Every integration lives behind a thin, lazy adapter that only touches the third-party import **at the moment you actually use it**. Three practical consequences:

1. **`import aranorm` never fails** because of a missing optional package, and cold starts never pay for pandas, torch, or spaCy.
2. **Nothing is silently degraded.** Request a capability whose library is missing and AraNorm raises one specific exception — `IntegrationUnavailableError` — whose message names the exact `pip` command to run.
3. **Mixing is safe.** Ship one code path on the dependency-free heuristic engine and another that upgrades to a neural model when the `[ml]` extra happens to be installed (see [§9](#9-error-handling-a-reusable-recipe)).

This guide covers the five library integrations (scikit-learn, pandas, spaCy, NLTK, HuggingFace `datasets`), the neural models (`[ml]` extra), the CAMeL Tools integration (`[camel]` extra), the processor plugin system, and the error-handling pattern that ties it all together. Prose is in English; all example data is real Arabic; output comments were captured by running each example against AraNorm 1.15.0.

---

## Table of Contents

1. [Quick decision table](#1-quick-decision-table)
2. [scikit-learn — vectorizers & ML pipelines](#2-scikit-learn--vectorizers--ml-pipelines)
3. [pandas — DataFrames at scale](#3-pandas--dataframes-at-scale)
4. [spaCy — stop words inside a Language object](#4-spacy--stop-words-inside-a-language-object)
5. [NLTK — lists, merges, and corpus interop](#5-nltk--lists-merges-and-corpus-interop)
6. [HuggingFace `datasets` — large-corpus normalization](#6-huggingface-datasets--large-corpus-normalization)
7. [Neural models with the `[ml]` extra](#7-neural-models-with-the-ml-extra)
8. [CAMeL Tools with the `[camel]` extra](#8-camel-tools-with-the-camel-extra)
9. [Error handling: a reusable recipe](#9-error-handling-a-reusable-recipe)
10. [Plugin system — custom processors](#10-plugin-system--custom-processors)
11. [Summary & links](#11-summary--links)

### Installation extras at a glance

| Extra | Command | What you get |
|---|---|---|
| *(none)* | `pip install aranorm` | Full core: pipelines, stop words, analyzers, CLI, server |
| `camel` | `pip install "aranorm[camel]"` | `camel-tools>=1.5.0` — model-based dialect ID (MADAR corpus, >90% accuracy) |
| `ml` | `pip install "aranorm[ml]"` | `transformers>=4.30.0`, `torch>=2.0.0`, `sentencepiece>=0.1.99` — neural CODA/MSA normalization |
| `full` | `pip install "aranorm[full]"` | All of the above plus `pyarabic`, `tnkeeh`, `tahdheeb`, `emoji`, `regex`, `tqdm` |

The library integrations (pandas, scikit-learn, spaCy, NLTK, `datasets`) are not bundled in any extra — install the library itself and AraNorm's adapters pick it up.

---

## 1. Quick decision table

| Your situation | What to do |
|---|---|
| "I'm building a TF-IDF / BoW model" | [`SklearnStopWordsAdapter.to_sklearn_list()`](#2-scikit-learn--vectorizers--ml-pipelines) → `TfidfVectorizer(stop_words=...)` |
| "My text lives in a DataFrame" | [`PandasNormalizer.normalize_dataframe()`](#3-pandas--dataframes-at-scale); add [`expand_results()`](#3-pandas--dataframes-at-scale) for dialect + confidence columns |
| "I already have a spaCy pipeline" | [`SpacyStopWordsAdapter.enrich_spacy(nlp)`](#4-spacy--stop-words-inside-a-language-object) — mutates the `Language` in place |
| "I tokenize with NLTK" | [`NLTKStopWordsAdapter.filter_tokens()`](#5-nltk--lists-merges-and-corpus-interop) — works *without* NLTK installed |
| "I want AraNorm + NLTK stop words combined" | [`merge_with_nltk()`](#5-nltk--lists-merges-and-corpus-interop) (needs `nltk.download('stopwords')` once) |
| "My corpus is a HF `Dataset` / `DatasetDict`" | [`HuggingFaceNormalizer.normalize_dataset()`](#6-huggingface-datasets--large-corpus-normalization) — batched `map` |
| "Rules are good enough for dialect → MSA" | [`DialectNormalizer("msa")`](#8-camel-tools-with-the-camel-extra) — dependency-free, deterministic |
| "I need publication-grade dialect→MSA/CODA rewriting" | `pip install "aranorm[ml]"` → [`MSAModel` / `CODAModel`](#7-neural-models-with-the-ml-extra) |
| "I need >90% dialect ID accuracy" | `pip install "aranorm[camel]"` → [`DialectIDModel`](#8-camel-tools-with-the-camel-extra) or `DialectIdentifier(use_camel_tools=True)` |
| "I want my own cleaning step in pipelines" | [Register a custom `Processor`](#10-plugin-system--custom-processors) |
| "My app must run with or without extras" | [The `IntegrationUnavailableError` recipe](#9-error-handling-a-reusable-recipe) |

---

## 2. scikit-learn — vectorizers & ML pipelines

**Requires:** `pip install scikit-learn` (for the vectorizer itself — the adapter needs nothing but AraNorm).

### 2.1 Stop words for `TfidfVectorizer` / `CountVectorizer`

`SklearnStopWordsAdapter` converts any AraNorm stop-word scope into the container scikit-learn expects. It never imports scikit-learn, so it also works in projects that merely *export* stop words for an sklearn job running elsewhere.

```python
from aranorm.integrations import SklearnStopWordsAdapter

adapter = SklearnStopWordsAdapter()               # optional: pass a StopWordsRegistry()
stop_words = adapter.to_sklearn_list("universal") # sorted list — pass this to vectorizers
probe_set  = adapter.to_sklearn_set("universal")  # frozenset — O(1) membership in your code
```

> **Which method goes into `stop_words=`?** Use `to_sklearn_list()`. Recent scikit-learn releases validate `stop_words` as a **list** (or `"english"`/`None`) and reject other collections, while older versions accepted any set-like object — the sorted list is accepted everywhere. Keep `to_sklearn_set()` for your own lookups.

Both methods accept the standard scopes — `universal` (2,449 words in v1.15.0), `msa` (715), `filler` (98), `social` (58), `arabizi` (22), `internet` (131), `numbers` (10):

```python
from sklearn.feature_extraction.text import TfidfVectorizer

vec = TfidfVectorizer(stop_words=adapter.to_sklearn_list("universal"), ngram_range=(1, 2))
X = vec.fit_transform(["أنا أحب القراءة كثيراً", "الخدمة كانت سيئة للغاية"])
```

### 2.2 A complete normalize → vectorize → classify pipeline

The recommended production layout: normalization happens *inside* the sklearn `Pipeline` via a `FunctionTransformer`, so training and inference can never drift apart, and cross-validation measures the real system.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.integrations import SklearnStopWordsAdapter

normalizer = ArabicNormalizationPipeline(PipelineConfig())   # one shared instance

def normalize_series(texts):
    """Normalize a batch of raw Arabic strings for scikit-learn."""
    return [r.normalized_text for r in normalizer.process_batch(list(texts))]

stop_words = SklearnStopWordsAdapter().to_sklearn_list("universal")

clf = Pipeline([
    ("normalize", FunctionTransformer(normalize_series, validate=False)),
    ("tfidf",     TfidfVectorizer(stop_words=stop_words, ngram_range=(1, 2))),
    ("clf",       LogisticRegression(max_iter=1000)),
])

texts = [
    "هذا المنتج رائع جداً وأنا سعيد به", "الخدمة كانت سيئة للغاية ولن أعود",
    "أحب هذا المطعم كثيراً والطعام لذيذ", "التجربة كانت مملة ولا أنصح بها",
]
labels = [1, 0, 1, 0]

clf.fit(texts, labels)
print(clf.predict(["المنتج جيد جداً وسأشتريه مرة أخرى", "خدمة سيئة جداً"]))
# → [1 0]
```

Two practical notes: use a **named function** (as above) rather than a `lambda` if you plan to persist the fitted pipeline with `joblib` across processes; and for social-media text, switch to `PipelineConfig(preset="social_media")` and drop noisy scopes as stop words (`"social"`, `"internet"`, `"arabizi"`).

---

## 3. pandas — DataFrames at scale

**Requires:** `pip install pandas`. The constructor checks immediately and raises `IntegrationUnavailableError("pandas is not installed. Run: pip install pandas")` when it is missing — you find out at construction time, not mid-batch.

`PandasNormalizer(pipeline=None, n_workers=1)` wraps an `ArabicNormalizationPipeline` (a default `standard` pipeline is created when omitted; `n_workers` is forwarded to `process_batch` for parallel row processing) and exposes four operations:

| Method | Returns | What it does |
|---|---|---|
| `normalize_column(series)` | `pd.Series` | Normalized strings; `NaN` → `""` |
| `normalize_dataframe(df, column, output_column=None)` | `pd.DataFrame` | Copy of `df` plus a `"{column}_normalized"` column |
| `expand_results(series, fields=None)` | `pd.DataFrame` | One column per `NormalizationResult` field |
| `apply_stop_words(series, stop_words_field="stop_words_removed")` | `pd.Series` | Stop-word-stripped text (needs a stop-words-enabled pipeline) |

### 3.1 A realistic DataFrame workflow

```python
import pandas as pd

from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig
from aranorm.integrations import PandasNormalizer

df = pd.DataFrame({
    "tweet": [
        "أنا أحب القراءة كثيراً 😍",        # MSA, clean
        "شلونك اليوم؟ شخبارك",              # Gulf dialect
        None,                               # missing value
        "EL 7amdulillah 3la kol 7al",      # Arabizi (Latin script)
    ],
    "likes": [120, 45, 3, 87],
})

# A) One normalized column, added to a copy of df
normalizer = PandasNormalizer()                     # default standard pipeline
df = normalizer.normalize_dataframe(df, "tweet")
print(df["tweet_normalized"].tolist())
# ['انا احب القراءة كثيرا 😍', 'شلونك اليوم? شخبارك', '', 'EL 7amdulillah 3la kol 7al']
# B) Full result fields: dialect, confidence, applied steps
details = normalizer.expand_results(df["tweet"])
print(details[["dialect", "dialect_confidence"]].to_dict("records"))
# [{'dialect': 'MSA', 'dialect_confidence': 0.4},
#  {'dialect': 'GLF', 'dialect_confidence': 0.66},
#  {'dialect': 'UNK', 'dialect_confidence': 0.0},
#  {'dialect': 'UNK', 'dialect_confidence': 0.0}]
```

`expand_results` defaults to the fields `normalized_text`, `dialect`, `dialect_confidence`, and `applied_steps`; pass any subset of `NormalizationResult` field names via `fields=[...]` (e.g. `fields=["normalized_text", "processing_time_ms", "stop_words_found"]`).

### 3.2 Dialect statistics on top of the expanded columns

Because `expand_results` returns ordinary columns, downstream analytics is plain pandas:

```python
df = pd.concat([df, details], axis=1)
print(df["dialect"].value_counts())                       # dialect distribution
print(df.groupby("dialect")["dialect_confidence"].mean()) # confidence per dialect

# Rows the pipeline was least certain about — a ready-made manual-review queue:
print(df.nsmallest(10, "dialect_confidence")[["tweet", "dialect"]])
```

### 3.3 Stop-word removal over a Series

`apply_stop_words` requires a pipeline built with a `StopWordsConfig` — it surfaces the stop-words output the pipeline already produced. The `stop_words_field` argument selects the output: `"stop_words_removed"` (default) for the stripped text, or `"processed_text"` for the fully processed text of the stop-words stage.

```python
cfg = PipelineConfig(stop_words_config=StopWordsConfig(mode="remove"))
stop_normalizer = PandasNormalizer(pipeline=ArabicNormalizationPipeline(cfg))

clean = stop_normalizer.apply_stop_words(pd.Series(["أنا أحب القراءة كثيراً", "شلونك اليوم؟"]))
print(clean.tolist())
# ['القراءة', 'شلونك اليوم?']      # function words أنا/أحب dropped
```

Keep the default `n_workers=1` for deterministic runs; raise it for columns in the tens of thousands of rows and up.

---

## 4. spaCy — stop words inside a Language object

**Requires:** `pip install spacy`. `SpacyStopWordsAdapter` has two methods:

- `to_spacy_set(scope="universal")` — AraNorm stop words as a plain `set` (2,449 words for `universal`).
- `enrich_spacy(nlp, scope="universal")` — **mutates a loaded spaCy `Language` in place**: it unions the scope's words into `nlp.Defaults.stop_words` and sets `nlp.vocab[word].is_stop = True` for words already present in the vocabulary. It returns the same `nlp` object for chaining.

If spaCy is missing, or the object you passed is not a spaCy `Language`, `enrich_spacy` raises `IntegrationUnavailableError` with a clear message.

### 4.1 Blank `ar` pipeline with AraNorm stop words

A common Arabic setup — a blank tokenizer pipeline (no heavyweight statistical model) enriched with dialect-aware stop words:

```python
import spacy
from aranorm.integrations import SpacyStopWordsAdapter

nlp = spacy.blank("ar")                                # tokenizer-only Arabic pipeline
nlp = SpacyStopWordsAdapter().enrich_spacy(nlp, scope="universal")   # in place

doc = nlp("أنا سعيد اليوم بالنجاح")
print([(token.text, token.is_stop) for token in doc])
# [('أنا', True), ('سعيد', False), ('اليوم', True), ('بالنجاح', False)]
print([token.text for token in doc if not token.is_stop])
# ['سعيد', 'بالنجاح']
```

### 4.2 Normalization *before* spaCy

`enrich_spacy` handles stop words; to also normalize orthography (alef variants, diacritics, tatweel…) before spaCy sees the text, run the AraNorm pipeline first:

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

pipeline = ArabicNormalizationPipeline(PipelineConfig())
for text in ["إِنَّ اللّٰهَ غَفُورٌ رَحِيمٌ", "شـكراً جزيلاً 🌸"]:
    doc = nlp(pipeline.process(text).normalized_text)   # clean, canonical text
    print([t.text for t in doc if not t.is_stop])
```

This split — **AraNorm owns normalization, spaCy owns tokenization** — avoids patching spaCy internals with custom components and keeps both libraries independently upgradable.

---

## 5. NLTK — lists, merges, and corpus interop

`NLTKStopWordsAdapter` is the most method-rich adapter because NLTK workflows vary widely:

| Method | NLTK needed? | Returns |
|---|---|---|
| `to_nltk_list(scope="universal")` | no | Sorted `List[str]` |
| `to_frozenset(scope)` | no | `FrozenSet[str]` for O(1) membership tests |
| `filter_tokens(tokens, scope="universal")` | **no** | Tokens with stop words removed, order preserved |
| `merge_with_nltk(scope)` | **yes** + corpus | Sorted union of AraNorm and NLTK Arabic stop words |
| `register_with_nltk(scope)` | **yes** + corpus | Same union, cached on the adapter |

Valid scopes are `universal`, `msa`, `filler`, `social`, `arabizi`, `internet`, `numbers`.

### 5.1 Standalone token filtering (no NLTK required)

`filter_tokens` is deliberately dependency-free — it accepts tokens from *any* tokenizer (NLTK's `word_tokenize`, AraNorm's own tokenizer, or a plain `str.split()`):

```python
from aranorm.integrations import NLTKStopWordsAdapter

adapter = NLTKStopWordsAdapter()
print(adapter.filter_tokens(["أنا", "سعيد", "جداً", "اليوم"]))
# ['سعيد']

# Dialectal / social scopes work exactly the same way:
print(adapter.filter_tokens(["يعني", "خلاص", "المشروع", "تقدم"], scope="filler"))
# ['المشروع', 'تقدم']
```

### 5.2 Merging with NLTK's Arabic stop-word list

`merge_with_nltk` returns the sorted union of the chosen AraNorm scope and `nltk.corpus.stopwords.words("arabic")`. Prepare the corpus once per machine:

```python
import nltk
nltk.download("stopwords")        # one-time; both NLTK and this corpus are required

from aranorm.integrations import NLTKStopWordsAdapter

adapter = NLTKStopWordsAdapter()
merged = adapter.merge_with_nltk("universal")
print(len(merged))
# 2696      # AraNorm's 2,449 universal words ∪ NLTK's Arabic list

stop_set = set(merged)                                        # use anywhere a custom
content_words = [t for t in tokens if t not in stop_set]      # collection fits
```

`register_with_nltk(scope)` calls `merge_with_nltk` and caches the result on the adapter (`adapter._registered_words`) so repeated lookups reuse one merged list. Because NLTK's corpus reader exposes no supported API for injecting words at runtime, the adapter intentionally *returns* the merged list instead of patching NLTK internals — pass it to whichever NLTK function accepts a custom stop-word collection. If NLTK is not installed, both methods raise `IntegrationUnavailableError("NLTK is not installed. Run: pip install nltk")`.

---

## 6. HuggingFace `datasets` — large-corpus normalization

**Requires:** `pip install datasets`. As with pandas, the constructor verifies availability up front. `HuggingFaceNormalizer(pipeline=None, batch_size=512, num_proc=None)` rides on `datasets`' native `Dataset.map()` — you get Arrow-backed caching, progress bars, and multiprocessing for free:

```python
from datasets import Dataset
from aranorm.integrations import HuggingFaceNormalizer

ds = Dataset.from_dict({
    "text": ["هذا المنتج رائع جداً 😍", "شلونك اليوم؟ ما أحوالك", "وصلنا متأخرين بسبب الزحمة"],
    "label": [1, 0, 1],
})

norm = HuggingFaceNormalizer()                       # batch_size=512 by default
ds = norm.normalize_dataset(ds, text_column="text")  # adds "text_normalized"
print(ds.column_names)
# ['text', 'label', 'text_normalized']
```

Key parameters of `normalize_dataset(dataset, text_column="text", output_column=None, remove_original=False)`:

- `text_column` — column to normalize (default `"text"`); `output_column` — where results land, defaulting to `f"{text_column}_normalized"`.
- `remove_original=True` — drop the original column after normalization (halves storage when preparing a final training set).
- **`DatasetDict` support** — passing a `DatasetDict` (e.g. straight from `load_dataset(...)`) maps the normalization over every split.

### 6.1 Large-corpus recipe with parallel workers

```python
from datasets import load_dataset
from aranorm.integrations import HuggingFaceNormalizer

corpus = load_dataset("arabic_speech_corpus", split="train")   # your dataset

norm = HuggingFaceNormalizer(batch_size=1024, num_proc=8)  # forwarded to dataset.map
normalized = norm.normalize_dataset(corpus, text_column="text", remove_original=False)
```

`num_proc` goes directly to `dataset.map()`, so the usual caveats apply (pickling of the map function, per-worker memory, fingerprint cache invalidation).

### 6.2 Expanding result fields into columns

`expand_dataset(dataset, text_column="text", fields=None)` adds one column per requested `NormalizationResult` field — handy for dialect-stratified training or corpus filtering. Defaults are `normalized_text`, `dialect`, `dialect_confidence`; pass any field names via `fields=[...]`.

```python
ds = norm.expand_dataset(ds, text_column="text")
print(ds.column_names)
# ['text', 'label', 'text_normalized', 'normalized_text', 'dialect', 'dialect_confidence']

msa = ds.filter(lambda ex: ex["dialect"] == "MSA" and ex["dialect_confidence"] >= 0.8)
```

---

## 7. Neural models with the `[ml]` extra

**Requires:** `pip install "aranorm[ml]"` (`transformers>=4.30.0`, `torch>=2.0.0`, `sentencepiece>=0.1.99`).

When rule-based dialect normalization is not enough — heavy code-switching, non-standard spellings, full sentence rewriting — AraNorm wraps Hugging Face Seq2Seq models behind two facades plus one shared base:

| Class | Target | Example model ID | Key methods |
|---|---|---|---|
| `TransformersSeq2SeqModel` | generic base | any Seq2Seq (e.g. `Helsinki-NLP/opus-mt-ar-en`) | `predict`, `predict_batch`, `is_loaded`, `unload` |
| `CODAModel` | dialectal → CODA orthography | user-supplied, e.g. `CAMeL-Lab/arabart` | `normalize`, `normalize_batch` |
| `MSAModel` | dialectal → MSA | e.g. `Helsinki-NLP/opus-mt-ar-ar` | `normalize`, `normalize_batch` |

All three share the same lazy-loading contract:

- **Nothing downloads at construction.** The model and tokenizer (via `AutoModelForSeq2SeqLM` + `AutoTokenizer`) are fetched on the *first* `predict`/`normalize` call; constructing the object is always cheap and offline-safe. **First use therefore requires network access to the Hugging Face Hub.**
- **`predict_batch` is a single padded forward pass** — inputs are batched, padded together, and truncated at `max_length=512` tokens, far faster than looping `predict`. Empty input lists return `[]` without loading anything.
- **`device`** accepts standard torch device strings (`"cpu"`, `"cuda:0"`); when omitted, the model stays on its default device. **`max_new_tokens`** (default 128) caps generation length per input. **`is_loaded()`** reports whether weights are resident, and **`unload()`** frees them so you can release GPU memory between phases.
- If `transformers` is missing, any prediction attempt raises `IntegrationUnavailableError` pointing at `pip install aranorm[ml]`; model load/generation failures raise `NormalizationError` with the model name.

### 7.1 Dialectal Arabic → MSA

```python
# pip install "aranorm[ml]"
import torch
from aranorm.models import MSAModel

device = "cuda:0" if torch.cuda.is_available() else "cpu"
model = MSAModel("Helsinki-NLP/opus-mt-ar-ar", device=device, max_new_tokens=128)

# First call downloads the model from the Hugging Face Hub (network required):
print(model.normalize("شلونك؟"))
# → 'كيف حالك؟'          (illustrative; output depends on the chosen model)

# Batch mode — one padded forward pass for all inputs:
msa_batch = model.normalize_batch(["شلونك اليوم؟", "إزاي بقى كده؟", "شو بتعمل هلق؟"])
model.is_loaded()   # True — weights cached on the instance
model.unload()      # release memory when done
```

### 7.2 CODA normalization

CODA (Conventional Orthography for Dialectal Arabic) keeps the *dialect* but spells it consistently — the standard target for dialect corpora. Because the right CODA model is domain-specific and changes over time, `CODAModel` ships with **no default identifier**: you pass the Hugging Face model ID of your choice (the CAMeL-Lab `arabart` family is a common starting point).

```python
# pip install "aranorm[ml]"
from aranorm.models import CODAModel

model = CODAModel("CAMeL-Lab/arabart")   # your chosen Seq2Seq CODA model

# The dialect stays dialectal — only the orthography becomes consistent:
print(model.normalize("شلونك وايد مبسوط"))   # model-dependent CODA spelling
coda_corpus = model.normalize_batch(["شلونك", "خوش حيل", "زين زين"])
```

### 7.3 Rule-based vs. neural: choosing the right tier

| | Rule-based (core) | Neural (`[ml]` extra) |
|---|---|---|
| **Speed** | microseconds per text; ~100k+ texts/min in batch | depends on hardware; GPU strongly recommended for corpora |
| **Quality** | deterministic, conservative word-level rewrites | fluent sentence-level rewriting |
| **Offline** | fully offline | first use downloads from the HF Hub |
| **Dependencies** | none | `transformers`, `torch`, `sentencepiece` |
| **Determinism** | identical output every run | model-dependent (decoding settings) |
| **Best for** | ETL, search indexing, feature extraction, latency-critical services | corpus preparation, benchmark datasets, quality-critical rewriting |

A pragmatic hybrid: run the rule-based `DialectNormalizer` everywhere by default and reserve neural models for the subset your system flags as low-confidence (see the `dialect_confidence` column in §3.2).

---

## 8. CAMeL Tools with the `[camel]` extra

**Requires:** `pip install "aranorm[camel]"` (`camel-tools>=1.5.0`). AraNorm integrates CAMeL Tools in two places: the standalone `DialectIDModel` wrapper and the `DialectIdentifier` stage.

### 8.1 `DialectIDModel` — model-based dialect prediction

`DialectIDModel(supported_dialects=None)` lazily wraps `camel_tools.dialectid.DialectIdentifier.pretrained()` — the model loads on first `predict`, not at construction:

```python
# pip install "aranorm[camel]"
from aranorm.models import DialectIDModel

did = DialectIDModel(supported_dialects=["EGY", "GLF", "LEV"])

label, confidence = did.predict("شلونك اليوم؟ شخبارك")
print(label, confidence)          # e.g. 'GLF' 0.93 (model output)
```

Behavioral contract:

- Returns a `(label, confidence)` tuple with upper-cased labels (`"GLF"`, `"EGY"`, `"MSA"`, …). If `supported_dialects` was given and the predicted label is **not** in it, the model returns `("UNK", 0.0)` instead of an out-of-domain label — perfect for routing only the dialects your downstream handlers support.
- Without `camel_tools`, `predict` raises `IntegrationUnavailableError` suggesting `pip install aranorm[camel]`; failures inside CAMeL Tools surface as `DialectDetectionError`.

### 8.2 The `DialectIdentifier` stage: heuristic vs. model

The stage (from `aranorm.stages.dialect_id`) powers the pipeline's built-in dialect tagging and supports **both engines behind one interface**:

```python
from aranorm.stages.dialect_id import DialectIdentifier

# A) Heuristic engine — default, dependency-free
#    (10 labels: EGY GLF LEV IRQ NOR TUN MSA YEM SDN MTN)
heuristic = DialectIdentifier()

# B) Model engine — CAMeL Tools, >90% accuracy on the MADAR corpus
model_based = DialectIdentifier(use_camel_tools=True)

# Both return the same DialectIdentification dataclass:
result = heuristic.identify("شلونك اليوم؟ شخبارك")
print(result.dialect_label, round(result.confidence_score, 2), result.is_msa)
# GLF 0.87 False
print(result.dialect)            # backward-compatible alias → 'GLF'
print(heuristic.identify("إزاي كده يا باشا").dialect_label)    # EGY
print(heuristic.identify("هذا المنتج جيد").dialect_label)      # MSA
print(heuristic.identify("كيفك اليوم شو بتعمل").dialect_label) # LEV
```

| | Heuristic (default) | `use_camel_tools=True` |
|---|---|---|
| **Dependencies** | none | `aranorm[camel]` |
| **Accuracy** | solid on marker-heavy social text | >90% on the MADAR corpus |
| **Latency** | ~free (weighted lexical markers, whole-token matched) | ML model inference |
| **Confidence** | soft score (0.40 default for MSA, capped at 0.95) | model-calibrated |
| **Failure mode** | non-Arabic/empty text → `("UNK", 0.0)` | `IntegrationUnavailableError` if `[camel]` missing; `DialectDetectionError` on model failure |

`supported_dialects` restricts the heuristic to a subset of labels (e.g. `DialectIdentifier(supported_dialects=["EGY", "GLF"])`), mirroring the `DialectIDModel` argument.

### 8.3 `DialectNormalizer` and its strategies

From `aranorm.stages.dialect_norm`, `DialectNormalizer(target, coda_strategy=None, msa_strategy=None)` routes text through a pluggable strategy (`target` is `"coda"` or `"msa"`; anything else raises `ValueError`):

```python
from aranorm.stages.dialect_norm import (
    DialectNormalizer,
    RuleBasedCODAStrategy,     # dependency-free, bundled replacements
    RuleBasedMSAStrategy,      # dialect_mappings.json, whole-word
    ModelDialectStrategy,      # Transformers Seq2Seq — needs [ml]
)

# Rule-based MSA: dialectal → فصحى
msa = DialectNormalizer("msa")
print(msa.process("شلونك وايد زين اليوم"))
# كيف حالك كثير جيد اليوم

# Rule-based CODA: conservative orthographic repairs only
coda = DialectNormalizer("coda")
print(coda.process("هاذا الشي انشاءالله زين"))
# هذا الشي إن شاء الله زين
```

How the rule-based strategies work — and why they are safe:

- **Whole-word replacement only.** Sources match when surrounded by whitespace or string edges (`(?<!\S)…(?!\S)`), so a dialect marker never corrupts a longer word that merely contains it.
- **Longest-first ordering.** `RuleBasedMSAStrategy` merges every dialect table from the bundled `dialect_mappings.json` and applies longer sources before shorter ones, preventing prefix shadowing.
- **`RuleBasedCODAStrategy`** applies a curated list of unambiguous fixes — restoring dropped hamzas (`اكل → أكل`), splitting contractions (`انشاءالله → إن شاء الله`) — while deliberately leaving dialect vocabulary intact.

When rules are not enough, inject the neural strategy. `ModelDialectStrategy(model_name, device=None, max_new_tokens=128)` follows the same lazy pattern as §7 — nothing downloads until the first `normalize` call, and a missing `transformers` raises `IntegrationUnavailableError` suggesting `pip install aranorm[ml]`. Any custom class implementing `normalize(text) -> str` can be passed as `coda_strategy` / `msa_strategy` — the natural extension point for in-house models:

```python
# pip install "aranorm[ml]"
neural_msa = DialectNormalizer(
    "msa",
    msa_strategy=ModelDialectStrategy("Helsinki-NLP/opus-mt-ar-ar", device="cuda:0"),
)
print(neural_msa.process("شلونك؟"))
```

---

## 9. Error handling: a reusable recipe

Every optional capability in AraNorm funnels into **one exception**: `IntegrationUnavailableError` (a subclass of both `AraNormError` and `RuntimeError`). Its message always names the missing integration and the fix, which makes graceful degradation a five-line pattern:

```python
from aranorm.exceptions import IntegrationUnavailableError

def normalize_dialectal(text: str) -> str:
    """Best-effort dialect→MSA: neural if available, rules otherwise."""
    try:
        from aranorm.stages.dialect_norm import DialectNormalizer, ModelDialectStrategy
        normalizer = DialectNormalizer("msa", msa_strategy=ModelDialectStrategy("Helsinki-NLP/opus-mt-ar-ar"))
        return normalizer.process(text)
    except IntegrationUnavailableError:
        # [ml] extra not installed — fall back to the dependency-free tier
        from aranorm.stages.dialect_norm import DialectNormalizer
        return DialectNormalizer("msa").process(text)
```

### 9.1 Feature detection at startup

For services, probe once at startup instead of catching per request. This is safe precisely because the wrappers are lazy — construction never downloads anything:

```python
def detect_capabilities() -> dict:
    caps = {}
    for key, module in [("pandas", "pandas"), ("neural", "transformers"), ("camel", "camel_tools")]:
        try:
            __import__(module)
            caps[key] = True
        except ImportError:
            caps[key] = False
    return caps

CAPS = detect_capabilities()
# Route accordingly: CAPS["camel"] → DialectIDModel.predict(...) else → heuristic stage
```

### 9.2 What you will actually see

Verified messages raised by each integration when its library is absent:

| Call | Message (abridged) |
|---|---|
| `PandasNormalizer()` | `pandas is not installed. Run: pip install pandas` |
| `HuggingFaceNormalizer()` | ``HuggingFace `datasets` is not installed. Run: pip install datasets`` |
| `MSAModel(...).normalize(...)` | `Transformers is not installed; use 'pip install aranorm[ml]'` |
| `DialectIDModel().predict(...)` | `CAMeL Tools is not installed; use 'pip install aranorm[camel]'` |
| `DialectIdentifier(use_camel_tools=True).identify(...)` | `CAMeL Tools is required for model-based dialect identification; install with: pip install aranorm[camel]` |

Two related exceptions complete the picture: a model that *is* installed but fails (bad model ID, corrupted download, OOM during generation) raises **`NormalizationError`**, and dialect-ID failures inside CAMeL Tools raise **`DialectDetectionError`** — catch `IntegrationUnavailableError` for "capability missing" and let the other two bubble up as genuine bugs.

---

## 10. Plugin system — custom processors

AraNorm pipelines are assembled from `Processor` classes, and the registry that manages them is public API (`aranorm.ProcessorRegistry`). A custom processor needs exactly two things: a `name` class attribute and a `process(text, context)` method:

```python
from aranorm import Processor, ProcessorContext, ProcessorRegistry

class HonorificCleaner(Processor):
    """Strip honorifics before further processing."""

    name = "honorific_cleaner"

    def process(self, text: str, context: ProcessorContext = None) -> str:
        cleaned = text.replace("حفظه الله", "").strip()
        if context is not None:
            context.record(self.name)   # shows up in applied_steps
        return cleaned

registry = ProcessorRegistry()
registry.register("honorific", HonorificCleaner)

cleaner = registry.get("honorific")()
ctx = ProcessorContext()
print(cleaner.process("الملك عبدالله حفظه الله افتتح المؤتمر", ctx))
# الملك عبدالله  افتتح المؤتمر
print(ctx.applied_steps)                # ['honorific_cleaner']
```

The registry enforces its contracts with clear errors: registering an empty name raises `ValueError`, registering a non-`Processor` class raises `TypeError`, and `get("unknown")` raises `ProcessorNotFoundError` listing every available name. `ProcessorFactory(registry)` adds `create(name, **kwargs)` instantiation, and `snapshot()` returns the full name→class mapping.

### 10.1 Distributing processors as entry-point plugins

Third-party packages can plug into AraNorm declaratively via the **`aranorm.processors`** entry-point group — no changes in AraNorm needed:

```toml
# pyproject.toml of your plugin package
[project.entry-points."aranorm.processors"]
honorific = "my_aranorm_plugins.honorific:HonorificCleaner"
```

Consumers discover installed plugins through the registry:

```python
report = registry.discover_report("aranorm.processors")   # strict=False default
print(report.to_dict())
# {'group': 'aranorm.processors', 'ok': True, 'discovered': [...], 'failures': []}
```

`discover_report` sorts candidates deterministically by entry-point name and value, ignores duplicates after the first candidate, and — by default — **collects** every load failure as a `PluginDiscoveryFailure` (name, group, error type, message) instead of raising. That makes it ideal for ops dashboards: `report.ok` is `True` only when every plugin loaded. Pass `strict=True` to flip the contract — the first broken or duplicate plugin raises immediately, which is what you want in CI. The older `discover(group="aranorm.processors")` returns the plain list of newly discovered names with the same semantics.

---

## 11. Summary & links

| Capability | Import | Needs | Fails with |
|---|---|---|---|
| sklearn stop words | `aranorm.integrations.SklearnStopWordsAdapter` | nothing (adapter) | — |
| pandas DataFrames | `aranorm.integrations.PandasNormalizer` | `pandas` | `IntegrationUnavailableError` |
| spaCy enrichment | `aranorm.integrations.SpacyStopWordsAdapter` | `spacy` | `IntegrationUnavailableError` |
| NLTK merge | `aranorm.integrations.NLTKStopWordsAdapter` | `nltk` + corpus | `IntegrationUnavailableError` |
| HF datasets | `aranorm.integrations.HuggingFaceNormalizer` | `datasets` | `IntegrationUnavailableError` |
| CODA/MSA neural models | `aranorm.models.CODAModel` / `MSAModel` | `aranorm[ml]` | `IntegrationUnavailableError` |
| Dialect ID (model / stage) | `aranorm.models.DialectIDModel` / `aranorm.stages.dialect_id.DialectIdentifier` | nothing / `aranorm[camel]` | `IntegrationUnavailableError` / `DialectDetectionError` |
| Dialect normalization | `aranorm.stages.dialect_norm.DialectNormalizer` | nothing / `aranorm[ml]` | `IntegrationUnavailableError` |
| Plugin registry | `aranorm.ProcessorRegistry` | nothing | `ProcessorNotFoundError` / `ValueError` / `TypeError` |

The through-line: **the core never requires any of this.** Install an extra or a third-party library only when the corresponding section of this guide earns its keep in your workload, and let `IntegrationUnavailableError` be the contract that keeps optional truly optional.

### Further reading

- [README](../README.md) · [Analysis guide](analysis.md) · [CLI guide](cli.md) · [CHANGELOG](../CHANGELOG.md)
- [PyPI: aranorm](https://pypi.org/project/aranorm/) · [GitHub: Alqudimi/AraNorm](https://github.com/Alqudimi/AraNorm) · [Issue tracker](https://github.com/Alqudimi/AraNorm/issues)
- Model references: [CAMeL Tools](https://github.com/CAMeL-Lab/camel_tools) · [Helsinki-NLP opus-mt](https://huggingface.co/Helsinki-NLP) · [CAMeL-Lab on the HF Hub](https://huggingface.co/CAMeL-Lab)
