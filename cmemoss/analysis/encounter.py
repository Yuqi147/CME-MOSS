"""Parker-wavefront encounter search pipeline.

This is the *strict* dynamic encounter determination.  For every DONKI CME
event and every body the pipeline runs the staged search::

    candidate ICME
      -> coarse time filter            (propagation window)
      -> coarse spatial filter         (angular cone + radial reach)
      -> candidate ICME screen         (arrival solve, encounter window W)
      -> Parker propagation            (analytic front at sample times)
      -> wavefront precise calc        (gap, angular separation, front speed)
      -> sweep detection               (front crosses the probe, outward)
      -> region membership             (probe inside ICME after the sweep)
      -> confirmed encounter

The old single-instant ``cone && radial shell`` test is gone.  A body is
reported as encountering the ICME **only** when the Parker-propagating
wavefront (with velocity evolution) actually sweeps across it inside the
encounter time window and the probe remains inside the ICME's effective
spatial region afterwards.  In particular::

    orbit-geometry intersection        != encounter
    approaching the ICME              != encounter
    inside the ICME region, no sweep   != encounter
    wavefront sweeps probe + probe
      stays in ICME region             == confirmed encounter

The pure-numpy function :func:`evaluate_wavefront_encounter` contains the
whole physical test and is unit tested without network or sunpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from cmemoss.domain import (
    BodyEncounter,
    CMEEncounter,
    CMEEvent,
    SearchParameters,
    SearchResult,
)
from cmemoss.physics import cone, wavefront
from cmemoss.preprocess.coordinates import EphemerisPoints

_DAY_S = 86_400.0
# Bisection accuracy (seconds) for the exact wavefront-crossing time.
_SWEEP_TOL_S = 1.0


@dataclass(frozen=True)
class WavefrontResult:
    """Pure-numpy outcome of the wavefront evaluation for one probe."""

    verdict: str
    enter_index: int
    exit_index: int
    sweep_index: int
    sweep_unix: float
    enter_unix: float
    exit_unix: float
    sweep_radius_km: float
    front_speed_km_s: float
    angular_separation_deg: float
    n_points: int
    tolerance_km: float


def _iso_from_unix(unix: float) -> str:
    """Second-resolution UTC ISO string ('T' separator) for a unix time."""
    from astropy.time import Time

    return str(Time(float(unix), format="unix").iso).replace(" ", "T")[:19]


# --------------------------------------------------------------------------- #
# Coarse filters
# --------------------------------------------------------------------------- #
def _coarse_time_mask(
    t_unix: np.ndarray,
    t_event_unix: float,
    propagation_window_days: float,
) -> np.ndarray:
    """Samples inside the propagation window ``[t_event, t_event + T]``."""
    dt_s = t_unix - t_event_unix
    return (dt_s >= 0.0) & (dt_s <= propagation_window_days * _DAY_S)


def _coarse_angular_mask(
    lon_deg: np.ndarray,
    lat_deg: np.ndarray,
    r_km: np.ndarray,
    m_t: np.ndarray,
    *,
    lon_source_deg: float,
    lat_source_deg: float,
    half_width_deg: float,
    params: SearchParameters,
) -> np.ndarray:
    """Angular pre-screen around the *source* axis with spiral-bend margin.

    The bent axis can drift from the source longitude by up to the Parker
    shift at the largest probe radius inside the window, so the coarse limit
    is ``half_width + tolerance + shift(r_max)``.
    """
    r_max = float(np.max(r_km[m_t])) if np.any(m_t) else 0.0
    margin = (
        half_width_deg
        + params.angle_tolerance_deg
        + float(
            wavefront.axis_shift_deg(
                r_max, params.v_sw_km_s, params.launch_radius_km
            )
        )
    )
    sep = cone.angular_separation_deg(
        lon_source_deg, lat_source_deg, lon_deg, lat_deg
    )
    return sep <= margin


def _coarse_radial_reachable(
    r_km: np.ndarray,
    m_t: np.ndarray,
    t_event_unix: float,
    speed_km_s: float,
    params: SearchParameters,
) -> bool:
    """The front must be able to reach the probe's radial range in-window."""
    r_min = float(np.min(r_km[m_t]))
    r_front_end = float(
        wavefront.front_radius_km(
            params.propagation_window_days * _DAY_S,
            speed_km_s,
            params.propagation_model,
            params.ambient_wind_km_s,
            params.drag_parameter_km,
            params.launch_radius_km,
        )
    )
    return r_front_end >= r_min - params.encounter_tolerance_km


# --------------------------------------------------------------------------- #
# Precise wavefront evaluation
# --------------------------------------------------------------------------- #
def _encounter_window(
    r_ref_km: float,
    t_event_unix: float,
    speed_km_s: float,
    params: SearchParameters,
) -> tuple[float, float] | None:
    """Encounter search window centred on the model-predicted arrival.

    Returns ``(W0, W1)`` seconds (unix) or ``None`` when the model cannot
    predict an arrival inside the propagation window.
    """
    try:
        t_arr_dt = wavefront.front_arrival_s(
            r_ref_km,
            speed_km_s,
            params.propagation_model,
            params.ambient_wind_km_s,
            params.drag_parameter_km,
            params.launch_radius_km,
        )
    except ValueError:
        return None
    t_arr = t_event_unix + t_arr_dt
    half = 0.5 * params.encounter_time_window_hours * 3600.0
    t_end = t_event_unix + params.propagation_window_days * _DAY_S
    w0 = max(t_event_unix, t_arr - half)
    w1 = min(t_end, t_arr + half)
    if w1 <= w0:
        return None
    return w0, w1


def _probe_interp(
    t0: float, t1: float, v0: float, v1: float, t_sweep: float
) -> float:
    s = (t_sweep - t0) / max(t1 - t0, 1e-9)
    return float(v0 + s * (v1 - v0))


def _refine_sweep_unix(
    t0: float,
    t1: float,
    r0: float,
    r1: float,
    t_event_unix: float,
    speed_km_s: float,
    params: SearchParameters,
) -> float:
    """Bisect the exact time the front surface crosses the probe track.

    The probe is interpolated linearly between samples ``(t0, r0)`` and
    ``(t1, r1)``; the front is evaluated analytically, so the root of
    ``f(t) = r_front(t) - r_probe(t)`` is sub-sample accurate.
    """

    def gap_at(t: float) -> float:
        r_front = float(
            wavefront.front_radius_km(
                t - t_event_unix,
                speed_km_s,
                params.propagation_model,
                params.ambient_wind_km_s,
                params.drag_parameter_km,
                params.launch_radius_km,
            )
        )
        return r_front - _probe_interp(t0, t1, r0, r1, t)

    lo, hi = t0, t1
    if gap_at(lo) >= 0.0:  # probe already behind the front at interval start
        return t0
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if gap_at(mid) < 0.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < _SWEEP_TOL_S:
            break
    return 0.5 * (lo + hi)


def _sweep_candidates(
    gap: np.ndarray,
    tolerance_km: float,
) -> tuple[list[tuple[int, int]], list[int]]:
    """Ordered candidate sweep sites: outward crossings first, then samples
    sitting exactly on the front (``|gap| <= tol``)."""
    crossings, on_front = wavefront.sweep_crossing_intervals(
        gap, tolerance_km
    )
    return crossings, on_front


def evaluate_wavefront_encounter(
    t_unix: np.ndarray,
    lon_deg: np.ndarray,
    lat_deg: np.ndarray,
    r_km: np.ndarray,
    *,
    t_event_unix: float,
    lon_source_deg: float,
    lat_source_deg: float,
    half_width_deg: float,
    speed_km_s: float,
    params: SearchParameters,
) -> Optional[WavefrontResult]:
    """Strict dynamic wavefront encounter test for one probe.

    Returns a :class:`WavefrontResult` with ``verdict="confirmed"`` only if

    1. the Parker-propagating front (with velocity evolution) crosses the
       probe's heliocentric distance from inside to outside inside the
       encounter window (wavefront sweep), with the probe inside the angular
       cap at that moment; and
    2. after the sweep the probe stays inside the ICME effective region
       (``0 <= gap <= H`` and inside the angular cap) within the window.

    Returns ``None`` when the probe fails any stage (geometry intersection,
    proximity, or region entry without a wavefront sweep all yield ``None``).
    """
    t = np.asarray(t_unix, dtype=float)
    lon = np.asarray(lon_deg, dtype=float)
    lat = np.asarray(lat_deg, dtype=float)
    r = np.asarray(r_km, dtype=float)

    # 1) coarse time filter ---------------------------------------------- #
    m_t = _coarse_time_mask(t, t_event_unix, params.propagation_window_days)
    if not np.any(m_t):
        return None

    # 2) coarse spatial filters ------------------------------------------ #
    m_ang = _coarse_angular_mask(
        lon, lat, r, m_t,
        lon_source_deg=lon_source_deg,
        lat_source_deg=lat_source_deg,
        half_width_deg=half_width_deg,
        params=params,
    )
    if not np.any(m_ang & m_t):
        return None
    if not _coarse_radial_reachable(r, m_t, t_event_unix, speed_km_s, params):
        return None

    # 3) candidate screen: arrival & encounter window -------------------- #
    r_ref = float(np.median(r[m_t]))
    window = _encounter_window(r_ref, t_event_unix, speed_km_s, params)
    if window is None:
        return None
    w0, w1 = window

    # 4) Parker propagation: analytic front at every sample --------------- #
    dt_s = t - t_event_unix
    r_front = wavefront.front_radius_km(
        dt_s, speed_km_s, params.propagation_model,
        params.ambient_wind_km_s, params.drag_parameter_km,
        params.launch_radius_km,
    )
    gap = wavefront.gap_km(r_front, r)
    sep = wavefront.angular_separation_to_axis_deg(
        lon, lat, r,
        lon_source_deg, lat_source_deg,
        params.v_sw_km_s, params.launch_radius_km,
    )
    angular_ok = sep <= (half_width_deg + params.angle_tolerance_deg)
    tol = params.encounter_tolerance_km
    half_thickness = params.icme_half_thickness_km

    # 5) wavefront sweep detection ---------------------------------------- #
    crossings, on_front = _sweep_candidates(gap, tol)

    def _check_sweep(
        t_sweep: float, p_lon: float, p_lat: float, p_r: float
    ) -> Optional[WavefrontResult]:
        if not (w0 <= t_sweep <= w1):
            return None
        sep_sweep = float(
            wavefront.angular_separation_to_axis_deg(
                np.array([p_lon]), np.array([p_lat]), np.array([p_r]),
                lon_source_deg, lat_source_deg,
                params.v_sw_km_s, params.launch_radius_km,
            )[0]
        )
        if sep_sweep > (half_width_deg + params.angle_tolerance_deg):
            return None  # front swept radially but outside the angular cap
        v_front = float(
            wavefront.front_speed_km_s(
                t_sweep - t_event_unix, speed_km_s,
                params.propagation_model, params.ambient_wind_km_s,
                params.drag_parameter_km,
            )
        )
        if v_front <= 0.0:
            return None  # the front must genuinely propagate outward

        # 6) region membership after the sweep ---------------------------- #
        m_after = (t > t_sweep) & (t <= w1)
        in_region = (
            m_after
            & (gap >= 0.0)
            & (gap <= half_thickness)
            & angular_ok
        )
        idx = np.flatnonzero(in_region)
        if idx.size == 0:
            return None  # swept, but never inside the ICME region
        i_enter, i_exit = int(idx[0]), int(idx[-1])
        sweep_i = int(np.argmin(np.abs(t - t_sweep)))
        return WavefrontResult(
            verdict="confirmed",
            enter_index=i_enter,
            exit_index=i_exit,
            sweep_index=sweep_i,
            sweep_unix=t_sweep,
            enter_unix=float(t[i_enter]),
            exit_unix=float(t[i_exit]),
            sweep_radius_km=p_r,
            front_speed_km_s=v_front,
            angular_separation_deg=sep_sweep,
            n_points=int(idx.size),
            tolerance_km=tol,
        )

    for k, (i0, i1) in enumerate(crossings):
        t_sweep = _refine_sweep_unix(
            float(t[i0]), float(t[i1]),
            float(r[i0]), float(r[i1]),
            t_event_unix, speed_km_s, params,
        )
        s = (t_sweep - t[i0]) / max(t[i1] - t[i0], 1e-9)
        p_lon = lon[i0] + s * (lon[i1] - lon[i0])
        p_lat = lat[i0] + s * (lat[i1] - lat[i0])
        p_r = r[i0] + s * (r[i1] - r[i0])
        result = _check_sweep(t_sweep, float(p_lon), float(p_lat), float(p_r))
        if result is not None:
            return result
    for i in on_front:
        result = _check_sweep(
            float(t[i]), float(lon[i]), float(lat[i]), float(r[i])
        )
        if result is not None:
            return result
    return None


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class EncounterSearch:
    """Orchestrates catalog retrieval, ephemeris and encounter detection.

    Collaborators are injected so the pipeline is testable with fakes.
    """

    def __init__(
        self,
        catalog_query: Optional[Callable[..., list[CMEEvent]]] = None,
        ephemeris_service=None,
    ) -> None:
        if catalog_query is None:
            from cmemoss.data.donki import query_cme_events

            catalog_query = query_cme_events
        if ephemeris_service is None:
            from cmemoss.data.ephemeris import EphemerisService

            ephemeris_service = EphemerisService()
        self._query_catalog = catalog_query
        self._ephemeris = ephemeris_service

    # ------------------------------------------------------------------ #
    def run(self, params: SearchParameters) -> SearchResult:
        events = self._query_catalog(params.start_date, params.end_date)

        span_start, span_end = self._ephemeris_span(events, params)
        ephemeris = self._ephemeris.get_many(
            span_start, span_end, params.bodies
        )

        encounters = [
            self._evaluate_event(event, ephemeris, params) for event in events
        ]
        return SearchResult(
            parameters=params,
            events=events,
            ephemeris=ephemeris,
            encounters=encounters,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _ephemeris_span(events: list[CMEEvent], params: SearchParameters):
        import astropy.units as u

        from cmemoss.core.time_utils import parse_time

        first = parse_time(events[0].event_time) - 1 * u.day
        last = parse_time(events[-1].event_time) + params.propagation_window_days * u.day
        return first, last

    def _evaluate_event(
        self,
        event: CMEEvent,
        ephemeris: dict[str, EphemerisPoints],
        params: SearchParameters,
    ) -> CMEEncounter:
        from cmemoss.core.time_utils import parse_time

        t_event = parse_time(event.event_time)
        t_event_unix = float(t_event.unix)

        found: dict[str, BodyEncounter] = {}
        for body_key, points in ephemeris.items():
            result = evaluate_wavefront_encounter(
                points.unix, points.lon_deg, points.lat_deg, points.r_km,
                t_event_unix=t_event_unix,
                lon_source_deg=float(event.lon_deg),
                lat_source_deg=float(event.lat_deg),
                half_width_deg=float(event.half_width_deg),
                speed_km_s=float(event.speed_km_s),
                params=params,
            )
            if result is None or result.verdict != "confirmed":
                continue
            found[body_key] = BodyEncounter(
                body=body_key,
                enter_index=result.enter_index,
                exit_index=result.exit_index,
                enter_time=_iso_from_unix(result.enter_unix),
                exit_time=_iso_from_unix(result.exit_unix),
                enter_radius_km=float(points.r_km[result.enter_index]),
                exit_radius_km=float(points.r_km[result.exit_index]),
                n_points=result.n_points,
                verdict=result.verdict,
                sweep_time=_iso_from_unix(result.sweep_unix),
                sweep_index=result.sweep_index,
                sweep_radius_km=result.sweep_radius_km,
                front_speed_km_s=result.front_speed_km_s,
                angular_separation_deg=result.angular_separation_deg,
                tolerance_km=result.tolerance_km,
            )
        return CMEEncounter(event=event, bodies=found)
