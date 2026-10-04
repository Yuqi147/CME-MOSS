"""In-situ data service: instrument-level de-duplication and uniform output.

The legacy code re-downloaded the same instrument product every time
``load_mag_data / load_vel_data / load_dens_data`` was called (PSP/SPI was
fetched three times to plot three quantities). This service executes each
unique ``(instrument, product, time window)`` call once per process and
converts pytplot variables into framework
:class:`~cmemoss.preprocess.timeseries.TimeSeries` objects.
"""

from __future__ import annotations

import importlib
from typing import Optional

from cmemoss.core.time_utils import to_date_string
from cmemoss.data.insitu.loaders import (
    MISSION_REGISTRY,
    MeasurementSpec,
    PSP_ELECTRON_DENSITY,
    PyspedasCall,
    UnsupportedMeasurement,
    get_spec,
)
from cmemoss.preprocess.timeseries import TimeSeries


class InsituDependencyMissing(ImportError):
    """Raised when pyspedas is requested but not installed."""


def _require_pyspedas():
    try:
        import pyspedas  # noqa: F401
    except ImportError as exc:
        raise InsituDependencyMissing(
            "in-situ data access requires the optional dependency pyspedas. "
            "Install with: pip install cmemoss[insitu]"
        ) from exc
    return pyspedas


class InsituDataService:
    def __init__(self) -> None:
        self._executed: set[tuple] = set()

    # ------------------------------------------------------------------ #
    def _execute(self, call: PyspedasCall, trange: tuple[str, str]) -> None:
        dedup_key = (
            call.module,
            call.func,
            tuple(sorted(call.kwargs.items())),
            trange[0],
            trange[1],
        )
        if dedup_key in self._executed:
            return
        _require_pyspedas()
        module = importlib.import_module(f"pyspedas.projects.{call.module}")
        func = getattr(module, call.func)
        func(trange=list(trange), time_clip=True, **call.kwargs)
        self._executed.add(dedup_key)

    def _load(self, spec: MeasurementSpec, start: str, end: str) -> str:
        # pyspedas trange accepts 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS';
        # normalise an ISO 'T' separator and leave plain dates untouched.
        trange = (
            start.replace("T", " ")[:19] if len(start) > 10 else to_date_string(start),
            end.replace("T", " ")[:19] if len(end) > 10 else to_date_string(end),
        )
        for call in spec.calls:
            self._execute(call, trange)
        return spec.tplot_variable

    # ------------------------------------------------------------------ #
    def get_series(
        self,
        body: str,
        kind: str,
        start: str,
        end: str,
        *,
        electron_density: bool = False,
    ) -> TimeSeries:
        """Load one measurement and return it as a :class:`TimeSeries`."""
        if electron_density:
            if body != "PSP":
                raise UnsupportedMeasurement(
                    "electron density variant is only defined for PSP"
                )
            spec: MeasurementSpec = PSP_ELECTRON_DENSITY
        else:
            spec = get_spec(body, kind)

        var_name = self._load(spec, start, end)

        from pytplot import get_data, get_units  # lazy: part of the insitu extra

        result = get_data(var_name)
        if result is None:
            raise RuntimeError(
                f"tplot variable {var_name!r} not found after loading {body} {kind}"
            )
        columns = list(spec.components) if spec.components else [spec.description
                                                                 or var_name]
        unit = self._safe_unit(get_units, var_name)
        series = TimeSeries.from_pytplot_result(result, var_name, columns, unit)
        # Automatically expose |B| / |V| for 3-component vectors.
        if spec.components and len(spec.components) == 3:
            mag_label = f"|{kind[0]}|"
            series = series.with_magnitude(spec.components, mag_label, unit)
        return series

    @staticmethod
    def _safe_unit(get_units, var_name: str) -> str:
        try:
            unit = get_units(var_name)
        except Exception:  # pragma: no cover - defensive around pytplot API
            unit = ""
        return unit if isinstance(unit, str) else str(unit or "")

    def supported_kinds(self, body: str) -> tuple[str, ...]:
        return tuple(MISSION_REGISTRY.get(body, {}).keys())
