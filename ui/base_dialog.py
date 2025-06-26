import sys
from typing import Optional

from PyQt5.QtCore import Qt, QSize, QPoint, QTimer
from PyQt5.QtGui import QMouseEvent, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)


class BaseDialog(QDialog):
    """
    A base class for creating custom, frameless, and responsive dialogs.
    It provides functionality for dragging, resizing, and custom window
    controls (minimize, maximize, close).
    """

    parent: Optional[QWidget]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # --- For frameless window interaction ---
        self.old_pos = None
        self.resizing = False
        self.resize_grip_size = 10  # The thickness of the resize handles

        self._init_frameless_ui()

    def _init_frameless_ui(self) -> None:
        """Initializes the frameless window properties."""
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        # --- Set a dynamic size based on a percentage of the screen ---
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        initial_width = int(screen_geometry.width() * 0.8)
        initial_height = int(screen_geometry.height() * 0.8)
        self.resize(initial_width, initial_height)
        self.setMinimumSize(960, 600)

        # Main container that will hold all content and have rounded corners
        self.main_container = QWidget()
        self.main_container.setObjectName("mainContainer")
        self.main_container.setMouseTracking(True)

        # The dialog's own layout just holds the main container
        super_layout = QVBoxLayout(self)
        super_layout.setContentsMargins(0, 0, 0, 0)
        super_layout.addWidget(self.main_container)

    def _create_window_controls(self) -> QHBoxLayout:
        """
        Creates the minimize, maximize, and close buttons and returns them
        in a horizontal layout.
        """
        controls_layout = QHBoxLayout()
        controls_layout.addStretch()

        button_size = QSize(32, 32)

        if sys.platform != "darwin":
            self.minimize_button = QPushButton("—")
            self.minimize_button.setObjectName("minimizeButton")
            self.minimize_button.setFixedSize(button_size)
            self.minimize_button.setCursor(Qt.PointingHandCursor)
            self.minimize_button.setToolTip("Minimize")
            self.minimize_button.clicked.connect(self.showMinimized)
            controls_layout.addWidget(self.minimize_button)

        self.maximize_button = QPushButton("☐")
        self.maximize_button.setObjectName("maximizeButton")
        self.maximize_button.setFixedSize(button_size)
        self.maximize_button.setCursor(Qt.PointingHandCursor)
        self.maximize_button.setToolTip("Maximize")
        self.maximize_button.clicked.connect(self.toggle_maximize)
        controls_layout.addWidget(self.maximize_button)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(button_size)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(self.reject)
        controls_layout.addWidget(self.close_button)

        return controls_layout

    def toggle_maximize(self) -> None:
        """Toggles the window between maximized and normal states."""
        if self.isMaximized():
            self.showNormal()
            self.maximize_button.setText("☐")
            self.maximize_button.setToolTip("Maximize")
        else:
            self.showMaximized()
            self.maximize_button.setText("❐")
            self.maximize_button.setToolTip("Restore Down")

    # --- Methods for dragging and resizing the frameless window ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            if self.isMaximized():
                self.toggle_maximize()
                QTimer.singleShot(0, lambda: self.start_drag(event.globalPos()))
                return

            self.resizing = self._is_on_edge(event.pos())
            if self.resizing:
                self.old_pos = event.globalPos()
            else:
                self.start_drag(event.globalPos())

    def start_drag(self, global_pos: QPoint) -> None:
        """Helper to safely start a drag operation."""
        child = self.childAt(self.mapFromGlobal(global_pos))
        if not isinstance(child, (QLineEdit, QPushButton)):
            self.old_pos = global_pos

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.old_pos = None
            self.resizing = False
            self.unsetCursor()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.resizing and self.old_pos is None:
            if not self.isMaximized():
                self._update_cursor(event.pos())

        if self.resizing:
            delta = QPoint(event.globalPos() - self.old_pos)
            self._resize_window(delta)
            self.old_pos = event.globalPos()
        elif self.old_pos is not None:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def _is_on_edge(self, pos: QPoint) -> bool:
        """Check if the mouse is on the edge of the window."""
        if self.isMaximized():
            return False
        grip = self.resize_grip_size
        return (
            pos.x() < grip
            or pos.x() > self.width() - grip
            or pos.y() < grip
            or pos.y() > self.height() - grip
        )

    def _update_cursor(self, pos: QPoint) -> None:
        """Update cursor shape when hovering over window edges."""
        if self.isMaximized():
            self.unsetCursor()
            return

        grip = self.resize_grip_size
        on_left = pos.x() < grip
        on_right = pos.x() > self.width() - grip
        on_top = pos.y() < grip
        on_bottom = pos.y() > self.height() - grip

        if (on_top and on_left) or (on_bottom and on_right):
            self.setCursor(Qt.SizeFDiagCursor)
        elif (on_top and on_right) or (on_bottom and on_left):
            self.setCursor(Qt.SizeBDiagCursor)
        elif on_left or on_right:
            self.setCursor(Qt.SizeHorCursor)
        elif on_top or on_bottom:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()

    def _resize_window(self, delta: QPoint) -> None:
        """Resize the window based on mouse drag."""
        if self.isMaximized():
            return

        rect = self.geometry()
        pos = self.mapFromGlobal(self.old_pos)
        grip = self.resize_grip_size

        on_left = pos.x() < grip
        on_right = pos.x() > self.width() - grip
        on_top = pos.y() < grip
        on_bottom = pos.y() > self.height() - grip

        if on_top:
            rect.setTop(rect.top() + delta.y())
        if on_bottom:
            rect.setBottom(rect.bottom() + delta.y())
        if on_left:
            rect.setLeft(rect.left() + delta.x())
        if on_right:
            rect.setRight(rect.right() + delta.x())

        if rect.width() < self.minimumWidth():
            rect.setWidth(self.minimumWidth())
        if rect.height() < self.minimumHeight():
            rect.setHeight(self.minimumHeight())

        self.setGeometry(rect)
