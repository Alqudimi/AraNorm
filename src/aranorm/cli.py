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
from typing import Iterator, List, Optional

# ── Input helpers ───────────────────────────────────────────────────────────────


def _iter_nonempty_lines(path: str) -> Iterator[str]:
    """Yield non-empty UTF-8 lines without materializing the input file."""
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            value = line.rstrip("\n")
            if value.strip():
                yield value


def _count_nonempty_lines(path: str) -> int:
    """Count non-empty UTF-8 lines using a bounded-memory scan."""
    return sum(1 for _ in _iter_nonempty_lines(path))


# ── Sub-command handlers ───────────────────────────────────────────────────────


def _cmd_normalize(args: argparse.Namespace) -> int:
    """Handle the ``normalize`` sub-command."""
    from aranorm import ArabicNormalizationPipeline, BatchRetryPolicy, PipelineConfig, StopWordsConfig

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
        emit_steps_trace=getattr(args, "emit_steps_trace", False),
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
    retry_report = None
    if getattr(args, "retry", False):
        retry_report = pipeline.process_batch_retry(
            texts,
            retry_policy=BatchRetryPolicy(
                max_retries=args.max_retries,
                batch_size=args.batch_size,
                n_workers=n_workers,
            ),
        )
        results = retry_report.results
    else:
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
                if getattr(args, "emit_steps_trace", False):
                    entry["steps_trace"] = list(r.steps_trace or [])
                output_data.append(entry)
            if retry_report is not None:
                payload = {
                    "results": output_data,
                    "retry": retry_report.to_dict(),
                    "schema_version": "1.0",
                }
                json.dump(payload, out, ensure_ascii=False, indent=2)
            else:
                json.dump(output_data, out, ensure_ascii=False, indent=2)
            out.write("\n")
        else:
            for r in results:
                out.write(r.normalized_text + "\n")
    finally:
        if args.output:
            out.close()

    if retry_report is not None and retry_report.failed_indices:
        print(
            f"Error: {len(retry_report.failed_indices)} item(s) failed after retries.",
            file=sys.stderr,
        )
        return 2
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
        print(
            f"Count     : {stats.get('count', 0)} / {stats.get('total_tokens', 0)} "
            f"({stats.get('percentage', 0.0):.1f}%)"
        )
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

    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": "1",
                    "package": "aranorm",
                    "version": __version__,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(f"aranorm {__version__}")
    return 0


def _cmd_describe(args: argparse.Namespace) -> int:
    """Handle the ``describe`` sub-command."""
    from aranorm import ArabicNormalizationPipeline, PipelineConfig

    pipeline = ArabicNormalizationPipeline(PipelineConfig(preset=args.preset))
    description = pipeline.describe_operational()
    if args.json:
        print(json.dumps(description, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Pipeline: {description['pipeline_class']}")
        print(f"Schema version: {description['schema_version']}")
        print(f"Preset: {description['config']['preset']}")
        print(f"Config fingerprint: {description['config_fingerprint']}")
    return 0


def _cmd_plugins(args: argparse.Namespace) -> int:
    """Handle the ``plugins`` sub-command."""
    from aranorm.core import ProcessorRegistry

    registry = ProcessorRegistry()
    report = registry.discover_report(group=args.group, strict=args.strict)

    if args.json:
        payload = report.to_dict()
        payload["schema_version"] = "1"
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        status = "ok" if report.ok else "degraded"
        print(f"Plugin group : {report.group}")
        print(f"Status       : {status}")
        print(f"Discovered   : {', '.join(report.discovered) or '<none>'}")
        if report.failures:
            print("Failures:")
            for failure in report.failures:
                print(f"  {failure.name}: {failure.error_type}: {failure.message}")
    return 0


def _cmd_readability(args: argparse.Namespace) -> int:
    """Handle the ``readability`` sub-command."""
    from aranorm.analysis.readability import ArabicReadabilityAnalyzer

    analyzer = ArabicReadabilityAnalyzer()
    r = analyzer.analyze(args.text)
    if args.json:
        print(
            json.dumps(
                {
                    "score": r.score,
                    "label": r.readability_label,
                    "avg_sentence_length": r.avg_sentence_length,
                    "avg_word_length": r.avg_word_length,
                    "long_word_ratio": r.long_word_ratio,
                    "complexity_marker_count": r.complexity_marker_count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
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
        print(
            json.dumps(
                {
                    "summary": r.summary_text,
                    "original_sentences": r.original_sentence_count,
                    "summary_sentences": r.summary_sentence_count,
                    "compression_ratio": r.compression_ratio,
                    "top_keywords": r.top_keywords,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(
            f"Compression : {r.original_sentence_count} → {r.summary_sentence_count} sentences "
            f"({r.compression_ratio:.0%})"
        )
        print(f"Keywords    : {', '.join(r.top_keywords[:5])}")
        print(f"\nSummary:\n{r.summary_text}")
    return 0


def _cmd_detect(args: argparse.Namespace) -> int:
    """Handle the ``detect`` sub-command."""
    from aranorm.utils.language_detector import LanguageDetector

    detector = LanguageDetector()
    r = detector.detect_detailed(args.text)
    if args.json:
        print(
            json.dumps(
                {
                    "label": r.label,
                    "arabic_ratio": r.arabic_ratio,
                    "latin_ratio": r.latin_ratio,
                    "arabizi_score": r.arabizi_score,
                    "is_arabic": r.label == "arabic",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Label     : {r.label}")
        print(f"Arabic    : {r.arabic_ratio:.0%}")
        print(f"Latin     : {r.latin_ratio:.0%}")
        print(f"Arabizi   : {r.arabizi_score:.2f}")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    """Handle the ``batch`` sub-command — bulk normalize with export."""
    from aranorm import ArabicNormalizationPipeline, BatchRetryPolicy, PipelineConfig
    from aranorm.utils.exporters import BatchExporter, StreamingBatchExporter
    from aranorm.utils.progress import (
        ConsoleProgressCallback,
        ProgressCallback,
        TqdmProgressCallback,
    )

    values: Optional[List[str]] = None
    try:
        if args.stream:
            stream_texts = _iter_nonempty_lines(args.file)
            total = _count_nonempty_lines(args.file)
        else:
            values = list(_iter_nonempty_lines(args.file))
            total = len(values)
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    if total == 0:
        print("Error: input file is empty.", file=sys.stderr)
        return 1

    pipeline = ArabicNormalizationPipeline(
        PipelineConfig(preset=args.preset, emit_steps_trace=getattr(args, "emit_steps_trace", False))
    )

    callback: Optional[ProgressCallback] = None
    if args.progress:
        try:
            callback = TqdmProgressCallback()
        except ImportError:
            callback = ConsoleProgressCallback(total=total or 0)

    on_error = None
    if args.skip_errors:

        def _skip_error(index: int, text: str, exc: Exception) -> Optional[str]:
            print(f"Warning: skipped item {index}: {exc}", file=sys.stderr)
            return None

        on_error = _skip_error

    if args.stream:
        if getattr(args, "retry", False):
            print("Error: --retry cannot be combined with --stream.", file=sys.stderr)
            return 2
        stream_results = pipeline.process_iter(
            stream_texts,
            batch_size=args.batch_size,
            n_workers=args.workers,
            on_error=on_error,
            progress_callback=callback,
            total=total,
        )
        stream_exporter = StreamingBatchExporter()
        target = args.output or sys.stdout
        count = stream_exporter.write(stream_results, target, format=args.format)
        if args.output:
            print(f"Wrote {count} results to {args.output}")
        return 0

    assert values is not None
    retry_report = None
    if getattr(args, "retry", False):
        retry_report = pipeline.process_batch_retry(
            values,
            retry_policy=BatchRetryPolicy(
                max_retries=args.max_retries,
                batch_size=args.batch_size,
                n_workers=args.workers,
            ),
            on_error=on_error,
            progress_callback=callback,
        )
        results = retry_report.results
    else:
        results = pipeline.process_batch(
            values,
            batch_size=args.batch_size,
            n_workers=args.workers,
            on_error=on_error,
            progress_callback=callback,
        )

    fields = None
    if getattr(args, "emit_steps_trace", False) and args.format != "jsonl":
        fields = [
            "original_text",
            "normalized_text",
            "dialect",
            "dialect_confidence",
            "applied_steps",
            "stop_words_removed",
            "stop_words_found",
            "steps_trace",
        ]
    batch_exporter = BatchExporter(results, fields=fields)
    if args.format == "csv":
        content = batch_exporter.to_csv_string()
    elif args.format == "json":
        content = batch_exporter.to_json_string()
    else:
        content = batch_exporter.to_jsonl_string()

    if args.output:
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        with open(args.output, "w", encoding=encoding) as fh:
            fh.write(content)
        print(f"Wrote {len(results)} results to {args.output}")
    else:
        sys.stdout.write(content)
    if retry_report is not None and retry_report.failed_indices:
        print(
            f"Error: {len(retry_report.failed_indices)} item(s) failed after retries.",
            file=sys.stderr,
        )
        return 2
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
        print(
            json.dumps(
                {
                    "document_count": r.document_count,
                    "corpus_stop_word_ratio": r.corpus_stop_word_ratio,
                    "lexical_diversity": r.lexical_diversity,
                    "top_content_words": [{"word": w, "count": c} for w, c in r.top_content_words[: args.top_n]],
                    "top_stop_words": [{"word": w, "count": c} for w, c in r.top_stop_words[:10]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Documents          : {r.document_count}")
        print(f"Stop-word ratio    : {r.corpus_stop_word_ratio:.1%}")
        print(f"Lexical diversity  : {r.lexical_diversity:.4f}")
        print(f"\nTop {args.top_n} content words:")
        for word, count in r.top_content_words[: args.top_n]:
            print(f"  {word}: {count}")
        print("\nTop stop words:")
        for word, count in r.top_stop_words[:5]:
            print(f"  {word}: {count}")
    return 0


def _cmd_spec(args: argparse.Namespace) -> int:
    """Create or validate a portable PipelineSpec JSON document."""
    from aranorm import ArabicNormalizationPipeline, PipelineConfig, PipelineSpec

    try:
        if args.spec_command == "export":
            config = PipelineConfig.from_file(args.config) if args.config else PipelineConfig(preset=args.preset)
            pipeline = ArabicNormalizationPipeline(config)
            metadata = {}
            if args.metadata_json:
                metadata = json.loads(args.metadata_json)
                if not isinstance(metadata, dict):
                    raise ValueError("--metadata-json must contain a JSON object")
            spec = pipeline.to_spec(metadata=metadata)
            if args.output:
                spec.write_file(args.output)
                if args.json:
                    print(
                        json.dumps(
                            {"valid": True, "output": args.output, **spec.to_dict()}, ensure_ascii=False, sort_keys=True
                        )
                    )
                else:
                    print(f"Wrote PipelineSpec to {args.output}")
            else:
                print(spec.to_json())
            return 0

        if args.spec_command == "validate":
            spec = PipelineSpec.read_file(args.file)
            payload = {"valid": True, **spec.to_dict()}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(f"Valid PipelineSpec: {args.file}")
                print(f"Schema version: {spec.schema_version}")
                print(f"Config fingerprint: {spec.config_fingerprint}")
            return 0

        print("Error: a spec sub-command is required.", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, ImportError) as error:
        print(f"Error: invalid PipelineSpec: {error}", file=sys.stderr)
        return 1


def _cmd_stream(args: argparse.Namespace) -> int:
    """Run, resume, or inspect a durable file streaming session."""
    from aranorm import (
        ArabicNormalizationPipeline,
        CheckpointError,
        PipelineConfig,
        StreamCheckpoint,
        StreamingSession,
        StreamingSessionError,
    )

    if args.stream_command == "status":
        try:
            checkpoint = StreamCheckpoint.load(args.checkpoint)
        except (OSError, ValueError, TypeError, CheckpointError) as error:
            print(f"Error: could not load streaming checkpoint: {error}", file=sys.stderr)
            return 1
        payload = checkpoint.to_dict()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"Checkpoint : {args.checkpoint}")
            print(f"Source     : {checkpoint.source_path}")
            print(f"Output     : {checkpoint.output_path}")
            print(f"Next index : {checkpoint.next_index}")
            print(f"Processed  : {checkpoint.input_count}")
            print(f"Completed  : {'yes' if checkpoint.completed else 'no'}")
        return 0

    try:
        pipeline = ArabicNormalizationPipeline(PipelineConfig(preset=args.preset))
        session = StreamingSession(
            pipeline,
            args.source,
            args.output,
            args.checkpoint,
            batch_size=args.batch_size,
            n_workers=args.workers,
            max_input_bytes=args.max_input_bytes,
            lock_enabled=args.lock_enabled,
        )
        report = session.run(resume=args.stream_command == "resume")
    except (OSError, ValueError, TypeError, CheckpointError, StreamingSessionError, ImportError) as error:
        print(f"Error: streaming session failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"ok": True, "report": report.to_dict()}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        action = "Resumed" if args.stream_command == "resume" else "Processed"
        print(f"{action} streaming session")
        print(f"Source     : {report.source_path}")
        print(f"Output     : {report.output_path}")
        print(f"Checkpoint : {report.checkpoint_path}")
        print(f"Processed  : {report.processed_count}")
        print(f"Next index : {report.next_index}")
        print(f"Completed  : {'yes' if report.completed else 'no'}")
        if report.cancelled:
            print("Cancelled  : yes")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    """Handle the opt-in standard-library HTTP service."""
    from aranorm import PipelineConfig, PipelineRuntime, PipelineSpec
    from aranorm.server import serve

    spec_path = getattr(args, "spec", None)
    try:
        if args.config and spec_path:
            raise ValueError("--config and --spec are mutually exclusive")
        if spec_path:
            runtime = PipelineRuntime(PipelineSpec.read_file(spec_path).to_pipeline().config)
        else:
            config = PipelineConfig.from_file(args.config) if args.config else PipelineConfig(preset=args.preset)
            runtime = PipelineRuntime(config)
    except (OSError, ValueError, TypeError, ImportError) as error:
        print(f"Error: could not load configuration: {error}", file=sys.stderr)
        return 1

    print(f"AraNorm server listening on http://{args.host}:{args.port}", file=sys.stderr)
    try:
        serve_kwargs = {
            "host": args.host,
            "port": args.port,
            "max_body_bytes": args.max_body_bytes,
            "config_path": args.config,
            "reload_interval": args.reload_interval,
        }
        if spec_path is not None:
            serve_kwargs["spec_path"] = spec_path
        if getattr(args, "streaming_enabled", False):
            serve_kwargs["streaming_enabled"] = True
        if getattr(args, "streaming_root", None):
            if not getattr(args, "streaming_enabled", False):
                raise ValueError("--streaming-root requires --streaming-enabled")
            serve_kwargs["streaming_root"] = args.streaming_root
        serve(runtime, **serve_kwargs)
    except (OSError, ValueError, TypeError) as error:
        print(f"Error: could not start server: {error}", file=sys.stderr)
        return 1
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
    p_norm.add_argument(
        "--preset",
        default="standard",
        choices=["light", "standard", "deep", "social_media"],
        help="Normalization preset (default: standard)",
    )
    p_norm.add_argument(
        "--dialect-target",
        default="none",
        choices=["none", "coda", "msa"],
        dest="dialect_target",
        help="Target dialect form (default: none)",
    )
    p_norm.add_argument(
        "--keep-diacritics",
        action="store_true",
        default=False,
        dest="keep_diacritics",
        help="Preserve Arabic diacritics",
    )
    p_norm.add_argument("--keep-urls", action="store_true", default=False, dest="keep_urls", help="Keep URLs in output")
    p_norm.add_argument(
        "--clean-emojis", action="store_true", default=False, dest="clean_emojis", help="Remove emoji characters"
    )
    p_norm.add_argument("--stop-words", action="store_true", default=False, dest="stop_words", help="Remove stop words")
    p_norm.add_argument(
        "--sw-scope",
        default="universal",
        choices=["universal", "msa_only", "dialect_aware"],
        dest="sw_scope",
        help="Stop-word scope (requires --stop-words)",
    )
    p_norm.add_argument("--json", action="store_true", default=False)
    p_norm.add_argument(
        "--emit-steps-trace",
        action="store_true",
        default=False,
        dest="emit_steps_trace",
        help="Include processor trace in JSON output (opt-in)",
    )
    p_norm.add_argument("--retry", action="store_true", default=False, help="Retry failed items with bounded retries")
    p_norm.add_argument(
        "--max-retries", type=int, default=3, dest="max_retries", help="Maximum retries per item (default: 3)"
    )
    p_norm.add_argument("--batch-size", type=int, default=32, dest="batch_size", help="Retry batch size (default: 32)")

    # ── stopwords ────────────────────────────────────────────────────────
    p_sw = sub.add_parser("stopwords", help="Analyze stop words in text")
    p_sw.add_argument("text", help="Text to analyze")
    p_sw.add_argument("--mode", default="remove", choices=["remove", "extract", "highlight", "count"])
    p_sw.add_argument("--scope", default="universal", choices=["universal", "msa_only", "dialect_aware", "custom"])
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
    p_kw.add_argument("--top-n", type=int, default=10, dest="top_n", help="Number of keywords to return (default: 10)")
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
    p_tok.add_argument(
        "--sentences", "-s", action="store_true", default=False, help="Split into sentences instead of words"
    )
    p_tok.add_argument(
        "--split-clitics",
        action="store_true",
        default=False,
        dest="split_clitics",
        help="Split common clitic prefixes/suffixes",
    )
    p_tok.add_argument(
        "--keep-punctuation",
        action="store_true",
        default=False,
        dest="keep_punctuation",
        help="Keep punctuation tokens",
    )
    p_tok.add_argument("--json", action="store_true", default=False)

    # ── sentiment ────────────────────────────────────────────────────────
    p_sent = sub.add_parser("sentiment", help="Analyze sentiment of Arabic text")
    p_sent.add_argument("text", nargs="?", help="Text (or use --file / stdin)")
    p_sent.add_argument("--file", "-f", help="Input file (one text per line)")
    p_sent.add_argument("--json", action="store_true", default=False)

    # ── version ──────────────────────────────────────────────────────────
    p_version = sub.add_parser("version", help="Print the library version and exit")
    p_version.add_argument("--json", action="store_true", default=False)

    # ── describe ─────────────────────────────────────────────────────────
    p_desc = sub.add_parser("describe", help="Show versioned pipeline metadata")
    p_desc.add_argument(
        "--preset",
        default="standard",
        choices=["light", "standard", "deep", "social_media"],
        help="Normalization preset to describe (default: standard)",
    )
    p_desc.add_argument("--json", action="store_true", default=False)

    # ── plugins ───────────────────────────────────────────────────────────
    p_plugins = sub.add_parser("plugins", help="Discover processor plugins")
    p_plugins.add_argument(
        "--group",
        default="aranorm.processors",
        help="Entry-point group to discover (default: aranorm.processors)",
    )
    p_plugins.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail on the first plugin loading or duplicate error",
    )
    p_plugins.add_argument("--json", action="store_true", default=False)

    # ── readability ───────────────────────────────────────────────────────
    p_read = sub.add_parser("readability", help="Compute readability score for text")
    p_read.add_argument("text", help="Arabic text to score")
    p_read.add_argument("--json", action="store_true", default=False)

    # ── summarize ────────────────────────────────────────────────────────
    p_sum = sub.add_parser("summarize", help="Summarize Arabic text (extractive)")
    p_sum.add_argument("text", nargs="?", help="Text (or use --file / stdin)")
    p_sum.add_argument("--file", "-f", help="Input file")
    p_sum.add_argument(
        "--max-sentences", type=int, default=3, dest="max_sentences", help="Maximum summary sentences (default: 3)"
    )
    p_sum.add_argument("--json", action="store_true", default=False)

    # ── detect ────────────────────────────────────────────────────────────
    p_det = sub.add_parser("detect", help="Detect script / language of text")
    p_det.add_argument("text", help="Text to classify")
    p_det.add_argument("--json", action="store_true", default=False)

    # ── batch ─────────────────────────────────────────────────────────────
    p_batch = sub.add_parser("batch", help="Bulk normalize with export (CSV/JSON/JSONL)")
    p_batch.add_argument("--file", "-f", required=True, help="Input file (one text per line)")
    p_batch.add_argument("--output", "-o", help="Output file (default: stdout)")
    p_batch.add_argument(
        "--format",
        default="jsonl",
        choices=["csv", "json", "jsonl"],
        dest="format",
        help="Export format (default: jsonl)",
    )
    p_batch.add_argument("--preset", default="standard", choices=["light", "standard", "deep", "social_media"])
    p_batch.add_argument("--workers", type=int, default=1, help="Number of parallel workers (default: 1)")
    p_batch.add_argument(
        "--batch-size",
        type=int,
        default=32,
        dest="batch_size",
        help="Maximum inputs kept in flight at once (default: 32)",
    )
    p_batch.add_argument(
        "--stream",
        action="store_true",
        default=False,
        help="Process and export incrementally without loading the full file",
    )
    p_batch.add_argument(
        "--skip-errors",
        action="store_true",
        default=False,
        help="Skip items that fail normalization instead of aborting",
    )
    p_batch.add_argument("--progress", action="store_true", default=False, help="Show progress bar (requires tqdm)")
    p_batch.add_argument(
        "--emit-steps-trace",
        action="store_true",
        default=False,
        dest="emit_steps_trace",
        help="Include processor trace in exported output (opt-in)",
    )
    p_batch.add_argument("--retry", action="store_true", default=False, help="Retry failed items with bounded retries")
    p_batch.add_argument(
        "--max-retries", type=int, default=3, dest="max_retries", help="Maximum retries per item (default: 3)"
    )

    # ── spec ──────────────────────────────────────────────────────────────
    p_spec = sub.add_parser("spec", help="Create or validate a portable pipeline specification")
    spec_sub = p_spec.add_subparsers(dest="spec_command", required=True)
    p_spec_export = spec_sub.add_parser("export", help="Export a PipelineSpec from a preset or config file")
    p_spec_export.add_argument("--config", help="JSON/YAML pipeline configuration file")
    p_spec_export.add_argument(
        "--preset",
        default="standard",
        choices=["light", "standard", "deep", "social_media"],
        help="Preset used when --config is omitted (default: standard)",
    )
    p_spec_export.add_argument("--metadata-json", help="JSON object stored as non-operational metadata")
    p_spec_export.add_argument("--output", "-o", help="Output PipelineSpec file (default: stdout)")
    p_spec_export.add_argument("--json", action="store_true", default=False, help="Print a JSON result after writing")
    p_spec_validate = spec_sub.add_parser("validate", help="Validate an existing PipelineSpec JSON file")
    p_spec_validate.add_argument("file", help="PipelineSpec JSON file")
    p_spec_validate.add_argument("--json", action="store_true", default=False)

    # ── stream ────────────────────────────────────────────────────────────
    p_stream = sub.add_parser("stream", help="Run resumable file-to-file normalization")
    stream_sub = p_stream.add_subparsers(dest="stream_command", required=True)
    for stream_command, help_text in (
        ("run", "Start a new streaming session"),
        ("resume", "Resume a streaming session from its checkpoint"),
    ):
        p_stream_run = stream_sub.add_parser(stream_command, help=help_text)
        p_stream_run.add_argument("--source", required=True, help="UTF-8 input file, one text item per line")
        p_stream_run.add_argument("--output", required=True, help="JSONL output file")
        p_stream_run.add_argument("--checkpoint", required=True, help="Durable checkpoint JSON file")
        p_stream_run.add_argument(
            "--preset",
            default="standard",
            choices=["light", "standard", "deep", "social_media"],
            help="Normalization preset (default: standard)",
        )
        p_stream_run.add_argument(
            "--batch-size",
            type=int,
            default=32,
            dest="batch_size",
            help="Inputs processed per checkpoint (default: 32)",
        )
        p_stream_run.add_argument("--workers", type=int, default=1, help="Number of workers (default: 1)")
        p_stream_run.add_argument(
            "--lock",
            action="store_true",
            default=False,
            dest="lock_enabled",
            help="Acquire a local advisory lock for this source/output/checkpoint tuple",
        )
        p_stream_run.add_argument(
            "--max-input-bytes",
            type=int,
            default=1024 * 1024 * 1024,
            dest="max_input_bytes",
            help="Maximum input file size (default: 1073741824)",
        )
        p_stream_run.add_argument("--json", action="store_true", default=False)

    p_stream_status = stream_sub.add_parser("status", help="Inspect a streaming checkpoint")
    p_stream_status.add_argument("--checkpoint", required=True, help="Checkpoint JSON file")
    p_stream_status.add_argument("--json", action="store_true", default=False)

    # ── serve ─────────────────────────────────────────────────────────────
    p_serve = sub.add_parser("serve", help="Run the optional HTTP normalization service")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    p_serve.add_argument("--config", help="JSON/YAML pipeline configuration file")
    p_serve.add_argument("--spec", help="Validated PipelineSpec JSON file")
    p_serve.add_argument(
        "--preset",
        default="standard",
        choices=["light", "standard", "deep", "social_media"],
        help="Preset used when --config is omitted (default: standard)",
    )
    p_serve.add_argument(
        "--max-body-bytes",
        type=int,
        default=2_000_000,
        dest="max_body_bytes",
        help="Maximum JSON request body size (default: 2000000)",
    )
    p_serve.add_argument(
        "--reload-interval",
        type=float,
        default=0.0,
        dest="reload_interval",
        help="Poll --config for changes every N seconds; disabled by default",
    )
    p_serve.add_argument(
        "--streaming-enabled",
        action="store_true",
        default=False,
        dest="streaming_enabled",
        help="Enable the local-files /v1/stream endpoint (opt-in)",
    )
    p_serve.add_argument(
        "--streaming-root",
        dest="streaming_root",
        help="Restrict /v1/stream paths to an existing local directory (requires --streaming-enabled)",
    )

    # ── spelling ──────────────────────────────────────────────────────────
    p_spell = sub.add_parser("spelling", help="Arabic spelling report for text")
    p_spell.add_argument("text", nargs="?", help="Arabic text to check")
    p_spell.add_argument("--file", "-f", help="Input file (reads full content)")
    p_spell.add_argument("--json", action="store_true", default=False)
    # ── quality ───────────────────────────────────────────────────────────
    p_qual = sub.add_parser("quality", help="Composite Arabic text quality score")
    p_qual.add_argument("text", nargs="?", help="Arabic text to score")
    p_qual.add_argument("--file", "-f", help="Input file (reads full content)")
    p_qual.add_argument("--json", action="store_true", default=False)
    # ── profile ───────────────────────────────────────────────────────────
    p_prof = sub.add_parser("profile", help="Corpus-level batch analysis report")
    p_prof.add_argument("--file", "-f", required=True, help="One document per line")
    p_prof.add_argument("--json", action="store_true", default=False)

    # ── corpus ───────────────────────────────────────────────────────────
    p_corpus = sub.add_parser("corpus", help="Corpus-level stop-word & keyword analysis")
    p_corpus.add_argument("--file", "-f", required=True, help="Input file (one document per line)")
    p_corpus.add_argument(
        "--top-n", type=int, default=10, dest="top_n", help="Number of top content words to show (default: 10)"
    )
    p_corpus.add_argument("--json", action="store_true", default=False)

    # ── add --workers to normalize ────────────────────────────────────────
    p_norm.add_argument("--workers", type=int, default=1, help="Number of parallel workers (default: 1)")

    # ── entities ──────────────────────────────────────────────────────────
    p_ent = sub.add_parser("entities", help="Extract named entities from Arabic text")
    p_ent.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_ent.add_argument("--file", "-f", help="Input file (reads full content)")
    p_ent.add_argument("--json", action="store_true", default=False)

    # ── topics ────────────────────────────────────────────────────────────
    p_top = sub.add_parser("topics", help="Classify the topic of Arabic text")
    p_top.add_argument("text", nargs="?", help="Arabic text to classify (or use --file / stdin)")
    p_top.add_argument("--file", "-f", help="Input file (reads full content)")
    p_top.add_argument("--json", action="store_true", default=False)

    # ── pronouns ──────────────────────────────────────────────────────────
    p_pro = sub.add_parser("pronouns", help="Decompose Arabic clitics and attached pronouns")
    p_pro.add_argument("text", nargs="?", help="Arabic word or sentence (or use --file / stdin)")
    p_pro.add_argument("--file", "-f", help="Input file (one word per line)")
    p_pro.add_argument("--json", action="store_true", default=False)

    # ── idioms ────────────────────────────────────────────────────────────
    p_idi = sub.add_parser("idioms", help="Detect Arabic idioms and fixed expressions")
    p_idi.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_idi.add_argument("--file", "-f", help="Input file (reads full content)")
    p_idi.add_argument("--json", action="store_true", default=False)

    # ── snapshot ──────────────────────────────────────────────────────────
    p_snap = sub.add_parser("snapshot", help="Save or restore a pipeline configuration snapshot")
    snap_sub = p_snap.add_subparsers(dest="snapshot_command", required=True)
    p_snap_save = snap_sub.add_parser("save", help="Save the current config to a snapshot file")
    p_snap_save.add_argument("--output", "-o", required=True, help="Snapshot output file (JSON)")
    p_snap_save.add_argument(
        "--preset",
        default="standard",
        choices=["light", "standard", "deep", "social_media"],
        help="Pipeline preset (default: standard)",
    )
    p_snap_save.add_argument("--json", action="store_true", default=False, help="Print the snapshot JSON after saving")
    p_snap_restore = snap_sub.add_parser("restore", help="Restore and print a snapshot file")
    p_snap_restore.add_argument("--input", "-i", required=True, help="Snapshot input file (JSON)")
    p_snap_restore.add_argument("--json", action="store_true", default=False)
    # ── frequency profile ─────────────────────────────────────────────────
    p_freq = sub.add_parser("freqprofile", help="Vocabulary frequency and diversity profile")
    p_freq.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_freq.add_argument("--file", "-f", help="Input file (reads full content)")
    p_freq.add_argument("--top-n", type=int, default=10, help="Number of top words (default: 10)")
    p_freq.add_argument("--json", action="store_true", default=False)
    # ── coherence ─────────────────────────────────────────────────────────
    p_coh = sub.add_parser("coherence", help="Deterministic Arabic text coherence score")
    p_coh.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_coh.add_argument("--file", "-f", help="Input file (reads full content)")
    p_coh.add_argument("--json", action="store_true", default=False)
    # ── style ─────────────────────────────────────────────────────────────
    p_style = sub.add_parser("style", help="Arabic register (formal / informal / digital) analysis")
    p_style.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_style.add_argument("--file", "-f", help="Input file (reads full content)")
    p_style.add_argument("--json", action="store_true", default=False)
    # ── emotions ──────────────────────────────────────────────────────────
    p_em = sub.add_parser("emotions", help="Detect emotions (Plutchik-style) in Arabic text")
    p_em.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_em.add_argument("--file", "-f", help="Input file (reads full content)")
    p_em.add_argument("--json", action="store_true", default=False)
    # ── profile ───────────────────────────────────────────────────────────
    p_prof2 = sub.add_parser("textprofile", help="Composite one-pass text profiling report")
    p_prof2.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_prof2.add_argument("--file", "-f", help="Input file (reads full content)")
    p_prof2.add_argument(
        "--axes",
        nargs="*",
        default=None,
        help="Subset of axes (sentiment coherence quality readability style emotions word_frequency topics)",
    )
    p_prof2.add_argument("--json", action="store_true", default=False)
    # ── rhythm ────────────────────────────────────────────────────────────
    p_rhy = sub.add_parser("rhythm", help="Arabic rhythmic patterns (saj', balance, repetition)")
    p_rhy.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_rhy.add_argument("--file", "-f", help="Input file (reads full content)")
    p_rhy.add_argument("--json", action="store_true", default=False)
    # ── figurate ──────────────────────────────────────────────────────────
    p_fig = sub.add_parser("figurate", help="Detect Arabic rhetorical figures (simile, antithesis, ...)")
    p_fig.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_fig.add_argument("--file", "-f", help="Input file (reads full content)")
    p_fig.add_argument("--json", action="store_true", default=False)
    # ── numbers ───────────────────────────────────────────────────────────
    p_num = sub.add_parser("numbers", help="Extract and classify Arabic numbers, percentages, currencies")
    p_num.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_num.add_argument("--file", "-f", help="Input file (reads full content)")
    p_num.add_argument("--json", action="store_true", default=False)
    # ── quotation ─────────────────────────────────────────────────────────
    p_quo = sub.add_parser("quotation", help="Analyze Arabic quotation environments (direct speech, reports)")
    p_quo.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_quo.add_argument("--file", "-f", help="Input file (reads full content)")
    p_quo.add_argument("--json", action="store_true", default=False)
    # ── loans ─────────────────────────────────────────────────────────────
    p_loa = sub.add_parser("loans", help="Detect Arabicised loanwords and Latin-script fragments")
    p_loa.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_loa.add_argument("--file", "-f", help="Input file (reads full content)")
    p_loa.add_argument("--json", action="store_true", default=False)
    # ── roots ─────────────────────────────────────────────────────────────
    p_roo = sub.add_parser("roots", help="Arabic trilateral-root derivation density profile")
    p_roo.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_roo.add_argument("--file", "-f", help="Input file (reads full content)")
    p_roo.add_argument("--json", action="store_true", default=False)
    # ── contrast ──────────────────────────────────────────────────────────
    p_con = sub.add_parser("contrast", help="Detect Arabic antonym pairs (تضاد / طباق)")
    p_con.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_con.add_argument("--file", "-f", help="Input file (reads full content)")
    p_con.add_argument("--json", action="store_true", default=False)
    # ── fillers ───────────────────────────────────────────────────────────
    p_fil = sub.add_parser("fillers", help="Detect filler phrases and word repetition")
    p_fil.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_fil.add_argument("--file", "-f", help="Input file (reads full content)")
    p_fil.add_argument("--json", action="store_true", default=False)
    # ── complexity ────────────────────────────────────────────────────────
    p_cpx = sub.add_parser("complexity", help="Morphological complexity and word-length profile")
    p_cpx.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_cpx.add_argument("--file", "-f", help="Input file (reads full content)")
    p_cpx.add_argument("--json", action="store_true", default=False)
    # ── rhetorical questions ──────────────────────────────────────────────
    p_rqs = sub.add_parser("rquestions", help="Detect rhetorical and interrogative questions in Arabic text")
    p_rqs.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_rqs.add_argument("--file", "-f", help="Input file (reads full content)")
    p_rqs.add_argument("--json", action="store_true", default=False)
    # ── anaphora / cohesion ───────────────────────────────────────────────
    p_ana = sub.add_parser("anaphora", help="Arabic anaphora and cross-sentence cohesion analysis")
    p_ana.add_argument("text", nargs="?", help="Arabic text to analyze (or use --file / stdin)")
    p_ana.add_argument("--file", "-f", help="Input file (reads full content)")
    p_ana.add_argument("--json", action="store_true", default=False)
    return parser


def _cmd_style(args: argparse.Namespace) -> int:
    """Handle the ``style`` sub-command — Arabic register analysis."""
    from aranorm.analysis.style_analyzer import analyze_style

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_style(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text        : {result.text[:80]}")
        print(f"Style index : {result.style_index:.4f} ({result.label})")
        print(
            f"Formal      : {result.signals.formal_markers:.4f}   "
            f"Colloquial  : {result.signals.colloquial_markers:.4f}   "
            f"Digital     : {result.signals.digital_signals:.4f}"
        )
        if result.formal_words:
            print(f"Formal words: {', '.join(result.formal_words[:10])}")
        if result.colloquial_words:
            print(f"Colloquial  : {', '.join(result.colloquial_words[:10])}")
        if result.elongations:
            print(f"Elongations : {', '.join(result.elongations[:10])}")
        print(f"Emoji count : {result.emoji_count}")
    return 0


def _cmd_emotions(args: argparse.Namespace) -> int:
    """Handle the ``emotions`` sub-command — Plutchik-style emotion detection."""
    from aranorm.analysis.emotion_analyzer import analyze_emotions

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_emotions(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text             : {result.text[:80]}")
        print(f"Dominant emotion : {result.dominant_emotion} (confidence {result.confidence:.4f})")
        print("Counts           : " + ", ".join(f"{key}={value}" for key, value in result.counts.to_dict().items()))
        matched = {key: value for key, value in result.matched_words.items() if value}
        if matched:
            print("Matched words    : " + ", ".join(f"{key}: {', '.join(value)}" for key, value in matched.items()))
    return 0


def _cmd_textprofile(args: argparse.Namespace) -> int:
    """Handle the ``textprofile`` sub-command — composite one-pass text profiling."""
    from aranorm.analysis.profiler import AnalysisProfiler

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    axes = args.axes if args.axes else None
    result = AnalysisProfiler(axes=axes).profile(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text     : {result.text[:80]}")
        for axis_name, axis_data in result.axes.items():
            if "label" in axis_data:
                print(f"{axis_name:<16} {axis_data['label']}")
            elif "dominant_emotion" in axis_data:
                print(f"{axis_name:<16} dominant={axis_data['dominant_emotion']}")
            elif "style_index" in axis_data:
                print(f"{axis_name:<16} {axis_data['style_index']:.4f} ({axis_data['label']})")
        if result.insights:
            print("\nInsights:")
            for insight in result.insights:
                print(f"  [{insight.rule}] {insight.message}")
    return 0


def _cmd_rhythm(args: argparse.Namespace) -> int:
    """Handle the ``rhythm`` sub-command — Arabic rhythmic pattern analysis."""
    from aranorm.analysis.rhythm_analyzer import analyze_rhythm

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_rhythm(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Sentences   : {result.sentence_count}   Words : {result.word_count}")
        print(f"Rhythm idx  : {result.rhythm_index:.4f} ({result.label})")
        print(f"Saj signals : {result.saj_signals}")
        print(
            f"Balance     : {result.parallel_balance:.4f}   "
            f"Repetition  : {result.repetition_density:.4f}   "
            f"Line ratio  : {result.poetic_line_ratio:.4f}"
        )
        if result.saj_pairs:
            for pair in result.saj_pairs[:5]:
                print(f"  saj' pair : {pair.clause_a!r} ≈ {pair.clause_b!r} ({pair.shared_stem})")
    return 0


def _cmd_figurate(args: argparse.Namespace) -> int:
    """Handle the ``figurate`` sub-command — rhetorical figure detection."""
    from aranorm.analysis.figurate_analyzer import analyze_figurative

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_figurative(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Words       : {result.word_count}")
        print(f"Figure idx  : {result.figure_index:.4f} ({result.label})")
        print(f"Figures     : {', '.join(result.figures) if result.figures else '(none)'}")
        print(
            f"Counts      : simile={result.simile_count} tibaq={result.tibaq_count} "
            f"taraduf={result.taraduf_count} takrir={result.takrir_count}"
        )
        if result.takrir_words:
            print(f"Refrain     : {', '.join(result.takrir_words)}")
        if result.occurrences:
            for occurrence in result.occurrences[:5]:
                print(f"  occurrence: {occurrence.figure} ({', '.join(occurrence.words)})")
    return 0


def _cmd_numbers(args: argparse.Namespace) -> int:
    """Handle the ``numbers`` sub-command — Arabic number extraction and classification."""
    from aranorm.analysis.numeric_analyzer import analyze_numeric

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_numeric(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Words       : {result.word_count}")
        print(f"Western     : {result.western_count}   Arabic-Indic : {result.arabic_indic_count}")
        print(f"Written     : {result.written_count}   Percentages  : {result.percentage_count}")
        print(f"Currency    : {result.currency_count}   Mix systems  : {result.digit_system_mix}")
        print(f"Density     : {result.numeric_density:.4f}")
        if result.spans:
            for span in result.spans[:8]:
                print(f"  {span.category:<16} {span.text!r}")
    return 0


def _cmd_quotation(args: argparse.Namespace) -> int:
    """Handle the ``quotation`` sub-command — quotation environment analysis."""
    from aranorm.analysis.quotation_analyzer import analyze_quotations

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_quotations(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Words        : {result.word_count}")
        print(f"Quotation    : {result.quotation_ratio:.4f} ({result.label})")
        types = ", ".join(f"{category}={count}" for category, count in result.quotation_types.items()) or "(none)"
        print(f"Types        : {types}")
        print(f"Partial      : {result.partial_count}")
        if result.spans:
            for span in result.spans[:8]:
                print(f"  {span.category:<16} {span.text!r}")
    return 0


def _cmd_loans(args: argparse.Namespace) -> int:
    """Handle the ``loans`` sub-command — loanword and foreign-word detection."""
    from aranorm.analysis.loanword_analyzer import analyze_loanwords

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_loanwords(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Words        : {result.word_count}")
        print(f"Loanwords    : {result.loanword_count} ({result.loanword_ratio:.4f})")
        print(f"Latin        : {result.latin_count} ({result.latin_ratio:.4f})")
        print(f"Density      : {result.foreign_density:.4f} ({result.label})")
        if result.samples:
            print(f"Samples      : {', '.join(result.samples)}")
        if result.spans:
            for span in result.spans[:8]:
                print(f"  {span.category:<18} {span.text!r}")
    return 0


def _cmd_roots(args: argparse.Namespace) -> int:
    """Handle the ``roots`` sub-command — trilateral-root derivation profile."""
    from aranorm.analysis.root_density_analyzer import analyze_root_density

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_root_density(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Words        : {result.root_count}")
        print(f"Unique roots : {result.unique_roots}")
        print(f"Diversity    : {result.diversity_index:.4f} ({result.label})")
        print(f"Hapax        : {result.hapax_ratio:.4f}")
        if result.top_root:
            print(f"Top root     : {result.top_root['root']} (x{result.top_root['frequency']})")
    return 0


def _cmd_contrast(args: argparse.Namespace) -> int:
    """Handle the ``contrast`` sub-command — Arabic antonym (تضاد) detection."""
    from aranorm.analysis.contrast_analyzer import analyze_contrast

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_contrast(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Label          : {result.label}")
        print(f"Contrast pairs : {len(result.contrast_pairs)}")
        print(f"Unique pairs   : {result.unique_pairs}")
        print(f"Density        : {result.contrast_density:.4f}")
        for pair in result.contrast_pairs:
            print(f"  - {pair.member_a} ⬌ {pair.member_b} @ {pair.second_start}")
    return 0


def _cmd_fillers(args: argparse.Namespace) -> int:
    """Handle the ``fillers`` sub-command — filler / repetition detection."""
    from aranorm.analysis.filler_analyzer import analyze_fillers

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_fillers(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Label             : {result.label}")
        print(f"Filler phrases    : {result.filler_count}")
        print(f"Repetitions       : {result.repetition_count}")
        print(f"Filler density    : {result.filler_density:.4f}")
        print(f"Repetition density: {result.repetition_density:.4f}")
        for span in result.filler_spans:
            print(f"  filler  : {span.text!r} @ {span.start}")
        for rspan in result.repetition_spans:
            print(f"  repeat  : {rspan.word!r} @ {rspan.second_start}")
    return 0


def _cmd_complexity(args: argparse.Namespace) -> int:
    """Handle the ``complexity`` sub-command — morphological complexity profile."""
    from aranorm.analysis.complexity_analyzer import analyze_complexity

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_complexity(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Label           : {result.label}")
        print(f"Avg word length : {result.avg_word_length:.2f}")
        print(f"Max word length : {result.max_word_length}")
        print(f"Fused ratio     : {result.fused_ratio:.4f}")
        print(f"Word count      : {result.word_count}")
        distribution = result.length_distribution
        if distribution:
            print(
                "Distribution    : "
                + ", ".join(f"{key} letters→{value}" for key, value in sorted(distribution.items()))
            )
    return 0


# ── Entry point ────────────────────────────────────────────────────────────────


def _cmd_freqprofile(args: argparse.Namespace) -> int:
    """Handle the ``freqprofile`` sub-command — vocabulary frequency profile."""
    from aranorm.analysis.word_frequency import WordFrequencyProfiler

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    profiler = WordFrequencyProfiler(top_n=getattr(args, "top_n", 10))
    result = profiler.profile(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text           : {result.original_text[:80]}")
        print(f"Tokens         : {result.total_tokens}")
        print(f"Unique types   : {result.unique_types}")
        print(f"TTR            : {result.type_token_ratio:.4f}")
        print(f"Corrected TTR  : {result.corrected_ttr:.4f}")
        print(f"Root TTR       : {result.root_ttr:.4f}")
        print(f"Lexical density: {result.lexical_density:.4f}")
        if result.zipf_exponent is not None:
            print(f"Zipf exponent  : {result.zipf_exponent:.4f}")
        if result.frequency_table:
            print("\nTop words:")
            for entry in result.frequency_table[: args.top_n]:
                print(f"  #{entry.rank:<3} {entry.word:<15} x{entry.count:<4} " f"({entry.relative_frequency:.2%})")
    return 0


def _cmd_coherence(args: argparse.Namespace) -> int:
    """Handle the ``coherence`` sub-command — deterministic coherence score."""
    from aranorm.analysis.coherence_score import analyze_coherence

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_coherence(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text       : {result.text[:80]}")
        print(f"Score      : {result.score:.4f} ({result.label})")
        print(f"Sentences  : {result.sentence_count}")
        print(f"Connectives: {result.connective_count}")
        if result.breakdown:
            print("\nAxis breakdown:")
            for item in result.breakdown:
                print(f"  {item.axis:<20} {item.value:.4f} (weight {item.weight})")
    return 0


# @@@ R17_WP2_CLI_MARKER


def _cmd_spelling(args: argparse.Namespace) -> int:
    """Handle the ``spelling`` sub-command — spelling report for text."""
    from aranorm.analysis.spelling_report import analyze_spelling

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1

    report = analyze_spelling(text)

    if args.json:
        print(
            json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Original   : {report.original_text}")
        print(f"Corrected  : {report.corrected_text}")
        print(f"Words      : {report.total_words}")
        print(f"Issues     : {report.spelling_issues_found} ({report.unique_issues} unique)")
        print(f"Correct    : {report.correct_ratio:.0%}")
        if report.corrections:
            print("\nCorrections:")
            for correction in report.corrections:
                print(
                    f"  {correction.word} -> {correction.replacement} " f"(x{correction.count}, {correction.category})"
                )
        if report.category_distribution:
            print("\nCategory distribution:")
            for category, count in sorted(report.category_distribution.items(), key=lambda item: -item[1]):
                print(f"  {category}: {count}")
    return 0


def _cmd_quality(args: argparse.Namespace) -> int:
    """Handle the ``quality`` sub-command — composite quality score for text."""
    from aranorm.analysis.quality_score import analyze_quality

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1

    result = analyze_quality(text)

    if args.json:
        print(
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Quality score : {result.score}/100 ({result.label})")
        print("\nComponents:")
        for component in result.components:
            print(f"  {component.name}: {component.score:.1f} (weight {component.weight:.0%})")
        if result.issues:
            print("\nIssues:")
            for issue in result.issues:
                print(f"  - {issue}")
        if result.suggestions:
            print("\nSuggestions:")
            for suggestion in result.suggestions:
                print(f"  * {suggestion}")
    return 0


def _cmd_profile(args: argparse.Namespace) -> int:
    """Handle the ``profile`` sub-command — corpus-level batch analysis."""
    from aranorm.analysis.batch_analysis import analyze_batch

    try:
        with open(args.file, encoding="utf-8") as fh:
            docs = [line.rstrip("\n") for line in fh if line.strip()]
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    if not docs:
        print("Error: input file is empty.", file=sys.stderr)
        return 1

    report = analyze_batch(docs)

    if args.json:
        print(
            json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Texts        : {report.texts_count}")
        print(f"Total words  : {report.total_tokens}")
        print(f"Total chars  : {report.total_chars}")
        print(f"Avg quality  : {report.avg_quality_score}/100")
        print(f"Lexical div. : {report.corpus_lexical_diversity:.4f}")
        print(f"Unique words : {report.unique_words}")
        print(f"Readability  : {report.avg_readability}/100")
        print(f"Spelling     : {report.spelling_issues_total} issue(s)")
        print("\nQuality distribution:")
        for band, count in report.quality_distribution.to_dict().items():
            print(f"  {band}: {count}")
        if report.language_distribution:
            print("\nLanguage distribution:")
            for label, count in sorted(report.language_distribution.items(), key=lambda item: -item[1]):
                print(f"  {label}: {count}")
        if report.dialect_distribution:
            print("\nDialect distribution:")
            for label, count in sorted(report.dialect_distribution.items(), key=lambda item: -item[1]):
                print(f"  {label}: {count}")
        if report.top_issues:
            print("\nTop spelling issues:")
            for issue in report.top_issues[:5]:
                print(f"  {issue['correction']} (x{issue['count']})")
        print("\nRecommendations:")
        for recommendation in report.recommendations:
            print(f"  * {recommendation}")
    return 0


def _cmd_entities(args: argparse.Namespace) -> int:
    """Handle the ``entities`` sub-command — named entity extraction."""
    from aranorm.analysis.entity_analyzer import EntityAnalyzer

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()

    analyzer = EntityAnalyzer()
    result = analyzer.analyze(text)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text        : {result.original_text[:80]}")
        print(f"Entities    : {result.entity_count}")
        print(f"Persons     : {result.person_count}")
        print(f"Locations   : {result.location_count}")
        print(f"Orgs        : {result.organization_count}")
        print(f"Money       : {result.money_count}")
        print(f"Dates       : {result.date_count}")
        print(f"Phones      : {result.phone_count}")
        if result.entities:
            print("\nDetected entities:")
            for entity in result.entities:
                print(f"  [{entity.entity_type}] {entity.text} ({entity.start}:{entity.end})")
    return 0


def _cmd_topics(args: argparse.Namespace) -> int:
    """Handle the ``topics`` sub-command — topic classification."""
    from aranorm.analysis.topic_classifier import TopicClassifier

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()

    classifier = TopicClassifier()
    result = classifier.classify(text)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text          : {result.original_text[:80]}")
        print(f"Primary topic : {result.primary_topic}")
        print(f"Score         : {result.primary_score:.1f}")
        print(f"Confidence    : {result.confidence:.0%}")
        print(f"Topic words   : {result.topic_word_count} / {result.word_count}")
        print("\nTop topics:")
        for topic in result.top_topics:
            scores = [score for score in result.scores if score.topic == topic]
            if scores:
                print(f"  {topic}: {scores[0].score:.1f} (coverage {scores[0].coverage:.0%})")
    return 0


def _cmd_pronouns(args: argparse.Namespace) -> int:
    """Handle the ``pronouns`` sub-command — clitic and pronoun decomposition."""
    from aranorm.analysis.pronoun_analyzer import PronounAnalyzer

    analyzer = PronounAnalyzer()
    tokens: List[str] = []
    if args.text:
        tokens = [args.text]
    elif args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                tokens = [line.rstrip("\n").strip() for line in fh if line.strip()]
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    else:
        tokens = [line.rstrip("\n").strip() for line in sys.stdin if line.strip()]

    results = analyzer.analyze_tokens(tokens)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            role = f" [{r.pronoun_role}]" if r.has_pronoun else ""
            print(f"{r.original_token} -> stem={r.stem!r}{role}  prefix={r.prefixes} suffix={r.suffixes}")
    return 0


def _cmd_idioms(args: argparse.Namespace) -> int:
    """Handle the ``idioms`` sub-command — idiom and fixed expression detection."""
    from aranorm.analysis.idiom_analyzer import IdiomAnalyzer

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()

    analyzer = IdiomAnalyzer()
    result = analyzer.analyze(text)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text         : {result.original_text[:80]}")
        print(f"Idioms found : {result.idiom_count} ({len(result.unique_idioms)} unique)")
        if result.idioms:
            print("\nDetected idioms:")
            for idiom in result.idioms:
                print(f"  [{idiom.category}] {idiom.text} -> {idiom.canonical} ({idiom.start}:{idiom.end})")
    return 0


def _cmd_rquestions(args: argparse.Namespace) -> int:
    """Handle the ``rquestions`` sub-command — rhetorical question detection."""
    from aranorm.analysis.rhetorical_question_analyzer import analyze_rquestions

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_rquestions(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text         : {result.questions[0].text[:80] if result.questions else ''}")
        print(f"Questions    : {len(result.questions)} ({result.label})")
        print(
            f"Inversion    : {result.inversion_questions}   "
            f"Direct       : {result.direct_questions}   "
            f"Markers      : {result.rhetorical_markers}"
        )
        print(f"Density      : {result.question_density:.4f} per 100 words")
        for question in result.questions[:10]:
            print(f"  [{question.question_type}] {question.text} ({question.start}:{question.end})")
    return 0


def _cmd_anaphora(args: argparse.Namespace) -> int:
    """Handle the ``anaphora`` sub-command — anaphora and cohesion analysis."""
    from aranorm.analysis.anaphora_analyzer import analyze_anaphora

    text = args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read().rstrip("\n")
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
    if not text:
        text = sys.stdin.read()
    result = analyze_anaphora(text)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Text         : {result.attached_pronouns[0].text[:80] if result.attached_pronouns else ''}")
        print(f"Label        : {result.label}")
        print(
            f"Attached     : {result.attached_pronoun_count}   "
            f"Independent  : {result.independent_pronoun_count}   "
            f"Demonstrative: {result.demonstrative_count}   "
            f"Relative     : {result.relative_reference_count}"
        )
        print(
            f"Re-mentions  : {result.lexical_remention_count}  |  "
            f"Cohesion     : {result.cohesion_score:.4f}  |  "
            f"Density      : {result.reference_density:.4f} per 100 words"
        )
        print(f"Words        : {result.word_count}  |  Sentences  : {result.sentence_count}")
        if result.lexical_rementions:
            print(f"Re-mentioned : {', '.join(result.lexical_rementions[:10])}")
    return 0


def _cmd_snapshot(args: argparse.Namespace) -> int:
    """Handle the ``snapshot`` sub-command — save or restore config snapshots."""
    from aranorm import ArabicNormalizationPipeline, PipelineConfig
    from aranorm.core.snapshot import PipelineSnapshot, snapshot_pipeline

    if args.snapshot_command == "save":
        try:
            pipeline = ArabicNormalizationPipeline(PipelineConfig(preset=args.preset))
            snapshot = snapshot_pipeline(pipeline.config)
            content = snapshot.save(args.output)
        except (OSError, ValueError, TypeError) as error:
            print(f"Error: could not save snapshot: {error}", file=sys.stderr)
            return 1
        if args.json:
            print(content)
        else:
            print(f"Saved pipeline snapshot to {args.output}")
            print(f"AraNorm version: {snapshot.aranorm_version}")
            print(f"Preset: {snapshot.config.get('preset')}")
            print(f"Stages: {len(snapshot.stage_order)}")
        return 0

    if args.snapshot_command == "restore":
        try:
            snapshot = PipelineSnapshot.load(args.input)
        except (OSError, ValueError, TypeError) as error:
            print(f"Error: could not load snapshot: {error}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"Snapshot     : {args.input}")
            print(f"AraNorm      : {snapshot.aranorm_version}")
            print(f"Preset       : {snapshot.config.get('preset')}")
            print(f"Schema       : {snapshot.schema_version}")
            print(f"Stage order  : {', '.join(snapshot.stage_order)}")
            if snapshot.metadata:
                print(f"Metadata     : {snapshot.metadata}")
        return 0

    print("Error: a snapshot sub-command is required.", file=sys.stderr)
    return 2


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
        "describe": _cmd_describe,
        "plugins": _cmd_plugins,
        "readability": _cmd_readability,
        "summarize": _cmd_summarize,
        "detect": _cmd_detect,
        "batch": _cmd_batch,
        "corpus": _cmd_corpus,
        "spelling": _cmd_spelling,
        "quality": _cmd_quality,
        "profile": _cmd_profile,
        "serve": _cmd_serve,
        "stream": _cmd_stream,
        "spec": _cmd_spec,
        "entities": _cmd_entities,
        "topics": _cmd_topics,
        "pronouns": _cmd_pronouns,
        "idioms": _cmd_idioms,
        "snapshot": _cmd_snapshot,
        "freqprofile": _cmd_freqprofile,
        "coherence": _cmd_coherence,
        "style": _cmd_style,
        "emotions": _cmd_emotions,
        "textprofile": _cmd_textprofile,
        "rhythm": _cmd_rhythm,
        "figurate": _cmd_figurate,
        "numbers": _cmd_numbers,
        "quotation": _cmd_quotation,
        "loans": _cmd_loans,
        "roots": _cmd_roots,
        "contrast": _cmd_contrast,
        "fillers": _cmd_fillers,
        "complexity": _cmd_complexity,
        "rquestions": _cmd_rquestions,
        "anaphora": _cmd_anaphora,
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
