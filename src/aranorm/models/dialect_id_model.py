"""CAMeL Tools dialect ID wrapper."""

from typing import Any, Optional, Sequence

from aranorm.exceptions import DialectDetectionError, IntegrationUnavailableError


class DialectIDModel:
    """Lazy wrapper around CAMeL Tools' pretrained dialect identifier."""

    def __init__(self, supported_dialects: Optional[Sequence[str]] = None) -> None:
        self.supported_dialects = {item.upper() for item in (supported_dialects or [])}
        self._model: Any = None

    def predict(self, text: str) -> tuple:
        """Return ``(label, confidence)`` for one string."""
        try:
            from camel_tools.dialectid import DialectIdentifier
        except ImportError as error:
            raise IntegrationUnavailableError(
                "CAMeL Tools is not installed; use 'pip install aranorm[camel]'"
            ) from error
        try:
            if self._model is None:
                self._model = DialectIdentifier.pretrained()
            label, confidence = self._model.predict([text])[0]
            if self.supported_dialects and label.upper() not in self.supported_dialects:
                return "UNK", 0.0
            return label.upper(), float(confidence)
        except Exception as error:
            raise DialectDetectionError("CAMeL Tools dialect prediction failed") from error
