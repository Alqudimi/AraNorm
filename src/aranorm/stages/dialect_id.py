"""Dialect identification with optional CAMeL Tools integration."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Sequence

from aranorm.exceptions import DialectDetectionError, IntegrationUnavailableError
from aranorm.utils.helpers import contains_arabic

LOGGER = logging.getLogger(__name__)

# All supported dialect labels (matching CAMeL Tools schema).
ALL_DIALECT_LABELS: FrozenSet[str] = frozenset(
    [
        "EGY",  # Egyptian
        "GLF",  # Gulf (Saudi, UAE, Kuwait, Bahrain, Qatar, Oman)
        "LEV",  # Levantine (Syria, Lebanon, Palestine, Jordan)
        "IRQ",  # Iraqi
        "NOR",  # North African (Algeria, Libya, Morocco)
        "TUN",  # Tunisian
        "MSA",  # Modern Standard Arabic (Fus-ha)
        "YEM",  # Yemeni
        "SDN",  # Sudanese
        "MTN",  # Mauritanian
    ]
)


@dataclass(frozen=True)
class DialectIdentification:
    """Dialect identification result."""

    dialect_label: str
    confidence_score: float
    is_msa: bool

    @property
    def dialect(self) -> str:
        """Backward-compatible short property name."""
        return self.dialect_label


class DialectIdentifier:
    """Identify dialects using CAMeL Tools when available or a lexical heuristic.

    The built-in heuristic uses transparent word-level markers for seven
    dialects.  For model-level accuracy (>90 % on MADAR) install CAMeL Tools
    and set ``use_camel_tools=True``.
    """

    # ── Lexical markers per dialect ────────────────────────────────────────
    # Each entry is a tuple of (marker, weight).  Higher-weight markers are
    # stronger discriminators between dialects.
    _DIALECT_MARKERS: Dict[str, Sequence[tuple]] = {
        "EGY": [
            ("عايز", 2),
            ("عاوز", 2),
            ("عاوزه", 2),
            ("مش", 1),
            ("ليه", 2),
            ("دلوقتي", 3),
            ("ازاي", 3),
            ("إزاي", 3),
            ("أيوه", 2),
            ("أيوا", 2),
            ("يعني", 1),
            ("بقى", 2),
            ("بقا", 2),
            ("كده", 3),
            ("كدا", 3),
            ("كدة", 3),
            ("فين", 2),
            ("امتى", 3),
            ("إمتى", 3),
            ("إيه", 2),
            ("ايه", 2),
            ("مين", 2),
            ("النهارده", 3),
            ("بكره", 2),
            ("بكرة", 2),
            ("أنهارده", 3),
            ("عشان", 2),
            ("علشان", 2),
            ("أكتر", 2),
            ("اكتر", 2),
            ("هينا", 2),
            ("حاعمل", 3),
            ("هعمل", 3),
        ],
        "GLF": [
            ("شلون", 2),
            ("شلونك", 3),
            ("شخبارك", 3),
            ("شخبار", 2),
            ("وايد", 3),
            ("الحين", 3),
            ("أبي", 1),
            ("ابغى", 3),
            ("أبغى", 3),
            ("شنو", 2),
            ("ليش", 3),
            ("وين", 2),
            ("زين", 2),
            ("خوش", 2),
            ("مسوي", 2),
            ("يسوي", 2),
            ("هاذا", 2),
            ("هاذي", 2),
            ("صح", 1),
            ("گال", 3),
            ("گلت", 3),
            ("گاعد", 3),
            ("ما أدري", 3),
            ("يدري", 2),
            ("بس", 1),
        ],
        "LEV": [
            ("شو", 2),
            ("كيفك", 3),
            ("كيفكم", 3),
            ("هلق", 3),
            ("هلأ", 3),
            ("لسا", 2),
            ("لسه", 2),
            ("كتير", 2),
            ("بدّي", 3),
            ("بدي", 2),
            ("بدك", 2),
            ("منيح", 3),
            ("مزبوط", 3),
            ("هيك", 3),
            ("هاد", 2),
            ("هاي", 2),
            ("إجا", 3),
            ("رح", 2),
            ("عم", 1),
            ("قديش", 3),
            ("ألله", 1),
            ("يسلمو", 2),
            ("يعطيك العافية", 3),
            ("نحنا", 3),
            ("هنن", 3),
        ],
        "IRQ": [
            ("شلونك", 2),
            ("هواية", 3),
            ("أكو", 3),
            ("ماكو", 3),
            ("يمّه", 3),
            ("يباه", 3),
            ("گلت", 2),
            ("گال", 2),
            ("هيچي", 3),
            ("چون", 3),
            ("مال", 2),
            ("مالي", 2),
            ("ديچي", 3),
            ("ذيچي", 3),
        ],
        "NOR": [
            ("بزاف", 3),
            ("واش", 3),
            ("ديال", 3),
            ("راك", 3),
            ("باغي", 3),
            ("داير", 3),
            ("كيفاش", 3),
            ("علاش", 3),
            ("فين", 2),
            ("واعر", 3),
            ("مزيان", 3),
            ("مليح", 2),
            ("خاصني", 3),
            ("خاصك", 3),
            ("ماعنديش", 3),
            ("حنا", 3),
            ("نتا", 3),
            ("هوما", 2),
        ],
        "TUN": [
            ("برشا", 3),
            ("شنوة", 3),
            ("ياسر", 3),
            ("نحب", 2),
            ("علاش", 2),
            ("فما", 3),
            ("مافماش", 3),
            ("أش", 2),
            ("وقتاش", 3),
            ("قداش", 3),
            ("مانجمش", 3),
            ("نجم", 2),
            ("موش", 3),
            ("زادة", 2),
            ("باش", 2),
            ("بش", 2),
        ],
        "YEM": [
            ("شفيك", 3),
            ("عشان", 1),
            ("شو", 1),
            ("أيش", 3),
            ("كيف الحال", 1),
            ("بالله", 2),
            ("إيش", 3),
            ("يمة", 3),
            ("وش", 2),
            ("ليش", 2),
            ("متين", 3),
            ("وشو", 3),
        ],
        "SDN": [
            ("زاتو", 3),
            ("شنو", 3),
            ("كيفن", 3),
            ("وين", 2),
            ("منو", 3),
            ("ما زاتو", 3),
            ("في شنو", 3),
            ("نحن الناس", 2),
            ("دقيقو", 3),
            ("برضو", 2),
            ("برضه", 2),
            ("زي ده", 2),
            ("من زمان", 1),
            ("قاعد", 2),
            ("قاعدة", 2),
            ("شايل", 2),
            ("ماني", 3),
            ("مانو", 3),
            ("ماهي", 3),
        ],
        "MTN": [
            ("أنا تفو", 3),
            ("آشكو", 3),
            ("دوبا", 3),
            ("هاني", 3),
            ("اشنو", 3),
            ("لباس", 2),
            ("بخير", 1),
            ("واتر", 3),
        ],
        "MSA": [
            ("الذي", 2),
            ("التي", 2),
            ("الذين", 2),
            ("اللواتي", 3),
            ("هذا", 1),
            ("هذه", 1),
            ("ذلك", 1),
            ("تلك", 1),
            ("إن", 1),
            ("أن", 1),
            ("لأن", 1),
            ("كان", 1),
            ("لذلك", 2),
            ("وهكذا", 2),
            ("ومن ثم", 3),
            ("وبالتالي", 2),
            ("علاوة على ذلك", 3),
            ("بيد أن", 3),
            ("إذ", 2),
            ("وقد", 2),
            ("بينما", 2),
        ],
    }

    def __init__(
        self,
        supported_dialects: Optional[Sequence[str]] = None,
        use_camel_tools: bool = False,
    ) -> None:
        self.supported_dialects = {d.upper() for d in (supported_dialects or [])}
        self.use_camel_tools = use_camel_tools
        self._camel_model: Any = None

    def identify(self, text: str) -> DialectIdentification:
        """Identify a text's dialect and confidence.

        Args:
            text: Arabic text to classify.

        Returns:
            DialectIdentification with label, confidence, and is_msa flag.

        Raises:
            DialectDetectionError: If the optional model fails unexpectedly.
            IntegrationUnavailableError: If CAMeL Tools was requested but absent.
        """
        if self.use_camel_tools:
            return self._identify_with_camel(text)
        return self._identify_with_heuristic(text)

    def _identify_with_camel(self, text: str) -> DialectIdentification:
        """Call CAMeL's dialect identifier lazily."""
        try:
            from camel_tools.dialectid import DialectIdentifier as CamelDI
        except ImportError as error:
            raise IntegrationUnavailableError(
                "CAMeL Tools is required for model-based dialect identification; "
                "install with: pip install aranorm[camel]"
            ) from error
        try:
            if self._camel_model is None:
                self._camel_model = CamelDI.pretrained()
            label, confidence = self._camel_model.predict([text])[0]
            normalized_label = str(label).upper()
            return DialectIdentification(
                normalized_label,
                float(confidence),
                normalized_label == "MSA",
            )
        except Exception as error:
            LOGGER.exception("CAMeL dialect identification failed")
            raise DialectDetectionError("CAMeL Tools could not identify the dialect") from error

    @staticmethod
    def _count_marker(text: str, marker: str) -> int:
        """Count a marker only when it occupies a complete Arabic token/phrase.

        The previous substring-based count made ``شلونك`` contribute both the
        ``شلون`` and ``شلونك`` markers.  Boundary-aware matching prevents that
        double counting while still supporting multi-word markers.
        """
        escaped = re.escape(marker).replace(r"\ ", r"\s+")
        pattern = rf"(?<![\u0621-\u064A]){escaped}(?![\u0621-\u064A])"
        return len(re.findall(pattern, text))

    def _identify_with_heuristic(self, text: str) -> DialectIdentification:
        """Classify using weighted lexical markers as a dependency-free fallback."""
        if not text.strip() or not contains_arabic(text):
            return DialectIdentification("UNK", 0.0, False)

        # Compute weighted scores for each dialect.
        scores: Dict[str, float] = {}
        active_dialects = self.supported_dialects if self.supported_dialects else set(self._DIALECT_MARKERS.keys())

        for label, markers in self._DIALECT_MARKERS.items():
            if label not in active_dialects:
                continue
            score = sum(weight * self._count_marker(text, marker) for marker, weight in markers)
            if score > 0:
                scores[label] = score

        if not scores:
            # No markers matched — assume MSA
            return DialectIdentification("MSA", 0.40, True)

        winner = max(scores, key=scores.get)  # type: ignore[arg-type]
        top_score = scores[winner]

        # Soft confidence: cap at 0.95, minimum 0.55 when at least one marker hit.
        # Gap between winner and second place boosts confidence.
        sorted_scores = sorted(scores.values(), reverse=True)
        gap = (sorted_scores[0] - sorted_scores[1]) if len(sorted_scores) > 1 else top_score
        confidence = min(0.95, 0.55 + gap * 0.05 + top_score * 0.02)

        return DialectIdentification(winner, confidence, winner == "MSA")
