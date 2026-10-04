"""Two-level (memory + disk) cache.

The memory cache removes repeated work inside one run; the disk cache removes
repeated network downloads (DONKI catalog, JPL/Horizons ephemeris) across runs.

Only numpy arrays / JSON-serialisable payloads are stored so the cache is
portable and human-inspectable.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import numpy as np

T = TypeVar("T")


def stable_key(*parts: Any) -> str:
    """Deterministic hash of any JSON-serialisable parts."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class MemoryCache:
    """Small process-local key/value cache."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get_or_set(self, key: str, producer: Callable[[], T]) -> T:
        if key not in self._store:
            self._store[key] = producer()
        return self._store[key]  # type: ignore[no-any-return]

    def clear(self) -> None:
        self._store.clear()


class NpzDiskCache:
    """Disk cache mapping a string key to named numpy arrays + JSON metadata."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.npz"

    def has(self, key: str) -> bool:
        return self._path(key).exists()

    def load(self, key: str) -> Optional[dict[str, Any]]:
        path = self._path(key)
        if not path.exists():
            return None
        with np.load(path, allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files if k != "__meta__"}
            try:
                meta = (json.loads(str(z["__meta__"]))
                        if "__meta__" in z.files else {})
            except (ValueError, json.JSONDecodeError):
                meta = {}
        return {"arrays": arrays, "meta": meta}

    def save(self, key: str, arrays: dict[str, np.ndarray], meta: Optional[dict] = None) -> None:
        tmp = self._path(key).with_suffix(".tmp.npz")
        payload = {k: np.asarray(v) for k, v in arrays.items()}
        if meta is not None:
            payload["__meta__"] = np.asarray(json.dumps(meta, default=str))
        np.savez_compressed(tmp, **payload)
        tmp.replace(self._path(key))

    def get_or_set(
        self,
        key: str,
        producer: Callable[[], tuple[dict[str, np.ndarray], dict]],
    ) -> dict[str, Any]:
        cached = self.load(key)
        if cached is not None:
            return cached
        arrays, meta = producer()
        self.save(key, arrays, meta)
        return {"arrays": arrays, "meta": meta}
