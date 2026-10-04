"""Tests for ballistic and drag-based CME propagation."""

import numpy as np
import pytest

from cmemoss.constants import AU_KM
from cmemoss.physics import propagation


def test_ballistic_basics():
    assert propagation.ballistic_radius_km(800, 10.0) == 8000.0
    assert propagation.ballistic_arrival_s(AU_KM, 800) == pytest.approx(
        AU_KM / 800.0)


def test_shell_limits_legacy_cap():
    t = np.array([100.0])
    # Legacy rule: inner speed is min(v-dv, 400) - a CAP at 400 km/s.
    # v=800 -> min(700,400)=400
    inner, outer = propagation.shell_limits_ballistic(t, 800, 100, 400)
    assert inner[0] == 40_000.0 and outer[0] == 90_000.0
    # v=300 -> min(200,400)=200
    inner, _ = propagation.shell_limits_ballistic(t, 300, 100, 400)
    assert inner[0] == 20_000.0


def test_drag_speed_limits():
    assert propagation.drag_speed_km_s(0.0, 1200, 400, 0.2e-7) == 1200.0
    late = propagation.drag_speed_km_s(1e9, 1200, 400, 0.2e-7)
    assert late > 400.0 and late < 401.0  # asymptotes to ambient wind


def test_drag_radius_monotone_and_arrival_consistent():
    t = np.linspace(0, 5 * 86_400.0, 500)
    r = propagation.drag_radius_km(t, 1200, 400, 0.2e-7)
    assert np.all(np.diff(r) > 0)

    t_arr = propagation.drag_arrival_s(AU_KM, 1200, 400, 0.2e-7)
    r_at = propagation.drag_radius_km(t_arr, 1200, 400, 0.2e-7)
    assert abs(r_at - AU_KM) / AU_KM < 1e-6


def test_drag_slower_than_ballistic_for_fast_cme():
    t_drag = propagation.drag_arrival_s(AU_KM, 1500, 400, 0.2e-7)
    t_ball = propagation.ballistic_arrival_s(AU_KM, 1500)
    assert t_drag > t_ball


def test_in_radial_shell():
    # Spacecraft at 1 AU; 800 km/s with +/-100 km/s tolerance. Legacy cap
    # fixes the inner edge at 400 km/s, so the encounter window is
    # AU/900 ~ 46.2 h  <=  t  <=  AU/400 ~ 103.9 h.
    dt = np.array([0.0, 46.0, 52.0, 60.0, 104.0]) * 3600.0
    r = np.full_like(dt, AU_KM)
    mask = propagation.in_radial_shell(r, dt, 800, 100, "ballistic", 400)
    assert mask.tolist() == [False, False, True, True, False]
