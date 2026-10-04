# CME-MOSS architecture

## 1. Layered design

```
Data / IO          data/donki.py, data/ephemeris.py, data/insitu/*
      |
Preprocessing      preprocess/coordinates.py, preprocess/timeseries.py
      |
Physical models    physics/cone.py, physics/wavefront.py, physics/parker.py
      |
Analysis           analysis/encounter.py
      |
Visualization      visualization/encounter_plot.py, visualization/timeseries_plot.py
      |
Application        app/gui.py (views), app/controller.py, cli.py
```

Imports only point downward. Shared, dependency-light dataclasses live in
`domain.py`. The GUI never imports pyspedas, requests or sunpy directly and
performs no network access.

| Stage | Responsibility | Key types / modules |
|---|---|---|
| I/O | remote catalog, ephemeris, in-situ files; disk+memory cache | `data.donki`, `data.ephemeris.EphemerisService`, `data.insitu` |
| Preprocessing | frames, arrays, unit vectors, gaps, cropping | `EphemerisPoints`, `TimeSeries` |
| Physics | pure SI numpy functions, no I/O | cone / wavefront / parker |
| Analysis | strict wavefront-encounter pipeline, vectorised | `EncounterSearch`, `evaluate_wavefront_encounter` |
| Visualization | matplotlib only, consumes domain objects | `make_encounter_figure`, `plot_time_series_panels` |
| App | threading, config, widgets | `AnalysisController`, `CMEMossApp` |

## 2. Data flow

```
SearchParameters
   -> DONKI CMEAnalysis (HTTP, cached) -> list[CMEEvent]
   -> Horizons ephemeris per body (cached .npz) -> EphemerisPoints
   -> strict Parker-wavefront encounter search for every (event, body):
          coarse time -> coarse angular/radial -> candidate screen
          -> Parker propagation (drag-based velocity evolution)
          -> wavefront sweep (refined crossing) -> region membership
   -> SearchResult {events, ephemeris, encounters}
          -> legacy .txt / .json export
          -> polar wavefront map (+ Parker overlay)
          -> on-demand in-situ InsituDataService -> TimeSeries -> panels
```

## 3. Performance measures

* **No single-point KDTree.** The legacy code built a `scipy.spatial.KDTree`
  containing one CME point per event and ran nested Python loops. Angular
  membership is now a vectorised great-circle mask (`physics/cone.py`).
* **Vectorised SkyCoord conversion.** `SkyCoord.lon/lat/radius` are array
  quantities; the legacy per-coordinate Python comprehension is gone.
* **Two-level cache.** `MemoryCache` (within a run) + compressed `.npz`/text
  disk cache under `~/.cmemoss` (across runs) keyed by exact request, so
  repeat searches never re-hit DONKI or Horizons.
* **Instrument-level in-situ de-duplication.** PSP/SPI (used for velocity,
  density and temperature) is fetched at most once per window/process instead
  of once per plotted quantity.
* **Minimal intervals.** The ephemeris span and in-situ windows are derived
  from the event range / encounter enter-exit times, not whole data sets.
* **O(log n) annotation lookup** in the time-series plots.

## 4. Physics bookkeeping

* Constants (solar radius, AU, Carrington sidereal rate) in `constants.py`.
* Physics functions take SI floats/arrays (s, km, km/s, deg); astropy
  quantities live only at the I/O boundary.
* Three distinct concepts:
  * `physics/parker.py` - steady **background wind** field geometry;
  * `physics/wavefront.py` - **ICME Parker wavefront**: drag-based radial
    evolution (velocity decay/acceleration) + spiral-bent front axis + finite
    ICME region + sweep primitives;
  * `physics/cone.py` - great-circle angular geometry used by the wavefront.
* `SearchParameters.propagation_model` selects the wavefront model; the
  default is `parker_drag`. The strict encounter verdict (wavefront sweep +
  region membership) is produced by `analysis/encounter.py`.

## 5. Extending

**Add a target body** - one entry in `bodies.py` (Horizons id, launch time,
cadence, colour), and, if in-situ data exist, one declarative block in
`data/insitu/loaders.py` mapping kinds to pyspedas calls and tplot variables.

**Add a measurement product** - add a `MeasurementSpec`; no loader class or
plotting code changes are needed. The service converts the pytplot variable to
`TimeSeries` (units read from pytplot), and the plotter handles it.

## 6. Threading model

`AnalysisController` runs searches / downloads on daemon threads and pushes
`(callback, ok, payload)` onto a queue; Tk drains the queue with
`after(200 ms, poll)`, so all widget updates remain on the UI thread.

## 7. Dependencies

Core: numpy, astropy, sunpy, matplotlib, requests.
Optional `insitu`: pyspedas (CDAWeb / pytplot).
Removed from the legacy code: scipy, pandas, python-dateutil (direct use),
BeautifulSoup.
