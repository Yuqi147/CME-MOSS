"""Time helpers.

``astropy`` / ``sunpy`` are imported lazily so the pure-numpy physics modules
(and their unit tests) do not pay for, or depend on, the full astronomy stack.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Tuple

_DATE_FMT = "%Y-%m-%d"


def parse_time(value: Any):
    """Parse anything date-like into an ``astropy.time.Time`` via sunpy."""
    from sunpy.time import parse_time  # local import: heavy dependency

    return parse_time(value)


def to_date_string(value: Any) -> str:
    """Normalise a date-like value to ``YYYY-MM-DD`` (UTC)."""
    if isinstance(value, str):
        # Fast path for the common ISO strings used throughout the GUI / API.
        return value.strip().replace("/", "-")[:10]
    if isinstance(value, datetime):
        return value.strftime(_DATE_FMT)
    return str(parse_time(value).datetime.strftime(_DATE_FMT))


def validate_date_string(value: str) -> str:
    """Raise ``ValueError`` unless *value* is a valid ``YYYY-MM-DD`` date."""
    datetime.strptime(value, _DATE_FMT)
    return value


def unix_seconds(time_obj: Any) -> "Any":
    """Return POSIX seconds (numpy float array possible) from an astropy Time."""
    return time_obj.unix


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_bounds(start: Any, end: Any) -> Tuple[Any, Any]:
    t0 = parse_time(to_date_string(start) + "T00:00:00")
    t1 = parse_time(to_date_string(end) + "T23:59:59")
    return t0, t1
