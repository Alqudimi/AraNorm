"""Portable, validated pipeline specifications.

The specification layer serializes declarative configuration only.  It never
serializes Python callables, processor instances, or importable object
references, which keeps files portable and safe to validate before use.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Union

from aranorm.core.config import PipelineConfig
from aranorm.exceptions.errors import ConfigurationError

PIPELINE_SPEC_SCHEMA_VERSION = 1
DEFAULT_MAX_SPEC_BYTES = 1_048_576
_SPEC_PIPELINE_CLASS = "ArabicNormalizationPipeline"
_REQUIRED_FIELDS = {
    "schema_version",
    "library_version",
    "pipeline_class",
    "config",
    "config_fingerprint",
    "metadata",
}


def _canonical_json(value: Any) -> str:
    """Return deterministic, strict JSON for a validated value."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("PipelineSpec contains a non-JSON value") from exc


def _clone_json(value: Any, *, label: str) -> Any:
    """Clone JSON-compatible data and reject non-JSON values."""
    try:
        return json.loads(_canonical_json(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"{label} must be JSON-compatible") from exc


def _config_fingerprint(config: Mapping[str, Any]) -> str:
    """Match ArabicNormalizationPipeline.configuration_fingerprint()."""
    payload = _canonical_json(config)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_hex_fingerprint(value: Any) -> str:
    """Validate a configuration SHA-256 fingerprint."""
    if not isinstance(value, str) or len(value) != 64:
        raise ConfigurationError("config_fingerprint must be a 64-character SHA-256 hex string")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ConfigurationError("config_fingerprint must contain hexadecimal characters only") from exc
    return value.lower()


def _validate_size(text: str, max_bytes: int) -> None:
    """Reject oversized specifications before JSON parsing."""
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    if len(text.encode("utf-8")) > max_bytes:
        raise ConfigurationError(f"PipelineSpec exceeds the {max_bytes}-byte limit")


@dataclass(frozen=True)
class PipelineSpec:
    """Versioned declarative representation of a normalization pipeline.

    Only ``PipelineConfig`` data is persisted.  Custom processor instances and
    plugin references are intentionally outside this contract and cannot be
    reconstructed from a spec file.
    """

    schema_version: int
    library_version: str
    pipeline_class: str
    config: Dict[str, Any]
    config_fingerprint: str
    metadata: Dict[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != PIPELINE_SPEC_SCHEMA_VERSION:
            raise ConfigurationError(f"Unsupported PipelineSpec schema version: {self.schema_version}")
        if not isinstance(self.library_version, str) or not self.library_version.strip():
            raise ConfigurationError("library_version must be a non-empty string")
        if self.pipeline_class != _SPEC_PIPELINE_CLASS:
            raise ConfigurationError(f"Unsupported pipeline_class: {self.pipeline_class!r}")
        if not isinstance(self.config, dict):
            raise ConfigurationError("config must be a dictionary")
        if not isinstance(self.metadata, dict):
            raise ConfigurationError("metadata must be a dictionary")

        config = _clone_json(self.config, label="config")
        metadata = _clone_json(self.metadata, label="metadata")
        # Both values are guaranteed to be JSON objects at this point because
        # the field-level type checks above already rejected non-dict values.
        assert isinstance(config, dict) and isinstance(metadata, dict), "config and metadata must be JSON objects"
        PipelineConfig.from_dict(config).validate()
        expected = _config_fingerprint(config)
        actual = _validate_hex_fingerprint(self.config_fingerprint)
        if actual != expected:
            raise ConfigurationError("config_fingerprint does not match config")
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "config_fingerprint", actual)

    @classmethod
    def from_pipeline(
        cls,
        pipeline: Any,
        *,
        library_version: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "PipelineSpec":
        """Create a spec from an existing ArabicNormalizationPipeline."""
        from aranorm import __version__

        if not hasattr(pipeline, "config") or not hasattr(pipeline, "configuration_fingerprint"):
            raise TypeError("pipeline must expose config and configuration_fingerprint()")
        config = _clone_json(pipeline.config.to_dict(), label="config")
        fingerprint = pipeline.configuration_fingerprint()
        return cls(
            schema_version=PIPELINE_SPEC_SCHEMA_VERSION,
            library_version=library_version or __version__,
            pipeline_class=type(pipeline).__name__,
            config=config,
            config_fingerprint=fingerprint,
            metadata=_clone_json(dict(metadata or {}), label="metadata"),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PipelineSpec":
        """Validate and construct a spec from a JSON-compatible mapping."""
        if not isinstance(data, Mapping):
            raise TypeError("PipelineSpec.from_dict() expects a mapping")
        values = dict(data)
        unknown = sorted(set(values) - _REQUIRED_FIELDS)
        missing = sorted(_REQUIRED_FIELDS - set(values))
        if unknown:
            raise ConfigurationError("Unknown PipelineSpec field(s): " + ", ".join(unknown))
        if missing:
            raise ConfigurationError("Missing PipelineSpec field(s): " + ", ".join(missing))
        if not isinstance(values["schema_version"], int) or isinstance(values["schema_version"], bool):
            raise ConfigurationError("schema_version must be an integer")
        if not isinstance(values["pipeline_class"], str):
            raise ConfigurationError("pipeline_class must be a string")
        if not isinstance(values["library_version"], str):
            raise ConfigurationError("library_version must be a string")
        if not isinstance(values["config"], Mapping):
            raise ConfigurationError("config must be a mapping")
        if not isinstance(values["metadata"], Mapping):
            raise ConfigurationError("metadata must be a mapping")
        return cls(
            schema_version=values["schema_version"],
            library_version=values["library_version"],
            pipeline_class=values["pipeline_class"],
            config=_clone_json(dict(values["config"]), label="config"),
            config_fingerprint=values["config_fingerprint"],
            metadata=_clone_json(dict(values["metadata"]), label="metadata"),
        )

    @classmethod
    def from_json(cls, text: str, *, max_bytes: int = DEFAULT_MAX_SPEC_BYTES) -> "PipelineSpec":
        """Parse and validate a bounded UTF-8 JSON specification."""
        if not isinstance(text, str):
            raise TypeError("PipelineSpec.from_json() expects a string")
        _validate_size(text, max_bytes)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"Invalid PipelineSpec JSON: {exc.msg}") from exc
        return cls.from_dict(data)

    @classmethod
    def read_file(
        cls,
        path: Union[str, os.PathLike[str]],
        *,
        max_bytes: int = DEFAULT_MAX_SPEC_BYTES,
    ) -> "PipelineSpec":
        """Read and validate a bounded UTF-8 JSON specification file."""
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            raise ConfigurationError(f"Cannot inspect PipelineSpec file: {exc}") from exc
        if size > max_bytes:
            raise ConfigurationError(f"PipelineSpec exceeds the {max_bytes}-byte limit")
        try:
            with open(path, encoding="utf-8") as stream:
                text = stream.read(max_bytes + 1)
        except (OSError, UnicodeError) as exc:
            raise ConfigurationError(f"Cannot read PipelineSpec file: {exc}") from exc
        return cls.from_json(text, max_bytes=max_bytes)

    def to_dict(self) -> Dict[str, Any]:
        """Return a defensive JSON-compatible mapping."""
        return {
            "schema_version": self.schema_version,
            "library_version": self.library_version,
            "pipeline_class": self.pipeline_class,
            "config": _clone_json(self.config, label="config"),
            "config_fingerprint": self.config_fingerprint,
            "metadata": _clone_json(self.metadata, label="metadata"),
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Return canonical JSON with deterministic key ordering."""
        if indent is not None and (not isinstance(indent, int) or isinstance(indent, bool) or indent < 0):
            raise ValueError("indent must be a non-negative integer or None")
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=indent,
            allow_nan=False,
        )

    def write_file(self, path: Union[str, os.PathLike[str]], *, indent: Optional[int] = 2) -> None:
        """Atomically write the specification as UTF-8 JSON."""
        text = self.to_json(indent=indent) + "\n"
        directory = os.path.dirname(os.fspath(path)) or "."
        temporary_path: Optional[str] = None
        try:
            descriptor, temporary_path = tempfile.mkstemp(prefix=".aranorm-spec-", suffix=".tmp", dir=directory)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, path)
        except OSError as exc:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass
            raise ConfigurationError(f"Cannot write PipelineSpec file: {exc}") from exc

    def to_pipeline(self) -> Any:
        """Reconstruct a pipeline from declarative configuration only."""
        from aranorm.core.pipeline import ArabicNormalizationPipeline

        config = PipelineConfig.from_dict(self.config)
        pipeline = ArabicNormalizationPipeline(config)
        if pipeline.configuration_fingerprint() != self.config_fingerprint:
            raise ConfigurationError("reconstructed pipeline fingerprint does not match spec")
        return pipeline
