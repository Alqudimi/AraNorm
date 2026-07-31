"""MSA model wrapper.

Dialect-to-MSA (Modern Standard Arabic) normalization using a Seq2Seq
Transformer model.

Example
-------
>>> # pip install aranorm[ml]
>>> from aranorm.models import MSAModel
>>> model = MSAModel("Helsinki-NLP/opus-mt-ar-ar")
>>> model.normalize("شلونك؟")
'كيف حالك؟'
"""

from __future__ import annotations

from typing import List, Optional

from aranorm.models._transformers_model import TransformersSeq2SeqModel


class MSAModel(TransformersSeq2SeqModel):
    """Lazy Seq2Seq wrapper for dialect-to-MSA normalization.

    Parameters
    ----------
    model_name:
        Hugging Face model identifier for a Seq2Seq dialect→MSA model.
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
        """Normalize one string to MSA form.

        Parameters
        ----------
        text:
            Dialectal Arabic string.
        """
        return self.predict(text)

    def normalize_batch(self, texts: List[str]) -> List[str]:
        """Normalize a batch of strings to MSA form.

        Parameters
        ----------
        texts:
            List of dialectal Arabic strings.
        """
        return self.predict_batch(texts)
