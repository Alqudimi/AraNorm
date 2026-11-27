"""Example 03: Text analysis features.

Demonstrates text statistics, sentiment analysis, keyword extraction,
readability, summarization, and text comparison.
"""

from aranorm.analysis import (
    ArabicReadabilityAnalyzer,
    ArabicTextSummarizer,
    KeywordExtractor,
    SentimentAnalyzer,
    TextAnalyzer,
    TextComparator,
)

TEXT = """
أعلن الرئيس عن خطة اقتصادية شاملة تهدف إلى تطوير البنية التحتية وتحسين مستوى
المعيشة للمواطنين. وتشمل الخطة الاستثمار في قطاعات التعليم والصحة والتكنولوجيا.
وقال المسؤولون إن هذه الإصلاحات ستساهم في تعزيز النمو الاقتصادي خلال السنوات القادمة.
"""

# ── 1. Text statistics ────────────────────────────────────────────────────────
analyzer = TextAnalyzer()
stats = analyzer.analyze(TEXT)
print("Text Statistics:")
print(f"  Words:            {stats.total_words}")
print(f"  Sentences:        {stats.sentence_count}")
print(f"  Unique words:     {stats.unique_words}")
print(f"  Content words:    {stats.content_words_count} ({stats.content_words_ratio:.0%})")
print(f"  Lexical diversity: {stats.lexical_diversity:.2f}")
print(f"  Complexity:       {stats.estimated_complexity}")
print(f"  Dialect hint:     {stats.dialect_hint}")
print()

# ── 2. Sentiment analysis ─────────────────────────────────────────────────────
sa = SentimentAnalyzer()
samples = [
    "هذا المنتج رائع جداً وأنصح بشرائه",
    "الخدمة كانت سيئة جداً ولن أعود مرة أخرى",
    "الطقس اليوم معتدل",
]
print("Sentiment Analysis:")
for text in samples:
    result = sa.analyze(text)
    print(f"  [{result.label:8}] {result.score:+.2f}  {text}")
print()

# ── 3. Keyword extraction ─────────────────────────────────────────────────────
ke = KeywordExtractor(top_n=5)
keywords = ke.extract(TEXT)
print("Top Keywords:")
for word, score in keywords.keywords:
    print(f"  {word:15} {score:.4f}")
print()

# ── 4. Readability ────────────────────────────────────────────────────────────
ra = ArabicReadabilityAnalyzer()
readability = ra.analyze(TEXT)
print(f"Readability Score: {readability.score:.1f}/100 ({readability.readability_label})")
print()

# ── 5. Summarization ──────────────────────────────────────────────────────────
summarizer = ArabicTextSummarizer(max_sentences=2)
summary = summarizer.summarize(TEXT)
print("Summary (2 sentences):")
print(f"  {summary.summary_text}")
print(f"  (compression: {summary.compression_ratio:.0%})")
print()

# ── 6. Text comparison ────────────────────────────────────────────────────────
comparator = TextComparator()
text1 = "أنا أحب اللغة العربية وأدرسها كل يوم"
text2 = "أنا أعشق اللغة العربية وأتعلمها باستمرار"
similarity = comparator.compare(text1, text2)
print(f"Similarity: {similarity.overall_similarity:.2f} ({similarity.verdict})")
print(f"  Text 1: {text1}")
print(f"  Text 2: {text2}")
