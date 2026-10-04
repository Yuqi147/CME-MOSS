"""Tests for great-circle cone geometry."""

import numpy as np
import pytest

from cmemoss.physics import cone


def test_cardinal_separations():
    assert cone.angular_separation_deg(0, 0, 0, 0) == pytest.approx(0.0)
    assert cone.angular_separation_deg(0, 0, 180, 0) == pytest.approx(180.0)
    assert cone.angular_separation_deg(0, 0, 0, 90) == pytest.approx(90.0)
    assert float(cone.angular_separation_deg(0, 0, 90, 0)) == pytest.approx(90.0)


def test_latitude_distortion_is_geodesic():
    # A 10-degree longitude step at 80 deg latitude must NOT be 10 degrees in
    # great-circle distance (the legacy Euclidean metric wrongly returned 10).
    sep = float(cone.angular_separation_deg(0, 80, 10, 80))
    assert sep < 2.0  # 10 * cos(80) ~ 1.74 deg


def test_in_cone_boundary_and_tolerance():
    lon = np.array([0.0, 20.0, 45.0, 46.0])
    lat = np.zeros(4)
    mask = cone.in_cone(0, 0, half_width_deg=35, lon_deg=lon, lat_deg=lat,
                        extra_half_width_deg=10)
    assert mask.tolist() == [True, True, True, False]
