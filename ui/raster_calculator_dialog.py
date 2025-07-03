import re
from typing import Optional, List, Tuple, Dict
from PyQt5.QtWidgets import (
    QDialog,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QTextEdit,
    QComboBox,
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QSettings


class RasterCalculatorDialog(QDialog):
    """
    A dialog for performing custom raster calculations with presets, history,
    and real-time validation.
    """

    def __init__(self, available_bands: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Raster Calculator")
        self.setMinimumWidth(550)

        self.available_bands = available_bands
        self.formula = ""
        self.output_name = ""
        self.coefficients = {}

        # --- Formula Presets and History ---
        self.presets = {
            "GNDVI (Green NDVI)": "(nir - green) / (nir + green)",
            "NDWI (Water Index)": "(green - nir) / (green + nir)",
            "SAVI (Soil-Adjusted)": "((nir - red) / (nir + red + L)) * (1.0 + L)",
            "EVI (Enhanced)": "G * ((nir - red) / (nir + C1 * red - C2 * blue + L))",
        }
        self.history_settings_key = "IDPMPlugin/calculatorHistory"
        self.history = self._load_history()

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- Top Section: Bands and Presets ---
        top_layout = QHBoxLayout()

        # --- Band List ---
        bands_layout = QVBoxLayout()
        bands_layout.addWidget(QLabel("Available Bands (Double-click to add):"))
        self.bands_list_widget = QListWidget()
        for band in available_bands:
            self.bands_list_widget.addItem(QListWidgetItem(band))
        self.bands_list_widget.itemDoubleClicked.connect(self._on_band_double_clicked)
        bands_layout.addWidget(self.bands_list_widget)
        top_layout.addLayout(bands_layout, 2)  # Give more space to bands list

        # --- Presets and History ---
        presets_layout = QVBoxLayout()
        presets_layout.addWidget(QLabel("Presets & History:"))
        self.presets_combo = QComboBox()
        self._populate_presets_combo()
        self.presets_combo.currentIndexChanged.connect(self._on_preset_selected)
        presets_layout.addWidget(self.presets_combo)
        presets_layout.addStretch()
        top_layout.addLayout(presets_layout, 3)

        # --- Formula Input ---
        formula_layout = QVBoxLayout()
        formula_layout.addWidget(QLabel("Formula:"))
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("e.g., (nir - red) / (nir + red)")
        self.formula_input.setFont(QFont("Monospace"))
        self.formula_input.textChanged.connect(self._validate_formula)
        formula_layout.addWidget(self.formula_input)

        # --- Coefficients Input ---
        coeffs_layout = QVBoxLayout()
        coeffs_layout.addWidget(QLabel("Custom Coefficients (one per line):"))
        self.coeffs_input = QTextEdit()
        self.coeffs_input.setPlaceholderText("L = 0.5\nG = 2.5\nC1 = 6.0\nC2 = 7.5")
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

        main_layout.addLayout(top_layout)
        main_layout.addLayout(formula_layout)
        main_layout.addLayout(coeffs_layout)
        main_layout.addLayout(output_layout)
        main_layout.addWidget(button_box)

        self._validate_formula(self.formula_input.text())  # Initial validation

    def _populate_presets_combo(self):
        """Fills the presets combo box with presets and history."""
        self.presets_combo.blockSignals(True)
        self.presets_combo.clear()
        self.presets_combo.addItem("Select a preset or history...", userData=None)

        # Add Presets
        self.presets_combo.insertSeparator(self.presets_combo.count())
        header_item = self.presets_combo.model().item(self.presets_combo.count() - 1)
        header_item.setText("--- PRESETS ---")
        header_item.setEnabled(False)
        for name, formula in self.presets.items():
            self.presets_combo.addItem(name, userData=formula)

        # Add History
        if self.history:
            self.presets_combo.insertSeparator(self.presets_combo.count())
            header_item = self.presets_combo.model().item(
                self.presets_combo.count() - 1
            )
            header_item.setText("--- HISTORY ---")
            header_item.setEnabled(False)
            for formula in self.history:
                # Show a truncated version in the dropdown for readability
                display_text = formula if len(formula) < 40 else formula[:37] + "..."
                self.presets_combo.addItem(display_text, userData=formula)

        self.presets_combo.blockSignals(False)

    def _on_band_double_clicked(self, item: QListWidgetItem):
        """Inserts the band name into the formula input at the current cursor position."""
        self.formula_input.insert(f" {item.text()} ")

    def _on_preset_selected(self, index: int):
        """Applies the selected preset/history formula to the input field."""
        formula = self.presets_combo.itemData(index)
        if formula:
            self.formula_input.setText(formula)
            self.presets_combo.setCurrentIndex(0)  # Reset combo after selection

    def _validate_formula(self, text: str):
        """Performs real-time syntax validation on the formula input."""
        # Check for balanced parentheses
        balance = 0
        for char in text:
            if char == "(":
                balance += 1
            elif char == ")":
                balance -= 1
            if balance < 0:
                break  # An closing parenthesis came before an opening one

        if balance != 0:
            # Invalid: unbalanced parentheses
            self.formula_input.setStyleSheet("border: 1px solid red;")
            return False
        else:
            # Valid (or at least, parentheses are balanced)
            self.formula_input.setStyleSheet("")  # Revert to default stylesheet
            return True

    def _load_history(self) -> List[str]:
        """Loads formula history from QSettings."""
        settings = QSettings()
        return settings.value(self.history_settings_key, [], type=list)

    def _save_history(self, new_formula: str):
        """Saves a new formula to the history, keeping it unique and limited in size."""
        if new_formula in self.history:
            self.history.remove(new_formula)
        self.history.insert(0, new_formula)
        # Keep the history list to a maximum of 5 items
        self.history = self.history[:5]

        settings = QSettings()
        settings.setValue(self.history_settings_key, self.history)

    def accept(self):
        """Validate inputs and parse coefficients before accepting the dialog."""
        from .themed_message_box import ThemedMessageBox

        if not self._validate_formula(self.formula_input.text()):
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Invalid Formula",
                "The formula has unbalanced parentheses.",
            )
            return

        self.formula = self.formula_input.text().strip()
        self.output_name = self.output_name_input.text().strip()

        if not self.formula or not self.output_name:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Input Error",
                "Both a formula and an output name are required.",
            )
            return

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
                    ThemedMessageBox.show_message(
                        self,
                        QMessageBox.Critical,
                        "Input Error",
                        f"Invalid number for coefficient '{key}'.",
                    )
                    return
            else:
                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Critical,
                    "Input Error",
                    f"Invalid coefficient format: '{line}'. Please use 'key = value'.",
                )
                return

        # --- New Validation Step ---
        # Find all potential variables in the formula
        formula_vars = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", self.formula))

        # Define all known names (bands and user-defined coefficients)
        known_names = set(self.available_bands) | set(self.coefficients.keys())

        # Find any variables in the formula that are not known
        undefined_vars = formula_vars - known_names

        if undefined_vars:
            missing_str = ", ".join(sorted(list(undefined_vars)))
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Missing Coefficients",
                f"The following variables are used in the formula but have not been defined in the coefficients box:\n\n{missing_str}",
            )
            return
        # --- End of New Validation ---

        # Save the valid formula to history
        self._save_history(self.formula)
        super().accept()

    def get_calculation_details(self) -> Tuple[str, str, Dict[str, float]]:
        """Returns the user-defined formula, output name, and coefficients."""
        return self.formula, self.output_name, self.coefficients
