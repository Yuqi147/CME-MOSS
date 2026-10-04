"""Offline demonstration of the strict Parker-wavefront encounter pipeline.

Uses the real 2022-09-05T16:36 CME event (lon=177, lat=-25, half=60,
v=1377 km/s) from the original example run and synthetic stationary probes at
realistic positions:

* PSP at ~0.068 AU on the source axis  - the original example "encounter",
  now re-evaluated with the strict dynamic test (sweep + region membership);
* a probe magnetically connected at 1 AU (on the Parker-bent front axis);
* Earth at 1 AU (lon ~ 0)               - swept radially but far outside the
  angular cap: must be rejected.

No network access is needed: catalog and ephemeris are injected as fakes.
Run:  python demo_wavefront_encounter.py
"""

from __future__ import annotations

import numpy as np

from cmemoss.analysis.encounter import EncounterSearch
from cmemoss.constants import AU_KM, R_SUN_KM
from cmemoss.domain import CMEEvent, SearchParameters
from cmemoss.physics import wavefront
from cmemoss.preprocess.coordinates import EphemerisPoints

EVENT = CMEEvent(
    trigger_time="2022-09-05T19:03",
    lat_deg=-25, lon_deg=177, half_width_deg=60, speed_km_s=1377,
    event_time="2022-09-05T16:36:00",
    cme_id="CME-001", source="M2M_CATALOG", catalog_flag="true",
    cme_type="LE",
)

OUT_DIR = "runs"


class _FakeTime:
    def __init__(self, unix):
        self.unix = np.asarray(unix, dtype=float)


def _probe(body_key, lon, lat, r_km, cadence_s=3600.0, days=9.0,
           t0_unix=None):
    t = t0_unix + np.arange(0.0, days * 86_400.0, cadence_s)
    n = t.size
    return EphemerisPoints(
        body_key=body_key, obstime=_FakeTime(t),
        lon_deg=np.full(n, lon), lat_deg=np.full(n, lat),
        r_km=np.full(n, r_km), cadence=f"{cadence_s / 60:.0f}m",
    )


def _build_ephemeris(t0_unix):
    psp_r_km = 1.0237e7  # PSP heliocentric distance at the event (~0.068 AU)
    axis_1au = float(
        wavefront.axis_longitude_deg(AU_KM, EVENT.lon_deg, 400.0, R_SUN_KM)
    )
    return {
        # Original example target: PSP near the Sun, on the source axis.
        "PSP": _probe("PSP", EVENT.lon_deg, EVENT.lat_deg, psp_r_km,
                      cadence_s=900.0, t0_unix=t0_unix),
        # Magnetically connected probe at 1 AU on the bent front axis.
        "connected": _probe("connected", axis_1au, EVENT.lat_deg, AU_KM,
                            t0_unix=t0_unix),
        # Earth at 1 AU, lon ~ 0 (Sun-Earth line).
        "Earth": _probe("Earth", 0.0, 0.0, AU_KM, t0_unix=t0_unix),
    }


def _params():
    return SearchParameters(
        start_date="2022-09-05", end_date="2022-09-06",
        propagation_model="parker_drag",
        ambient_wind_km_s=400.0,
        drag_parameter_km=0.2e-7,
        v_sw_km_s=400.0,
        launch_radius_km=R_SUN_KM,
        encounter_time_window_hours=10.0,
        encounter_tolerance_km=1000.0,
        icme_half_thickness_km=0.10 * AU_KM,
        angle_tolerance_deg=10.0,
        # No background speed-reference spirals in the map figure: the plot
        # shows only the ICME geometry (boundaries + curved wavefront + body).
        parker_wind_speeds_km_s=(),
        bodies=("PSP", "connected", "Earth"),
    )


def main() -> None:
    from astropy.time import Time

    from cmemoss.export.report import write_json

    t0_unix = float(Time(EVENT.event_time, format="isot", scale="utc").unix)
    params = _params()
    ephemeris = _build_ephemeris(t0_unix)

    search = EncounterSearch(
        catalog_query=lambda start, end: [EVENT],
        ephemeris_service=_FakeService(ephemeris),
    )
    result = search.run(params)

    print("=" * 78)
    print(f"CME {EVENT.event_time}  lon={EVENT.lon_deg} lat={EVENT.lat_deg} "
          f"half={EVENT.half_width_deg} v={EVENT.speed_km_s} km/s")
    print(f"model={params.propagation_model}  w={params.ambient_wind_km_s} "
          f"gamma={params.drag_parameter_km:g}  v_sw={params.v_sw_km_s} "
          f"r0={params.launch_radius_km / R_SUN_KM:.2f} Rsun")
    print(f"encounter window={params.encounter_time_window_hours:g} h  "
          f"tolerance={params.encounter_tolerance_km:g} km  "
          f"thickness={params.icme_half_thickness_km / AU_KM:.3f} AU")
    print("=" * 78)

    enc = result.encounters[0]
    for body_key in ("PSP", "connected", "Earth"):
        b = enc.bodies.get(body_key)
        if b is None:
            print(f"\n{body_key:>10}:  NO CONFIRMED ENCOUNTER "
                  f"(rejected by strict wavefront test)")
            continue
        print(f"\n{body_key:>10}:  {b.verdict.upper()} ENCOUNTER")
        print(f"           sweep        : {b.sweep_time}  "
              f"(r = {b.sweep_radius_km / 1e6:.2f}e6 km, "
              f"v_front = {b.front_speed_km_s:.0f} km/s, "
              f"sep = {b.angular_separation_deg:.1f} deg)")
        print(f"           in ICME region: {b.enter_time} -> {b.exit_time}  "
              f"({b.n_points} samples)")
        print(f"           front r(enter) : {b.enter_radius_km / 1e6:.2f}e6 km")

    import os

    write_json(result, os.path.join(OUT_DIR, "result_wavefront_demo.json"))
    print(f"\njson: runs/result_wavefront_demo.json")

    # --- polar wavefront map ------------------------------------------- #
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from cmemoss.visualization.encounter_plot import make_encounter_figure

    # The figure shows the ICME geometry only: two lateral boundary lines,
    # the curved leading wavefront and the filled ICME body.  The "connected"
    # synthetic probe is a single dot (no geometric meaning) and its black
    # fallback colour only adds noise - it stays in the encounter data / json
    # but is excluded from the map.  Same for the old speed-reference lines.
    map_ephemeris = {k: v for k, v in ephemeris.items() if k != "connected"}
    fig = make_encounter_figure(EVENT, enc.bodies, map_ephemeris, params)
    fig.suptitle("Strict Parker-wavefront encounter map", y=0.98)
    map_path = os.path.join(OUT_DIR, "encounter_wavefront_demo.png")
    fig.savefig(map_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"figure: {map_path}")

    # --- sweep diagnostics for PSP ------------------------------------- #
    fig2, axes = plt.subplots(3, 1, figsize=(9.5, 9), sharex=True)
    psp = ephemeris["PSP"]
    t = psp.unix
    dt = t - t0_unix
    r_front = wavefront.front_radius_km(
        dt, EVENT.speed_km_s, params.propagation_model,
        params.ambient_wind_km_s, params.drag_parameter_km,
        params.launch_radius_km,
    )
    gap = r_front - psp.r_km
    sep = wavefront.angular_separation_to_axis_deg(
        psp.lon_deg, psp.lat_deg, psp.r_km,
        EVENT.lon_deg, EVENT.lat_deg, params.v_sw_km_s,
        params.launch_radius_km,
    )
    hours = dt / 3600.0
    sweep_h = 0.0
    b = enc.bodies.get("PSP")
    if b is not None:
        sweep_h = (float(Time(b.sweep_time, scale="utc").unix) - t0_unix) / 3600.0

    ax = axes[0]
    ax.plot(hours, r_front / AU_KM, label="r_front(t) (Parker drag)",
            color="orange", lw=1.6)
    ax.axhline(psp.r_km[0] / AU_KM, color="purple", ls="--",
               label="PSP r (0.068 AU)")
    if b is not None:
        ax.axvline(sweep_h, color="k", ls=":", lw=1.2)
        ax.plot(sweep_h, psp.r_km[0] / AU_KM, "kx", ms=9, mew=2)
    ax.set_ylabel("r (AU)")
    ax.legend(fontsize=8)
    ax.set_title("PSP: Parker wavefront reaches the probe "
                 f"(sweep at t = {sweep_h:.2f} h)")

    ax = axes[1]
    ax.plot(hours, gap / 1e6, color="tab:blue", lw=1.4, label="gap = r_front - r_probe")
    ax.axhline(0.0, color="k", lw=0.8)
    ax.axhline(params.encounter_tolerance_km / 1e6, color="g", ls=":",
               label=f"sweep tolerance ±{params.encounter_tolerance_km / 1e6:.2g} Mm")
    ax.axhline(-params.encounter_tolerance_km / 1e6, color="g", ls=":")
    ax.axhline(params.icme_half_thickness_km / 1e6, color="r", ls="--",
               label=f"ICME region H = {params.icme_half_thickness_km / 1e6:.1f} Mm")
    ax.fill_between(hours, 0, params.icme_half_thickness_km / 1e6,
                    color="red", alpha=0.10, label="ICME region")
    if b is not None:
        ax.axvline(sweep_h, color="k", ls=":", lw=1.2)
        ax.plot(sweep_h, 0.0, "kx", ms=9, mew=2)
        ax.axvspan((float(Time(b.enter_time, scale="utc").unix) - t0_unix) / 3600.0,
                   (float(Time(b.exit_time, scale="utc").unix) - t0_unix) / 3600.0,
                   color="purple", alpha=0.15, label="confirmed in-region")
    ax.set_ylabel("gap (Mm)")
    ax.legend(fontsize=8)
    ax.set_title("Wavefront sweep: gap crosses 0, then stays inside the region")

    ax = axes[2]
    ax.plot(hours, sep, color="tab:green", lw=1.2, label="probe-to-axis angle")
    ax.axhline(EVENT.half_width_deg + params.angle_tolerance_deg,
               color="k", ls="--", label="cone limit (half + tol)")
    ax.set_ylabel("sep (deg)")
    ax.set_xlabel("hours since event")
    ax.legend(fontsize=8)
    ax.set_title("Angular separation to the Parker-bent axis")

    fig2.suptitle("PSP wavefront-sweep diagnostics (2022-09-05 CME)",
                  y=0.995)
    fig2.tight_layout()
    diag_path = os.path.join(OUT_DIR, "encounter_sweep_diagnostics.png")
    fig2.savefig(diag_path, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"figure: {diag_path}")


class _FakeService:
    def __init__(self, ephemeris):
        self._ephemeris = ephemeris

    def get_many(self, span_start, span_end, bodies):
        return self._ephemeris


if __name__ == "__main__":
    main()
