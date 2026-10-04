"""Single source of truth for tracked spacecraft / planets.

This replaces four independently-maintained mappings in the legacy code
(``SC`` list in ``cone_search_HEEQ.py``, ``spacecrafts_names`` / ``colors`` in
``data_visualization.py`` and ``target_dict`` in the in-situ module).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

HorizonsTarget = Union[str, int]


@dataclass(frozen=True)
class BodySpec:
    """Static metadata for one tracked body.

    Parameters
    ----------
    key:
        Short identifier used everywhere inside CME-MOSS.
    horizons:
        Target id accepted by ``sunpy.coordinates.get_horizons_coord``.
    launch_iso:
        Launch time (UTC) or ``None`` for planets. Requests are clipped to
        times after launch and bodies are skipped before launch.
    cadence:
        Ephemeris sampling step, e.g. ``"15m"`` (matches legacy settings).
    in_situ:
        Whether in-situ science data loaders exist for this body.
    """

    key: str
    horizons: HorizonsTarget
    label: str
    color: str
    launch_iso: Optional[str]
    cadence: str
    in_situ: bool = True


# Order is significant: it is the column order used in the text report.
BODY_REGISTRY: dict[str, BodySpec] = {
    "PSP": BodySpec("PSP", "Parker Solar Probe", "Parker Solar Probe",
                    "purple", "2018-08-12T08:17:00", "15m"),
    "SolO": BodySpec("SolO", "Solar Orbiter", "Solar Orbiter",
                     "red", "2020-02-10T05:00:00", "15m"),
    "BC": BodySpec("BC", "Bepi", "BepiColombo",
                   "green", "2018-10-20T02:14:00", "15m"),
    "SA": BodySpec("SA", "STEREO-A", "STEREO-A",
                   "#236B8E", None, "30m"),
    "Mercury": BodySpec("Mercury", 1, "Mercury", "grey", None, "60m",
                        in_situ=False),
    "Earth": BodySpec("Earth", 3, "Earth", "blue", None, "60m"),
    "Mars": BodySpec("Mars", 4, "Mars", "brown", None, "60m"),
}

BODY_ORDER: tuple[str, ...] = tuple(BODY_REGISTRY.keys())


def get_body(key: str) -> BodySpec:
    try:
        return BODY_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"unknown body {key!r}; valid: {', '.join(BODY_ORDER)}") from exc


def available_at(launch_iso: Optional[str], start_time, end_time) -> Optional[object]:
    """Return the effective start time if the body exists over the interval.

    ``None`` means the whole interval is before launch. Inputs are astropy
    ``Time`` (compared here with sunpy's parsed launch time).
    """
    from cmemoss.core.time_utils import parse_time

    if launch_iso is None:
        return start_time
    launch = parse_time(launch_iso)
    if end_time < launch:
        return None
    if start_time >= launch:
        return start_time
    return launch
