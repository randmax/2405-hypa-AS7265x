"""Run with the project venv; Linux CI uses xvfb-run for a real Tk event loop."""
import time
import tkinter as tk
import unittest
from unittest.mock import patch

import numpy as np
from mySpectRead02 import SpectralReader


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.tk.call("tk", "scaling", 2.0)  # Exercise a 150% desktop scale.
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.app = SpectralReader(self.root)
        self.root.update()
        self.app.update_plot()
        self.root.update()

    def tearDown(self):
        if self.app.worker:
            self.app.worker.stop_event.set()
            self.app.worker.join(1)
        self.root.after_cancel(self.app.timer)
        self.app._cancel_canvas_callbacks()
        self.root.destroy()
        self.assertEqual(self.errors, [])

    def test_tooltip_uses_current_theme_and_releases_widgets(self):
        self.app.theme_var.set("Fekete")
        self.app.apply_theme()
        registered = len(self.app.theme.widgets)
        tip = self.app.tooltips[-1]
        tip.show()
        self.root.update()
        label = tip.window.winfo_children()[0]
        self.assertEqual(label.cget("background"), self.app.theme.colors["tooltip"])
        tip.hide()
        self.assertEqual(len(self.app.theme.widgets), registered)

    def pump(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)

    def test_theme_preserves_geometry_values_zoom_and_existing_dialog(self):
        self.app.buffer.append(np.arange(18, dtype=float))
        self.app.update_plot()
        self.app.autoscale_var.set(False)
        self.app.ax.set_xlim(3, 9)
        self.app.ax.set_ylim(2, 7)
        self.app.sections[0].toggle()
        self.root.update()
        geometry = self.root.geometry()
        axes = self.app.ax
        dialog = self.app.show_dialog("Test", "A long message " * 100)
        self.root.update()
        for name in ("Fekete", "Világos"):
            self.app.theme_var.set(name)
            self.app.apply_theme()
            self.root.update()
            self.assertEqual(self.root.geometry(), geometry)
            self.assertEqual(self.app.ax.get_xlim(), (3, 9))
            self.assertEqual(self.app.ax.get_ylim(), (2, 7))
            self.assertIs(self.app.ax, axes)
            self.assertEqual(dialog.cget("background"), self.app.theme.colors["window"])
            self.assertFalse(self.app.sections[0].open)
        dialog.destroy()

    def test_plot_reuses_artists_and_waterfall_oldest_is_top(self):
        self.app.average_count_var.set("3")
        for value in (2, 4, 8):
            self.app.buffer.append(np.full(18, float(value)))
        self.app.update_plot()
        axes, bars = self.app.ax, self.app.bars
        self.app.update_plot()
        self.assertIs(self.app.ax, axes)
        self.assertIs(self.app.bars, bars)
        self.assertAlmostEqual(bars[0].get_height(), 14 / 3)
        self.app.display_mode_var.set("Waterfall")
        self.app.update_plot()
        image = self.app.image
        np.testing.assert_array_equal(np.asarray(image.get_array())[:, 0], [2, 4, 8])
        self.assertGreater(self.app.ax.get_ylim()[0], self.app.ax.get_ylim()[1])
        self.app.update_plot()
        self.assertIs(image, self.app.image)
        self.assertEqual(len(self.app.figure.axes), 2)

    def test_all_channels_follow_latest_sample_without_waiting_for_history(self):
        self.app.sample_count_var.set("1000")
        for _ in range(999):
            self.app.buffer.append(np.full(18, 1000.0))
        latest = np.arange(18, dtype=float)
        self.app.buffer.append(latest)
        self.app.update_plot()
        np.testing.assert_array_equal([bar.get_height() for bar in self.app.bars], latest)
        self.assertEqual(len(self.app.buffer), 1000)
        self.assertIn("legfrissebb minta", self.app.ax.get_title(loc="left"))
        self.app.average_count_var.set("2")
        self.app.update_plot()
        np.testing.assert_allclose([bar.get_height() for bar in self.app.bars], (1000 + latest) / 2)

    def test_first_frame_after_gui_pause_uses_latest_received_sample(self):
        self.app.demo_var.set(True)
        self.app.start_measurement()
        # Deliberately do not run Tk while acquisition keeps receiving samples.
        time.sleep(0.35)
        worker = self.app.worker
        self.assertGreaterEqual(self.app.buffer.received, 3)
        worker.stop_event.set()
        worker.join(1)
        expected = self.app.buffer.snapshot()
        rendered = []
        connection = self.app.canvas.mpl_connect("draw_event", lambda event: rendered.append(
            (time.monotonic(), self.app.last_plotted_received,
             [bar.get_height() for bar in self.app.bars])))
        resumed = time.monotonic()
        self.pump(0.4)
        self.app.canvas.mpl_disconnect(connection)
        self.assertTrue(rendered)
        self.assertEqual(rendered[0][1], expected.received)
        np.testing.assert_array_equal(rendered[0][2], expected.values)
        self.assertLess(rendered[0][0] - resumed, 1.0)

    def test_scaled_bitmap_matches_available_canvas(self):
        widget = self.app.canvas.get_tk_widget()
        self.assertAlmostEqual(self.app.figure.bbox.width, widget.winfo_width(), delta=1)
        self.assertAlmostEqual(self.app.figure.bbox.height, widget.winfo_height(), delta=1)
        self.assertGreater(self.app.theme.scale, 1.4)

    def test_manual_view_is_restored_per_mode(self):
        self.app.autoscale_var.set(False)
        self.app.ax.set_xlim(3, 9)
        self.app.ax.set_ylim(20, 80)
        self.app.display_mode_var.set("Waterfall")
        self.app.update_plot()
        self.app.ax.set_xlim(2, 6)
        self.app.ax.set_ylim(5, 1)
        self.app.display_mode_var.set("Histogram")
        self.app.update_plot()
        self.assertEqual(self.app.ax.get_xlim(), (3, 9))
        self.assertEqual(self.app.ax.get_ylim(), (20, 80))
        self.app.display_mode_var.set("Waterfall")
        self.app.update_plot()
        self.assertEqual(self.app.ax.get_xlim(), (2, 6))
        self.assertEqual(self.app.ax.get_ylim(), (5, 1))

    def test_wheel_requires_click_and_loses_permission_on_focus_out(self):
        widget = self.app.sample_entry
        widget.focus_force()
        self.root.update()
        before = self.app.sample_count_var.get()
        widget.event_generate("<MouseWheel>", delta=120)
        self.root.update()
        self.assertEqual(self.app.sample_count_var.get(), before)
        widget.event_generate("<ButtonPress-1>", x=8, y=8)
        widget.event_generate("<ButtonRelease-1>", x=8, y=8)
        widget.event_generate("<MouseWheel>", delta=120)
        self.root.update()
        self.assertNotEqual(self.app.sample_count_var.get(), before)
        self.app.baud_combo.focus_force()
        self.root.update()
        widget.focus_force()
        self.root.update()
        before = self.app.sample_count_var.get()
        widget.event_generate("<MouseWheel>", delta=120)
        self.root.update()
        self.assertEqual(self.app.sample_count_var.get(), before)

    def test_demo_stop_restart_and_csv_remains_available(self):
        self.app.demo_var.set(True)
        self.app.start_measurement()
        worker = self.app.worker
        self.app.start_measurement()
        self.assertIs(self.app.worker, worker)
        self.pump(0.6)
        self.assertGreater(len(self.app.buffer), 0)
        self.app.stop_measurement()
        self.pump(0.5)
        self.assertIsNone(self.app.worker)
        self.assertFalse(worker.is_alive())
        self.assertEqual(str(self.app.save_btn.cget("state")), "normal")
        self.app.start_measurement()
        self.pump(0.3)
        self.assertIsNot(self.app.worker, worker)

    def test_long_status_small_window_and_log_are_bounded(self):
        p = self.app.theme.px
        self.root.geometry("{}x{}".format(p(820), p(560)))
        self.root.update()
        geometry = self.root.geometry()
        self.app.status_var.set("/very/long/path/" * 300)
        for i in range(30):
            for line in range(100):
                self.app._log("sample {} {}".format(i, line))
            self.app._flush_log()
        self.root.update()
        self.assertEqual(self.root.geometry(), geometry)
        self.assertLessEqual(int(self.app.log_text.index("end-1c").split(".")[0]), 2001)
        self.assertGreater(self.app.toolbar.winfo_height(), 10)
        self.assertGreater(self.app.side_canvas.bbox("all")[3], self.app.side_canvas.winfo_height())
