"""HuggingFace Datasets integration for AraNorm.

Provides :class:`HuggingFaceNormalizer` which maps an
:class:`~aranorm.core.pipeline.ArabicNormalizationPipeline` over a
HuggingFace ``Dataset`` or ``DatasetDict`` using ``dataset.map()``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from aranorm.core.config import PipelineConfig
from aranorm.exceptions import IntegrationUnavailableError


class HuggingFaceNormalizer:
    """Normalize Arabic text columns in a HuggingFace Dataset.

    Parameters
    ----------
    pipeline:
        Pre-configured normalization pipeline. A default ``standard``
        pipeline is used when omitted.
    batch_size:
        Number of examples processed per ``dataset.map`` batch.
    num_proc:
        Passed directly to ``dataset.map(num_proc=...)``.  Use ``None``
        for single-process (default).

    Example
    -------
    >>> from datasets import load_dataset
    >>> from aranorm.integrations import HuggingFaceNormalizer
    >>>
    >>> ds = load_dataset("twitter_ar_sarcasm_detection", split="train")
    >>> norm = HuggingFaceNormalizer()
    >>> ds_normalized = norm.normalize_dataset(ds, text_column="text")
    """

    def __init__(
        self,
        pipeline: Optional[Any] = None,
        batch_size: int = 512,
        num_proc: Optional[int] = None,
    ) -> None:
        self._ensure_datasets()
        if pipeline is None:
            from aranorm.core.pipeline import ArabicNormalizationPipeline

            pipeline = ArabicNormalizationPipeline(PipelineConfig())
        self.pipeline = pipeline
        self.batch_size = batch_size
        self.num_proc = num_proc

    # ── Public API ────────────────────────────────────────────────────────

    def normalize_dataset(
        self,
        dataset: Any,
        text_column: str = "text",
        output_column: Optional[str] = None,
        remove_original: bool = False,
    ) -> Any:
        """Apply normalization to *text_column* in *dataset*.

        Works with both ``Dataset`` and ``DatasetDict``.

        Parameters
        ----------
        dataset:
            A HuggingFace ``datasets.Dataset`` or ``DatasetDict``.
        text_column:
            Name of the column to normalize.
        output_column:
            Target column name. Defaults to ``f"{text_column}_normalized"``.
        remove_original:
            When *True*, drop the original *text_column* after normalization.
        """
        try:
            from datasets import DatasetDict  # type: ignore
        except ImportError as exc:
            raise IntegrationUnavailableError(
                "HuggingFace `datasets` is not installed. " "Run: pip install datasets"
            ) from exc

        out_col = output_column or f"{text_column}_normalized"

        if isinstance(dataset, DatasetDict):
            return dataset.map(
                self._make_map_fn(text_column, out_col),
                batched=True,
                batch_size=self.batch_size,
                num_proc=self.num_proc,
                remove_columns=[text_column] if remove_original else None,
                desc=f"Normalizing {text_column}",
            )
        return dataset.map(
            self._make_map_fn(text_column, out_col),
            batched=True,
            batch_size=self.batch_size,
            num_proc=self.num_proc,
            remove_columns=[text_column] if remove_original else None,
            desc=f"Normalizing {text_column}",
        )

    def expand_dataset(
        self,
        dataset: Any,
        text_column: str = "text",
        fields: Optional[List[str]] = None,
    ) -> Any:
        """Add one column per requested NormalizationResult field.

        Parameters
        ----------
        dataset:
            A HuggingFace ``Dataset``.
        text_column:
            Column containing Arabic text.
        fields:
            Result fields to expand. Defaults to
            ``["normalized_text", "dialect", "dialect_confidence"]``.
        """
        _default_fields = ["normalized_text", "dialect", "dialect_confidence"]
        selected = fields or _default_fields

        def _expand_fn(batch: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
            texts = batch[text_column]
            results = self.pipeline.process_batch(texts)
            output: Dict[str, List[Any]] = {f: [] for f in selected}
            for r in results:
                for f in selected:
                    output[f].append(getattr(r, f, None))
            return output

        return dataset.map(
            _expand_fn,
            batched=True,
            batch_size=self.batch_size,
            num_proc=self.num_proc,
            desc=f"Expanding {text_column}",
        )

    # ── Private ───────────────────────────────────────────────────────────

    def _make_map_fn(self, text_column: str, out_col: str) -> Callable[[Dict[str, List[Any]]], Dict[str, List[Any]]]:
        """Return a batched map function for the given columns."""
        pipeline = self.pipeline

        def _fn(batch: Dict[str, List[Any]]) -> Dict[str, List[Any]]:
            texts = [str(t) if t is not None else "" for t in batch[text_column]]
            results = pipeline.process_batch(texts)
            return {out_col: [r.normalized_text for r in results]}

        return _fn

    @staticmethod
    def _ensure_datasets() -> None:
        try:
            import datasets  # type: ignore  # noqa: F401
        except ImportError as exc:
            raise IntegrationUnavailableError(
                "HuggingFace `datasets` is not installed. " "Run: pip install datasets"
            ) from exc
