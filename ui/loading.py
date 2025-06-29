import math
from PyQt5.QtWidgets import QDialog, QWidget, QVBoxLayout
from PyQt5.QtGui import QPainter, QColor, QPaintEvent
from PyQt5.QtCore import Qt, QTimer, QPoint


class SpinnerWidget(QWidget):
    """A custom widget that paints an animated loading spinner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(80, 80)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        # Animation speed: a lower interval is faster
        self._timer.setInterval(50)

        self.num_dots = 12
        self.dot_radius = 5
        # The color of the spinner dots
        self.trail_color = QColor(255, 255, 255)

    def _update_animation(self):
        """Rotates the spinner by one step."""
        self._angle = (self._angle + 360 // self.num_dots) % 360
        self.update()  # Trigger a repaint

    def start(self):
        """Starts the animation timer."""
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        """Stops the animation timer."""
        if self._timer.isActive():
            self._timer.stop()

    def paintEvent(self, event: QPaintEvent):
        """Paints the spinner dots with fading opacity."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        # Calculate the radius of the circle on which dots are drawn
        radius = min(self.width(), self.height()) / 2 - self.dot_radius * 2

        for i in range(self.num_dots):
            # Calculate the angle for the current dot
            angle_rad = math.radians(self._angle - (i * (360 // self.num_dots)))

            # Calculate dot position on the circle
            x = center.x() + radius * math.cos(angle_rad)
            y = center.y() + radius * math.sin(angle_rad)

            # Calculate opacity (alpha) to create a fading tail effect
            alpha = int(255 * (1.0 - (i / self.num_dots)))
            self.trail_color.setAlpha(alpha)

            painter.setBrush(self.trail_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(
                QPoint(int(x), int(y)), self.dot_radius, self.dot_radius
            )


class LoadingDialog(QDialog):
    """A simple, frameless, themed loading indicator dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Make the dialog frameless and have a transparent background
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(120, 120)

        # Use our custom spinner widget instead of a QMovie
        self.spinner = SpinnerWidget(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.spinner)

        # This stylesheet creates the dark, rounded, semi-transparent background
        # using a color from your theme.
        self.setStyleSheet(
            """
            QDialog {
                background-color: rgba(46, 68, 52, 0.85); /* Themed from #2E4434 */
                border-radius: 16px;
            }
            """
        )

    def start_animation(self):
        """Public method to start the spinner."""
        self.spinner.start()

    def stop_animation(self):
        """Public method to stop the spinner."""
        self.spinner.stop()

    def showEvent(self, event):
        """Center the dialog on the parent and start animation when shown."""
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.center() - self.rect().center())
        super().showEvent(event)
        self.start_animation()

    def hideEvent(self, event):
        """Stop animation when the dialog is hidden."""
        self.stop_animation()
        super().hideEvent(event)
