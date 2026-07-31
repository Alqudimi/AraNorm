"""Progress callback utilities for batch processing.

Provides :class:`ProgressCallback` and :class:`TqdmProgressCallback` (when
``tqdm`` is installed) that can be passed to batch processing methods to
report real-time progress.

Example
-------
>>> from aranorm import ArabicNormalizationPipeline, PipelineConfig
>>> from aranorm.utils.progress import ConsoleProgressCallback
>>>
>>> pipeline = ArabicNormalizationPipeline(PipelineConfig())
>>> callback = ConsoleProgressCallback(total=1000)
>>> results = pipeline.process_batch(texts, progress_callback=callback)
Processing:  43%|████████░░░░░░░░│  430/1000
"""

from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Optional


class ProgressCallback(ABC):
    """Abstract base class for progress tracking during batch processing.

    Implement :meth:`on_start`, :meth:`on_item`, and :meth:`on_finish` to
    integrate with any progress-reporting system.
    """

    @abstractmethod
    def on_start(self, total: int) -> None:
        """Called once before processing begins.

        Parameters
        ----------
        total:
            Total number of items to process.
        """

    @abstractmethod
    def on_item(self, index: int, text: str, success: bool) -> None:
        """Called after each item is processed.

        Parameters
        ----------
        index:
            Zero-based index of the item just processed.
        text:
            The input text that was processed.
        success:
            *False* when the item raised an exception.
        """

    @abstractmethod
    def on_finish(self) -> None:
        """Called once after all items have been processed."""


class NoOpProgressCallback(ProgressCallback):
    """Silent no-op callback — use as a safe default."""

    def on_start(self, total: int) -> None:
        pass

    def on_item(self, index: int, text: str, success: bool) -> None:
        pass

    def on_finish(self) -> None:
        pass


class ConsoleProgressCallback(ProgressCallback):
    """Print a simple ASCII progress bar to *sys.stderr*.

    Parameters
    ----------
    total:
        Total number of items (required for the progress bar).
    width:
        Width of the bar in characters (default 40).
    prefix:
        Text printed before the bar (default ``"Processing"``).
    file:
        Output stream (default ``sys.stderr``).

    Example
    -------
    >>> callback = ConsoleProgressCallback(total=500)
    >>> pipeline.process_batch(texts, progress_callback=callback)
    Processing: 100%|████████████████████████████████████████| 500/500 [00:02]
    """

    def __init__(
        self,
        total: int = 0,
        width: int = 40,
        prefix: str = "Processing",
        file: Any = None,
    ) -> None:
        self.total = total
        self.width = width
        self.prefix = prefix
        self._file = file or sys.stderr
        self._done = 0
        self._errors = 0
        self._start_time: Optional[float] = None

    def on_start(self, total: int) -> None:
        self.total = total
        self._done = 0
        self._errors = 0
        self._start_time = time.perf_counter()
        self._render()

    def on_item(self, index: int, text: str, success: bool) -> None:
        self._done += 1
        if not success:
            self._errors += 1
        self._render()

    def on_finish(self) -> None:
        elapsed = time.perf_counter() - (self._start_time or time.perf_counter())
        rate = self._done / elapsed if elapsed > 0 else 0
        self._file.write(
            f"\r{self.prefix}: 100%|{'█' * self.width}| "
            f"{self._done}/{self.total} "
            f"[{elapsed:.1f}s, {rate:.0f} items/s]"
            f"{' (errors: ' + str(self._errors) + ')' if self._errors else ''}\n"
        )
        self._file.flush()

    def _render(self) -> None:
        if self.total == 0:
            pct = 0.0
            filled = 0
        else:
            pct = self._done / self.total
            filled = int(self.width * pct)

        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = time.perf_counter() - (self._start_time or time.perf_counter())
        self._file.write(
            f"\r{self.prefix}: {pct:4.0%}|{bar}| {self._done}/{self.total} "
            f"[{elapsed:.1f}s]"
        )
        self._file.flush()


class TqdmProgressCallback(ProgressCallback):
    """Progress callback backed by ``tqdm`` (must be installed separately).

    Parameters
    ----------
    **tqdm_kwargs:
        Forwarded directly to :class:`tqdm.tqdm`.

    Example
    -------
    >>> cb = TqdmProgressCallback(desc="Normalizing", colour="green")
    >>> pipeline.process_batch(texts, progress_callback=cb)
    """

    def __init__(self, **tqdm_kwargs: Any) -> None:
        try:
            from tqdm import tqdm  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "tqdm is required for TqdmProgressCallback. Run: pip install tqdm"
            ) from exc
        self._tqdm_cls = tqdm
        self._tqdm_kwargs = tqdm_kwargs
        self._bar: Any = None

    def on_start(self, total: int) -> None:
        self._bar = self._tqdm_cls(total=total, **self._tqdm_kwargs)

    def on_item(self, index: int, text: str, success: bool) -> None:
        if self._bar is not None:
            self._bar.update(1)

    def on_finish(self) -> None:
        if self._bar is not None:
            self._bar.close()
            self._bar = None
