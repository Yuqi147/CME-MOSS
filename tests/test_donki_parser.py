"""DONKI CMEAnalysis parser - locks down the legacy wire format (no network)."""

from cmemoss.data.donki import parse_cme_analysis

SAMPLE = (
    "2022-09-05T00:00:00Z lat=30 lon=-12 rad=45 vel=987 "
    "#2022-09-05T05:09:05-2022-09-05T05:09:05-CME-001 "
    "SourceRegion CATALOG_FLAG Type"
)


def test_parse_sample_row():
    events = parse_cme_analysis(SAMPLE)
    assert len(events) == 1
    e = events[0]
    assert e.lat_deg == 30
    assert e.lon_deg == -12
    assert e.half_width_deg == 45
    assert e.speed_km_s == 987
    assert e.event_time == "2022-09-05T05:09:05"
    assert e.source == "SourceRegion"
    assert e.catalog_flag == "CATALOG_FLAG"
    assert e.cme_type == "Type"


def test_unparseable_lines_are_skipped():
    assert parse_cme_analysis("garbage line\n\n") == []
