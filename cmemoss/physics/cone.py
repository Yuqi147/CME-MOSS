"""Cone angular geometry.

The legacy code put a single CME point into a ``scipy.spatial.KDTree`` and
measured plain Euclidean distance in (longitude, latitude) degrees. With one
point the tree provides no benefit, and an unweighted lon-lat distance
distorts badly away from the equator. Both issues are replaced here by the
true great-circle angular separation, fully vectorised.

All angles are degrees; inputs broadcast against each other.
"""

from __future__ import annotations

import numpy as np


def angular_separation_deg(
    lon1: np.ndarray,
    lat1: np.ndarray,
    lon2: np.ndarray,
    lat2: np.ndarray,
) -> np.ndarray:
    """Great-circle central angle via the haversine formula."""
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    hav = (
        np.sin((lat2 - lat1) / 2.0) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2.0) ** 2
    )
    hav = np.clip(hav, 0.0, 1.0)
    return np.degrees(2.0 * np.arcsin(np.sqrt(hav)))


def in_cone(
    axis_lon_deg: float,
    axis_lat_deg: float,
    half_width_deg: float,
    lon_deg: np.ndarray,
    lat_deg: np.ndarray,
    extra_half_width_deg: float = 0.0,
) -> np.ndarray:
    """Boolean mask of points whose angle to the cone axis is within the width.

    ``half_width_deg`` is the DONKI cone half-angle; ``extra_half_width_deg``
    reproduces the legacy fixed +10 degree observational tolerance.
    """
    limit = half_width_deg + extra_half_width_deg
    sep = angular_separation_deg(
        axis_lon_deg, axis_lat_deg, lon_deg, lat_deg
    )
    return sep <= limit
