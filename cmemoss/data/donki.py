"""CCMC DONKI ``CMEAnalysis`` catalog client.

Replaces ``CME_query`` in the legacy ``cone_search_HEEQ.py``:

* the regular expression and its field semantics are preserved verbatim
  (validated by ``tests/test_donki_parser.py``);
* rows are parsed into typed :class:`~cmemoss.domain.CMEEvent` objects instead
  of a loose ``DataFrame`` (pandas dependency removed);
* the raw response is cached on disk so repeated searches never re-download;
* HTTP / empty-result failures raise explicit exceptions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from cmemoss.config import CONFIG
from cmemoss.core.time_utils import utc_now_iso, validate_date_string
from cmemoss.domain import CMEEvent

CME_ANALYSIS_URL = (
    "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/CMEAnalysis.txt"
    "?startDate={start}&endDate={end}"
)

# Kept byte-for-byte compatible with the legacy parser.
_LINE_RE = re.compile(
    r"(?P<trigger_time>\S+)\s+lat=(?P<lat>-?\d+)\s+lon=(?P<lon>-?\d+)\s+"
    r"rad=(?P<rad>\d+)\s+vel=(?P<vel>\d+)\s+"
    r"#(?P<event_time>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})-"
    r"(?P<cme_id>[^ ]+)\s+(?P<source>[^ ]+)\s+"
    r"(?P<catalog_flag>\S+)\s+(?P<type>\S+)"
)


class DonkiError(RuntimeError):
    """Raised when DONKI cannot be reached or returns no usable catalog."""


def parse_cme_analysis(raw_text: str) -> list[CMEEvent]:
    """Parse a CMEAnalysis.txt payload into typed events."""
    events: list[CMEEvent] = []
    for line in raw_text.strip().splitlines():
        m = _LINE_RE.match(line.strip())
        if not m:
            continue
        g = m.groupdict()
        events.append(
            CMEEvent(
                trigger_time=g["trigger_time"],
                lat_deg=int(g["lat"]),
                lon_deg=int(g["lon"]),
                half_width_deg=int(g["rad"]),
                speed_km_s=int(g["vel"]),
                event_time=g["event_time"],
                cme_id=g["cme_id"],
                source=g["source"],
                catalog_flag=g["catalog_flag"],
                cme_type=g["type"],
            )
        )
    events.sort(key=lambda e: e.event_time)
    return events


def _cache_path(start: str, end: str) -> Path:
    return CONFIG.donki_cache_dir / f"CMEAnalysis_{start}_{end}.txt"


def _read_cached(start: str, end: str) -> Optional[str]:
    path = _cache_path(start, end)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _write_cache(start: str, end: str, raw_text: str) -> None:
    header = f"# cached {utc_now_iso()} from {CME_ANALYSIS_URL}\n"
    _cache_path(start, end).write_text(header + raw_text, encoding="utf-8")


def fetch_cme_analysis_raw(
    start: str, end: str, *, force_refresh: bool = False, timeout: Optional[float] = None
) -> str:
    """Download (or load cached) raw CMEAnalysis text for a date range."""
    start = validate_date_string(start)
    end = validate_date_string(end)
    if not force_refresh:
        cached = _read_cached(start, end)
        if cached is not None:
            return cached
    url = CME_ANALYSIS_URL.format(start=start, end=end)
    import requests  # lazy: parsing stays usable without networking deps

    try:
        response = requests.get(url, timeout=timeout or CONFIG.http_timeout_s)
    except requests.RequestException as exc:
        raise DonkiError(f"failed to contact DONKI ({url}): {exc}") from exc
    if response.status_code != 200:
        raise DonkiError(f"DONKI returned HTTP {response.status_code} for {url}")
    raw = response.text
    _write_cache(start, end, raw)
    return raw


def query_cme_events(
    start: str, end: str, *, force_refresh: bool = False
) -> list[CMEEvent]:
    """Return the parsed, time-sorted CME catalog for *start*..*end*."""
    raw = fetch_cme_analysis_raw(start, end, force_refresh=force_refresh)
    events = parse_cme_analysis(raw)
    if not events:
        raise DonkiError(f"no parseable CMEAnalysis rows for {start} .. {end}")
    return events
