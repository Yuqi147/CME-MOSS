"""SearchParameters JSON save/load roundtrip."""

from cmemoss.app.project_config import load_parameters, save_parameters
from cmemoss.domain import SearchParameters


def test_config_roundtrip(tmp_path):
    params = SearchParameters(
        start_date="2022-01-01", end_date="2022-01-10",
        speed_tolerance_km_s=80.0, propagation_model="drag",
        ambient_wind_km_s=450.0, drag_parameter_km=1.5e-8,
        bodies=("PSP", "Earth"),
        parker_wind_speeds_km_s=(300.0, 400.0),
    )
    path = save_parameters(params, tmp_path / "cfg.json")
    restored = load_parameters(path)
    assert restored == params
    assert isinstance(restored.bodies, tuple)
    assert isinstance(restored.parker_wind_speeds_km_s, tuple)


def test_invalid_model_rejected():
    import pytest

    with pytest.raises(ValueError):
        SearchParameters("2022-01-01", "2022-01-10", propagation_model="warp")
