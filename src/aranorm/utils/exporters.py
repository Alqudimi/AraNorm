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
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Literal, Optional, Sequence, TextIO, cast

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
        elif isinstance(value, list) and field != "steps_trace":
            value = "|".join(str(v) for v in value)
        row[field] = value
    return row


CsvQuoting = Literal[0, 1, 2, 3]


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
        quoting: CsvQuoting = cast(CsvQuoting, csv.QUOTE_MINIMAL),
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
        quoting: CsvQuoting = cast(CsvQuoting, csv.QUOTE_MINIMAL),
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
                fh.write(json.dumps(result.to_dict(), ensure_ascii=ensure_ascii) + "\n")

    def to_jsonl_string(self, ensure_ascii: bool = False) -> str:
        """Return results as a JSONL string.

        Parameters
        ----------
        ensure_ascii:
            Preserve Arabic characters when *False* (default).
        """
        lines = [json.dumps(r.to_dict(), ensure_ascii=ensure_ascii) for r in self.results]
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
            raise ImportError("pandas is required for to_dataframe(). Run: pip install pandas") from exc

        rows = [_result_to_row(r, self.fields) for r in self.results]
        return pd.DataFrame(rows, columns=self.fields)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _to_json_data(self) -> List[Dict[str, Any]]:
        return [_result_to_row(r, self.fields) for r in self.results]

    def __len__(self) -> int:
        return len(self.results)

    def __repr__(self) -> str:
        return f"BatchExporter(results={len(self.results)}, fields={self.fields})"


@contextmanager
def _open_output(target: Any, encoding: str, newline: str = "") -> Iterator[TextIO]:
    """Yield a writable text stream and close it only when opened here."""
    if hasattr(target, "write"):
        yield cast(TextIO, target)
        return

    with open(target, "w", encoding=encoding, newline=newline) as stream:
        yield stream


class StreamingBatchExporter:
    """Write normalization results incrementally without materializing a batch.

    This exporter is designed for generators and large JSONL/text files. It accepts
    either a filesystem path or an already-open text stream and returns the number
    of rows written. JSON output is emitted as a valid array incrementally, while
    JSONL and CSV are written record-by-record.
    """

    def __init__(self, fields: Optional[List[str]] = None) -> None:
        self.fields = fields or list(_DEFAULT_FIELDS)

    def write_jsonl(
        self,
        results: Iterable["NormalizationResult"],
        target: Any,
        ensure_ascii: bool = False,
    ) -> int:
        """Write one JSON object per line and return the number of rows."""
        count = 0
        with _open_output(target, encoding="utf-8") as stream:
            for result in results:
                stream.write(json.dumps(result.to_dict(), ensure_ascii=ensure_ascii) + "\n")
                count += 1
        return count

    def write_csv(
        self,
        results: Iterable["NormalizationResult"],
        target: Any,
        encoding: str = "utf-8-sig",
        delimiter: str = ",",
        quoting: CsvQuoting = cast(CsvQuoting, csv.QUOTE_MINIMAL),
    ) -> int:
        """Write CSV rows incrementally and return the number of data rows."""
        count = 0
        with _open_output(target, encoding=encoding, newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=self.fields,
                delimiter=delimiter,
                quoting=quoting,
            )
            writer.writeheader()
            for result in results:
                writer.writerow(_result_to_row(result, self.fields))
                count += 1
        return count

    def write_json(
        self,
        results: Iterable["NormalizationResult"],
        target: Any,
        ensure_ascii: bool = False,
        indent: Optional[int] = None,
    ) -> int:
        """Write a valid JSON array incrementally and return the row count."""
        count = 0
        with _open_output(target, encoding="utf-8") as stream:
            stream.write("[\n" if indent is not None else "[")
            for result in results:
                if count:
                    stream.write(",\n" if indent is not None else ",")
                payload = _result_to_row(result, self.fields)
                stream.write(json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent))
                count += 1
            stream.write("\n]" if indent is not None else "]")
        return count

    def write(
        self,
        results: Iterable["NormalizationResult"],
        target: Any,
        format: Literal["csv", "json", "jsonl"] = "jsonl",
        ensure_ascii: bool = False,
    ) -> int:
        """Write using the requested format and return the number of rows."""
        if format == "csv":
            return self.write_csv(results, target)
        if format == "json":
            return self.write_json(results, target, ensure_ascii=ensure_ascii, indent=2)
        if format == "jsonl":
            return self.write_jsonl(results, target, ensure_ascii=ensure_ascii)
        raise ValueError("format must be one of: csv, json, jsonl")

    def __repr__(self) -> str:
        return f"StreamingBatchExporter(fields={self.fields})"


def export_jsonl(
    results: Iterable["NormalizationResult"],
    target: Any,
    fields: Optional[List[str]] = None,
    ensure_ascii: bool = False,
) -> int:
    """Export *results* as a JSON Lines file with a given field subset.

    This module-level convenience wrapper combines the streaming exporter
    with a field projection: each output line contains only the requested
    fields in insertion order, which keeps payloads compact when the full
    result dictionary is not needed.

    Parameters
    ----------
    results:
        Iterable of :class:`NormalizationResult` objects (e.g. from
        ``pipeline.process_batch``).
    target:
        Destination filesystem path or any object exposing a ``write``
        method.
    fields:
        Subset of fields to emit per line. When *None*, a sensible default
        set is used (see :data:`_DEFAULT_FIELDS`).
    ensure_ascii:
        Preserve Arabic characters when *False* (default).

    Returns
    -------
    int
        Number of JSON lines written.

    Example
    -------
    >>> exporter = export_jsonl(results, "out.jsonl", fields=["original_text", "normalized_text", "dialect"])
    >>> exporter >= 1
    True
    """
    exporter = StreamingBatchExporter(fields=fields)
    rows = ({key: row[key] for key in exporter.fields} for row in (_result_to_row(r, exporter.fields) for r in results))
    count = 0
    with _open_output(target, encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=ensure_ascii) + "\n")
            count += 1
    return count
