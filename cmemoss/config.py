"""Runtime configuration: cache / output locations and tunable knobs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def default_cache_dir() -> Path:
    """Return the on-disk cache directory (overridable with ``CMEMOSS_CACHE_DIR``)."""
    env = os.environ.get("CMEMOSS_CACHE_DIR")
    if env:
        return Path(env)
    return Path.home() / ".cmemoss"


@dataclass(frozen=True)
class RuntimeConfig:
    """Process-wide settings. Use :data:`CONFIG` unless overriding in tests."""

    cache_dir: Path = None  # type: ignore[assignment]
    http_timeout_s: float = 60.0
    # Horizons / CDAWeb can be slow; tolerate transient failures upstream.
    http_retries: int = 2

    def __post_init__(self) -> None:
        if self.cache_dir is None:
            object.__setattr__(self, "cache_dir", default_cache_dir())
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ephemeris_cache_dir(self) -> Path:
        p = self.cache_dir / "ephemeris"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def donki_cache_dir(self) -> Path:
        p = self.cache_dir / "donki"
        p.mkdir(parents=True, exist_ok=True)
        return p


CONFIG = RuntimeConfig()
