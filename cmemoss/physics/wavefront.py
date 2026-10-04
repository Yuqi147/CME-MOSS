"""Parker-spiral ICME wavefront model.

This is the physics behind the *strict* encounter determination. It replaces
the old static "cone + radial shell at one instant" test with a genuinely
dynamic picture:

* **Radial front evolution** - the ICME front propagates outward with a
  physically-motivated speed law. By default the drag-based model (DBM) of
  Vrsnak et al. (2013, Solar Phys. 285, 295) is used, in which aerodynamic
  drag against the ambient solar wind makes the front relax toward the wind
  speed ``w`` (velocity evolution / deceleration). A constant-speed
  (ballistic) branch is provided for comparison. Unlike
  :mod:`cmemoss.physics.propagation`, the DBM branch here is defined for
  **both** ``v0 > w`` (deceleration) and ``v0 < w`` (acceleration toward the
  wind), so slow ICMEs embedded in a fast wind do not blow up.

* **Parker-spiral propagation path** - the front axis is not held at a fixed
  inertial longitude. Because the ICME is embedded in the corotating
  background flow, its effective longitudinal position bends with
  heliocentric distance along the Parker spiral (Parker 1958)::

      lon_axis(r) = lon_source - Omega * (r - r0) / v_sw

  This is exactly the footpoint / connectivity mapping implemented in
  :mod:`cmemoss.physics.parker`; here it is applied to the ICME front itself
  so that the encounter geometry follows the background-flow geometry.

* **Finite ICME region** - the ICME occupies a spherical cap: angular
  half-width (DONKI cone half-angle + tolerance) around the bent axis and a
  radial half-thickness ``H`` behind the front. A probe is "inside the ICME"
  only when the front has already swept past it (radial gap in
  ``[0, H]``) *and* it sits inside the angular cap.

* **Wavefront sweep** - the front *sweeps across* a probe when the front
  radius crosses the probe's heliocentric distance from inside to outside
  (``gap = r_front - r_probe`` changes from negative to positive) within a
  tolerance, with the front genuinely propagating (``v_front > 0``). This is
  the event that separates a confirmed encounter from mere geometric
  proximity or orbit intersection.

All units: km, seconds, km/s, degrees; ``gamma`` in 1/km.
"""

from __future__ import annotations

import numpy as np

from cmemoss.constants import (
    AU_KM,
    R_SUN_KM,
    SOLAR_ROTATION_RAD_PER_S,
)
from cmemoss.physics import parker

__all__ = [
    "dbm_speed_km_s",
    "dbm_radius_km",
    "front_radius_km",
    "front_speed_km_s",
    "front_arrival_s",
    "axis_shift_deg",
    "axis_longitude_deg",
    "angular_separation_to_axis_deg",
    "gap_km",
    "in_angular_cone_mask",
    "in_icme_region_mask",
    "sweep_crossing_intervals",
]

# --------------------------------------------------------------------------- #
# Radial evolution: two-branch drag-based model + ballistic
# --------------------------------------------------------------------------- #
def dbm_speed_km_s(
    t_s: np.ndarray,
    v0_km_s: float,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
) -> np.ndarray:
    """Instantaneous front speed under the two-branch drag-based model.

    ``dv = v0 - w``.  For ``dv > 0`` (fast CME) the front decelerates toward
    ``w``; for ``dv < 0`` (slow CME in a fast wind) it accelerates toward
    ``w`` from below.  Both branches are asymptotically regular for all
    ``t >= 0``.
    """
    t = np.asarray(t_s, dtype=float)
    dv = v0_km_s - w_km_s
    if dv > 0.0:
        denom = 1.0 + gamma_per_km * dv * t
        return w_km_s + dv / np.maximum(denom, 1e-300)
    if dv < 0.0:
        a = -dv  # w - v0 > 0
        denom = 1.0 + gamma_per_km * a * t
        return w_km_s - a / np.maximum(denom, 1e-300)
    return np.full_like(t, w_km_s)


def dbm_radius_km(
    t_s: np.ndarray,
    v0_km_s: float,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = R_SUN_KM,
) -> np.ndarray:
    """Heliocentric front distance under the two-branch drag-based model.

    Integrates :func:`dbm_speed_km_s` from ``r0``::

        dv > 0:  r(t) = r0 + w t + ln(1 + gamma dv t) / gamma
        dv < 0:  r(t) = r0 + w t - ln(1 + gamma a t) / gamma,  a = w - v0
    """
    t = np.asarray(t_s, dtype=float)
    dv = v0_km_s - w_km_s
    if dv > 0.0:
        denom = 1.0 + gamma_per_km * dv * t
        log_term = np.log(np.maximum(denom, 1e-300)) / gamma_per_km
        return r0_km + w_km_s * t + log_term
    if dv < 0.0:
        a = -dv
        denom = 1.0 + gamma_per_km * a * t
        log_term = np.log(np.maximum(denom, 1e-300)) / gamma_per_km
        return r0_km + w_km_s * t - log_term
    return r0_km + w_km_s * t


def front_radius_km(
    t_s: np.ndarray,
    v0_km_s: float,
    model: str = "parker_drag",
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = R_SUN_KM,
) -> np.ndarray:
    """Front heliocentric radius at time ``t`` for the selected radial model.

    ``model`` accepts the radial part of any supported propagation model:
    ``"parker_drag"`` / ``"drag"`` -> DBM; ``"parker_ballistic"`` /
    ``"ballistic"`` -> constant speed from ``r0``.
    """
    t = np.asarray(t_s, dtype=float)
    if model in ("parker_drag", "drag"):
        return dbm_radius_km(t, v0_km_s, w_km_s, gamma_per_km, r0_km)
    if model in ("parker_ballistic", "ballistic"):
        return r0_km + v0_km_s * t
    raise ValueError(f"unknown propagation model: {model!r}")


def front_speed_km_s(
    t_s: np.ndarray,
    v0_km_s: float,
    model: str = "parker_drag",
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
) -> np.ndarray:
    """Front propagation speed ``d r_front / dt`` at time ``t``."""
    t = np.asarray(t_s, dtype=float)
    if model in ("parker_drag", "drag"):
        return dbm_speed_km_s(t, v0_km_s, w_km_s, gamma_per_km)
    if model in ("parker_ballistic", "ballistic"):
        return np.full_like(t, v0_km_s)
    raise ValueError(f"unknown propagation model: {model!r}")


def front_arrival_s(
    r_target_km: float,
    v0_km_s: float,
    model: str = "parker_drag",
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = R_SUN_KM,
) -> float:
    """Time at which the front reaches ``r_target`` (scalar bisection)."""
    if r_target_km < r0_km:
        raise ValueError("target radius is inside the launch radius")
    if r_target_km == r0_km:
        return 0.0
    if model in ("parker_ballistic", "ballistic"):
        if v0_km_s <= 0:
            raise ValueError("speed must be positive")
        return (r_target_km - r0_km) / v0_km_s

    def radius(t: float) -> float:
        return float(front_radius_km(t, v0_km_s, model, w_km_s, gamma_per_km,
                                     r0_km))

    # Seed the bracket with the ballistic time, then double until covered.
    lo = 0.0
    hi = max(2.0 * (r_target_km - r0_km) / max(v0_km_s, 1e-9), 1.0)
    for _ in range(100):
        if radius(hi) >= r_target_km:
            break
        hi *= 2.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if radius(mid) < r_target_km:
            lo = mid
        else:
            hi = mid
        if (hi - lo) < 1e-9 * max(hi, 1.0):
            break
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- #
# Parker-spiral propagation path (front-axis bending)
# --------------------------------------------------------------------------- #
def axis_shift_deg(
    r_km: np.ndarray,
    v_sw_km_s: float = 400.0,
    r0_km: float = R_SUN_KM,
    omega_rad_s: float = SOLAR_ROTATION_RAD_PER_S,
) -> np.ndarray:
    """Magnitude of the longitudinal Parker bending at radius ``r``."""
    return np.abs(
        np.degrees(omega_rad_s * (np.asarray(r_km, dtype=float) - r0_km)
                   / v_sw_km_s)
    )


def axis_longitude_deg(
    r_km: np.ndarray,
    lon_source_deg: float,
    v_sw_km_s: float = 400.0,
    r0_km: float = R_SUN_KM,
    omega_rad_s: float = SOLAR_ROTATION_RAD_PER_S,
) -> np.ndarray:
    """Longitude of the ICME front axis at heliocentric radius ``r``.

    Follows the background-streamline (Parker spiral) geometry; delegates to
    :func:`cmemoss.physics.parker.spiral_longitude_deg`.
    """
    return parker.spiral_longitude_deg(
        r_km, lon_source_deg, v_sw_km_s, r0_km, omega_rad_s
    )


def angular_separation_to_axis_deg(
    lon_probe_deg: np.ndarray,
    lat_probe_deg: np.ndarray,
    r_probe_km: np.ndarray,
    lon_source_deg: float,
    lat_source_deg: float,
    v_sw_km_s: float = 400.0,
    r0_km: float = R_SUN_KM,
    omega_rad_s: float = SOLAR_ROTATION_RAD_PER_S,
) -> np.ndarray:
    """Great-circle angle between the probe and the *bent* front axis.

    The axis point is evaluated at the probe's own heliocentric radius, i.e.
    the front surface element at the same distance from the Sun as the probe.
    """
    from cmemoss.physics.cone import angular_separation_deg

    lon_axis = axis_longitude_deg(
        r_probe_km, lon_source_deg, v_sw_km_s, r0_km, omega_rad_s
    )
    lat_axis = np.full_like(np.asarray(lon_axis, dtype=float), lat_source_deg)
    return angular_separation_deg(
        lon_axis, lat_axis, np.asarray(lon_probe_deg, dtype=float),
        np.asarray(lat_probe_deg, dtype=float),
    )


def in_angular_cone_mask(
    lon_probe_deg: np.ndarray,
    lat_probe_deg: np.ndarray,
    r_probe_km: np.ndarray,
    lon_source_deg: float,
    lat_source_deg: float,
    half_width_deg: float,
    extra_half_width_deg: float = 0.0,
    v_sw_km_s: float = 400.0,
    r0_km: float = R_SUN_KM,
) -> np.ndarray:
    """Probe inside the ICME angular cap around the bent Parker axis."""
    sep = angular_separation_to_axis_deg(
        lon_probe_deg, lat_probe_deg, r_probe_km,
        lon_source_deg, lat_source_deg, v_sw_km_s, r0_km,
    )
    return sep <= (half_width_deg + extra_half_width_deg)


# --------------------------------------------------------------------------- #
# ICME spatial region & wavefront sweep
# --------------------------------------------------------------------------- #
def gap_km(r_front_km: np.ndarray, r_probe_km: np.ndarray) -> np.ndarray:
    """Radial gap ``r_front - r_probe`` (positive = probe behind the front)."""
    return np.asarray(r_front_km, dtype=float) - np.asarray(r_probe_km,
                                                            dtype=float)


def in_icme_region_mask(
    gap: np.ndarray,
    angular_ok: np.ndarray,
    half_thickness_km: float,
) -> np.ndarray:
    """Probe inside the ICME region: behind the front by at most ``H`` km
    (``0 <= gap <= H``) *and* inside the angular cap."""
    return (gap >= 0.0) & (gap <= half_thickness_km) & angular_ok


def sweep_crossing_intervals(
    gap: np.ndarray,
    tolerance_km: float = 1000.0,
) -> tuple[list[tuple[int, int]], list[int]]:
    """Sample intervals where the outward-moving front sweeps the probe.

    A sweep happens when the radial gap crosses from ``< -tol`` to ``> +tol``
    between consecutive samples ``(i-1, i)`` (the front passes from inside the
    probe's orbit to outside it).  Samples that sit on the front itself
    (``|gap| <= tol``) are reported separately as degenerate on-front sites.

    Returns ``(crossings, on_front)`` where ``crossings`` is a list of
    ``(i_start, i_end)`` candidate intervals and ``on_front`` a list of
    sample indices; the caller refines the exact crossing time between the
    bounding samples.
    """
    gap = np.asarray(gap, dtype=float)
    crossings: list[tuple[int, int]] = []
    on_front: list[int] = []
    n = gap.size
    for i in range(1, n):
        if gap[i - 1] < -tolerance_km and gap[i] > tolerance_km:
            crossings.append((i - 1, i))
    for i in range(n):
        if abs(gap[i]) <= tolerance_km:
            on_front.append(i)
    return crossings, on_front
