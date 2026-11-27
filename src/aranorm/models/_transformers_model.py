"""Shared lazy Transformers Seq2Seq model wrapper.

Provides :class:`TransformersSeq2SeqModel`, a lazy-loading wrapper that
defers model and tokenizer downloads until the first :meth:`predict` call.

Batch prediction via :meth:`predict_batch` pads inputs to a common length
and generates all outputs in a single forward pass for significantly higher
throughput than calling :meth:`predict` in a loop.
"""

from __future__ import annotations

from typing import Any, List, Optional

from aranorm.exceptions import IntegrationUnavailableError, NormalizationError


class TransformersSeq2SeqModel:
    """Lazy-loading wrapper for a Hugging Face Seq2Seq model.

    The model and tokenizer are only downloaded/loaded on the first call to
    :meth:`predict` or :meth:`predict_batch`.

    Parameters
    ----------
    model_name:
        Hugging Face model identifier (e.g. ``"Helsinki-NLP/opus-mt-ar-en"``).
    device:
        Target device string, e.g. ``"cpu"`` or ``"cuda:0"``.  When *None*
        the model stays on its default device.
    max_new_tokens:
        Maximum number of tokens generated per input (default 128).

    Example
    -------
    >>> model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    >>> model.predict("مرحباً بالعالم")
    'Hello World'
    """

    def __init__(
        self,
        model_name: str,
        device: Optional[str] = None,
        max_new_tokens: int = 128,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_new_tokens = max_new_tokens
        self._tokenizer: Any = None
        self._model: Any = None

    # ── Lazy loader ───────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load the model and tokenizer if not already loaded."""
        if self._tokenizer is not None and self._model is not None:
            return
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as error:
            raise IntegrationUnavailableError("Transformers is not installed; use 'pip install aranorm[ml]'") from error
        try:
            if self._tokenizer is None:
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            if self._model is None:
                self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
                if self.device:
                    self._model.to(self.device)
        except Exception as error:
            raise NormalizationError(f"failed to load model '{self.model_name}'") from error

    # ── Public API ────────────────────────────────────────────────────────

    def predict(self, text: str) -> str:
        """Generate one normalized string.

        Parameters
        ----------
        text:
            Input Arabic string.

        Returns
        -------
        str
            Model output string.
        """
        results = self.predict_batch([text])
        return results[0]

    def predict_batch(self, texts: List[str]) -> List[str]:
        """Generate normalized strings for a batch of inputs.

        Processes all *texts* in a single forward pass for significantly
        better throughput than calling :meth:`predict` in a loop.

        Parameters
        ----------
        texts:
            List of input Arabic strings.

        Returns
        -------
        List[str]
            Model outputs in the same order as *texts*.
        """
        if not texts:
            return []
        self._load()
        try:
            encoded = self._tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            if self.device:
                encoded = {k: v.to(self.device) for k, v in encoded.items()}
            generated = self._model.generate(**encoded, max_new_tokens=self.max_new_tokens)
            return [self._tokenizer.decode(ids, skip_special_tokens=True) for ids in generated]
        except Exception as error:
            raise NormalizationError(f"failed to generate output with model '{self.model_name}'") from error

    def is_loaded(self) -> bool:
        """Return *True* when the model and tokenizer are already loaded."""
        return self._tokenizer is not None and self._model is not None

    def unload(self) -> None:
        """Release the model and tokenizer from memory."""
        self._model = None
        self._tokenizer = None
