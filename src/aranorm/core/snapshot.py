"""Pipeline state snapshots: deterministic save/load of a configured pipeline.

A :class:`PipelineSnapshot` captures everything needed to recreate a
configured :class:`ArabicNormalizationPipeline` on another machine or at a
later time: the pipeline **version**, the ``PipelineConfig`` dictionary,
and the ordered list of active stages.  Snapshots round-trip through JSON
bit-for-bit (key order preserved) so they can be stored, diffed, and
replayed without any loss of configuration fidelity.

This module is fully additive — it serialises the existing public
configuration surface and never touches the pipeline internals.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aranorm

# The snapshot schema revision — bumped when the serialised shape changes
# in a backwards-incompatible way.
SNAPSHOT_SCHEMA_VERSION = 1


@dataclass
class PipelineSnapshot:
    """Frozen serialisable state of a configured pipeline.

    Attributes
    ----------
    aranorm_version:
        The ``aranorm`` package version that produced the snapshot.
    config:
        The pipeline configuration as a plain dictionary (same shape as
        ``PipelineConfig.to_dict()``).
    stage_order:
        Ordered list of active stage names that the pipeline will run.
    metadata:
        Optional free-form annotations (creator, environment, purpose…).

    Example
    -------
    >>> from aranorm.core.config import PipelineConfig
    >>> config = PipelineConfig()
    >>> snapshot = PipelineSnapshot(config=config.to_dict())
    >>> round_trip = PipelineSnapshot.from_json(snapshot.to_json())
    >>> round_trip == snapshot
    True
    """

    config: Dict[str, Any] = field(default_factory=dict)
    stage_order: List[str] = field(default_factory=list)
    aranorm_version: str = field(default_factory=lambda: aranorm.__version__)
    schema_version: int = SNAPSHOT_SCHEMA_VERSION
    metadata: Dict[str, str] = field(default_factory=dict)

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Plain-dictionary representation (JSON-ready)."""
        return {
            "schema_version": self.schema_version,
            "aranorm_version": self.aranorm_version,
            "config": dict(self.config),
            "stage_order": list(self.stage_order),
            "metadata": dict(self.metadata),
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Serialise the snapshot to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str, *, indent: Optional[int] = 2) -> str:
        """Write the snapshot to *path* and return the absolute file name.

        Parent directories are created automatically when missing.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        absolute = os.path.abspath(path)
        with open(absolute, "w", encoding="utf-8") as handle:
            handle.write(self.to_json(indent=indent))
        return absolute

    # ── Deserialization ──────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PipelineSnapshot":
        """Recreate a snapshot from a plain dictionary."""
        if not isinstance(payload, dict):
            raise TypeError(f"expected dict payload, got {type(payload).__name__}")
        return cls(
            config=dict(payload.get("config", {})),
            stage_order=list(payload.get("stage_order", [])),
            aranorm_version=str(payload.get("aranorm_version", aranorm.__version__)),
            schema_version=int(payload.get("schema_version", SNAPSHOT_SCHEMA_VERSION)),
            metadata={str(k): str(v) for k, v in payload.get("metadata", {}).items()},
        )

    @classmethod
    def from_json(cls, text: str) -> "PipelineSnapshot":
        """Parse a snapshot from a JSON string."""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid snapshot JSON: {exc}") from exc
        return cls.from_dict(payload)

    @classmethod
    def load(cls, path: str) -> "PipelineSnapshot":
        """Read a snapshot from a JSON file on disk."""
        if not os.path.isfile(path):
            raise FileNotFoundError(f"snapshot file not found: {path}")
        with open(path, encoding="utf-8") as handle:
            return cls.from_json(handle.read())

    # ── Utilities ────────────────────────────────────────────────────────────

    def diff(self, other: "PipelineSnapshot") -> Dict[str, Any]:
        """Highlight configuration differences between two snapshots.

        Returns a dictionary with ``config_changes``, ``stage_order_changes``,
        and ``version_mismatch`` keys; each ``config_changes`` entry maps a
        dotted path to ``{old, new}`` values.
        """
        config_changes: Dict[str, Dict[str, Any]] = {}
        all_keys = set(self.config) | set(other.config)
        for key in sorted(all_keys):
            if self.config.get(key) != other.config.get(key):
                config_changes[key] = {
                    "old": self.config.get(key),
                    "new": other.config.get(key),
                }
        stage_order_changes = (
            self.stage_order != other.stage_order and {"old": self.stage_order, "new": other.stage_order} or None
        )
        return {
            "config_changes": config_changes,
            "stage_order_changes": stage_order_changes,
            "version_mismatch": self.aranorm_version != other.aranorm_version,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PipelineSnapshot):
            return NotImplemented
        return (
            self.aranorm_version == other.aranorm_version
            and self.config == other.config
            and self.stage_order == other.stage_order
            and self.metadata == other.metadata
        )


def snapshot_pipeline(
    config: Any,
    stage_order: Optional[List[str]] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> PipelineSnapshot:
    """Build a snapshot straight from a ``PipelineConfig`` instance."""
    to_dict = getattr(config, "to_dict", None)
    config_dict = to_dict() if callable(to_dict) else dict(config or {})
    stages = stage_order or []
    if not stages:
        ordered = getattr(config, "stage_order", None)
        if ordered is not None:
            stages = [stage.stage_name for stage in ordered] if hasattr(ordered, "__iter__") else list(ordered)
    return PipelineSnapshot(config=config_dict, stage_order=stages, metadata=dict(metadata or {}))
