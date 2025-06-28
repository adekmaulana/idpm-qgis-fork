import os
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout
from PyQt5.QtGui import QMovie
from PyQt5.QtCore import Qt, QSize

from ..config import Config


class LoadingDialog(QDialog):
    """A simple, frameless, themed loading indicator dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Make the dialog frameless and have a transparent background
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(120, 120)

        self.label = QLabel(self)
        self.label.setFixedSize(100, 100)
        self.label.setAlignment(Qt.AlignCenter)

        # Load the GIF using the correct path from Config
        loading_gif_path = os.path.join(Config.ASSETS_PATH, "images", "loading.gif")
        if os.path.exists(loading_gif_path):
            self.movie = QMovie(loading_gif_path)
            self.movie.setScaledSize(QSize(80, 80))
            self.label.setMovie(self.movie)
        else:
            self.label.setText("Loading...")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.label)

        # This stylesheet creates the dark, rounded, semi-transparent background
        self.setStyleSheet(
            """
            QDialog {
                background-color: rgba(0, 0, 0, 0.7);
                border-radius: 16px;
            }
        """
        )

    def start_animation(self):
        if hasattr(self, "movie"):
            self.movie.start()

    def stop_animation(self):
        if hasattr(self, "movie"):
            self.movie.stop()

    def showEvent(self, event):
        """Center the dialog on the parent when shown."""
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.center() - self.rect().center())
        super().showEvent(event)
