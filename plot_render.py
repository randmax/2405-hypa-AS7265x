"""Fast histogram painting without redrawing axes, text or the whole Tk bitmap."""
import math


def nice_ceiling(value):
    if value <= 0:
        return 0.0
    power = 10 ** math.floor(math.log10(value))
    fraction = value / power
    return next(step * power for step in (1, 2, 5, 10) if fraction <= step)


class HistogramBlitter:
    def __init__(self, canvas, axes, bars):
        self.canvas, self.axes, self.bars = canvas, axes, bars
        self.background = None
        self.bounds = None
        for bar in bars:
            bar.set_animated(canvas.supports_blit)

    def invalidate(self):
        self.background = None

    def capture(self):
        if not self.canvas.supports_blit:
            return
        self.background = self.canvas.copy_from_bbox(self.axes.bbox)
        self.bounds = (self.axes.get_xlim(), self.axes.get_ylim(), tuple(self.axes.bbox.bounds))
        self._artists()

    def _artists(self):
        for bar in self.bars:
            self.axes.draw_artist(bar)

    def draw(self):
        bounds = (self.axes.get_xlim(), self.axes.get_ylim(), tuple(self.axes.bbox.bounds))
        if self.background is None or self.canvas.figure.stale or bounds != self.bounds:
            self.canvas.draw_idle()
            return False
        self.canvas.restore_region(self.background)
        self._artists()
        self.canvas.blit(self.axes.bbox)
        return True
