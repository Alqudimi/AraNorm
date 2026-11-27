# Stop Words — محرك الكلمات الوقفية

AraNorm's stop-word engine is one of its most powerful subsystems: a multi-dialect, multi-scope, context-aware system built on a Trie-backed registry with **2,400+ universal stop words**, per-dialect lists, domain lists, phrase matching, and morphological expansion — all dependency-free.

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
)
pipeline = ArabicNormalizationPipeline(config)
```

---

## Table of contents

1. [Quick tour](#quick-tour)
2. [Modes: remove, extract, highlight, count](#modes-remove-extract-highlight-count)
3. [Scopes: what counts as a stop word](#scopes-what-counts-as-a-stop-word)
4. [Dialects: eight regional lists](#dialects-eight-regional-lists)
5. [Domain stop words](#domain-stop-words)
6. [Context preservation](#context-preservation)
7. [Phrases: multi-word stop expressions](#phrases-multi-word-stop-expressions)
8. [Morphological expansion](#morphological-expansion)
9. [The StopWordsRegistry](#the-stopwordsregistry)
10. [Internet, Arabizi & number tokens](#internet-arabizi--number-tokens)
11. [Custom and excluded words](#custom-and-excluded-words)
12. [Presets and the CLI](#presets-and-the-cli)

---

## Quick tour

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

pipeline = ArabicNormalizationPipeline(PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
))

result = pipeline.process("أنا ذهبت إلى السوق لكي أشتري بعض الفواكه الطازجة")

result.normalized_text      # ذهبت السوق أشتري الفواكه الطازجة
result.stop_words_removed   # ذهبت السوق أشتري الفواكه الطازجة
result.stop_words_found     # {'أنا', 'إلى', 'لكي', 'بعض'}
result.stop_words_stats     # {'removed_count': 4, 'total_tokens': 9,
                           #  'percentage': 0.44, 'by_category': {...}}
result.stop_words_by_category  # {'pronouns': ['أنا'], 'prepositions': ['إلى', 'بعض'], ...}
```

Everything about stop words is reported: what was removed, what categories it belonged to, and the ratio.

## Modes: remove, extract, highlight, count

`StopWordsConfig.mode` controls what happens to matched words:

```python
from aranorm import StopWordsConfig
text = "أنا ذهبت إلى السوق"

StopWordsConfig(mode="remove")      # 'ذهبت السوق'        — strip them
StopWordsConfig(mode="extract")     # 'أنا إلى'           — keep ONLY them
StopWordsConfig(mode="highlight")   # '[[أنا]] ذهبت [[إلى]] السوق'
StopWordsConfig(mode="count")       # 'أنا ذهبت إلى السوق' — text unchanged, stats only
```

`highlight` is ideal for explainability (showing users why a document matched a query); `count` powers analytics without touching the text.

## Scopes: what counts as a stop word

`StopWordsConfig.scope` selects the active word lists:

| Scope | Stop-word universe | Use case |
|---|---|---|
| `universal` | MSA + all dialects + modern/social (2,449 words) | Default — safest general choice |
| `msa_only` | Classical MSA function words (715 words) | Formal/news text |
| `dialect_aware` | MSA + the dialect lists you name | Regional corpora |
| `custom` | **Only** your `custom_stop_words` | Full control |

```python
StopWordsConfig(mode="remove", scope="msa_only")
StopWordsConfig(mode="remove", scope="dialect_aware", dialects={"EGY", "GLF"})
StopWordsConfig(mode="remove", scope="custom", custom_stop_words={"كلمة", "أخرى"})
```

**Rule:** `dialect_aware` requires a non-empty `dialects` set and `custom` requires `custom_stop_words` — the config validates this and raises `ConfigurationError` early.

## Dialects: eight regional lists

Dialect stop words are the words that are *function words in that dialect but not in MSA* — إزيك، عشان، وايد، هيك، دغيا...

Valid codes: `EGY, GLF, LEV, IRQ, NOR, TUN, YEM, MSA`.

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

config = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(
        mode="remove",
        scope="dialect_aware",
        dialects={"EGY"},
    ),
)
pipeline = ArabicNormalizationPipeline(config)

result = pipeline.process("إزيك عامل إيه النهاردة يا محمد")
# EGY-specific function words (إزيك، إيه، النهاردة، يا) are removed
```

## Domain stop words

For specialized corpora, generic stop words are not enough — legal/medical texts are full of domain boilerplate. The `DomainStopProcessor` layers domain lists **on top of** the universal list:

```python
from aranorm.processors import DomainStopProcessor

processor = DomainStopProcessor(domains=["medical"], include_universal=True)

DomainStopProcessor.get_supported_domains()
# ['legal', 'medical', 'news', 'religious']

DomainStopProcessor.get_domain_words("medical")   # the raw domain list
processor.process("المريض يشكو من ألم في الصدر منذ يومين")
```

Standalone scope selection also works through the registry (see below): `get_words(scope="filler"|"social"|"arabizi"|"internet"|"numbers")`.

## Context preservation

Blind removal breaks meaning: "ما ذهبت" (I did not go) loses its negation if ما is removed. Context-aware options fix this:

```python
StopWordsConfig(
    mode="remove",
    scope="universal",
    preserve_negation=True,      # keep لا، لم، لن، ما — default True
    preserve_emphasis=False,     # keep إن/أن in emphatic contexts
    preserve_prepositions=False, # keep prepositions (للـ SEO/MT workloads)
)
```

For fine-grained control, the `ContextAwareProcessor` inspects the token *after* a candidate word to decide whether it is functional or semantic:

```python
from aranorm.processors import ContextAwareProcessor

ContextAwareProcessor(preserve_negation=True).process("ما ذهبت إلى السوق")
# 'ما ذهبت السوق'  — the negation ما survives
```

## Phrases: multi-word stop expressions

Some stop words are phrases, not single tokens: "إن شاء الله", "في الحقيقة", "على أي حال". The `PhraseStopProcessor` matches them with a sliding window (longest phrases first):

```python
from aranorm.processors import PhraseStopProcessor

processor = PhraseStopProcessor(mode="remove")
processor.process("في الحقيقة الأمر بسيط إن شاء الله")
# 'الأمر بسيط'

processor.get_phrases_found("في الحقيقة الأمر بسيط")  # matched phrases with positions
processor.phrase_count                                   # number of known phrases
```

Modes: `remove`, `highlight`, `tag`. Add your own phrases via `extra_phrases={"على العموم"}`.

## Morphological expansion

A stop word in Arabic wears many clothes: كان/كانت/كانوا/تكون... The `MorphologicalStopProcessor` expands the base list with:

- verb conjugations of كان وأخواتها
- cliticized prepositions (بـ، لـ، كـ + attached forms)
- ال-stripped forms (الذي stripped of the article in derived forms)

```python
from aranorm.processors import MorphologicalStopProcessor

processor = MorphologicalStopProcessor(
    include_clitic_forms=True,
    include_verb_forms=True,
)
processor.stop_set_size   # expanded set size
processor.process("كان الطلاب قد ذهبوا وكانت المدرسة مزدحمة")
```

## The StopWordsRegistry

All lists live in one thread-safe registry with a pure-Python **Trie** lookup (O(word-length) per token) and an LRU cache on the hot path:

```python
from aranorm import StopWordsRegistry

registry = StopWordsRegistry()

registry.is_stop("في")                      # True (MSA/universal)
registry.is_stop("إزيك", dialect="EGY")     # True (dialect list)
registry.is_stop("برمجة")                   # False

registry.get_words(scope="universal")       # the full universal set
registry.get_words(scope="msa")
registry.get_words(scope="dialect", dialects={"EGY", "GLF"})
registry.get_by_category("pronouns")        # category sets: prepositions, pronouns,
                                            # conjunctions, interrogatives, demonstratives,
                                            # relative_pronouns, negation, emphasis,
                                            # particles, adverbs, filler, social_media,
                                            # internet, arabizi, numbers
registry.get_stats()    # per-list word counts
registry.add_custom({"كلمة"})   # runtime additions (cache-safe)
registry.get_all_dialects()     # Dict[dialect, Set[str]]
```

## Internet, Arabizi & number tokens

Three modern token families have their own lists and toggles:

| Flag | Removes | Examples |
|---|---|---|
| `remove_filler=True` (default) | Spoken fillers | يعني، والله، خلاص، طيب |
| `remove_arabizi=True` | Arabizi function words | `2na`, `3nd`, `5alas` |
| `remove_internet=True` | Internet slang/leet | `www`, `http`, `lol`, `omg` |
| `remove_numbers=True` | Bare digit tokens | `2025`, `99` |

```python
StopWordsConfig(mode="remove", scope="universal",
                remove_filler=True, remove_internet=True,
                remove_arabizi=True, remove_numbers=True)
```

This exact combination is what the `social_media` preset enables automatically.

## Custom and excluded words

```python
StopWordsConfig(
    mode="remove",
    scope="universal",
    custom_stop_words={"شركة", "محدود"},   # added on top of the scope
    excluded_stop_words={"لا"},            # never removed, even if in the lists
)
```

## Presets and the CLI

Convenience constructors:

```python
StopWordsConfig.for_social_media()          # remove/universal + all modern toggles
StopWordsConfig.for_dialect("EGY", "GLF")   # dialect_aware removal
StopWordsConfig.count_only()                # count mode, stats only
```

CLI:

```bash
$ aranorm stopwords "أنا ذهبت إلى السوق" --mode remove --json
$ aranorm normalize "نص..." --stop-words --sw-scope dialect_aware
```

---

## Next steps

- [Processors](processors.md) — the full processor catalog
- [Analysis](analysis.md) — analyzers that build on stop-word separation (content words, lexical density)
- [API Reference](api.md) — `StopWordsConfig` field reference
