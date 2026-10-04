"""Polar encounter map: Sun, bodies, ICME wavefront cone and Parker overlay.

All inputs are domain objects / :class:`EphemerisPoints`; this module never
touches the network or the GUI.

For the Parker propagation models the cone follows the background-flow
(Parker spiral) geometry: the cone axis bends with heliocentric distance and
the wavefront is a curved arc that moves out with the propagated front.  The
whole ICME propagation channel between the two lateral boundary lines is
filled (launch radius to the leading wavefront).  The legacy straight-cone
drawing is kept for the ballistic / drag models.
"""

from __future__ import annotations

import numpy as np

import matplotlib.pyplot as plt

from cmemoss.constants import AU_KM, R_SUN_KM
from cmemoss.domain import CMEEvent, SearchParameters
from cmemoss.physics import parker, wavefront
from cmemoss.preprocess.coordinates import EphemerisPoints
from cmemoss.visualization.styles import (
    FRONT_CADENCE_HOURS,
    PARKER_COLORS,
    PLOT_R_MAX_AU,
    body_color,
    body_label,
)

_PAST_S = 4.0 * 86_400.0

_PARKER_MODELS = ("parker_drag", "parker_ballistic")


def _front_radius_km(t_s: np.ndarray, event: CMEEvent,
                     params: SearchParameters) -> np.ndarray:
    return wavefront.front_radius_km(
        t_s, event.speed_km_s, params.propagation_model,
        params.ambient_wind_km_s, params.drag_parameter_km,
        params.launch_radius_km,
    )


_FRONT_ARC_SAMPLES = 160


def _arc_points(center_lon_rad: float, half_rad: float, r_au: float,
                samples: int = _FRONT_ARC_SAMPLES) -> tuple[np.ndarray, np.ndarray]:
    """Dense samples of the sun-centred circular arc of the wavefront.

    Returns ``(theta, r)`` of ``samples`` points at constant radius ``r_au``
    spanning ``center_lon_rad +/- half_rad``.  With enough samples this
    renders as a curved arc, never as a straight chord.
    """
    theta = np.linspace(center_lon_rad - half_rad, center_lon_rad + half_rad,
                        samples)
    return theta, np.full_like(theta, r_au)


def _leading_front_radius_au(event: CMEEvent, params: SearchParameters,
                             r_max_au: float) -> float:
    """Radius of the outermost cadence wavefront inside the plot range.

    The arc moves outward with the ICME propagation distance: it is placed at
    the model-computed front radius (depends on the CME speed, the drag /
    velocity-evolution parameters and the launch radius), so changing the
    propagation parameters or the plot extent re-positions the wavefront.
    """
    dt_s = FRONT_CADENCE_HOURS * 3600.0
    r_lead: float | None = None
    n = 1
    while True:
        r_au = float(
            _front_radius_km(np.array([dt_s * n]), event, params)[0]
        ) / AU_KM
        if r_au > r_max_au:
            break
        r_lead = r_au
        n += 1
    return r_lead if r_lead is not None else r_max_au


def _parker_axis_segment(event: CMEEvent, params: SearchParameters,
                         r_lo_au: float, r_hi_au: float,
                         n: int = 300) -> tuple[np.ndarray, np.ndarray]:
    """``(lon_rad, r_au)`` of the bent front axis over ``[r_lo, r_hi]``."""
    r_au = np.linspace(r_lo_au, r_hi_au, n)
    r_km = r_au * AU_KM
    lon_deg = wavefront.axis_longitude_deg(
        r_km, float(event.lon_deg), params.v_sw_km_s, params.launch_radius_km
    )
    return np.radians(lon_deg), r_au


def _parker_axis_path(event: CMEEvent, params: SearchParameters,
                      r_max_au: float) -> tuple[np.ndarray, np.ndarray]:
    """``(lon_rad, r_au)`` of the bent front axis from launch to r_max."""
    return _parker_axis_segment(
        event, params, params.launch_radius_km / AU_KM, r_max_au, 300)


def _draw_parker_wavefront_region(
    ax, lon_axis_rad: np.ndarray, r_au: np.ndarray, half_rad: float,
    color: str = "orange", alpha: float = 0.3,
) -> None:
    """Fill the whole ICME propagation channel between the bent lateral
    edges (Parker models).

    ``lon_axis_rad`` / ``r_au`` sample the bent axis from the launch radius
    out to the leading front ``r_au[-1]``.  The fill follows the lower bent
    edge outward, crosses the front along a densely-sampled circular arc at
    ``r_au[-1]`` (the curved wavefront - never a straight chord), then
    returns along the upper bent edge.  The only closing segment is the tiny
    launch width at the CME launch radius, so the channel matches the two
    lateral boundary lines exactly and is capped by the arc-shaped wavefront.
    """
    lo = lon_axis_rad - half_rad
    hi = lon_axis_rad + half_rad
    front_th, front_r = _arc_points(lon_axis_rad[-1], half_rad, r_au[-1])
    theta = np.concatenate((lo, front_th, hi[::-1]))
    rr = np.concatenate((r_au, front_r, r_au[::-1]))
    ax.fill(theta, rr, color=color, alpha=alpha)


def _draw_legacy_wavefront_sector(
    ax, lon_rad: float, half_rad: float, r_lead_au: float,
    color: str = "orange", alpha: float = 0.3,
) -> None:
    """Fill the whole straight-cone ICME channel (ballistic / drag models):
    radial lateral edges from the Sun plus the curved leading wavefront."""
    lo = np.array([lon_rad - half_rad, lon_rad - half_rad])
    hi = np.array([lon_rad + half_rad, lon_rad + half_rad])
    r_lo = np.array([0.0, r_lead_au])
    front_th, front_r = _arc_points(lon_rad, half_rad, r_lead_au)
    theta = np.concatenate((lo, front_th, hi[::-1]))
    rr = np.concatenate((r_lo, front_r, r_lo[::-1]))
    ax.fill(theta, rr, color=color, alpha=alpha)


def plot_cone(ax, event: CMEEvent, params: SearchParameters,
              r_max_au: float = PLOT_R_MAX_AU) -> None:
    """Draw the ICME as **two lateral boundary lines + a curved leading
    wavefront** with the whole propagation channel filled.

    The fill covers the entire ICME path between the two lateral boundaries,
    from the launch radius out to the model-computed leading front
    ``r_lead``.  Its front edge is a circular arc (the curved wavefront) with
    angular width equal to the initial CME angular width (half-angle; the
    tolerance band is drawn separately).  The channel moves with the
    propagated front radius, so changing the propagation parameters or the
    plot extent re-positions the filled region.
    """
    lon = np.radians(event.lon_deg)
    half = np.radians(event.half_width_deg)
    tol = np.radians(params.angle_tolerance_deg)
    r_lead = _leading_front_radius_au(event, params, r_max_au)

    if params.propagation_model in _PARKER_MODELS:
        lon_axis, r_au = _parker_axis_path(event, params, r_lead)
        _draw_parker_wavefront_region(ax, lon_axis, r_au, half)
        _draw_parker_wavefront_region(ax, lon_axis, r_au, half + tol,
                                      alpha=0.08)
        # Lateral boundary lines along the full propagation channel.
        ax.plot(lon_axis - half, r_au, color="black", linestyle="dotted",
                linewidth=0.8)
        ax.plot(lon_axis + half, r_au, color="black", linestyle="dotted",
                linewidth=0.8)
        axis_lead = float(lon_axis[-1])
    else:
        _draw_legacy_wavefront_sector(ax, lon, half, r_lead)
        _draw_legacy_wavefront_sector(ax, lon, half + tol, r_lead, alpha=0.08)
        ax.plot([lon - half, lon - half], [0.0, r_lead], color="black",
                linestyle="dotted", linewidth=0.8)
        ax.plot([lon + half, lon + half], [0.0, r_lead], color="black",
                linestyle="dotted", linewidth=0.8)
        axis_lead = lon

    # Leading curved wavefront: the arc connecting the two lateral edges at
    # the leading front radius.
    theta_lead, r_lead_pts = _arc_points(axis_lead, half, r_lead)
    ax.plot(theta_lead, r_lead_pts, color="orange", linewidth=1.7,
            label="ICME wavefront")


def plot_body(ax, points: EphemerisPoints, t_event_unix: float,
              encounter, window_s: float) -> None:
    """Faint full track around the event; bold where the body is in-cone."""
    t = points.unix
    lon = np.radians(points.lon_deg)
    r_au = points.r_km / AU_KM
    color = body_color(points.body_key)

    near = (t >= t_event_unix - _PAST_S) & (t <= t_event_unix + window_s)
    if np.any(near):
        ax.plot(lon[near], r_au[near], color=color, alpha=0.35, linewidth=0.8)

    if encounter is not None:
        i0 = encounter.enter_index
        i1 = min(encounter.exit_index + 6, len(points) - 1)
        ax.plot(lon[i0:i1 + 1], r_au[i0:i1 + 1], color=color, linewidth=1.6,
                label=body_label(points.body_key))
        ax.plot(lon[i0], r_au[i0], marker="o", markersize=4, color=color)
        if encounter.sweep_index >= 0:
            s = encounter.sweep_index
            ax.plot(lon[s], r_au[s], marker="x", markersize=7,
                    color=color, mew=2)


def plot_parker_spirals(ax, wind_speeds, r_max_au: float = PLOT_R_MAX_AU,
                        footpoint_lon_deg: float = 0.0) -> None:
    """Overlay background-wind Parker spirals (dashed, labelled by speed)."""
    for i, v_sw in enumerate(sorted(wind_speeds)):
        lon, r_km = parker.spiral_curve(
            footpoint_lon_deg, v_sw, r_max_km=r_max_au * AU_KM
        )
        color = PARKER_COLORS[i % len(PARKER_COLORS)]
        ax.plot(np.radians(lon), r_km / AU_KM, linestyle="--", linewidth=0.9,
                color=color, alpha=0.8, label=f"Parker v={v_sw:.0f} km/s")


def plot_earth_now(ax, event: CMEEvent) -> None:
    """Place Earth at the event epoch (legacy code wrongly used 'now')."""
    try:
        from cmemoss.core.time_utils import parse_time
        from sunpy.coordinates import get_body_heliographic_stonyhurst

        earth = get_body_heliographic_stonyhurst(
            "earth", parse_time(event.event_time)
        )
        ax.plot(earth.lon.to_value("rad"), earth.radius.to_value("AU"),
                marker="o", color="blue", markersize=5, label="Earth")
    except Exception:
        # Ephemeris back-end unavailable - the Earth/L1 track still shows it.
        pass


def make_encounter_figure(
    event: CMEEvent,
    encounters: dict,
    ephemeris: dict[str, EphemerisPoints],
    params: SearchParameters,
    *,
    show_parker: bool = True,
) -> "plt.Figure":
    """Compose the full polar encounter map and return the figure."""
    from cmemoss.core.time_utils import parse_time

    t_event_unix = float(parse_time(event.event_time).unix)
    window_s = params.propagation_window_days * 86_400.0

    fig = plt.figure(figsize=(9.5, 9))
    ax = fig.add_subplot(projection="polar")
    ax.set_rmax(PLOT_R_MAX_AU)
    ax.plot(0, 0, marker="o", color="orange", markersize=8, label="Sun")

    plot_earth_now(ax, event)
    for body_key, points in ephemeris.items():
        plot_body(ax, points, t_event_unix,
                  encounters.get(body_key), window_s)
    # Background flow lines first: the (translucent) ICME fill, the lateral
    # boundary lines and the curved leading wavefront stay on top of them.
    if show_parker and params.parker_wind_speeds_km_s:
        plot_parker_spirals(ax, params.parker_wind_speeds_km_s)
    plot_cone(ax, event, params)

    ax.set_title(
        f"CME {event.event_time}  (lon={event.lon_deg}, lat={event.lat_deg}, "
        f"v={event.speed_km_s} km/s, model={params.propagation_model})\n"
        f"Parker front: v_sw={params.v_sw_km_s:.0f} km/s, "
        f"window={params.encounter_time_window_hours:g} h, "
        f"tol={params.encounter_tolerance_km:g} km, "
        f"thickness={params.icme_half_thickness_km / AU_KM:.2f} AU"
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8,
              frameon=True)
    fig.tight_layout()
    return fig


def save_figure(fig, path, dpi: int = 300) -> str:
    path = str(path)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
