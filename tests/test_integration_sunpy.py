"""Offline integration tests through real astropy/sunpy coordinate objects.

Skipped if sunpy is not installed. No network calls are made: HGS SkyCoords are
constructed directly. The planetary Earth lookup inside the figure builder is
defensively optional.
"""

import numpy as np
import pytest

pytest.importorskip("sunpy")

import astropy.units as u  # noqa: E402
import matplotlib  # noqa: E402
from astropy.coordinates import SkyCoord  # noqa: E402
from astropy.time import Time  # noqa: E402
from sunpy.coordinates import HeliographicStonyhurst  # noqa: E402

from cmemoss.analysis.encounter import EncounterSearch  # noqa: E402
from cmemoss.constants import AU_KM, R_SUN_KM  # noqa: E402
from cmemoss.domain import CMEEvent, SearchParameters  # noqa: E402
from cmemoss.physics import wavefront  # noqa: E402
from cmemoss.preprocess.coordinates import from_skycoord  # noqa: E402

matplotlib.use("Agg")


def _bent_axis_lon():
    """Longitude of the Parker-bent front axis at 1 AU (source lon 0)."""
    return float(
        wavefront.axis_longitude_deg(AU_KM, 0.0, 400.0, R_SUN_KM)
    )


def _points(body_key="PSP", lon=0.0, lat=0.0, r_km=AU_KM, n_hours=240):
    obstime = Time("2022-09-05T00:00:00", format="isot", scale="utc") \
        + np.arange(n_hours) * u.hour
    coord = SkyCoord(
        lon=np.full(n_hours, lon) * u.deg,
        lat=np.full(n_hours, lat) * u.deg,
        radius=np.full(n_hours, r_km) * u.km,
        obstime=obstime,
        frame=HeliographicStonyhurst,
    )
    return from_skycoord(coord, body_key, cadence="60m")


def _event(speed=800):
    return CMEEvent(
        trigger_time="2022-09-05T00:00:00Z", lat_deg=0, lon_deg=0,
        half_width_deg=30, speed_km_s=speed,
        event_time="2022-09-05T00:00:00", cme_id="CME-X", source="SR",
        catalog_flag="F", cme_type="S",
    )


def test_skycoord_roundtrip():
    pts = _points(lon=12.5, lat=-7.25, r_km=2.0e8)
    assert pts.lon_deg.shape == (240,)
    assert np.allclose(pts.lon_deg, 12.5)
    assert np.allclose(pts.lat_deg, -7.25)
    assert np.allclose(pts.r_km, 2.0e8)
    assert pts.unix[-1] - pts.unix[0] == pytest.approx(239 * 3600.0)


def test_evaluate_event_finds_body():
    # The probe sits on the Parker-bent front axis at 1 AU (magnetically
    # connected to the source), so the wavefront genuinely sweeps it.
    pts = {"PSP": _points(lon=_bent_axis_lon(), lat=0.0)}
    params = SearchParameters("2022-09-05", "2022-09-12")
    search = EncounterSearch(catalog_query=None, ephemeris_service=object())
    encounter = search._evaluate_event(_event(), pts, params)
    assert "PSP" in encounter.bodies
    window = encounter.bodies["PSP"]
    assert window.enter_time.startswith("2022-09-")
    assert "T" in window.enter_time
    assert window.exit_index >= window.enter_index
    assert window.n_points > 0
    assert window.verdict == "confirmed"
    assert window.sweep_time.startswith("2022-09-")


def test_evaluate_event_misses_body_off_axis():
    pts = {"PSP": _points(lon=90.0, lat=0.0)}
    params = SearchParameters("2022-09-05", "2022-09-12")
    search = EncounterSearch(catalog_query=None, ephemeris_service=object())
    encounter = search._evaluate_event(_event(), pts, params)
    assert "PSP" not in encounter.bodies


def test_encounter_figure_renders():
    import matplotlib.pyplot as plt

    from cmemoss.visualization.encounter_plot import make_encounter_figure

    pts = {"PSP": _points(lon=_bent_axis_lon(), lat=0.0)}
    params = SearchParameters("2022-09-05", "2022-09-12",
                              parker_wind_speeds_km_s=(300.0, 400.0, 500.0))
    search = EncounterSearch(catalog_query=None, ephemeris_service=object())
    encounter = search._evaluate_event(_event(), pts, params)
    fig = make_encounter_figure(_event(), encounter.bodies, pts, params)
    fig.canvas.draw()
    assert len(fig.axes) == 1
    plt.close(fig)
