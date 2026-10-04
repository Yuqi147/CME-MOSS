"""Cached, vectorised JPL/Horizons ephemeris service.

Replaces the five near-identical ``get_PSP / get_SolO / get_STEREO_A /
get_BepiColombo / get_Planets`` functions with one registry-driven call.

* A request is identified by ``(body, start, stop, cadence)`` and served from
  an in-memory cache, then a compressed ``.npz`` disk cache, and only fetched
  from Horizons on a true miss.
* Launch windows are honoured from :mod:`cmemoss.bodies`.
* The returned trajectory is a numpy-backed
  :class:`~cmemoss.preprocess.coordinates.EphemerisPoints`.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from cmemoss.bodies import BODY_ORDER, BodySpec, available_at, get_body
from cmemoss.core.cache import MemoryCache, NpzDiskCache, stable_key
from cmemoss.preprocess.coordinates import EphemerisPoints, from_skycoord


class EphemerisService:
    def __init__(self, disk_cache: Optional[NpzDiskCache] = None) -> None:
        from cmemoss.config import CONFIG

        self._memory = MemoryCache()
        self._disk = disk_cache or NpzDiskCache(CONFIG.ephemeris_cache_dir)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _query_horizons(spec: BodySpec, start_time, end_time) -> EphemerisPoints:
        from sunpy.coordinates import get_horizons_coord

        coord = get_horizons_coord(
            spec.horizons,
            {"start": start_time, "stop": end_time, "step": spec.cadence},
        )
        return from_skycoord(coord, spec.key, cadence=spec.cadence)

    def _request(self, spec: BodySpec, start_time, end_time) -> EphemerisPoints:
        """Memory -> disk -> Horizons lookup for one body."""
        key = stable_key(
            "ephem", spec.key, str(start_time.iso), str(end_time.iso), spec.cadence
        )

        def from_disk() -> EphemerisPoints:
            def producer() -> tuple[dict, dict]:
                points = self._query_horizons(spec, start_time, end_time)
                return (
                    {
                        "unix": points.unix,
                        "lon": points.lon_deg,
                        "lat": points.lat_deg,
                        "r": points.r_km,
                    },
                    {"body": spec.key, "cadence": spec.cadence},
                )

            bundle = self._disk.get_or_set(key, producer)
            from astropy.time import Time

            arr = bundle["arrays"]
            return EphemerisPoints(
                body_key=bundle["meta"].get("body", spec.key),
                obstime=Time(np.asarray(arr["unix"], dtype=float).reshape(-1),
                             format="unix"),
                lon_deg=np.asarray(arr["lon"], dtype=float).reshape(-1),
                lat_deg=np.asarray(arr["lat"], dtype=float).reshape(-1),
                r_km=np.asarray(arr["r"], dtype=float).reshape(-1),
                cadence=bundle["meta"].get("cadence", spec.cadence),
            )

        return self._memory.get_or_set(key, from_disk)

    # ------------------------------------------------------------------ #
    def get(self, body_key: str, start_time, end_time) -> Optional[EphemerisPoints]:
        """Return a body trajectory, or ``None`` if it has not launched yet."""
        spec = get_body(body_key)
        effective_start = available_at(spec.launch_iso, start_time, end_time)
        if effective_start is None:
            return None
        return self._request(spec, effective_start, end_time)

    def get_many(
        self, start_time, end_time, body_keys: Optional[tuple[str, ...]] = None
    ) -> dict[str, EphemerisPoints]:
        """Fetch trajectories for all (available) bodies over one interval."""
        keys = body_keys or BODY_ORDER
        out: dict[str, EphemerisPoints] = {}
        for key in keys:
            points = self.get(key, start_time, end_time)
            if points is not None and len(points) > 0:
                out[key] = points
        return out
