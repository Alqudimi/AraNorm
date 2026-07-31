"""Export utilities for :class:`~aranorm.core.pipeline.NormalizationResult` objects.

Supports writing single results or batches to **CSV**, **JSON**, and **JSONL**
(JSON Lines) formats.

Example
-------
>>> from aranorm import ArabicNormalizationPipeline, PipelineConfig
>>> from aranorm.utils.exporters import BatchExporter
>>>
>>> pipeline = ArabicNormalizationPipeline(PipelineConfig())
>>> results = pipeline.process_batch(["شلونك؟", "أنا سعيد جداً"])
>>>
>>> exporter = BatchExporter(results)
>>> exporter.to_csv("output.csv")
>>> exporter.to_jsonl("output.jsonl")
>>> json_str = exporter.to_json_string()
"""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

if TYPE_CHECKING:
    from aranorm.core.pipeline import NormalizationResult

# Default fields exported in CSV / JSON
_DEFAULT_FIELDS = [
    "original_text",
    "normalized_text",
    "dialect",
    "dialect_confidence",
    "applied_steps",
    "stop_words_removed",
    "stop_words_found",
]


def _result_to_row(
    result: "NormalizationResult",
    fields: List[str],
) -> Dict[str, Any]:
    """Convert one result to a flat dictionary for export."""
    row: Dict[str, Any] = {}
    for field in fields:
        value = getattr(result, field, None)
        if isinstance(value, (set, frozenset)):
            value = "|".join(sorted(value)) if value else ""
        elif isinstance(value, list):
            value = "|".join(str(v) for v in value)
        row[field] = value
    return row


class BatchExporter:
    """Export a collection of :class:`NormalizationResult` objects.

    Parameters
    ----------
    results:
        Sequence of results to export (e.g. from ``pipeline.process_batch``).
    fields:
        Columns / fields to include. When *None*, a sensible default set is
        used (see :data:`_DEFAULT_FIELDS`).

    Example
    -------
    >>> exporter = BatchExporter(results, fields=["original_text", "normalized_text", "dialect"])
    >>> exporter.to_csv("out.csv")
    """

    def __init__(
        self,
        results: Sequence["NormalizationResult"],
        fields: Optional[List[str]] = None,
    ) -> None:
        self.results = list(results)
        self.fields = fields or list(_DEFAULT_FIELDS)

    # ── CSV ───────────────────────────────────────────────────────────────

    def to_csv(
        self,
        path: str,
        encoding: str = "utf-8-sig",
        delimiter: str = ",",
        quoting: int = csv.QUOTE_MINIMAL,
    ) -> None:
        """Write results to a CSV file.

        Parameters
        ----------
        path:
            Destination file path.
        encoding:
            File encoding (default ``"utf-8-sig"`` — includes BOM so Excel
            opens the file with correct Arabic rendering).
        delimiter:
            Column delimiter (default ``","``).
        quoting:
            ``csv.QUOTE_*`` constant.
        """
        with open(path, "w", encoding=encoding, newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=self.fields,
                delimiter=delimiter,
                quoting=quoting,
            )
            writer.writeheader()
            for result in self.results:
                writer.writerow(_result_to_row(result, self.fields))

    def to_csv_string(
        self,
        delimiter: str = ",",
        quoting: int = csv.QUOTE_MINIMAL,
    ) -> str:
        """Return CSV output as a string (useful for in-memory processing).

        Parameters
        ----------
        delimiter:
            Column delimiter.
        quoting:
            ``csv.QUOTE_*`` constant.
        """
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=self.fields,
            delimiter=delimiter,
            quoting=quoting,
        )
        writer.writeheader()
        for result in self.results:
            writer.writerow(_result_to_row(result, self.fields))
        return buf.getvalue()

    # ── JSON ──────────────────────────────────────────────────────────────

    def to_json(
        self,
        path: str,
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> None:
        """Write results to a pretty-printed JSON file.

        Parameters
        ----------
        path:
            Destination file path.
        indent:
            JSON indentation level.
        ensure_ascii:
            When *False* (default), Arabic characters are preserved as-is.
        """
        data = self._to_json_data()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=indent, ensure_ascii=ensure_ascii)

    def to_json_string(
        self,
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> str:
        """Return results as a JSON string.

        Parameters
        ----------
        indent:
            JSON indentation level.
        ensure_ascii:
            Preserve Arabic characters when *False* (default).
        """
        return json.dumps(
            self._to_json_data(),
            indent=indent,
            ensure_ascii=ensure_ascii,
        )

    # ── JSONL (JSON Lines) ────────────────────────────────────────────────

    def to_jsonl(
        self,
        path: str,
        ensure_ascii: bool = False,
    ) -> None:
        """Write results to a JSON Lines file (one JSON object per line).

        JSON Lines is the preferred format for large datasets because it can
        be streamed line-by-line without loading the entire file into memory.

        Parameters
        ----------
        path:
            Destination file path.
        ensure_ascii:
            Preserve Arabic characters when *False* (default).
        """
        with open(path, "w", encoding="utf-8") as fh:
            for result in self.results:
                fh.write(
                    json.dumps(
                        result.to_dict(), ensure_ascii=ensure_ascii
                    ) + "\n"
                )

    def to_jsonl_string(self, ensure_ascii: bool = False) -> str:
        """Return results as a JSONL string.

        Parameters
        ----------
        ensure_ascii:
            Preserve Arabic characters when *False* (default).
        """
        lines = [
            json.dumps(r.to_dict(), ensure_ascii=ensure_ascii)
            for r in self.results
        ]
        return "\n".join(lines) + ("\n" if lines else "")

    # ── Pandas (optional) ─────────────────────────────────────────────────

    def to_dataframe(self) -> Any:
        """Return a ``pandas.DataFrame`` of results.

        Raises
        ------
        ImportError
            If pandas is not installed.
        """
        try:
            import pandas as pd  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "pandas is required for to_dataframe(). Run: pip install pandas"
            ) from exc

        rows = [_result_to_row(r, self.fields) for r in self.results]
        return pd.DataFrame(rows, columns=self.fields)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _to_json_data(self) -> List[Dict[str, Any]]:
        return [_result_to_row(r, self.fields) for r in self.results]

    def __len__(self) -> int:
        return len(self.results)

    def __repr__(self) -> str:
        return f"BatchExporter(results={len(self.results)}, fields={self.fields})"
