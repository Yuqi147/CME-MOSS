"""Strict Parker-wavefront encounter pipeline tests (no network).

Synthetic hour-sampled stationary/moving probes exercise
:func:`evaluate_wavefront_encounter` - the pure-numpy core of the new
dynamic encounter determination - plus one orchestrator test with fakes.

The verified semantics are exactly the strict definition:

* geometry/cone intersection alone            -> NOT an encounter
* approaching the ICME (no sweep)             -> NOT an encounter
* inside the ICME region without a sweep      -> NOT an encounter
* wavefront sweeps probe + probe stays in
  the ICME region after the sweep             -> confirmed encounter
"""

import numpy as np
import pytest

from cmemoss.analysis.encounter import EncounterSearch, evaluate_wavefront_encounter
from cmemoss.constants import AU_KM, R_SUN_KM
from cmemoss.domain import CMEEvent, SearchParameters
from cmemoss.physics import wavefront
from cmemoss.preprocess.coordinates import EphemerisPoints

T0 = 1_577_836_800.0  # 2020-01-01T00:00:00 UTC
HOUR = 3600.0
DAY = 86_400.0

# CME event geometry used by most tests: source on the Sun-Earth line.
EVENT = dict(
    lon_source_deg=0.0, lat_source_deg=0.0, half_width_deg=30.0,
    speed_km_s=800.0,
)


def _params(**overrides):
    base = dict(
        start_date="2020-01-01", end_date="2020-01-10",
        speed_tolerance_km_s=100.0, angle_tolerance_deg=10.0,
        propagation_window_days=9.0,
    )
    base.update(overrides)
    return SearchParameters(**base)


def _stationary(lon, r_au=1.0, hours=9 * 24, lat=0.0):
    """Hour-sampled stationary probe starting at the event time."""
    t = T0 + np.arange(0.0, hours * HOUR, HOUR)
    n = t.size
    return (t, np.full(n, lon), np.full(n, lat), np.full(n, r_au * AU_KM))


def _bent_axis_lon(r_au=1.0):
    return float(
        wavefront.axis_longitude_deg(r_au * AU_KM, 0.0, 400.0, R_SUN_KM)
    )


# --------------------------------------------------------------------------- #
# Confirmed encounters
# --------------------------------------------------------------------------- #
def test_confirmed_encounter_on_parker_axis():
    lon = _bent_axis_lon()
    t, lon_a, lat_a, r = _stationary(lon)
    params = _params()
    res = evaluate_wavefront_encounter(
        t, lon_a, lat_a, r, t_event_unix=T0, **EVENT, params=params
    )
    assert res is not None and res.verdict == "confirmed"

    t_arr = wavefront.front_arrival_s(AU_KM, 800.0, "parker_drag",
                                      400.0, 0.2e-7, R_SUN_KM)
    assert abs(res.sweep_unix - (T0 + t_arr)) < 120.0  # sub-sample sweep time
    assert res.enter_unix > res.sweep_unix             # region entry after sweep
    assert res.n_points >= 1
    assert res.angular_separation_deg < 30.0           # inside the cap
    # Deceleration: front speed at 1 AU is below the launch speed 800 km/s.
    assert 400.0 < res.front_speed_km_s < 800.0
    assert res.tolerance_km == 1000.0


def test_confirmed_parker_ballistic_constant_speed():
    lon = _bent_axis_lon()
    t, lon_a, lat_a, r = _stationary(lon)
    params = _params(propagation_model="parker_ballistic")
    res = evaluate_wavefront_encounter(
        t, lon_a, lat_a, r, t_event_unix=T0, **EVENT, params=params
    )
    assert res is not None and res.verdict == "confirmed"
    assert res.front_speed_km_s == 800.0  # no velocity evolution


def test_slow_icme_accelerates_toward_wind():
    # v0 = 200 km/s < ambient w = 400 km/s: the two-branch drag model
    # accelerates the front; it still arrives and sweeps the probe.
    lon = _bent_axis_lon()
    t, lon_a, lat_a, r = _stationary(lon)
    res = evaluate_wavefront_encounter(
        t, lon_a, lat_a, r, t_event_unix=T0,
        lon_source_deg=0.0, lat_source_deg=0.0, half_width_deg=30.0,
        speed_km_s=200.0, params=_params(),
    )
    assert res is not None and res.verdict == "confirmed"
    assert res.front_speed_km_s > 200.0  # accelerated by the fast wind


# --------------------------------------------------------------------------- #
# Rejections
# --------------------------------------------------------------------------- #
def test_off_axis_probe_sees_nothing():
    t, lon, lat, r = _stationary(90.0)
    res = evaluate_wavefront_encounter(
        t, lon, lat, r, t_event_unix=T0, **EVENT, params=_params()
    )
    assert res is None


def test_front_never_reaches_probe_is_not_encounter():
    # 50 km/s constant-speed front reaches only ~0.26 AU in the 9-day window.
    t, lon, lat, r = _stationary(0.0)
    res = evaluate_wavefront_encounter(
        t, lon, lat, r, t_event_unix=T0,
        lon_source_deg=0.0, lat_source_deg=0.0, half_width_deg=30.0,
        speed_km_s=50.0, params=_params(propagation_model="parker_ballistic"),
    )
    assert res is None


def test_geometry_intersection_without_sweep_is_not_encounter():
    # The probe sits ON the source axis (straight-cone geometry intersects)
    # but the Parker-bent front at 1 AU is ~61 deg away - outside the cone.
    # Orbit-cone intersection must NOT be called an encounter.
    t, lon, lat, r = _stationary(0.0)
    res = evaluate_wavefront_encounter(
        t, lon, lat, r, t_event_unix=T0, **EVENT, params=_params()
    )
    assert res is None


def test_parker_bend_admits_connected_probe_outside_straight_cone():
    # Probe on the *bent* (magnetically connected) axis: 61 deg from the
    # source, far outside the straight cone, but a genuine Parker encounter.
    lon = _bent_axis_lon()
    assert abs(lon) > 40.0  # outside straight cone + 10 deg tolerance
    t, lon_a, lat_a, r = _stationary(lon)
    res = evaluate_wavefront_encounter(
        t, lon_a, lat_a, r, t_event_unix=T0, **EVENT, params=_params()
    )
    assert res is not None and res.verdict == "confirmed"


def test_inside_region_without_wavefront_sweep_is_not_encounter():
    # Samples begin after the front has already passed the probe and the
    # probe sits inside the ICME region - but no wavefront sweep is observed
    # in the evaluated samples, so this must NOT be confirmed.
    lon = _bent_axis_lon()
    t_arr = wavefront.front_arrival_s(AU_KM, 800.0, "parker_drag",
                                      400.0, 0.2e-7, R_SUN_KM)
    t = T0 + t_arr + np.array([3.0, 4.0, 5.0, 6.0, 7.0]) * HOUR
    n = t.size
    lon_a = np.full(n, lon)
    lat_a = np.zeros(n)
    r = np.full(n, AU_KM)
    res = evaluate_wavefront_encounter(
        t, lon_a, lat_a, r, t_event_unix=T0, **EVENT, params=_params()
    )
    assert res is None


def test_tiny_icme_thickness_rejects_because_probe_never_inside_region():
    # With a 1000 km ICME half-thickness the probe (sampled hourly) leaves the
    # region between samples: swept radially, but never *inside* the region.
    lon = _bent_axis_lon()
    t, lon_a, lat_a, r = _stationary(lon)
    params = _params(icme_half_thickness_km=1000.0)
    res = evaluate_wavefront_encounter(
        t, lon_a, lat_a, r, t_event_unix=T0, **EVENT, params=params
    )
    assert res is None


def test_propagation_window_too_short_is_not_encounter():
    lon = _bent_axis_lon()
    t, lon_a, lat_a, r = _stationary(lon)
    params = _params(propagation_window_days=0.5)
    res = evaluate_wavefront_encounter(
        t, lon_a, lat_a, r, t_event_unix=T0, **EVENT, params=params
    )
    assert res is None


# --------------------------------------------------------------------------- #
# Orchestrator with fakes
# --------------------------------------------------------------------------- #
class _FakeTime:
    def __init__(self, unix):
        self.unix = np.asarray(unix, dtype=float)


def _event():
    return CMEEvent(
        trigger_time="2020-01-01T00:00:00",
        lat_deg=0, lon_deg=0, half_width_deg=30, speed_km_s=800,
        event_time="2020-01-01T00:00:00",
        cme_id="CME-001", source="TEST", catalog_flag="true", cme_type="S",
    )


def _fake_catalog(start, end):
    return [_event()]


def _fake_ephemeris(span_start, span_end, bodies):
    lon = _bent_axis_lon()
    t = T0 + np.arange(0.0, 9 * 24 * HOUR, HOUR)
    n = t.size
    return {
        "PSP": EphemerisPoints(
            body_key="PSP", obstime=_FakeTime(t),
            lon_deg=np.full(n, lon), lat_deg=np.zeros(n),
            r_km=np.full(n, AU_KM), cadence="60m",
        )
    }


def test_search_reports_wavefront_diagnostics():
    params = _params()
    search = EncounterSearch(
        catalog_query=_fake_catalog, ephemeris_service=_FakeEphemeris()
    )
    result = search.run(params)
    enc = result.encounters[0]
    assert enc.has_match
    psp = enc.bodies["PSP"]
    assert psp.verdict == "confirmed"
    # Sweep happens ~66 h after the event (decelerated arrival at 1 AU).
    assert psp.sweep_time.startswith("2020-01-03T")
    assert psp.enter_time > psp.sweep_time
    assert psp.sweep_radius_km == pytest.approx(AU_KM, rel=1e-3)
    assert psp.front_speed_km_s > 400.0
    assert psp.angular_separation_deg < 30.0


class _FakeEphemeris:
    def get_many(self, span_start, span_end, bodies):
        return _fake_ephemeris(span_start, span_end, bodies)
