"""Tests for the TimeSeries container and robustness helpers."""

import numpy as np

from cmemoss.preprocess.timeseries import TimeSeries


def _vector_series():
    t = np.arange(0.0, 100.0, 10.0)
    y = np.column_stack([t, 2 * t, 3 * t])
    return TimeSeries("v", t, y, ["x", "y", "z"], {"x": "km/s", "y": "km/s",
                                                    "z": "km/s"})


def test_magnitude_column():
    s = _vector_series().with_magnitude(("x", "y", "z"), "|v|", "km/s")
    assert s.columns[-1] == "|v|"
    # rows are [10i, 20i, 30i] -> magnitude 10i*sqrt(14)
    expected = 10.0 * np.linalg.norm([1, 2, 3]) * np.arange(0, 10)
    assert np.allclose(s.values[:, -1], expected)


def test_crop():
    s = _vector_series().crop(20.0, 50.0)
    assert s.epochs_unix.tolist() == [20.0, 30.0, 40.0, 50.0]


def test_gap_detection():
    t = np.array([0.0, 10.0, 20.0, 200.0, 210.0])
    y = np.zeros_like(t)
    gaps = TimeSeries("x", t, y, ["x"]).gaps(min_gap_s=60.0)
    assert gaps == [(20.0, 200.0)]


def test_nan_finite_mask():
    t = np.arange(3.0)
    y = np.array([[1.0], [np.nan], [3.0]])
    s = TimeSeries("x", t, y, ["x"])
    assert s.finite_mask().tolist() == [True, False, True]
