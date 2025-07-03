import json
import os
from PyQt5.QtCore import QUrl, QSettings, QTimer
from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager
from PyQt5.QtWidgets import QAction, QMessageBox, QDialog
from PyQt5.QtGui import QFontDatabase
from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgisInterface

from ..config import Config


class IDPMPlugin:
    """
    Integrated Data Platform Management (IDPM) Plugin for QGIS.
    """

    iface: QgisInterface
    action: QAction
    _menu_dialog_instance: QDialog
    _form_token_manager: QNetworkAccessManager
    _form_token_request_active: bool
    login_dialog_instance: QDialog

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface
        self.action = None
        self._menu_dialog_instance = None
        self._form_token_manager = None
        self._form_token_request_active = False
        self.login_dialog_instance = None
        self.load_custom_fonts()

    def load_custom_fonts(self) -> None:
        """Loads custom fonts from the assets folder."""
        fonts_dir = os.path.join(Config.ASSETS_PATH, "fonts")
        montserrat_dir = os.path.join(fonts_dir, "montserrat")

        if not os.path.exists(montserrat_dir):
            QgsMessageLog.logMessage(
                f"Montserrat font directory not found: {montserrat_dir}",
                "IDPMPlugin",
                Qgis.Warning,
            )
            return

        try:
            font_files = os.listdir(montserrat_dir)
        except FileNotFoundError:
            QgsMessageLog.logMessage(
                f"Could not list files in directory: {montserrat_dir}",
                "IDPMPlugin",
                Qgis.Warning,
            )
            return

        for font_file in font_files:
            font_path = os.path.join(montserrat_dir, font_file)
            if font_file.lower().endswith(".ttf"):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id == -1:
                    QgsMessageLog.logMessage(
                        f"Failed to load font: {font_path}", "IDPMPlugin", Qgis.Warning
                    )
                else:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        QgsMessageLog.logMessage(
                            f"Successfully loaded font: {font_families[0]}",
                            "IDPMPlugin",
                            Qgis.Info,
                        )

    def initGui(self) -> None:
        self.action = QAction("IDPM", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)

    def unload(self) -> None:
        self.iface.removeToolBarIcon(self.action)
        del self.action
        if self._menu_dialog_instance and self._menu_dialog_instance.isVisible():
            try:
                self._menu_dialog_instance.close()
            except RuntimeError:
                pass
        self._menu_dialog_instance = None
        QgsMessageLog.logMessage("MinimalPlugin unloaded.", "IDPMPlugin", Qgis.Info)

    def run(self) -> None:
        from qgis.utils import plugins
        from ..ui import ThemedMessageBox

        if "a00_qpip" not in plugins:
            ThemedMessageBox.show_message(
                self.iface.mainWindow(),
                QMessageBox.Critical,
                "Dependency Missing",
                "The 'qpip' plugin is required for IDPMPlugin to function. "
                "Please install it from the QGIS Plugin Manager.",
            )
            return

        settings = QSettings()
        token = settings.value("IDPMPlugin/token", defaultValue=None, type=str)

        if token:
            self.show_menu_dialog_singleton()
        else:
            if self._form_token_request_active:
                QgsMessageLog.logMessage(
                    "Form token request already in progress.",
                    "IDPMPlugin",
                    Qgis.Warning,
                )
                return
            self.perform_login()

    def show_menu_dialog_singleton(self) -> None:
        """
        Creates and shows the MenuWidget if it doesn't exist,
        or brings the existing one (or its child dialogs) to the front.
        """
        from ..ui import MenuWidget

        if self._menu_dialog_instance is None:
            QgsMessageLog.logMessage(
                "Creating new MenuWidget (singleton).", "IDPMPlugin", Qgis.Info
            )
            self._menu_dialog_instance = MenuWidget(
                iface=self.iface, parent=self.iface.mainWindow()
            )
            self._menu_dialog_instance.finished.connect(self._handle_menu_dialog_closed)
            self._menu_dialog_instance.show()
        else:
            if (
                hasattr(self._menu_dialog_instance, "image_list_dialog")
                and self._menu_dialog_instance.image_list_dialog is not None
            ):
                self._menu_dialog_instance.image_list_dialog.raise_()
                self._menu_dialog_instance.image_list_dialog.activateWindow()
            else:
                self._menu_dialog_instance.raise_()
                self._menu_dialog_instance.activateWindow()

    def _handle_menu_dialog_closed(self, result_code: int) -> None:
        """Slot called when MenuDialog is closed, clears the instance reference."""
        QgsMessageLog.logMessage(
            f"MenuDialog closed (result: {result_code}). Clearing singleton instance.",
            "IDPMPlugin",
            Qgis.Info,
        )
        self._menu_dialog_instance = None

    def perform_login(self) -> None:
        self._form_token_request_active = True
        QgsMessageLog.logMessage(
            "perform_login: Fetching form token.", "IDPMPlugin", Qgis.Info
        )
        message_bar = self.iface.messageBar()
        if message_bar is not None:
            message_bar.pushMessage(
                "IDPMPlugin", "Preparing login...", level=Qgis.Info, duration=0
            )
        self._form_token_manager = QNetworkAccessManager()
        self._form_token_manager.finished.connect(self.handle_form_token_response)
        self._form_token_manager.get(
            QNetworkRequest(QUrl(f"{Config.API_URL}/auth/formtoken"))
        )

    def handle_form_token_response(self, reply) -> None:
        from ..ui import LoginWidget, ThemedMessageBox

        message_bar = self.iface.messageBar()
        if message_bar is not None:
            message_bar.clearWidgets()

        self._form_token_request_active = False
        form_token = None
        error_occurred = False

        try:
            if reply.error():
                ThemedMessageBox.show_message(
                    self.iface.mainWindow(),
                    QMessageBox.Critical,
                    "Network Error",
                    f"Failed to fetch form token: {reply.errorString()}",
                )
                error_occurred = True
            else:
                response_data = reply.readAll()
                if not response_data:
                    ThemedMessageBox.show_message(
                        self.iface.mainWindow(),
                        QMessageBox.Critical,
                        "Error",
                        "Empty response for form token.",
                    )
                    error_occurred = True
                else:
                    response = json.loads(response_data.data().decode("utf-8"))
                    if response.get("status", True) is False:
                        ThemedMessageBox.show_message(
                            self.iface.mainWindow(),
                            QMessageBox.Critical,
                            "API Error",
                            f"Failed to fetch form token: {response.get('msg', 'Unknown error')}",
                        )
                        error_occurred = True
                    else:
                        form_token = response.get("token")
                        if not form_token:
                            ThemedMessageBox.show_message(
                                self.iface.mainWindow(),
                                QMessageBox.Critical,
                                "API Error",
                                "No form token in response.",
                            )
                            error_occurred = True
        except json.JSONDecodeError:
            ThemedMessageBox.show_message(
                self.iface.mainWindow(),
                QMessageBox.Critical,
                "Error",
                "Invalid JSON response for form token.",
            )
            error_occurred = True
        except Exception as e:
            ThemedMessageBox.show_message(
                self.iface.mainWindow(),
                QMessageBox.Critical,
                "Error",
                f"An error occurred processing form token: {str(e)}",
            )
            error_occurred = True
        finally:
            reply.deleteLater()
            if self._form_token_manager:
                self._form_token_manager.deleteLater()
                self._form_token_manager = None

        if error_occurred or not form_token:
            return

        if self.login_dialog_instance:
            self.login_dialog_instance.raise_()
            self.login_dialog_instance.activateWindow()
            return

        self.login_dialog_instance = LoginWidget(
            form_token=form_token,
            iface=self.iface,
            parent=self.iface.mainWindow(),
        )
        self.login_dialog_instance.finished.connect(self.handle_login_dialog_closed)
        self.login_dialog_instance.show()

    def handle_login_dialog_closed(self, result: int) -> None:
        if result == QDialog.Accepted:
            QgsMessageLog.logMessage("LoginDialog successful.", "IDPMPlugin", Qgis.Info)
            QTimer.singleShot(0, self.show_menu_dialog_singleton)
        else:
            QgsMessageLog.logMessage(
                "LoginDialog failed or cancelled.", "IDPMPlugin", Qgis.Info
            )

        if self.login_dialog_instance:
            self.login_dialog_instance.deleteLater()
            self.login_dialog_instance = None
