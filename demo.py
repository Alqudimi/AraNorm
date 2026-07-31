#!/usr/bin/env python3
"""AraNorm Comprehensive Demo  ·  v1.2.0

Demonstrates all major features:
  1.  Basic pipeline normalization
  2.  Stop-words (modes, scopes, presets)
  3.  Text analysis, readability, and summarization
  4.  Sentiment analysis
  5.  Keyword extraction
  6.  Text comparison
  7.  Dialect identification
  8.  Language / script detection
  9.  Caching & export
  10. Third-party integrations (sklearn, NLTK, spaCy adapters)
  11. PipelineBuilder fluent API
  12. Batch processing with progress

Run with:  python demo.py
"""

import json
from textwrap import indent

# ── Colour helpers (ANSI) ─────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
MAGENTA = "\033[95m"
RED     = "\033[91m"


def header(title: str) -> None:
    width = 70
    print(f"\n{CYAN}{'═' * width}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{CYAN}{'═' * width}{RESET}")


def section(title: str) -> None:
    print(f"\n{YELLOW}{BOLD}▶ {title}{RESET}")


def show(label: str, value: object) -> None:
    if isinstance(value, (set, frozenset)):
        value = sorted(value)
    elif isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, indent=2)
    print(f"  {GREEN}{label}:{RESET} {value}")


# ── Imports ───────────────────────────────────────────────────────────────────
from aranorm import (
    ArabicNormalizationPipeline,
    PipelineBuilder,
    PipelineConfig,
    StopWordsConfig,
    StopWordsRegistry,
    __version__,
)
from aranorm.analysis import (
    ArabicReadabilityAnalyzer,
    ArabicTextSummarizer,
    CorpusAnalyzer,
    KeywordExtractor,
    SentimentAnalyzer,
    TextAnalyzer,
    TextComparator,
)
from aranorm.integrations import (
    NLTKStopWordsAdapter,
    SklearnStopWordsAdapter,
    SpacyStopWordsAdapter,
)
from aranorm.processors import (
    ArabiziStopProcessor,
    ContextAwareProcessor,
    DialectStopProcessor,
    InternetStopProcessor,
    StopWordsProcessor,
)
from aranorm.utils import (
    BatchExporter,
    ConsoleProgressCallback,
    LanguageDetector,
    NormalizationCache,
    compute_stats,
    detect_language,
    word_tokenize,
)


# ═══════════════════════════════════════════════════════════════════════════════
header(f"AraNorm Demo  ·  v{__version__}")


# ── 1. Basic Pipeline ─────────────────────────────────────────────────────────
header("1. Basic Pipeline Normalization")

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))

section("Standard preset")
result = pipeline.process("شلونك حبيبي؟ وايد زين مبسوط")
show("normalized_text", result.normalized_text)
show("dialect", result.dialect)
show("dialect_confidence", result.dialect_confidence)
show("processing_time_ms", result.processing_time_ms)
show("applied_steps", result.applied_steps[:5])
show("repr", repr(result))

section("Deep preset — diacritics + repeated chars")
deep = ArabicNormalizationPipeline(PipelineConfig(preset="deep"))
r_deep = deep.process("مَرْحَبًا بِكُمْ يااااا إخوتي")
show("normalized", r_deep.normalized_text)

section("Social-media preset — URLs + emojis + mentions")
social = ArabicNormalizationPipeline(PipelineConfig(preset="social_media"))
r_social = social.process("RT @أحمد: شلونك ياا؟ 😊 https://t.co/abc #السعودية")
show("normalized", r_social.normalized_text)


# ── 2. Stop-words ─────────────────────────────────────────────────────────────
header("2. Stop-Words — Modes & Scopes")

registry = StopWordsRegistry()
text_sw = "أنا والله يعني سعيد جداً اليوم 😊"

for mode in ("remove", "extract", "highlight", "count"):
    section(f"mode='{mode}'")
    cfg = StopWordsConfig(mode=mode, scope="universal", remove_filler=True)
    proc = StopWordsProcessor(config=cfg, registry=registry)
    r = proc.process_detailed(text_sw)
    show("processed_text", r.processed_text)
    show("stop_words_found", r.stop_words_found)

section("Dialect-aware scope (EGY + GLF)")
cfg_d = StopWordsConfig(mode="remove", scope="dialect_aware",
                        dialects=frozenset(["EGY", "GLF"]))
proc_d = StopWordsProcessor(config=cfg_d, registry=registry)
show("result", proc_d.process("أنا كده الحين سعيد جداً"))

section("Full pipeline with stop-words")
config_sw = PipelineConfig(
    preset="standard",
    stop_words_config=StopWordsConfig(
        mode="remove", scope="universal",
        remove_filler=True, preserve_negation=True,
    ),
)
pipeline_sw = ArabicNormalizationPipeline(config_sw)
result_sw = pipeline_sw.process("أنا والله يعني سعيد جداً اليوم")
show("stop_words_removed", result_sw.stop_words_removed)
show("stop_words_found", result_sw.stop_words_found)
show("stop_words_stats", result_sw.stop_words_stats)

section("StopWordsConfig presets")
show("for_social_media().mode", StopWordsConfig.for_social_media().mode)
show("for_dialect('EGY','GLF').dialects", sorted(StopWordsConfig.for_dialect("EGY", "GLF").dialects))
show("count_only().mode", StopWordsConfig.count_only().mode)


# ── 3. Text Analysis ─────────────────────────────────────────────────────────
header("3. Text Analysis")

analyzer = TextAnalyzer()
long_text = "الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات المتعاقبة والتغيرات المتسارعة"

section("TextAnalyzer.analyze()")
analysis = analyzer.analyze(long_text)
show("total_words", analysis.total_words)
show("stop_words_count", analysis.stop_words_count)
show("stop_words_ratio", analysis.stop_words_ratio)
show("content_words", analysis.content_words[:5])
show("estimated_complexity", analysis.estimated_complexity)
show("lexical_diversity", analysis.lexical_diversity)
show("dialect_hint", analysis.dialect_hint)

section("TextStats (compute_stats)")
stats = compute_stats(long_text)
show("word_count", stats.word_count)
show("avg_word_length", stats.avg_word_length)
show("readability_score", stats.readability_score)
show("readability_label", stats.readability_label)


# ── 4. Readability ────────────────────────────────────────────────────────────
header("4. Readability Analysis")

ra = ArabicReadabilityAnalyzer()

texts_for_read = [
    "الكتاب جيد. أحببته.",
    "أعلن الرئيس عن خطة اقتصادية شاملة تستهدف تحقيق نمو مستدام في ظل التحديات الراهنة.",
    "في إطار السياق السوسيو-اقتصادي المعاصر وتداعياته المتشعبة على المنظومة التنموية الشاملة.",
]

for t in texts_for_read:
    r = ra.analyze(t)
    section(f"Score={r.score:.1f}  [{r.readability_label}]")
    show("text_preview", t[:60])
    show("avg_sentence_length", r.avg_sentence_length)
    show("avg_word_length", r.avg_word_length)
    show("complexity_markers", r.complexity_marker_count)


# ── 5. Summarization ──────────────────────────────────────────────────────────
header("5. Extractive Summarization")

article = (
    "يشهد الاقتصاد العالمي تحولات جذرية تؤثر على جميع الدول. "
    "الأزمات المالية المتكررة تدفع الحكومات إلى إعادة النظر في سياساتها. "
    "التكنولوجيا باتت محركاً رئيسياً للنمو الاقتصادي في العصر الحديث. "
    "الطاقة المتجددة تحتل مكانة متصاعدة في خطط التنمية المستدامة. "
    "التحديات البيئية تفرض نفسها على صانعي القرار حول العالم. "
    "التعاون الدولي ضرورة حتمية لمواجهة الأزمات المشتركة. "
    "الذكاء الاصطناعي يفتح آفاقاً جديدة في مجالات عديدة. "
)

summarizer = ArabicTextSummarizer(max_sentences=3)
summary = summarizer.summarize(article)
section("Summary (3 sentences)")
show("original sentences", summary.original_sentence_count)
show("summary sentences", summary.summary_sentence_count)
show("compression_ratio", f"{summary.compression_ratio:.0%}")
show("top_keywords", summary.top_keywords[:5])
show("summary_text", summary.summary_text)


# ── 6. Sentiment Analysis ─────────────────────────────────────────────────────
header("6. Sentiment Analysis")

sa = SentimentAnalyzer()
sentiment_samples = [
    "هذا المنتج رائع جداً وممتاز بكل المقاييس",
    "لا أحب هذا الفيلم إطلاقاً، كان مملاً ومزعجاً",
    "الطقس اليوم عادي لا سيء ولا جيد",
    "ما شاء الله عليهم، إنجاز رائع وعمل مبدع",
]

for text in sentiment_samples:
    r = sa.analyze(text)
    icon = {"positive": "✓", "negative": "✗", "neutral": "–"}.get(r.label, "?")
    print(f"  {icon} [{r.label:>8}] score={r.score:+.3f}  conf={r.confidence:.0%}  | {text[:50]}")

show("lexicon_stats", sa.get_lexicon_stats())


# ── 7. Keyword Extraction ─────────────────────────────────────────────────────
header("7. Keyword Extraction")

kw = KeywordExtractor(top_n=7)
kw_text = "الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات المتعاقبة والتغيرات المتسارعة في التكنولوجيا"
kw_result = kw.extract(kw_text)
section("Single text")
show("top_keywords", kw_result.top_keywords)
show("content_word_count", kw_result.content_word_count)
show("coverage_ratio", kw_result.coverage_ratio)


# ── 8. Text Comparison ────────────────────────────────────────────────────────
header("8. Text Comparison & Similarity")

comp = TextComparator()
pairs = [
    ("أنا سعيد اليوم",          "أنا فرحان اليوم"),
    ("الاقتصاد العالمي",        "الاقتصاد العالمي يتحسن"),
    ("مرحباً بكم في العالم",    "أهلاً وسهلاً يا أصدقاء"),
]

for a, b in pairs:
    r = comp.compare(a, b)
    section(f"'{a[:30]}' ↔ '{b[:30]}'")
    show("verdict", r.verdict)
    show("overall_similarity", r.overall_similarity)
    show("shared_content_words", list(r.shared_content_words)[:5])


# ── 9. Dialect Identification ─────────────────────────────────────────────────
header("9. Dialect Identification")

from aranorm.stages import DialectIdentifier

identifier = DialectIdentifier()
dialect_samples = {
    "EGY": "عايز أروح المطار دلوقتي ازاي",
    "GLF": "شلونك وايد زين الحين أبغى شيء",
    "LEV": "شو بدك تعمل هلق كتير متعب",
    "MSA": "أعلن الرئيس عن خطة لتطوير القطاع الاقتصادي",
}

for expected, text in dialect_samples.items():
    r = identifier.identify(text)
    status = "✓" if r.dialect_label == expected else "✗"
    print(f"  {status} [{expected}→{r.dialect_label:>3}] conf={r.confidence_score:.2f} | {text[:40]!r}")


# ── 10. Language Detection ────────────────────────────────────────────────────
header("10. Language / Script Detection")

detector = LanguageDetector()
ld_samples = [
    "شلونك حبيبي؟",
    "Hello world!",
    "7abibi shloak 3ala ra7tak",
    "أنا 7abibi good",
    "مرحبا hello mixed",
]

for text in ld_samples:
    r = detector.detect_detailed(text)
    print(f"  [{r.label:>8}] arabic={r.arabic_ratio:.0%}  latin={r.latin_ratio:.0%}  arabizi={r.arabizi_score:.2f}  | {text!r}")


# ── 11. Caching & Export ──────────────────────────────────────────────────────
header("11. Caching & Batch Export")

section("NormalizationCache")
base_pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
cache = NormalizationCache(base_pipeline, maxsize=100)

texts_to_cache = ["مرحباً بكم", "شلونك حبيبي", "مرحباً بكم"]  # 3rd is a cache hit
for t in texts_to_cache:
    r = cache.process(t)
    print(f"  [{r.dialect or 'UNK'}] {r.normalized_text!r}")

show("cache_stats", cache.stats())

section("BatchExporter — CSV string (first 300 chars)")
results_batch = base_pipeline.process_batch(
    ["أنا سعيد", "أنا حزين", "أنا بخير"]
)
exporter = BatchExporter(results_batch, fields=["original_text", "normalized_text", "dialect"])
csv_str = exporter.to_csv_string()
print(indent(csv_str[:300], "  "))

section("BatchExporter — JSONL (first 2 lines)")
jsonl = exporter.to_jsonl_string()
for line in jsonl.splitlines()[:2]:
    print(f"  {line[:100]}")


# ── 12. PipelineBuilder ───────────────────────────────────────────────────────
header("12. PipelineBuilder Fluent API")

custom_pipeline = (
    ArabicNormalizationPipeline.builder()
    .add_cleaner(urls=True, html=True, emojis=True)
    .add_normalizer(normalize_alef=True, normalize_diacritics=True, normalize_tatweel=True)
    .add_dialect_processor(normalize_to="msa", supported_dialects=["EGY", "GLF", "LEV"])
    .add_stop_words(mode="remove", scope="universal", remove_filler=True)
    .build()
)
r_custom = custom_pipeline.process("أنا والله عايز أروح المطار دلوقتي")
show("normalized", r_custom.normalized_text)
show("msa_text", r_custom.msa_text)
show("dialect", r_custom.dialect)
show("stop_words_removed", r_custom.stop_words_removed)


# ── 13. Integrations ─────────────────────────────────────────────────────────
header("13. Third-party Integrations")

section("scikit-learn — SklearnStopWordsAdapter")
sklearn_adapter = SklearnStopWordsAdapter(registry)
sw_set = sklearn_adapter.to_sklearn_set()
show("type", type(sw_set).__name__)
show("len", len(sw_set))
show("sample (first 5)", sorted(sw_set)[:5])

section("NLTK — NLTKStopWordsAdapter")
nltk_adapter = NLTKStopWordsAdapter(registry)
nltk_list = nltk_adapter.to_nltk_list()
show("len", len(nltk_list))
show("sample (first 5)", nltk_list[:5])
filtered = nltk_adapter.filter_tokens(["أنا", "سعيد", "اليوم", "جداً"])
show("filter_tokens result", filtered)

section("spaCy — SpacyStopWordsAdapter.to_spacy_set()")
spacy_adapter = SpacyStopWordsAdapter(registry)
spacy_set = spacy_adapter.to_spacy_set()
show("len", len(spacy_set))
show("sample (first 5)", sorted(spacy_set)[:5])


# ── 14. PipelineConfig utilities ─────────────────────────────────────────────
header("14. PipelineConfig Utilities")

section("copy_with() — immutable variant")
base_cfg = PipelineConfig(preset="standard")
variant = base_cfg.copy_with(preset="deep", clean_emojis=True)
show("base.preset", base_cfg.preset.value)
show("variant.preset", variant.preset.value)
show("variant.clean_emojis", variant.clean_emojis)

section("to_json() / from_json() round-trip")
json_str = base_cfg.to_json()
restored = PipelineConfig.from_json(json_str)
show("round-trip ok", restored.preset == base_cfg.preset)

section("validate() — consistency check")
try:
    PipelineConfig(
        stop_words_config=StopWordsConfig(mode="remove", scope="dialect_aware")
    ).validate()
except Exception as e:
    show("ConfigurationError raised", str(e)[:80])

section("repr()")
show("repr", repr(base_cfg))


# ── 15. Batch Processing with Progress ───────────────────────────────────────
header("15. Batch Processing with Progress Callback")

batch_texts = [f"نص رقم {i} باللغة العربية" for i in range(20)]
callback = ConsoleProgressCallback(total=len(batch_texts), width=30)
light_pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))
batch_results = light_pipeline.process_batch(
    batch_texts,
    n_workers=2,
    progress_callback=callback,
)
show("batch_count", len(batch_results))
show("first_result", batch_results[0].normalized_text)


# ── 16. Corpus Analysis ──────────────────────────────────────────────────────
header("16. Corpus Analysis")

corpus = [
    "الاقتصاد العالمي يشهد تحولات جذرية",
    "التكنولوجيا تغير وجه العالم الحديث",
    "الذكاء الاصطناعي يفتح آفاقاً جديدة",
    "التنمية المستدامة هدف رئيسي للحكومات",
    "التعاون الدولي ضرورة لمواجهة الأزمات",
]
ca = CorpusAnalyzer()
corpus_result = ca.analyze(corpus)
section("CorpusAnalyzer.analyze()")
show("document_count", corpus_result.document_count)
show("corpus_stop_word_ratio", corpus_result.corpus_stop_word_ratio)
show("top_content_words", [w for w, _ in corpus_result.top_content_words[:5]])
show("lexical_diversity", corpus_result.lexical_diversity)


# ── Done ──────────────────────────────────────────────────────────────────────
header(f"Demo complete ✓  (AraNorm v{__version__})")
print(f"\n{GREEN}All features demonstrated successfully!{RESET}\n")
