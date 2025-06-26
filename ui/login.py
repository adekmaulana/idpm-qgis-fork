from typing import Optional
import os
import json
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
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
from PyQt5.QtGui import QFont, QPixmap, QMouseEvent
from PyQt5.QtCore import Qt, QSize, QUrl, QSettings, QByteArray, QPoint
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qgis.gui import QgisInterface

from ..config import Config


class LoginWidget(QDialog):
    """
    A responsive, custom login dialog that integrates with the QGIS plugin's
    authentication flow. It scales its UI elements based on screen resolution.
    """

    form_token: str
    iface: QgisInterface
    parent: Optional[QWidget]

    def __init__(
        self, form_token: str, iface: QgisInterface, parent: Optional[QWidget] = None
    ):
        """
        Initializes the LoginWidget.

        Args:
            form_token (str): The token received from the initial API call.
            iface (QgisInterface): The QGIS interface instance for message bars, etc.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.form_token = form_token
        self.iface = iface
        self.network_manager = QNetworkAccessManager(self)

        # --- For frameless window interaction ---
        self.old_pos = None
        self.resizing = False
        self.resize_grip_size = 10  # The thickness of the resize handles on the edges

        # --- Define asset paths using the Config class ---
        self.background_img_path = os.path.join(
            Config.ASSETS_PATH, "images", "forest_bg.png"
        )
        self.logo1_path = os.path.join(Config.ASSETS_PATH, "images", "klhk_logo.png")
        self.logo2_path = os.path.join(Config.ASSETS_PATH, "images", "idpm_logo.png")
        self.logo3_path = os.path.join(Config.ASSETS_PATH, "images", "m4cr_logo.png")
        self.logo4_path = os.path.join(
            Config.ASSETS_PATH, "images", "world_bank_logo.png"
        )

        # Initialize the user interface
        self.initUI()

    def initUI(self) -> None:
        """Sets up the main UI components and layout."""
        self.setWindowTitle("Login IDPM")

        # --- Make the dialog frameless and an independent window ---
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Enable mouse tracking to change cursor on hover without a click
        self.setMouseTracking(True)

        # --- Set a dynamic size based on a percentage of the screen ---
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        initial_width = int(screen_geometry.width() * 0.8)
        initial_height = int(screen_geometry.height() * 0.8)
        self.resize(initial_width, initial_height)
        self.setMinimumSize(960, 600)

        self.main_container = QWidget()
        self.main_container.setObjectName("mainContainer")
        self.main_container.setMouseTracking(True)

        main_layout = QHBoxLayout(self.main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        left_panel = self._create_left_panel()
        left_panel.setMouseTracking(True)
        right_panel = self._create_right_panel()
        right_panel.setMouseTracking(True)

        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 3)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(self.main_container)

        self.apply_stylesheet()

    def _attempt_login(self) -> None:
        """
        Slot for the Login button. Gathers credentials and sends the
        authentication request.
        """
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            QMessageBox.warning(self, "Input Error", "Email and password are required.")
            return

        payload = json.dumps(
            {
                "username": email,
                "password": password,
                "form_token": self.form_token,
            }
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
            QMessageBox.critical(
                self, "Network Error", f"Login request failed: {reply.errorString()}"
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
                QMessageBox.warning(self, "Login Failed", error_msg)
            else:
                api_token = response_json.get("token")
                if api_token:
                    settings = QSettings()
                    settings.setValue("IDPMPlugin/token", api_token)
                    QMessageBox.information(self, "Success", "Login successful!")
                    self.accept()
                else:
                    QMessageBox.critical(
                        self, "API Error", "Login succeeded but no token was provided."
                    )
        except (json.JSONDecodeError, Exception) as e:
            QMessageBox.critical(
                self, "Error", f"An error occurred processing the response: {e}"
            )

    def _create_left_panel(self) -> QWidget:
        """Creates the scaled left-side panel."""
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
                    QSize(146, 104),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
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
        """Creates the scaled right-side panel with window controls."""
        panel = QWidget()
        panel.setObjectName("rightPanel")

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 10, 20, 20)

        # --- Window controls (minimize, close) ---
        controls_layout = QHBoxLayout()
        controls_layout.addStretch()

        self.minimize_button = QPushButton("—")  # Em-dash for minimize icon
        self.minimize_button.setObjectName("minimizeButton")
        self.minimize_button.setCursor(Qt.PointingHandCursor)
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.clicked.connect(self.showMinimized)
        controls_layout.addWidget(self.minimize_button)

        self.close_button = QPushButton("×")  # Multiplication sign for close icon
        self.close_button.setObjectName("closeButton")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(self.reject)
        controls_layout.addWidget(self.close_button)

        # --- Centered form ---
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

        # Add layouts to the main panel layout
        panel_layout.addLayout(controls_layout)
        panel_layout.addStretch(1)
        panel_layout.addLayout(form_container_layout)
        panel_layout.addStretch(2)

        return panel

    def apply_stylesheet(self) -> None:
        """Applies the scaled QSS to style the dialog."""
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
            
            #minimizeButton, #closeButton {{
                background-color: transparent; color: white; border: none;
                font-family: "Montserrat", sans-serif;
                font-weight: bold; padding: 2px 8px; margin: 0;
            }}
            #minimizeButton {{ font-size: 20px; }}
            #closeButton {{ font-size: 28px; }}

            #minimizeButton:hover, #closeButton:hover {{
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }}
            #minimizeButton:pressed, #closeButton:pressed {{ 
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

            /* --- Style for QMessageBox --- */
            QMessageBox {{
                background-color: #3D5A43;
            }}
            QMessageBox QLabel {{
                color: white;
                font-size: 14px;
            }}
            QMessageBox QPushButton {{
                background-color: white;
                color: #222222;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: #E8E8E8;
            }}
        """
        self.setStyleSheet(qss)

    # --- Methods for dragging and resizing the frameless window ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.resizing = self._is_on_edge(event.pos())
            if self.resizing:
                self.old_pos = event.globalPos()
            else:
                child = self.childAt(event.pos())
                if not isinstance(child, (QLineEdit, QPushButton)):
                    self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.old_pos = None
            self.resizing = False
            self.unsetCursor()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.resizing and not self.old_pos:
            self._update_cursor(event.pos())

        if self.resizing:
            delta = QPoint(event.globalPos() - self.old_pos)
            self._resize_window(delta)
            self.old_pos = event.globalPos()
        elif self.old_pos:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def _is_on_edge(self, pos: QPoint) -> bool:
        """Check if the mouse is on the edge of the window."""
        grip = self.resize_grip_size
        return (
            pos.x() < grip
            or pos.x() > self.width() - grip
            or pos.y() < grip
            or pos.y() > self.height() - grip
        )

    def _update_cursor(self, pos: QPoint) -> None:
        """Update cursor shape when hovering over window edges."""
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
