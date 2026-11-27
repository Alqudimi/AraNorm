"""AraNorm text analysis utilities built on top of the stop-words system."""

from aranorm.analysis.corpus_analyzer import CorpusAnalyzer, CorpusStopWordsBuilder
from aranorm.analysis.keyword_extractor import KeywordExtractor, KeywordResult
from aranorm.analysis.readability import ArabicReadabilityAnalyzer, ReadabilityResult
from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer, SentimentResult
from aranorm.analysis.summarizer import ArabicTextSummarizer, SummaryResult
from aranorm.analysis.text_analyzer import TextAnalyzer, TextAnalysisResult
from aranorm.analysis.similarity_matrix import (
    ClosestPair,
    SimilarityMatrixResult,
    TextSimilarityMatrix,
)
from aranorm.analysis.text_comparator import TextComparator, SimilarityResult
from aranorm.analysis.text_diff_report import DiffToken, TextDiffReport, TextDiffResult
from aranorm.analysis.entity_analyzer import EntityAnalyzer, EntityAnalysisResult, EntitySpan
from aranorm.analysis.topic_classifier import TopicClassifier, TopicClassificationResult, TopicScore
from aranorm.analysis.pronoun_analyzer import CliticSegment, PronounAnalyzer, PronounAnalysisResult
from aranorm.analysis.idiom_analyzer import IdiomAnalyzer, IdiomAnalysisResult, IdiomSpan
from aranorm.analysis.word_frequency import (
    FrequencyEntry,
    WordFrequencyProfiler,
    WordFrequencyResult,
)
from aranorm.analysis.coherence_score import (
    CoherenceAnalyzer,
    CoherenceBreakdown,
    CoherenceScore,
    analyze_coherence,
)
from aranorm.analysis.style_analyzer import (
    StyleAnalyzer,
    StyleAnalysisResult,
    StyleSignals,
    analyze_style,
)
from aranorm.analysis.emotion_analyzer import (
    EmotionAnalyzer,
    EmotionAnalysisResult,
    EmotionCounts,
    analyze_emotions,
)
from aranorm.analysis.profiler import (
    AnalysisProfiler,
    ProfilerInsight,
    ProfilerResult,
    profile_text,
)

__all__ = [
    # Text analysis
    "TextAnalyzer",
    "TextAnalysisResult",
    # Sentiment
    "SentimentAnalyzer",
    "SentimentResult",
    # Keywords
    "KeywordExtractor",
    "KeywordResult",
    # Comparison
    "TextComparator",
    "SimilarityResult",
    # Pairwise similarity
    "TextSimilarityMatrix",
    "SimilarityMatrixResult",
    "ClosestPair",
    # Diff reports
    "TextDiffReport",
    "TextDiffResult",
    "DiffToken",
    # Corpus-level
    "CorpusAnalyzer",
    "CorpusStopWordsBuilder",
    # Readability
    "ArabicReadabilityAnalyzer",
    "ReadabilityResult",
    # Summarization
    "ArabicTextSummarizer",
    "SummaryResult",
    # Named-entity analysis
    "EntityAnalyzer",
    "EntityAnalysisResult",
    "EntitySpan",
    # Topic classification
    "TopicClassifier",
    "TopicClassificationResult",
    "TopicScore",
    # Pronoun / clitic decomposition
    "PronounAnalyzer",
    "PronounAnalysisResult",
    "CliticSegment",
    # Idiom detection
    "IdiomAnalyzer",
    "IdiomAnalysisResult",
    "IdiomSpan",
    # Word frequency profiling
    "WordFrequencyProfiler",
    "WordFrequencyResult",
    "FrequencyEntry",
    # Coherence scoring
    "CoherenceAnalyzer",
    "CoherenceScore",
    "CoherenceBreakdown",
    "analyze_coherence",
    # Style / register analysis
    "StyleAnalyzer",
    "StyleAnalysisResult",
    "StyleSignals",
    "analyze_style",
    # Emotion detection
    "EmotionAnalyzer",
    "EmotionAnalysisResult",
    "EmotionCounts",
    "analyze_emotions",
    # Composite profiling
    "AnalysisProfiler",
    "ProfilerResult",
    "ProfilerInsight",
    "profile_text",
]
