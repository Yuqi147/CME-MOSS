"""Headless rendering smoke tests for the visualization layer.

Skipped entirely if matplotlib is not installed. Uses a fake ephemeris object
so no network / sunpy is needed; sunpy-dependent parts (Earth marker, time
parsing) are exercised in integration use.
"""

import numpy as np
import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from cmemoss.constants import AU_KM  # noqa: E402
from cmemoss.domain import CMEEvent, SearchParameters  # noqa: E402
from cmemoss.preprocess.coordinates import EphemerisPoints  # noqa: E402
from cmemoss.preprocess.timeseries import TimeSeries  # noqa: E402
from cmemoss.visualization import encounter_plot, timeseries_plot  # noqa: E402


class _FakeTime:
    def __init__(self, unix):
        self.unix = np.asarray(unix, dtype=float)


def _ephemeris():
    t = np.arange(0.0, 9 * 86400.0, 3600.0)
    n = t.size
    return EphemerisPoints(
        body_key="PSP",
        obstime=_FakeTime(t),
        lon_deg=np.full(n, 5.0),
        lat_deg=np.full(n, 1.0),
        r_km=np.linspace(0.3, 1.0, n) * AU_KM,
        cadence="60m",
    )


def test_polar_map_components_render():
    params = SearchParameters(
        "2020-01-01", "2020-01-02",
        parker_wind_speeds_km_s=(300.0, 400.0),
    )
    event = CMEEvent("t", lat_deg=0, lon_deg=0, half_width_deg=30,
                     speed_km_s=900, event_time="2020-01-01T00:00:00",
                     cme_id="x", source="s", catalog_flag="f", cme_type="S")

    fig = plt.figure()
    ax = fig.add_subplot(projection="polar")
    encounter_plot.plot_parker_spirals(ax, params.parker_wind_speeds_km_s)
    encounter_plot.plot_cone(ax, event, params)
    points = _ephemeris()
    encounter_plot.plot_body(ax, points, t_event_unix=0.0, encounter=None,
                             window_s=9 * 86400.0)
    fig.canvas.draw()
    plt.close(fig)


def test_timeseries_panel_with_magnitude_renders():
    t = np.arange(0.0, 1000.0, 60.0)
    y = np.column_stack([np.sin(t / 200), np.cos(t / 200),
                         0.5 * np.ones_like(t)])
    series = TimeSeries("B", t, y, ["Br", "Bt", "Bn"],
                        {"Br": "nT", "Bt": "nT", "Bn": "nT"})
    series = series.with_magnitude(("Br", "Bt", "Bn"), "|B|", "nT")
    fig = timeseries_plot.plot_time_series_panels(
        [("mag", series)], interactive=False)
    assert len(fig.axes) == 1
    # Four lines: 3 components + magnitude.
    assert len(fig.axes[0].lines) == 4
    fig.canvas.draw()
    plt.close(fig)
