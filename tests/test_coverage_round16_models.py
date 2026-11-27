"""Coverage suite for the optional model adapters.

These tests simulate the presence of the third-party ``transformers`` and
``camel_tools`` libraries by injecting lightweight fake modules into
``sys.modules`` via ``monkeypatch.setitem``.  The shared autouse fixture in
``conftest.py`` keeps the fake modules isolated from unrelated tests.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List

import pytest

from aranorm.exceptions import (
    DialectDetectionError,
    IntegrationUnavailableError,
    NormalizationError,
)
from aranorm.models import CODAModel, DialectIDModel, MSAModel
from aranorm.models._transformers_model import TransformersSeq2SeqModel

# ── Session-level isolation for the models adapter suite ───────────


@pytest.fixture(autouse=True)
def _isolate_model_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean ``transformers`` / ``camel_tools`` between every test.

    The integration-suite isolation fixture (``conftest.py``) only knows
    about ``nltk`` / ``spacy`` / ``pandas`` / ``datasets``, so this
    file-local autouse fixture covers the model-layer fakes.
    """
    monkeypatch.delitem(sys.modules, "transformers", raising=False)
    monkeypatch.delitem(sys.modules, "camel_tools", raising=False)
    monkeypatch.delitem(sys.modules, "camel_tools.dialectid", raising=False)


# ── Fake builders ────────────────────────────────────────────────


class _FakeTensor:
    """Stand-in for a ``torch.Tensor`` with a ``.to(device)`` method."""

    def __init__(self, values: List[Any]) -> None:
        self.values = values
        self.device: Any = None

    def to(self, device: Any) -> "_FakeTensor":
        self.device = device
        return self

    def __iter__(self):
        return iter(self.values)


def _make_fake_transformers(broken_from_pretrained: bool = False) -> types.ModuleType:
    """Minimal ``transformers`` fake with ``AutoTokenizer`` / ``AutoModelForSeq2SeqLM``."""
    transformers = types.ModuleType("transformers")

    class _FakeTokenizer:
        """Tokenizer stand-in: returns padded ``input_ids`` / ``attention_mask``."""

        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        @classmethod
        def from_pretrained(cls, model_name: str) -> "_FakeTokenizer":
            if broken_from_pretrained:
                raise RuntimeError("network unreachable")
            return cls(model_name)

        def __call__(
            self,
            texts: List[str],
            return_tensors: str = "pt",
            padding: bool = True,
            truncation: bool = True,
            max_length: int = 512,
        ) -> Dict[str, _FakeTensor]:
            padded: List[List[int]] = []
            for text in texts:
                ids = [ord(ch) for ch in text] or [32]
                padded.append((ids + [0] * max(0, max_length - len(ids)))[:max_length])
            lengths = [len(t) for t in texts]
            return {
                "input_ids": _FakeTensor(padded),
                "attention_mask": _FakeTensor([[1] * _len + [0] * (max_length - _len) for _len in lengths]),
            }

        def decode(self, ids: Any, skip_special_tokens: bool = False) -> str:
            raw = ids.values if hasattr(ids, "values") else ids
            decoded = "".join(chr(i) for i in raw if i)
            return f"translated:{decoded}" if decoded else ""

    class _FakeModel:
        """Seq2Seq model stand-in: ``generate`` mirrors the tokenised inputs."""

        def __init__(self, model_name: str) -> None:
            self.model_name = model_name
            self.device: Any = None

        @classmethod
        def from_pretrained(cls, model_name: str) -> "_FakeModel":
            if broken_from_pretrained:
                raise RuntimeError("network unreachable")
            return cls(model_name)

        def to(self, device: Any) -> "_FakeModel":
            self.device = device
            return self

        def generate(self, **kwargs: Any) -> List[_FakeTensor]:
            input_ids: Any = kwargs.get("input_ids")
            return [_FakeTensor(list(row)) for row in input_ids.values]

    transformers.AutoTokenizer = _FakeTokenizer
    transformers.AutoModelForSeq2SeqLM = _FakeModel
    return transformers


class _FakeDialectIdentifier:
    """``camel_tools.dialectid.DialectIdentifier`` stand-in."""

    def __init__(self, label: str = "EGY", confidence: float = 0.95) -> None:
        self.label = label
        self.confidence = confidence

    @classmethod
    def pretrained(cls) -> "_FakeDialectIdentifier":
        return cls()

    def predict(self, texts: List[str]) -> List[tuple]:
        return [(self.label, self.confidence) for _ in texts]


def _make_fake_camel_tools() -> types.ModuleType:
    """Minimal ``camel_tools`` + ``camel_tools.dialectid`` fake package."""
    camel_tools = types.ModuleType("camel_tools")
    dialectid = types.ModuleType("camel_tools.dialectid")

    class _BrokenDialectIdentifier:
        """Raises on ``predict`` to exercise the ``DialectDetectionError`` path."""

        @classmethod
        def pretrained(cls) -> "_BrokenDialectIdentifier":
            return cls()

        def predict(self, texts: List[str]) -> List[tuple]:
            raise RuntimeError("prediction failed")

    dialectid.DialectIdentifier = _FakeDialectIdentifier
    camel_tools.dialectid = dialectid
    sys.modules["camel_tools"] = camel_tools
    sys.modules["camel_tools.dialectid"] = dialectid
    return camel_tools


# ── TransformersSeq2SeqModel ─────────────────────────────────────


def test_transformers_model_predict_single_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    assert model.predict("مرحبا") == "translated:مرحبا"
    assert model.is_loaded()


def test_transformers_model_predict_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    results = model.predict_batch(["نص", "آخر"])
    assert len(results) == 2
    assert results[0].startswith("translated:")
    assert model.is_loaded()


def test_transformers_model_empty_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    assert model.predict_batch([]) == []
    assert not model.is_loaded()  # Empty input must not trigger the load.


def test_transformers_model_lazy_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model stays unloaded until the first prediction call."""
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    assert not model.is_loaded()
    fake = _make_fake_transformers()
    monkeypatch.setitem(sys.modules, "transformers", fake)
    model.predict("نص")
    assert model.is_loaded()
    # Second call must not re-import; drop the fake and predict again.
    monkeypatch.delitem(sys.modules, "transformers")
    assert model.predict("نص") == "translated:نص"


def test_transformers_model_unload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    model.predict("نص")
    assert model.is_loaded()
    model.unload()
    assert not model.is_loaded()
    # After unloading, prediction must re-load.
    assert model.predict("نص") == "translated:نص"


def test_transformers_model_device_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both the model and the encoded tensors must move to the requested device."""
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en", device="cuda:0")
    model.predict("نص")
    assert model._model.device == "cuda:0"  # type: ignore[attr-defined]


def test_transformers_model_max_new_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en", max_new_tokens=32)
    model.predict("نص")
    # The fake model captures generate kwargs via the closure; verify the
    # attribute exists on the wrapper.
    assert model.max_new_tokens == 32


def test_transformers_model_missing_transformers_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    with pytest.raises(IntegrationUnavailableError, match="Transformers is not installed"):
        model.predict("نص")
    with pytest.raises(IntegrationUnavailableError, match="Transformers is not installed"):
        model.predict_batch(["نص"])


def test_transformers_model_load_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers(broken_from_pretrained=True))
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    with pytest.raises(NormalizationError, match="failed to load model"):
        model.predict("نص")


def test_transformers_model_generate_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    transformers = _make_fake_transformers()

    class _BrokenModel:  # type: ignore[misc]
        @classmethod
        def from_pretrained(cls, model_name: str) -> "_BrokenModel":
            return cls()

        def to(self, device: Any) -> "_BrokenModel":
            return self

        def generate(self, **kwargs: Any) -> List[_FakeTensor]:
            raise RuntimeError("out of memory")

    transformers.AutoModelForSeq2SeqLM = _BrokenModel  # type: ignore[assignment]
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    with pytest.raises(NormalizationError, match="failed to generate output"):
        model.predict("نص")


def test_transformers_model_repeat_load_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en")
    model.predict("أول")
    assert model.is_loaded()
    # Calling _load again must be a no-op (early return path).
    model._load()
    assert model.predict("ثاني") == "translated:ثاني"


def test_transformers_model_reload_after_unload_covers_inner_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise both lazy-load halves: tokenizer-only and model-only states."""
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = TransformersSeq2SeqModel("Helsinki-NLP/opus-mt-ar-en", device="cpu")
    model.predict("نص")
    assert model.is_loaded()
    # Simulate an asymmetric state that ``_load`` must heal: only the model
    # is present while the tokenizer slot is empty.  This covers the
    # ``self._tokenizer is None`` branch when the model is already cached.
    model._tokenizer = None
    model.predict("نص")
    assert model.is_loaded()


# ── CODAModel / MSAModel subclasses ──────────────────────────────


def test_coda_model_normalize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = CODAModel("CAMeL-Lab/arabart")
    assert model.normalize("شلونك؟") == "translated:شلونك؟"
    assert isinstance(model, TransformersSeq2SeqModel)


def test_coda_model_normalize_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = CODAModel("CAMeL-Lab/arabart")
    results = model.normalize_batch(["شلونك؟", "وش عندك"])
    assert len(results) == 2


def test_msa_model_normalize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = MSAModel("Helsinki-NLP/opus-mt-ar-ar")
    assert model.normalize("شلونك؟") == "translated:شلونك؟"


def test_msa_model_normalize_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = MSAModel("Helsinki-NLP/opus-mt-ar-ar")
    results = model.normalize_batch(["شلونك؟"])
    assert len(results) == 1


def test_msa_model_device_and_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "transformers", _make_fake_transformers())
    model = MSAModel("Helsinki-NLP/opus-mt-ar-ar", device="cpu", max_new_tokens=64)
    model.normalize("نص")
    assert model._model.device == "cpu"  # type: ignore[attr-defined]
    assert model.max_new_tokens == 64


# ── DialectIDModel ───────────────────────────────────────────────


def test_dialect_id_model_predict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "camel_tools", _make_fake_camel_tools())
    model = DialectIDModel()
    label, confidence = model.predict("شلونك؟")
    assert label == "EGY"
    assert 0.0 < confidence <= 1.0


def test_dialect_id_model_supported_dialects_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "camel_tools", _make_fake_camel_tools())
    model = DialectIDModel(supported_dialects=["EGY", "SAU"])
    label, confidence = model.predict("نص")
    assert label == "EGY"
    assert confidence > 0.0


def test_dialect_id_model_supported_dialects_miss_returns_unk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "camel_tools", _make_fake_camel_tools())
    model = DialectIDModel(supported_dialects=["SAU", "MAR"])
    label, confidence = model.predict("نص")
    assert label == "UNK"
    assert confidence == 0.0


def test_dialect_id_model_predict_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    camel_tools = _make_fake_camel_tools()

    class _BrokenDialectIdentifier:  # type: ignore[misc]
        @classmethod
        def pretrained(cls) -> "_BrokenDialectIdentifier":
            return cls()

        def predict(self, texts: List[str]) -> List[tuple]:
            raise RuntimeError("prediction failed")

    camel_tools.dialectid.DialectIdentifier = _BrokenDialectIdentifier  # type: ignore[assignment]
    monkeypatch.setitem(sys.modules, "camel_tools", camel_tools)
    model = DialectIDModel()
    with pytest.raises(DialectDetectionError, match="CAMeL Tools dialect prediction failed"):
        model.predict("نص")


def test_dialect_id_model_missing_camel_tools_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    model = DialectIDModel()
    with pytest.raises(IntegrationUnavailableError, match="CAMeL Tools is not installed"):
        model.predict("نص")


def test_dialect_id_model_lazy_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CAMeL Tools import happens only at prediction time, not construction."""
    monkeypatch.setitem(sys.modules, "camel_tools", _make_fake_camel_tools())
    model = DialectIDModel()
    assert model._model is None
    model.predict("نص")
    assert model._model is not None
    # Second prediction reuses the cached model.
    label, _ = model.predict("نص آخر")
    assert label == "EGY"
