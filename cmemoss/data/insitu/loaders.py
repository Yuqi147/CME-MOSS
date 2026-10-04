"""Declarative mission/variable registry for in-situ data.

Instead of seven loader classes with four copied methods each, every mission's
mapping from a physical *kind* of measurement to (a) the pyspedas call(s) that
fetch the instrument product and (b) the resulting tplot variable is one row
of :data:`MISSION_REGISTRY`.

Conventions
-----------
* ``kind`` is one of ``mag / vel / dens / temp``.
* Components are RTN for PSP, Solar Orbiter and STEREO-A; GSE for WIND/ACE.
* Units are *not* hardcoded here - they are read from pytplot at load time so
  an instrument calibration change cannot silently mislabel a plot.

Science note (STEREO-A temperature): the legacy ``load_temp_data`` downloaded
SEPT, an energetic electron/proton telescope, while plotting
``proton_temperature``. PLASTIC is the correct source for the bulk proton
temperature and is what is wired here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class PyspedasCall:
    """One ``pyspedas.projects.<module>.<func>(trange=..., time_clip=True, ...)``."""

    module: str
    func: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MeasurementSpec:
    kind: str
    calls: tuple[PyspedasCall, ...]
    tplot_variable: str
    components: Optional[tuple[str, ...]]  # None => scalar
    description: str = ""


def _c(module: str, func: str, **kwargs: Any) -> PyspedasCall:
    return PyspedasCall(module, func, kwargs)


# Body key -> kind -> measurement specification
MISSION_REGISTRY: dict[str, dict[str, MeasurementSpec]] = {
    "PSP": {
        "mag": MeasurementSpec(
            "mag", (_c("psp", "fields", datatype="mag_RTN_4_Sa_per_Cyc"),),
            "psp_fld_l2_mag_RTN_4_Sa_per_Cyc", ("Br", "Bt", "Bn"),
            "FIELDS magnetic field, RTN"),
        "vel": MeasurementSpec(
            "vel", (_c("psp", "spi"),),
            "psp_spi_VEL_RTN_SUN", ("Vr", "Vt", "Vn"),
            "SWEAP/SPI proton bulk velocity, RTN"),
        "dens": MeasurementSpec(
            "dens", (_c("psp", "spi"),),
            "psp_spi_DENS", None, "SWEAP/SPI ion number density"),
        "temp": MeasurementSpec(
            "temp", (_c("psp", "spi"),),
            "psp_spi_TEMP", None, "SWEAP/SPI ion temperature"),
    },
    "SolO": {
        "mag": MeasurementSpec(
            "mag", (_c("solo", "mag", datatype="rtn-normal"),),
            "B_RTN", ("Br", "Bt", "Bn"), "MAG magnetic field, RTN"),
        "vel": MeasurementSpec(
            "vel", (_c("solo", "swa", datatype="pas-grnd-mom"),),
            "V_RTN", ("Vr", "Vt", "Vn"), "SWA/PAS proton velocity, RTN"),
        "dens": MeasurementSpec(
            "dens", (_c("solo", "swa", datatype="pas-grnd-mom"),),
            "N", None, "SWA/PAS number density"),
        "temp": MeasurementSpec(
            "temp", (_c("solo", "swa", datatype="pas-grnd-mom"),),
            "T", None, "SWA/PAS temperature"),
    },
    "SA": {
        "mag": MeasurementSpec(
            "mag", (_c("stereo", "mag"),),
            "BFIELD", ("Br", "Bt", "Bn"), "IMPACT/MAG magnetic field, RTN"),
        "vel": MeasurementSpec(
            "vel", (_c("stereo", "plastic"),),
            "proton_bulk_speed", None, "PLASTIC proton bulk speed"),
        "dens": MeasurementSpec(
            "dens", (_c("stereo", "plastic"),),
            "proton_number_density", None, "PLASTIC proton number density"),
        "temp": MeasurementSpec(
            "temp", (_c("stereo", "plastic"),),
            "proton_temperature", None, "PLASTIC proton temperature"),
    },
    "WIND": {
        "mag": MeasurementSpec(
            "mag", (_c("wind", "mfi"),),
            "BGSE", ("Bx", "By", "Bz"), "MFI magnetic field, GSE"),
        "dens": MeasurementSpec(
            "dens", (_c("wind", "swe"),),
            "NcElec", None, "SWE electron number density"),
        "temp": MeasurementSpec(
            "temp", (_c("wind", "swe"),),
            "TcElec", None, "SWE electron temperature"),
    },
    "ACE": {
        "mag": MeasurementSpec(
            "mag", (_c("ace", "mfi"),),
            "BGSEc", ("Bx", "By", "Bz"), "MAG magnetic field, GSE"),
        "vel": MeasurementSpec(
            "vel", (_c("ace", "swe"),),
            "V_GSE", ("Vx", "Vy", "Vz"), "SWEPAM proton velocity, GSE"),
        "dens": MeasurementSpec(
            "dens", (_c("ace", "swe"),),
            "Np", None, "SWEPAM proton number density"),
        "temp": MeasurementSpec(
            "temp", (_c("ace", "swe"),),
            "Tpr", None, "SWEPAM proton temperature"),
    },
}

# Earth L1 composite: magnetic field from WIND, plasma from ACE (matches the
# variable mapping the legacy GUI used for "Earth").
MISSION_REGISTRY["Earth"] = {
    "mag": MISSION_REGISTRY["WIND"]["mag"],
    "vel": MISSION_REGISTRY["ACE"]["vel"],
    "dens": MISSION_REGISTRY["ACE"]["dens"],
    "temp": MISSION_REGISTRY["ACE"]["temp"],
}

# PSP additionally exposes electron density from the FIELDS quasi-thermal
# noise receiver.
PSP_ELECTRON_DENSITY = MeasurementSpec(
    "dens",
    (_c("psp", "spi"), _c("psp", "fields", datatype="sqtn_rfs_V1V2", level="l3")),
    "electron_density", None, "FIELDS/QTN electron density",
)

MEASUREMENT_KINDS = ("mag", "vel", "dens", "temp")


class UnsupportedMeasurement(RuntimeError):
    """A mission does not provide the requested measurement (e.g. WIND velocity,
    MAVEN, which is not yet wired to pyspedas)."""


def get_spec(body: str, kind: str) -> MeasurementSpec:
    if body not in MISSION_REGISTRY:
        raise UnsupportedMeasurement(
            f"in-situ data for {body!r} are not available"
        )
    table = MISSION_REGISTRY[body]
    if kind not in table:
        raise UnsupportedMeasurement(f"{body!r} does not provide {kind!r} data")
    return table[kind]
