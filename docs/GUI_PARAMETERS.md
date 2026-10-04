# GUI parameters & propagation models (code-grounded reference)

This document explains every user-facing parameter and every propagation
model **as implemented in the code**. File locations are given per item so
the statements can be checked directly. The GUI collects exactly the fields
of `SearchParameters` (`cmemoss/domain.py`); the physics lives in
`cmemoss/physics/wavefront.py`, `cmemoss/physics/parker.py` and
`cmemoss/physics/cone.py`; the strict encounter test is in
`cmemoss/analysis/encounter.py`.

---

## 1. Parameters (GUI fields -> code)

| GUI label | code field | unit | default | meaning & effect (code evidence) |
|---|---|---|---|---|
| Start date / End date | `start_date`, `end_date` | date | today | DONKI catalog query window (`EncounterSearch.run` -> `query_cme_events(start, end)`). Only CMEs whose event time lies in this window are candidates. |
| Speed tolerance | `speed_tolerance_km_s` | km/s | 100 | **Legacy only.** Used by the old radial-shell model in `physics/propagation.py` (`inner_speed = min(v - tol, min_shell_speed)`, `outer_speed = v + tol`). **It is NOT read by the strict Parker-wavefront encounter test** (`analysis/encounter.py` has no reference to it) - the GUI labels it accordingly. |
| Propagation model | `propagation_model` | - | `parker_drag` | Selects the radial speed law and the axis geometry (section 2). |
| Ambient wind w | `ambient_wind_km_s` | km/s | 400 | Target speed `w` of the drag-based model (DBM): the front relaxes toward `w` (`wavefront.dbm_speed_km_s`). Only used by `parker_drag` / `drag`. |
| Drag gamma | `drag_parameter_km` | 1/km | 0.2e-7 | Aerodynamic drag coefficient `gamma` of the DBM; relaxation timescale ~ `1/(gamma*|v0-w|)`. Only used by `parker_drag` / `drag`. |
| Spiral wind v_sw | `v_sw_km_s` | km/s | 400 | Solar-wind speed used for the **Parker-spiral bending of the front axis** (`wavefront.axis_longitude_deg` -> `parker.spiral_longitude_deg`). Can differ from `w` (different physical role). Used by `parker_drag` / `parker_ballistic`. |
| Launch r | `launch_radius_km` | input in R_sun, stored km | 1.0 R_sun | Start radius `r0` of the DBM integration and of the axis bending. Entered in solar radii; multiplied by `R_SUN_KM` in the GUI / CLI. |
| Encounter window | `encounter_time_window_hours` | h | 10 | Half-width of the window around the predicted wavefront arrival inside which the sweep must occur (`analysis/encounter.py::_encounter_window`). |
| Tolerance | `encounter_tolerance_km` | km | 1000 | Radial tolerance of the sweep test: the gap `r_front - r_probe` must cross from `< -tol` to `> +tol` between samples (`wavefront.sweep_crossing_intervals`). |
| ICME half-thickness | `icme_half_thickness_km` | km | 0.10 AU | Radial half-thickness `H` behind the front; after the sweep the probe must satisfy `0 <= gap <= H` inside the angular cap (`wavefront.in_icme_region_mask`). |
| Parker overlay wind speeds | `parker_wind_speeds_km_s` | km/s | **GUI: removed from the input page** | Background-wind speeds for the Parker-spiral **overlay lines only** (`visualization/encounter_plot.plot_parker_spirals`). Explicitly never enters the ICME arrival-time calculation (comment in `domain.py`). Now entered per-map on the Orbit / Cone Map control bar; empty input = no overlay. |
| Targets | `bodies` | - | all registry bodies | Bodies whose ephemeris is queried and tested. |

Parameters without a GUI field (fixed defaults, used by the strict test):

| field | default | meaning |
|---|---|---|
| `angle_tolerance_deg` | 10 | Additional angular cap beyond the DONKI cone half-width: `sep <= half_width + 10 deg` (`encounter.py:314`); also drawn as the tolerance band. |
| `propagation_window_days` | 9 | Coarse time filter and ephemeris/plot window after the event (`encounter.py:89`, `encounter_plot.make_encounter_figure`). |
| `min_shell_speed_km_s` | 400 | Legacy radial-shell lower speed bound (`physics/propagation.py` only). |

Relations between parameters:

- `w` and `gamma` jointly define the DBM: `v(t) = w + (v0-w)/(1 + gamma*|v0-w|*t)`.
  CMEs with `v0 > w` decelerate, `v0 < w` accelerate toward `w`.
- `v_sw` sets how strongly the axis bends with distance (`Omega*(r-r0)/v_sw`);
  a smaller `v_sw` gives a tighter spiral. It is independent of `w`.
- `r0` is the common origin of the radial law and of the bending.
- `encounter_tolerance_km` and `icme_half_thickness_km` together define the
  "swept and inside the ICME region" test; `encounter_time_window_hours` gates
  when the sweep may happen.
- `angle_tolerance_deg` widens the angular acceptance for both the verdict and
  the plotted cap.

---

## 2. Propagation models

All four models share the same building blocks (`wavefront.front_radius_km`):

| model | radial speed law | axis geometry |
|---|---|---|
| `ballistic` | constant `v0` | straight (fixed source longitude) |
| `drag` | DBM (two-branch) | straight |
| `parker_ballistic` | constant `v0` | Parker-spiral bending |
| `parker_drag` | DBM (two-branch) | Parker-spiral bending |

### 2.1 ballistic  (geometric approximation)
- Assumptions: ICME front expands radially at the catalog speed, no
  interaction with the wind, no longitudinal evolution.
- Model: `r(t) = r0 + v0*t`, axis fixed at `(lon_source, lat_source)`.
- Inputs: `v0` (catalog `speed_km_s`), `r0`.
- Path: straight radial lines; wavefront: a sun-centred circular arc at
  `r(t)` (visualisation approximation; see 2.5).
- Use: reproduction of the legacy cone-search results; speed reference.

### 2.2 drag  (physical radial model, straight cone)
- Assumptions: aerodynamic drag against the ambient wind controls the front.
- Model: two-branch DBM (Vrsnak et al. 2013),
  `v(t) = w + (v0-w)/(1 + gamma*|v0-w|*t)`; both branches (`v0>w` deceleration,
  `v0<w` acceleration) are regular for all `t >= 0`
  (`wavefront.dbm_speed_km_s`); `r(t) = r0 + w*t +- ln(1+gamma*|v0-w|*t)/gamma`.
- Inputs: `v0`, `w`, `gamma`, `r0`.
- Path: straight radial; axis fixed at the source longitude.
- Use: radial-only physics; isolate the effect of velocity evolution from the
  Parker geometry.

### 2.3 parker_ballistic  (background-flow geometry, constant speed)
- Assumptions: the ICME is embedded in the corotating background flow; its
  effective longitude bends with heliocentric distance along the Parker
  spiral (Parker 1958); no velocity evolution.
- Model: `lon_axis(r) = lon_source - Omega*(r - r0)/v_sw`
  (`wavefront.axis_longitude_deg` -> `parker.spiral_longitude_deg`; `Omega` =
  Carrington sidereal rotation, `SOLAR_ROTATION_RAD_PER_S`); `r(t) = r0 + v0*t`.
- Inputs: `v0`, `v_sw`, `r0`, source longitude/latitude.
- Path: bent (Parker-spiral) axis; the encounter geometry follows the
  background-flow geometry.
- Use: isolate the effect of axis bending from velocity evolution.

### 2.4 parker_drag  (default; background-flow geometry + DBM)
- Combines 2.2 and 2.3: bent Parker axis **and** DBM radial evolution.
- Inputs: `v0`, `w`, `gamma`, `v_sw`, `r0`.
- Path: bent axis; front speed decays/accelerates toward `w`.
- Use: default and physically most complete of the four.

### 2.5 What is physics vs. geometry / visualisation approximation
- **Physics**: DBM radial law (drag evolution); Parker-spiral axis bending as
  the corotating background-flow geometry; the finite ICME region (angular
  cap + radial half-thickness `H`); the sweep test.
- **Geometry / visualisation approximation**: the wavefront drawn as a
  sun-centred circular arc of angular width `2*half` at the computed front
  radius (`encounter_plot._arc_points`); the constant-speed (`ballistic`)
  models; the Parker-spiral overlay lines (`parker.spiral_curve`), which are
  background-wind guide lines and never modify the propagation/encounter
  result.

### 2.6 Common ground
- All models take `v0` from the catalog and `r0` from `launch_radius_km`.
- All use the same angular cap logic (`cone.angular_separation_deg`,
  haversine great-circle angle) and the same strict sweep/region verdict.
- `parker_*` models share the same axis-bending function; `*_drag` models
  share the same DBM functions. The only difference between the four is which
  combination is enabled.

---

## 3. GUI workflow (after the rework)

```
1. Data / Event  ->  2. Propagation  ->  3. ICME / Encounter
        ->  4. Orbit / Cone Map  ->  5. Visualization / Export
```

- The input page no longer shows `Parker overlay wind speeds`.
- Overlay is entered per map on the Orbit / Cone Map control bar:
  `[Open orbit / cone map] [speed(s) km/s] [Plot]`. Empty input draws no
  overlay; multiple comma-separated speeds are supported; the overlay is
  drawn with `make_encounter_figure(..., parker_wind_speeds_km_s=speeds)`
  and never changes the propagation or the encounter results.
- Old fixed 300/400/500 km/s lines are gone (the demo figure and the GUI
  input both start empty).
