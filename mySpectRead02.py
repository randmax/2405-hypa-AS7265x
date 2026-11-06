"""AS7265x spectral acquisition GUI (Tkinter, Windows and Linux)."""
if __name__ == "__main__":
    from bootstrap import bootstrap_or_exit
    bootstrap_or_exit()

import argparse
from collections import deque
import os
import queue
import sys
import time
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, filedialog

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
from serial.tools import list_ports

from gui_style import Theme, Collapsible, WheelGuard, Tooltip
from spectral_core import Acquisition, SpectrumBuffer, WAVELENGTHS, MAX_SAMPLES, CONTROL_QUEUE_SIZE


class SpectralCanvas(FigureCanvasTkAgg):
    def _update_device_pixel_ratio(self, event=None):
        super()._update_device_pixel_ratio(event)
        widget = self.get_tk_widget()
        # Tk may keep the allocated size when the backend changes its requested
        # size on <Map>. In that case no <Configure> arrives to resize the bitmap.
        if widget.winfo_width() > 1 and widget.winfo_height() > 1:
            self.resize(SimpleNamespace(width=widget.winfo_width(), height=widget.winfo_height()))


class SpectralReader:
    def __init__(self, master, demo=False):
        self.master = master
        self.theme = Theme(master)
        p = self.theme.px
        master.title("AS7265x · Spektrális adatgyűjtő")
        master.geometry("{}x{}".format(min(p(1180), master.winfo_screenwidth() - 60),
                                      min(p(800), master.winfo_screenheight() - 90)))
        master.minsize(min(p(820), master.winfo_screenwidth() - 60),
                       min(p(560), master.winfo_screenheight() - 90))
        master.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue(maxsize=CONTROL_QUEUE_SIZE)
        self.buffer = SpectrumBuffer()
        self.worker = None
        self.running = self.closing = False
        self.dirty = True
        self.last_render = 0.0
        self.last_received = 0
        self.last_plotted_received = 0
        self.pending_log = deque(maxlen=100)
        self.mode = self.colorbar = self.bars = self.image = None
        self.view_limits = {}
        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="115200")
        self.sample_count_var = tk.StringVar(value="50")
        self.waterfall_rows_var = tk.StringVar(value="50")
        self.average_count_var = tk.StringVar(value="1")
        self.display_mode_var = tk.StringVar(value="Histogram")
        self.demo_var = tk.BooleanVar(value=demo)
        self.theme_var = tk.StringVar(value="Világos")
        self.autoscale_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Készen áll · válassz portot, vagy indíts demómérést.")
        self.count_var = tk.StringVar(value="0 / 50 minta")
        self.metric_var = tk.StringVar(value="18 csatorna  ·  410–940 nm")
        self._menus()
        heading = ttk.Frame(master, padding=(p(18), p(14), p(18), p(10)))
        heading.pack(fill="x")
        ttk.Label(heading, text="AS7265x", style="Title.TLabel").pack(anchor="w")
        ttk.Label(heading, text="Spektrális adatgyűjtő  /  élő mérés és elemzés",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(p(3), 0))
        content = ttk.Frame(master, padding=(p(18), 0, p(18), p(12)))
        content.pack(fill="both", expand=True)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        side = ttk.Frame(content, width=p(300))
        side.grid(row=0, column=0, sticky="ns", padx=(0, p(14)))
        side.grid_propagate(False)
        side.rowconfigure(0, weight=1)
        side.columnconfigure(0, weight=1)
        self.side_canvas = self.theme.register(tk.Canvas(side, width=p(284), highlightthickness=0),
                                               background="window")
        self.side_canvas.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(side, orient="vertical", command=self.side_canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.side_canvas.configure(yscrollcommand=scroll.set)
        self.sidebar = ttk.Frame(self.side_canvas)
        self.side_item = self.side_canvas.create_window((0, 0), window=self.sidebar, anchor="nw")
        self.sidebar.bind("<Configure>", lambda e: self.side_canvas.configure(
            scrollregion=self.side_canvas.bbox("all")))
        self.side_canvas.bind("<Configure>", lambda e: self.side_canvas.itemconfigure(
            self.side_item, width=e.width))
        self.guard = WheelGuard(master, self._scroll_sidebar)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            master.bind_all(seq, self._sidebar_wheel, add="+")
        self.sections = []
        connection = self._section("Kapcsolat")
        self.port_combo = self._field(connection, "Soros port", self.port_var, values=[])
        self.port_combo.configure(state="normal")
        self.refresh_btn = ttk.Button(connection, text="Portok frissítése", command=self.refresh_ports)
        self.refresh_btn.pack(fill="x", pady=(p(6), p(8)))
        self.baud_combo = self._field(connection, "Átviteli sebesség (baud)", self.baud_var,
                                      values=(9600, 19200, 38400, 57600, 115200, 230400))
        self.demo_check = ttk.Checkbutton(connection, text="Eszköz nélküli demó", variable=self.demo_var)
        self.demo_check.pack(anchor="w", pady=(p(10), p(2)))
        acquisition = self._section("Adatgyűjtés")
        self.sample_entry = self._field(acquisition, "Puffer mérete (minta)", self.sample_count_var,
                                         maximum=MAX_SAMPLES)
        ttk.Label(acquisition, text="A CSV és a waterfall az utolsó N mintát őrzi. Az élő nézet ettől független.",
                  style="Muted.TLabel", wraplength=p(235)).pack(fill="x", pady=(p(5), p(8)))
        self.start_btn = ttk.Button(acquisition, text="Mérés indítása", style="Primary.TButton",
                                    command=self.start_measurement)
        self.start_btn.pack(fill="x", pady=p(3))
        self.stop_btn = ttk.Button(acquisition, text="Leállítás", state="disabled",
                                   command=self.stop_measurement)
        self.stop_btn.pack(fill="x", pady=p(3))
        self.save_btn = ttk.Button(acquisition, text="Mentés CSV-be…", state="disabled",
                                   command=self.save_csv)
        self.save_btn.pack(fill="x", pady=p(3))
        view = self._section("Megjelenítés")
        self.display_mode_combo = self._field(view, "Diagram típusa", self.display_mode_var,
                                               values=("Histogram", "Waterfall"))
        self.average_entry = self._field(view, "Átlagolás (minta, 1 = élő)", self.average_count_var,
                                          maximum=MAX_SAMPLES)
        self.waterfall_rows_entry = self._field(view, "Waterfall magassága (sor)",
                                                 self.waterfall_rows_var, maximum=2000)
        ttk.Checkbutton(view, text="Automatikus tengelyhatárok", variable=self.autoscale_var,
                        command=self._settings_changed).pack(anchor="w", pady=(p(10), p(5)))
        ttk.Button(view, text="Nézet alaphelyzetbe", command=self.reset_view).pack(fill="x")
        for variable in (self.sample_count_var, self.waterfall_rows_var, self.display_mode_var,
                         self.average_count_var):
            variable.trace_add("write", self._settings_changed)
        workspace = ttk.Frame(content)
        workspace.grid(row=0, column=1, sticky="nsew")
        self.panes = self.theme.register(tk.PanedWindow(workspace, orient="vertical", sashwidth=p(6),
                                                       borderwidth=0, relief="flat"), background="splitter")
        self.panes.pack(fill="both", expand=True)
        chart = ttk.Frame(self.panes, style="Panel.TFrame", padding=p(8))
        top = ttk.Frame(chart, style="Panel.TFrame")
        top.pack(fill="x", pady=(0, p(5)))
        ttk.Label(top, text="SPEKTRUM", style="Panel.TLabel",
                  font=(self.theme.family, -p(12), "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.metric_var, style="Muted.TLabel", width=1,
                  anchor="e").pack(side="right", fill="x", expand=True)
        # TkAgg applies the screen pixel ratio itself; do not scale DPI twice.
        self.figure = Figure(figsize=(7, 4), dpi=100)
        self.figure.subplots_adjust(left=0.10, right=0.95, bottom=0.23, top=0.88)
        self.ax = self.figure.add_subplot(111)
        self.canvas = SpectralCanvas(self.figure, master=chart)
        self.canvas.get_tk_widget().configure(width=p(300), height=p(220), highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, chart, pack_toolbar=False)
        self.toolbar.pack(fill="x", pady=(p(5), 0), before=self.canvas.get_tk_widget())
        tips = {"Home": "Eredeti diagramnézet", "Back": "Előző diagramnézet",
                "Forward": "Következő diagramnézet", "Pan": "Diagram eltolása",
                "Zoom": "Terület nagyítása", "Subplots": "Diagram margói",
                "Save": "Diagram mentése képként"}
        self.tooltips = [Tooltip(button, self.theme, tips.get(name, name))
                         for name, button in self.toolbar._buttons.items()]
        self.canvas.mpl_connect("button_release_event", self._navigation_finished)
        self.canvas.mpl_connect("draw_event", self._draw_finished)
        self.panes.add(chart, minsize=p(260), stretch="always")
        log_panel = ttk.Frame(self.panes, style="Panel.TFrame", padding=p(8))
        log_header = ttk.Frame(log_panel, style="Panel.TFrame")
        log_header.pack(fill="x")
        ttk.Label(log_header, text="ADATNAPLÓ", style="Panel.TLabel",
                  font=(self.theme.family, -p(12), "bold")).pack(side="left")
        ttk.Button(log_header, text="Törlés", command=self.clear_log).pack(side="right")
        log_area = ttk.Frame(log_panel, style="Panel.TFrame")
        log_area.pack(fill="both", expand=True, pady=(p(6), 0))
        self.log_text = self.theme.register(tk.Text(log_area, height=5, width=1, wrap="word",
                                                   borderwidth=0, state="disabled",
                                                   font=(self.theme.family, -p(12))),
                                             background="input", foreground="text", insertbackground="text",
                                             selectbackground="selection", selectforeground="selection_text")
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_area, command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.panes.add(log_panel, minsize=p(100), height=p(160), stretch="never")
        status = ttk.Frame(master, style="Status.TFrame", padding=(p(18), p(7)))
        status.pack(fill="x")
        self.status_label = ttk.Label(status, textvariable=self.status_var, style="Status.TLabel",
                                       width=1, anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.tooltips.append(Tooltip(self.status_label, self.theme, self.status_var.get))
        ttk.Label(status, textvariable=self.count_var, style="Status.TLabel", width=22,
                  anchor="e").pack(side="right")
        self.refresh_ports()
        self.apply_theme()
        self._log("Készen áll. 18 csatorna · 410–940 nm. A napló legfeljebb 2000 sort őriz.")
        self.timer = master.after(50, self._tick)
        if demo:
            master.after(150, self.start_measurement)

    def _menus(self):
        bar = self.theme.register(tk.Frame(self.master, borderwidth=0), background="menu")
        bar.pack(fill="x")
        self.menus = []
        for title in ("Fájl", "Téma", "Súgó"):
            button = self.theme.register(tk.Menubutton(bar, text=title, padx=14, pady=6,
                                                       relief="flat", takefocus=True),
                                         background="menu", foreground="text",
                                         activebackground="hover", activeforeground="text")
            button.pack(side="left")
            menu = self.theme.register(tk.Menu(button, tearoff=False), background="menu", foreground="text",
                                       activebackground="popup_selection", activeforeground="selection_text",
                                       selectcolor="accent")
            button.configure(menu=menu)
            self.menus.append(menu)
        self.menus[0].add_command(label="Mentés CSV-be…", command=self.save_csv)
        self.menus[0].add_separator()
        self.menus[0].add_command(label="Kilépés", command=self.close)
        for name in ("Világos", "Fekete"):
            self.menus[1].add_radiobutton(label=name, variable=self.theme_var, value=name,
                                          command=self.apply_theme)
        self.menus[2].add_command(label="Használat és rendszer", command=self.show_help)

    def _section(self, title):
        section = Collapsible(self.sidebar, title, self.theme.px)
        section.pack(fill="x", pady=(0, self.theme.px(10)))
        self.sections.append(section)
        return section.body

    def _field(self, parent, label, variable, values=None, maximum=None):
        p = self.theme.px
        ttk.Label(parent, text=label, style="Panel.TLabel").pack(anchor="w", pady=(p(5), p(4)))
        if maximum:
            widget = ttk.Spinbox(parent, from_=1, to=maximum, textvariable=variable, width=8)
        else:
            widget = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=8)
        widget.pack(fill="x", pady=(0, p(4)))
        self.guard.watch(widget)
        return widget

    def _scroll_sidebar(self, direction):
        bounds = self.side_canvas.bbox("all")
        if bounds and bounds[3] > self.side_canvas.winfo_height():
            self.side_canvas.yview_scroll(direction * 2, "units")

    def _sidebar_wheel(self, event):
        widget = event.widget
        while widget is not None:
            if widget is self.sidebar or widget is self.side_canvas:
                self._scroll_sidebar(self.guard.direction(event))
                return "break"
            widget = getattr(widget, "master", None)

    def refresh_ports(self):
        if self.worker:
            return
        try:
            self.available_ports = [port.device for port in list_ports.comports()]
            self.port_combo.configure(values=self.available_ports)
            if not self.port_var.get() and self.available_ports:
                self.port_var.set(self.available_ports[0])
        except (OSError, RuntimeError) as exc:
            self._log("Portlista: {}".format(exc))

    @staticmethod
    def _integer(variable, maximum, name):
        try:
            value = int(variable.get())
            if not 1 <= value <= maximum:
                raise ValueError()
            return value
        except ValueError:
            raise ValueError("{}: 1–{} közötti egész szám szükséges.".format(name, maximum))

    def _settings_changed(self, *args):
        try:
            self.buffer.resize(self._integer(self.sample_count_var, MAX_SAMPLES, "Puffer"))
        except ValueError:
            pass  # Allow intermediate text while editing; validate again on start.
        self.dirty = True

    def start_measurement(self):
        if self.worker or self.closing:
            return
        try:
            capacity = self._integer(self.sample_count_var, MAX_SAMPLES, "Puffer")
            self._integer(self.waterfall_rows_var, 2000, "Waterfall")
            self._integer(self.average_count_var, MAX_SAMPLES, "Átlagolás")
            baud = int(self.baud_var.get())
            if baud <= 0:
                raise ValueError("Az átviteli sebesség pozitív egész szám legyen.")
            port = self.port_var.get().strip()
            if not port and not self.demo_var.get():
                raise ValueError("Adj meg portot (COM3 vagy /dev/ttyUSB0), vagy válassz demót.")
        except ValueError as exc:
            self.show_dialog("Beállítási hiba", str(exc))
            return
        self.buffer = SpectrumBuffer(capacity)
        self.events = queue.Queue(maxsize=CONTROL_QUEUE_SIZE)
        self.worker = Acquisition(self.events, port, baud, self.demo_var.get(), buffer=self.buffer)
        self.last_received = self.last_plotted_received = 0
        self.running = True
        self._controls(True)
        self.save_btn.configure(state="disabled")
        self.status_var.set("Kapcsolódás…")
        self._log("Új mérés indul. Az előző mérés pufferét lecseréltük.")
        self.dirty = True
        self.worker.start()
        self.master.after_cancel(self.timer)
        self.timer = self.master.after(0, self._tick)

    def _controls(self, active):
        for widget in (self.port_combo, self.baud_combo, self.demo_check, self.refresh_btn):
            widget.configure(state="disabled" if active else "normal")
        if not active:
            self.baud_combo.configure(state="readonly")
        self.start_btn.configure(state="disabled" if active else "normal")
        self.stop_btn.configure(state="normal" if active else "disabled")

    def stop_measurement(self):
        if self.worker:
            self.worker.stop_event.set()
            self.running = False
            self.status_var.set("Leállítás…")
            self.stop_btn.configure(state="disabled")

    def _log(self, message):
        self.pending_log.append(time.strftime("%H:%M:%S") + "  " + message.replace("\n", " ")[:400])

    def _flush_log(self):
        if not self.pending_log:
            return
        at_bottom = self.log_text.yview()[1] >= 0.98
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "\n".join(self.pending_log) + "\n")
        self.pending_log.clear()
        excess = int(self.log_text.index("end-1c").split(".")[0]) - 2001
        if excess > 0:
            self.log_text.delete("1.0", "{}.0".format(excess + 1))
        if at_bottom:
            self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        self.pending_log.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _tick(self):
        started = time.monotonic()
        count = 0
        while count < 16 and time.monotonic() - started < 0.004:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            count += 1
            if kind == "ready":
                self.status_var.set("Mérés folyamatban · " + payload)
                self._log(payload)
            elif kind == "error":
                self.status_var.set("Kapcsolati hiba · részletek az adatnaplóban")
                self._log("HIBA: " + payload)
                if not self.closing:
                    self.show_dialog("Soros kapcsolat hibája", payload +
                                     "\n\nLinuxon ellenőrizd az eszköz jogosultságát (dialout/uucp csoport), "
                                     "és hogy más program nem használja-e.")
            else:
                self._log("Kihagyott / szöveges sor: " + payload)
        # Sampling continues in the worker while Tk is drawing or a dialog is open.
        # Read a fresh snapshot, never replay a queue of stale display samples.
        received = self.buffer.received
        if received != self.last_received:
            if not self.last_received:
                self.save_btn.configure(state="normal")
            self.last_received = received
            self.dirty = True
        if self.worker and not self.worker.is_alive() and self.events.empty():
            if self.worker.suppressed_messages:
                self._log("Összevont diagnosztika: {} további szöveges / hibás sor kihagyva."
                          .format(self.worker.suppressed_messages))
            self.worker = None
            self.running = False
            self._controls(False)
            if not self.status_var.get().startswith("Kapcsolati hiba"):
                self.status_var.set("Mérés leállítva · a puffer CSV-be menthető.")
            self._log("Mérés befejezve. {} fogadott minta.".format(self.buffer.received))
        if self.closing:
            if self.worker is None:
                self._cancel_canvas_callbacks()
                self.master.destroy()
                return
        elif self.dirty and time.monotonic() - self.last_render >= 0.05:
            self.update_plot()
            self.last_render = time.monotonic()
            self.dirty = False
        self._flush_log()
        self.timer = self.master.after(20 if self.worker else 150, self._tick)

    def _build_plot(self, mode):
        # Only a deliberate view change rebuilds axes/artists.
        if self.mode:
            self.view_limits[self.mode] = (self.ax.get_xlim(), self.ax.get_ylim())
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        self.bars = self.image = self.colorbar = None
        self.mode = mode
        self.ax.set_xticks(np.arange(18), [str(w) for w in WAVELENGTHS], rotation=45, ha="right")
        self.ax.set_xlabel("Hullámhossz (nm)")
        if mode == "Histogram":
            self.bars = self.ax.bar(np.arange(18), np.zeros(18), width=0.72, zorder=3)
            self.ax.set_title("Élő spektrum", loc="left", fontsize=11, fontweight="bold")
            self.ax.set_ylabel("Intenzitás")
            self.ax.grid(axis="y", alpha=0.4, zorder=0)
            self.ax.set_xlim(-0.7, 17.7)
        else:
            self.image = self.ax.imshow(np.zeros((1, 18)), origin="upper", aspect="auto",
                                       interpolation="nearest", cmap="viridis",
                                       extent=(-0.5, 17.5, 0.5, -0.5))
            self.ax.set_title("Idősoros spektrum · legrégebbi felül", loc="left", fontsize=11,
                              fontweight="bold")
            self.ax.set_ylabel("Minta (legújabb alul)")
            self.colorbar = self.figure.colorbar(self.image, ax=self.ax, pad=0.035, fraction=0.04)
            self.colorbar.set_label("Intenzitás")
        self.toolbar.update()
        if not self.autoscale_var.get() and mode in self.view_limits:
            self.ax.set_xlim(self.view_limits[mode][0])
            self.ax.set_ylim(self.view_limits[mode][1])
        self._plot_colors()

    def update_plot(self):
        mode = self.display_mode_var.get()
        try:
            average = self._integer(self.average_count_var, MAX_SAMPLES, "Átlagolás")
        except ValueError:
            average = 1
        try:
            rows = self._integer(self.waterfall_rows_var, 2000, "Waterfall")
        except ValueError:
            rows = 50
        snapshot = self.buffer.snapshot(average=average, rows=rows if mode == "Waterfall" else 0)
        if mode != self.mode:
            self._build_plot(mode)
        values = snapshot.values
        if mode == "Histogram":
            title = ("Élő spektrum · legfrissebb minta" if average == 1 else
                     "Átlagolt spektrum · {} minta".format(min(average, snapshot.count)))
            if self.ax.get_title(loc="left") != title:
                self.ax.set_title(title, loc="left", fontsize=11, fontweight="bold",
                                  color=self.theme.colors["text"])
            for bar, value in zip(self.bars, values):
                bar.set_height(value)
            if self.autoscale_var.get():
                low, high = min(0, float(values.min())), max(1, float(values.max()))
                margin = (high - low) * 0.08
                self.ax.set_ylim(low - margin if low < 0 else 0, high + margin)
        else:
            data = snapshot.history if snapshot.count else np.zeros((1, 18))
            self.image.set_data(data)
            old_limits = self.ax.get_xlim(), self.ax.get_ylim()
            self.image.set_extent((-0.5, 17.5, len(data) - 0.5, -0.5))
            if self.autoscale_var.get():
                self.ax.set_xlim(-0.5, 17.5)
                self.ax.set_ylim(len(data) - 0.5, -0.5)
                low, high = float(data.min()), float(data.max())
                self.image.set_clim(low, high if high > low else low + 1)
            else:
                self.ax.set_xlim(old_limits[0])
                self.ax.set_ylim(old_limits[1])
        self.count_var.set("{} / {} minta".format(snapshot.count, snapshot.capacity))
        if snapshot.count:
            index = int(np.argmax(values))
            self.metric_var.set("Csúcs: {} nm · {:.1f}  |  {} minta".format(
                WAVELENGTHS[index], values[index], snapshot.received))
        else:
            self.metric_var.set("18 csatorna  ·  410–940 nm  ·  még nincs adat")
        self.last_plotted_received = snapshot.received
        self.canvas.draw_idle()

    def _plot_colors(self):
        c = self.theme.colors
        self.figure.set_facecolor(c["panel"])
        self.ax.set_facecolor(c["histogram"])
        self.ax.set_title(self.ax.get_title(loc="left"), loc="left", color=c["text"],
                          fontsize=11, fontweight="bold")
        for axis in self.figure.axes:
            axis.tick_params(colors=c["axis_text"], labelsize=8)
            for spine in axis.spines.values():
                spine.set_color(c["axis"])
            axis.xaxis.label.set_color(c["axis_text"])
            axis.yaxis.label.set_color(c["axis_text"])
            axis.title.set_color(c["text"])
            for line in axis.get_xgridlines() + axis.get_ygridlines():
                line.set_color(c["grid"])
        if self.bars:
            for bar in self.bars:
                bar.set_facecolor(c["accent"])
                bar.set_edgecolor(c["histogram"])
        self.canvas.get_tk_widget().configure(background=c["panel"])

    def apply_theme(self):
        self.theme.apply(self.theme_var.get())
        c = self.theme.colors
        self.toolbar.configure(background=c["panel"])
        for child in self.toolbar.winfo_children():
            if isinstance(child, (tk.Button, tk.Checkbutton)):
                child.configure(background=c["button"], foreground=c["text"],
                                activebackground=c["hover"], activeforeground=c["text"])
                if isinstance(child, tk.Checkbutton):
                    child.configure(selectcolor=c["checked"])
                self.toolbar._set_image_for_button(child)
            elif isinstance(child, tk.Label):
                child.configure(background=c["panel"], foreground=c["text"])
            elif isinstance(child, tk.Frame):
                child.configure(background=c["panel"])
        for widget in (self.port_combo, self.baud_combo, self.display_mode_combo):
            popdown = widget.tk.call("ttk::combobox::PopdownWindow", str(widget))
            widget.tk.call(popdown + ".f.l", "configure", "-background", c["input"],
                           "-foreground", c["text"], "-selectbackground", c["popup_selection"],
                           "-selectforeground", c["text"])
        self._plot_colors()
        self.canvas.draw_idle()

    def _navigation_finished(self, event):
        if self.toolbar.mode:
            self.autoscale_var.set(False)

    def _draw_finished(self, event):
        # Limit redraws from actual paint completion, including slow/high-DPI
        # renderers; acquisition still advances independently between frames.
        self.last_render = time.monotonic()

    def reset_view(self):
        self.autoscale_var.set(True)
        self.ax.set_xlim(-0.7, 17.7)
        self.dirty = True

    def save_csv(self):
        if not len(self.buffer):
            self.show_dialog("CSV mentés", "Még nincs menthető adat.")
            return
        path = filedialog.asksaveasfilename(parent=self.master, title="Mérési puffer mentése",
                                           defaultextension=".csv", filetypes=[("CSV fájl", "*.csv")])
        if path:
            try:
                self.buffer.save_csv(path)
                self._log("CSV mentve: " + path)
                self.status_var.set("CSV mentve · részletes útvonal az adatnaplóban")
            except OSError as exc:
                self.show_dialog("Mentési hiba", str(exc))

    def show_dialog(self, title, message):
        dialog = self.theme.register(tk.Toplevel(self.master), background="window")
        dialog.title(title)
        dialog.transient(self.master)
        p = self.theme.px
        dialog.geometry("{}x{}".format(p(520), p(300)))
        body = ttk.Frame(dialog, padding=p(18))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=title, style="Title.TLabel").pack(anchor="w", pady=(0, p(10)))
        text = self.theme.register(tk.Text(body, width=1, height=5, wrap="word", relief="flat", borderwidth=0),
                                   background="window", foreground="text", selectbackground="selection",
                                   selectforeground="selection_text")
        text.pack(fill="both", expand=True)
        text.insert("1.0", message)
        text.configure(state="disabled")
        ttk.Button(body, text="Bezárás", command=dialog.destroy).pack(anchor="e", pady=(p(10), 0))
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        return dialog

    def show_help(self):
        self.show_dialog("Használat és rendszer",
                         "Válassz portot (Windows: COM3; Linux: /dev/ttyUSB0 vagy /dev/ttyACM0), "
                         "majd indíts mérést. A demóhoz nem kell eszköz.\n\n"
                         "A bemenet soronként 18, vesszővel elválasztott érték. "
                         "A CSV és a waterfall az utolsó N mintát tartalmazza. A hisztogram alapból "
                         "a legfrissebb mintát mutatja; az átlagolás külön állítható (1 = élő). "
                         "Nagyobb átlagolási ablak lassítja a változások követését. "
                         "Új mérés új puffert kezd.\n\n"
                         "Nagyítás / eltolás után az automatikus skálázás kikapcsol. "
                         "A Nézet alaphelyzetbe gomb visszaállítja.\n\nPython: " + sys.executable +
                         "\nVenv: " + sys.prefix)

    def close(self):
        self.closing = True
        self.stop_measurement()
        self.status_var.set("Kilépés · soros kapcsolat lezárása…")

    def _cancel_canvas_callbacks(self):
        for tip in self.tooltips:
            tip.hide()
        # Tk must not execute a pending Matplotlib callback after canvas destruction.
        for attribute in ("_idle_draw_id", "_event_loop_id"):
            callback = getattr(self.canvas, attribute, None)
            if callback:
                self.canvas.get_tk_widget().after_cancel(callback)
                setattr(self.canvas, attribute, None)


def main():
    parser = argparse.ArgumentParser(description="AS7265x spektrális adatgyűjtő")
    parser.add_argument("--demo", action="store_true", help="Eszköz nélküli demómérés")
    parser.add_argument("--check-env", action="store_true", help="Venv és függőségek ellenőrzése")
    args = parser.parse_args()
    if args.check_env:
        print("Python: {}\nVenv: {}\nTk: {}\nKörnyezet rendben."
              .format(sys.executable, sys.prefix, tk.TkVersion))
        return
    if os.name == "nt":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print("Nem nyitható grafikus ablak. Linuxon grafikus munkamenet / DISPLAY szükséges.\n{}"
              .format(exc), file=sys.stderr)
        raise SystemExit(1)
    SpectralReader(root, demo=args.demo)
    root.mainloop()


if __name__ == "__main__":
    main()
