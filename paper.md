---
title: 'CME-MOSS: multi-spacecraft analysis of ICME propagation and wavefront encounters'
tags:
  - heliophysics
  - space weather
  - coronal mass ejections
  - ICME propagation
  - Parker spiral
  - solar wind
  - multi-spacecraft analysis
  - scientific visualization
authors:
  - name: "CME-MOSS contributors"   # placeholder: replace with the submitting author(s)
    orcid: 0000-0000-0000-0000     # placeholder: must be a real ORCID at submission
    affiliation: 1
affiliations:
  - name: "To be completed by the authors"   # placeholder
    index: 1
date: 22 September 2026
doi: 10.21105/joss.00000          # placeholder: assigned by JOSS upon acceptance
bibliography: paper.bib
---

# Summary

The Sun occasionally releases enormous, magnetized clouds of plasma into
interplanetary space. When such a cloud — observed near the Sun as a coronal
mass ejection (CME) and in the heliosphere as an interplanetary CME (ICME) —
expands past a spacecraft or a planet, it compresses the surrounding magnetic
field and plasma, which can disturb the local space environment. A basic
question in heliophysics and space-weather research is therefore: *which
spacecraft or planets does a given CME actually encounter, and when?*

CME-MOSS (Coronal Mass Ejection — Multiple Objects Search Software) is an
open-source Python framework that answers this question with one reproducible
pipeline. It combines four ingredients: (1) CME candidates from the NASA CCMC
DONKI catalog; (2) analytic propagation of the ICME front through the inner
heliosphere, following the Parker-spiral background-flow geometry and
including drag-based deceleration toward (or acceleration to) the ambient
solar wind; (3) a **strict, dynamic encounter test** — a body is reported as
encountering the ICME only when the propagating wavefront actually sweeps
across it inside a user-specified time window and the body then remains inside
the ICME's finite spatial region; and (4) scientific visualization of the
orbit, cone and wavefront geometry together with in-situ measurements.
The same analysis can be run from a desktop GUI, a command-line interface, or
the Python API, and every run is fully defined by a serialisable parameter
object, making studies reproducible and propagation models directly
comparable.

# Statement of Need

ICME arrival and encounter studies are typically assembled from a chain of
independent pieces: a catalog query for CME parameters (e.g., DONKI), ephemeris
services for spacecraft and planetary trajectories (e.g., JPL Horizons), a
propagation model for the ICME front, an encounter criterion, and plotting
code. Each step usually lives in a separate script with its own conventions,
so reproducing an analysis — or comparing how the result depends on the
propagation model — requires manual bookkeeping.

A second, more fundamental issue is the encounter criterion itself. Many
studies flag a spacecraft if its trajectory comes geometrically close to a
CME's cone axis, or if the orbit intersects a static cone. Such criteria do
not respect causality: a trajectory that passes through the region a CME
*will* occupy, or one whose radial crossing happens before the wavefront
arrives, is reported as an "encounter" even though the ICME never reaches the
spacecraft. CME-MOSS was written to replace these static tests with a
space-time one: the wavefront position and speed are computed at every
ephemeris sample, and an encounter requires the wavefront to sweep across the
probe and the probe to remain inside the ICME region afterwards. By exposing
the propagation model and every velocity-evolution, ICME-scale and encounter
parameter in a single `SearchParameters` object — adjustable from the GUI, the
CLI, or the Python API — CME-MOSS turns a multi-script, hard-to-audit analysis
into a reproducible, auditable workflow.

# State of the Field

Heliospheric ICME modeling spans two families. Full three-dimensional
magnetohydrodynamic (MHD) models such as WSA-ENLIL and EUHFORIA
[@pomoell2018] provide global context but are computationally expensive and
are usually operated by dedicated forecasting groups. At the lighter end, the
analytic Drag-Based Model (DBM) [@vrsnak2013; @cargill2004] — rooted in
observed ICME deceleration and acceleration toward the solar-wind speed
[@gopalswamy2001] — is widely used for arrival-time estimates. CME-MOSS
belongs to the analytic family: it uses the two-branch DBM for the radial
front and embeds the front axis in the Parker-spiral background-flow geometry
[@parker1958], which analytic tools that assume radial propagation omit.

The data and software ecosystem provides the building blocks: the DONKI
catalog for CME parameters [@donki], JPL Horizons for ephemerides
[@horizons], CDAWeb and the `pyspedas` package for in-situ data
[@pyspedas2022; @cdawed], and the `sunpy`,
`astropy`, `numpy` and `matplotlib` ecosystem for coordinate handling and
visualization [@sunpy2020; @astropy2022; @numpy2020; @matplotlib2007].
What is missing from this ecosystem is a lightweight, self-contained,
multi-spacecraft encounter-analysis layer that combines catalog, ephemeris,
propagation, a strict dynamic encounter criterion, and visualization in one
reproducible workflow. CME-MOSS fills that gap: it does not replace MHD
forecasting, but offers an auditable, parameter-study-friendly complement for
rapidly screening many CME events against many spacecraft.

# Software Design

CME-MOSS follows a strictly layered architecture in which imports point only
downward: data I/O → preprocessing → physics → analysis → visualization →
application (GUI/CLI). Shared dependency-light dataclasses in `cmemoss.domain`
(`CMEEvent`, `SearchParameters`, `BodyEncounter`, `SearchResult`) define the
contract between layers.

**Data layer.** The DONKI CMEAnalysis catalog is queried over the requested
date window (`cmemoss.data.donki`); spacecraft and planetary trajectories come
from the NASA/JPL Horizons API (`cmemoss.data.ephemeris`). Both are cached
(memory and disk, `~/.cmemoss/`, keyed by exact request) so repeated runs and
model comparisons avoid redundant network traffic. An optional in-situ layer
(`cmemoss.data.insitu`, requiring the `pyspedas` extra) downloads
magnetic-field, velocity, density and temperature data for PSP, Solar Orbiter,
STEREO-A, WIND and ACE.

**Physics layer.** Three pure, vectorised modules implement the models.
`cmemoss.physics.cone` provides great-circle (haversine) angular geometry.
`cmemoss.physics.parker` implements the Parker-spiral background flow
[@parker1958]: spiral longitude as a function of distance and wind speed,
spiral angle, travel time, and ballistic footpoint mapping. `cmemoss.physics.wavefront` combines these
into the ICME model used by the encounter test: the
front radius evolves with the two-branch DBM,
`v(t) = w + (v0−w)/(1+γ|v0−w|t)` with `r(t)` integrated analytically
(regular for both `v0>w` and `v0<w`) [@vrsnak2013]; the front axis bends as
`lon_axis(r) = lon0 − Ω(r−r0)/v_sw`; and the ICME occupies a finite region —
an angular cap of the catalog cone half-width around the bent axis and a
radial half-thickness `H` behind the front. Four model variants select whether
the drag evolution and/or the Parker bending are enabled (`parker_drag`,
`parker_ballistic`, `drag`, `ballistic`), enabling controlled model
comparison. The background-flow Parker spiral itself is used for
connectivity and visualization only; it never enters arrival-time
calculations.

**Analysis layer.** `cmemoss.analysis.encounter` implements the strict
space-time encounter pipeline per (event, body): a coarse time filter over the
propagation window (default 9 days), coarse angular and radial screens, then
the analytic Parker propagation evaluated at every ephemeris sample. The
radial gap `r_front − r_probe` is tracked: a confirmed encounter requires the
gap to cross from negative to positive (a wavefront sweep) within the
encounter time window (default 10 h), crossing ±a radial tolerance (default
1000 km), and afterwards the probe must remain inside the ICME region
(`0 ≤ gap ≤ H` within the angular cap). Sweep times are refined by root
finding between samples, and diagnostics (sweep time, front speed at sweep)
are reported per encounter. Geometry intersection, mere proximity, or entering
the region without a wavefront sweep are explicitly rejected, and this
behaviour is locked in by dedicated tests.

**Visualization layer.** `cmemoss.visualization` produces polar orbit/cone/
wavefront maps — two bent lateral boundaries, a curved leading wavefront and
the filled ICME body, with optional Parker-spiral guide lines — and
multi-panel in-situ time-series figures. The application layer provides a
threaded controller (`cmemoss.app.controller`) so the GUI never blocks on
network I/O, and a research-workflow GUI (`cmemoss.app.gui`) whose pages follow
Data/Event → Propagation → ICME/Encounter → Orbit/Cone Map →
Visualization/Export; the GUI contains no scientific logic itself. All
heavy loops are vectorised with `numpy`; no Python-level per-sample loops
remain except the root-finding refinement.

**Testing.** The suite (`pytest`, 60 tests, offline) covers the DBM branches
and limits, Parker-spiral geometry and footpoint round-trips, cone geometry,
the strict-encounter accept/reject cases (including the rejection of static
intersections), parsing, config/export round-trips, controller threading,
importability without the optional `pyspedas` stack, and headless figure
rendering.

# Research Impact Statement

CME-MOSS directly supports ICME arrival and propagation studies: the four
propagation models let a researcher quantify how the encounter outcome depends
on velocity evolution and background-flow geometry for the same event.
Multi-spacecraft encounter analysis — screening a catalog of events against
missions such as Parker Solar Probe, Solar Orbiter, BepiColombo, STEREO-A,
Mercury, Earth (L1) and Mars — becomes a single parameterised search whose
results are exported as reproducible JSON. The strict dynamic criterion
prevents the false positives of static cone tests, which matters for event
selection and for comparing ICME candidates against in-situ observations. The
software also supports solar-wind environment studies through its Parker
background-flow geometry and on-demand overlay lines. The authors are not
aware of published scientific results produced with this software yet; the
tool is provided as a reusable research instrument rather than as a claim of
validated forecasting performance.

# AI Usage Disclosure

The code and documentation of CME-MOSS were developed with the assistance of
generative AI (the Doubao assistant, ByteDance; model version not pinned, as
the service updates). AI assistance covered: drafting and refactoring of
Python modules (physics, encounter analysis, GUI), test scaffolding, the
README and this paper. Human authors reviewed, edited and validated all
AI-assisted outputs: every scientific model, default parameter and the
encounter criterion were designed and checked by the authors; AI-generated
code was verified by code review, the 60-test offline suite, example runs
(`demo_wavefront_encounter.py`), and visual inspection of rendered figures;
all functional statements in this paper were checked against the repository.

# Acknowledgements

CME-MOSS uses data and services from the NASA Community Coordinated Modeling
Center (DONKI CME catalog), NASA/JPL Solar System Dynamics (Horizons
ephemerides) and the NASA Space Physics Data Facility (CDAWeb in-situ data via
`pyspedas`). It builds on the open-source ecosystem of `sunpy`, `astropy`,
`numpy`, `matplotlib` and `pyspedas`. The pre-refactor flat-file
implementation is preserved under `legacy/` for scientific traceability.

# References
