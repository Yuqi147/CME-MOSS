"""Background solar-wind Parker spiral (Parker 1958, ApJ 128, 664).

Scope - read carefully
----------------------
These functions describe the **steady background solar wind** magnetic-field
geometry under the standard assumptions:

* radial, constant-speed wind ``v_sw``;
* field frozen into the flow (ideal MHD);
* Sun rotating rigidly at the Carrington sidereal rate ``Omega``;
* field line starting at radius ``r0`` (often the source surface, 2.5 R_s).

They provide magnetic connectivity / spiral-angle information. They do **not**
model ICME/CME transients or arrival times - see
:mod:`cmemoss.physics.propagation` for that.

Sign convention
---------------
Heliographic longitudes increase westward in the direction of solar rotation.
A plasma parcel emitted at travel time ``tau = (r - r0) / v_sw`` in the past
sits east of the present-day footpoint, so::

    lon(r) = lon_foot - Omega * (r - r0) / v_sw      [inertial longitude]

``footpoint_longitude`` is the inverse mapping (spacecraft -> footpoint).
"""

from __future__ import annotations

import numpy as np

from cmemoss.constants import (
    AU_KM,
    CARRINGTON_SIDEREAL_PERIOD_S,
    R_SUN_KM,
    SOLAR_ROTATION_RAD_PER_S,
)

__all__ = [
    "travel_time_s",
    "spiral_longitude_deg",
    "footpoint_longitude_deg",
    "parker_angle_deg",
    "spiral_curve",
]


def travel_time_s(r_km: np.ndarray, v_sw_km_s: float,
                  r0_km: float = R_SUN_KM) -> np.ndarray:
    """Ballistic wind travel time from ``r0`` to ``r`` (seconds)."""
    if v_sw_km_s <= 0:
        raise ValueError("solar-wind speed must be positive")
    return (np.asarray(r_km, dtype=float) - r0_km) / v_sw_km_s


def spiral_longitude_deg(
    r_km: np.ndarray,
    footpoint_lon_deg: float,
    v_sw_km_s: float,
    r0_km: float = R_SUN_KM,
    omega_rad_s: float = SOLAR_ROTATION_RAD_PER_S,
) -> np.ndarray:
    """Inertial longitude of the field line at radius ``r``."""
    tau = travel_time_s(r_km, v_sw_km_s, r0_km)
    return footpoint_lon_deg - np.degrees(omega_rad_s * tau)


def footpoint_longitude_deg(
    spacecraft_lon_deg: np.ndarray,
    spacecraft_r_km: np.ndarray,
    v_sw_km_s: float,
    r0_km: float = R_SUN_KM,
    omega_rad_s: float = SOLAR_ROTATION_RAD_PER_S,
) -> np.ndarray:
    """Source-surface footpoint longitude magnetically connected to a body.

    Inverse of :func:`spiral_longitude_deg` (ballistic back-mapping).
    """
    tau = travel_time_s(spacecraft_r_km, v_sw_km_s, r0_km)
    return spacecraft_lon_deg + np.degrees(omega_rad_s * tau)


def parker_angle_deg(
    r_km: np.ndarray,
    v_sw_km_s: float,
    lat_deg: float = 0.0,
    r0_km: float = R_SUN_KM,
    omega_rad_s: float = SOLAR_ROTATION_RAD_PER_S,
) -> np.ndarray:
    """Angle between the background field and the radial direction.

    ``tan(psi) = Omega (r - r0) cos(lat) / v_sw`` (the ``cos(lat)`` is
    ``sin(theta)`` with colatitude ``theta``). Equator default.
    """
    tau = travel_time_s(r_km, v_sw_km_s, r0_km)
    return np.degrees(
        np.arctan(omega_rad_s * tau * np.cos(np.radians(lat_deg)))
    )


def spiral_curve(
    footpoint_lon_deg: float,
    v_sw_km_s: float,
    r_max_km: float = AU_KM,
    n: int = 400,
    r0_km: float = R_SUN_KM,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample a spiral field line ``(lon_deg, r_km)`` for polar plotting."""
    r = np.linspace(r0_km, r_max_km, n)
    lon = spiral_longitude_deg(r, footpoint_lon_deg, v_sw_km_s, r0_km)
    return lon, r
