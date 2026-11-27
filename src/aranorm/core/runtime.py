"""Thread-safe runtime snapshots for long-lived AraNorm services.

The runtime layer deliberately composes the existing pipeline instead of
reimplementing processing.  A reload builds a complete replacement snapshot
before publishing it, so readers never observe a partially initialised
pipeline.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union

from aranorm.core.config import PipelineConfig
from aranorm.core.pipeline import ArabicNormalizationPipeline, NormalizationResult
from aranorm.core.spec import PipelineSpec

PipelineFactory = Callable[[PipelineConfig], ArabicNormalizationPipeline]


@dataclass(frozen=True)
class ReloadResult:
    """Machine-readable outcome of a runtime configuration reload."""

    success: bool
    generation: int
    config_fingerprint: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a stable, JSON-compatible representation."""
        return {
            "schema_version": 1,
            "success": self.success,
            "generation": self.generation,
            "config_fingerprint": self.config_fingerprint,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class RuntimeHealth:
    """Liveness/readiness state for an AraNorm runtime snapshot."""

    generation: int
    config_fingerprint: str
    last_reload_error: Optional[Dict[str, str]] = None

    @property
    def ready(self) -> bool:
        """Return whether a usable pipeline snapshot is available."""
        return True

    @property
    def status(self) -> str:
        """Return ``ready`` or ``degraded`` without exposing input text."""
        return "degraded" if self.last_reload_error else "ready"

    def to_dict(self) -> Dict[str, Any]:
        """Return a defensive JSON-compatible health payload."""
        return {
            "schema_version": 1,
            "status": self.status,
            "ready": self.ready,
            "generation": self.generation,
            "config_fingerprint": self.config_fingerprint,
            "last_reload_error": dict(self.last_reload_error) if self.last_reload_error else None,
        }


def _safe_error(error: Exception) -> Dict[str, str]:
    """Return bounded diagnostics without retaining configuration payloads."""
    error_type = type(error).__name__
    if isinstance(error, FileNotFoundError):
        message = "configuration file was not found"
    elif isinstance(error, PermissionError):
        message = "configuration file could not be read"
    elif isinstance(error, ValueError):
        message = str(error) or "configuration value is invalid"
    else:
        message = "runtime reload failed"
    message = " ".join(message.split())[:240]
    return {"error_type": error_type, "message": message}


def _copy_config(config: PipelineConfig) -> PipelineConfig:
    """Clone a configuration through its validated public serialization."""
    return PipelineConfig.from_dict(config.to_dict())


class PipelineRuntime:
    """Manage an atomically replaceable pipeline snapshot.

    The class is intentionally small and synchronous.  Existing pipeline
    methods remain responsible for normalization, batching, metrics, and
    resource limits; this class only owns snapshot publication and operational
    state.  A failed reload leaves the previous pipeline active and marks the
    runtime as degraded for readiness reporting.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        *,
        factory: Optional[PipelineFactory] = None,
    ) -> None:
        self._factory = factory or ArabicNormalizationPipeline
        initial = _copy_config(config or PipelineConfig())
        initial.validate()
        self._pipeline = self._factory(initial)
        self._config = initial
        self._generation = 0
        self._last_reload_error: Optional[Dict[str, str]] = None
        self._lock = threading.RLock()

    @property
    def generation(self) -> int:
        """Return the current snapshot generation."""
        with self._lock:
            return self._generation

    @property
    def config(self) -> PipelineConfig:
        """Return a defensive copy of the current configuration."""
        with self._lock:
            return _copy_config(self._config)

    def get_pipeline(self) -> ArabicNormalizationPipeline:
        """Return the currently published pipeline snapshot.

        The returned object is a stable snapshot for the caller; future
        reloads publish a different object and do not mutate this reference.
        Callers should prefer :meth:`process` for ordinary request handling.
        """
        with self._lock:
            return self._pipeline

    def process(self, text: str) -> NormalizationResult:
        """Process one item using the snapshot visible at call start."""
        with self._lock:
            pipeline = self._pipeline
        return pipeline.process(text)

    def process_batch(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 32,
        n_workers: int = 1,
    ) -> List[NormalizationResult]:
        """Process a batch using one stable pipeline snapshot."""
        with self._lock:
            pipeline = self._pipeline
        return pipeline.process_batch(texts, batch_size=batch_size, n_workers=n_workers)

    def describe(self) -> Dict[str, Any]:
        """Return pipeline description plus runtime generation metadata."""
        with self._lock:
            pipeline = self._pipeline
            generation = self._generation
        description = dict(pipeline.describe_operational())
        description["runtime"] = {"generation": generation, "status": self.health().status}
        return description

    def health(self) -> RuntimeHealth:
        """Return readiness state without including user text or results."""
        with self._lock:
            pipeline = self._pipeline
            generation = self._generation
            last_error = dict(self._last_reload_error) if self._last_reload_error else None
        return RuntimeHealth(
            generation=generation,
            config_fingerprint=pipeline.configuration_fingerprint(),
            last_reload_error=last_error,
        )

    def reload(self, config: PipelineConfig) -> ReloadResult:
        """Build and publish a new snapshot, preserving the old one on error."""
        try:
            candidate = _copy_config(config)
            candidate.validate()
            pipeline = self._factory(candidate)
            fingerprint = pipeline.configuration_fingerprint()
        except Exception as error:  # noqa: BLE001
            details = _safe_error(error)
            with self._lock:
                self._last_reload_error = details
                generation = self._generation
            return ReloadResult(
                success=False,
                generation=generation,
                error_type=details["error_type"],
                error_message=details["message"],
            )

        with self._lock:
            self._pipeline = pipeline
            self._config = candidate
            self._generation += 1
            self._last_reload_error = None
            generation = self._generation
        return ReloadResult(success=True, generation=generation, config_fingerprint=fingerprint)

    def spec(self, *, metadata: Optional[Mapping[str, Any]] = None) -> PipelineSpec:
        """Return a portable spec for the currently published snapshot."""
        with self._lock:
            pipeline = self._pipeline
        return pipeline.to_spec(metadata=metadata)

    def reload_from_spec(self, spec: Union[PipelineSpec, Mapping[str, Any]]) -> ReloadResult:
        """Validate a spec and reload through the atomic configuration path."""
        try:
            validated = spec if isinstance(spec, PipelineSpec) else PipelineSpec.from_dict(spec)
            config = PipelineConfig.from_dict(validated.config)
        except Exception as error:  # noqa: BLE001
            details = _safe_error(error)
            with self._lock:
                self._last_reload_error = details
                generation = self._generation
            return ReloadResult(
                success=False,
                generation=generation,
                error_type=details["error_type"],
                error_message=details["message"],
            )
        return self.reload(config)

    def reload_from_spec_file(self, path: Union[str, os.PathLike[str]]) -> ReloadResult:
        """Read a bounded PipelineSpec file and reload it safely."""
        try:
            spec = PipelineSpec.read_file(path)
        except Exception as error:  # noqa: BLE001
            details = _safe_error(error)
            with self._lock:
                self._last_reload_error = details
                generation = self._generation
            return ReloadResult(
                success=False,
                generation=generation,
                error_type=details["error_type"],
                error_message=details["message"],
            )
        return self.reload_from_spec(spec)

    def reload_from_file(self, path: Union[str, os.PathLike[str]]) -> ReloadResult:
        """Load JSON/YAML through ``PipelineConfig.from_file`` and reload safely."""
        try:
            config = PipelineConfig.from_file(path)
        except Exception as error:  # noqa: BLE001
            details = _safe_error(error)
            with self._lock:
                self._last_reload_error = details
                generation = self._generation
            return ReloadResult(
                success=False,
                generation=generation,
                error_type=details["error_type"],
                error_message=details["message"],
            )
        return self.reload(config)
