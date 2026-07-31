"""Public Arabic normalization pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from aranorm.core.base import ProcessorContext
from aranorm.core.config import DialectTarget, PipelineConfig
from aranorm.exceptions import InvalidTextError
from aranorm.stages.cleaner import ContentCleaner
from aranorm.stages.dialect_id import DialectIdentifier
from aranorm.stages.dialect_norm import DialectNormalizer
from aranorm.stages.normalizer import OrthographicNormalizer
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
        return (
            f"NormalizationResult("
            f"normalized={self.normalized_text[:40]!r}"
            f"{dialect_str}"
            f"{time_str})"
        )

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
            "dialect": self.dialect,
            "dialect_confidence": self.dialect_confidence,
            "coda_text": self.coda_text,
            "msa_text": self.msa_text,
            "applied_steps": self.applied_steps,
            "processing_time_ms": self.processing_time_ms,
            "stop_words_removed": self.stop_words_removed,
            "stop_words_found": sorted(self.stop_words_found) if self.stop_words_found else None,
            "stop_words_stats": self.stop_words_stats,
            "stop_words_by_category": self.stop_words_by_category,
            "stop_words_by_dialect": self.stop_words_by_dialect,
            "applied_stop_words_steps": self.applied_stop_words_steps,
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
            applied_steps=data.get("applied_steps", []),
            processing_time_ms=data.get("processing_time_ms"),
            stop_words_removed=data.get("stop_words_removed"),
            stop_words_found=set(found) if found is not None else None,
            stop_words_stats=data.get("stop_words_stats"),
            stop_words_by_category=data.get("stop_words_by_category"),
            stop_words_by_dialect=data.get("stop_words_by_dialect"),
            applied_stop_words_steps=data.get("applied_stop_words_steps"),
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
            "original_text", "normalized_text", "dialect",
            "dialect_confidence", "stop_words_removed", "stop_words_found",
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
    ) -> None:
        self.config = config or PipelineConfig()
        self.cleaner = cleaner or ContentCleaner(self.config)
        self.normalizer = normalizer or OrthographicNormalizer(self.config)
        self.dialect_identifier = dialect_identifier or DialectIdentifier(
            self.config.supported_dialects
        )
        self.dialect_normalizer = (
            DialectNormalizer(self.config.dialect_target.value)
            if self.config.dialect_target != DialectTarget.NONE
            else None
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
        config = PipelineConfig(**data)
        return cls(config=config)

    # ── Single-text processing ─────────────────────────────────────────────

    def process(self, text: str) -> NormalizationResult:
        """Process one text and return normalized text plus metadata.

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
        original_text = validate_text(text)
        context = ProcessorContext()
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
        if self.config.stop_words_config is not None:
            from aranorm.stages.stop_words_stage import StopWordsStage

            sw_stage = StopWordsStage(config=self.config.stop_words_config)
            sw_stage.execute(normalized, context)
            sw_result = context.metadata.get("stop_words_result")
            if sw_result is not None:
                result.stop_words_removed = sw_result.stop_words_removed
                result.stop_words_found = sw_result.stop_words_found
                result.stop_words_stats = sw_result.stop_words_stats
                result.stop_words_by_category = sw_result.stop_words_by_category
                result.stop_words_by_dialect = sw_result.stop_words_by_dialect
                result.applied_stop_words_steps = sw_result.applied_stop_words_steps
            result.applied_steps = context.applied_steps
        result.processing_time_ms = round((time.perf_counter() - t_start) * 1000, 3)
        return result

    # ── Batch processing ───────────────────────────────────────────────────

    def process_batch(
        self,
        texts: Sequence[str],
        batch_size: int = 32,
        n_workers: int = 1,
        on_error: Optional[Callable[[int, str, Exception], Optional[str]]] = None,
        progress_callback: Optional[Any] = None,
    ) -> List[NormalizationResult]:
        """Process texts sequentially or concurrently while preserving order.

        Parameters
        ----------
        texts:
            Sequence of input strings.
        batch_size:
            Number of texts per worker chunk (currently informational; all
            texts are dispatched at once for simplicity).
        n_workers:
            Number of threads to use (``1`` = sequential, safe default).
        on_error:
            Optional callback ``(index, text, exc) -> replacement_text | None``.
            When provided and a text fails, the callback receives the failure
            information and may return a fallback string; if it returns *None*
            the item is skipped in the output.
        progress_callback:
            Optional :class:`~aranorm.utils.progress.ProgressCallback` instance
            for real-time progress reporting.

        Returns
        -------
        List[NormalizationResult]
            Results in the same order as *texts*.
        """
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if n_workers < 1:
            raise ValueError("n_workers must be positive")
        values = list(texts)
        if not values:
            return []

        if progress_callback is not None:
            progress_callback.on_start(len(values))

        if on_error is not None:
            results = self._process_batch_safe(values, on_error, progress_callback)
        elif n_workers == 1 or len(values) <= 1:
            results = []
            for idx, text in enumerate(values):
                r = self.process(text)
                results.append(r)
                if progress_callback is not None:
                    progress_callback.on_item(idx, text, True)
        else:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = list(executor.map(self.process, values))
            results = list(futures)
            if progress_callback is not None:
                for idx, (text, r) in enumerate(zip(values, results)):
                    progress_callback.on_item(idx, text, True)

        if progress_callback is not None:
            progress_callback.on_finish()

        return results

    def _process_batch_safe(
        self,
        texts: List[str],
        on_error: Callable[[int, str, Exception], Optional[str]],
        progress_callback: Optional[Any] = None,
    ) -> List[NormalizationResult]:
        """Process with per-item error handling and optional progress reporting."""
        results: List[NormalizationResult] = []
        for idx, text in enumerate(texts):
            success = True
            try:
                results.append(self.process(text))
            except Exception as exc:  # noqa: BLE001
                success = False
                LOGGER.warning("Processing failed for item %d: %s", idx, exc)
                fallback = on_error(idx, text, exc)
                if fallback is not None:
                    try:
                        results.append(self.process(fallback))
                        success = True
                    except Exception as inner_exc:  # noqa: BLE001
                        LOGGER.warning(
                            "Fallback processing also failed for item %d: %s",
                            idx,
                            inner_exc,
                        )
            if progress_callback is not None:
                progress_callback.on_item(idx, text, success)
        return results

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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process, text)

    async def process_batch_async(
        self,
        texts: Sequence[str],
        n_workers: int = 4,
    ) -> List[NormalizationResult]:
        """Async batch processing using a thread-pool executor.

        Parameters
        ----------
        texts:
            Sequence of Arabic strings.
        n_workers:
            Thread-pool size.
        """
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=n_workers)
        try:
            tasks = [loop.run_in_executor(executor, self.process, t) for t in texts]
            return list(await asyncio.gather(*tasks))
        finally:
            executor.shutdown(wait=False)

    # ── Introspection ─────────────────────────────────────────────────────

    def describe(self) -> Dict[str, Any]:
        """Return a human-readable description of this pipeline's configuration.

        Example
        -------
        >>> pipeline.describe()["preset"]
        'standard'
        """
        cfg = self.config
        return {
            "preset": cfg.preset.value,
            "dialect_target": cfg.dialect_target.value,
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

    def add_cleaner(self, **options: bool) -> "PipelineBuilder":
        """Configure content cleaning options."""
        for name, value in options.items():
            field_name = name
            if name.startswith("remove_"):
                field_name = f"clean_{name.removeprefix('remove_')}"
            elif not name.startswith("clean_"):
                field_name = f"clean_{name}"
            if hasattr(self._config, field_name):
                setattr(self._config, field_name, value)
        return self

    def add_normalizer(self, **options: bool) -> "PipelineBuilder":
        """Configure orthographic normalization options."""
        for name, value in options.items():
            field_name = name
            if name == "normalize_diacritics":
                field_name = "remove_diacritics"
            if hasattr(self._config, field_name):
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
