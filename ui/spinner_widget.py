import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QTimer, QRectF


class SpinnerWidget(QWidget):
    """A custom widget that programmatically paints an animated loading arc."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(16, 16)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        self._timer.setInterval(20)  # Faster update for smoother rotation

        self.color = QColor(0, 0, 0)
        self.pen_width = 2.0

    def _update_animation(self):
        """Rotates the spinner by 10 degrees and triggers a repaint."""
        self._angle = (self._angle + 10) % 360
        self.update()

    def start(self):
        """Starts the animation timer."""
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        """Stops the animation timer."""
        if self._timer.isActive():
            self._timer.stop()

    def setVisible(self, visible):
        """Overrides setVisible to automatically start/stop the animation."""
        if visible:
            self.start()
        else:
            self.stop()
        super().setVisible(visible)

    def paintEvent(self, event):
        """Paints the rotating arc."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width(), self.height())

        pen = QPen(self.color, self.pen_width, Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)  # Makes the ends of the arc rounded
        painter.setPen(pen)

        # The rectangle for the arc should be inset by half the pen width
        # to avoid the painter clipping the edges.
        rect = QRectF(
            self.pen_width / 2,
            self.pen_width / 2,
            side - self.pen_width,
            side - self.pen_width,
        )

        # QPainter.drawArc uses 1/16th of a degree, so we multiply by 16
        start_angle = self._angle * 16
        span_angle = 270 * 16  # A 270-degree arc (three-quarters of a circle)

        painter.drawArc(rect, start_angle, span_angle)
