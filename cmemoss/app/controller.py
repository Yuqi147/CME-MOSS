"""Backend controller: keeps blocking I/O off the GUI thread.

The Tkinter layer never performs network access or pyspedas calls itself. It
submits jobs here; worker threads run them and push results onto a queue that
the GUI drains on its own event loop (``poll`` via ``after``), so all widget
updates happen on the Tk thread.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable, Optional

from cmemoss.analysis.encounter import EncounterSearch
from cmemoss.data.insitu.service import InsituDataService
from cmemoss.domain import SearchParameters, SearchResult
from cmemoss.preprocess.timeseries import TimeSeries

# callback signature: callback(success: bool, payload: result | exception)
JobCallback = Callable[[bool, object], None]


class AnalysisController:
    def __init__(
        self,
        search_engine: Optional[EncounterSearch] = None,
        insitu_service: Optional[InsituDataService] = None,
    ) -> None:
        self._search = search_engine or EncounterSearch()
        self._insitu = insitu_service or InsituDataService()
        self._queue: "queue.Queue[tuple[JobCallback, bool, object]]" = queue.Queue()

    # ------------------------------------------------------------------ #
    def poll(self) -> None:
        """Drain completed jobs; call periodically from the UI event loop."""
        while True:
            try:
                callback, ok, payload = self._queue.get_nowait()
            except queue.Empty:
                return
            try:
                callback(ok, payload)
            except Exception as exc:  # a broken callback must not kill polling
                print(f"[controller] UI callback error: {exc}")

    def _submit(self, fn, callback: JobCallback) -> None:
        def worker() -> None:
            try:
                self._queue.put((callback, True, fn()))
            except Exception as exc:  # surface every failure to the UI thread
                self._queue.put((callback, False, exc))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    def start_search(self, params: SearchParameters,
                     callback: JobCallback) -> None:
        self._submit(lambda: self._search.run(params), callback)

    def start_load_series(
        self,
        body: str,
        kind: str,
        start_iso: str,
        end_iso: str,
        callback: JobCallback,
        *,
        electron_density: bool = False,
    ) -> None:
        self._submit(
            lambda: self._insitu.get_series(
                body, kind, start_iso, end_iso,
                electron_density=electron_density,
            ),
            callback,
        )

    # Synchronous, local-only helpers (no network worth offloading). ------ #
    @staticmethod
    def export_report(result: SearchResult, directory: str = "."):
        from cmemoss.export.report import write_legacy_report

        return write_legacy_report(result, directory)

    @staticmethod
    def export_json(result: SearchResult, path: str):
        from cmemoss.export.report import write_json

        return write_json(result, path)
