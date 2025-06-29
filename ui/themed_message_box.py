from PyQt5.QtWidgets import QMessageBox, QWidget
from PyQt5.QtCore import Qt


class ThemedMessageBox(QMessageBox):
    """
    A custom QMessageBox that automatically applies the plugin's theme.
    It supports standard message box icons and buttons.
    """

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setStyleSheet(
            """
            QMessageBox {
                background-color: #5E765F;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                padding: 20px;
            }
            QMessageBox QLabel#qt_msgbox_label { /* Title Label */
                color: white;
                font-family: "Montserrat";
                font-size: 16px;
                font-weight: bold;
            }
            QMessageBox QLabel#qt_msgbox_informativetext { /* Informative Text */
                color: #E0E0E0;
                font-family: "Montserrat";
                font-size: 14px;
            }
            QMessageBox QPushButton {
                background-color: white;
                color: #2E4434;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                min-width: 80px;
                font-weight: bold;
                font-family: "Montserrat";
            }
            QMessageBox QPushButton:hover {
                background-color: #F0F0F0;
            }
        """
        )

    @staticmethod
    def show_message(
        parent: QWidget,
        icon: QMessageBox.Icon,
        title: str,
        text: str,
        buttons=QMessageBox.Ok,
        default_button=QMessageBox.NoButton,
    ) -> int:
        """
        Factory method to create and show a themed message box.

        Args:
            parent: The parent widget.
            icon: The icon to display (e.g., QMessageBox.Information).
            title: The text for the window title bar.
            text: The main message text.
            buttons: Standard buttons to show (e.g., QMessageBox.Yes | QMessageBox.No).
            default_button: The button to be selected by default.

        Returns:
            The standard button that was clicked.
        """
        msg_box = ThemedMessageBox(parent)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setStandardButtons(buttons)
        msg_box.setDefaultButton(default_button)
        return msg_box.exec_()
