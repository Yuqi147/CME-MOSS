"""Result serialisation.

``write_legacy_report`` preserves the tab-separated layout and header of the
legacy ``CME{start}to{end}.txt`` so existing workflows keep working; the
companion JSON export carries the full provenance (model, parameters, units).
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Union

from cmemoss.bodies import BODY_ORDER
from cmemoss.domain import SearchResult

_REPORT_HEADERS = (
    "#event: CME occurrence time",
    "#Object: Spacecrafts or planets",
    "#start: Cone-zone entering time",
    "#end: Cone-zone exiting time",
    "#distance1: entering distance from the sun (km)",
    "#distance2: exiting distance from the sun (km)",
)


def report_filename(start: str, end: str) -> str:
    return f"CME{start}to{end}.txt"


def write_legacy_report(result: SearchResult, directory: Union[str, Path] = ".") -> Path:
    """Write the legacy TSV encounter report; return its path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_filename(result.parameters.start_date,
                                        result.parameters.end_date)

    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("###header start###\n")
        f.write("precision at the hour level\n")
        f.write("\n".join(_REPORT_HEADERS) + "\n")
        f.write("event\n")
        f.write("Object\tstart\tend\tdistance1\tdistance2\n")
        f.write("###header end###\n")

        writer = csv.writer(f, delimiter="\t")
        for encounter in result.encounters:
            if not encounter.has_match:
                continue
            writer.writerow([encounter.event.event_time])
            for body in BODY_ORDER:
                window = encounter.bodies.get(body)
                if window is None:
                    continue
                writer.writerow([
                    body,
                    window.enter_time,
                    window.exit_time,
                    f"{window.enter_radius_km:.1f}",
                    f"{window.exit_radius_km:.1f}",
                ])
            writer.writerow([])
    return path


def write_json(result: SearchResult, path: Union[str, Path]) -> Path:
    """Write the full search result (parameters, events, encounters) as JSON.

    Ephemeris samples are not embedded (they are reproducible from the cached
    Horizons requests); event and encounter records are fully self-contained.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "parameters": asdict(result.parameters),
        "events": [asdict(e) for e in result.events],
        "encounters": [
            {
                "event": asdict(enc.event),
                "bodies": {k: asdict(v) for k, v in enc.bodies.items()},
            }
            for enc in result.encounters
            if enc.has_match
        ],
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
