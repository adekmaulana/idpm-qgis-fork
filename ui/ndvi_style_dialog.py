from typing import Optional, List, Tuple
from PyQt5.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QDoubleSpinBox,
    QColorDialog,
    QDialogButtonBox,
)
from PyQt5.QtGui import QColor, QPalette, QIcon
from PyQt5.QtCore import Qt
from qgis.core import QgsColorRampShader

from ..config import Config


class ColorPickerButton(QPushButton):
    """A button that displays a color and opens a color dialog on click."""

    def __init__(self, initial_color: QColor, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color = QColor()
        self.setColor(initial_color)
        self.clicked.connect(self.pick_color)
        self.setFixedSize(40, 28)

    def getColor(self) -> QColor:
        return self._color

    def setColor(self, color: QColor):
        if color.isValid():
            self._color = color
            self.setStyleSheet(f"background-color: {self._color.name()};")

    def pick_color(self):
        new_color = QColorDialog.getColor(self._color, self)
        self.setColor(new_color)


class NdviStyleDialog(QDialog):
    """A dialog to let users customize the NDVI classification style."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Customize NDVI Classification")
        self.setMinimumWidth(500)

        self.rows: List[Tuple[QDoubleSpinBox, ColorPickerButton, QLineEdit]] = []

        main_layout = QVBoxLayout(self)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        grid_layout.addWidget(QLabel("Upper Value"), 0, 0)
        grid_layout.addWidget(QLabel("Color"), 0, 1)
        grid_layout.addWidget(QLabel("Label"), 0, 2)

        # Default classification values
        defaults = [
            (0.0, QColor(0, 0, 255), "Water/Non-Vegetation"),
            (0.2, QColor(255, 255, 0), "Jarang (Sparse)"),
            (0.5, QColor(0, 255, 0), "Sedang (Medium)"),
            (1.0, QColor(0, 100, 0), "Rapat (Dense)"),
        ]

        for i, (value, color, label) in enumerate(defaults):
            spin_box = QDoubleSpinBox()
            spin_box.setRange(-1.0, 1.0)
            spin_box.setSingleStep(0.1)
            spin_box.setValue(value)

            color_button = ColorPickerButton(color)

            label_edit = QLineEdit(label)

            grid_layout.addWidget(spin_box, i + 1, 0)
            grid_layout.addWidget(color_button, i + 1, 1)
            grid_layout.addWidget(label_edit, i + 1, 2)

            self.rows.append((spin_box, color_button, label_edit))

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout.addLayout(grid_layout)
        main_layout.addWidget(button_box)

    def get_classification_items(self) -> List[QgsColorRampShader.ColorRampItem]:
        """Returns the configured classification as a list of ColorRampItems."""
        items = []
        for spin_box, color_button, label_edit in self.rows:
            value = spin_box.value()
            color = color_button.getColor()
            label = label_edit.text()
            items.append(QgsColorRampShader.ColorRampItem(value, color, label))
        return items
