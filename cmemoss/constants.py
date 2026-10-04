"""Physical constants in SI base units.

The physics layer is intentionally pure-numpy and works with plain SI floats
(seconds, km, km/s, degrees/radians); the astropy ``Quantity`` wrappers live in
the data / application layers. Keeping constants here (rather than scattered
magic numbers) is what makes calculations auditable and reproducible.

References
----------
Parker, E. N. (1958), ApJ 128, 664.
Vrsnak, B. et al. (2013), Solar Phys. 285, 295 (drag-based model).
"""

from __future__ import annotations

import math

# --- Lengths (km) ---------------------------------------------------------
R_SUN_KM: float = 6.957e5          # IAU nominal solar radius
AU_KM: float = 1.495978707e8       # astronomical unit in km

# --- Solar rotation -------------------------------------------------------
# Carrington sidereal rotation period (25.38 days) -> angular velocity.
# The inertial Heliographic Stonyhurst longitudes used for cone geometry do
# NOT rotate with the Sun, so the sidereal (not synodic) rate is the correct
# one for Parker-spiral mapping.
CARRINGTON_SIDEREAL_PERIOD_S: float = 25.38 * 86_400.0
SOLAR_ROTATION_RAD_PER_S: float = 2.0 * math.pi / CARRINGTON_SIDEREAL_PERIOD_S  # ~2.865e-6

# --- Default analysis parameters (legacy-compatible) ----------------------
DEFAULT_SPEED_TOLERANCE_KM_S: float = 100.0
# Legacy cone test used ``min(v - dv, 400)`` as the inner shell speed.
DEFAULT_MIN_SHELL_SPEED_KM_S: float = 400.0
# Legacy cone test silently widened the DONKI half-angle by 10 degrees.
DEFAULT_ANGLE_TOLERANCE_DEG: float = 10.0
DEFAULT_PROPAGATION_WINDOW_DAYS: float = 9.0

# Typical background solar-wind speeds used when no in-situ measurement of the
# upstream wind is available.
PARKER_DEFAULT_WIND_SPEEDS_KM_S: tuple[float, ...] = (300.0, 400.0, 500.0)
