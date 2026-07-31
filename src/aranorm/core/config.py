"""Typed pipeline configuration and presets."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from aranorm.core.stop_words_config import StopWordsConfig  # noqa: F401 (re-exported)


class Preset(str, Enum):
    """Built-in processing profiles."""

    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"
    SOCIAL_MEDIA = "social_media"


class DialectTarget(str, Enum):
    """Optional output dialect target."""

    NONE = "none"
    CODA = "coda"
    MSA = "msa"


@dataclass
class PipelineConfig:
    """Configuration for ArabicNormalizationPipeline.

    All boolean flags default to a sensible *standard* profile.
    Use :meth:`from_preset` or the ``preset`` argument to quickly
    apply one of the four built-in profiles.

    Example
    -------
    >>> cfg = PipelineConfig(preset="deep", remove_diacritics=True)
    >>> cfg.to_json()
    '{"preset": "deep", ...}'
    """

    preset: Union[Preset, str] = Preset.STANDARD
    dialect_target: Union[DialectTarget, str] = DialectTarget.NONE
    remove_diacritics: bool = True
    normalize_hamza: bool = True
    handle_arabizi: bool = False
    normalize_unicode: bool = True
    normalize_alef: bool = True
    normalize_taa_marbuta: bool = False
    normalize_alef_maqsura: bool = True
    normalize_tatweel: bool = True
    normalize_digits: bool = True
    normalize_ligatures: bool = True
    normalize_punctuation: bool = True
    normalize_whitespace: bool = True
    normalize_repeated_chars: bool = False
    remove_extra_punctuation: bool = False
    clean_urls: bool = True
    clean_emails: bool = True
    clean_mentions: bool = False
    clean_hashtags: bool = False
    clean_emojis: bool = False
    clean_html: bool = True
    remove_non_arabic: bool = False
    remove_english: bool = False
    fix_spacing: bool = True
    supported_dialects: Optional[List[str]] = field(default=None)
    # Stop-words support – None means disabled
    stop_words_config: Optional[StopWordsConfig] = field(default=None)

    def __post_init__(self) -> None:
        """Normalize enum-like values and apply profile defaults."""
        self.preset = Preset(self.preset)
        self.dialect_target = DialectTarget(self.dialect_target)
        if self.preset != Preset.STANDARD:
            self._apply_preset_defaults(self.preset)
        self.supported_dialects = self.supported_dialects or []

    def _apply_preset_defaults(self, preset: Preset) -> None:
        """Apply only the options that distinguish a built-in preset."""
        if preset == Preset.LIGHT:
            self.clean_urls = False
            self.clean_emails = False
            self.clean_html = False
            self.normalize_repeated_chars = False
        elif preset == Preset.DEEP:
            self.remove_diacritics = True
            self.normalize_repeated_chars = True
            self.clean_urls = True
            self.clean_emails = True
            self.clean_html = True
            self.fix_spacing = True
        elif preset == Preset.SOCIAL_MEDIA:
            self.clean_urls = True
            self.clean_emails = True
            self.clean_mentions = True
            self.clean_hashtags = False
            self.clean_emojis = True
            self.clean_html = True
            self.normalize_repeated_chars = True
            self.fix_spacing = True
            # Social media preset enables filler + internet removal automatically
            if self.stop_words_config is None:
                self.stop_words_config = StopWordsConfig(
                    mode="remove",
                    scope="universal",
                    remove_filler=True,
                    remove_internet=True,
                    remove_arabizi=True,
                )

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain JSON-serialisable dictionary.

        The result can be round-tripped via :meth:`from_dict`.

        Example
        -------
        >>> cfg = PipelineConfig(preset="standard")
        >>> cfg.to_dict()["preset"]
        'standard'
        """
        data: Dict[str, Any] = {
            "preset": self.preset.value if isinstance(self.preset, Preset) else str(self.preset),
            "dialect_target": (
                self.dialect_target.value
                if isinstance(self.dialect_target, DialectTarget)
                else str(self.dialect_target)
            ),
            "remove_diacritics": self.remove_diacritics,
            "normalize_hamza": self.normalize_hamza,
            "handle_arabizi": self.handle_arabizi,
            "normalize_unicode": self.normalize_unicode,
            "normalize_alef": self.normalize_alef,
            "normalize_taa_marbuta": self.normalize_taa_marbuta,
            "normalize_alef_maqsura": self.normalize_alef_maqsura,
            "normalize_tatweel": self.normalize_tatweel,
            "normalize_digits": self.normalize_digits,
            "normalize_ligatures": self.normalize_ligatures,
            "normalize_punctuation": self.normalize_punctuation,
            "normalize_whitespace": self.normalize_whitespace,
            "normalize_repeated_chars": self.normalize_repeated_chars,
            "remove_extra_punctuation": self.remove_extra_punctuation,
            "clean_urls": self.clean_urls,
            "clean_emails": self.clean_emails,
            "clean_mentions": self.clean_mentions,
            "clean_hashtags": self.clean_hashtags,
            "clean_emojis": self.clean_emojis,
            "clean_html": self.clean_html,
            "remove_non_arabic": self.remove_non_arabic,
            "remove_english": self.remove_english,
            "fix_spacing": self.fix_spacing,
            "supported_dialects": list(self.supported_dialects or []),
        }
        if self.stop_words_config is not None:
            sw = self.stop_words_config
            data["stop_words_config"] = {
                "mode": sw.mode,
                "scope": sw.scope,
                "dialects": sorted(sw.dialects),
                "preserve_negation": sw.preserve_negation,
                "preserve_emphasis": sw.preserve_emphasis,
                "preserve_prepositions": sw.preserve_prepositions,
                "remove_filler": sw.remove_filler,
                "remove_arabizi": sw.remove_arabizi,
                "remove_internet": sw.remove_internet,
                "remove_numbers": sw.remove_numbers,
                "custom_stop_words": sorted(sw.custom_stop_words) if sw.custom_stop_words else None,
                "excluded_stop_words": sorted(sw.excluded_stop_words) if sw.excluded_stop_words else None,
            }
        else:
            data["stop_words_config"] = None
        return data

    def to_json(self, indent: int = 2, ensure_ascii: bool = False) -> str:
        """Serialise the configuration to a JSON string.

        Parameters
        ----------
        indent:
            JSON indentation (default 2).
        ensure_ascii:
            When *False* (default), Arabic characters are preserved.

        Example
        -------
        >>> cfg = PipelineConfig()
        >>> json_str = cfg.to_json()
        >>> PipelineConfig.from_json(json_str).preset == cfg.preset
        True
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Create a :class:`PipelineConfig` from a plain dictionary.

        Accepts the output of :meth:`to_dict` and any partial config dict
        (missing keys take default values).

        Parameters
        ----------
        data:
            Dictionary with config fields (all optional).

        Example
        -------
        >>> cfg = PipelineConfig.from_dict({"preset": "deep", "clean_emojis": True})
        >>> cfg.preset.value
        'deep'
        """
        sw_data = data.pop("stop_words_config", None) if isinstance(data, dict) else None
        data = dict(data)  # make a mutable copy

        # Remove stop_words_config before passing to constructor (we handle it separately)
        data.pop("stop_words_config", None)

        config = cls(**{k: v for k, v in data.items() if hasattr(cls, k) or k in cls.__dataclass_fields__})

        if sw_data is not None:
            config.stop_words_config = StopWordsConfig(
                mode=sw_data.get("mode", "remove"),
                scope=sw_data.get("scope", "universal"),
                dialects=frozenset(sw_data.get("dialects") or []),
                preserve_negation=sw_data.get("preserve_negation", True),
                preserve_emphasis=sw_data.get("preserve_emphasis", False),
                preserve_prepositions=sw_data.get("preserve_prepositions", False),
                remove_filler=sw_data.get("remove_filler", True),
                remove_arabizi=sw_data.get("remove_arabizi", False),
                remove_internet=sw_data.get("remove_internet", False),
                remove_numbers=sw_data.get("remove_numbers", False),
                custom_stop_words=frozenset(sw_data["custom_stop_words"]) if sw_data.get("custom_stop_words") else None,
                excluded_stop_words=frozenset(sw_data["excluded_stop_words"]) if sw_data.get("excluded_stop_words") else None,
            )
        return config

    @classmethod
    def from_json(cls, json_str: str) -> "PipelineConfig":
        """Create a :class:`PipelineConfig` from a JSON string.

        Parameters
        ----------
        json_str:
            JSON produced by :meth:`to_json` or a manually crafted config.

        Example
        -------
        >>> cfg = PipelineConfig.from_json('{"preset": "light"}')
        >>> cfg.preset.value
        'light'
        """
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_preset(cls, preset: Union[Preset, str], **overrides: Any) -> "PipelineConfig":
        """Create a configuration from a named preset and explicit overrides."""
        return cls(preset=preset, **overrides)

    def copy_with(self, **overrides: Any) -> "PipelineConfig":
        """Return a new :class:`PipelineConfig` with specific fields overridden.

        The current instance is never mutated.  Useful for building variants
        of an existing configuration without losing shared settings.

        Parameters
        ----------
        **overrides:
            Any :class:`PipelineConfig` field and its new value.

        Example
        -------
        >>> base = PipelineConfig(preset="standard")
        >>> social = base.copy_with(preset="social_media", clean_emojis=True)
        >>> social is not base
        True
        """
        data = self.to_dict()
        data.update(overrides)
        return PipelineConfig.from_dict(data)

    def validate(self) -> "PipelineConfig":
        """Validate the configuration and raise on any inconsistency.

        Checks for:

        * ``dialect_aware`` scope but no dialect codes specified.
        * ``custom`` scope but no custom stop words supplied.
        * Conflicting flags (e.g. both ``remove_non_arabic`` and
          ``handle_arabizi`` enabled — Arabizi is Latin script).

        Returns
        -------
        PipelineConfig
            *self*, so the call can be chained.

        Raises
        ------
        ConfigurationError
            When the configuration is inconsistent.

        Example
        -------
        >>> PipelineConfig(preset="standard").validate()
        PipelineConfig(preset=<Preset.STANDARD: 'standard'>, ...)
        """
        from aranorm.exceptions import ConfigurationError

        sw = self.stop_words_config
        if sw is not None:
            if sw.scope == "dialect_aware" and not sw.dialects:
                raise ConfigurationError(
                    "stop_words_config.scope='dialect_aware' requires at least one "
                    "dialect code in stop_words_config.dialects."
                )
            if sw.scope == "custom" and not sw.custom_stop_words:
                raise ConfigurationError(
                    "stop_words_config.scope='custom' requires "
                    "stop_words_config.custom_stop_words to be non-empty."
                )

        if self.remove_non_arabic and self.handle_arabizi:
            import warnings
            warnings.warn(
                "remove_non_arabic=True will strip Arabizi (Latin-script Arabic) "
                "before handle_arabizi can convert it.  Consider setting "
                "remove_non_arabic=False when handle_arabizi=True.",
                UserWarning,
                stacklevel=2,
            )
        return self

    def to_yaml(self) -> str:
        """Serialise the configuration to a YAML string.

        Requires ``PyYAML`` (``pip install PyYAML``).

        Returns
        -------
        str
            YAML representation of this configuration.

        Raises
        ------
        ImportError
            When PyYAML is not installed.
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for to_yaml(). Run: pip install PyYAML"
            ) from exc
        return yaml.dump(
            self.to_dict(),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "PipelineConfig":
        """Create a :class:`PipelineConfig` from a YAML string.

        Parameters
        ----------
        yaml_str:
            YAML produced by :meth:`to_yaml` or manually crafted.

        Raises
        ------
        ImportError
            When PyYAML is not installed.

        Example
        -------
        >>> cfg = PipelineConfig.from_yaml('preset: deep\\nremove_diacritics: true')
        >>> cfg.preset.value
        'deep'
        """
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for from_yaml(). Run: pip install PyYAML"
            ) from exc
        data = yaml.safe_load(yaml_str) or {}
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: str) -> "PipelineConfig":
        """Load a :class:`PipelineConfig` from a JSON or YAML file.

        The format is inferred from the file extension (``.json``, ``.yaml``,
        ``.yml``).

        Parameters
        ----------
        path:
            Absolute or relative path to the configuration file.

        Raises
        ------
        ValueError
            When the file extension is not recognised.
        FileNotFoundError
            When the file does not exist.

        Example
        -------
        >>> cfg = PipelineConfig.from_file("config/pipeline.json")
        """
        import os
        _, ext = os.path.splitext(path.lower())
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        if ext == ".json":
            return cls.from_json(content)
        if ext in (".yaml", ".yml"):
            return cls.from_yaml(content)
        raise ValueError(
            f"Unsupported config file extension {ext!r}. Use .json, .yaml, or .yml."
        )

    def __repr__(self) -> str:
        sw = "enabled" if self.stop_words_config is not None else "disabled"
        return (
            f"PipelineConfig("
            f"preset={self.preset.value if isinstance(self.preset, Preset) else self.preset!r}, "
            f"dialect_target={self.dialect_target.value if isinstance(self.dialect_target, DialectTarget) else self.dialect_target!r}, "
            f"stop_words={sw})"
        )
