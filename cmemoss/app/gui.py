"""Tkinter graphical front-end (research-workflow layout).

Design rule: this module contains **no science and no I/O logic**. Every
search, download and export goes through :class:`~cmemoss.app.controller.
AnalysisController`; all figures come from the visualization layer. The GUI
only collects the parameters defined in :class:`~cmemoss.domain.
SearchParameters` and displays what the backend returns.

Workflow tabs follow the research pipeline::

    Data / Event Input  ->  Propagation Parameters  ->  ICME / Encounter
        ->  Orbit / Cone Map  ->  Visualization / Export

matplotlib is imported lazily inside window constructors so the module can be
imported (and the CLI / tests run) on a minimal install.
"""

from __future__ import annotations

import datetime as _dt
import tkinter as tk
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk

from cmemoss.app.controller import AnalysisController
from cmemoss.app.project_config import load_parameters, save_parameters
from cmemoss.bodies import BODY_ORDER, BODY_REGISTRY
from cmemoss.data.insitu.loaders import MISSION_REGISTRY
from cmemoss.domain import CMEEncounter, SearchParameters, SearchResult

_KIND_LABELS = {
    "mag": ("Magnetic field", "nT"),
    "vel": ("Solar wind velocity", "km/s"),
    "dens": ("Density", ""),
    "temp": ("Temperature", ""),
}

# Propagation-model reference text (from cmemoss/physics/wavefront.py).
_MODEL_INFO = {
    "parker_drag": (
        "Parker-spiral bent axis + two-branch drag-based model (DBM, "
        "Vrsnak et al. 2013).\n\n"
        "Axis:  lon_axis(r) = lon0 - Omega*(r - r0)/v_sw   (corotating "
        "background-flow geometry)\n"
        "Speed: v(t) = w + (v0 - w)/(1 + gamma*|v0 - w|*t)  -> the front "
        "decelerates toward the ambient wind w when v0 > w and accelerates "
        "toward w when v0 < w.\n\nDefault model. Physically most complete: "
        "background-flow bending plus aerodynamic-drag velocity evolution."
    ),
    "parker_ballistic": (
        "Parker-spiral bent axis + constant speed.\n\n"
        "Axis:  lon_axis(r) = lon0 - Omega*(r - r0)/v_sw\n"
        "Speed: v(t) = v0  (no velocity evolution).\n\n"
        "Background-flow geometry without drag. Use to isolate the effect of "
        "the axis bending from the velocity evolution."
    ),
    "drag": (
        "Straight cone + two-branch drag-based model (DBM).\n\n"
        "Axis:  fixed at the source longitude (no bending)\n"
        "Speed: v(t) = w + (v0 - w)/(1 + gamma*|v0 - w|*t)\n\n"
        "Legacy radial-only model with realistic velocity evolution; kept "
        "for comparison with the pre-Parker implementation."
    ),
    "ballistic": (
        "Straight cone + constant speed.\n\n"
        "Axis:  fixed at the source longitude (no bending)\n"
        "Speed: v(t) = v0\n\n"
        "Pure geometric approximation; kept for reproducibility of the "
        "legacy cone-search results."
    ),
}

# One-line hints shown on hover (tooltips) - parameter meaning, units, impact.
_PARAM_HINTS = {
    "start": "Catalog query window start (DONKI CMEAnalysis), YYYY-MM-DD.",
    "end": "Catalog query window end (DONKI CMEAnalysis), YYYY-MM-DD.",
    "dv": "Legacy radial-shell speed tolerance (km/s). NOT used by the "
          "strict Parker-wavefront encounter test.",
    "model": "Propagation model for the ICME front (see description below).",
    "wind": "Ambient solar-wind speed w (km/s): the DBM target speed that "
            "the ICME front relaxes toward.",
    "gamma": "Aerodynamic drag parameter gamma (1/km); relaxation timescale "
             "~ 1/(gamma*|v0 - w|).",
    "v_sw": "Solar-wind speed v_sw (km/s) used for the Parker-spiral bending "
            "of the front axis; can differ from w.",
    "launch": "Front launch radius r0 in solar radii; start of the DBM "
              "integration and of the axis bending.",
    "window": "Half-width of the encounter search window (h) centred on the "
              "predicted wavefront arrival at the probe.",
    "tol": "Radial tolerance (km) of the wavefront-sweep crossing test.",
    "thickness": "ICME radial half-thickness H (km) behind the front; the "
                 "probe must stay in [front-H, front] after the sweep.",
    "targets": "Bodies whose ephemeris is queried and tested (None = all).",
}


def _pad_iso(iso: str, hours: float) -> str:
    t = _dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
    return (t + _dt.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
# Lightweight tooltip
# --------------------------------------------------------------------------- #
class _Tooltip:
    """Small hover tooltip bound to a widget (plain tk.Toplevel)."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event=None) -> None:
        if self._tip is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self._tip, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", 8), wraplength=320,
                         padx=6, pady=4)
        label.pack()

    def _hide(self, _event=None) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


# --------------------------------------------------------------------------- #
# Embedded matplotlib window
# --------------------------------------------------------------------------- #
class FigureWindow(tk.Toplevel):
    """Standalone figure viewer; the figure can be replaced in place."""

    def __init__(self, master, fig, title: str, default_name: str = "figure.png"):
        super().__init__(master)
        self.title(title)
        self.geometry("980x820")
        self._fig = fig
        self._default_name = default_name
        self._toolbar = None

        from matplotlib.backends.backend_tkagg import (
            FigureCanvasTkAgg,
            NavigationToolbar2Tk,
        )

        self._canvas_frame = tk.Frame(self)
        self._canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas = FigureCanvasTkAgg(fig, master=self._canvas_frame)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, self, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side=tk.TOP, fill=tk.X)
        self._toolbar = toolbar
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._canvas = canvas

        bar = tk.Frame(self)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(bar, text="Save image", command=self._save).pack(side=tk.RIGHT,
                                                                   padx=6, pady=4)

    def set_figure(self, fig) -> None:
        """Replace the displayed figure in place (keeps the window open)."""
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self._fig = fig
        for w in self._canvas_frame.winfo_children():
            w.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self._canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._canvas = canvas
        if self._toolbar is not None:
            self._toolbar.update()

    def _save(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            initialfile=self._default_name,
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
        )
        if path:
            self._fig.savefig(path, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Saved", path, parent=self)


# --------------------------------------------------------------------------- #
# Results window
# --------------------------------------------------------------------------- #
class ResultsWindow(tk.Toplevel):
    def __init__(self, master: "CMEMossApp", result: SearchResult):
        super().__init__(master)
        self.app = master
        self.result = result
        self._map_window: FigureWindow | None = None
        self.title("CME results")
        self.geometry("1200x680")

        tk.Label(self, text="CME list (double-click row for orbit map)",
                 font=("Segoe UI", 11)).pack(pady=5)

        body = tk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)

        self._build_tree(body)
        self.detail = tk.Frame(body, bd=2, relief=tk.GROOVE, padx=10, pady=10)
        self.detail.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self._fill_tree()

        actions = tk.Frame(self)
        actions.pack(fill=tk.X, pady=4)
        tk.Button(actions, text="Export .txt report",
                  command=self._export_txt).pack(side=tk.LEFT, padx=6)
        tk.Button(actions, text="Export .json",
                  command=self._export_json).pack(side=tk.LEFT, padx=6)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)

    # ------------------------------------------------------------------ #
    def _build_tree(self, parent) -> None:
        left = tk.Frame(parent)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = tk.Scrollbar(left)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        cols = ("id", "time", "lon", "lat", "rad", "vel", "inside")
        self.tree = ttk.Treeview(left, columns=cols, show="headings",
                                 yscrollcommand=scroll.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        scroll.config(command=self.tree.yview)
        headings = {"id": "ID", "time": "time (UTC)", "lon": "lon",
                    "lat": "lat", "rad": "half-angle", "vel": "v (km/s)",
                    "inside": "bodies inside cone"}
        widths = {"id": 45, "lon": 55, "lat": 55, "rad": 85, "vel": 80}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, anchor=tk.CENTER, width=widths.get(c, 140))

    def _fill_tree(self) -> None:
        for i, encounter in enumerate(self.result.encounters):
            e = encounter.event
            inside = " ".join(
                k for k in BODY_ORDER if k in encounter.bodies
            )
            self.tree.insert(
                "", tk.END,
                values=(i, e.event_time, e.lon_deg, e.lat_deg,
                        e.half_width_deg, e.speed_km_s, inside),
            )

    # ------------------------------------------------------------------ #
    def _selected_encounter(self) -> CMEEncounter | None:
        item = self.tree.focus()
        if not item:
            return None
        cme_id = int(self.tree.item(item, "values")[0])
        return self.result.encounters[cme_id]

    def _on_select(self, _event=None) -> None:
        for w in self.detail.winfo_children():
            w.destroy()
        encounter = self._selected_encounter()
        if encounter is None:
            return
        tk.Label(self.detail, text=encounter.event.event_time,
                 font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 8))

        # Orbit / cone map control bar: open the map, optionally overlay
        # Parker background-wind spiral line(s) from the user-entered speeds.
        bar = tk.Frame(self.detail)
        bar.pack(anchor=tk.W, fill=tk.X, pady=(0, 2))
        tk.Button(bar, text="Open orbit / cone map",
                  command=lambda: self._show_map(encounter, speeds=()),
                  ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(bar, text="Parker overlay speed(s) (km/s, comma-separated):",
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 4))
        self.speed_entry = ttk.Entry(bar, width=18)
        self.speed_entry.pack(side=tk.LEFT, padx=(0, 6))
        _Tooltip(self.speed_entry,
                 "Optional background-wind speeds for the Parker-spiral "
                 "overlay, e.g. '300, 400'. Empty = no overlay. Overlay is a "
                 "visual guide only; it never changes the ICME propagation "
                 "or the encounter result.")
        tk.Button(bar, text="Plot", width=6,
                  command=lambda: self._plot_overlay(encounter),
                  ).pack(side=tk.LEFT)
        tk.Label(self.detail,
                 text="Overlay is a visual guide only (background-wind "
                      "Parker spiral); it does not affect propagation or "
                      "encounter results.",
                 font=("Segoe UI", 8), fg="#555555").pack(anchor=tk.W, pady=(0, 8))

        for body_key in BODY_ORDER:
            window = encounter.bodies.get(body_key)
            if window is None:
                continue
            row = tk.Frame(self.detail)
            row.pack(fill=tk.X, pady=3)
            info = (f"{body_key}: {window.enter_time} -> {window.exit_time}\n"
                    f"r = {window.enter_radius_km:.0f} .. "
                    f"{window.exit_radius_km:.0f} km ({window.n_points} samples)")
            tk.Label(row, text=info, justify=tk.LEFT).grid(row=0, column=0,
                                                           sticky=tk.W)
            btns = tk.Frame(row)
            btns.grid(row=0, column=1, padx=8)
            t0 = _pad_iso(window.enter_time, -6)
            t1 = _pad_iso(window.exit_time, 6)
            if body_key in MISSION_REGISTRY:
                for j, kind in enumerate(_KIND_LABELS):
                    tk.Button(
                        btns, text=kind, width=6,
                        command=lambda b=body_key, k=kind, a=t0, z=t1:
                        self._load_series(b, k, a, z),
                    ).grid(row=0, column=j, padx=2)
            else:
                tk.Label(btns, text="no in-situ loader").grid(
                    row=0, column=0, sticky=tk.W)

    def _on_double_click(self, _event=None) -> None:
        encounter = self._selected_encounter()
        if encounter is not None:
            self._show_map(encounter, speeds=())

    # ------------------------------------------------------------------ #
    def _parse_overlay_speeds(self) -> tuple[float, ...] | None:
        """Parse the overlay input; None when the field is empty."""
        text = self.speed_entry.get().strip() if hasattr(self, "speed_entry") else ""
        if not text:
            return None
        try:
            speeds = tuple(
                float(x) for x in text.replace(";", ",").split(",") if x.strip()
            )
        except ValueError as exc:
            raise ValueError(f"invalid speed value: {exc}") from exc
        if any(s <= 0 for s in speeds):
            raise ValueError("speeds must be positive")
        return speeds

    def _plot_overlay(self, encounter: CMEEncounter) -> None:
        try:
            speeds = self._parse_overlay_speeds()
        except ValueError as exc:
            messagebox.showerror("Parker overlay", str(exc), parent=self)
            return
        if speeds is None:
            messagebox.showinfo(
                "Parker overlay",
                "No speed entered - nothing plotted. Enter one or more "
                "background-wind speeds (km/s) and click Plot again.",
                parent=self,
            )
            return
        self._show_map(encounter, speeds=speeds)

    def _show_map(self, encounter: CMEEncounter,
                  speeds: tuple[float, ...]) -> None:
        try:
            from cmemoss.visualization.encounter_plot import make_encounter_figure

            params = replace(self.result.parameters,
                             parker_wind_speeds_km_s=speeds)
            fig = make_encounter_figure(
                encounter.event, encounter.bodies, self.result.ephemeris,
                params,
            )
        except Exception as exc:
            messagebox.showerror("Plot error", str(exc), parent=self)
            return
        title = f"CME {encounter.event.event_time}"
        if speeds:
            title += f"  (Parker overlay: {', '.join(f'{s:g}' for s in speeds)} km/s)"
        if self._map_window is not None and self._map_window.winfo_exists():
            self._map_window.title(title)
            self._map_window.set_figure(fig)
            self._map_window.lift()
        else:
            self._map_window = FigureWindow(
                self, fig, title,
                default_name=f"CME_{encounter.event.cme_id}.png",
            )

    def _load_series(self, body: str, kind: str, t0: str, t1: str) -> None:
        self.app.set_status(f"Loading {body} {kind} ...")

        def done(ok: bool, payload) -> None:
            self.app.set_status("Ready")
            if not ok:
                messagebox.showerror(
                    "In-situ data error",
                    f"{body} {kind}: {payload}", parent=self,
                )
                return
            self._show_series(body, kind, payload)

        self.app.controller.start_load_series(body, kind, t0, t1, done)

    def _show_series(self, body: str, kind: str, series) -> None:
        from cmemoss.visualization.timeseries_plot import (
            plot_time_series_panels,
        )

        title, unit = _KIND_LABELS[kind]
        fig = plot_time_series_panels(
            [(f"{body} {title}", series)],
            title=f"{body} {series.name}",
        )
        FigureWindow(self, fig, f"{body} {kind}",
                     default_name=f"{body}_{kind}.png")

    # ------------------------------------------------------------------ #
    def _export_txt(self) -> None:
        directory = filedialog.askdirectory(parent=self, mustexist=True)
        if directory:
            path = self.app.controller.export_report(self.result, directory)
            messagebox.showinfo("Exported", str(path), parent=self)

    def _export_json(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".json", initialfile="cmemoss_result.json"
        )
        if path:
            out = self.app.controller.export_json(self.result, path)
            messagebox.showinfo("Exported", str(out), parent=self)


# --------------------------------------------------------------------------- #
# Main application window (research-workflow notebook)
# --------------------------------------------------------------------------- #
class CMEMossApp(tk.Tk):
    def __init__(self, controller: AnalysisController | None = None) -> None:
        super().__init__()
        self.controller = controller or AnalysisController()
        self.title("CME-MOSS - multi-spacecraft CME analysis")
        self.geometry("780x640")
        self.minsize(700, 560)

        self._body_vars: dict[str, tk.BooleanVar] = {}
        self._build_widgets()
        self.after(200, self._poll_controller)

    # ------------------------------------------------------------------ #
    # Widget construction
    # ------------------------------------------------------------------ #
    def _build_widgets(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        self.start_var = tk.StringVar(value=_dt.date.today().isoformat())
        self.end_var = tk.StringVar(value=_dt.date.today().isoformat())
        self.dv_var = tk.StringVar(value="100")
        self.model_var = tk.StringVar(value="parker_drag")
        self.wind_var = tk.StringVar(value="400")
        self.gamma_var = tk.StringVar(value="2e-8")
        self.v_sw_var = tk.StringVar(value="400")
        self.launch_r_var = tk.StringVar(value="1.0")
        self.window_var = tk.StringVar(value="10")
        self.tol_var = tk.StringVar(value="1000")
        self.thickness_var = tk.StringVar(value="1.5e7")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self._build_data_tab()
        self._build_propagation_tab()
        self._build_encounter_tab()
        self._build_map_tab()
        self._build_export_tab()

        btns = tk.Frame(root)
        btns.pack(fill=tk.X, pady=(8, 0))
        self.search_btn = ttk.Button(btns, text="Search", command=self.on_search)
        self.search_btn.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btns, text="Save config", command=self.on_save_config).pack(
            side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Load config", command=self.on_load_config).pack(
            side=tk.LEFT, padx=6)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN,
                  anchor=tk.W, padding=(6, 2)).pack(fill=tk.X, side=tk.BOTTOM)

    # --- helpers ------------------------------------------------------ #
    @staticmethod
    def _param_row(parent, label: str, var: tk.StringVar, hint: str,
                   width: int = 22, unit: str | None = None,
                   row: int = 0) -> ttk.Entry:
        """One parameter line: label (with unit) + entry + hover hint."""
        text = label if unit is None else f"{label}  ({unit})"
        lbl = ttk.Label(parent, text=text)
        lbl.grid(row=row, column=0, sticky=tk.E, padx=(4, 8), pady=3)
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=1, sticky=tk.W, padx=(0, 4), pady=3)
        _Tooltip(lbl, hint)
        _Tooltip(entry, hint)
        return entry

    @staticmethod
    def _info_text(parent, text: str, height: int = 4, width: int = 66):
        box = tk.Text(parent, height=height, width=width, wrap=tk.WORD,
                      font=("Segoe UI", 8), bg="#f5f5f5", relief=tk.FLAT,
                      padx=6, pady=4)
        box.insert("1.0", text)
        box.config(state=tk.DISABLED)
        return box

    # --- tabs --------------------------------------------------------- #
    def _build_data_tab(self) -> None:
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text="1. Data / Event")

        grp = ttk.LabelFrame(page, text="Time range", padding=8)
        grp.pack(fill=tk.X, pady=(0, 6))
        self._param_row(grp, "Start date", self.start_var, _PARAM_HINTS["start"],
                        row=0)
        self._param_row(grp, "End date", self.end_var, _PARAM_HINTS["end"],
                        row=1)

        grp = ttk.LabelFrame(page, text="Catalog filter", padding=8)
        grp.pack(fill=tk.X, pady=6)
        self._param_row(grp, "Speed tolerance", self.dv_var, _PARAM_HINTS["dv"],
                        unit="km/s", row=0)
        self._info_text(
            grp,
            "Legacy radial-shell speed tolerance (physics/propagation.py). "
            "It is NOT used by the strict Parker-wavefront encounter test, "
            "which determines encounters from the dynamic wavefront sweep.",
            height=2,
        ).grid(row=1, column=0, columnspan=2, sticky="we", padx=4, pady=(4, 0))

        grp = ttk.LabelFrame(page, text="Targets", padding=8)
        grp.pack(fill=tk.BOTH, expand=True, pady=6)
        for i, key in enumerate(BODY_ORDER):
            var = tk.BooleanVar(value=True)
            self._body_vars[key] = var
            cb = ttk.Checkbutton(grp, text=BODY_REGISTRY[key].label,
                                 variable=var)
            cb.grid(row=i // 4, column=i % 4, sticky=tk.W, padx=10, pady=4)
            _Tooltip(cb, _PARAM_HINTS["targets"])

    def _build_propagation_tab(self) -> None:
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text="2. Propagation")

        grp = ttk.LabelFrame(page, text="Model", padding=8)
        grp.pack(fill=tk.X, pady=(0, 6))
        lbl = ttk.Label(grp, text="Propagation model")
        lbl.grid(row=0, column=0, sticky=tk.E, padx=(4, 8), pady=3)
        model_box = ttk.Combobox(
            grp, textvariable=self.model_var, width=20, state="readonly",
            values=("parker_drag", "parker_ballistic", "drag", "ballistic"),
        )
        model_box.grid(row=0, column=1, sticky=tk.W, padx=(0, 4), pady=3)
        _Tooltip(lbl, _PARAM_HINTS["model"])
        _Tooltip(model_box, _PARAM_HINTS["model"])
        model_box.bind("<<ComboboxSelected>>", lambda _e: self._update_model_info())
        self._model_text = self._info_text(grp, _MODEL_INFO["parker_drag"],
                                           height=6, width=72)
        self._model_text.grid(row=1, column=0, columnspan=2, sticky="we",
                              padx=4, pady=(6, 0))

        grp = ttk.LabelFrame(page, text="Drag-based velocity evolution (DBM)",
                             padding=8)
        grp.pack(fill=tk.X, pady=6)
        self._param_row(grp, "Ambient wind w", self.wind_var, _PARAM_HINTS["wind"],
                        unit="km/s", row=0)
        self._param_row(grp, "Drag parameter gamma", self.gamma_var,
                        _PARAM_HINTS["gamma"], unit="1/km", row=1)

        grp = ttk.LabelFrame(page, text="Parker-spiral geometry", padding=8)
        grp.pack(fill=tk.X, pady=6)
        self._param_row(grp, "Spiral wind v_sw", self.v_sw_var,
                        _PARAM_HINTS["v_sw"], unit="km/s", row=0)
        self._param_row(grp, "Launch radius r0", self.launch_r_var,
                        _PARAM_HINTS["launch"], unit="R_sun", row=1)

    def _build_encounter_tab(self) -> None:
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text="3. ICME / Encounter")

        grp = ttk.LabelFrame(page, text="Encounter search window", padding=8)
        grp.pack(fill=tk.X, pady=(0, 6))
        self._param_row(grp, "Encounter window", self.window_var,
                        _PARAM_HINTS["window"], unit="h", row=0)
        self._param_row(grp, "Sweep tolerance", self.tol_var,
                        _PARAM_HINTS["tol"], unit="km", row=1)

        grp = ttk.LabelFrame(page, text="ICME spatial scale", padding=8)
        grp.pack(fill=tk.X, pady=6)
        self._param_row(grp, "ICME half-thickness", self.thickness_var,
                        _PARAM_HINTS["thickness"], unit="km (behind front)",
                        row=0)
        self._info_text(
            grp,
            "Strict encounter test: the Parker-propagating wavefront must "
            "sweep across the probe inside the window (radial gap crosses "
            "0 within +/-tolerance) AND the probe must then stay inside the "
            "ICME region (gap in [0, H] and inside the angular cap half-width "
            "+ 10 deg).",
            height=3,
        ).grid(row=1, column=0, columnspan=2, sticky="we", padx=4, pady=(4, 0))

    def _build_map_tab(self) -> None:
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text="4. Orbit / Cone Map")

        self._info_text(
            page,
            "How to open the orbit / cone map and add a Parker overlay:\n"
            "  1. Run a search (bottom bar) - the results window lists the "
            "CMEs and their confirmed encounters.\n"
            "  2. Select a CME row. In the right-hand panel use "
            "[Open orbit / cone map] to draw the map without any overlay.\n"
            "  3. Enter one or more background solar-wind speeds in the "
            "adjacent field (km/s, comma-separated) and press [Plot] to "
            "overlay the corresponding Parker-spiral guide line(s) on the "
            "map.\n\n"
            "The overlay is a visual guide only (background-wind Parker "
            "spirals, parker.spiral_curve). It never changes the ICME "
            "propagation model or the encounter results.",
            height=10, width=80,
        ).pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _build_export_tab(self) -> None:
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text="5. Visualization / Export")

        self._info_text(
            page,
            "After a search the results window provides:\n"
            "  - double-click a CME row (or use Open orbit / cone map) for "
            "the polar wavefront map;\n"
            "  - per-body in-situ panels (mag / vel / dens / temp) for "
            "missions with a data loader;\n"
            "  - 'Export .txt report' (legacy format) and 'Export .json' "
            "(full parameters + events + encounters).\n\n"
            "Every figure window has a 'Save image' button (PNG / PDF / "
            "SVG, 300 dpi).",
            height=8, width=80,
        ).pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    # ------------------------------------------------------------------ #
    def _update_model_info(self) -> None:
        name = self.model_var.get()
        self._model_text.config(state=tk.NORMAL)
        self._model_text.delete("1.0", tk.END)
        self._model_text.insert("1.0", _MODEL_INFO.get(name, ""))
        self._model_text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ #
    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _poll_controller(self) -> None:
        self.controller.poll()
        self.after(200, self._poll_controller)

    # ------------------------------------------------------------------ #
    def collect_parameters(self) -> SearchParameters:
        start = self.start_var.get().strip()
        end = self.end_var.get().strip()
        _dt.datetime.strptime(start, "%Y-%m-%d")
        _dt.datetime.strptime(end, "%Y-%m-%d")
        bodies = tuple(k for k, v in self._body_vars.items() if v.get()) or None
        from cmemoss.constants import R_SUN_KM

        return SearchParameters(
            start_date=start,
            end_date=end,
            speed_tolerance_km_s=float(self.dv_var.get()),
            propagation_model=self.model_var.get(),
            ambient_wind_km_s=float(self.wind_var.get()),
            drag_parameter_km=float(self.gamma_var.get()),
            v_sw_km_s=float(self.v_sw_var.get()),
            launch_radius_km=float(self.launch_r_var.get()) * R_SUN_KM,
            encounter_time_window_hours=float(self.window_var.get()),
            encounter_tolerance_km=float(self.tol_var.get()),
            icme_half_thickness_km=float(self.thickness_var.get()),
            # No Parker-overlay speeds on the input page: overlays are added
            # per-map from the orbit/cone-map control bar only.
            parker_wind_speeds_km_s=(),
            bodies=bodies,
        )

    def apply_parameters(self, params: SearchParameters) -> None:
        from cmemoss.constants import R_SUN_KM

        self.start_var.set(params.start_date)
        self.end_var.set(params.end_date)
        self.dv_var.set(str(params.speed_tolerance_km_s))
        self.model_var.set(params.propagation_model)
        self.wind_var.set(str(params.ambient_wind_km_s))
        self.gamma_var.set(str(params.drag_parameter_km))
        self.v_sw_var.set(str(params.v_sw_km_s))
        self.launch_r_var.set(str(params.launch_radius_km / R_SUN_KM))
        self.window_var.set(str(params.encounter_time_window_hours))
        self.tol_var.set(str(params.encounter_tolerance_km))
        self.thickness_var.set(str(params.icme_half_thickness_km))
        self._update_model_info()
        selected = set(params.bodies or BODY_ORDER)
        for key, var in self._body_vars.items():
            var.set(key in selected)

    # ------------------------------------------------------------------ #
    def on_search(self) -> None:
        try:
            params = self.collect_parameters()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid input", f"Check the fields:\n{exc}")
            return
        self.search_btn.state(["disabled"])
        self.set_status("Querying catalog and ephemeris (may take a while) ...")

        def done(ok: bool, payload) -> None:
            self.search_btn.state(["!disabled"])
            if not ok:
                self.set_status("Search failed")
                messagebox.showerror("Search error", str(payload))
                return
            self.set_status(
                f"Done - {sum(e.has_match for e in payload.encounters)} / "
                f"{len(payload.encounters)} CMEs with encounters"
            )
            ResultsWindow(self, payload)

        self.controller.start_search(params, done)

    # ------------------------------------------------------------------ #
    def on_save_config(self) -> None:
        try:
            params = self.collect_parameters()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile="cmemoss_config.json")
        if path:
            save_parameters(params, path)
            self.set_status(f"Config saved: {path}")

    def on_load_config(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.apply_parameters(load_parameters(path))
            except Exception as exc:
                messagebox.showerror("Config error", str(exc))


def run() -> None:
    app = CMEMossApp()
    app.mainloop()
