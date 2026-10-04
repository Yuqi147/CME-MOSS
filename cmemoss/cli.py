"""Command-line entry point: ``cmemoss gui`` (default) or ``cmemoss search``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cmemoss",
                                     description="Multi-spacecraft CME analysis")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="launch the graphical application")

    s = sub.add_parser("search", help="run a Parker-wavefront encounter search headless")
    s.add_argument("--start", required=True, help="start date YYYY-MM-DD")
    s.add_argument("--end", required=True, help="end date YYYY-MM-DD")
    s.add_argument("--speed-tolerance", type=float, default=100.0,
                   help="radial speed tolerance in km/s (default 100)")
    s.add_argument("--model", choices=("ballistic", "drag", "parker_ballistic",
                                       "parker_drag"),
                   default="parker_drag")
    s.add_argument("--w", dest="wind", type=float, default=400.0,
                   help="ambient solar-wind speed for the drag evolution (km/s)")
    s.add_argument("--gamma", type=float, default=0.2e-7,
                   help="drag parameter in 1/km")
    s.add_argument("--v-sw", dest="v_sw", type=float, default=400.0,
                   help="Parker-spiral wind speed for the front-axis bend (km/s)")
    s.add_argument("--launch-radius", dest="launch_radius", type=float,
                   default=1.0,
                   help="front launch radius in solar radii (default 1.0)")
    s.add_argument("--window-hours", dest="window_hours", type=float,
                   default=10.0,
                   help="encounter search window half-width in hours "
                        "(default 10)")
    s.add_argument("--tolerance-km", dest="tolerance_km", type=float,
                   default=1000.0,
                   help="wavefront sweep radial tolerance in km (default 1000)")
    s.add_argument("--thickness-km", dest="thickness_km", type=float,
                   default=0.10 * 1.495978707e8,
                   help="ICME radial half-thickness behind the front in km "
                        "(default 0.10 AU)")
    s.add_argument("--parker", default="",
                   help="comma-separated background wind speeds for Parker "
                        "overlay metadata, e.g. '300,400,500'")
    s.add_argument("--bodies", default="",
                   help="comma-separated body keys; default: all")
    s.add_argument("--outdir", default=".", help="report output directory")
    s.add_argument("--json", dest="json_path", default="",
                   help="optional path for full JSON result")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.command in (None, "gui"):
        from cmemoss.app.gui import run

        run()
        return 0

    # --- search ------------------------------------------------------- #
    from cmemoss.analysis.encounter import EncounterSearch
    from cmemoss.constants import R_SUN_KM
    from cmemoss.domain import SearchParameters
    from cmemoss.export.report import write_json, write_legacy_report

    bodies = tuple(b.strip() for b in args.bodies.split(",") if b.strip()) or None
    parker = tuple(float(x) for x in args.parker.split(",") if x.strip())
    params = SearchParameters(
        start_date=args.start,
        end_date=args.end,
        speed_tolerance_km_s=args.speed_tolerance,
        propagation_model=args.model,
        ambient_wind_km_s=args.wind,
        drag_parameter_km=args.gamma,
        v_sw_km_s=args.v_sw,
        launch_radius_km=args.launch_radius * R_SUN_KM,
        encounter_time_window_hours=args.window_hours,
        encounter_tolerance_km=args.tolerance_km,
        icme_half_thickness_km=args.thickness_km,
        parker_wind_speeds_km_s=parker,
        bodies=bodies,
    )

    result = EncounterSearch().run(params)
    n_match = 0
    for encounter in result.encounters:
        if not encounter.has_match:
            continue
        n_match += 1
        bodies_in = ", ".join(encounter.bodies)
        print(f"{encounter.event.event_time}  "
              f"v={encounter.event.speed_km_s:5d} km/s  -> {bodies_in}")
    print(f"\n{n_match}/{len(result.encounters)} CMEs have encounters")

    report_path = write_legacy_report(result, args.outdir)
    print(f"report: {report_path}")
    if args.json_path:
        print(f"json:   {write_json(result, args.json_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
