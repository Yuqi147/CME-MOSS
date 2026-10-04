"""CME-MOSS - research-grade multi-spacecraft CME / ICME analysis.

Layered architecture (imports only point downward)::

    data / io  ->  preprocessing  ->  physics  ->  analysis  ->  visualization  ->  app(GUI)

Domain dataclasses live in :mod:`cmemoss.domain` and are shared by every layer.
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
