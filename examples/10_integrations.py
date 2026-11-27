"""Example 10: Integrations — pandas and scikit-learn.

Demonstrates the adapters for DataFrame workflows and ML vectorization.
The pandas path requires `pip install pandas`; the scikit-learn stop-word
list needs nothing extra (the adapter is dependency-free by itself).
"""

# ── 1. pandas: normalize a DataFrame column ───────────────────────────────────
try:
    import pandas as pd

    from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig
    from aranorm.integrations import PandasNormalizer

    pipeline = ArabicNormalizationPipeline(PipelineConfig(
        preset="standard",
        stop_words_config=StopWordsConfig(mode="remove", scope="universal"),
    ))
    normalizer = PandasNormalizer(pipeline)

    df = pd.DataFrame({
        "comment": [
            "هذا المنتج رائع جداً 😊 #توصية",
            "الخدمة كانت سيئة جداً ولن أعود https://example.com",
            "شلونكم يا أهل الخليج؟",
            "إزيك عامل إيه النهاردة؟",
            "الأسعار معقولة والجودة ممتازة",
        ],
    })

    # Normalize and expand into separate columns
    enriched = normalizer.normalize_dataframe(df, column="comment")
    expanded = normalizer.expand_results(enriched["comment_normalized"])

    result = pd.concat([enriched, expanded], axis=1)
    print("pandas result:")
    print(result[["comment", "normalized_text", "dialect", "dialect_confidence"]])
    print()

    # Stop-words columns appear when the pipeline has a stop-words config
    print("Stop-words removed (first 2):")
    print(normalizer.apply_stop_words(enriched["comment_normalized"]).head(2))
except ImportError:
    print("pandas is not installed — skipping the pandas section")
    print("Install with: pip install pandas")
print()

# ── 2. scikit-learn: stop words for TF-IDF vectorizers ────────────────────────
from aranorm.integrations import SklearnStopWordsAdapter

adapter = SklearnStopWordsAdapter()

# Modern scikit-learn requires a list (frozensets are rejected)
stop_word_list = adapter.to_sklearn_list(scope="universal")
print(f"scikit-learn stop words: {len(stop_word_list)} (list), "
      f"{len(adapter.to_sklearn_set(scope='universal'))} (frozenset)")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer

    documents = [
        "الاقتصاد ينمو بسرعة في المنطقة العربية",
        "التعليم أساس التقدم في أي دولة",
        "التكنولوجيا تغير شكل الاقتصاد العالمي",
    ]
    vectorizer = TfidfVectorizer(stop_words=stop_word_list, token_pattern=r"[ء-ي]+")
    matrix = vectorizer.fit_transform(documents)
    print(f"Vectorized: {matrix.shape[0]} docs x {matrix.shape[1]} Arabic features")
    print(f"Sample features: {vectorizer.get_feature_names_out()[:5].tolist()}")
except ImportError:
    print("scikit-learn is not installed — skipping the vectorizer section")
    print("Install with: pip install scikit-learn")
