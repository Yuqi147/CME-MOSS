"""Controller marshals worker results back to the caller thread via a queue."""

import threading

from cmemoss.app.controller import AnalysisController
from cmemoss.domain import (
    BodyEncounter,
    CMEEncounter,
    CMEEvent,
    SearchParameters,
    SearchResult,
)


class _FakeEngine:
    def __init__(self, result):
        self._result = result
        self.thread_name = None

    def run(self, params):
        self.thread_name = threading.current_thread().name
        return self._result


def _result():
    event = CMEEvent("t", 0, 0, 30, 800, "2020-01-01T00:00:00", "id",
                     "s", "f", "S")
    return SearchResult(
        SearchParameters("2020-01-01", "2020-01-02"),
        [event], {}, [CMEEncounter(event, {})],
    )


def test_search_runs_off_thread_and_polls_result():
    result = _result()
    engine = _FakeEngine(result)
    controller = AnalysisController(search_engine=engine,
                                    insitu_service=object())  # type: ignore[arg-type]

    received = []
    done = threading.Event()

    def cb(ok, payload):
        received.append((ok, payload))
        done.set()

    controller.start_search(result.parameters, cb)
    # Simulate the Tk event loop that drains the controller queue.
    for _ in range(100):
        controller.poll()
        if done.wait(0.05):
            break
    assert done.is_set(), "worker did not finish"

    assert len(received) == 1
    ok, payload = received[0]
    assert ok and payload is result
    assert engine.thread_name != threading.current_thread().name


def test_worker_exception_surfaces_through_poll():
    class Boom(_FakeEngine):
        def run(self, params):
            raise RuntimeError("network down")

    controller = AnalysisController(search_engine=Boom(None),  # type: ignore[arg-type]
                                    insitu_service=object())  # type: ignore[arg-type]
    received = []
    done = threading.Event()
    controller.start_search(SearchParameters("2020-01-01", "2020-01-02"),
                            lambda ok, p: (received.append((ok, p)), done.set()))
    for _ in range(100):
        controller.poll()
        if done.wait(0.05):
            break
    assert done.is_set()
    ok, payload = received[0]
    assert not ok and isinstance(payload, RuntimeError)
