from typing import Optional
import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QSize, QUrl, QSettings, QByteArray
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qgis.gui import QgisInterface
from qgis.core import Qgis, QgsMessageLog

from ..config import Config
from .base_dialog import BaseDialog
from .themed_message_box import ThemedMessageBox


class LoginWidget(BaseDialog):
    """
    The login dialog for the plugin. Inherits all frameless window
    functionality from BaseDialog.
    """

    form_token: str
    iface: QgisInterface
    parent: Optional[QWidget]

    def __init__(
        self, form_token: str, iface: QgisInterface, parent: Optional[QWidget] = None
    ):
        """
        Initializes the LoginWidget.
        """
        # Initialize the BaseDialog first
        super().__init__(parent)

        self.form_token = form_token
        self.iface = iface
        self.network_manager = QNetworkAccessManager(self)

        # --- Define asset paths ---
        self.background_img_path = os.path.join(
            Config.ASSETS_PATH, "images", "forest_bg.png"
        )
        self.logo1_path = os.path.join(Config.ASSETS_PATH, "images", "klhk_logo.png")
        self.logo2_path = os.path.join(Config.ASSETS_PATH, "images", "idpm_logo.png")
        self.logo3_path = os.path.join(Config.ASSETS_PATH, "images", "m4cr_logo.png")
        self.logo4_path = os.path.join(
            Config.ASSETS_PATH, "images", "world_bank_logo.png"
        )

        # Build the specific UI for this dialog
        self.init_login_ui()

    def init_login_ui(self) -> None:
        """Sets up the login-specific UI components."""
        self.setWindowTitle("Login IDPM")

        # The main_container is created by the BaseDialog. We just need to add to it.
        main_layout = QHBoxLayout(self.main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 3)

        self.apply_stylesheet()

    def _attempt_login(self) -> None:
        """
        Slot for the Login button. Gathers credentials and sends the
        authentication request.
        """
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Input Error",
                "Email and password are required.",
            )
            return

        payload = json.dumps(
            {"username": email, "password": password, "form_token": self.form_token}
        )
        request = QNetworkRequest(QUrl(f"{Config.API_URL}/auth/login"))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        self.login_button.setEnabled(False)
        self.login_button.setText("Logging in...")

        self.network_manager.finished.connect(self._handle_login_response)
        self.network_manager.post(request, QByteArray(payload.encode("utf-8")))

    def _handle_login_response(self, reply: QNetworkReply) -> None:
        """
        Handles the response from the login API endpoint.
        """
        self.login_button.setEnabled(True)
        self.login_button.setText("Login")

        try:
            self.network_manager.finished.disconnect(self._handle_login_response)
        except TypeError:
            pass

        if reply.error():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Network Error",
                f"Login request failed: {reply.errorString()}",
            )
            reply.deleteLater()
            return

        response_data = reply.readAll()
        reply.deleteLater()

        try:
            response_json = json.loads(response_data.data().decode("utf-8"))
            if not response_json.get("status"):
                error_msg = response_json.get(
                    "msg", "Invalid credentials or unknown error."
                )
                ThemedMessageBox.show_message(
                    self, QMessageBox.Warning, "Login Failed", error_msg
                )
            else:
                api_token = response_json.get("token")
                user_profile = response_json.get("profile")

                if api_token:
                    settings = QSettings()
                    settings.setValue("IDPMPlugin/token", api_token)

                    if user_profile and isinstance(user_profile, dict):
                        settings.setValue(
                            "IDPMPlugin/user_profile", json.dumps(user_profile)
                        )
                        QgsMessageLog.logMessage(
                            "User profile saved.", "IDPMPlugin", Qgis.Info
                        )
                    else:
                        settings.remove("IDPMPlugin/user_profile")
                        QgsMessageLog.logMessage(
                            "No user profile in response.", "IDPMPlugin", Qgis.Warning
                        )

                    ThemedMessageBox.show_message(
                        self, QMessageBox.Information, "Success", "Login successful!"
                    )
                    self.accept()
                else:
                    ThemedMessageBox.show_message(
                        self,
                        QMessageBox.Critical,
                        "API Error",
                        "Login succeeded but no token was provided.",
                    )
        except (json.JSONDecodeError, Exception) as e:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Error",
                f"An error occurred processing the response: {e}",
            )

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("leftPanel")
        overlay = QWidget(panel)
        overlay.setObjectName("leftPanelOverlay")
        margin = 40
        content_layout = QVBoxLayout(overlay)
        content_layout.setContentsMargins(margin, margin, margin, margin)
        content_layout.setSpacing(20)
        welcome_label = QLabel("Welcome Back")
        welcome_label.setObjectName("welcomeLabel")
        welcome_label.setFont(QFont("Montserrat", 12, QFont.Thin))
        title_label = QLabel(
            "Inovasi Geospasial Untuk Mendukung Pengelolaan Hutan Lingkungan"
        )
        title_label.setObjectName("titleLabel")
        title_label.setFont(QFont("Montserrat", 24, QFont.Bold))
        title_label.setWordWrap(True)
        logos_widget = QWidget()
        logos_layout = QHBoxLayout(logos_widget)
        logos_layout.setContentsMargins(0, 20, 0, 0)
        logos_layout.setSpacing(12)
        logos_layout.setAlignment(Qt.AlignLeft)
        logo_paths = [self.logo1_path, self.logo2_path]
        logo_size = 60
        for i, path in enumerate(logo_paths):
            label = QLabel()
            if os.path.exists(path):
                pixmap = QPixmap(path)
                label.setPixmap(
                    pixmap.scaled(
                        QSize(logo_size, logo_size),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
            else:
                label.setText(f"Logo {i+1}")
                label.setFixedSize(logo_size, logo_size)
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet(
                    f"background-color: #DDD; border: 1px solid #AAA; border-radius: 5px;"
                )
            logos_layout.addWidget(label)
        label = QLabel()
        if os.path.exists(self.logo3_path):
            pixmap = QPixmap(self.logo3_path)
            label.setPixmap(
                pixmap.scaled(
                    QSize(146, 104), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        else:
            label.setText(f"Logo 3")
            label.setFixedSize(logo_size, logo_size)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"background-color: #DDD; border: 1px solid #AAA; border-radius: 5px;"
            )
        logos_layout.addWidget(label)
        logos_layout.addStretch()
        logo4_label = QLabel()
        logo4_label.setAlignment(Qt.AlignLeft)
        if os.path.exists(self.logo4_path):
            pixmap = QPixmap(self.logo4_path)
            scaled_pixmap = pixmap.scaledToHeight(40, Qt.SmoothTransformation)
            logo4_label.setPixmap(scaled_pixmap)
        else:
            logo4_label.setText("Logo 4")
            logo4_label.setFixedSize(logo_size, logo_size)
            logo4_label.setStyleSheet(
                f"background-color: #DDD; border: 1px solid #AAA; border-radius: 5px;"
            )
        v_spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        content_layout.addWidget(welcome_label)
        content_layout.addWidget(title_label)
        content_layout.addWidget(logos_widget)
        content_layout.addWidget(logo4_label)
        content_layout.addSpacerItem(v_spacer)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(margin, margin, margin, margin)
        panel_layout.addStretch(1)
        panel_layout.addWidget(overlay)
        panel_layout.addStretch(1)
        return panel

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("rightPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 10, 20, 20)
        controls_layout = self._create_window_controls()
        form_container_layout = QVBoxLayout()
        form_container_layout.setAlignment(Qt.AlignCenter)
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(20)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_widget.setMaximumWidth(450)
        header_label = QLabel("Enter your username and password.")
        header_label.setObjectName("headerLabel")
        header_label.setFont(QFont("Montserrat", 14, QFont.Bold))
        sub_header_label = QLabel("Please log in to continue spatial data processing.")
        sub_header_label.setObjectName("subHeaderLabel")
        sub_header_label.setFont(QFont("Montserrat", 12))
        sub_header_label.setWordWrap(True)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("E-mail Address")
        self.email_input.setFont(QFont("Montserrat", 11))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setFont(QFont("Montserrat", 11))
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._attempt_login)
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 15, 0, 0)
        buttons_layout.setSpacing(15)
        self.login_button = QPushButton("Login")
        self.login_button.setObjectName("loginButton")
        self.login_button.setFont(QFont("Montserrat", 11, QFont.Bold))
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self._attempt_login)
        buttons_layout.addWidget(self.login_button)
        buttons_layout.addStretch()
        form_layout.addWidget(header_label)
        form_layout.addWidget(sub_header_label)
        form_layout.addSpacerItem(
            QSpacerItem(1, 20, QSizePolicy.Minimum, QSizePolicy.Fixed)
        )
        form_layout.addWidget(self.email_input)
        form_layout.addWidget(self.password_input)
        form_layout.addWidget(buttons_widget)
        form_container_layout.addWidget(form_widget)
        panel_layout.addLayout(controls_layout)
        panel_layout.addStretch(1)
        panel_layout.addLayout(form_container_layout)
        panel_layout.addStretch(2)
        return panel

    def apply_stylesheet(self) -> None:
        bg_path = (
            self.background_img_path.replace("\\", "/")
            if os.path.exists(self.background_img_path)
            else ""
        )
        qss = f"""
            QDialog {{ background-color: transparent; }}
            #mainContainer {{
                background-color: #5E765F;
                border-radius: 20px;
            }}
            #leftPanel {{
                border-image: url('{bg_path}') 0 0 0 0 stretch stretch;
                background-color: #2E4434;
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
            }}
            #leftPanelOverlay {{
                background-color: rgba(255, 255, 255, 0.55);
                border-radius: 20px;
            }}
            #welcomeLabel, #titleLabel, #copyrightLabel {{ color: white; }}
            #titleLabel {{ font-weight: bold; }}
            #copyrightLabel {{ color: #E0E0E0; }}
            #rightPanel {{ background-color: transparent; }}
            #headerLabel, #subHeaderLabel {{ color: white; }}
            #subHeaderLabel {{ color: #D0D0D0; }}
            
            #minimizeButton, #maximizeButton, #closeButton {{
                background-color: transparent; color: white; border: none;
                font-family: "Arial", sans-serif;
                font-weight: bold;
                border-radius: 4px;
            }}
            #minimizeButton {{ font-size: 16px; padding-bottom: 5px; }}
            #maximizeButton {{ font-size: 16px; padding-top: 1px; }}
            #closeButton {{ font-size: 24px; padding-bottom: 2px; }}

            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover {{
                background-color: rgba(255, 255, 255, 0.2);
            }}
            #minimizeButton:pressed, #maximizeButton:pressed, #closeButton:pressed {{ 
                background-color: rgba(255, 255, 255, 0.1); 
            }}
            
            QLineEdit {{
                background-color: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 12px 15px;
                color: white;
            }}
            QLineEdit:focus {{ border: 1px solid rgba(255, 255, 255, 0.5); }}
            QLineEdit::placeholder {{ color: #B0B0B0; }}
            #loginButton {{
                background-color: white; color: #222222; border: none;
                border-radius: 8px;
                padding: 12px 30px;
            }}
            #loginButton:hover {{ background-color: #E8E8E8; }}
            #loginButton:disabled {{ background-color: #B0B0B0; }}
        """
        self.setStyleSheet(qss)
