"""pandas DataFrame integration for AraNorm.

Provides :class:`PandasNormalizer` which applies an
:class:`~aranorm.core.pipeline.ArabicNormalizationPipeline` to an entire
DataFrame column, returning either a new column of normalized strings or a
DataFrame of full :class:`~aranorm.core.pipeline.NormalizationResult` fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from aranorm.core.config import PipelineConfig
from aranorm.exceptions import IntegrationUnavailableError

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd

    from aranorm.core.pipeline import ArabicNormalizationPipeline, NormalizationResult


class PandasNormalizer:
    """Apply AraNorm normalization to a pandas Series or DataFrame column.

    Parameters
    ----------
    pipeline:
        A pre-configured :class:`~aranorm.core.pipeline.ArabicNormalizationPipeline`.
        When *None*, a default ``standard`` pipeline is created.
    n_workers:
        Number of parallel workers passed to
        :meth:`~aranorm.core.pipeline.ArabicNormalizationPipeline.process_batch`.
        Set to ``1`` (default) for deterministic, single-threaded processing.

    Example
    -------
    >>> import pandas as pd
    >>> from aranorm import ArabicNormalizationPipeline, PipelineConfig
    >>> from aranorm.integrations import PandasNormalizer
    >>>
    >>> df = pd.DataFrame({"text": ["أنا أحب العربية", "شلونك؟"]})
    >>> norm = PandasNormalizer()
    >>> df["normalized"] = norm.normalize_column(df["text"])
    """

    def __init__(
        self,
        pipeline: Optional["ArabicNormalizationPipeline"] = None,
        n_workers: int = 1,
    ) -> None:
        self._ensure_pandas()
        if pipeline is None:
            from aranorm.core.pipeline import ArabicNormalizationPipeline
            pipeline = ArabicNormalizationPipeline(PipelineConfig())
        self.pipeline = pipeline
        self.n_workers = n_workers

    # ── Public API ────────────────────────────────────────────────────────

    def normalize_column(self, series: "pd.Series") -> "pd.Series":
        """Return a new Series of normalized text strings.

        Parameters
        ----------
        series:
            A pandas Series of Arabic strings.
        """
        import pandas as pd

        texts = series.fillna("").tolist()
        results = self.pipeline.process_batch(texts, n_workers=self.n_workers)
        return pd.Series(
            [r.normalized_text for r in results],
            index=series.index,
            name=series.name,
        )

    def normalize_dataframe(
        self,
        df: "pd.DataFrame",
        column: str,
        output_column: Optional[str] = None,
    ) -> "pd.DataFrame":
        """Normalize *column* in *df* and store the result in *output_column*.

        Parameters
        ----------
        df:
            Source DataFrame.
        column:
            Name of the column containing Arabic text.
        output_column:
            Name of the column to write results to. Defaults to
            ``f"{column}_normalized"``.
        """
        out_col = output_column or f"{column}_normalized"
        df = df.copy()
        df[out_col] = self.normalize_column(df[column])
        return df

    def expand_results(
        self,
        series: "pd.Series",
        fields: Optional[List[str]] = None,
    ) -> "pd.DataFrame":
        """Return a DataFrame with one column per :class:`NormalizationResult` field.

        Parameters
        ----------
        series:
            A pandas Series of Arabic strings.
        fields:
            Subset of result fields to include.  When *None*, returns
            ``normalized_text``, ``dialect``, ``dialect_confidence``,
            ``applied_steps``.
        """
        import pandas as pd

        _default_fields = [
            "normalized_text",
            "dialect",
            "dialect_confidence",
            "applied_steps",
        ]
        selected = fields or _default_fields

        texts = series.fillna("").tolist()
        results = self.pipeline.process_batch(texts, n_workers=self.n_workers)
        rows: List[Dict[str, Any]] = []
        for r in results:
            row: Dict[str, Any] = {}
            for f in selected:
                row[f] = getattr(r, f, None)
            rows.append(row)
        return pd.DataFrame(rows, index=series.index)

    def apply_stop_words(
        self,
        series: "pd.Series",
        stop_words_field: str = "stop_words_removed",
    ) -> "pd.Series":
        """Return a Series of texts with stop words removed.

        Requires ``pipeline.config.stop_words_config`` to be set.

        Parameters
        ----------
        series:
            A pandas Series of Arabic strings.
        stop_words_field:
            Which stop-words result field to use. One of:
            ``"stop_words_removed"``, ``"processed_text"``.
        """
        import pandas as pd

        texts = series.fillna("").tolist()
        results = self.pipeline.process_batch(texts, n_workers=self.n_workers)
        values = [getattr(r, stop_words_field, r.normalized_text) or "" for r in results]
        return pd.Series(values, index=series.index, name=series.name)

    # ── Private ───────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_pandas() -> None:
        """Raise a clear error when pandas is not installed."""
        try:
            import pandas  # noqa: F401
        except ImportError as exc:
            raise IntegrationUnavailableError(
                "pandas is not installed. Run: pip install pandas"
            ) from exc
