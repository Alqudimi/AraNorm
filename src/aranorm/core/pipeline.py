"""Public Arabic normalization pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from copy import deepcopy
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from itertools import islice
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple, cast

from aranorm.core.base import ProcessorContext
from aranorm.core.config import DialectTarget, PipelineConfig, Preset
from aranorm.core.contracts import (
    BatchProcessingPolicy,
    BatchRetryPolicy,
    BatchRetryReport,
    CancellationToken,
    ErrorHandler,
    PipelineHooks,
    ProgressCallbackProtocol,
)
from aranorm.core.metrics import ProcessingMetrics, ProcessingMetricsSnapshot
from aranorm.core.spec import PipelineSpec
from aranorm.stages.cleaner import ContentCleaner
from aranorm.stages.dialect_id import DialectIdentifier
from aranorm.stages.dialect_norm import DialectNormalizer
from aranorm.stages.normalizer import OrthographicNormalizer
from aranorm.stages.stop_words_stage import StopWordsStage
from aranorm.exceptions import BatchProcessingError
from aranorm.utils.chunker import chunk_text
from aranorm.utils.validators import validate_text

LOGGER = logging.getLogger(__name__)


@dataclass
class NormalizationResult:
    """Result returned for one input text.

    Attributes
    ----------
    original_text:
        The raw input string before any processing.
    normalized_text:
        Text after all enabled normalization steps.
    dialect:
        Detected dialect label (e.g. ``"EGY"``, ``"GLF"``, ``"MSA"``).
    dialect_confidence:
        Confidence score for the dialect detection (0.0–1.0).
    coda_text:
        CODA-normalized text (populated when ``dialect_target="coda"``).
    msa_text:
        MSA-normalized text (populated when ``dialect_target="msa"``).
    processing_metadata:
        Internal metadata dict from the processor context.
    applied_steps:
        Ordered list of processor names that ran.
    stop_words_removed:
        Text with stop words removed (populated when ``stop_words_config`` is set).
    stop_words_found:
        Set of stop words found in the normalized text.
    stop_words_stats:
        Dict of stop-word statistics (count, percentage, by_category).
    stop_words_by_category:
        Stop words grouped by linguistic category.
    stop_words_by_dialect:
        Stop words grouped by dialect source.
    applied_stop_words_steps:
        Stop-words pipeline step identifiers.
    steps_trace:
        Ordered trace of ``(processor, action)`` pairs recorded during one-item
        processing. Populated only when ``emit_steps_trace=True`` is requested,
        otherwise ``None``.
    """

    original_text: str
    normalized_text: str
    dialect: Optional[str] = None
    dialect_confidence: Optional[float] = None
    coda_text: Optional[str] = None
    msa_text: Optional[str] = None
    processing_metadata: Dict[str, Any] = field(default_factory=dict)
    applied_steps: List[str] = field(default_factory=list)
    processing_time_ms: Optional[float] = None
    # ── Stop-words fields (populated when stop_words_config is set) ──────
    stop_words_removed: Optional[str] = None
    stop_words_found: Optional[Set[str]] = None
    stop_words_stats: Optional[Dict[str, Any]] = None
    stop_words_by_category: Optional[Dict[str, List[str]]] = None
    stop_words_by_dialect: Optional[Dict[str, List[str]]] = None
    applied_stop_words_steps: Optional[List[str]] = None
    steps_trace: Optional[List[Tuple[str, str]]] = None

    # ── Convenience properties ────────────────────────────────────────────

    @property
    def dialect_label(self) -> Optional[str]:
        """Alias for the dialect label."""
        return self.dialect

    @property
    def confidence_score(self) -> Optional[float]:
        """Alias for the dialect confidence."""
        return self.dialect_confidence

    @property
    def is_msa(self) -> Optional[bool]:
        """Return whether the detected dialect is MSA."""
        return self.dialect == "MSA" if self.dialect is not None else None

    def __repr__(self) -> str:
        dialect_str = f", dialect={self.dialect!r}" if self.dialect else ""
        time_str = f", time={self.processing_time_ms:.1f}ms" if self.processing_time_ms else ""
        return f"NormalizationResult(" f"normalized={self.normalized_text[:40]!r}" f"{dialect_str}" f"{time_str})"

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary representation.

        All :class:`set` fields are converted to sorted lists so the
        result is directly compatible with ``json.dumps``.

        Example
        -------
        >>> result.to_dict()["dialect"]
        'GLF'
        """
        return {
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "processing_metadata": deepcopy(self.processing_metadata),
            "dialect": self.dialect,
            "dialect_confidence": self.dialect_confidence,
            "coda_text": self.coda_text,
            "msa_text": self.msa_text,
            "applied_steps": list(self.applied_steps),
            "processing_time_ms": self.processing_time_ms,
            "stop_words_removed": self.stop_words_removed,
            "stop_words_found": (sorted(self.stop_words_found) if self.stop_words_found is not None else None),
            "stop_words_stats": deepcopy(self.stop_words_stats),
            "stop_words_by_category": deepcopy(self.stop_words_by_category),
            "stop_words_by_dialect": deepcopy(self.stop_words_by_dialect),
            "applied_stop_words_steps": (
                list(self.applied_stop_words_steps) if self.applied_stop_words_steps is not None else None
            ),
            "steps_trace": (
                [[step, action] for step, action in self.steps_trace] if self.steps_trace is not None else None
            ),
        }

    def to_json(self, indent: Optional[int] = 2, ensure_ascii: bool = False) -> str:
        """Return a JSON string of the result.

        Parameters
        ----------
        indent:
            JSON indentation level (default 2).
        ensure_ascii:
            When *False* (default), Arabic characters are preserved as-is.

        Example
        -------
        >>> print(result.to_json())
        {
          "normalized_text": "شلونك",
          ...
        }
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizationResult":
        """Reconstruct a :class:`NormalizationResult` from a ``to_dict`` payload.

        Parameters
        ----------
        data:
            Dictionary produced by :meth:`to_dict`.
        """
        found = data.get("stop_words_found")
        return cls(
            original_text=data.get("original_text", ""),
            normalized_text=data.get("normalized_text", ""),
            dialect=data.get("dialect"),
            dialect_confidence=data.get("dialect_confidence"),
            coda_text=data.get("coda_text"),
            msa_text=data.get("msa_text"),
            processing_metadata=deepcopy(data.get("processing_metadata", {})),
            applied_steps=list(data.get("applied_steps", [])),
            processing_time_ms=data.get("processing_time_ms"),
            stop_words_removed=data.get("stop_words_removed"),
            stop_words_found=set(found) if found is not None else None,
            stop_words_stats=deepcopy(data.get("stop_words_stats")),
            stop_words_by_category=deepcopy(data.get("stop_words_by_category")),
            stop_words_by_dialect=deepcopy(data.get("stop_words_by_dialect")),
            applied_stop_words_steps=(
                list(data["applied_stop_words_steps"]) if data.get("applied_stop_words_steps") is not None else None
            ),
            steps_trace=(
                [(str(step), str(action)) for step, action in data["steps_trace"]]
                if isinstance(data.get("steps_trace"), list)
                else None
            ),
        )

    def to_csv_row(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Return a flat dictionary suitable for writing to CSV.

        Set fields are converted to pipe-separated strings.

        Parameters
        ----------
        fields:
            Which fields to include. When *None* a default set is used.

        Example
        -------
        >>> import csv
        >>> with open("out.csv", "w") as f:
        ...     writer = csv.DictWriter(f, fieldnames=["original_text", "normalized_text", "dialect"])
        ...     writer.writeheader()
        ...     writer.writerow(result.to_csv_row(["original_text", "normalized_text", "dialect"]))
        """
        _default = [
            "original_text",
            "normalized_text",
            "dialect",
            "dialect_confidence",
            "stop_words_removed",
            "stop_words_found",
        ]
        selected = fields or _default
        row: Dict[str, Any] = {}
        for f in selected:
            value = getattr(self, f, None)
            if isinstance(value, (set, frozenset)):
                value = "|".join(sorted(value)) if value else ""
            elif isinstance(value, list):
                value = "|".join(str(v) for v in value)
            row[f] = value
        return row


@dataclass
class AnalysisReport:
    """Analytical report for one pipeline normalization run.

    Bundles the :class:`NormalizationResult` with derived diagnostics:
    the character-level change ratio, a dialect-confidence band, a
    per-step summary of what ran, and the raw positions that changed
    between the original and the normalized text.

    Attributes
    ----------
    result:
        The underlying normalization result.
    input_length:
        Character count of the original text.
    output_length:
        Character count of the normalized text.
    change_ratio:
        Absolute fraction of characters changed
        (``changed_positions / input_length``).
    confidence_band:
        ``"high"`` when confidence >= 0.8, ``"medium"`` for
        ``0.5 <= confidence < 0.8``, ``"low"`` otherwise.
    step_summary:
        Mapping ``processor_name -> invocation_count`` from the applied
        steps.
    diff_changed_positions:
        Number of character positions where the normalized text differs
        from the original, plus any length difference.

    Example
    -------
    >>> report = AnalysisReport.from_result(result)
    >>> 0.0 <= report.change_ratio <= 1.0
    True
    """

    result: "NormalizationResult"
    input_length: int
    output_length: int
    change_ratio: float
    confidence_band: str
    step_summary: Dict[str, int]
    diff_changed_positions: int

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dictionary.

        Example
        -------
        >>> report.to_dict()["confidence_band"] in ("high", "medium", "low")
        True
        """
        return {
            "input_length": self.input_length,
            "output_length": self.output_length,
            "change_ratio": self.change_ratio,
            "confidence_band": self.confidence_band,
            "confidence": self.result.dialect_confidence,
            "dialect": self.result.dialect,
            "step_summary": dict(self.step_summary),
            "diff_changed_positions": self.diff_changed_positions,
            "processing_time_ms": self.result.processing_time_ms,
        }

    @classmethod
    def from_result(cls, result: "NormalizationResult") -> "AnalysisReport":
        """Build a report from a single :class:`NormalizationResult`.

        Parameters
        ----------
        result:
            A result produced by
            :meth:`ArabicNormalizationPipeline.process`.
        """
        original = result.original_text or ""
        normalized = result.normalized_text or ""
        input_length = len(original)
        output_length = len(normalized)

        compared = min(input_length, output_length)
        changed = sum(1 for index in range(compared) if original[index] != normalized[index]) + abs(
            input_length - output_length
        )
        change_ratio = changed / input_length if input_length else 0.0

        confidence = result.dialect_confidence
        if confidence is None:
            band = "low"
        elif confidence >= 0.8:
            band = "high"
        elif confidence >= 0.5:
            band = "medium"
        else:
            band = "low"

        step_summary: Dict[str, int] = {}
        for step in result.applied_steps or []:
            step_summary[step] = step_summary.get(step, 0) + 1

        return cls(
            result=result,
            input_length=input_length,
            output_length=output_length,
            change_ratio=round(change_ratio, 4),
            confidence_band=band,
            step_summary=step_summary,
            diff_changed_positions=changed,
        )


class ArabicNormalizationPipeline:
    """Composable, production-oriented Arabic text normalization pipeline.

    Parameters
    ----------
    config:
        :class:`~aranorm.core.config.PipelineConfig` instance.  A default
        ``standard`` config is used when omitted.
    cleaner:
        Custom :class:`~aranorm.stages.cleaner.ContentCleaner`.
    normalizer:
        Custom :class:`~aranorm.stages.normalizer.OrthographicNormalizer`.
    dialect_identifier:
        Custom :class:`~aranorm.stages.dialect_id.DialectIdentifier`.

    Example
    -------
    >>> pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
    >>> result = pipeline.process("شلونك حبيبي؟")
    >>> result.normalized_text
    'شلونك حبيبي؟'
    >>> result.dialect
    'GLF'
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        cleaner: Optional[ContentCleaner] = None,
        normalizer: Optional[OrthographicNormalizer] = None,
        dialect_identifier: Optional[DialectIdentifier] = None,
        metrics: Optional[ProcessingMetrics] = None,
        hooks: Optional[PipelineHooks] = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.config.validate()
        self.metrics = metrics or ProcessingMetrics()
        self.hooks = hooks or PipelineHooks()
        self.cleaner = cleaner or ContentCleaner(self.config)
        self.normalizer = normalizer or OrthographicNormalizer(self.config)
        self.dialect_identifier = dialect_identifier or DialectIdentifier(self.config.supported_dialects)
        self.dialect_normalizer = (
            DialectNormalizer(cast(DialectTarget, self.config.dialect_target).value)
            if self.config.dialect_target != DialectTarget.NONE
            else None
        )
        self.stop_words_stage = (
            StopWordsStage(config=self.config.stop_words_config) if self.config.stop_words_config is not None else None
        )

    # ── Factory methods ───────────────────────────────────────────────────

    @classmethod
    def builder(cls) -> "PipelineBuilder":
        """Return a builder for a custom pipeline."""
        return PipelineBuilder()

    @classmethod
    def from_preset(cls, preset: str, **overrides: Any) -> "ArabicNormalizationPipeline":
        """Create a pipeline from a named preset with optional overrides.

        Parameters
        ----------
        preset:
            One of ``"light"``, ``"standard"``, ``"deep"``, ``"social_media"``.
        **overrides:
            Any :class:`~aranorm.core.config.PipelineConfig` field to override.

        Example
        -------
        >>> pipeline = ArabicNormalizationPipeline.from_preset(
        ...     "deep", remove_diacritics=True
        ... )
        """
        config = PipelineConfig(preset=preset, **overrides)
        return cls(config=config)

    @classmethod
    def from_config_dict(cls, data: Dict[str, Any]) -> "ArabicNormalizationPipeline":
        """Create a pipeline from a plain configuration dictionary.

        Parameters
        ----------
        data:
            A dict whose keys match :class:`~aranorm.core.config.PipelineConfig`
            field names.

        Example
        -------
        >>> pipeline = ArabicNormalizationPipeline.from_config_dict({
        ...     "preset": "standard",
        ...     "clean_urls": True,
        ... })
        """
        config = PipelineConfig.from_dict(data)
        return cls(config=config)

    # ── Single-text processing ─────────────────────────────────────────────

    def process(self, text: str) -> NormalizationResult:
        """Process one text and record an operational metrics sample.

        Metrics are observational only and never replace or suppress the
        original result or exception.
        """
        started = time.perf_counter()
        try:
            result = self._process_unmeasured(text)
        except Exception as exc:  # noqa: BLE001
            if self.hooks.on_error is not None:
                try:
                    self.hooks.on_error(text, exc)
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Pipeline error hook failed")
            self.metrics.record(success=False, elapsed_ms=(time.perf_counter() - started) * 1000)
            raise
        self.metrics.record(success=True, elapsed_ms=(time.perf_counter() - started) * 1000)
        return result

    def _process_unmeasured(self, text: str) -> NormalizationResult:
        """Process one text without recording metrics.

        This private seam keeps the public operation small and makes the
        observability boundary explicit without duplicating normalization code.

        Parameters
        ----------
        text:
            Input Arabic string.

        Returns
        -------
        NormalizationResult
            Contains the normalized text, detected dialect, and optional
            stop-words analysis.

        Raises
        ------
        InvalidTextError
            If *text* is not a string.
        """
        t_start = time.perf_counter()
        limits = self.config.resource_limits
        original_text = validate_text(
            text,
            max_length=limits.max_text_length,
            reject_null_bytes=limits.reject_null_bytes,
        )
        if self.hooks.before_process is not None:
            original_text = validate_text(
                self.hooks.before_process(original_text),
                max_length=limits.max_text_length,
                reject_null_bytes=limits.reject_null_bytes,
            )
        context = ProcessorContext()
        if self.config.emit_steps_trace:
            context.enable_trace()
        cleaned = self.cleaner.process(original_text, context)
        normalized = self.normalizer.process(cleaned, context)
        identification = self.dialect_identifier.identify(normalized)
        context.metadata["is_msa"] = identification.is_msa
        result = NormalizationResult(
            original_text=original_text,
            normalized_text=normalized,
            dialect=identification.dialect_label,
            dialect_confidence=identification.confidence_score,
            processing_metadata=context.metadata,
            applied_steps=context.applied_steps,
        )
        if self.dialect_normalizer is not None:
            target_text = self.dialect_normalizer.process(normalized, context)
            if self.config.dialect_target == DialectTarget.CODA:
                result.coda_text = target_text
            else:
                result.msa_text = target_text
            result.applied_steps = context.applied_steps
        # ── Stop-words stage ──────────────────────────────────────────────
        if self.stop_words_stage is not None:
            self.stop_words_stage.execute(normalized, context)
            sw_result = context.metadata.get("stop_words_result")
            if sw_result is not None:
                result.stop_words_removed = sw_result.stop_words_removed
                result.stop_words_found = sw_result.stop_words_found
                result.stop_words_stats = sw_result.stop_words_stats
                result.stop_words_by_category = sw_result.stop_words_by_category
                result.stop_words_by_dialect = sw_result.stop_words_by_dialect
                result.applied_stop_words_steps = sw_result.applied_stop_words_steps
            result.applied_steps = context.applied_steps
        if self.config.emit_steps_trace:
            result.steps_trace = context.steps_trace()
        result.processing_time_ms = round((time.perf_counter() - t_start) * 1000, 3)
        if self.hooks.after_process is not None:
            self.hooks.after_process(result)
        return result

    def process_long_text(
        self,
        text: str,
        max_chunk_tokens: int = 512,
        overlap_tokens: int = 0,
    ) -> NormalizationResult:
        """Normalize a text too long for a single pass by chunking it first.

        The input is split into token-budgeted chunks (via
        :func:`aranorm.utils.chunker.chunk_text`), each chunk is normalized
        independently, and the outcomes are merged into one
        :class:`NormalizationResult` whose ``normalized_text`` is the
        concatenation of the chunk results.

        Parameters
        ----------
        text:
            The (possibly very long) input Arabic string.
        max_chunk_tokens:
            Token budget per chunk (default ``512``).
        overlap_tokens:
            Token overlap between consecutive chunks (default ``0``).

        Returns
        -------
        NormalizationResult
            ``original_text`` is the full input. ``dialect``/
            ``dialect_confidence`` reflect the highest-confidence detection
            among the chunks, ``applied_steps`` is the union of all steps,
            and ``processing_time_ms`` accumulates every chunk.

        Example
        -------
        >>> pipeline = ArabicNormalizationPipeline()
        >>> result = pipeline.process_long_text("مرحبا بالعالم. " * 200)
        >>> bool(result.normalized_text)
        True
        """
        started = time.perf_counter()
        chunks = chunk_text(text, max_tokens=max_chunk_tokens, overlap_tokens=overlap_tokens)
        if not chunks:
            return self.process("")

        results = [self._process_unmeasured(chunk) for chunk in chunks]
        merged_normalized = " ".join(result.normalized_text for result in results if result.normalized_text)
        best = max(results, key=lambda item: item.dialect_confidence or 0.0)
        merged_metadata: Dict[str, Any] = {}
        for result in results:
            merged_metadata.update(result.processing_metadata or {})
        merged_steps: List[str] = []
        seen_steps: Set[str] = set()
        for result in results:
            for step in result.applied_steps:
                if step not in seen_steps:
                    seen_steps.add(step)
                    merged_steps.append(step)

        merged = NormalizationResult(
            original_text=text,
            normalized_text=merged_normalized,
            dialect=best.dialect,
            dialect_confidence=best.dialect_confidence,
            coda_text=next((result.coda_text for result in results if result.coda_text), None),
            msa_text=next((result.msa_text for result in results if result.msa_text), None),
            processing_metadata=merged_metadata,
            applied_steps=merged_steps,
        )
        merged.stop_words_removed = next(
            (result.stop_words_removed for result in results if result.stop_words_removed),
            None,
        )
        found_sets: Set[str] = set()
        for result in results:
            if result.stop_words_found:
                found_sets.update(result.stop_words_found)
        if found_sets:
            merged.stop_words_found = found_sets
        stats_list = [result.stop_words_stats for result in results if isinstance(result.stop_words_stats, dict)]
        if stats_list:
            total_count = sum(float(stat.get("count", 0) or 0) for stat in stats_list)
            avg_percentage = sum(float(stat.get("percentage", 0.0) or 0.0) for stat in stats_list) / len(stats_list)
            merged.stop_words_stats = {
                "count": total_count,
                "percentage": avg_percentage,
                "chunk_count": len(stats_list),
            }
        merged.processing_time_ms = round(sum(result.processing_time_ms or 0.0 for result in results), 3)
        if self.hooks.after_process is not None:
            self.hooks.after_process(merged)
        self.metrics.record(success=True, elapsed_ms=(time.perf_counter() - started) * 1000)
        return merged

    # ── Batch processing ───────────────────────────────────────────────────

    def process_batch(
        self,
        texts: Sequence[str],
        batch_size: int = 32,
        n_workers: int = 1,
        on_error: Optional[ErrorHandler] = None,
        progress_callback: Optional[ProgressCallbackProtocol] = None,
        policy: Optional[BatchProcessingPolicy] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[NormalizationResult]:
        """Process a sequence while preserving order and bounded worker memory.

        ``batch_size`` now controls the number of inputs submitted to the
        executor at once. For generator-based inputs use :meth:`process_iter`
        directly to avoid materializing the complete corpus.
        """
        limits = self.config.resource_limits
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if batch_size > limits.max_batch_size:
            raise ValueError(f"batch_size cannot exceed configured maximum {limits.max_batch_size}")
        if n_workers < 1:
            raise ValueError("n_workers must be positive")
        if n_workers > limits.max_workers:
            raise ValueError(f"n_workers cannot exceed configured maximum {limits.max_workers}")
        values = list(texts)
        if not values:
            return []
        return list(
            self.process_iter(
                values,
                batch_size=batch_size,
                n_workers=n_workers,
                on_error=on_error,
                progress_callback=progress_callback,
                total=len(values),
                policy=policy,
                cancellation_token=cancellation_token,
            )
        )

    def process_batch_retry(
        self,
        texts: Sequence[str],
        max_retries: int = 3,
        batch_size: int = 32,
        n_workers: int = 1,
        on_error: Optional[ErrorHandler] = None,
        progress_callback: Optional[ProgressCallbackProtocol] = None,
        policy: Optional[BatchProcessingPolicy] = None,
        cancellation_token: Optional[CancellationToken] = None,
        *,
        retry_policy: Optional[BatchRetryPolicy] = None,
    ) -> "BatchRetryReport":
        """Process a sequence with bounded retries for failed items.

        Each input is first submitted through :meth:`process_batch` with the
        given failure policy; any item that could not produce a result is then
        retried on its own (single-threaded, so retry failures cannot hide
        concurrency artefacts) until either it succeeds or *max_retries*
        attempts are exhausted.

        The returned :class:`BatchRetryReport` separates final results from
        definitively failed items so callers can decide how to proceed without
        losing traceability.

        Parameters
        ----------
        texts:
            Input sequence to process.
        max_retries:
            Number of additional attempts per failed item after the initial
            batch pass (must be in ``0..10``).
        batch_size:
            Submission chunk size forwarded to :meth:`process_batch`.
        n_workers:
            Worker count forwarded to :meth:`process_batch`.
        on_error:
            Fallback handler forwarded to :meth:`process_batch`.
        progress_callback:
            Lifecycle callback forwarded to :meth:`process_batch`.
        policy:
            Failure policy for the initial pass. ``fail_fast`` is **not**
            supported in retry mode because it aborts the batch before all
            failures are known; ``collect`` is enforced.
        cancellation_token:
            Cooperative cancellation forwarded to :meth:`process_batch`.

        Returns
        -------
        BatchRetryReport
            Ordered results for successful items plus the failed input
            indices and their last exception.
        """
        from aranorm.exceptions import ConfigurationError

        if retry_policy is not None:
            if not isinstance(retry_policy, BatchRetryPolicy):
                raise TypeError("retry_policy must be a BatchRetryPolicy instance")
            max_retries = retry_policy.max_retries
            batch_size = retry_policy.batch_size
            n_workers = retry_policy.n_workers

        if not isinstance(max_retries, int) or isinstance(max_retries, bool):
            raise ValueError("max_retries must be a non-negative integer")
        if max_retries < 0 or max_retries > 10:
            raise ValueError("max_retries must be between 0 and 10")

        active_policy = policy or BatchProcessingPolicy(mode="collect")
        if active_policy.mode == "fail_fast":
            raise ConfigurationError(
                "process_batch_retry requires BatchProcessingPolicy(mode='collect' or 'skip'); "
                "fail_fast aborts the batch before all failures are known."
            )

        values = list(texts)
        if not values:
            return BatchRetryReport(
                results=[],
                failed_indices=[],
                retry_report={
                    "total_inputs": 0,
                    "max_retries": max_retries,
                    "retry_attempts": 0,
                    "recovered_count": 0,
                },
            )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        retry_attempts = 0
        recovered_count = 0
        retry_report: Dict[int, Exception] = {}
        initial_successes: Dict[int, NormalizationResult] = {}

        # The initial pass collects all failures into a single batch error
        # so the whole input is processed before any retry begins.
        failed: Dict[int, Exception] = {}
        try:
            initial = self.process_batch(
                values,
                batch_size=batch_size,
                n_workers=n_workers,
                on_error=on_error,
                progress_callback=progress_callback,
                policy=BatchProcessingPolicy(mode="collect"),
                cancellation_token=cancellation_token,
            )
            for index, result in enumerate(initial):

                if result is not None:
                    initial_successes[index] = result
                    continue
                failed[index] = RuntimeError("Item %d produced no result during the initial pass" % index)
        except BatchProcessingError as exc:
            # The collect policy appends results for successful items before
            # raising, so the exception itself carries the definitive failure map.
            # Rebuild per-index successes to keep input order deterministic.
            if exc.results is not None:
                known_failures = set(exc.errors or {})
                cursor = 0
                for index in range(len(values)):
                    if index not in known_failures and cursor < len(exc.results):
                        initial_successes[index] = exc.results[cursor]
                        cursor += 1
            if exc.errors:
                failed = dict(exc.errors)
        except Exception as exc:  # noqa: BLE001
            # All items failed catastrophically (e.g. cancelled or config error).
            return BatchRetryReport(
                results=[],
                failed_indices=list(range(len(values))),
                retry_report={
                    "total_inputs": len(values),
                    "max_retries": max_retries,
                    "retry_attempts": 0,
                    "recovered_count": 0,
                    "catastrophic_cause": type(exc).__name__,
                },
            )

        # Retry each failed item in input order, bounded and single-threaded.
        for index in sorted(failed):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            text = values[index]
            last_exc: Optional[Exception] = failed.get(index)
            for attempt in range(max_retries):
                try:
                    initial_successes[index] = self.process(text)
                    recovered_count += 1
                    last_exc = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    retry_attempts += 1
            if last_exc is not None:
                retry_report[index] = last_exc

        return BatchRetryReport(
            results=[initial_successes[i] for i in sorted(initial_successes)],
            failed_indices=sorted(retry_report),
            retry_report={
                "total_inputs": len(values),
                "max_retries": max_retries,
                "retry_attempts": retry_attempts,
                "recovered_count": recovered_count,
            },
        )

    def process_iter(
        self,
        texts: Iterable[str],
        batch_size: int = 32,
        n_workers: int = 1,
        on_error: Optional[ErrorHandler] = None,
        progress_callback: Optional[ProgressCallbackProtocol] = None,
        total: Optional[int] = None,
        policy: Optional[BatchProcessingPolicy] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Iterator[NormalizationResult]:
        """Process an iterable lazily with bounded memory and stable ordering.

        Inputs are consumed in chunks of ``batch_size``. At most one chunk is
        submitted to the thread pool at a time, so file or generator inputs can
        be processed without loading the full corpus. Results are yielded in
        input order even when ``n_workers`` is greater than one.

        When ``on_error`` is supplied, returning a string retries that item with
        the fallback; returning ``None`` skips the failed item. The callback
        receives the original zero-based input index. If ``cancellation_token``
        is cancelled, processing stops cooperatively at the next safe boundary
        and raises :class:`ProcessingCancelledError`.
        """
        limits = self.config.resource_limits
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if batch_size > limits.max_batch_size:
            raise ValueError(f"batch_size cannot exceed configured maximum {limits.max_batch_size}")
        if n_workers < 1:
            raise ValueError("n_workers must be positive")
        if n_workers > limits.max_workers:
            raise ValueError(f"n_workers cannot exceed configured maximum {limits.max_workers}")
        if total is not None and total < 0:
            raise ValueError("total cannot be negative")

        callback = progress_callback
        active_policy = policy or BatchProcessingPolicy()
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        if callback is not None:
            callback.on_start(total if total is not None else 0)

        failures: Dict[int, Exception] = {}
        results: List[NormalizationResult] = []
        index = 0
        executor: Optional[ThreadPoolExecutor] = None
        if n_workers > 1:
            executor = ThreadPoolExecutor(max_workers=n_workers)

        try:
            iterator = iter(texts)
            while True:
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                chunk = list(islice(iterator, batch_size))
                if not chunk:
                    break

                futures: List[Future[NormalizationResult]] = []
                if executor is not None:
                    futures = [executor.submit(self.process, text) for text in chunk]

                for offset, text in enumerate(chunk):
                    if cancellation_token is not None:
                        cancellation_token.raise_if_cancelled()
                    item_index = index + offset
                    success = True
                    result: Optional[NormalizationResult] = None
                    try:
                        result = futures[offset].result() if executor is not None else self.process(text)
                    except Exception as exc:  # noqa: BLE001
                        success = False
                        failure = exc
                        LOGGER.warning("Processing failed for item %d: %s", item_index, exc)
                        fallback = on_error(item_index, text, exc) if on_error is not None else None
                        if fallback is not None:
                            try:
                                result = self.process(fallback)
                                success = True
                            except Exception as inner_exc:  # noqa: BLE001
                                failure = inner_exc
                                LOGGER.warning(
                                    "Fallback processing also failed for item %d: %s",
                                    item_index,
                                    inner_exc,
                                )

                        if not success and active_policy.mode == "fail_fast" and on_error is None:
                            if executor is not None:
                                executor.shutdown(wait=False, cancel_futures=True)
                                executor = None
                            raise
                        if not success and active_policy.mode == "collect":
                            failures[item_index] = failure

                    if callback is not None:
                        callback.on_item(item_index, text, success)
                    if result is not None:
                        results.append(result)
                        yield result
                index += len(chunk)

            if failures and active_policy.mode == "collect":
                raise BatchProcessingError(
                    f"{len(failures)} item(s) failed during batch processing",
                    failed_indices=sorted(failures),
                    errors=failures,
                    results=list(results),
                )
        finally:
            if executor is not None:
                executor.shutdown(wait=True)
            if callback is not None:
                callback.on_finish()

    # ── Async interface ────────────────────────────────────────────────────

    async def process_async(self, text: str) -> NormalizationResult:
        """Async wrapper that runs :meth:`process` in a thread-pool executor.

        Suitable for use inside ``asyncio`` event loops (e.g. FastAPI, aiohttp).

        Parameters
        ----------
        text:
            Input Arabic string.

        Example
        -------
        >>> result = await pipeline.process_async("مرحباً")
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.process, text)

    async def process_batch_async(
        self,
        texts: Sequence[str],
        n_workers: int = 4,
        policy: Optional[BatchProcessingPolicy] = None,
        *,
        batch_size: int = 32,
        on_error: Optional[ErrorHandler] = None,
        progress_callback: Optional[ProgressCallbackProtocol] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[NormalizationResult]:
        """Process a sequence asynchronously with bounded executor submission.

        The async path preserves input order and mirrors the synchronous batch
        semantics for error policies, fallback handlers, and progress callbacks.
        At most ``batch_size`` items are submitted to the executor at once. A
        supplied ``cancellation_token`` stops submission and result consumption
        cooperatively at safe boundaries; running worker threads are not
        forcefully interrupted.
        """
        limits = self.config.resource_limits
        if n_workers < 1:
            raise ValueError("n_workers must be positive")
        if n_workers > limits.max_workers:
            raise ValueError(f"n_workers cannot exceed configured maximum {limits.max_workers}")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if batch_size > limits.max_batch_size:
            raise ValueError(f"batch_size cannot exceed configured maximum {limits.max_batch_size}")

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        values = list(texts)
        if len(values) > limits.max_batch_size:
            raise ValueError(f"async batch cannot exceed configured maximum {limits.max_batch_size} items")
        active_policy = policy or BatchProcessingPolicy()
        callback = progress_callback
        if callback is not None:
            callback.on_start(len(values))
        if not values:
            if callback is not None:
                callback.on_finish()
            return []

        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=n_workers)
        failures: Dict[int, Exception] = {}
        results: List[NormalizationResult] = []
        try:
            for start in range(0, len(values), batch_size):
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                chunk = values[start : start + batch_size]
                tasks = [loop.run_in_executor(executor, self.process, text) for text in chunk]
                if active_policy.mode == "fail_fast" and on_error is None:
                    chunk_results = await asyncio.gather(*tasks)
                    if cancellation_token is not None:
                        cancellation_token.raise_if_cancelled()
                    results.extend(chunk_results)
                    if callback is not None:
                        for offset, text in enumerate(chunk):
                            if cancellation_token is not None:
                                cancellation_token.raise_if_cancelled()
                            callback.on_item(start + offset, text, True)
                    continue

                chunk_values = await asyncio.gather(*tasks, return_exceptions=True)
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                for offset, (text, value) in enumerate(zip(chunk, chunk_values)):
                    if cancellation_token is not None:
                        cancellation_token.raise_if_cancelled()
                    item_index = start + offset
                    success = True
                    result: Optional[NormalizationResult] = None
                    if isinstance(value, BaseException):
                        if isinstance(value, asyncio.CancelledError):
                            raise value
                        success = False
                        failure = cast(Exception, value)
                        LOGGER.warning("Async processing failed for item %d: %s", item_index, failure)
                        fallback = on_error(item_index, text, failure) if on_error is not None else None
                        if fallback is not None:
                            if cancellation_token is not None:
                                cancellation_token.raise_if_cancelled()
                            try:
                                result = await loop.run_in_executor(executor, self.process, fallback)
                                success = True
                            except Exception as inner_exc:  # noqa: BLE001
                                failure = inner_exc
                                LOGGER.warning(
                                    "Async fallback processing also failed for item %d: %s",
                                    item_index,
                                    inner_exc,
                                )
                        if not success and active_policy.mode == "fail_fast" and on_error is None:
                            raise failure
                        if not success and active_policy.mode == "collect":
                            failures[item_index] = failure
                    else:
                        result = cast(NormalizationResult, value)

                    if callback is not None:
                        callback.on_item(item_index, text, success)
                    if result is not None:
                        results.append(result)

            if failures and active_policy.mode == "collect":
                raise BatchProcessingError(
                    f"{len(failures)} item(s) failed during async batch processing",
                    failed_indices=sorted(failures),
                    errors=failures,
                    results=list(results),
                )
            return results
        finally:
            await loop.run_in_executor(None, executor.shutdown, True)
            if callback is not None:
                callback.on_finish()

    async def process_batch_retry_async(
        self,
        texts: Sequence[str],
        max_retries: int = 3,
        n_workers: int = 4,
        policy: Optional[BatchProcessingPolicy] = None,
        *,
        batch_size: int = 32,
        on_error: Optional[ErrorHandler] = None,
        progress_callback: Optional[ProgressCallbackProtocol] = None,
        cancellation_token: Optional[CancellationToken] = None,
        retry_policy: Optional[BatchRetryPolicy] = None,
    ) -> "BatchRetryReport":
        """Process a sequence asynchronously with bounded item retries.

        The initial pass delegates to :meth:`process_batch_async` using the
        ``collect`` policy, then retries failed items one at a time through
        :meth:`process_async`.  This mirrors the synchronous retry contract
        while preserving cooperative cancellation and input-order results.
        """
        from aranorm.exceptions import ConfigurationError

        if retry_policy is not None:
            if not isinstance(retry_policy, BatchRetryPolicy):
                raise TypeError("retry_policy must be a BatchRetryPolicy instance")
            max_retries = retry_policy.max_retries
            batch_size = retry_policy.batch_size
            n_workers = retry_policy.n_workers

        if not isinstance(max_retries, int) or isinstance(max_retries, bool):
            raise ValueError("max_retries must be a non-negative integer")
        if max_retries < 0 or max_retries > 10:
            raise ValueError("max_retries must be between 0 and 10")
        if (policy or BatchProcessingPolicy(mode="collect")).mode == "fail_fast":
            raise ConfigurationError(
                "process_batch_retry_async requires BatchProcessingPolicy(mode='collect' or 'skip'); "
                "fail_fast aborts the batch before all failures are known."
            )

        values = list(texts)
        if not values:
            return BatchRetryReport(
                results=[],
                failed_indices=[],
                retry_report={
                    "total_inputs": 0,
                    "max_retries": max_retries,
                    "retry_attempts": 0,
                    "recovered_count": 0,
                },
            )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        retry_attempts = 0
        recovered_count = 0
        retry_report: Dict[int, Exception] = {}
        initial_successes: Dict[int, NormalizationResult] = {}
        failed: Dict[int, Exception] = {}
        try:
            initial = await self.process_batch_async(
                values,
                n_workers=n_workers,
                policy=BatchProcessingPolicy(mode="collect"),
                batch_size=batch_size,
                on_error=on_error,
                progress_callback=progress_callback,
                cancellation_token=cancellation_token,
            )
            for index, result in enumerate(initial):
                if result is not None:
                    initial_successes[index] = result
                else:
                    failed[index] = RuntimeError("Item %d produced no result during the initial async pass" % index)
        except BatchProcessingError as exc:
            if exc.results is not None:
                known_failures = set(exc.errors or {})
                cursor = 0
                for index in range(len(values)):
                    if index not in known_failures and cursor < len(exc.results):
                        initial_successes[index] = exc.results[cursor]
                        cursor += 1
            if exc.errors:
                failed = dict(exc.errors)
        except Exception as exc:  # noqa: BLE001
            return BatchRetryReport(
                results=[],
                failed_indices=list(range(len(values))),
                retry_report={
                    "total_inputs": len(values),
                    "max_retries": max_retries,
                    "retry_attempts": 0,
                    "recovered_count": 0,
                    "catastrophic_cause": type(exc).__name__,
                },
            )

        for index in sorted(failed):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            last_exc: Optional[Exception] = failed.get(index)
            for _attempt in range(max_retries):
                try:
                    initial_successes[index] = await self.process_async(values[index])
                    recovered_count += 1
                    last_exc = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    retry_attempts += 1
            if last_exc is not None:
                retry_report[index] = last_exc

        return BatchRetryReport(
            results=[initial_successes[i] for i in sorted(initial_successes)],
            failed_indices=sorted(retry_report),
            retry_report={
                "total_inputs": len(values),
                "max_retries": max_retries,
                "retry_attempts": retry_attempts,
                "recovered_count": recovered_count,
            },
        )

    # ── Introspection ─────────────────────────────────────────────────────

    def metrics_snapshot(self) -> ProcessingMetricsSnapshot:
        """Return an immutable snapshot of operational counters."""
        return self.metrics.snapshot()

    def describe(self) -> Dict[str, Any]:
        """Return a human-readable description of this pipeline's configuration.

        Example
        -------
        >>> pipeline.describe()["preset"]
        'standard'
        """
        cfg = self.config
        return {
            "preset": cast(Preset, cfg.preset).value,
            "dialect_target": cast(DialectTarget, cfg.dialect_target).value,
            "cleaning": {
                "clean_urls": cfg.clean_urls,
                "clean_emails": cfg.clean_emails,
                "clean_html": cfg.clean_html,
                "clean_mentions": cfg.clean_mentions,
                "clean_hashtags": cfg.clean_hashtags,
                "clean_emojis": cfg.clean_emojis,
                "remove_non_arabic": cfg.remove_non_arabic,
            },
            "normalization": {
                "remove_diacritics": cfg.remove_diacritics,
                "normalize_hamza": cfg.normalize_hamza,
                "normalize_alef": cfg.normalize_alef,
                "normalize_unicode": cfg.normalize_unicode,
                "normalize_tatweel": cfg.normalize_tatweel,
                "normalize_digits": cfg.normalize_digits,
                "normalize_repeated_chars": cfg.normalize_repeated_chars,
            },
            "stop_words_enabled": cfg.stop_words_config is not None,
            "supported_dialects": cfg.supported_dialects,
        }

    def to_spec(self, *, metadata: Optional[Mapping[str, Any]] = None) -> "PipelineSpec":
        """Return a validated, portable declarative specification."""
        from aranorm.core.spec import PipelineSpec

        return PipelineSpec.from_pipeline(self, metadata=metadata)

    @classmethod
    def from_spec(cls, spec: Any) -> "ArabicNormalizationPipeline":
        """Reconstruct a pipeline from a validated PipelineSpec or mapping."""
        from aranorm.core.spec import PipelineSpec

        validated = spec if isinstance(spec, PipelineSpec) else PipelineSpec.from_dict(spec)
        config = PipelineConfig.from_dict(validated.config)
        pipeline = cls(config)
        if pipeline.configuration_fingerprint() != validated.config_fingerprint:
            raise ValueError("PipelineSpec fingerprint does not match reconstructed pipeline")
        return pipeline

    def configuration_fingerprint(self) -> str:
        """Return a deterministic SHA-256 fingerprint of the pipeline config.

        The canonical payload contains configuration only. Input text, output
        text, and optional dependency state are intentionally excluded.
        """
        payload = json.dumps(
            self.config.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def describe_operational(self) -> Dict[str, Any]:
        """Return a versioned, machine-friendly operational description."""
        return {
            "schema_version": 1,
            "pipeline_class": self.__class__.__name__,
            "config_fingerprint": self.configuration_fingerprint(),
            "config": self.describe(),
        }


class PipelineBuilder:
    """Builder for constructing a custom pipeline step-by-step.

    Example
    -------
    >>> pipeline = (
    ...     ArabicNormalizationPipeline.builder()
    ...     .add_cleaner(urls=True, html=True)
    ...     .add_normalizer(remove_diacritics=True)
    ...     .add_dialect_processor(normalize_to="msa")
    ...     .build()
    ... )
    """

    def __init__(self) -> None:
        self._config = PipelineConfig(
            preset="light",
            clean_urls=False,
            clean_emails=False,
            clean_html=False,
        )

    def _resolve_boolean_options(self, options: Dict[str, bool], operation: str) -> Dict[str, bool]:
        """Resolve and validate boolean builder options before mutating config."""
        resolved: Dict[str, bool] = {}
        for name, value in options.items():
            if not isinstance(value, bool):
                raise TypeError(f"{operation} option {name!r} must be boolean")
            field_name = name
            if operation == "cleaner":
                if name in {"remove_non_arabic", "remove_english"}:
                    field_name = name
                elif name.startswith("remove_"):
                    field_name = f"clean_{name.removeprefix('remove_')}"
                elif not name.startswith("clean_"):
                    field_name = f"clean_{name}"
            elif name == "normalize_diacritics":
                field_name = "remove_diacritics"

            if not hasattr(self._config, field_name):
                raise ValueError(f"Unknown {operation} option: {name}")
            if not isinstance(getattr(self._config, field_name), bool):
                raise TypeError(f"{operation} option {name!r} must target a boolean field")
            resolved[field_name] = value
        return resolved

    def add_cleaner(self, **options: bool) -> "PipelineBuilder":
        """Configure content cleaning options.

        Unknown options and non-boolean values are rejected before the builder
        is mutated, so a typo cannot silently create a partial configuration.
        """
        for field_name, value in self._resolve_boolean_options(options, "cleaner").items():
            setattr(self._config, field_name, value)
        return self

    def add_normalizer(self, **options: bool) -> "PipelineBuilder":
        """Configure orthographic normalization options with strict validation."""
        for field_name, value in self._resolve_boolean_options(options, "normalizer").items():
            setattr(self._config, field_name, value)
        return self

    def add_dialect_processor(
        self,
        identify: bool = True,
        normalize_to: str = "none",
        supported_dialects: Optional[Sequence[str]] = None,
    ) -> "PipelineBuilder":
        """Configure dialect output and supported labels."""
        from aranorm.core.config import DialectTarget

        self._config.dialect_target = DialectTarget(normalize_to)
        self._config.supported_dialects = list(supported_dialects or [])
        return self

    def add_stop_words(
        self,
        mode: str = "remove",
        scope: str = "universal",
        **kwargs: Any,
    ) -> "PipelineBuilder":
        """Enable stop-word processing.

        Parameters
        ----------
        mode:
            One of ``"remove"``, ``"extract"``, ``"highlight"``, ``"count"``.
        scope:
            One of ``"universal"``, ``"msa_only"``, ``"dialect_aware"``, ``"custom"``.
        **kwargs:
            Passed directly to :class:`~aranorm.core.stop_words_config.StopWordsConfig`.
        """
        from aranorm.core.stop_words_config import StopWordsConfig

        self._config.stop_words_config = StopWordsConfig(mode=mode, scope=scope, **kwargs)
        return self

    def build(self) -> ArabicNormalizationPipeline:
        """Build and return the configured pipeline."""
        return ArabicNormalizationPipeline(config=self._config)
