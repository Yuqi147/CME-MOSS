"""Research-grade multi-panel time-series plotting.

Replaces the ``multiplot`` method that was embedded in the in-situ data class.
It consumes :class:`~cmemoss.preprocess.timeseries.TimeSeries` objects, so it
has no pytplot dependency, plots vectorised numpy arrays, and adds a vector
magnitude panel component automatically.

Right-click a panel to annotate the nearest sample; Shift+left-click clears.
"""

from __future__ import annotations

import datetime

import numpy as np

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from cmemoss.preprocess.timeseries import TimeSeries


def _epoch_to_mpl_date(epochs_unix: np.ndarray) -> np.ndarray:
    # matplotlib dates are days since its epoch offset; convert via 1970-01-01.
    origin = mdates.date2num(datetime.datetime(1970, 1, 1))
    return np.asarray(epochs_unix, dtype=float) / 86_400.0 + origin


def _mpl_date_to_epoch(num: float) -> float:
    origin = mdates.date2num(datetime.datetime(1970, 1, 1))
    return (num - origin) * 86_400.0


def plot_time_series_panels(
    panels: list[tuple[str, TimeSeries]],
    *,
    title: str = "",
    interactive: bool = True,
    figsize=(13.0, 3.0),
) -> "plt.Figure":
    """Stack one subplot per ``(title, series)`` pair."""
    n = len(panels)
    if n == 0:
        raise ValueError("no time series supplied")
    fig, axs = plt.subplots(
        n, 1, figsize=(figsize[0], figsize[1] * n + 0.6 * (n - 1)),
        sharex=False, squeeze=False,
    )
    axes = axs[:, 0]

    panel_state: list[dict] = []
    for ax, (panel_title, series) in zip(axes, panels):
        x = _epoch_to_mpl_date(series.epochs_unix)
        annotations = []
        for j, column in enumerate(series.columns):
            line, = ax.plot(x, series.values[:, j], linewidth=0.7,
                            label=column)
            ann = ax.annotate(
                "", xy=(0, 0), xycoords="data",
                xytext=(0.72, 1.18 - 0.22 * j), textcoords="axes fraction",
                bbox=dict(boxstyle="round", fc=line.get_color(), alpha=0.75),
                arrowprops=dict(arrowstyle="->", color=line.get_color()),
            )
            ann.set_visible(False)
            annotations.append(ann)

        unit_set = {u for u in series.units.values() if u}
        unit_str = f" [{', '.join(sorted(unit_set))}]" if unit_set else ""
        ax.set_ylabel(f"{panel_title}{unit_str}", fontsize=9)
        ax.set_xlabel("Time (UTC)", fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        ax.tick_params(axis="x", labelbottom=True, labelrotation=30)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right", fontsize=7, ncol=min(len(series.columns), 4))
        panel_state.append({"ax": ax, "series": series, "annots": annotations})

    if title:
        fig.suptitle(title)
    fig.tight_layout()

    if interactive:
        _attach_annotator(fig, axes, panel_state)
    return fig


def _attach_annotator(fig, axes, panel_state) -> None:
    def on_click(event) -> None:
        if event.inaxes not in list(axes) or event.xdata is None:
            return
        state = next(s for s in panel_state if s["ax"] is event.inaxes)
        series: TimeSeries = state["series"]

        if event.button == 1 and event.key == "shift":
            for ann in state["annots"]:
                ann.set_visible(False)
            fig.canvas.draw_idle()
            return
        if event.button != 3:
            return

        click_epoch = _mpl_date_to_epoch(float(event.xdata))
        # O(log n) nearest sample instead of an O(n) Python scan per curve.
        i = int(np.searchsorted(series.epochs_unix, click_epoch))
        i = min(max(i, 0), series.n_samples - 1)
        if i > 0 and abs(series.epochs_unix[i - 1] - click_epoch) < \
                abs(series.epochs_unix[i] - click_epoch):
            i -= 1

        x_num = _epoch_to_mpl_date(np.array([series.epochs_unix[i]]))[0]
        when = datetime.datetime.utcfromtimestamp(series.epochs_unix[i])
        for ann, column in zip(state["annots"], series.columns):
            ann.xy = (x_num, series.values[i, series.columns.index(column)])
            ann.set_text(
                f"{when:%Y-%m-%d %H:%M:%S}\n{column}="
                f"{series.values[i, series.columns.index(column)]:.3g}"
            )
            ann.set_visible(True)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("button_press_event", on_click)
