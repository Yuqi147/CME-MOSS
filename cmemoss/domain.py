"""Shared domain dataclasses - the typed data contract between all layers.

Nothing here imports sunpy/astropy at module import time; astropy ``Time``
objects may be carried as values but annotations use strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from cmemoss.constants import AU_KM, R_SUN_KM


@dataclass(frozen=True)
class CMEEvent:
    """One row of the DONKI CMEAnalysis catalog.

    Attributes mirror the legacy regex groups. ``half_width_deg`` is the
    catalog ``rad`` field (cone half-angle in degrees); ``speed_km_s`` is the
    radial plane-of-sky / model speed used as the constant propagation speed
    in the legacy ballistic model.
    """

    trigger_time: str
    lat_deg: int
    lon_deg: int
    half_width_deg: int
    speed_km_s: int
    event_time: str
    cme_id: str
    source: str
    catalog_flag: str
    cme_type: str

    @property
    def axis(self) -> tuple[int, int]:
        return self.lon_deg, self.lat_deg


@dataclass(frozen=True)
class SearchParameters:
    """User-configurable inputs for a Parker-wavefront encounter search.

    Parameters
    ----------
    propagation_model:
        ``"parker_drag"`` (default) - Parker-spiral-bent front axis with the
        two-branch drag-based radial evolution (velocity decay/acceleration);
        ``"parker_ballistic"`` - Parker-bent axis at constant speed;
        ``"drag"`` / ``"ballistic"`` - legacy straight-cone radial-only models
        (kept for reproducibility).
    ambient_wind_km_s:
        Ambient solar-wind speed ``w`` of the drag model (km/s).
    drag_parameter_km:
        Aerodynamic drag parameter ``gamma`` of the drag model (1/km).
    v_sw_km_s:
        Solar-wind speed used for the Parker-spiral bending of the front axis
        (km/s).  Can differ from ``ambient_wind_km_s``.
    launch_radius_km:
        Heliocentric radius from which the front starts propagating (km).
    encounter_time_window_hours:
        Half-width of the encounter search window centred on the model-
        predicted wavefront arrival at the probe (hours).  The wavefront must
        sweep the probe inside this window for a confirmed encounter.
    encounter_tolerance_km:
        Radial tolerance around the front surface for the sweep crossing
        (km).
    icme_half_thickness_km:
        Radial half-thickness ``H`` of the ICME behind the front (km).  After
        the sweep the probe must stay inside ``[front, front - H]`` to count
        as being inside the ICME region.
    """

    start_date: str
    end_date: str
    speed_tolerance_km_s: float = 100.0
    min_shell_speed_km_s: float = 400.0
    angle_tolerance_deg: float = 10.0
    propagation_window_days: float = 9.0
    bodies: Optional[tuple[str, ...]] = None  # None -> all registry bodies

    # Propagation model: "parker_drag" (default) / "parker_ballistic" /
    # "drag" / "ballistic".
    propagation_model: str = "parker_drag"
    ambient_wind_km_s: float = 400.0       # drag model: w (km/s)
    drag_parameter_km: float = 0.2e-7      # drag model: gamma [1/km]
    v_sw_km_s: float = 400.0               # Parker spiral wind (km/s)
    launch_radius_km: float = R_SUN_KM     # front launch radius (km)

    # Strict dynamic encounter parameters.
    encounter_time_window_hours: float = 10.0
    encounter_tolerance_km: float = 1000.0
    icme_half_thickness_km: float = 0.10 * AU_KM

    # Background Parker-spiral solar-wind speeds to overlay (km/s). Empty
    # tuple disables the overlay. These describe BACKGROUND WIND geometry only
    # and never enter the ICME arrival-time calculation.
    parker_wind_speeds_km_s: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.propagation_model not in (
            "ballistic", "drag", "parker_ballistic", "parker_drag"
        ):
            raise ValueError(
                f"unknown propagation model: {self.propagation_model!r} "
                "(expected ballistic, drag, parker_ballistic, parker_drag)"
            )
        if self.speed_tolerance_km_s < 0:
            raise ValueError("speed_tolerance_km_s must be >= 0")
        if self.propagation_window_days <= 0:
            raise ValueError("propagation_window_days must be > 0")
        if self.ambient_wind_km_s <= 0:
            raise ValueError("ambient_wind_km_s must be > 0")
        if self.drag_parameter_km < 0:
            raise ValueError("drag_parameter_km must be >= 0")
        if self.v_sw_km_s <= 0:
            raise ValueError("v_sw_km_s must be > 0")
        if self.launch_radius_km < 0:
            raise ValueError("launch_radius_km must be >= 0")
        if self.encounter_time_window_hours <= 0:
            raise ValueError("encounter_time_window_hours must be > 0")
        if self.encounter_tolerance_km < 0:
            raise ValueError("encounter_tolerance_km must be >= 0")
        if self.icme_half_thickness_km <= 0:
            raise ValueError("icme_half_thickness_km must be > 0")


@dataclass
class BodyEncounter:
    """Wavefront-based encounter of one body by one ICME.

    ``enter`` / ``exit`` describe the interval during which the probe actually
    sits **inside the ICME region** (behind the swept front, within the
    angular cap).  ``sweep_*`` fields are the wavefront-sweep diagnostics: the
    time the front crossed the probe, the probe distance at that moment, the
    local front speed and the probe-to-axis angular separation.

    ``verdict`` is ``"confirmed"`` only when the strict dynamic test passed:
    the Parker-propagating wavefront swept across the probe inside the
    encounter window *and* the probe remained inside the ICME region
    afterwards.
    """

    body: str
    enter_index: int
    exit_index: int
    enter_time: str
    exit_time: str
    enter_radius_km: float
    exit_radius_km: float
    n_points: int
    # --- wavefront sweep diagnostics (new strict determination) ----------- #
    verdict: str = "confirmed"
    sweep_time: str = ""
    sweep_index: int = -1
    sweep_radius_km: float = 0.0
    front_speed_km_s: float = 0.0
    angular_separation_deg: float = 0.0
    tolerance_km: float = 1000.0


@dataclass
class CMEEncounter:
    event: CMEEvent
    bodies: dict[str, BodyEncounter] = field(default_factory=dict)

    @property
    def has_match(self) -> bool:
        return bool(self.bodies)


@dataclass
class SearchResult:
    parameters: SearchParameters
    events: list[CMEEvent]
    # body key -> preprocess.coordinates.EphemerisPoints
    ephemeris: dict[str, Any]
    encounters: list[CMEEncounter]

    def indexed(self) -> dict[int, CMEEncounter]:
        return {i: enc for i, enc in enumerate(self.encounters)}
