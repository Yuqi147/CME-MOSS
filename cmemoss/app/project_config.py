"""Save / load a complete analysis configuration as JSON.

Persists exactly the contents of :class:`~cmemoss.domain.SearchParameters` so
an analysis saved from the GUI can be rerun from the CLI and vice versa.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Union

from cmemoss.domain import SearchParameters


def save_parameters(params: SearchParameters, path: Union[str, Path]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(params)
    # tuple -> list for JSON; bodies may be None ("all").
    data["bodies"] = list(params.bodies) if params.bodies else None
    data["parker_wind_speeds_km_s"] = list(params.parker_wind_speeds_km_s)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_parameters(path: Union[str, Path]) -> SearchParameters:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("bodies"):
        data["bodies"] = tuple(data["bodies"])
    if data.get("parker_wind_speeds_km_s"):
        data["parker_wind_speeds_km_s"] = tuple(
            float(v) for v in data["parker_wind_speeds_km_s"]
        )
    allowed = {f for f in SearchParameters.__dataclass_fields__}  # type: ignore[attr-defined]
    return SearchParameters(**{k: v for k, v in data.items() if k in allowed})
