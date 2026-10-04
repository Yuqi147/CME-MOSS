# Migration & science notes

This document lists every change from the legacy flat-file implementation
(`legacy/`) that can affect numerical results, so scientific conclusions stay
traceable. Changes with **no numerical effect** are listed separately.

## Changes that can change results

1. **Angular metric: lon/lat Euclidean -> great-circle distance.**
   Legacy: a one-point `scipy.spatial.KDTree` measured Euclidean distance in
   `(longitude, latitude)` degrees. Away from the equator one longitude degree
   is shorter than one latitude degree, so the old metric admitted/rejected
   points incorrectly at high latitudes. The new code uses the haversine
   central angle (`physics/cone.py`). Differences appear mainly near the cone
   boundary and at high |latitude|; equatorial near-axis results are
   essentially unchanged.

2. **Ephemeris time coverage unified to the propagation window (9 days).**
   Legacy: probes were sampled to `last_event + 8 d` while the encounter test
   searched to `+9 d` (the last day could never match); Mercury to `+3.5 d`,
   Earth/Mars to `+14 d`. New code samples every body to the configurable
   propagation window (default 9 d). A late Mercury encounter that the old
   coverage truncated can now appear; the extra Earth/Mars days were only used
   by the plot and are recreated on demand by the plot track.

3. **STEREO-A temperature product corrected.**
   The legacy `load_temp_data` downloaded **SEPT** (Solar Electron Proton
   Telescope - energetic particles) but the panel plotted `proton_temperature`
   (bulk thermal plasma from PLASTIC). The new loader downloads PLASTIC, which
   is the physically consistent source for the plotted variable. Previously the
   plotted variable could be missing/stale after using the temperature button.

4. **Reference Earth in the orbit map plotted at the event time.**
   Legacy `get_body_heliographic_stonyhurst('earth')` used the *current* wall-
   clock date, so the blue Earth marker was wrong for historical events. It now
   uses the CME event time. (This affects the figure, not the encounter table,
   which always used Horizons positions.)

5. **Body-track plotting window generalised.**
   Legacy "past trajectory" used a hard-coded 384-sample index (= 4 days only
   for 15-minute PSP/SolO cadence; 8 days at STEREO-A 30-minute cadence, 16
   days at hourly planet cadence). It is now a fixed physical 4-day offset for
   every cadence. The highlighted encounter segment and +1 cadence future
   extension are preserved.

## Default behaviour preserved

* **Radial shell test** is identical:
  `min(v - dv, 400) * dt <= r <= (v + dv) * dt` with default `dv = 100 km/s`
  and the 400 km/s **cap** on the inner-edge speed (`propagation.
  shell_limits_ballistic`). Note the empirical legacy semantics: the inner
  speed is capped (never exceeds 400), widening the shell for fast CMEs.
* **Angular tolerance** of +10 degrees added to the DONKI half-angle is kept
  (`SearchParameters.angle_tolerance_deg`).
* **Frame**: Heliographic Stonyhurst (heliocentric, inertial; longitude zero on
  the Sun-Earth line). DONKI source longitudes and Horizons body longitudes are
  compared directly, appropriate for a radially propagating launch direction;
  no co-rotating remapping is applied to the CME.
* **DONKI parsing** uses the same regular expression and field semantics
  (locked by `tests/test_donki_parser.py`).
* **Text report** keeps the same header and tab-separated columns.
* Default propagation model stays **ballistic/constant speed**, so default
  numerical conclusions are unchanged apart from items 1-2.

## New physics (opt-in, does not alter defaults)

* **Drag-based model** (Vrsnak et al. 2013, Solar Phys. 285, 295):
  `v(t) = w + (v0-w)/(1 + gamma(v0-w)t)`,
  `r(t) = r0 + w t + ln(1 + gamma(v0-w)t)/gamma`.
  Select with `propagation_model="drag"` and parameters `ambient_wind_km_s`
  (w), `drag_parameter_km` (gamma). The drag shell is `r_drag +/- dv*t`. It
  models the *CME transient* and is independent of the Parker spiral.

* **Parker spiral (background wind only)** - `physics/parker.py`:
  * field geometry `lon(r) = lon_foot - Omega (r-r0)/v_sw`;
  * spiral angle `tan psi = Omega (r-r0) cos(lat) / v_sw` (~47 deg at 1 AU for
    400 km/s; `Omega` is the Carrington **sidereal** rate because HGS longitudes
    are inertial);
  * ballistic footpoint back-mapping.
  It is an overlay/connectivity aid and never enters the ICME arrival-time
  criterion. Assumptions: steady, radial, constant-speed wind; frozen-in flux;
  rigid solar rotation; launch radius r0 = R_sun (configurable to the source
  surface, 2.5 R_s).

## Assumptions retained / made explicit

* CME propagates radially from the source-region longitude/latitude with no
  deflection, expansion-driven longitude drift, or interaction.
* Cone is circular; the DONKI `rad` value is treated as the cone half-angle.
* Spacecraft heliocentric distance is used as the CME travel distance
  (front launched from the Sun centre).
* Constant speed by default; use the drag model to include deceleration.
* All times UTC; distances km; angles degrees unless stated.

## Changes with no numerical effect

* scipy / pandas / python-dateutil direct usage and the unused BeautifulSoup
  import removed; pyspedas became an optional dependency.
* Repeated Horizons/DONKI downloads and repeated pyspedas instrument fetches
  eliminated via caching and per-instrument de-duplication.
* Result types are typed dataclasses; configuration is JSON-serialisable;
  longitudes/latitudes/distances converted with array SkyCoord quantities.
* GUI moved to a threaded controller; figures rendered the same way but
  matplotlib is now embedded in-app and exportable as PNG/PDF/SVG.

---

# Parker-wavefront encounter model (2026 rework)

This section documents the rework that replaced the static cone+shell test
with a strict, dynamic Parker-wavefront encounter determination. The legacy
models remain available (``ballistic`` / ``drag``) for reproducibility, but
the default and the physics behind the encounter verdict changed.

## 1. The strict encounter definition

An encounter is now a **dynamical time-space event**, not a geometric
intersection at one instant:

```
orbit-geometry intersection          != encounter
approaching the ICME                != encounter
inside the ICME region, no sweep    != encounter
wavefront sweeps the probe AND the
  probe stays in the ICME region    == confirmed encounter
```

A body is reported only with ``verdict="confirmed"`` when all of the
following hold inside the encounter time window:

1. the Parker-propagating ICME front **reaches the probe's heliocentric
   distance** and crosses it from inside to outside (radial gap
   ``r_front - r_probe`` changes from negative to positive within the sweep
   tolerance, default 1000 km);
2. the front is genuinely propagating outward (``v_front > 0``);
3. at the sweep moment the probe lies inside the ICME angular cap around the
   **bent** front axis (DONKI half-angle + tolerance);
4. after the sweep the probe remains inside the ICME effective region -
   ``0 <= r_front - r_probe <= H`` (radial half-thickness, default 0.10 AU)
   and inside the angular cap.

The old single-instant mask ``time && cone && radial-shell`` could mark a
single trajectory sample as an "encounter" without any wavefront ever passing
the probe; the new pipeline rejects all such cases.

## 2. Propagation: Parker-spiral wavefront

* **Front axis follows the background-flow geometry.** The ICME is embedded
  in the corotating solar wind, so its effective longitudinal position bends
  with heliocentric distance along the Parker spiral (connectivity /
  footpoint mapping of `physics/parker.py`):

  ``lon_axis(r) = lon_source - Omega * (r - r0) / v_sw``

  with the Carrington **sidereal** rotation rate (HGS longitudes are
  inertial). At 1 AU with ``v_sw = 400 km/s`` the axis is ~61 deg east of the
  source longitude. This is a modeling choice: the "cone" follows the
  background streamline geometry instead of a fixed inertial direction.
  ``v_sw`` is GUI-adjustable.

* **Velocity evolution (two-branch drag-based model).** The front radius
  evolves with the Vrsnak et al. (2013) drag-based model:

  ``v0 > w: v(t) = w + (v0 - w)/(1 + gamma (v0 - w) t)`` (deceleration)
  ``v0 < w: v(t) = w - (w - v0)/(1 + gamma (w - v0) t)`` (acceleration)

  so fast ICMEs relax toward the ambient wind while slow ICMEs embedded in a
  fast wind are accelerated, without the single-branch divergence. The
  constant-speed ``parker_ballistic`` branch is kept for comparison.
  Parameters ``w``, ``gamma``, launch radius ``r0`` are GUI-adjustable.

* **Finite ICME region.** The ICME occupies a spherical cap: angular
  half-width (cone + tolerance) around the bent axis and radial
  half-thickness ``H`` behind the front.

## 3. Encounter time window

The search window is centred on the model-predicted wavefront arrival at the
probe and defaults to ``encounter_time_window_hours = 10 h`` (GUI-adjustable).
The sweep must be detected inside this window, and the post-sweep region
membership is verified within it.

## 4. Defaults changed

* ``SearchParameters.propagation_model`` default: ``ballistic`` ->
  ``parker_drag`` (Parker-bent axis + drag-based velocity evolution).
* Encounter verdicts now require the wavefront sweep + region membership, so
  results differ from the legacy single-point cone-shell hits: cases where a
  probe merely intersected the static cone (e.g. inside the straight cone but
  not magnetically connected to the bent front) are no longer reported.
* New parameters: ``v_sw_km_s``, ``launch_radius_km``,
  ``encounter_time_window_hours``, ``encounter_tolerance_km``,
  ``icme_half_thickness_km``.

## 5. Pipeline & performance

Staged, vectorised pipeline in `analysis/encounter.py`:

```
coarse time filter -> coarse spatial filter (cone + radial reach)
  -> candidate screen (arrival solve, encounter window)
  -> Parker propagation (analytic front at every sample)
  -> wavefront precise calculation (gap, angular separation, front speed)
  -> sweep detection (refined crossing time by bisection)
  -> region membership -> confirmed encounter
```

All sample-level operations are numpy-vectorised; the front trajectory is
analytic (no integration grid), the exact crossing time is refined by scalar
bisection per candidate interval (typically 0-2 per body), and ephemeris /
catalog data come from the existing two-level cache, so no repeated SPICE /
orbit computation or file I/O is introduced.
