"""Shared semantic palette and Tk/ttk styling for all application windows."""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

_COLORS = {
    "window": ("#dce3eb", "#202735"), "text": ("#24334b", "#e0e7f0"),
    "accent": ("#355ccc", "#8eb2ff"), "muted": ("#5d6c82", "#a4b3c7"),
    "border": ("#b5c3d4", "#45546a"), "panel": ("#edf1f5", "#293445"),
    "button": ("#e2e9f2", "#35445b"), "input_border": ("#aebfd2", "#556a85"),
    "hover_border": ("#466ce7", "#779cff"), "hover": ("#cfddf3", "#405779"),
    "checked": ("#c3d6f2", "#365781"), "disabled_text": ("#98a3b5", "#78869a"),
    "disabled": ("#d9e0e8", "#263040"), "disabled_border": ("#dce2ec", "#374459"),
    "input": ("#f5f7fa", "#1e2938"), "popup_selection": ("#c3d6f2", "#405779"),
    "base": ("#edf2f7", "#263244"), "grid": ("#d3dce8", "#3b4b62"),
    "selection": ("#bdd1ef", "#405f8a"), "selection_text": ("#24334b", "#ffffff"),
    "header": ("#c7d4e5", "#354761"), "header_text": ("#344d70", "#c5d6ed"),
    "splitter": ("#afbed1", "#45546a"), "menu": ("#c7d4e5", "#182130"),
    "status": ("#c7d4e5", "#182130"), "scroll_track": ("#d5dee9", "#202c3d"),
    "scroll_handle": ("#8c9fb9", "#607a9a"), "image_background": ("#c4cfdd", "#162235"),
    "histogram": ("#e8eef5", "#233044"), "axis": ("#97a3b5", "#6f86a3"),
    "axis_text": ("#66758e", "#b3c7df"), "tooltip": ("#ffffff", "#354761"),
}
PALETTES = {name: {key: values[i] for key, values in _COLORS.items()}
            for i, name in enumerate(("Világos", "Fekete"))}


class Theme:
    def __init__(self, root):
        self.root = root
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.scale = max(1.0, float(root.tk.call("tk", "scaling")) / (96 / 72))
        families = tkfont.families(root)
        self.family = next((f for f in ("Segoe UI", "DejaVu Sans", "Liberation Sans")
                            if f in families), "sans-serif")
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=self.family, size=-self.px(12))
        self.widgets = []
        self.apply("Világos")

    def px(self, number):
        return round(number * self.scale)

    def register(self, widget, **options):
        entry = (widget, options)
        self.widgets.append(entry)
        def forget(event):
            if event.widget is widget and entry in self.widgets:
                self.widgets.remove(entry)
        widget.bind("<Destroy>", forget, add="+")
        widget.configure(**{key: self.colors[value] for key, value in options.items()})
        return widget

    def apply(self, name):
        self.colors = c = PALETTES[name]
        self.root.configure(background=c["window"])
        s = self.style
        s.configure(".", background=c["window"], foreground=c["text"], font="TkDefaultFont",
                    bordercolor=c["border"], lightcolor=c["panel"], darkcolor=c["border"],
                    troughcolor=c["scroll_track"], selectbackground=c["selection"],
                    selectforeground=c["selection_text"])
        s.map(".", background=[("disabled", c["disabled"]), ("active", c["hover"])],
              foreground=[("disabled", c["disabled_text"])],
              selectbackground=[("!focus", c["selection"])],
              selectforeground=[("!focus", c["selection_text"])])
        for style, token in (("TFrame", "window"), ("Panel.TFrame", "panel"), ("Status.TFrame", "status")):
            s.configure(style, background=c[token])
        s.configure("Panel.TFrame", borderwidth=1, relief="solid")
        for style, bg, fg in (("TLabel", "window", "text"), ("Panel.TLabel", "panel", "text"),
                              ("Muted.TLabel", "panel", "muted"), ("Status.TLabel", "status", "text")):
            s.configure(style, background=c[bg], foreground=c[fg])
        s.configure("Title.TLabel", font=(self.family, -self.px(20), "bold"))
        s.configure("Subtitle.TLabel", foreground=c["muted"])
        s.configure("TButton", background=c["button"], foreground=c["text"],
                    bordercolor=c["input_border"], borderwidth=1, relief="flat",
                    padding=(self.px(10), self.px(8)),
                    font=(self.family, -self.px(12), "bold"), focusthickness=1, focuscolor=c["accent"])
        s.map("TButton", background=[("disabled", c["disabled"]), ("pressed", c["checked"]),
                                     ("active", c["hover"])], foreground=[("disabled", c["disabled_text"])],
              bordercolor=[("disabled", c["disabled_border"]), ("focus", c["hover_border"]),
                           ("active", c["hover_border"])])
        s.configure("Primary.TButton", background="#466ce7", foreground="white", bordercolor="#466ce7")
        s.map("Primary.TButton", background=[("disabled", c["disabled"]), ("active", "#3556ca")],
              foreground=[("disabled", c["disabled_text"]), ("!disabled", "white")])
        s.configure("Header.TButton", background=c["header"], foreground=c["header_text"],
                    anchor="w", padding=self.px(7))
        s.map("Header.TButton", background=[("active", c["checked"])])
        for style in ("TEntry", "TCombobox", "TSpinbox"):
            s.configure(style, fieldbackground=c["input"], foreground=c["text"],
                        background=c["header"], arrowcolor=c["text"], bordercolor=c["input_border"],
                        padding=self.px(5), insertcolor=c["text"], arrowsize=self.px(14))
            s.map(style, fieldbackground=[("disabled", c["disabled"]), ("readonly", c["input"])],
                  foreground=[("disabled", c["disabled_text"]), ("readonly", c["text"])],
                  bordercolor=[("focus", c["accent"])], background=[("active", c["checked"])],
                  arrowcolor=[("disabled", c["disabled_text"])])
        s.configure("TCheckbutton", background=c["panel"], foreground=c["text"],
                    indicatorbackground=c["input"], indicatorforeground=c["accent"])
        s.map("TCheckbutton", background=[("active", c["panel"])],
              foreground=[("disabled", c["disabled_text"])],
              indicatorbackground=[("selected", c["checked"])])
        s.configure("Vertical.TScrollbar", background=c["scroll_handle"], arrowcolor=c["text"],
                    troughcolor=c["scroll_track"], width=self.px(12), arrowsize=self.px(12))
        s.map("Vertical.TScrollbar", background=[("disabled", c["scroll_handle"]),
                                                  ("active", c["hover_border"])],
              arrowcolor=[("disabled", c["muted"])])
        for option, token in (("background", "input"), ("foreground", "text"),
                              ("selectBackground", "popup_selection"), ("selectForeground", "text")):
            self.root.option_add("*TCombobox*Listbox." + option, c[token])
        alive = []
        for widget, options in self.widgets:
            if widget.winfo_exists():
                widget.configure(**{key: c[value] for key, value in options.items()})
                alive.append((widget, options))
        self.widgets = alive


class Tooltip:
    def __init__(self, widget, theme, text):
        self.widget, self.theme, self.text = widget, theme, text
        self.window = self.job = None
        # Replace the Matplotlib toolbar's unthemed tooltip bindings as well.
        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.hide)
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def enter(self, event=None):
        self.hide()
        self.job = self.widget.after(500, self.show)

    def show(self):
        self.job = None
        text = self.text() if callable(self.text) else self.text
        if not text:
            return
        self.window = self.theme.register(tk.Toplevel(self.widget), background="border")
        self.window.overrideredirect(True)
        self.window.geometry("+{}+{}".format(self.widget.winfo_rootx(),
                                             self.widget.winfo_rooty() + self.widget.winfo_height() + 4))
        label = self.theme.register(tk.Label(self.window, text=text, justify="left",
                                              wraplength=self.theme.px(440), padx=8, pady=6),
                                    background="tooltip", foreground="text")
        label.pack(padx=1, pady=1)

    def hide(self, event=None):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None
        if self.window:
            self.window.destroy()
            self.window = None


class Collapsible(ttk.Frame):
    def __init__(self, parent, title, px):
        super().__init__(parent, style="Panel.TFrame", padding=px(8))
        self.title, self.open, self.px = title, True, px
        self.header = ttk.Button(self, style="Header.TButton", command=self.toggle, text="▾  " + title)
        self.header.pack(fill="x")
        self.body = ttk.Frame(self, style="Panel.TFrame", padding=px(2))
        self.body.pack(fill="x", pady=(px(8), 0))

    def toggle(self):
        self.open = not self.open
        self.header.configure(text=("▾  " if self.open else "▸  ") + self.title)
        if self.open:
            self.body.pack(fill="x", pady=(self.px(8), 0))
        else:
            self.body.pack_forget()


class WheelGuard:
    """Run before Tk class bindings, on Windows and Linux/X11 wheel events."""
    def __init__(self, root, scroll):
        self.root, self.scroll, self.armed = root, scroll, None
        root.bind_all("<ButtonPress-1>", self.clicked, add="+")
        self.tag = "SpectReadWheelGuard"
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_class(self.tag, sequence, self.wheel)

    def watch(self, widget):
        widget.bindtags((self.tag,) + widget.bindtags())
        widget.bind("<FocusOut>", lambda event: self.disarm(widget), add="+")

    def clicked(self, event):
        self.armed = event.widget if isinstance(event.widget, (ttk.Combobox, ttk.Spinbox)) else None

    def disarm(self, widget):
        if self.armed is widget:
            self.armed = None

    @staticmethod
    def direction(event):
        return -1 if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0 else 1

    def wheel(self, event):
        widget = event.widget
        if self.armed is not widget or self.root.focus_get() is not widget:
            self.scroll(self.direction(event))
            return "break"
        if isinstance(widget, ttk.Combobox) and str(widget.cget("state")) != "disabled":
            values = widget.cget("values")
            index = max(0, min(len(values) - 1, widget.current() + self.direction(event)))
            if values:
                widget.current(index)
                widget.event_generate("<<ComboboxSelected>>")
            return "break"
        return None
