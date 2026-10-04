"""Tests for the Parker-spiral ICME wavefront model."""

import numpy as np
import pytest

from cmemoss.constants import AU_KM, R_SUN_KM, SOLAR_ROTATION_RAD_PER_S
from cmemoss.physics import parker, wavefront


# --------------------------------------------------------------------------- #
# Radial evolution (two-branch drag-based model)
# --------------------------------------------------------------------------- #
def test_dbm_fast_cme_decelerates_to_wind():
    t = np.linspace(0.0, 5 * 86_400.0, 500)
    v = wavefront.dbm_speed_km_s(t, 1200.0, 400.0, 0.2e-7)
    assert v[0] == pytest.approx(1200.0)
    assert np.all(np.diff(v) < 0)
    assert 400.0 < v[-1] < 600.0  # relaxed towards the wind on the 5-day span
    # True asymptote: at t -> 1e9 s the speed is within 0.1 km/s of the wind.
    late = float(wavefront.dbm_speed_km_s(1e9, 1200.0, 400.0, 0.2e-7))
    assert 400.0 < late < 401.0


def test_dbm_slow_cme_accelerates_to_wind_without_divergence():
    # v0 < w: the front accelerates toward the wind speed; the classic
    # single-branch formula would diverge, the two-branch version must not.
    t = np.linspace(0.0, 5 * 86_400.0, 500)
    v = wavefront.dbm_speed_km_s(t, 200.0, 400.0, 0.2e-7)
    assert v[0] == pytest.approx(200.0)
    assert np.all(np.diff(v) > 0)
    assert 200.0 < v[-1] < 400.0
    late = float(wavefront.dbm_speed_km_s(1e9, 200.0, 400.0, 0.2e-7))
    assert 399.0 < late < 400.0  # approaches from below, stays bounded
    assert np.all(np.isfinite(v))


def test_dbm_radius_monotone_both_branches():
    t = np.linspace(0.0, 5 * 86_400.0, 500)
    for v0 in (1200.0, 200.0, 400.0):
        r = wavefront.dbm_radius_km(t, v0, 400.0, 0.2e-7, R_SUN_KM)
        assert np.all(np.diff(r) > 0)
        assert r[0] == pytest.approx(R_SUN_KM)
        assert np.all(np.isfinite(r))


def test_front_radius_speed_wrappers():
    t = np.array([0.0, 3600.0])
    # parker_ballistic == constant speed from launch radius.
    r = wavefront.front_radius_km(t, 800.0, "parker_ballistic",
                                  r0_km=R_SUN_KM)
    assert np.allclose(r, R_SUN_KM + 800.0 * t)
    v = wavefront.front_speed_km_s(t, 800.0, "parker_ballistic")
    assert np.allclose(v, 800.0)
    # parker_drag == two-branch DBM.
    r2 = wavefront.front_radius_km(t, 1200.0, "parker_drag",
                                   400.0, 0.2e-7, R_SUN_KM)
    assert np.allclose(r2, wavefront.dbm_radius_km(t, 1200.0, 400.0,
                                                   0.2e-7, R_SUN_KM))
    with pytest.raises(ValueError):
        wavefront.front_radius_km(t, 800.0, "warp")


def test_front_arrival_is_inverse_of_front_radius():
    for model in ("parker_ballistic", "parker_drag"):
        t_arr = wavefront.front_arrival_s(
            AU_KM, 900.0, model, 400.0, 0.2e-7, R_SUN_KM
        )
        r_at = float(
            wavefront.front_radius_km(t_arr, 900.0, model, 400.0, 0.2e-7,
                                      R_SUN_KM)
        )
        assert abs(r_at - AU_KM) / AU_KM < 1e-6


def test_drag_slower_than_ballistic_for_fast_cme():
    t_drag = wavefront.front_arrival_s(AU_KM, 1500.0, "parker_drag",
                                       400.0, 0.2e-7, R_SUN_KM)
    t_ball = wavefront.front_arrival_s(AU_KM, 1500.0, "parker_ballistic",
                                       r0_km=R_SUN_KM)
    assert t_drag > t_ball


# --------------------------------------------------------------------------- #
# Parker-spiral propagation path (axis bending)
# --------------------------------------------------------------------------- #
def test_axis_shift_at_1_au():
    shift = float(wavefront.axis_shift_deg(AU_KM, 400.0, R_SUN_KM))
    assert 55.0 < shift < 70.0  # canonical ~61 deg at 1 AU for 400 km/s
    assert float(wavefront.axis_shift_deg(R_SUN_KM, 400.0, R_SUN_KM)) == 0.0


def test_axis_longitude_consistent_with_parker():
    r = np.array([0.3 * AU_KM, AU_KM])
    lon = wavefront.axis_longitude_deg(r, 33.0, 400.0, R_SUN_KM)
    ref = parker.spiral_longitude_deg(r, 33.0, 400.0, R_SUN_KM)
    assert np.allclose(lon, ref)
    assert lon[0] > lon[1]  # bends to smaller longitude with radius


def test_separation_to_bent_axis_zero_on_axis():
    r = AU_KM
    lon_axis = float(wavefront.axis_longitude_deg(r, 0.0, 400.0, R_SUN_KM))
    sep = wavefront.angular_separation_to_axis_deg(
        np.array([lon_axis]), np.array([0.0]), np.array([r]),
        0.0, 0.0, 400.0, R_SUN_KM,
    )
    assert sep[0] == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# ICME region & sweep primitives
# --------------------------------------------------------------------------- #
def test_in_icme_region_mask_semantics():
    gap = np.array([-1e6, 0.0, 5e6, 2e7, 3e7])
    ang = np.array([True, True, True, True, False])
    mask = wavefront.in_icme_region_mask(gap, ang, half_thickness_km=1.5e7)
    assert mask.tolist() == [False, True, True, False, False]


def test_sweep_crossing_detection():
    gap = np.array([-5e6, -3e6, 2000.0, 2e6, 5e6, -1e6])
    crossings, on_front = wavefront.sweep_crossing_intervals(
        gap, tolerance_km=1000.0
    )
    # Only the outward - -> + crossing between samples 1 and 2 counts.
    assert crossings == [(1, 2)]
    # Sample 2 sits just past the front, outside the tolerance band.
    assert on_front == []


def test_on_front_sample_reported_separately():
    # A sample sitting exactly on the front (within tolerance) is a
    # degenerate sweep site, not an interval crossing.
    gap = np.array([-5e6, -3e6, 500.0, 2e6, 5e6])
    crossings, on_front = wavefront.sweep_crossing_intervals(
        gap, tolerance_km=1000.0
    )
    assert crossings == []
    assert on_front == [2]


def test_no_crossing_when_gap_stays_negative():
    gap = np.array([-5e6, -4e6, -3e6, -2e6])
    crossings, on_front = wavefront.sweep_crossing_intervals(
        gap, tolerance_km=1000.0
    )
    assert crossings == [] and on_front == []


def test_inward_probe_catching_front_is_not_a_sweep():
    # gap goes + -> - (probe passes through the front from behind): the
    # wavefront does not sweep the probe, so no crossing is reported.
    gap = np.array([5e6, 3e6, -3e6, -5e6])
    crossings, on_front = wavefront.sweep_crossing_intervals(
        gap, tolerance_km=1000.0
    )
    assert crossings == [] and on_front == []
