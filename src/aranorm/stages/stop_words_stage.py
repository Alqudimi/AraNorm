"""Stop-words pipeline stage.

Integrates the stop-words subsystem into the main
:class:`~aranorm.core.pipeline.ArabicNormalizationPipeline` as a self-contained
stage that is activated whenever ``PipelineConfig.stop_words_config`` is set.
"""

from __future__ import annotations

from typing import Optional

from aranorm.core.base import ProcessorContext
from aranorm.core.stop_words_config import StopWordsConfig
from aranorm.core.stop_words_registry import StopWordsRegistry
from aranorm.processors.stop_words_processor import StopWordsProcessor, StopWordsResult


class StopWordsStage:
    """Pipeline stage that applies stop-words processing to normalized text.

    The stage wraps :class:`~aranorm.processors.stop_words_processor.StopWordsProcessor`
    and exposes the same execute / process interface used by other stages.

    Parameters
    ----------
    config:
        :class:`~aranorm.core.stop_words_config.StopWordsConfig` that controls
        the stage behaviour.
    registry:
        Optional shared :class:`~aranorm.core.stop_words_registry.StopWordsRegistry`.
        A singleton is created automatically when omitted.
    """

    def __init__(
        self,
        config: Optional[StopWordsConfig] = None,
        registry: Optional[StopWordsRegistry] = None,
    ) -> None:
        self.config = config or StopWordsConfig()
        self.registry = registry or StopWordsRegistry()
        self._processor = StopWordsProcessor(config=self.config, registry=self.registry)

    # ── Main entry point ─────────────────────────────────────────────────

    def execute(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Execute the stage and return the (possibly modified) text.

        Also stores the detailed :class:`~aranorm.processors.stop_words_processor.StopWordsResult`
        in *context.metadata* under the key ``"stop_words_result"`` so the
        pipeline can attach it to the final :class:`~aranorm.core.pipeline.NormalizationResult`.
        """
        if not text or not text.strip():
            return text

        result: StopWordsResult = self._processor.process_detailed(text)

        if context is not None:
            context.metadata["stop_words_result"] = result
            for step in result.applied_stop_words_steps:
                context.record(f"stop_words:{step}")

        return result.processed_text

    # Alias so it can be used as a plain processor too
    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        """Alias for :meth:`execute`."""
        return self.execute(text, context)

    def get_last_result(self, context: ProcessorContext) -> Optional[StopWordsResult]:
        """Retrieve the :class:`StopWordsResult` stored in *context* metadata."""
        return context.metadata.get("stop_words_result")
