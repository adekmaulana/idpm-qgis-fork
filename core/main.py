import json
from PyQt5.QtCore import QUrl, QSettings, QTimer  # Import QTimer
from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager
from PyQt5.QtWidgets import QAction, QMessageBox, QDialog
from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgisInterface

from ..config import Config  # Import the Config class for API URL
from ..ui import LoginWidget  # Import the LoginWidget from ui module


class IDPMPlugin:
    """
    Integrated Data Platform Management (IDPM) Plugin for QGIS.
    This plugin provides a simple interface to manage user authentication
    and access to the IDPM system, allowing users to log in and access
    their data seamlessly.
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
        self._menu_dialog_instance = None  # For singleton MenuDialog
        self._form_token_manager = None
        self._form_token_request_active = False
        self.login_dialog_instance = None

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
        # QgsMessageLog.logMessage("Plugin run method called.", "IDPMPlugin", Qgis.Info)
        # settings = QSettings()
        # token = settings.value("IDPMPlugin/token", defaultValue=None, type=str)

        # if token:
        #     self.show_menu_dialog_singleton()  # Use the singleton method
        # else:
        if self._form_token_request_active:  # Check flag
            QgsMessageLog.logMessage(
                "Form token request already in progress.",
                "IDPMPlugin",
                Qgis.Warning,
            )
            return
        self.perform_login()  # Renamed for clarity, will fetch token and then show LoginDialog

    def show_menu_dialog_singleton(self) -> None:
        """
        Creates and shows the MenuDialog if it doesn't exist (singleton),
        or brings the existing one to the front.
        """
        # if self._menu_dialog_instance is None:
        #     QgsMessageLog.logMessage(
        #         "Creating new MenuDialog (singleton).", "IDPMPlugin", Qgis.Info
        #     )
        #     self._menu_dialog_instance = MenuDialog(
        #         iface=self.iface, parent=self.iface.mainWindow()
        #     )
        #     self._menu_dialog_instance.finished.connect(self._handle_menu_dialog_closed)
        #     self._menu_dialog_instance.show()
        # else:
        #     QgsMessageLog.logMessage(
        #         "Raising existing MenuDialog (singleton).", "IDPMPlugin", Qgis.Info
        #     )
        #     self._menu_dialog_instance.raise_()
        #     self._menu_dialog_instance.activateWindow()

    def _handle_menu_dialog_closed(self, result_code: int) -> None:
        """Slot called when MenuDialog is closed, clears the instance reference."""
        QgsMessageLog.logMessage(
            f"MenuDialog closed (result: {result_code}). Clearing singleton instance.",
            "IDPMPlugin",
            Qgis.Info,
        )
        self._menu_dialog_instance = None

    def perform_login(self) -> None:  # Fetches form token
        self._form_token_request_active = True  # Set flag
        QgsMessageLog.logMessage(
            "perform_login: Fetching form token.", "IDPMPlugin", Qgis.Info
        )

        message_bar = self.iface.messageBar()
        if message_bar is not None:
            message_bar.pushMessage(
                "IDPMPlugin", "Preparing login...", level=Qgis.Info, duration=0
            )

        self._form_token_manager = QNetworkAccessManager()
        self._form_token_manager.finished.connect(
            self.handle_form_token_response
        )  # Changed handler name
        self._form_token_manager.get(
            QNetworkRequest(QUrl(f"{Config.API_URL}/auth/formtoken"))
        )

    def handle_form_token_response(self, reply) -> None:  # Changed name from _reverted
        message_bar = self.iface.messageBar()
        if message_bar is not None:
            message_bar.clearWidgets()

        self._form_token_request_active = False  # Reset flag
        form_token = None
        error_occurred = False

        try:
            # ... (Keep your full error handling for the reply as in your working version)
            if reply.error():
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Network Error",
                    f"Failed to fetch form token: {reply.errorString()}",
                )
                error_occurred = True
            else:
                response_data = reply.readAll()
                if not response_data:
                    QMessageBox.critical(
                        self.iface.mainWindow(),
                        "Error",
                        "Empty response for form token.",
                    )
                    error_occurred = True
                else:
                    response = json.loads(response_data.data().decode("utf-8"))
                    if response.get("status", True) is False:
                        QMessageBox.critical(
                            self.iface.mainWindow(),
                            "API Error",
                            f"Failed to fetch form token: {response.get('msg', 'Unknown error')}",
                        )
                        error_occurred = True
                    else:
                        form_token = response.get("token")
                        if not form_token:
                            QMessageBox.critical(
                                self.iface.mainWindow(),
                                "API Error",
                                "No form token in response.",
                            )
                            error_occurred = True
        except json.JSONDecodeError:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                "Invalid JSON response for form token.",
            )
            error_occurred = True
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
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

        # If a dialog is already open, bring it to the front
        if self.login_dialog_instance:
            self.login_dialog_instance.raise_()
            self.login_dialog_instance.activateWindow()
            return

        # Create and store the instance on self to prevent garbage collection
        self.login_dialog_instance = LoginWidget(
            form_token=form_token,
            iface=self.iface,
            parent=None,
        )
        # Connect to the finished signal to handle the result later
        self.login_dialog_instance.finished.connect(self.handle_login_dialog_closed)

        # Show the dialog modelessly instead of executing it
        self.login_dialog_instance.show()

    def handle_login_dialog_closed(self, result: int) -> None:
        """
        This new method is called when the LoginWidget is closed.
        The 'result' is QDialog.Accepted (1) or QDialog.Rejected (0).
        """
        if result == QDialog.Accepted:
            QgsMessageLog.logMessage("LoginDialog successful.", "IDPMPlugin", Qgis.Info)
            # The token is already saved by the widget. Now show the main menu.
            QTimer.singleShot(0, self.show_menu_dialog_singleton)
        else:
            QgsMessageLog.logMessage(
                "LoginDialog failed or cancelled.", "IDPMPlugin", Qgis.Info
            )

        # Schedule the dialog for deletion and clear the reference
        if self.login_dialog_instance:
            self.login_dialog_instance.deleteLater()
            self.login_dialog_instance = None
