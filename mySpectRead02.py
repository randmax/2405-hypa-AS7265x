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
from plot_render import HistogramBlitter, nice_ceiling
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
        self.histogram_blitter = None
        self.last_scale_change = 0.0
        self.presented_frames = 0
        self.presented_at = 0.0
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
        self.device_available = False
        self.device_state = None
        self.pending_device = {}
        self.measurement_format = "calibrated"
        self.device_info_var = tk.StringVar(value="Panelvezérlés: az új Nano firmware szükséges.")
        self.temperature_var = tk.StringVar(value="Hőmérséklet: — / — / — °C")
        self.gain_var = tk.StringVar(value="16×")
        self.cycles_var = tk.StringVar(value="10")
        self.sensor_format_var = tk.StringVar(value="Kalibrált")
        self.led_vars = [tk.BooleanVar(value=False) for _ in range(3)]
        self.led_current_vars = [tk.StringVar(value="12.5 mA") for _ in range(3)]
        self.indicator_vars = [tk.BooleanVar(value=False) for _ in range(3)]
        self.indicator_current_vars = [tk.StringVar(value="1 mA") for _ in range(3)]
        self.board_widgets = []
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
        self._board_panel()
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
        self._board_controls()
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

    def _board_panel(self):
        p = self.theme.px
        panel = self._section("Nano / szenzor vezérlése")
        ttk.Label(panel, textvariable=self.device_info_var, style="Muted.TLabel",
                  wraplength=p(235)).pack(fill="x", pady=(0, p(8)))
        for index, name in enumerate(("Fehér · AS72651", "IR · AS72652", "UV · AS72653")):
            row = ttk.Frame(panel, style="Panel.TFrame")
            row.pack(fill="x", pady=p(3))
            check = ttk.Checkbutton(row, text=name, variable=self.led_vars[index],
                                    command=lambda i=index: self._send_led(i))
            check.pack(side="left", fill="x", expand=True)
            current = ttk.Combobox(row, textvariable=self.led_current_vars[index], width=8,
                                    state="readonly", values=("12.5 mA", "25 mA", "50 mA", "100 mA"))
            current.pack(side="right")
            current.bind("<<ComboboxSelected>>", lambda event, i=index: self._send_led(i))
            self.guard.watch(current)
            self.board_widgets.extend((check, current))
            check.device_command = current.device_command = "LED"
        self.off_btn = ttk.Button(panel, text="Minden LED kikapcsolása", command=lambda: self._send_device("OFF"))
        self.off_btn.pack(fill="x", pady=(p(6), p(10)))
        self.gain_combo = self._field(panel, "Szenzor erősítése", self.gain_var,
                                      values=("1×", "3.7×", "16×", "64×"))
        self.cycles_entry = self._field(panel, "Integrációs ciklus / bank (1–256)", self.cycles_var, maximum=256)
        self.sensor_format_combo = self._field(panel, "Szenzoradat típusa", self.sensor_format_var,
                                               values=("Kalibrált", "Nyers"))
        self.sensor_apply_btn = ttk.Button(panel, text="Mérési beállítások alkalmazása", command=self._apply_sensor)
        self.sensor_apply_btn.pack(fill="x", pady=p(5))
        ttk.Label(panel, text="18 csatorna: kb. 2 × ciklus × 2,8 ms + kiolvasás. Rövidebb idő: gyorsabb, zajosabb mérés.",
                  style="Muted.TLabel", wraplength=p(235)).pack(fill="x", pady=(p(3), p(8)))
        self.stream_btn = ttk.Button(panel, text="Adatküldés szüneteltetése", command=self._toggle_stream)
        self.stream_btn.pack(fill="x", pady=p(3))
        self.shot_btn = ttk.Button(panel, text="Egy mérés (szünetben)", command=lambda: self._send_device("SHOT"))
        self.shot_btn.pack(fill="x", pady=p(3))
        ttk.Label(panel, text="Jelző LED-ek (ha ki vannak építve)", style="Panel.TLabel").pack(anchor="w", pady=(p(10), p(3)))
        for index, name in enumerate(("AS72651", "AS72652", "AS72653")):
            row = ttk.Frame(panel, style="Panel.TFrame")
            row.pack(fill="x", pady=p(3))
            check = ttk.Checkbutton(row, text=name, variable=self.indicator_vars[index],
                                    command=lambda i=index: self._send_led(i, indicator=True))
            check.pack(side="left", fill="x", expand=True)
            current = ttk.Combobox(row, textvariable=self.indicator_current_vars[index], width=8,
                                    state="readonly", values=("1 mA", "2 mA", "4 mA", "8 mA"))
            current.pack(side="right")
            current.bind("<<ComboboxSelected>>", lambda event, i=index: self._send_led(i, indicator=True))
            self.guard.watch(current)
            self.board_widgets.extend((check, current))
            check.device_command = current.device_command = "IND"
        ttk.Label(panel, textvariable=self.temperature_var, style="Muted.TLabel", wraplength=p(235)).pack(fill="x", pady=p(8))
        self.temp_btn = ttk.Button(panel, text="Hőmérsékletek / állapot lekérése", command=lambda: self._send_device("TEMP"))
        self.temp_btn.pack(fill="x")
        self.board_widgets.extend((self.gain_combo, self.cycles_entry, self.sensor_format_combo,
                                   self.sensor_apply_btn, self.stream_btn, self.shot_btn, self.temp_btn))
        self.stream_btn.device_command = "RUN"
        self.shot_btn.device_command = "SHOT"
        self.temp_btn.device_command = "TEMP"
        self.sections[-1].toggle()

    def _board_controls(self):
        available = bool(self.device_available and self.worker and self.running and not self.closing)
        busy = bool(self.pending_device)
        caps = set(self.worker.protocol.hello["caps"]) if available and self.worker.protocol.hello else set()
        for widget in self.board_widgets:
            supported = getattr(widget, "device_command", "SET") in caps
            state = "disabled" if not available or busy or not supported else ("readonly" if isinstance(widget, ttk.Combobox) else "normal")
            widget.configure(state=state)
        self.off_btn.configure(state="normal" if available and "OFF" in caps else "disabled")
        if available and not busy and self.device_state and self.device_state["stream"]:
            self.shot_btn.configure(state="disabled")

    def _send_device(self, op, *args):
        if not self.worker or not self.device_available or not self.running:
            return
        if op == "OFF" and "OFF" in self.pending_device.values():
            return
        try:
            request = self.worker.command(op, *args)
            self.pending_device[request] = op
            self.device_info_var.set("Parancs elküldve · visszaigazolásra vár…")
            self._board_controls()
        except ValueError as exc:
            self._device_event({"type": "error", "id": 0, "message": str(exc)})

    def _send_led(self, index, indicator=False):
        variables = self.indicator_vars if indicator else self.led_vars
        currents = self.indicator_current_vars if indicator else self.led_current_vars
        choices = ("1 mA", "2 mA", "4 mA", "8 mA") if indicator else ("12.5 mA", "25 mA", "50 mA", "100 mA")
        self._send_device("IND" if indicator else "LED", index, int(variables[index].get()), choices.index(currents[index].get()))

    def _apply_sensor(self):
        try:
            gain = ("1×", "3.7×", "16×", "64×").index(self.gain_var.get())
            cycles = self._integer(self.cycles_var, 256, "Integrációs ciklus")
            self._send_device("SET", gain, cycles, "raw" if self.sensor_format_var.get() == "Nyers" else "calibrated")
        except ValueError as exc:
            self.device_info_var.set(str(exc))

    def _toggle_stream(self):
        if self.device_state:
            self._send_device("RUN", 0 if self.device_state["stream"] else 1)

    def _device_event(self, message):
        kind = message["type"]
        request = message.get("id", 0)
        acknowledged = self.pending_device.pop(request, None)
        if kind == "pong":
            return
        if kind == "hello":
            self.device_available = bool(message["sensor_ok"])
            self.device_info_var.set("{} · firmware {}{}".format(message["board"], message["firmware"],
                                     "" if self.device_available else " · szenzorhiba"))
        elif kind == "state":
            self.device_state = message
            self.gain_var.set(("1×", "3.7×", "16×", "64×")[message["gain"]])
            self.cycles_var.set(str(message["cycles"]))
            self.sensor_format_var.set("Nyers" if message["format"] == "raw" else "Kalibrált")
            self.measurement_format = message["format"]
            for index in range(3):
                self.led_vars[index].set(bool(message["led"][index]))
                self.led_current_vars[index].set(("12.5 mA", "25 mA", "50 mA", "100 mA")[message["current"][index]])
                self.indicator_vars[index].set(bool(message["indicator"][index]))
                self.indicator_current_vars[index].set(("1 mA", "2 mA", "4 mA", "8 mA")[message["indicator_current"][index]])
            self.stream_btn.configure(text="Adatküldés szüneteltetése" if message["stream"] else "Adatküldés folytatása")
            if acknowledged:
                self.device_info_var.set("Visszaigazolva · {}".format(acknowledged))
            self.dirty = True
            if not len(self.buffer):
                self.save_btn.configure(state="disabled")
        elif kind == "temperature":
            self.temperature_var.set("51 / 52 / 53: {} / {} / {} °C".format(*message["values"]))
            if acknowledged:
                self.device_info_var.set("Hőmérsékletek visszaigazolva.")
        elif kind in {"error", "timeout"}:
            if self.device_state:
                # Requested checkbox/input values are not evidence of an applied
                # hardware setting. Restore the last confirmed values on failure.
                confirmed = self.device_state
                for index in range(3):
                    self.led_vars[index].set(bool(confirmed["led"][index]))
                    self.indicator_vars[index].set(bool(confirmed["indicator"][index]))
                    self.led_current_vars[index].set(("12.5 mA", "25 mA", "50 mA", "100 mA")[confirmed["current"][index]])
                    self.indicator_current_vars[index].set(("1 mA", "2 mA", "4 mA", "8 mA")[confirmed["indicator_current"][index]])
                self.gain_var.set(("1×", "3.7×", "16×", "64×")[confirmed["gain"]])
                self.cycles_var.set(str(confirmed["cycles"]))
                self.sensor_format_var.set("Nyers" if confirmed["format"] == "raw" else "Kalibrált")
            self.device_info_var.set("Panelhiba · " + message["message"])
            self._log("Panel: " + message["message"])
        elif kind == "cancelled":
            self._log(message["message"])
        self._board_controls()

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
        self.device_available = False
        self.device_state = None
        self.pending_device.clear()
        self.measurement_format = "calibrated"
        self.device_info_var.set("Panel firmware keresése… Régi CSV-firmware is olvasható.")
        self.running = True
        self._controls(True)
        self.save_btn.configure(state="disabled")
        self.status_var.set("Kapcsolódás…")
        self._log("Új mérés indul. Az előző mérés pufferét lecseréltük.")
        self.dirty = True
        self.worker.start()
        self._board_controls()
        self.master.after_cancel(self.timer)
        self.timer = self.master.after(0, self._tick)

    def _controls(self, active):
        for widget in (self.port_combo, self.baud_combo, self.demo_check, self.refresh_btn):
            widget.configure(state="disabled" if active else "normal")
        if not active:
            self.baud_combo.configure(state="readonly")
        self.start_btn.configure(state="disabled" if active else "normal")
        self.stop_btn.configure(state="normal" if active else "disabled")
        if not active:
            self.device_available = False
            self.pending_device.clear()
            self.device_info_var.set("Kapcsolat zárva · új csatlakozással vezérelhető.")
        self._board_controls()

    def stop_measurement(self):
        if self.worker:
            self.worker.stop_event.set()
            self.running = False
            self.status_var.set("Leállítás…")
            self.stop_btn.configure(state="disabled")
            self._board_controls()

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
            elif kind == "device":
                self._device_event(payload)
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
        elif self.dirty and time.monotonic() - self.last_render >= 1 / 30:
            self.update_plot()
            self.last_render = time.monotonic()
            self.dirty = False
        self._flush_log()
        self.timer = self.master.after(10 if self.worker else 150, self._tick)

    def _build_plot(self, mode):
        # Only a deliberate view change rebuilds axes/artists.
        if self.mode:
            self.view_limits[self.mode] = (self.ax.get_xlim(), self.ax.get_ylim())
        self.figure.clear()
        self.histogram_blitter = None
        self.ax = self.figure.add_subplot(111)
        self.bars = self.image = self.colorbar = None
        self.mode = mode
        self.ax.set_xticks(np.arange(18), [str(w) for w in WAVELENGTHS], rotation=45, ha="right")
        self.ax.set_xlabel("Hullámhossz (nm)")
        if mode == "Histogram":
            self.bars = self.ax.bar(np.arange(18), np.zeros(18), width=0.72, zorder=3)
            self.histogram_blitter = HistogramBlitter(self.canvas, self.ax, self.bars)
            self.ax.set_title("Élő spektrum", loc="left", fontsize=11, fontweight="bold")
            self.ax.set_ylabel("ADC érték" if self.measurement_format == "raw" else "Kalibrált intenzitás")
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
            ylabel = "ADC érték" if self.measurement_format == "raw" else "Kalibrált intenzitás"
            if self.ax.get_ylabel() != ylabel:
                self.ax.set_ylabel(ylabel, color=self.theme.colors["axis_text"])
            title = ("Élő spektrum · legfrissebb minta" if average == 1 else
                     "Átlagolt spektrum · {} minta".format(min(average, snapshot.count)))
            if self.ax.get_title(loc="left") != title:
                self.ax.set_title(title, loc="left", fontsize=11, fontweight="bold",
                                  color=self.theme.colors["text"])
            for bar, value in zip(self.bars, values):
                bar.set_height(value)
            if self.autoscale_var.get():
                low = -nice_ceiling(max(0, -float(values.min())) * 1.1)
                high = nice_ceiling(max(1, float(values.max())) * 1.1)
                old_low, old_high = self.ax.get_ylim()
                now = time.monotonic()
                expand = low < old_low or high > old_high
                shrink = high - low < (old_high - old_low) * 0.55
                if expand or (shrink and now - self.last_scale_change > 1.0):
                    self.ax.set_ylim(low, high)
                    self.last_scale_change = now
        else:
            ylabel = "ADC érték" if self.measurement_format == "raw" else "Kalibrált intenzitás"
            if self.colorbar.ax.get_ylabel() != ylabel:
                self.colorbar.set_label(ylabel, color=self.theme.colors["axis_text"])
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
        if self.histogram_blitter is not None:
            if self.histogram_blitter.draw():
                self._frame_presented()
        else:
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
        if self.histogram_blitter is not None:
            self.histogram_blitter.invalidate()
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
        if event.canvas is not self.canvas or self.canvas.is_saving():
            if self.histogram_blitter is not None:
                self.histogram_blitter.invalidate()
            return
        if self.histogram_blitter is not None:
            self.histogram_blitter.capture()
        self._frame_presented()

    def _frame_presented(self):
        self.last_render = time.monotonic()
        self.presented_at = self.last_render
        self.presented_frames += 1

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
                         "Panelvezérlés: a firmware/AS7265xController programot előbb töltsd a Nanóra. "
                         "Bekötés: SDA=A4, SCL=A5. A Nano / szenzor vezérlése szekcióban a LED-ek, "
                         "áramok, erősítés, integráció és hőmérsékletek érhetők el.\n\n"
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
