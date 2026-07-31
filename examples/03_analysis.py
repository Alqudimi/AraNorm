"""Example 03: Text analysis features.

Demonstrates sentiment analysis, keyword extraction, readability, and summarization.
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
print(f"  Words: {stats.word_count}")
print(f"  Sentences: {stats.sentence_count}")
print(f"  Unique words: {stats.unique_words}")
print(f"  Lexical diversity: {stats.lexical_diversity:.2f}")
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
ke = KeywordExtractor()
keywords = ke.extract(TEXT, top_k=5)
print("Top Keywords:")
for word, score in keywords:
    print(f"  {word:15} {score:.4f}")
print()

# ── 4. Readability ────────────────────────────────────────────────────────────
ra = ArabicReadabilityAnalyzer()
score = ra.score(TEXT)
print(f"Readability Score: {score:.1f}/100")
print()

# ── 5. Summarization ──────────────────────────────────────────────────────────
summarizer = ArabicTextSummarizer()
summary = summarizer.summarize(TEXT, max_sentences=2)
print("Summary (2 sentences):")
print(f"  {summary}")
print()

# ── 6. Text comparison ────────────────────────────────────────────────────────
comparator = TextComparator()
text1 = "أنا أحب اللغة العربية وأدرسها كل يوم"
text2 = "أنا أعشق اللغة العربية وأتعلمها باستمرار"
sim = comparator.similarity(text1, text2)
print(f"Similarity: {sim:.2f}")
print(f"  Text 1: {text1}")
print(f"  Text 2: {text2}")
