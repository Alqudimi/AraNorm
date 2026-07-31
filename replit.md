# AraNorm

**AraNorm** is a production-grade, composable Arabic text normalization library for Python. It supports Modern Standard Arabic (MSA) and 8+ dialects (Egyptian, Gulf, Levantine, Iraqi, Maghrebi, Tunisian, Yemeni, Sudanese).

## Version

`1.2.0`

## Architecture

```
src/aranorm/
├── __init__.py              # Public API surface
├── cli.py                   # Command-line interface (aranorm CLI)
├── core/
│   ├── base.py              # Processor + ProcessorContext abstractions
│   ├── config.py            # PipelineConfig + Preset + DialectTarget enums
│   ├── pipeline.py          # ArabicNormalizationPipeline + PipelineBuilder
│   ├── registry.py          # ProcessorRegistry + ProcessorFactory
│   ├── stop_words_config.py # StopWordsConfig immutable dataclass
│   └── stop_words_registry.py # Trie-backed stop-word registry
├── analysis/
│   ├── corpus_analyzer.py   # CorpusAnalyzer + CorpusStopWordsBuilder
│   ├── keyword_extractor.py # KeywordExtractor (TF-IDF)
│   ├── readability.py       # ArabicReadabilityAnalyzer (FARS score)
│   ├── sentiment_analyzer.py # SentimentAnalyzer (lexicon-based)
│   ├── summarizer.py        # ArabicTextSummarizer (extractive)
│   ├── text_analyzer.py     # TextAnalyzer (stop-word density, complexity)
│   └── text_comparator.py   # TextComparator (Jaccard/cosine similarity)
├── exceptions/
│   └── errors.py            # Full exception hierarchy
├── integrations/
│   ├── huggingface_integration.py # HuggingFaceNormalizer
│   ├── nltk_stopwords.py    # NLTKStopWordsAdapter
│   ├── pandas_integration.py # PandasNormalizer
│   ├── sklearn_stopwords.py # SklearnStopWordsAdapter
│   └── spacy_stopwords.py   # SpacyStopWordsAdapter
├── models/
│   ├── _transformers_model.py # TransformersSeq2SeqModel (lazy, batch)
│   ├── coda_model.py        # CODAModel wrapper
│   ├── dialect_id_model.py  # DialectIDModel (CAMeL Tools)
│   └── msa_model.py         # MSAModel wrapper
├── processors/              # 25+ individual text processors
├── stages/
│   ├── cleaner.py           # ContentCleaner stage
│   ├── dialect_id.py        # DialectIdentifier stage
│   ├── dialect_norm.py      # DialectNormalizer + strategies
│   ├── morphological.py     # MorphologicalProcessor (injected)
│   ├── normalizer.py        # OrthographicNormalizer stage
│   └── stop_words_stage.py  # StopWordsStage
└── utils/
    ├── cache.py             # NormalizationCache (LRU, thread-safe)
    ├── chunker.py           # TextChunker
    ├── exporters.py         # BatchExporter (CSV / JSON / JSONL)
    ├── helpers.py           # contains_arabic, is_arabic_char
    ├── language_detector.py # LanguageDetector (script detection)
    ├── normalizer_utils.py  # Low-level normalization functions
    ├── progress.py          # ProgressCallback + ConsoleProgressCallback
    ├── root_extractor.py    # RootExtractor
    ├── stemmer.py           # ArabicStemmer
    ├── text_stats.py        # TextStats + compute_stats
    ├── tokenizer.py         # ArabicTokenizer
    └── validators.py        # validate_text
```

## Running the demo

```bash
python demo.py
```

## Running tests

```bash
python -m pytest tests/ -v
```

## CLI quick reference

```bash
aranorm normalize "شلونك حبيبي؟"
aranorm normalize --preset deep --file input.txt --output out.txt --workers 4
aranorm batch --file texts.txt --format csv --output results.csv
aranorm sentiment "هذا المنتج رائع جداً"
aranorm keywords "الاقتصاد العالمي"
aranorm readability "أعلن الرئيس عن خطة اقتصادية"
aranorm summarize --max-sentences 3 "نص طويل..."
aranorm dialect "شلونك وايد زين"
aranorm detect "7abibi shloak"
aranorm compare "أنا أحب العربية" "أنا أعشق اللغة العربية"
aranorm corpus --file corpus.txt
aranorm version
aranorm info
```

## User preferences

- Always use clean, type-annotated Python (3.9+)
- Follow Google-style docstrings with examples
- No mandatory external dependencies in the core; all ML/NLP integrations are optional
- Keep the `Processor` interface minimal: `process(text, context) → str`
- File encoding: UTF-8 everywhere; CSV export uses UTF-8-sig for Excel compatibility
