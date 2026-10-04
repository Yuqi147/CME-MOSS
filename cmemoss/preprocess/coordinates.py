"""Vectorised ephemeris data structure and coordinate helpers.

:class:`EphemerisPoints` stores a sampled body trajectory in Heliographic
Stonyhurst (HGS) coordinates - a heliocentric, approximately inertial frame
whose longitude zero points along the Sun-Earth line. DONKI source-region
longitudes and spacecraft positions are directly comparable in this frame
(no co-rotating offset is applied), which is the correct frame for radially
propagating a CME launched at a fixed inertial direction.

All arrays are plain numpy; sunpy/astropy are touched only at the SkyCoord
boundary (``from_skycoord``), replacing the legacy per-element Python loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

FRAME_NAME = "HeliographicStonyhurst"


@dataclass
class EphemerisPoints:
    """Sampled trajectory of one body in HGS coordinates.

    Attributes
    ----------
    body_key:
        Registry key of the body.
    obstime:
        ``astropy.time.Time`` array aligned with the positional arrays.
    lon_deg, lat_deg:
        HGS longitude / latitude in degrees.
    r_km:
        Heliocentric distance in km.
    cadence:
        Requested sampling step (informational).
    """

    body_key: str
    obstime: Any
    lon_deg: np.ndarray
    lat_deg: np.ndarray
    r_km: np.ndarray
    cadence: str = ""

    def __len__(self) -> int:
        return len(self.r_km)

    @property
    def unix(self) -> np.ndarray:
        return np.asarray(self.obstime.unix, dtype=float)

    def time_mask(self, t0_unix: float, t1_unix: float) -> np.ndarray:
        t = self.unix
        return (t >= t0_unix) & (t <= t1_unix)


def from_skycoord(coord: Any, body_key: str, cadence: str = "") -> EphemerisPoints:
    """Build an :class:`EphemerisPoints` from a sunpy SkyCoord array.

    ``SkyCoord.lon`` / ``.lat`` / ``.radius`` are array quantities, so the
    legacy list comprehensions over every coordinate collapse to three
    vectorised conversions.
    """
    import astropy.units as u

    return EphemerisPoints(
        body_key=body_key,
        obstime=coord.obstime,
        lon_deg=np.asarray(coord.lon.to_value(u.deg), dtype=float),
        lat_deg=np.asarray(coord.lat.to_value(u.deg), dtype=float),
        r_km=np.asarray(coord.radius.to_value(u.km), dtype=float),
        cadence=cadence,
    )


def unit_vectors(lon_deg: np.ndarray, lat_deg: np.ndarray) -> np.ndarray:
    """HGS spherical -> Cartesian unit vectors (heliocentric, inertial).

    ``x`` points along the Sun-Earth line (lon=0); returns shape ``(..., 3)``.
    """
    lon = np.radians(lon_deg)
    lat = np.radians(lat_deg)
    clat = np.cos(lat)
    return np.stack(
        (clat * np.cos(lon), clat * np.sin(lon), np.sin(lat)), axis=-1
    )
