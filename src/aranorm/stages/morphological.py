"""Optional morphological processing adapters."""

from typing import Any, Dict, List

from aranorm.exceptions import IntegrationUnavailableError


class MorphologicalProcessor:
    """Lazy adapter for CAMeL Tools, Farasa, or Qalsadi-style integrations."""

    def __init__(self, analyzer: Any = None) -> None:
        self.analyzer = analyzer

    def analyze(self, text: str) -> List[Dict[str, Any]]:
        """Analyze text using an injected analyzer.

        An analyzer may expose ``analyze(text)`` or be callable. This keeps the
        core library independent of heavyweight morphology packages.
        """
        if self.analyzer is None:
            raise IntegrationUnavailableError(
                "No morphological analyzer configured. Inject a Farasa, Qalsadi, "
                "or CAMeL-compatible analyzer."
            )
        if hasattr(self.analyzer, "analyze"):
            result = self.analyzer.analyze(text)
        elif callable(self.analyzer):
            result = self.analyzer(text)
        else:
            raise TypeError("analyzer must be callable or expose analyze(text)")
        return list(result)
