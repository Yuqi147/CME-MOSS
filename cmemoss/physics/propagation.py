"""CME radial propagation and the radial-shell encounter test.

Two models are provided and must not be conflated:

* **ballistic** - constant radial speed ``v0``; exactly the model used by the
  legacy code, kept as the default so historical results are reproducible.
* **drag** - the analytical drag-based model (DBM) of Vrsnak et al. (2013,
  Solar Phys. 285, 295), in which the CME asymptotically relaxes to the
  ambient solar-wind speed ``w`` with aerodynamic drag parameter ``gamma``::

      v(t) = w + (v0 - w) / (1 + gamma (v0 - w) t)
      r(t) = r0 + w t + ln(1 + gamma (v0 - w) t) / gamma

These describe the ICME/CME *transient*. The background Parker spiral lives in
:mod:`cmemoss.physics.parker` and is intentionally separate.

Units throughout: km, seconds, km/s (gamma in 1/km).
"""

from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------- #
# Ballistic model (legacy)
# --------------------------------------------------------------------------- #
def ballistic_radius_km(speed_km_s: float, t_s: np.ndarray) -> np.ndarray:
    return speed_km_s * t_s


def ballistic_arrival_s(r_km: float, speed_km_s: float) -> float:
    if speed_km_s <= 0:
        raise ValueError("speed must be positive")
    return r_km / speed_km_s


def shell_limits_ballistic(
    t_s: np.ndarray,
    speed_km_s: float,
    speed_tolerance_km_s: float,
    min_shell_speed_km_s: float = 400.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Inner/outer radial shell, reproducing the legacy inequality::

        min(v - dv, floor) * dt  <=  r  <=  (v + dv) * dt

    Note the empirical legacy semantics: the inner-edge speed is **capped** at
    ``min_shell_speed_km_s`` (400 km/s), not floored there. For any CME faster
    than ``dv + 400`` the inner edge stays at 400 km/s, so the shell widens
    with time. This behaviour is preserved exactly for reproducibility.
    """
    inner_speed = np.minimum(speed_km_s - speed_tolerance_km_s,
                             min_shell_speed_km_s)
    return inner_speed * t_s, (speed_km_s + speed_tolerance_km_s) * t_s


# --------------------------------------------------------------------------- #
# Drag-based model (Vrsnak et al. 2013)
# --------------------------------------------------------------------------- #
def drag_speed_km_s(
    t_s: np.ndarray,
    v0_km_s: float,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
) -> np.ndarray:
    """Instantaneous CME speed under the drag-based model.

    Negative times (pre-launch samples) return +inf so they fall outside any
    encounter shell, rather than producing a divide-by-zero warning.
    """
    t = np.asarray(t_s, dtype=float)
    denom = 1.0 + gamma_per_km * (v0_km_s - w_km_s) * t
    return w_km_s + np.where(
        denom > 0.0, (v0_km_s - w_km_s) / np.maximum(denom, 1e-300), np.inf
    )


def drag_radius_km(
    t_s: np.ndarray,
    v0_km_s: float,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = 0.0,
) -> np.ndarray:
    """Heliocentric CME distance under the drag-based model."""
    dv0 = v0_km_s - w_km_s
    t = np.asarray(t_s, dtype=float)
    denom = 1.0 + gamma_per_km * dv0 * t
    log_term = np.where(denom > 0.0,
                        np.log(np.maximum(denom, 1e-300)) / gamma_per_km,
                        -np.inf)
    return r0_km + w_km_s * t + log_term


def drag_arrival_s(
    r_target_km: float,
    v0_km_s: float,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = 0.0,
) -> float:
    """Time for the DBM front to reach ``r_target`` (scalar bisection)."""
    if r_target_km < r0_km:
        raise ValueError("target radius is inside the launch radius")
    if r_target_km == r0_km:
        return 0.0
    if v0_km_s <= w_km_s:
        raise ValueError("drag model requires v0 > ambient wind speed w")

    def radius(t: float) -> float:
        return float(drag_radius_km(t, v0_km_s, w_km_s, gamma_per_km, r0_km))

    hi = max(2.0 * r_target_km / v0_km_s, 1.0)
    while radius(hi) < r_target_km:
        hi *= 2.0
    lo = 0.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if radius(mid) < r_target_km:
            lo = mid
        else:
            hi = mid
        if (hi - lo) < 1e-10 * max(hi, 1.0):
            break
    return 0.5 * (lo + hi)


def shell_limits_drag(
    t_s: np.ndarray,
    speed_km_s: float,
    speed_tolerance_km_s: float,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Radial uncertainty band around the DBM front, ``r_drag +/- dv*t``."""
    center = drag_radius_km(t_s, speed_km_s, w_km_s, gamma_per_km, r0_km)
    half_width = speed_tolerance_km_s * t_s
    return center - half_width, center + half_width


# --------------------------------------------------------------------------- #
# Unified interface used by the analysis layer
# --------------------------------------------------------------------------- #
def shell_limits(
    t_s: np.ndarray,
    speed_km_s: float,
    speed_tolerance_km_s: float,
    model: str = "ballistic",
    min_shell_speed_km_s: float = 400.0,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(r_inner, r_outer)`` for the selected propagation model."""
    if model == "ballistic":
        return shell_limits_ballistic(
            t_s, speed_km_s, speed_tolerance_km_s, min_shell_speed_km_s
        )
    if model == "drag":
        return shell_limits_drag(
            t_s, speed_km_s, speed_tolerance_km_s, w_km_s, gamma_per_km, r0_km
        )
    raise ValueError(f"unknown propagation model: {model!r}")


def in_radial_shell(
    r_km: np.ndarray,
    t_s: np.ndarray,
    speed_km_s: float,
    speed_tolerance_km_s: float,
    model: str = "ballistic",
    min_shell_speed_km_s: float = 400.0,
    w_km_s: float = 400.0,
    gamma_per_km: float = 0.2e-7,
    r0_km: float = 0.0,
) -> np.ndarray:
    """Boolean mask of samples lying within the propagating radial shell."""
    inner, outer = shell_limits(
        t_s, speed_km_s, speed_tolerance_km_s, model, min_shell_speed_km_s,
        w_km_s, gamma_per_km, r0_km,
    )
    return (r_km >= inner) & (r_km <= outer)
