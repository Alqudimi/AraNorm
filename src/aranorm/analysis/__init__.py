"""AraNorm text analysis utilities built on top of the stop-words system."""

from aranorm.analysis.corpus_analyzer import CorpusAnalyzer, CorpusStopWordsBuilder
from aranorm.analysis.keyword_extractor import KeywordExtractor, KeywordResult
from aranorm.analysis.readability import ArabicReadabilityAnalyzer, ReadabilityResult
from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer, SentimentResult
from aranorm.analysis.summarizer import ArabicTextSummarizer, SummaryResult
from aranorm.analysis.text_analyzer import TextAnalyzer, TextAnalysisResult
from aranorm.analysis.text_comparator import TextComparator, SimilarityResult

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
    # Corpus-level
    "CorpusAnalyzer",
    "CorpusStopWordsBuilder",
    # Readability
    "ArabicReadabilityAnalyzer",
    "ReadabilityResult",
    # Summarization
    "ArabicTextSummarizer",
    "SummaryResult",
]
