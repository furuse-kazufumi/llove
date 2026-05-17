"""Engine metadata."""
from __future__ import annotations

import dataclasses
import importlib.metadata
import platform


@dataclasses.dataclass(frozen=True)
class EngineInfo:
    """Static engine metadata returned by introspection endpoints."""

    name: str = "llove-engine"
    version: str = ""
    phase: str = "1-skeleton"  # 1-skeleton / 2-research-ide / 3-multi-ui
    python: str = ""
    platform: str = ""
    capabilities: tuple[str, ...] = (
        "sources",
        "export",
        "mcp",
        "events",
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "phase": self.phase,
            "python": self.python,
            "platform": self.platform,
            "capabilities": list(self.capabilities),
        }


def engine_info() -> EngineInfo:
    """Return engine metadata for the currently installed llove."""
    try:
        version = importlib.metadata.version("llmesh-llove")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        version = "dev"
    return EngineInfo(
        version=version,
        python=platform.python_version(),
        platform=platform.platform(),
    )
