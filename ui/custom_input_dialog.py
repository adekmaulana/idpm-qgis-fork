from typing import Optional, List
from PyQt5.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QListView,
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class CustomInputDialog(QDialog):
    """A custom, themed dialog to replace QInputDialog.getItem."""

    def __init__(
        self, parent: Optional[QWidget], title: str, label: str, items: List[str]
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(400)

        self._selected_item = ""

        # --- Layouts and Widgets ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        prompt_label = QLabel(label)
        prompt_label.setFont(QFont("Montserrat", 11))
        prompt_label.setWordWrap(True)

        self.combo_box = QComboBox()
        self.combo_box.addItems(items)
        # --- FIX: Force the dropdown to use a styleable view ---
        self.combo_box.setView(QListView())

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("dialogButton")
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("dialogButton")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        main_layout.addWidget(prompt_label)
        main_layout.addWidget(self.combo_box)
        main_layout.addSpacing(10)
        main_layout.addLayout(button_layout)

        self.apply_stylesheet()

    def accept(self):
        """Store the selected item before closing."""
        self._selected_item = self.combo_box.currentText()
        super().accept()

    def selectedItem(self) -> str:
        """Returns the item that was selected when OK was clicked."""
        return self._selected_item

    def apply_stylesheet(self):
        """Applies the custom theme to the dialog."""
        self.setStyleSheet(
            """
            QDialog {
                background-color: #5E765F;
            }
            QLabel {
                color: white;
                font-family: "Montserrat";
            }
            QComboBox {
                padding: 8px;
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                font-family: "Montserrat";
                font-size: 14px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            QComboBox::drop-down {
                border: none;
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #4A634B;
                selection-background-color: rgba(255, 255, 255, 0.2);
                color: white;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                outline: 0px;
            }
            QPushButton#dialogButton {
                background-color: white;
                color: #2E4434;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-family: "Montserrat";
            }
            QPushButton#dialogButton:hover {
                background-color: #F0F0F0;
            }
        """
        )
