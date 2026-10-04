"""Lightweight in-memory time series used between the in-situ loaders and the
plotting layer, so plotting never depends on pytplot.

Robustness helpers (NaN masking, gap detection, cropping) live here, shared by
every mission loader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np


@dataclass
class TimeSeries:
    """Uniform interface for scalar / vector measurement time series.

    Parameters
    ----------
    name:
        Original tplot variable name (provenance).
    epochs_unix:
        1-D POSIX seconds (UTC).
    values:
        2-D array ``(n_samples, n_components)``; scalars use one column.
    columns:
        Component labels, e.g. ``("Br", "Bt", "Bn")``.
    units:
        Column -> physical unit mapping.
    """

    name: str
    epochs_unix: np.ndarray
    values: np.ndarray
    columns: list[str]
    units: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.epochs_unix = np.asarray(self.epochs_unix, dtype=float).reshape(-1)
        self.values = np.atleast_2d(np.asarray(self.values, dtype=float))
        if self.values.shape[0] != self.epochs_unix.size:
            # pytplot stores vector data as (N, C); guard against transposition.
            if self.values.shape[1] == self.epochs_unix.size:
                self.values = self.values.T
        if self.values.shape[1] != len(self.columns):
            raise ValueError(
                f"{self.name}: {self.values.shape[1]} components but "
                f"{len(self.columns)} labels {self.columns}"
            )

    # ------------------------------------------------------------------ #
    @classmethod
    def from_pytplot_result(cls, result, name: str, columns: Sequence[str],
                            unit: str = "") -> "TimeSeries":
        """Adapt a ``pytplot.get_data`` result without importing pytplot."""
        units = {c: unit for c in columns}
        return cls(name=name, epochs_unix=result.times, values=result.y,
                   columns=list(columns), units=units)

    @property
    def n_samples(self) -> int:
        return self.epochs_unix.size

    def as_datetime64(self) -> np.ndarray:
        ns = (self.epochs_unix * 1e9).astype("timedelta64[ns]")
        return np.datetime64("1970-01-01T00:00:00", "ns") + ns

    def crop(self, t0_unix: float, t1_unix: float) -> "TimeSeries":
        mask = (self.epochs_unix >= t0_unix) & (self.epochs_unix <= t1_unix)
        return TimeSeries(self.name, self.epochs_unix[mask], self.values[mask],
                          list(self.columns), dict(self.units))

    def finite_mask(self) -> np.ndarray:
        """Rows with at least one non-NaN component."""
        return np.isfinite(self.values).any(axis=1)

    def with_magnitude(self, vector_columns: Sequence[str], mag_label: str,
                       unit: str = "") -> "TimeSeries":
        """Append the vector magnitude as a final column if present."""
        idx = [self.columns.index(c) for c in vector_columns if c in self.columns]
        if len(idx) < 2:
            return self
        mag = np.linalg.norm(self.values[:, idx], axis=1, keepdims=True)
        return TimeSeries(
            self.name,
            self.epochs_unix,
            np.hstack([self.values, mag]),
            self.columns + [mag_label],
            {**self.units, mag_label: unit or next(iter(self.units.values()), "")},
        )

    def gaps(self, min_gap_s: float) -> list[tuple[float, float]]:
        """Return ``(t_start, t_end)`` gaps longer than *min_gap_s*."""
        if self.epochs_unix.size < 2:
            return []
        dt = np.diff(self.epochs_unix)
        big = np.where(dt > min_gap_s)[0]
        return [(float(self.epochs_unix[i]), float(self.epochs_unix[i + 1]))
                for i in big]
