"""Shared plotting constants; colours/labels come from the body registry."""

from __future__ import annotations

from cmemoss.bodies import BODY_REGISTRY

# Polar map radial extent in AU.
PLOT_R_MAX_AU = 1.5

# Propagation-front cadence for the cone plot (legacy: 12 hours).
FRONT_CADENCE_HOURS = 12.0


def body_color(body_key: str) -> str:
    spec = BODY_REGISTRY.get(body_key)
    return spec.color if spec else "black"


def body_label(body_key: str) -> str:
    spec = BODY_REGISTRY.get(body_key)
    return spec.label if spec else body_key


PARKER_COLORS = ("0.35", "0.25", "0.15")
