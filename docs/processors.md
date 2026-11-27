# Processors — دليل المعالجات الكامل

Every transformation in AraNorm is a **processor**: a small, single-purpose class with a registered name. Stages compose processors in a fixed order, and the pipeline composes stages. This guide documents all of them — what they do, when to use them, and what they produce.

```python
from aranorm.processors import ALEFProcessor

processor = ALEFProcessor()
output = processor.process("أحمد إبراهيم", context=None)
```

---

## Table of contents

1. [How processors work](#how-processors-work)
2. [The ProcessorRegistry](#the-processorregistry)
3. [Content cleaning processors](#content-cleaning-processors)
4. [Orthographic normalization processors](#orthographic-normalization-processors)
5. [Structure & spacing processors](#structure--spacing-processors)
6. [Stop-word processors](#stop-word-processors)
7. [Enrichment processors](#enrichment-processors)
8. [Platform-specific processors](#platform-specific-processors)
9. [Text-level processors](#text-level-processors)
10. [Stage composition order](#stage-composition-order)
11. [Writing your own processor](#writing-your-own-processor)

---

## How processors work

Every processor implements the two-method `Processor` contract:

```python
class Processor(ABC):
    name: str = "processor"

    @abstractmethod
    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Transform text and record the step in the context."""
```

- **`process(text, context)`** returns the transformed string — processors are pure string→string functions.
- **`ProcessorContext`** accumulates `applied_steps` and metadata as text flows through the pipeline; it is how `NormalizationResult.applied_steps` gets populated. With `emit_steps_trace=True`, the context also records an ordered `(processor, action)` trace.
- Most processors subclass `TextProcessor` (validates input via `validate_text` then calls your `transform()`) or `RegexProcessor` (pattern → replacement) — both handle context recording for you.

## The ProcessorRegistry

Processors are discoverable by name through a thread-safe registry:

```python
from aranorm.core import ProcessorRegistry, ProcessorFactory

registry = ProcessorRegistry()
registry.names()          # all registered processor names, alphabetical
registry.get("normalize_alef")   # → the ALEFProcessor class
registry.contains("normalize_alef")  # True

factory = ProcessorFactory(registry)
processor = factory.create("normalize_alef")   # ready-to-use instance
```

Plugins can be discovered from installed packages via the `aranorm.processors` entry-point group (`aranorm plugins --strict` in the CLI). Unknown names raise `ProcessorNotFoundError` with the list of available names.

---

## Content cleaning processors

Remove noise. These never rewrite words that stay in the text.

| Processor class | Registered name | Effect |
|---|---|---|
| `URLProcessor` | `remove_urls` | Delete `http(s)://…` and `www.…` links |
| `EmailProcessor` | `remove_emails` | Delete email addresses |
| `MentionProcessor` | `remove_mentions` | Delete `@username` mentions |
| `HashtagProcessor` | `remove_hashtags` | Delete only the `#` marker — the word remains |
| `HTMLProcessor` | `remove_html_tags` | Delete simple HTML tags, keep contents |
| `EmojiProcessor` | `remove_emojis` | Delete emoji code points (no external library) |
| `NonArabicProcessor(keep_digits=True, keep_punctuation=True)` | `remove_non_arabic` | Keep only Arabic letters (+digits/punctuation as configured) |
| `EnglishProcessor` | `remove_english` | Delete Latin words and letters |

```python
from aranorm.processors import URLProcessor, MentionProcessor

cleaner = URLProcessor()
cleaner.process("زوروا https://example.com الآن")
# 'زوروا  الآن'

mentions = MentionProcessor()
mentions.process("شكراً @ahmed على الإطراء")
# 'شكراً  على الإطراء'
```

---

## Orthographic normalization processors

Unify spelling. Idempotent: running twice changes nothing the second time.

| Processor class | Registered name | Effect |
|---|---|---|
| `UnicodeProcessor` | `normalize_unicode` | Unicode NFKC compatibility normalization |
| `LigaturesProcessor` | `normalize_ligatures` | Expand presentation ligatures ﻻ ﻷ ﻹ ﻵ |
| `ALEFProcessor` | `normalize_alef` | أ إ آ ٱ → ا |
| `AlefMaqsuraProcessor` | `normalize_alef_maqsura` | ى → ي |
| `TaaMarbutaProcessor` | `normalize_taa_marbuta` | ة → ه |
| `HamzaProcessor` | `normalize_hamza` | ؤ، ئ → ء |
| `DiacriticsProcessor` | `normalize_diacritics` | Remove harakat, shadda, sukun, Quranic signs |
| `TatweelProcessor` | `normalize_tatweel` | Remove kashida ـ |
| `DigitsProcessor` | `normalize_digits` | ٠-٩ and ۰-۹ → 0-9 |
| `PunctuationProcessor` | `normalize_punctuation` | ، ؛ ؟ ٪ «» → ASCII equivalents; drop zero-widths |
| `ArabiziProcessor` | `normalize_arabizi` | `2na 3ndi 7aga` → Arabic script |

```python
from aranorm.processors import ALEFProcessor, DiacriticsProcessor, ArabiziProcessor

ALEFProcessor().process("أحمد إبراهيم")     # احمد ابراهيم
DiacriticsProcessor().process("مُحَمَّد")      # محمد
ArabiziProcessor().process("2na 3ndi 7aga")  # انا عندي حاجه
```

The Arabizi mapping follows the standard numeric conventions: `2`→ء/ق-glottal, `3`→ع, `7`→ح, `5`/`kh`→خ, `9`→ص, `sh`→ش, doubled vowels for long vowels, etc.

---

## Structure & spacing processors

| Processor class | Registered name | Effect |
|---|---|---|
| `WhitespaceProcessor` | `normalize_whitespace` | Collapse whitespace runs → single space, trim |
| `SpacingProcessor` | `fix_spacing` | No space before punctuation, one space after |
| `RepeatedCharsProcessor(limit=2)` | `normalize_repeated_chars` | Collapse expressive runs keeping `limit`: هاااااي → هااي |
| `RepeatedPunctuationProcessor` | `remove_extra_punctuation` | ؟؟؟؟ → ؟ |

```python
from aranorm.processors import RepeatedCharsProcessor

RepeatedCharsProcessor(limit=2).process("هاااااااي")
# 'هااي'
```

---

## Stop-word processors

Six specialized engines, from the simple to the morphological. Full semantics in the [Stop Words guide](stopwords.md).

| Processor class | Registered name | What it removes |
|---|---|---|
| `StopWordsProcessor(config=None, registry=None)` | `stop_words_processor` | The main engine — 4 modes × 4 scopes, per-category/dialect attribution |
| `DialectStopProcessor(dialects, registry=None)` | `dialect_stop_processor` | MSA + dialect-specific stop words for the given codes |
| `DomainStopProcessor(domains, include_universal=True)` | `domain_stop_processor` | Domain stop words (legal/medical/news/religious) + universal |
| `PhraseStopProcessor(extra_phrases=None, mode="remove")` | `phrase_stop_processor` | Multi-word stop phrases ("إن شاء الله"، "في الحقيقة") |
| `MorphologicalStopProcessor(include_clitic_forms=True, include_verb_forms=True)` | `morphological_stop_processor` | Stop words + all inflected variants (كان conjugations, cliticized prepositions, ال-stripped forms) |
| `ContextAwareProcessor(preserve_negation=True, preserve_emphasis=False)` | `context_aware_stop_words` | Context-sensitive removal — keeps true negation (لا) and emphatic إن, drops idiomatic uses |
| `ArabiziStopProcessor(registry=None)` | `arabizi_stop_processor` | Arabizi function words (`2na`, `3nd`) and digit-only tokens |
| `InternetStopProcessor(registry=None)` | `internet_stop_processor` | Internet slang/leet (`www`, `lol`, `http`) and bare URL fragments |

```python
from aranorm.processors import StopWordsProcessor, ContextAwareProcessor

engine = StopWordsProcessor()                    # remove/universal defaults
engine.process("أنا ذهبت إلى السوق")              # 'ذهبت السوق'
engine.process_detailed("أنا ذهبت إلى السوق")     # StopWordsResult with full stats

context_aware = ContextAwareProcessor(preserve_negation=True)
context_aware.process("ما ذهبت إلى السوق")        # negation ما kept
```

---

## Enrichment processors

Classify or canonicalize special tokens instead of deleting them.

| Processor class | Registered name | Modes | Effect |
|---|---|---|---|
| `CurrencyProcessor(mode="normalize")` | `normalize_currency` | `normalize`/`remove`/`keep` | `50 ريال` → `50 SAR`; or remove all currency mentions |
| `DateTimeProcessor(mode="normalize")` | `normalize_datetime` | `normalize`/`remove` | Hijri/Gregorian dates, times → `MONTH_01`, `DATE_…`, `TIME_…`, `TODAY` tokens |
| `PhoneProcessor(mode="remove")` | `remove_phone_numbers` | `remove`/`mask`/`normalize` | Gulf/Levant/Egyptian/international phone numbers → removed, `[PHONE]`, or canonical form |
| `NumberWordsProcessor(replace_ordinals=True)` | `number_words` | — | Written numbers → digits: `خمسة وعشرون` → `25` |
| `SpellingProcessor()` | `spelling_correction` | — | Deterministic common-error fixes: `بالزبط`→`بالضبط`, `مسئول`→`مسؤول` |

```python
from aranorm.processors import CurrencyProcessor, NumberWordsProcessor

CurrencyProcessor(mode="normalize").process("دفعت 50 ريال فقط")
# 'دفعت 50 SAR فقط'

NumberWordsProcessor().process("قرأت خمسة وعشرين كتاباً")
# 'قرأت 25 كتاباً'
```

---

## Platform-specific processors

Built for the texture of each platform.

| Processor class | Registered name | Effect |
|---|---|---|
| `TwitterNormalizer(remove_rt=True, expand_hashtags=True, remove_mentions=True, remove_via=True, remove_thread_markers=True)` | `normalize_twitter` | Strip `RT`/`via` prefixes, thread markers, mentions; expand hashtags |
| `WhatsAppNormalizer(expand_abbreviations=True, remove_media_markers=True, remove_formatting=True)` | `normalize_whatsapp` | Expand chat abbreviations, strip media markers and `*bold* _italic_ ~strike~` |
| `ChatNormalizer(normalize_laughter=True, expand_abbreviations=True, fix_common_errors=True)` | `normalize_chat` | Collapse `ههههه`/`lol` laughter, expand abbreviations, fix `اللة`→`الله` |

```python
from aranorm.processors import TwitterNormalizer

twitter = TwitterNormalizer()
twitter.process("RT @user: ممتاز! #السعودية https://t.co/x")
# 'ممتاز! السعودية'
```

---

## Text-level processors

Sentence-scope fixes beyond single characters.

| Processor class | Registered name | Effect |
|---|---|---|
| `RedundancyProcessor` | `redundancy_cleaner` | Remove zero-width/invisible Unicode, collapse redundant whitespace/tatweel |
| `SentenceNormalizerProcessor(fix_punctuation_spacing=True, remove_directional_marks=True)` | `sentence_normalizer` | `كيف حالك ؟` → `كيف حالك؟`; strip LTR/RTL directional marks |

---

## Stage composition order

The pipeline composes processors through three stages, each with a **fixed, deterministic order**:

**ContentCleaner** (only enabled flags run):
`HTML → URLs → emails → mentions → hashtags → emojis → non-Arabic → English → whitespace`

**OrthographicNormalizer**:
`Arabizi → Unicode → ligatures → alef → alef-maqsura → taa-marbuta → hamza → diacritics → tatweel → digits → punctuation → repeated chars → extra punctuation → spacing → whitespace`

**DialectProcessor** (when `dialect_target` is set): dialect identification → CODA/MSA normalization.

This ordering is a correctness decision: e.g. Arabizi runs first (before Latin letters could be stripped), diacritics before hamza (so carrier forms are visible), digits before punctuation (so Arabic-Indic digits aren't mistaken for punctuation).

---

## Writing your own processor

Subclass `TextProcessor`, implement `transform()`, and register it:

```python
from aranorm.processors._base import TextProcessor
from aranorm.core import ProcessorRegistry


class SmileysToTextProcessor(TextProcessor):
    """Convert emoticons to sentiment words."""

    name = "smileys_to_text"

    def transform(self, text: str) -> str:
        return text.replace(":-)", " سعيد").replace(":-(", " حزين")


registry = ProcessorRegistry()
registry.register("smileys_to_text", SmileysToTextProcessor)
processor = registry.get("smileys_to_text")()
processor.process("فزت :-)")
# 'فزت  سعيد'
```

To distribute processors as **plugins**, expose them under the `aranorm.processors` entry-point group in your `pyproject.toml`; `aranorm plugins --strict` then discovers them in any environment where your package is installed.

---

## Next steps

- [Configuration](configuration.md) — which flags activate which processors
- [Stop Words](stopwords.md) — deep dive on the stop-word family
- [API Reference](api.md) — exact constructor signatures
