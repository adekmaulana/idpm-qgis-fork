from typing import Optional, List, Tuple, Dict
from PyQt5.QtWidgets import (
    QDialog,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QTextEdit,
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class RasterCalculatorDialog(QDialog):
    """
    A dialog for performing custom raster calculations based on available bands.
    """

    def __init__(self, available_bands: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Raster Calculator")
        self.setMinimumWidth(500)

        self.formula = ""
        self.output_name = ""
        self.coefficients = {}

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- Band List ---
        bands_layout = QVBoxLayout()
        bands_layout.addWidget(
            QLabel("Available Bands (Double-click to add to formula):")
        )
        self.bands_list_widget = QListWidget()
        for band in available_bands:
            self.bands_list_widget.addItem(QListWidgetItem(band))
        self.bands_list_widget.itemDoubleClicked.connect(self._on_band_double_clicked)
        bands_layout.addWidget(self.bands_list_widget)

        # --- Formula Input ---
        formula_layout = QVBoxLayout()
        formula_layout.addWidget(QLabel("Formula:"))
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("e.g., (nir - red) / (nir + red + L)")
        self.formula_input.setFont(QFont("Monospace"))
        formula_layout.addWidget(self.formula_input)

        # *** ADDED: Coefficients Input ***
        coeffs_layout = QVBoxLayout()
        coeffs_layout.addWidget(QLabel("Custom Coefficients (one per line):"))
        self.coeffs_input = QTextEdit()
        self.coeffs_input.setPlaceholderText("L = 0.5\nc1 = 2.5")
        self.coeffs_input.setFont(QFont("Monospace"))
        self.coeffs_input.setFixedHeight(80)
        coeffs_layout.addWidget(self.coeffs_input)

        # --- Output Name Input ---
        output_layout = QVBoxLayout()
        output_layout.addWidget(QLabel("Output Layer Name:"))
        self.output_name_input = QLineEdit()
        self.output_name_input.setPlaceholderText("e.g., MyCustomIndex")
        output_layout.addWidget(self.output_name_input)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout.addLayout(bands_layout)
        main_layout.addLayout(formula_layout)
        main_layout.addLayout(coeffs_layout)
        main_layout.addLayout(output_layout)
        main_layout.addWidget(button_box)

    def _on_band_double_clicked(self, item: QListWidgetItem):
        """Inserts the band name into the formula input at the current cursor position."""
        self.formula_input.insert(f" {item.text()} ")

    def accept(self):
        """Validate inputs and parse coefficients before accepting the dialog."""
        self.formula = self.formula_input.text().strip()
        self.output_name = self.output_name_input.text().strip()

        # Parse coefficients
        self.coefficients = {}
        lines = self.coeffs_input.toPlainText().strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("=")
            if len(parts) == 2:
                key = parts[0].strip()
                try:
                    value = float(parts[1].strip())
                    self.coefficients[key] = value
                except ValueError:
                    from .themed_message_box import ThemedMessageBox

                    ThemedMessageBox.show_message(
                        self,
                        QMessageBox.Critical,
                        "Input Error",
                        f"Invalid number for coefficient '{key}'.",
                    )
                    return
            else:
                from .themed_message_box import ThemedMessageBox

                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Critical,
                    "Input Error",
                    f"Invalid coefficient format: '{line}'. Please use 'key = value'.",
                )
                return

        if not self.formula or not self.output_name:
            from .themed_message_box import ThemedMessageBox

            ThemedMessageBox.show_message(
                self,
                1,
                "Input Error",
                "Both a formula and an output name are required.",
            )
            return

        super().accept()

    def get_calculation_details(self) -> Tuple[str, str, Dict[str, float]]:
        """Returns the user-defined formula, output name, and coefficients."""
        return self.formula, self.output_name, self.coefficients
