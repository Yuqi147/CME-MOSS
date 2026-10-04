"""Tests for the background-wind Parker spiral geometry."""

import numpy as np
import pytest

from cmemoss.constants import AU_KM, R_SUN_KM
from cmemoss.physics import parker


def test_travel_time_basic():
    # One second at 400 km/s travels exactly 400 km.
    assert parker.travel_time_s(R_SUN_KM + 400.0, 400.0) == pytest.approx(1.0)


def test_spiral_longitude_decreases_outward():
    r = np.array([R_SUN_KM, 0.5 * AU_KM, AU_KM])
    lon = parker.spiral_longitude_deg(r, footpoint_lon_deg=0.0,
                                      v_sw_km_s=400.0)
    assert lon[0] == 0.0
    assert lon[1] > lon[2]  # bends eastward (smaller longitude) with radius
    assert lon[2] < -50.0   # ~ -61 deg at 1 AU for 400 km/s


def test_faster_wind_tighter_spiral():
    slow = parker.spiral_longitude_deg(AU_KM, 0.0, 300.0)
    fast = parker.spiral_longitude_deg(AU_KM, 0.0, 700.0)
    assert abs(fast) < abs(slow)


def test_footpoint_is_inverse_of_spiral():
    lon_sc = parker.spiral_longitude_deg(AU_KM, 33.0, 400.0)
    foot = parker.footpoint_longitude_deg(lon_sc, AU_KM, 400.0)
    assert abs(float(foot) - 33.0) < 1e-9


def test_parker_angle_known_values():
    assert float(parker.parker_angle_deg(R_SUN_KM, 400.0)) == 0.0
    angle = float(parker.parker_angle_deg(AU_KM, 400.0))
    assert 44.0 < angle < 50.0  # canonical ~45-47 deg at 1 AU
    # Field more radial at high latitude.
    assert (parker.parker_angle_deg(AU_KM, 400.0, lat_deg=60.0)
            < parker.parker_angle_deg(AU_KM, 400.0, lat_deg=0.0))
