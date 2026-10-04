"""Legacy TSV report export from a synthetic result."""

from cmemoss.domain import (
    BodyEncounter,
    CMEEncounter,
    CMEEvent,
    SearchParameters,
    SearchResult,
)
from cmemoss.export.report import write_json, write_legacy_report


def _result():
    event = CMEEvent(
        trigger_time="2022-09-05T00:00:00Z", lat_deg=10, lon_deg=-5,
        half_width_deg=40, speed_km_s=900,
        event_time="2022-09-05T05:09:05", cme_id="CME-001",
        source="SR", catalog_flag="FLAG", cme_type="S",
    )
    encounter = CMEEncounter(
        event=event,
        bodies={
            "PSP": BodyEncounter("PSP", 10, 40,
                                 "2022-09-06T02:00:00", "2022-09-06T10:00:00",
                                 4.1e7, 7.0e7, 31),
        },
    )
    params = SearchParameters("2022-09-05", "2022-09-06")
    return SearchResult(params, [event], {}, [encounter])


def test_legacy_report_contents(tmp_path):
    path = write_legacy_report(_result(), tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "###header start###" in text
    assert "###header end###" in text
    assert "2022-09-05T05:09:05" in text
    assert "PSP\t2022-09-06T02:00:00\t2022-09-06T10:00:00" in text
    assert path.name == "CME2022-09-05to2022-09-06.txt"


def test_json_export_roundtrip(tmp_path):
    import json

    path = write_json(_result(), tmp_path / "r.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["parameters"]["start_date"] == "2022-09-05"
    assert data["encounters"][0]["bodies"]["PSP"]["n_points"] == 31
