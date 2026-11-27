"""Internal processor helpers."""

import re
from typing import Optional

from aranorm.core.base import Processor, ProcessorContext
from aranorm.utils.validators import validate_text


class TextProcessor(Processor):
    """Base class that validates input and records the step."""

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Validate input, transform it, and record the processor name."""
        value = self.transform(validate_text(text))
        self._record(context)
        return value

    def transform(self, text: str) -> str:
        """Transform validated text."""
        raise NotImplementedError


class RegexProcessor(TextProcessor):
    """Processor that replaces regex matches with a static or callable value."""

    pattern: re.Pattern
    replacement: str

    def transform(self, text: str) -> str:
        """Replace all matches."""
        return self.pattern.sub(self.replacement, text)


def processor_transform(processor: Processor, text: str, context: Optional[ProcessorContext]) -> str:
    """Run a processor without requiring callers to know its concrete type."""
    return processor.process(text, context)
