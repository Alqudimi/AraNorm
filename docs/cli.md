# AraNorm CLI Reference

**Version 1.15.0** · Arabic text normalization & analysis toolkit

The `aranorm` command-line interface exposes the complete AraNorm pipeline —
normalization, stop-word handling, and more than 40 Arabic text analyzers — to
your shell and build scripts. Every analyzer available in the Python API is
reachable from the CLI, and every command prints either a human-readable report
or machine-readable JSON.

The CLI is available through two equivalent entry points:

```console
$ aranorm normalize "شلونك حبيبي؟"
$ python -m aranorm.cli normalize "شلونك حبيبي؟"
```

- `aranorm` — the console script installed with the package (`pip install aranorm`).
- `python -m aranorm.cli` — the same program, invoked as a module (useful in
  virtual environments, containers, or when the script is not on `PATH`).

Almost every command accepts the `--json` flag, which switches the output from
a formatted report to a JSON document (serialized with `ensure_ascii=False`
and `indent=2`, so Arabic text stays readable). JSON output is stable and
intended for piping into `jq`, logs, or downstream tools.

> **Tip — `--json` placement:** always place `--json` **after** the sub-command
> name (`aranorm version --json`). A `--json` placed *before* the sub-command
> name is accepted syntactically but is overridden by the sub-command's own
> default, and the report will be printed in human-readable form.

---

## Table of contents

1. [Getting help](#getting-help)
2. [Input & output conventions](#input--output-conventions)
3. [Normalization](#normalization)
   - [`normalize`](#normalize)
4. [Analysis commands](#analysis-commands)
   - [Text statistics & structure](#text-statistics--structure) — `analyze`, `readability`, `detect`, `tokenize`
   - [Language identification & similarity](#language-identification--similarity) — `dialect`, `compare`
   - [Sentiment & emotions](#sentiment--emotions) — `sentiment`, `emotions`
   - [Content extraction](#content-extraction) — `keywords`, `summarize`, `entities`, `topics`, `numbers`
   - [Linguistic analysis](#linguistic-analysis) — `pronouns`, `idioms`, `roots`, `complexity`
   - [Rhetoric, style & discourse](#rhetoric-style--discourse) — `rhythm`, `figurate`, `contrast`, `rquestions`, `anaphora`, `quotation`, `loans`, `fillers`, `coherence`, `style`, `freqprofile`, `textprofile`
   - [Quality & spelling](#quality--spelling) — `quality`, `spelling`
5. [Stop words](#stop-words) — `stopwords`
6. [Batch processing](#batch-processing) — `batch`, `corpus`, `profile`
7. [Pipeline management](#pipeline-management) — `describe`, `plugins`, `spec export`, `spec validate`, `snapshot save`, `snapshot restore`
8. [Streaming sessions](#streaming-sessions) — `stream run`, `stream resume`, `stream status`
9. [HTTP server](#http-server) — `serve`
10. [Info & version](#info--version) — `info`, `version`
11. [Recipes](#recipes)
12. [Shell completion](#shell-completion)

---

## Getting help

```console
$ aranorm --help            # list every sub-command
$ aranorm normalize --help  # flags and defaults for one command
$ aranorm spec --help       # sub-command groups also have help pages
$ aranorm stream run --help # help for nested sub-commands
```

`aranorm --help` prints the full command catalog with one-line descriptions.
Each command's own `--help` page lists its flags, accepted values, and defaults.
Running `aranorm` with no arguments (or with an unknown command) is a usage
error: the parser prints the problem to stderr and exits with code `2`.

---

## Input & output conventions

Most commands follow the same three-way input model. When more than one input
source is supplied, the first available one in this order wins:

| Priority | Input method | Example | Notes |
|:--------:|--------------|---------|-------|
| 1 | Positional `text` argument | `aranorm normalize "السلام عليكم"` | Always quote text on the shell. Optional (`text?`) on most commands; **required** on some (see below). |
| 2 | `--file` / `-f FILE` | `aranorm sentiment -f reviews.txt` | UTF-8 file. Read line-by-line or as full content depending on the command (see below). |
| 3 | Standard input (fallback) | `cat notes.txt \| aranorm quality` | Used only when neither `text` nor `--file` is given, and only on commands whose `text` argument is optional. |

### File modes: line-oriented vs. full content

| Mode | Behavior | Commands |
|------|----------|----------|
| **Line-oriented** | Each non-empty line is one independent input; results are reported per line. | `normalize`, `keywords`, `sentiment`, `pronouns` (one *word* per line), plus `batch`, `corpus`, `profile` (file required) |
| **Full content** | The whole file is read as a single text and analyzed as one document. | `spelling`, `quality`, `entities`, `topics`, `idioms`, `freqprofile`, `coherence`, `style`, `emotions`, `textprofile`, `rhythm`, `figurate`, `numbers`, `quotation`, `loans`, `roots`, `contrast`, `fillers`, `complexity`, `rquestions`, `anaphora`, `tokenize`, `summarize` |

### Commands with special input rules

- **Required positional text — no `--file`/stdin support:** `stopwords`,
  `analyze`, `dialect`, `compare` (two positionals), `readability`, `detect`.
- **Required `--file`:** `batch`, `corpus`, `profile`.
- **No text input at all:** `info`, `version`, `describe`, `plugins`,
  `spec export`, `spec validate` (takes a spec *file* positional),
  `snapshot save`, `snapshot restore`, `stream *`, `serve`.

### Output behavior

- **Human mode (default).** Formatted, labeled reports designed for terminals.
  For line-oriented commands, one result block per input line.
- **JSON mode (`--json`).** The same data serialized as JSON with
  `ensure_ascii=False` (Arabic characters are not escaped) and `indent=2`.
  Arrays of results are used for line-oriented commands; single objects for
  document commands. A few commands (`version`, server responses) use compact
  or sorted serialization — noted where relevant.
- **Writing files.** `normalize` and `batch` accept `-o/--output` to write
  results to a file instead of stdout. CSV exports are written with a UTF-8
  BOM (`utf-8-sig`) so Excel opens Arabic correctly; JSON/JSONL exports are
  plain UTF-8.
- **Errors go to stderr.** Every failure prints an `Error: …` (or `Warning: …`
  for skipped items) line on stderr; stdout remains clean for piping.

### Exit codes

| Code | Meaning |
|:----:|---------|
| `0` | Success. |
| `1` | Runtime error — missing/unreadable input file, empty input, invalid spec/snapshot file, server startup failure, or any unexpected exception. |
| `2` | Usage error — unknown command, missing required argument, invalid flag value. Also returned by `normalize`/`batch` when some items still fail **after** `--retry` exhausted all attempts. |
| `130` | Interrupted with `Ctrl+C` (SIGINT). |

---

## Normalization

### `normalize`

Normalize one text, or a file of texts line-by-line. This is the CLI front end
of `ArabicNormalizationPipeline`.

**Synopsis**

```text
aranorm normalize [text?] [-f FILE] [-o OUTPUT] [--preset PRESET]
                  [--dialect-target TARGET] [--keep-diacritics] [--keep-urls]
                  [--clean-emojis] [--stop-words] [--sw-scope SCOPE]
                  [--workers N] [--retry] [--max-retries N] [--batch-size N]
                  [--emit-steps-trace] [--json]
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `text` (positional, optional) | — | A single text to normalize. |
| `-f, --file FILE` | — | Input file, **one text per line** (empty lines skipped). |
| `-o, --output FILE` | stdout | Write results to this file instead of stdout. |
| `--preset {light,standard,deep,social_media}` | `standard` | Normalization preset (see table below). |
| `--dialect-target {none,coda,msa}` | `none` | Optional dialect rewriting stage: `coda` maps dialectal orthography toward the CODA conventions, `msa` toward Modern Standard Arabic. |
| `--keep-diacritics` | off | Preserve Arabic diacritics (harakāt) instead of stripping them. |
| `--keep-urls` | off | Keep URLs in the output (default is to clean them). |
| `--clean-emojis` | off | Remove emoji characters. |
| `--stop-words` | off | Remove stop words while normalizing. |
| `--sw-scope {universal,msa_only,dialect_aware}` | `universal` | Which stop-word lists `--stop-words` uses. |
| `--workers N` | `1` | Number of parallel workers for multi-text runs. |
| `--retry` | off | Retry failed items with bounded retries (adds a `retry` report to JSON output). |
| `--max-retries N` | `3` | Maximum retries per item under `--retry`. |
| `--batch-size N` | `32` | Retry batch size (items kept in flight per attempt). |
| `--emit-steps-trace` | off | Include the per-processor `steps_trace` in JSON output (opt-in). |
| `--json` | off | JSON output instead of plain lines. |

**Presets**

| Preset | Use case |
|--------|----------|
| `light` | Orthographic pass only — nothing is removed. |
| `standard` | Default balance: cleans URLs/emails/HTML and applies full normalization. |
| `deep` | Maximum cleaning plus expressive repetition collapse (e.g. `ياااا` → `يا`). |
| `social_media` | Social platforms: strips mentions/emojis and applies automatic stop-word removal. |

Every preset can be fine-tuned with the individual boolean flags above (for
example `--preset standard --clean-emojis`).

**Input.** Positional text → `--file` (line-oriented) → stdin (one text per
line).

**Output.** Human mode prints one normalized text per input line. JSON mode
prints an array of objects with `original`, `normalized`, `dialect`,
`dialect_confidence`, plus `stop_words_removed` (when `--stop-words` is used)
and `steps_trace` (when `--emit-steps-trace` is used). With `--retry`, the
payload becomes `{"results": [...], "retry": {...}, "schema_version": "1.0"}`.

**Examples**

Normalize a single text (note the tatweel removal and punctuation folding):

```console
$ aranorm normalize "شلونـك حبيبي؟؟ 😂👍 يلا نروح"
شلونك حبيبي?? 😂👍 يلا نروح
```

Normalize a stream from stdin, strip emoji, write to a file:

```console
$ cat tweets.txt | aranorm normalize --clean-emojis -o clean.txt
```

Normalize a file line-by-line with the social-media preset and dialect-aware
stop-word removal:

```console
$ aranorm normalize -f tweets.txt -o normalized.txt \
    --preset social_media --stop-words --sw-scope dialect_aware
```

Machine-readable output with dialect tagging:

```console
$ aranorm normalize --json "السلام عليكم ورحمة الله"
[
  {
    "original": "السلام عليكم ورحمة الله",
    "normalized": "السلام عليكم ورحمة الله",
    "dialect": "MSA",
    "dialect_confidence": 0.4
  }
]
```

---

## Analysis commands

All analyzers share the input conventions described
[above](#input--output-conventions). Each command below lists its synopsis,
options, input mode, output shape, and an example. Unless noted otherwise,
JSON mode prints a single object (or an array for line-oriented commands).

### Text statistics & structure

#### `analyze`

Text statistics and readability for a single text.

```text
aranorm analyze <text> [--json]
```

**Input.** Required positional `text` — no file or stdin support.

**Output.** Human mode prints word/sentence counts, average lengths,
vocabulary size, type-token ratio, Arabic ratio, readability label and score,
and the top words. JSON mode returns `word_count`, `arabic_word_count`,
`sentence_count`, `avg_word_length`, `avg_sentence_length`, `vocabulary_size`,
`type_token_ratio`, `arabic_ratio`, `diacritic_ratio`, `readability_score`,
`readability_label`, and `top_words`.

```console
$ aranorm analyze "أعلنت وزارة التعليم عن نتائج الامتحانات النهائية للعام الدراسي."
Word count         : 9
Arabic words       : 9
Sentences          : 1
...
Readability        : very_easy (80/100)
```

#### `readability`

A dedicated readability score (0–100) with its drivers.

```text
aranorm readability <text> [--json]
```

**Input.** Required positional `text`.

**Output.** Human mode prints the score with label, average sentence length,
average word length, long-word ratio, and complexity marker count. JSON mode
returns exactly those fields: `score`, `label`, `avg_sentence_length`,
`avg_word_length`, `long_word_ratio`, `complexity_marker_count`.

```console
$ aranorm readability "اللغة العربية من أغنى لغات العالم بالمفردات والتراكيب."
Readability   : easy (68.5/100)
Avg sent len  : 8.0 words
Avg word len  : 5.8 chars
Long word %   : 50%
Complexity    : 0 markers
```

#### `detect`

Script/language detection. Classifies the dominant script and flags Arabizi.

```text
aranorm detect <text> [--json]
```

**Input.** Required positional `text`.

**Output.** The `label` is one of `arabic`, `arabizi`, `latin`, `mixed`, or
`numeric`. Human mode prints the label plus Arabic/Latin ratios and an
`arabizi_score`. JSON mode adds `is_arabic`.

```console
$ aranorm detect "صباح الخير ya sadiqi"
Label     : mixed
Arabic    : 53%
Latin     : 47%
Arabizi   : 0.00
```

```console
$ aranorm detect --json "صباح الخير ya sadiqi"
{
  "label": "mixed",
  "arabic_ratio": 0.5294,
  "latin_ratio": 0.4706,
  "arabizi_score": 0.0,
  "is_arabic": false
}
```

#### `tokenize`

Word or sentence tokenization.

```text
aranorm tokenize [text?] [-f FILE] [-s|--sentences] [--split-clitics]
                 [--keep-punctuation] [--json]
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `-s, --sentences` | off | Split into sentences instead of words. |
| `--split-clitics` | off | Split common clitic prefixes/suffixes (e.g. `والـ`, `ـكم`). |
| `--keep-punctuation` | off | Keep punctuation as tokens. |

**Input.** Positional text → `--file` (read as **full content**) → stdin
(full content).

**Output.** Word mode: human output joins tokens with ` | `; JSON prints the
token array. Sentence mode: human prints `[index] sentence` lines; JSON prints
an array of `{"index": n, "text": "..."}`.

```console
$ aranorm tokenize "أهلاً بكم. كيف حالكم؟"
أهلاً | بكم. | كيف | حالكم؟

$ aranorm tokenize -s "أهلاً بكم. كيف حالكم؟"
[0] أهلاً بكم.
[1] كيف حالكم؟
```

### Language identification & similarity

#### `dialect`

Identify the Arabic dialect of a text (MSA, GLF, EGY, LEV, …).

```text
aranorm dialect <text> [--json]
```

**Input.** Required positional `text`.

**Output.** Human mode prints the dialect label, a confidence percentage, and
whether the text is MSA. JSON mode returns `dialect`, `confidence`, `is_msa`.

```console
$ aranorm dialect "شلونك وايد زين"
Dialect    : GLF
Confidence : 95%
Is MSA     : No
```

#### `compare`

Similarity comparison of two texts.

```text
aranorm compare <text_a> <text_b> [--json]
```

**Input.** Two required positional texts.

**Output.** Human mode prints both texts (truncated), a verdict, overall
similarity, Jaccard similarity, content-word Jaccard, and up to ten shared
content words. JSON mode returns the comparator's full result object
(`verdict`, `overall_similarity`, `jaccard_similarity`, `content_jaccard`,
`shared_content_words`, …).

```console
$ aranorm compare "أنا أحب العربية" "أنا أعشق اللغة العربية"
Text A    : أنا أحب العربية
Text B    : أنا أعشق اللغة العربية
Verdict   : somewhat_similar
Overall   : 36%
Jaccard   : 40%
Content   : 25%
Shared KW : العربية
```

### Sentiment & emotions

#### `sentiment`

Polarity analysis (`positive` / `negative` / `neutral`) with matched words.

```text
aranorm sentiment [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**line-oriented**, one text per line) →
stdin (line-oriented).

**Output.** Human mode prints, per text, a preview, the labeled sentiment, a
signed score with confidence, and the positive/negative words found. JSON mode
prints an array of per-text result objects.

```console
$ aranorm sentiment "هذا المنتج رائع جداً وممتاز"
Text      : هذا المنتج رائع جداً وممتاز
Sentiment : ✓ Positive
Score     : +1.000  (confidence 52%)
Positive  : رائع
```

#### `emotions`

Eight-emotion detection: joy, sadness, anger, fear, surprise, disgust,
trust, hope.

```text
aranorm emotions [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints the dominant emotion with confidence, per-emotion
counts, and the matched words per emotion. JSON mode returns the full emotion
result object.

```console
$ aranorm emotions "أشعر بالخوف والرعب من هذا الموقف المرعب المخيف"
Dominant emotion : fear (confidence 1.0000)
Counts           : joy=0, sadness=0, anger=0, fear=1, surprise=0, disgust=0, trust=0, hope=0
Matched words    : fear: المرعب
```

### Content extraction

#### `keywords`

Keyword extraction per text.

```text
aranorm keywords [text?] [-f FILE] [--top-n N] [--json]
```

**Options.** `--top-n N` — number of keywords to return (default `10`).

**Input.** Positional text → `--file` (**line-oriented**) → stdin.

**Output.** Human mode prints a text preview and its comma-separated keywords
per input line. JSON mode prints an array of objects with `text_preview`,
`keywords`, `keyword_count`, and `coverage_ratio`.

```console
$ aranorm keywords --top-n 3 "الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات المتعاقبة"
Text    : الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات المتعاقبة
Keywords: الاقتصاد, تحولات, جذرية
```

#### `summarize`

Extractive summarization.

```text
aranorm summarize [text?] [-f FILE] [--max-sentences N] [--json]
```

**Options.** `--max-sentences N` — maximum sentences in the summary
(default `3`).

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints the compression ratio, top keywords, and the
summary text. JSON mode returns `summary`, `original_sentences`,
`summary_sentences`, `compression_ratio`, and `top_keywords`.

```console
$ aranorm summarize --max-sentences 2 "يعتبر التعليم أساس التقدم في المجتمعات. وبناء عليه تنهض الأمم وتتطور. كما أن التعليم يفتح آفاق المستقبل للشباب. لكن الجهل يؤدي إلى التخلف. لذلك تستثمر الدول في التعليم."
Compression : 5 → 2 sentences (39%)
Keywords    : يعتبر, أساس, التقدم, المجتمعات, وبناء

Summary:
يعتبر التعليم أساس التقدم في المجتمعات. وبناء عليه تنهض الأمم وتتطور.
```

#### `entities`

Named entity extraction: persons, locations, organizations, money, dates,
phone numbers.

```text
aranorm entities [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints per-type counts and each entity as
`[type] text (start:end)` character spans. JSON mode returns the full entity
result object.

```console
$ aranorm entities "التقى الرئيس عبد الفتاح السيسي في القاهرة مع وفد سعودي."
Entities    : 2
Persons     : 1
Locations   : 1
...
Detected entities:
  [person] عبد الفتاح السيسي (13:30)
  [location] القاهرة (34:41)
```

#### `topics`

Topic classification across 13 domains: news, social, legal, medical,
religious, sport, technology, economy, education, history, environment,
culture, community.

```text
aranorm topics [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints the primary topic, its score and confidence, the
topic-word coverage, and the ranked top topics. JSON mode returns the full
classification result.

```console
$ aranorm topics "ارتفعت أسعار النفط في الأسواق العالمية بعد اجتماع أوبك"
Primary topic : economy
Score         : 1.4
...
```

#### `numbers`

Numeric expression extraction & classification — Western and Arabic-Indic
digits, written-out numbers, percentages, and currencies.

```text
aranorm numbers [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints counts per numeric category, whether digit
systems are mixed, the numeric density, and the extracted spans with their
category. JSON mode returns the full numeric result object.

```console
$ aranorm numbers "حققت الشركة أرباحاً بلغت ١٢ مليون دولار بنسبة نمو 15٪"
Western     : 1   Arabic-Indic : 1
Written     : 2   Percentages  : 1
Currency    : 1   Mix systems  : True
Density     : 0.5000
  western_digits   '15'
  arabic_indic_digits '١٢'
  currency         'مليون دولار'
```

### Linguistic analysis

#### `pronouns`

Clitic & attached-pronoun decomposition.

```text
aranorm pronouns [text?] [-f FILE] [--json]
```

**Input.** Positional word/text → `--file` (**one word per line**) → stdin
(one word per line).

**Output.** Human mode prints one line per token:
`token -> stem='…' [role] prefix=[…] suffix=[…]`. JSON mode prints an array of
per-token decomposition objects.

```console
$ aranorm pronouns "كتابهم"
كتابهم -> stem='كتاب' [ضمير الغائبين الجمع المتصل]  prefix=[] suffix=['هم']
```

(The bracketed role is the attached pronoun's grammatical description.)

#### `idioms`

Idiom and fixed-expression detection.

```text
aranorm idioms [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints the idiom count and each idiom as
`[category] text -> canonical (start:end)`. JSON mode returns the full idiom
result object.

```console
$ aranorm idioms "الحمد لله هذا من فضل ربي، وسأعود مرة أخرى بإذن الله"
Idioms found : 3 (3 unique)

Detected idioms:
  [دعاء] الحمد لله -> الحمد لله (0:9)
  [تكرار] مرة أخرى -> مرة أخرى (33:41)
  [دعاء] بإذن الله -> بإذن الله (42:51)
```

#### `roots`

Trilateral-root derivation density profile.

```text
aranorm roots [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints the root count, unique roots, a diversity index
with label, the hapax ratio, and the most frequent root. JSON mode returns the
full root-density result object.

```console
$ aranorm roots "الكتاب مكتوب والكاتب يكتب كتابة جميلة"
Unique roots : 2
Diversity    : 0.5000 (moderate)
Top root     : كتب (x3)
```

#### `complexity`

Morphological complexity and word-length profile.

```text
aranorm complexity [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints a complexity label, average and maximum word
length, the fused-token ratio (words with attached clitics), the word count,
and the word-length distribution. JSON mode returns the full complexity
result object.

```console
$ aranorm complexity "وبالعمل نحقق أحلامنا الكبيرة"
Label           : complex
Avg word length : 6.25
Fused ratio     : 0.7500
Distribution    : 4 letters→1, 7 letters→3
```

### Rhetoric, style & discourse

All commands in this group take `[text?] [-f FILE] [--json]` and read
`--file` as **full content**, falling back to full-content stdin. Human mode
prints a labeled report; `--json` prints the analyzer's result object.

#### `rhythm`

Rhythmic pattern analysis — sajʿ (rhymed prose), parallel balance, repetition,
and poetic line structure.

```text
aranorm rhythm [text?] [-f FILE] [--json]
```

Human output: sentence/word counts, a rhythm index with label, sajʿ signal
count, parallel balance, repetition density, poetic line ratio, and up to five
detected sajʿ pairs with their shared stem.

```console
$ aranorm rhythm "البحرُ هائجٌ، والموجُ لائجٌ، والريحُ عاصفةٌ، والنجمُ طالعٌ"
Rhythm idx  : 0.4000 (rhythmic)
Saj signals : 1
  saj' pair : 'البحرُ هائجٌ' ≈ 'والموجُ لائجٌ' (ائج)
```

#### `figurate`

Rhetorical figure detection — simile (تشبيه), antithesis (طباق), synonymy
(ترادف), and refrain/epizeuxis (تكرار).

```text
aranorm figurate [text?] [-f FILE] [--json]
```

Human output: a figure index with label, detected figure names, per-figure
counts, refrain words, and up to five located occurrences.

```console
$ aranorm figurate "العلم نور والجهل ظلام، وهو كالشمس في السماء"
Figure idx  : 0.3150 (moderate)
Figures     : tibaq, tashbih
Counts      : simile=1 tibaq=1 taraduf=0 takrir=0
  occurrence: tashbih (كالشمس, السماء)
  occurrence: tibaq (نور, ظلام)
```

#### `contrast`

Antonym pair detection (طباق / تضاد).

```text
aranorm contrast [text?] [-f FILE] [--json]
```

Human output: a label, the number of contrast pairs (total and unique), the
contrast density, and each pair rendered as `a ⬌ b`.

```console
$ aranorm contrast "الحياة والاختبار، والنور والظلام، والخير والشر"
Label          : contrastive
Contrast pairs : 2
  - والنور ⬌ والظلام @ 25
  - والخير ⬌ والشر @ 41
```

#### `rquestions`

Rhetorical and interrogative question detection.

```text
aranorm rquestions [text?] [-f FILE] [--json]
```

Human output: the question count with label, inversion vs. direct question
counts, rhetorical marker count, question density per 100 words, and up to ten
located questions with type and span.

```console
$ aranorm rquestions "أليس العلمَ نوراً؟ وهل يجهل قيمته عاقل؟"
Questions    : 2 (interrogative-rich)
Inversion    : 1   Direct       : 0   Markers      : 1
  [inversion] أليس (0:4)
```

#### `anaphora`

Anaphora and cross-sentence cohesion analysis.

```text
aranorm anaphora [text?] [-f FILE] [--json]
```

Human output: a label; counts of attached, independent, demonstrative, and
relative references; lexical re-mentions; a cohesion score; reference density
per 100 words; and sentence/word counts.

```console
$ aranorm anaphora "زار أحمد المتحف ثم اشترى تذكرة وعاد إلى بيته مسروراً"
Label        : moderate
Attached     : 1   Independent  : 0
Cohesion     : 0.1500
```

#### `quotation`

Quotation environment analysis — direct speech, reported speech, citations.

```text
aranorm quotation [text?] [-f FILE] [--json]
```

Human output: the quotation ratio with label, per-type counts, partial
quotation count, and up to eight quoted spans with category.

```console
$ aranorm quotation 'قال المدير: "سنطلق المشروع قريباً" ثم غادر القاعة'
Quotation    : 0.3750 (partially_quoted)
Types        : standard_quotes=1
  standard_quotes  '"سنطلق المشروع قريباً"'
```

#### `loans`

Loanword (Arabicised borrowings) and Latin-script fragment detection.

```text
aranorm loans [text?] [-f FILE] [--json]
```

Human output: loanword count and ratio, Latin token count and ratio, a
foreign-density label, sample words, and up to eight spans with category.

```console
$ aranorm loans "الموضوع نورمال تماماً وأوكيه"
Loanwords    : 2 (0.5000)
Latin        : 0 (0.0000)
Density      : 0.5000 (loanwords)
Samples      : نورمال, أوكيه
  transliterated_loan 'نورمال'
  transliterated_loan 'وأوكيه'
```

#### `fillers`

Filler phrase and word-repetition detection.

```text
aranorm fillers [text?] [-f FILE] [--json]
```

Human output: a label, filler phrase count, repetition count, both densities,
and the located filler and repetition spans with offsets.

```console
$ aranorm fillers "يعني بصراحة الموضوع يعني بصراحة ممتاز جداً جداً"
Label             : filler_heavy
Filler phrases    : 4
Repetitions       : 2
  filler  : 'يعني' @ 0
  filler  : 'صراحة' @ 6
  repeat  : 'جداً' @ 43
```

#### `coherence`

Deterministic coherence score across four weighted axes: lexical repetition,
connectors, sentence balance, and topic consistency.

```text
aranorm coherence [text?] [-f FILE] [--json]
```

Human output: the score with label, sentence count, connective count, and a
weighted per-axis breakdown.

```console
$ aranorm coherence "يعتبر التعليم أساس التقدم. وبناء عليه تنهض الأمم. كما أن التعليم يفتح آفاق المستقبل"
Score      : 0.1600 (fragmented)
Sentences  : 3
Connectives: 0

Axis breakdown:
  lexical_repeat       0.0000 (weight 0.35)
  connectors           0.0000 (weight 0.25)
  sentence_balance     0.9275 (weight 0.15)
  topic_consistency    0.0833 (weight 0.25)
```

#### `style`

Register analysis: formal / colloquial / digital signals.

```text
aranorm style [text?] [-f FILE] [--json]
```

Human output: the style index with label, the three signal scores, matched
formal and colloquial words, elongations, and the emoji count.

```console
$ aranorm style "علاوةً على ذلك، ينبغي الإشارة إلى أن الوزارة أعلنت في بيان رسمي"
Style index : 0.0375 (semi_formal)
Formal      : 0.0833   Colloquial  : 0.0000   Digital     : 0.0000
Formal words: علاوة
```

#### `freqprofile`

Vocabulary frequency & diversity profile.

```text
aranorm freqprofile [text?] [-f FILE] [--top-n N] [--json]
```

**Options.** `--top-n N` — number of top words to list (default `10`).

Human output: token and type counts, TTR, corrected TTR, root TTR, lexical
density, the fitted Zipf exponent (when available), and a ranked top-words
table with relative frequencies.

```console
$ aranorm freqprofile --top-n 3 "اللغة العربية لغة غنية واللغة العربية لغة عريقة واللغة جميلة"
Tokens         : 10
Unique types   : 7
TTR            : 0.7000
Corrected TTR  : 2.2136
Root TTR       : 0.8451

Top words:
  #1   العربيه         x2    (20.00%)
```

#### `textprofile`

Composite one-pass profiling across a 22-axis report; by default it runs
sentiment, coherence, quality, readability, style, emotions, word frequency,
and topics axes together.

```text
aranorm textprofile [text?] [-f FILE] [--axes AXIS ...] [--json]
```

**Options.** `--axes AXIS ...` — restrict the report to a subset of axes,
chosen from: `sentiment`, `coherence`, `quality`, `readability`, `style`,
`emotions`, `word_frequency`, `topics`. Omit the flag for the full report.

Human output: the text preview, one labeled line per axis, and an insights
section with rule-based cross-signal notes (messages are printed in Arabic).

```console
$ aranorm textprofile --axes sentiment style quality "المقال رائع ومكتوب بأسلوب أكاديمي دقيق"
Text     : المقال رائع ومكتوب بأسلوب أكاديمي دقيق
sentiment       positive
style           0.5412 (formal)
quality         good

Insights:
  [high_quality_positive] جودة النص مرتفعة والنبرة محايدة أو إيجابية.
```

### Quality & spelling

#### `quality`

Composite text quality score (0–100) built from 8 weighted components:
spelling, consistency, lexical balance, readability, diacritics, rhetorical
richness, structural balance, and rhetorical depth.

```text
aranorm quality [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints the total score out of 100 with a label, each
component's score and weight, detected issues, and suggestions. JSON mode
returns the full quality result object.

```console
$ aranorm quality "شكرا جزيلا علي الحضور ونتمني لكم التوفيق"
Quality score : 77.38/100 (good)

Components:
  spelling: 74.1 (weight 26%)
  consistency: 95.0 (weight 22%)
  ...

Suggestions:
  * Fix 1 spelling issue(s): علي → على
```

#### `spelling`

Arabic spelling report with suggested corrections.

```text
aranorm spelling [text?] [-f FILE] [--json]
```

**Input.** Positional text → `--file` (**full content**) → stdin.

**Output.** Human mode prints the original and corrected text, total words,
issue counts (total and unique), the correct ratio, each correction as
`word -> replacement (xcount, category)`, and the category distribution.
JSON mode returns the full spelling report object.

```console
$ aranorm spelling "شكرا جزيلا علي الحضور ونتمني لكم التوفيق"
Original   : شكرا جزيلا علي الحضور ونتمني لكم التوفيق
Corrected  : شكراً جزيلا على الحضور ونتمني لكم التوفيق
Words      : 7
Issues     : 1 (1 unique)
Correct    : 86%

Corrections:
  علي -> على (x1, alef)
```

---

## Stop words

### `stopwords`

Stop-word analysis for a single text, with four modes and four scopes.

```text
aranorm stopwords <text> [--mode {remove,extract,highlight,count}]
                  [--scope {universal,msa_only,dialect_aware,custom}] [--json]
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `remove` | `remove` — return the text without stop words; `extract` — list the stop words found; `highlight` — mark stop words inside the text; `count` — count occurrences. |
| `--scope` | `universal` | `universal` — all built-in lists (2,449 terms); `msa_only` — Modern Standard Arabic lists only; `dialect_aware` — include dialectal stop words (Gulf, Egyptian, Levantine, …); `custom` — user-defined registry lists. |

**Input.** Required positional `text` — no file or stdin support. For bulk
stop-word work, pipe texts through `normalize --stop-words` or use
`corpus`.

**Output.** Human mode prints the original text, the processed text, the
sorted stop words found, and the `count / total (percentage)` line. JSON mode
returns `original`, `processed`, `stop_words_found`, and `stats`.

```console
$ aranorm stopwords "أنا سعيد جداً اليوم لأنني نجحت في الاختبار"
Original  : أنا سعيد جداً اليوم لأنني نجحت في الاختبار
Cleaned   : سعيد لانني نجحت الاختبار
Stop words: اليوم, انا, جدا, في
Count     : 4 / 8 (50.0%)
```

```console
$ aranorm stopwords --mode count --scope msa_only "وفي هذا اليوم من الله" --json
```

The size of every stop-word list (msa, egy, glf, lev, …) can be inspected with
[`aranorm info`](#info).

---

## Batch processing

### `batch`

Bulk normalization with export to CSV, JSON, or JSONL.

```text
aranorm batch -f FILE [-o OUTPUT] [--format {csv,json,jsonl}]
              [--preset PRESET] [--workers N] [--batch-size N] [--stream]
              [--skip-errors] [--progress] [--emit-steps-trace]
              [--retry] [--max-retries N]
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `-f, --file FILE` (required) | — | Input file, **one text per line**; empty lines are skipped. |
| `-o, --output FILE` | stdout | Export file. CSV files are written as UTF-8 with BOM; JSON/JSONL as plain UTF-8. |
| `--format {csv,json,jsonl}` | `jsonl` | Export format. `jsonl` writes one JSON object per input line, `json` a single array, `csv` a spreadsheet. |
| `--preset {light,standard,deep,social_media}` | `standard` | Normalization preset (same meanings as [`normalize`](#normalize)). |
| `--workers N` | `1` | Number of parallel workers. |
| `--batch-size N` | `32` | Maximum inputs kept in flight at once. |
| `--stream` | off | Process and export incrementally without loading the whole file into memory (constant-memory mode). Cannot be combined with `--retry`. |
| `--skip-errors` | off | Skip items that fail normalization (warning to stderr) instead of aborting the run. |
| `--progress` | off | Show progress reporting — a `tqdm` progress bar when installed, otherwise a plain console counter. |
| `--emit-steps-trace` | off | Include the per-processor trace in the export (opt-in). |
| `--retry` | off | Retry failed items with bounded retries. |
| `--max-retries N` | `3` | Maximum retries per item under `--retry`. |

**Output.** Exports one record per input line containing the original and
normalized text plus pipeline metadata (dialect, confidence, applied steps).
When `-o` is used, a `Wrote N results to FILE` confirmation is printed. If
items still fail after `--retry`, an error is printed to stderr and the exit
code is `2`.

**Examples**

Export a corpus to JSONL with 8 workers and a progress bar:

```console
$ aranorm batch -f corpus.txt -o normalized.jsonl --preset deep --workers 8 --progress
Wrote 12500 results to normalized.jsonl
```

Stream a very large file with constant memory, skipping bad lines:

```console
$ aranorm batch -f huge.txt --stream --skip-errors --format jsonl -o out.jsonl
```

CSV export for spreadsheets:

```console
$ aranorm batch -f corpus.txt -o results.csv --format csv --preset social_media
```

### `corpus`

Corpus-level stop-word & keyword analysis. One document per line.

```text
aranorm corpus -f FILE [--top-n N] [--json]
```

**Options.** `-f, --file FILE` (required, one document per line); `--top-n N`
number of top content words to report (default `10`).

**Output.** Human mode prints the document count, corpus stop-word ratio,
lexical diversity, the top content words, and the top stop words. JSON mode
returns `document_count`, `corpus_stop_word_ratio`, `lexical_diversity`,
`top_content_words`, and `top_stop_words`.

```console
$ aranorm corpus -f news.txt --top-n 15
Documents          : 420
Stop-word ratio    : 41.3%
...
```

### `profile`

Corpus-level batch analysis report — the one-command corpus audit.

```text
aranorm profile -f FILE [--json]
```

**Input.** Required `--file`, one document per line.

**Output.** Human mode prints text/token/character totals, average quality
score, corpus lexical diversity, unique words, average readability, spelling
issue totals, quality-band and language/dialect distributions, top spelling
issues, and actionable recommendations. JSON mode returns the full report
object.

```console
$ aranorm profile -f corpus.txt --json > corpus-report.json
```

---

## Pipeline management

### `describe`

Describe the pipeline configuration for a preset.

```text
aranorm describe [--preset {light,standard,deep,social_media}] [--json]
```

**Output.** Human mode prints the pipeline class, schema version, preset, and
config fingerprint. JSON mode prints the full versioned configuration
description (sorted keys) — processor chain, options, and fingerprints.

```console
$ aranorm describe --preset deep
Pipeline: ArabicNormalizationPipeline
Schema version: 1
Preset: deep
Config fingerprint: eaadcfcf680c1e0f…
```

### `plugins`

Discover third-party processor plugins through Python entry points.

```text
aranorm plugins [--group GROUP] [--strict] [--json]
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--group` | `aranorm.processors` | Entry-point group to scan. |
| `--strict` | off | Fail (non-zero exit) on the first plugin loading or duplicate error. |

**Output.** Human mode prints the group, an `ok`/`degraded` status, the
discovered processor names, and any per-plugin failures. JSON mode prints the
full discovery report plus `schema_version`.

```console
$ aranorm plugins
Plugin group : aranorm.processors
Status       : ok
Discovered   : <none>
```

### `spec export`

Export a portable `PipelineSpec` JSON document from a preset or config file.

```text
aranorm spec export [--config PATH] [--preset PRESET] [--metadata-json JSON]
                    [-o OUTPUT] [--json]
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--config PATH` | — | JSON/YAML pipeline configuration file. |
| `--preset {light,standard,deep,social_media}` | `standard` | Preset used when `--config` is omitted. |
| `--metadata-json JSON` | — | A JSON object stored verbatim as non-operational metadata (invalid JSON → exit `1`). |
| `-o, --output FILE` | stdout | Write the spec to a file. Without it, the spec JSON is printed to stdout. |
| `--json` | off | After writing with `-o`, print a JSON result envelope (spec content plus `valid: true`). |

```console
$ aranorm spec export --preset social_media -o spec.json
Wrote PipelineSpec to spec.json

$ aranorm spec export --preset light --metadata-json '{"team": "nlp"}'
```

The exported document pins the full configuration plus a config fingerprint,
so a spec can be diffed, reviewed, and pinned in version control.

### `spec validate`

Validate an existing `PipelineSpec` JSON file.

```text
aranorm spec validate <file> [--json]
```

**Input.** Required positional spec file path.

**Output.** Human mode prints `Valid PipelineSpec`, the schema version, and
the config fingerprint. JSON mode prints the full spec with `valid: true`.
Invalid or unreadable files print `Error: invalid PipelineSpec: …` and exit
with code `1`.

```console
$ aranorm spec validate spec.json
Valid PipelineSpec: spec.json
Schema version: 1
Config fingerprint: 63ab7fbab77b8f0f…
```

### `snapshot save`

Save a pipeline configuration snapshot (config + stage order + version) to a
JSON file.

```text
aranorm snapshot save -o OUTPUT [--preset PRESET] [--json]
```

**Options.** `-o, --output FILE` (required) — snapshot JSON file;
`--preset` (default `standard`); `--json` — print the snapshot JSON after
saving.

```console
$ aranorm snapshot save -o snap.json --preset deep
Saved pipeline snapshot to snap.json
AraNorm version: 1.15.0
Preset: deep
```

The snapshot records the schema version, the AraNorm version, the resolved
config, and the pipeline stage order — everything needed to reproduce the run
later.

### `snapshot restore`

Restore (read and verify) a snapshot file.

```text
aranorm snapshot restore -i INPUT [--json]
```

**Options.** `-i, --input FILE` (required) — snapshot JSON file;
`--json` — print the snapshot as a JSON object.

```console
$ aranorm snapshot restore -i snap.json
Snapshot     : snap.json
AraNorm      : 1.15.0
Preset       : deep
Schema       : 1
```

Human mode also prints the stored stage order and any snapshot metadata.

---

## Streaming sessions

Streaming sessions normalize a line-oriented input file to a JSONL output
with a **durable checkpoint** that survives crashes and can resume exactly
where it stopped.

### `stream run` / `stream resume`

Start a new resumable session, or resume one from its checkpoint. Both
sub-commands take exactly the same arguments:

```text
aranorm stream run     --source PATH --output PATH --checkpoint PATH [OPTIONS]
aranorm stream resume  --source PATH --output PATH --checkpoint PATH [OPTIONS]
```

**Options for `run` / `resume`**

| Flag | Default | Description |
|------|---------|-------------|
| `--source PATH` (required) | — | UTF-8 input file, one text item per line. |
| `--output PATH` (required) | — | JSONL output file, appended safely on resume. |
| `--checkpoint PATH` (required) | — | Durable checkpoint JSON file. |
| `--preset {light,standard,deep,social_media}` | `standard` | Normalization preset. |
| `--batch-size N` | `32` | Inputs processed per checkpoint write. |
| `--workers N` | `1` | Number of workers. |
| `--lock` | off | Acquire a local advisory lock for this source/output/checkpoint tuple, preventing concurrent runs. |
| `--max-input-bytes N` | `1073741824` | Refuse source files larger than this (1 GiB by default). |
| `--json` | off | Print the session report as JSON. |

**Session workflow**

```text
                 ┌──────────────┐
   input.jsonl ─▶│  stream run  │──▶ output.jsonl (JSONL, appended)
                 └──────┬───────┘
                        │ writes after every batch
                        ▼
                 ┌──────────────┐     ┌────────────────┐
                 │ checkpoint   │────▶│ stream status  │ (inspect progress)
                 │ next_index … │     └────────────────┘
                 └──────┬───────┘
                        │ crash / Ctrl+C (exit 130)
                        ▼
                 ┌────────────────┐
                 │ stream resume  │──▶ continues from next_index, no duplicates
                 └────────────────┘
```

**Output.** Human mode prints the session type (Processed/Resumed), source,
output, and checkpoint paths, processed count, next index, completion flag,
and whether the run was cancelled. JSON mode returns
`{"ok": true, "report": {...}}`.

```console
$ aranorm stream run --source input.jsonl --output out.jsonl --checkpoint ckpt.json --workers 4
Processed streaming session
Source     : input.jsonl
Output     : out.jsonl
Checkpoint : ckpt.json
Processed  : 12500
Next index : 12500
Completed  : yes

$ aranorm stream status --checkpoint ckpt.json
Checkpoint : ckpt.json
Source     : input.jsonl
Output     : out.jsonl
Next index : 12500
Processed  : 12500
Completed  : yes
```

`stream resume` picks up from the checkpoint's `next_index` — already-written
output lines are never duplicated. A changed or corrupted checkpoint/source
fails with `Error: streaming session failed: …` and exit code `1`.

### `stream status`

Inspect a checkpoint without running anything:

```text
aranorm stream status --checkpoint PATH [--json]
```

**Options.** `--checkpoint PATH` (required) — the checkpoint JSON file.

**Output.** Human mode prints the checkpoint path, the recorded source and
output paths, the next index to process, the number of processed inputs, and
whether the session completed. JSON mode returns the full checkpoint object
(sorted keys).

---

## HTTP server

### `serve`

Run an opt-in, standard-library-only HTTP normalization service.

```text
aranorm serve [--host HOST] [--port PORT] [--config PATH] [--spec PATH]
              [--preset PRESET] [--max-body-bytes N] [--reload-interval SEC]
              [--streaming-enabled] [--streaming-root PATH]
```

**Options**

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address. Keep on localhost unless you put a reverse proxy in front. |
| `--port` | `8765` | Bind port. |
| `--config PATH` | — | JSON/YAML pipeline configuration file. Mutually exclusive with `--spec`. |
| `--spec PATH` | — | A validated `PipelineSpec` JSON file (e.g. from `spec export`). |
| `--preset {light,standard,deep,social_media}` | `standard` | Preset used when neither `--config` nor `--spec` is given. |
| `--max-body-bytes N` | `2000000` | Maximum JSON request body size (2 MB). Larger bodies are rejected. |
| `--reload-interval SEC` | `0.0` | Poll `--config` for changes every N seconds and hot-reload; disabled by default. |
| `--streaming-enabled` | off | Enable the local-files `POST /v1/stream` endpoint (opt-in). |
| `--streaming-root PATH` | — | Restrict `/v1/stream` paths to this existing local directory (requires `--streaming-enabled`; paths outside it get HTTP 403). |

**Behavior.** The server prints `AraNorm server listening on http://HOST:PORT`
to **stderr** and then serves until interrupted (Ctrl+C → exit `130`). All
responses are JSON with `Content-Type: application/json; charset=utf-8` and
`Cache-Control: no-store`. Errors use the envelope
`{"schema_version": 1, "error": {"code": "…", "message": "…"}}`.

**Endpoints**

| Method & path | Purpose | Request body | Success response |
|---------------|---------|--------------|------------------|
| `GET /health/live` | Liveness probe | — | `{"schema_version": 1, "status": "live"}` |
| `GET /health/ready` | Readiness probe | — | Health object (`503` when not ready) |
| `GET /v1/describe` | Pipeline description | — | Runtime description object |
| `POST /v1/normalize` | Normalize one text | `{"text": "…"}` | `{"schema_version": 1, "result": {…}}` |
| `POST /v1/batch` | Normalize many texts | `{"texts": ["…"], "batch_size": 32, "workers": 1}` | `{"schema_version": 1, "count": N, "results": [ … ]}` |
| `POST /v1/stream` | Start/resume a streaming session on server-local files (requires `--streaming-enabled`) | `{"source_path": "…", "output_path": "…", "checkpoint_path": "…", "resume": true, "batch_size": 32, "workers": 1, "max_input_bytes": 1073741824}` | `{"schema_version": 1, "report": {…}}` |

**Examples**

Start the server with a spec and a 10 MB body limit:

```console
$ aranorm serve --spec spec.json --port 9000 --max-body-bytes 10000000
AraNorm server listening on http://127.0.0.1:9000
```

Health checks and pipeline description:

```console
$ curl -s http://127.0.0.1:8765/health/live
{"schema_version":1,"status":"live"}

$ curl -s http://127.0.0.1:8765/v1/describe | jq .
```

Normalize a single text:

```console
$ curl -s -X POST http://127.0.0.1:8765/v1/normalize \
       -H 'Content-Type: application/json' \
       -d '{"text": "شلونـك اليوم؟"}'
{"schema_version":1,"result":{"normalized_text":"شلونك اليوم؟", …}}
```

Normalize a batch:

```console
$ curl -s -X POST http://127.0.0.1:8765/v1/batch \
       -H 'Content-Type: application/json' \
       -d '{"texts": ["أهلا وسهلا", "صباح الخير"], "batch_size": 16, "workers": 2}'
```

---

## Info & version

### `info`

Print the library version and stop-words registry statistics.

```text
aranorm info [--json]
```

**Output.** Human mode prints `AraNorm v…` followed by the size of every
stop-word list. JSON mode returns `{"version": …, "stop_words": {…}}`.

```console
$ aranorm info
AraNorm v1.15.0

Stop-words registry:
  arabizi             :    22
  egy                 :   102
  ...
  total_universal     :  2449
```

### `version`

Print the package version.

```text
aranorm version [--json]
```

**Output.** Human mode prints `aranorm 1.15.0`. JSON mode prints a compact,
sorted object:

```console
$ aranorm version --json
{"package": "aranorm", "schema_version": "1", "version": "1.15.0"}
```

---

## Recipes

Practical shell recipes combining the commands above.

### 1. Social-media cleanup pipeline

Route mixed-script posts through detection, then normalize aggressively and
drop dialectal stop words:

```console
$ aranorm detect "wa9fa m3ak ya akhi 💪"          # → arabizi
$ cat posts.txt \
    | aranorm normalize --preset social_media --clean-emojis \
                        --stop-words --sw-scope dialect_aware \
                        -o clean_posts.txt
```

### 2. Corpus quality audit

One report per corpus plus a per-document deep dive:

```console
$ aranorm profile -f corpus.txt --json > corpus_report.json
$ aranorm corpus -f corpus.txt --top-n 25 > top_words.txt
$ aranorm quality -f worst_doc.txt          # full-content mode, per document
```

### 3. JSONL batch with resume

Large corpora get a crash-safe streaming session instead of a plain batch:

```console
$ aranorm stream run --source corpus.jsonl --output normalized.jsonl \
                     --checkpoint ckpt.json --workers 4 --lock
# …interrupted? resume with identical arguments:
$ aranorm stream resume --source corpus.jsonl --output normalized.jsonl \
                        --checkpoint ckpt.json --workers 4 --lock
$ aranorm stream status --checkpoint ckpt.json --json | jq .report.next_index
```

### 4. Sentiment of a file

Line-oriented mode scores every comment (array order matches input line
order), and `jq` pulls out the negatives with their line numbers:

```console
$ aranorm sentiment -f comments.txt --json \
    | jq -r 'to_entries[] | select(.value.label == "negative") | "line \(.key+1): \(.value.score)"'
```

### 5. Entity extraction to JSON

Extract entities from an article and keep only the people:

```console
$ aranorm entities -f article.txt --json > entities.json
$ jq '[.entities[] | select(.entity_type == "person") | .text]' entities.json
```

### 6. Share a pipeline as a spec, then serve it

Freeze an exact configuration, validate it, and run it as a service:

```console
$ aranorm spec export --preset deep --metadata-json '{"team": "search"}' -o spec.json
$ aranorm spec validate spec.json
$ aranorm serve --spec spec.json --port 8765
```

---

## Shell completion

The CLI does not ship its own completion, but because every command is a
simple sub-command name, a lightweight bash completion is enough. Add this to
your `~/.bashrc`:

```bash
_aranorm_completions() {
  local commands="analyze anaphora batch coherence compare complexity contrast \
corpus describe detect dialect emotions entities figurate fillers freqprofile \
idioms info keywords loans normalize numbers plugins profile pronouns \
quotation readability rquestions roots sentiment serve snapshot spec spelling \
stopwords stream style summarize textprofile tokenize topics version"
  local cur="${COMP_WORDS[COMP_CWORD]}"
  if [ "$COMP_CWORD" -eq 1 ]; then
    COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
  else
    COMPREPLY=( $(compgen -f -- "$cur") )   # fall back to filename completion
  fi
}
complete -F _aranorm_completions aranorm
```

Zsh users can get the same effect with
`autoload -Uz bashcompinit && bashcompinit` before sourcing the snippet.

---

**See also** — [GitHub repository](https://github.com/Alqudimi/AraNorm) ·
[PyPI package](https://pypi.org/project/aranorm/) ·
Library API and presets: see the project `README.md`.
