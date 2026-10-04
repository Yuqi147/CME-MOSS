"""Import smoke tests for layers that should load without heavy extras.

matplotlib and pyspedas must NOT be required to import the GUI module or
controller (they are imported lazily at use time).
"""

import importlib

import pytest


def test_controller_imports_without_pyspedas():
    controller = importlib.import_module("cmemoss.app.controller")
    assert hasattr(controller, "AnalysisController")


def test_gui_module_imports_tkinter_only():
    pytest.importorskip("tkinter")
    gui = importlib.import_module("cmemoss.app.gui")
    assert hasattr(gui, "CMEMossApp")
    assert hasattr(gui, "run")


def test_insitu_service_imports_without_pyspedas():
    service = importlib.import_module("cmemoss.data.insitu.service")
    assert hasattr(service, "InsituDataService")
