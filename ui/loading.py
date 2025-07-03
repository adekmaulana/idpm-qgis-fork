from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

from .spinner_widget import SpinnerWidget


class LoadingDialog(QDialog):
    """
    A simple, frameless, themed loading indicator dialog that uses the
    reusable SpinnerWidget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Make the dialog frameless and have a transparent background
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(120, 120)

        # Use our custom spinner widget
        self.spinner = SpinnerWidget(self)
        # Set the color for this specific loading dialog
        self.spinner.color = QColor(255, 255, 255)
        self.spinner.pen_width = 4.0  # Make the arc thicker for the larger dialog

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.spinner)

        # This stylesheet creates the dark, rounded, semi-transparent background
        self.setStyleSheet(
            """
            QDialog {
                background-color: rgba(46, 68, 52, 0.85); /* Themed from #2E4434 */
                border-radius: 16px;
            }
            """
        )

    def showEvent(self, event):
        """Center the dialog on the parent when shown."""
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.center() - self.rect().center())
        super().showEvent(event)
