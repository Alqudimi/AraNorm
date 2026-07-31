"""AraNorm command-line interface.

Usage examples::

    # Normalize a single text
    aranorm normalize "شلونك حبيبي؟"

    # Normalize with a specific preset
    aranorm normalize --preset deep "مَرْحَبًا"

    # Process a file (one text per line)
    aranorm normalize --file input.txt --output output.txt

    # Show stop-word stats for a text
    aranorm stopwords "أنا سعيد جداً اليوم"

    # Show library version and stats
    aranorm info

    # Analyze a text
    aranorm analyze "النص الذي تريد تحليله"

    # Identify dialect
    aranorm dialect "شلونك وايد زين"

    # Extract keywords
    aranorm keywords "الاقتصاد العالمي يشهد تحولات جذرية في ظل الأزمات المتعاقبة"

    # Compare two texts for similarity
    aranorm compare "أنا أحب العربية" "أنا أعشق اللغة العربية"

    # Tokenize text
    aranorm tokenize "أهلاً بكم. كيف حالكم؟"

    # Analyze sentiment
    aranorm sentiment "هذا المنتج رائع جداً وممتاز"
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional


# ── Sub-command handlers ───────────────────────────────────────────────────────

def _cmd_normalize(args: argparse.Namespace) -> int:
    """Handle the ``normalize`` sub-command."""
    from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

    sw_config = None
    if args.stop_words:
        sw_config = StopWordsConfig(mode="remove", scope=args.sw_scope or "universal")

    config = PipelineConfig(
        preset=args.preset,
        dialect_target=args.dialect_target,
        remove_diacritics=not args.keep_diacritics,
        clean_urls=not args.keep_urls,
        clean_emojis=args.clean_emojis,
        stop_words_config=sw_config,
    )
    pipeline = ArabicNormalizationPipeline(config)

    texts: List[str] = []

    if args.text:
        texts = [args.text]
    elif args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                texts = [line.rstrip("\n") for line in fh if line.strip()]
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        texts = [line.rstrip("\n") for line in sys.stdin if line.strip()]

    n_workers = getattr(args, "workers", 1) or 1
    results = pipeline.process_batch(texts, n_workers=n_workers)

    out = sys.stdout
    if args.output:
        try:
            out = open(args.output, "w", encoding="utf-8")  # noqa: WPS515
        except OSError as exc:
            print(f"Error: cannot write to {args.output}: {exc}", file=sys.stderr)
            return 1

    try:
        if args.json:
            output_data = []
            for r in results:
                entry: dict = {
                    "original": r.original_text,
                    "normalized": r.normalized_text,
                    "dialect": r.dialect,
                    "dialect_confidence": r.dialect_confidence,
                }
                if r.stop_words_removed is not None:
                    entry["stop_words_removed"] = r.stop_words_removed
                output_data.append(entry)
            json.dump(output_data, out, ensure_ascii=False, indent=2)
            out.write("\n")
        else:
            for r in results:
                out.write(r.normalized_text + "\n")
    finally:
        if args.output:
            out.close()

    return 0


def _cmd_stopwords(args: argparse.Namespace) -> int:
    """Handle the ``stopwords`` sub-command."""
    from aranorm import ArabicNormalizationPipeline, PipelineConfig, StopWordsConfig

    config = PipelineConfig(
        stop_words_config=StopWordsConfig(
            mode=args.mode,
            scope=args.scope,
        )
    )
    pipeline = ArabicNormalizationPipeline(config)
    result = pipeline.process(args.text)

    if args.json:
        data = {
            "original": result.original_text,
            "processed": result.stop_words_removed,
            "stop_words_found": sorted(result.stop_words_found or []),
            "stats": result.stop_words_stats,
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Original  : {result.original_text}")
        print(f"Cleaned   : {result.stop_words_removed}")
        print(f"Stop words: {', '.join(sorted(result.stop_words_found or []))}")
        stats = result.stop_words_stats or {}
        print(f"Count     : {stats.get('count', 0)} / {stats.get('total_tokens', 0)} "
              f"({stats.get('percentage', 0.0):.1f}%)")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    """Handle the ``analyze`` sub-command."""
    from aranorm.utils.text_stats import compute_stats

    stats = compute_stats(args.text)
    if args.json:
        data = {
            "word_count": stats.word_count,
            "arabic_word_count": stats.arabic_word_count,
            "sentence_count": stats.sentence_count,
            "avg_word_length": stats.avg_word_length,
            "avg_sentence_length": stats.avg_sentence_length,
            "vocabulary_size": stats.vocabulary_size,
            "type_token_ratio": stats.type_token_ratio,
            "arabic_ratio": stats.arabic_ratio,
            "diacritic_ratio": stats.diacritic_ratio,
            "readability_score": stats.readability_score,
            "readability_label": stats.readability_label,
            "top_words": stats.top_words,
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Word count         : {stats.word_count}")
        print(f"Arabic words       : {stats.arabic_word_count}")
        print(f"Sentences          : {stats.sentence_count}")
        print(f"Avg word length    : {stats.avg_word_length}")
        print(f"Avg sentence len   : {stats.avg_sentence_length}")
        print(f"Vocabulary size    : {stats.vocabulary_size}")
        print(f"Type-token ratio   : {stats.type_token_ratio}")
        print(f"Arabic ratio       : {stats.arabic_ratio:.2%}")
        print(f"Readability        : {stats.readability_label} ({stats.readability_score:.0f}/100)")
        if stats.top_words:
            print("\nTop words:")
            for word, count in stats.top_words[:10]:
                print(f"  {word}: {count}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    """Handle the ``info`` sub-command."""
    from aranorm import __version__
    from aranorm.core.stop_words_registry import StopWordsRegistry

    reg = StopWordsRegistry()
    stats = reg.get_stats()

    if args.json:
        data = {"version": __version__, "stop_words": stats}
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"AraNorm v{__version__}")
        print("\nStop-words registry:")
        for key, count in sorted(stats.items()):
            print(f"  {key:<20}: {count:>5}")
    return 0


def _cmd_dialect(args: argparse.Namespace) -> int:
    """Handle the ``dialect`` sub-command."""
    from aranorm.stages.dialect_id import DialectIdentifier

    identifier = DialectIdentifier()
    result = identifier.identify(args.text)

    if args.json:
        data = {
            "dialect": result.dialect_label,
            "confidence": result.confidence_score,
            "is_msa": result.is_msa,
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Dialect    : {result.dialect_label}")
        print(f"Confidence : {result.confidence_score:.0%}")
        print(f"Is MSA     : {'Yes' if result.is_msa else 'No'}")
    return 0


def _cmd_keywords(args: argparse.Namespace) -> int:
    """Handle the ``keywords`` sub-command."""
    from aranorm.analysis.keyword_extractor import KeywordExtractor

    extractor = KeywordExtractor(top_n=args.top_n)

    texts: List[str] = []
    if args.text:
        texts = [args.text]
    elif args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                texts = [line.rstrip("\n") for line in fh if line.strip()]
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    else:
        texts = [line.rstrip("\n") for line in sys.stdin if line.strip()]

    results = extractor.extract_batch(texts)

    if args.json:
        output_data = [
            {
                "text_preview": r.original_text[:80],
                "keywords": r.top_keywords,
                "keyword_count": r.keyword_count,
                "coverage_ratio": r.coverage_ratio,
            }
            for r in results
        ]
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    else:
        for r in results:
            preview = r.original_text[:60] + ("…" if len(r.original_text) > 60 else "")
            print(f"Text    : {preview}")
            print(f"Keywords: {', '.join(r.top_keywords)}")
            print()
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    """Handle the ``compare`` sub-command."""
    from aranorm.analysis.text_comparator import TextComparator

    comparator = TextComparator()
    result = comparator.compare(args.text_a, args.text_b)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text A    : {args.text_a[:60]}")
        print(f"Text B    : {args.text_b[:60]}")
        print(f"Verdict   : {result.verdict}")
        print(f"Overall   : {result.overall_similarity:.0%}")
        print(f"Jaccard   : {result.jaccard_similarity:.0%}")
        print(f"Content   : {result.content_jaccard:.0%}")
        if result.shared_content_words:
            print(f"Shared KW : {', '.join(sorted(result.shared_content_words)[:10])}")
    return 0


def _cmd_tokenize(args: argparse.Namespace) -> int:
    """Handle the ``tokenize`` sub-command."""
    from aranorm.utils.tokenizer import ArabicTokenizer

    tokenizer = ArabicTokenizer(
        split_clitics=args.split_clitics,
        keep_punctuation=args.keep_punctuation,
    )

    texts: List[str] = []
    if args.text:
        texts = [args.text]
    elif args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                texts = [fh.read()]
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    else:
        texts = [sys.stdin.read()]

    for text in texts:
        if args.sentences:
            sentences = tokenizer.split_sentences(text)
            if args.json:
                data = [{"index": s.index, "text": s.text} for s in sentences]
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                for s in sentences:
                    print(f"[{s.index}] {s.text}")
        else:
            tokens = tokenizer.tokenize(text)
            if args.json:
                print(json.dumps(tokens, ensure_ascii=False, indent=2))
            else:
                print(" | ".join(tokens))
    return 0


def _cmd_sentiment(args: argparse.Namespace) -> int:
    """Handle the ``sentiment`` sub-command."""
    from aranorm.analysis.sentiment_analyzer import SentimentAnalyzer

    analyzer = SentimentAnalyzer()

    texts: List[str] = []
    if args.text:
        texts = [args.text]
    elif args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                texts = [line.rstrip("\n") for line in fh if line.strip()]
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    else:
        texts = [line.rstrip("\n") for line in sys.stdin if line.strip()]

    results = [analyzer.analyze(t) for t in texts]

    if args.json:
        output_data = [r.to_dict() for r in results]
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    else:
        for t, r in zip(texts, results):
            preview = t[:60] + ("…" if len(t) > 60 else "")
            label_icon = {"positive": "✓ Positive", "negative": "✗ Negative", "neutral": "– Neutral"}
            print(f"Text      : {preview}")
            print(f"Sentiment : {label_icon.get(r.label, r.label)}")
            print(f"Score     : {r.score:+.3f}  (confidence {r.confidence:.0%})")
            if r.positive_words:
                print(f"Positive  : {', '.join(r.positive_words[:5])}")
            if r.negative_words:
                print(f"Negative  : {', '.join(r.negative_words[:5])}")
            print()
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    """Handle the ``version`` sub-command."""
    from aranorm import __version__
    print(f"aranorm {__version__}")
    return 0


def _cmd_readability(args: argparse.Namespace) -> int:
    """Handle the ``readability`` sub-command."""
    from aranorm.analysis.readability import ArabicReadabilityAnalyzer
    analyzer = ArabicReadabilityAnalyzer()
    r = analyzer.analyze(args.text)
    if args.json:
        print(json.dumps({
            "score": r.score,
            "label": r.readability_label,
            "avg_sentence_length": r.avg_sentence_length,
            "avg_word_length": r.avg_word_length,
            "long_word_ratio": r.long_word_ratio,
            "complexity_marker_count": r.complexity_marker_count,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Readability   : {r.readability_label} ({r.score:.1f}/100)")
        print(f"Avg sent len  : {r.avg_sentence_length:.1f} words")
        print(f"Avg word len  : {r.avg_word_length:.1f} chars")
        print(f"Long word %   : {r.long_word_ratio:.0%}")
        print(f"Complexity    : {r.complexity_marker_count} markers")
    return 0


def _cmd_summarize(args: argparse.Namespace) -> int:
    """Handle the ``summarize`` sub-command."""
    from aranorm.analysis.summarizer import ArabicTextSummarizer
    text = args.text
    if not text:
        if args.file:
            try:
                with open(args.file, encoding="utf-8") as fh:
                    text = fh.read()
            except FileNotFoundError:
                print(f"Error: file not found: {args.file}", file=sys.stderr)
                return 1
        else:
            text = sys.stdin.read()
    if not text.strip():
        print("Error: no text provided.", file=sys.stderr)
        return 1
    summarizer = ArabicTextSummarizer(max_sentences=args.max_sentences)
    r = summarizer.summarize(text)
    if args.json:
        print(json.dumps({
            "summary": r.summary_text,
            "original_sentences": r.original_sentence_count,
            "summary_sentences": r.summary_sentence_count,
            "compression_ratio": r.compression_ratio,
            "top_keywords": r.top_keywords,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Compression : {r.original_sentence_count} → {r.summary_sentence_count} sentences "
              f"({r.compression_ratio:.0%})")
        print(f"Keywords    : {', '.join(r.top_keywords[:5])}")
        print(f"\nSummary:\n{r.summary_text}")
    return 0


def _cmd_detect(args: argparse.Namespace) -> int:
    """Handle the ``detect`` sub-command."""
    from aranorm.utils.language_detector import LanguageDetector
    detector = LanguageDetector()
    r = detector.detect_detailed(args.text)
    if args.json:
        print(json.dumps({
            "label": r.label,
            "arabic_ratio": r.arabic_ratio,
            "latin_ratio": r.latin_ratio,
            "arabizi_score": r.arabizi_score,
            "is_arabic": r.label == "arabic",
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Label     : {r.label}")
        print(f"Arabic    : {r.arabic_ratio:.0%}")
        print(f"Latin     : {r.latin_ratio:.0%}")
        print(f"Arabizi   : {r.arabizi_score:.2f}")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    """Handle the ``batch`` sub-command — bulk normalize with export."""
    from aranorm import ArabicNormalizationPipeline, PipelineConfig
    from aranorm.utils.exporters import BatchExporter
    from aranorm.utils.progress import ConsoleProgressCallback, TqdmProgressCallback

    try:
        with open(args.file, encoding="utf-8") as fh:
            texts = [line.rstrip("\n") for line in fh if line.strip()]
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    if not texts:
        print("Error: input file is empty.", file=sys.stderr)
        return 1

    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset=args.preset))

    callback = None
    if args.progress:
        try:
            callback = TqdmProgressCallback(total=len(texts))
        except ImportError:
            callback = ConsoleProgressCallback(total=len(texts))

    results = pipeline.process_batch(
        texts, n_workers=args.workers, progress_callback=callback
    )

    exporter = BatchExporter(results)
    if args.format == "csv":
        content = exporter.to_csv_string()
    elif args.format == "json":
        content = exporter.to_json_string()
    else:
        content = exporter.to_jsonl_string()

    if args.output:
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        with open(args.output, "w", encoding=encoding) as fh:
            fh.write(content)
        print(f"Wrote {len(results)} results to {args.output}")
    else:
        sys.stdout.write(content)
    return 0


def _cmd_corpus(args: argparse.Namespace) -> int:
    """Handle the ``corpus`` sub-command — corpus-level analysis."""
    from aranorm.analysis.corpus_analyzer import CorpusAnalyzer

    try:
        with open(args.file, encoding="utf-8") as fh:
            docs = [line.rstrip("\n") for line in fh if line.strip()]
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    if not docs:
        print("Error: corpus file is empty.", file=sys.stderr)
        return 1

    analyzer = CorpusAnalyzer()
    r = analyzer.analyze(docs)

    if args.json:
        print(json.dumps({
            "document_count": r.document_count,
            "corpus_stop_word_ratio": r.corpus_stop_word_ratio,
            "lexical_diversity": r.lexical_diversity,
            "top_content_words": [{"word": w, "count": c} for w, c in r.top_content_words[:args.top_n]],
            "top_stop_words": [{"word": w, "count": c} for w, c in r.top_stop_words[:10]],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Documents          : {r.document_count}")
        print(f"Stop-word ratio    : {r.corpus_stop_word_ratio:.1%}")
        print(f"Lexical diversity  : {r.lexical_diversity:.4f}")
        print(f"\nTop {args.top_n} content words:")
        for word, count in r.top_content_words[:args.top_n]:
            print(f"  {word}: {count}")
        print("\nTop stop words:")
        for word, count in r.top_stop_words[:5]:
            print(f"  {word}: {count}")
    return 0


# ── Parser factory ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aranorm",
        description="AraNorm — Arabic text normalization CLI",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── normalize ─────────────────────────────────────────────────────────
    p_norm = sub.add_parser("normalize", help="Normalize Arabic text")
    p_norm.add_argument("text", nargs="?", help="Text to normalize (or use --file / stdin)")
    p_norm.add_argument("--file", "-f", help="Input file (one text per line)")
    p_norm.add_argument("--output", "-o", help="Output file (default: stdout)")
    p_norm.add_argument("--preset", default="standard",
                        choices=["light", "standard", "deep", "social_media"],
                        help="Normalization preset (default: standard)")
    p_norm.add_argument("--dialect-target", default="none",
                        choices=["none", "coda", "msa"],
                        dest="dialect_target",
                        help="Target dialect form (default: none)")
    p_norm.add_argument("--keep-diacritics", action="store_true", default=False,
                        dest="keep_diacritics",
                        help="Preserve Arabic diacritics")
    p_norm.add_argument("--keep-urls", action="store_true", default=False,
                        dest="keep_urls",
                        help="Keep URLs in output")
    p_norm.add_argument("--clean-emojis", action="store_true", default=False,
                        dest="clean_emojis",
                        help="Remove emoji characters")
    p_norm.add_argument("--stop-words", action="store_true", default=False,
                        dest="stop_words",
                        help="Remove stop words")
    p_norm.add_argument("--sw-scope", default="universal",
                        choices=["universal", "msa_only", "dialect_aware"],
                        dest="sw_scope",
                        help="Stop-word scope (requires --stop-words)")
    p_norm.add_argument("--json", action="store_true", default=False)

    # ── stopwords ────────────────────────────────────────────────────────
    p_sw = sub.add_parser("stopwords", help="Analyze stop words in text")
    p_sw.add_argument("text", help="Text to analyze")
    p_sw.add_argument("--mode", default="remove",
                      choices=["remove", "extract", "highlight", "count"])
    p_sw.add_argument("--scope", default="universal",
                      choices=["universal", "msa_only", "dialect_aware", "custom"])
    p_sw.add_argument("--json", action="store_true", default=False)

    # ── analyze ──────────────────────────────────────────────────────────
    p_an = sub.add_parser("analyze", help="Text statistics and readability")
    p_an.add_argument("text", help="Text to analyze")
    p_an.add_argument("--json", action="store_true", default=False)

    # ── info ─────────────────────────────────────────────────────────────
    p_info = sub.add_parser("info", help="Library version and data stats")
    p_info.add_argument("--json", action="store_true", default=False)

    # ── dialect ──────────────────────────────────────────────────────────
    p_dial = sub.add_parser("dialect", help="Identify dialect of Arabic text")
    p_dial.add_argument("text", help="Arabic text to classify")
    p_dial.add_argument("--json", action="store_true", default=False)

    # ── keywords ─────────────────────────────────────────────────────────
    p_kw = sub.add_parser("keywords", help="Extract keywords from Arabic text")
    p_kw.add_argument("text", nargs="?", help="Text (or use --file / stdin)")
    p_kw.add_argument("--file", "-f", help="Input file (one text per line)")
    p_kw.add_argument("--top-n", type=int, default=10, dest="top_n",
                      help="Number of keywords to return (default: 10)")
    p_kw.add_argument("--json", action="store_true", default=False)

    # ── compare ──────────────────────────────────────────────────────────
    p_cmp = sub.add_parser("compare", help="Compare two Arabic texts for similarity")
    p_cmp.add_argument("text_a", help="First text")
    p_cmp.add_argument("text_b", help="Second text")
    p_cmp.add_argument("--json", action="store_true", default=False)

    # ── tokenize ─────────────────────────────────────────────────────────
    p_tok = sub.add_parser("tokenize", help="Tokenize Arabic text into words or sentences")
    p_tok.add_argument("text", nargs="?", help="Text (or use --file / stdin)")
    p_tok.add_argument("--file", "-f", help="Input file")
    p_tok.add_argument("--sentences", "-s", action="store_true", default=False,
                       help="Split into sentences instead of words")
    p_tok.add_argument("--split-clitics", action="store_true", default=False,
                       dest="split_clitics",
                       help="Split common clitic prefixes/suffixes")
    p_tok.add_argument("--keep-punctuation", action="store_true", default=False,
                       dest="keep_punctuation",
                       help="Keep punctuation tokens")
    p_tok.add_argument("--json", action="store_true", default=False)

    # ── sentiment ────────────────────────────────────────────────────────
    p_sent = sub.add_parser("sentiment", help="Analyze sentiment of Arabic text")
    p_sent.add_argument("text", nargs="?", help="Text (or use --file / stdin)")
    p_sent.add_argument("--file", "-f", help="Input file (one text per line)")
    p_sent.add_argument("--json", action="store_true", default=False)

    # ── version ──────────────────────────────────────────────────────────
    sub.add_parser("version", help="Print the library version and exit")

    # ── readability ───────────────────────────────────────────────────────
    p_read = sub.add_parser("readability", help="Compute readability score for text")
    p_read.add_argument("text", help="Arabic text to score")
    p_read.add_argument("--json", action="store_true", default=False)

    # ── summarize ────────────────────────────────────────────────────────
    p_sum = sub.add_parser("summarize", help="Summarize Arabic text (extractive)")
    p_sum.add_argument("text", nargs="?", help="Text (or use --file / stdin)")
    p_sum.add_argument("--file", "-f", help="Input file")
    p_sum.add_argument("--max-sentences", type=int, default=3, dest="max_sentences",
                       help="Maximum summary sentences (default: 3)")
    p_sum.add_argument("--json", action="store_true", default=False)

    # ── detect ────────────────────────────────────────────────────────────
    p_det = sub.add_parser("detect", help="Detect script / language of text")
    p_det.add_argument("text", help="Text to classify")
    p_det.add_argument("--json", action="store_true", default=False)

    # ── batch ─────────────────────────────────────────────────────────────
    p_batch = sub.add_parser("batch", help="Bulk normalize with export (CSV/JSON/JSONL)")
    p_batch.add_argument("--file", "-f", required=True, help="Input file (one text per line)")
    p_batch.add_argument("--output", "-o", help="Output file (default: stdout)")
    p_batch.add_argument("--format", default="jsonl",
                         choices=["csv", "json", "jsonl"], dest="format",
                         help="Export format (default: jsonl)")
    p_batch.add_argument("--preset", default="standard",
                         choices=["light", "standard", "deep", "social_media"])
    p_batch.add_argument("--workers", type=int, default=1,
                         help="Number of parallel workers (default: 1)")
    p_batch.add_argument("--progress", action="store_true", default=False,
                         help="Show progress bar (requires tqdm)")

    # ── corpus ───────────────────────────────────────────────────────────
    p_corpus = sub.add_parser("corpus", help="Corpus-level stop-word & keyword analysis")
    p_corpus.add_argument("--file", "-f", required=True,
                          help="Input file (one document per line)")
    p_corpus.add_argument("--top-n", type=int, default=10, dest="top_n",
                          help="Number of top content words to show (default: 10)")
    p_corpus.add_argument("--json", action="store_true", default=False)

    # ── add --workers to normalize ────────────────────────────────────────
    p_norm.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (default: 1)")

    return parser


# ── Entry point ────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    """Parse arguments and dispatch to the appropriate handler."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    _handlers = {
        "normalize": _cmd_normalize,
        "stopwords": _cmd_stopwords,
        "analyze": _cmd_analyze,
        "info": _cmd_info,
        "dialect": _cmd_dialect,
        "keywords": _cmd_keywords,
        "compare": _cmd_compare,
        "tokenize": _cmd_tokenize,
        "sentiment": _cmd_sentiment,
        "version": _cmd_version,
        "readability": _cmd_readability,
        "summarize": _cmd_summarize,
        "detect": _cmd_detect,
        "batch": _cmd_batch,
        "corpus": _cmd_corpus,
    }

    handler = _handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
