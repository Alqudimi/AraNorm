"""Third-party NLP library adapters for AraNorm stop words and pipelines."""

from aranorm.integrations.huggingface_integration import HuggingFaceNormalizer
from aranorm.integrations.nltk_stopwords import NLTKStopWordsAdapter
from aranorm.integrations.pandas_integration import PandasNormalizer
from aranorm.integrations.sklearn_stopwords import SklearnStopWordsAdapter
from aranorm.integrations.spacy_stopwords import SpacyStopWordsAdapter

__all__ = [
    "HuggingFaceNormalizer",
    "NLTKStopWordsAdapter",
    "PandasNormalizer",
    "SklearnStopWordsAdapter",
    "SpacyStopWordsAdapter",
]
