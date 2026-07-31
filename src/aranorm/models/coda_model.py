"""CODA model wrapper.

CODA (Conventional Orthography for Dialectal Arabic) normalization using a
Seq2Seq Transformer model.  The default model identifier is intentionally left
for the user to supply, since appropriate CODA models are domain-specific and
change over time.  Community options include models published by CAMeL Lab or
QCRI on the Hugging Face Hub.

Example
-------
>>> # pip install aranorm[ml]
>>> from aranorm.models import CODAModel
>>> model = CODAModel("CAMeL-Lab/arabart")
>>> model.normalize("شلونك وايد مبسوط")
'كيف حالك كثيراً مبسوط'
"""

from __future__ import annotations

from typing import List, Optional

from aranorm.models._transformers_model import TransformersSeq2SeqModel


class CODAModel(TransformersSeq2SeqModel):
    """Lazy Seq2Seq wrapper for CODA dialect normalization.

    Parameters
    ----------
    model_name:
        Hugging Face model identifier for a Seq2Seq CODA model.  No default
        is provided because the right choice is domain-specific; the CAMeL
        Lab ``arabart`` family is a common starting point.
    device:
        Target device (``"cpu"``, ``"cuda:0"``).
    max_new_tokens:
        Maximum token budget for generation (default 128).
    """

    def __init__(
        self,
        model_name: str,
        device: Optional[str] = None,
        max_new_tokens: int = 128,
    ) -> None:
        super().__init__(model_name, device, max_new_tokens)

    def normalize(self, text: str) -> str:
        """Normalize one string to CODA form.

        Parameters
        ----------
        text:
            Dialectal Arabic string.
        """
        return self.predict(text)

    def normalize_batch(self, texts: List[str]) -> List[str]:
        """Normalize a batch of strings to CODA form.

        Parameters
        ----------
        texts:
            List of dialectal Arabic strings.
        """
        return self.predict_batch(texts)
