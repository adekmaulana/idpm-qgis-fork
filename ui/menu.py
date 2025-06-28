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
    QPushButton,
    QMessageBox,
    QInputDialog,
    QDialog,
    QMenu,
    QAction,
    QStyleOption,
    QStyle,
)
from PyQt5.QtGui import QFont, QPixmap, QIcon, QPainter, QMouseEvent
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QSize, QUrl, QSettings, QByteArray, QTimer
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qgis.gui import QgisInterface
from qgis.core import Qgis, QgsMessageLog

from ..config import Config
from .base_dialog import BaseDialog
from .profile import ProfileDialog
from .list_raster import ImageListDialog
from .loading import LoadingDialog
from .custom_input_dialog import CustomInputDialog


class ActionCard(QWidget):
    """A custom card-like button with an icon, title, and subtitle."""

    def __init__(
        self,
        icon_path: str,
        title: str,
        subtitle: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("actionCard")
        self.setAutoFillBackground(True)
        self.setFixedSize(220, 120)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignTop)

        icon_label = QLabel()
        icon_size = QSize(24, 24)
        icon_label.setFixedSize(icon_size)

        if os.path.exists(icon_path):
            if icon_path.lower().endswith(".svg"):
                renderer = QSvgRenderer(icon_path)
                pixmap = QPixmap(icon_size)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                icon_label.setPixmap(pixmap)
            else:
                pixmap = QPixmap(icon_path)
                icon_label.setPixmap(
                    pixmap.scaled(
                        icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setFont(QFont("Montserrat", 12, QFont.Bold))

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("cardSubtitle")
        subtitle_label.setFont(QFont("Montserrat", 10))

        main_layout.addWidget(icon_label)
        main_layout.addSpacing(10)
        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)
        main_layout.addStretch()

    def paintEvent(self, event):
        """
        Ensures the widget background is painted correctly according to the stylesheet.
        """
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)


class MenuWidget(BaseDialog):
    """
    The main menu dialog for the plugin, styled to match the new theme.
    """

    iface: QgisInterface
    parent: Optional[QWidget]

    def __init__(self, iface: QgisInterface, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.iface = iface
        self.network_manager = QNetworkAccessManager(self)

        self.image_list_dialog = None
        self.profile_dialog = None
        self.loading_dialog = None
        self.user_profile = {}

        self.main_bg_path = os.path.join(Config.ASSETS_PATH, "images", "menu_bg.jpg")

        self.init_menu_ui()
        self._load_and_apply_profile()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # <<< FIX: Only process mouse events if no other modal dialog is active >>>
        active_modal = QApplication.activeModalWidget()
        if active_modal and active_modal != self:
            return

        # If no other modal is active, proceed with the default behavior
        super().mousePressEvent(event)

    def init_menu_ui(self) -> None:
        """Sets up the menu-specific UI components."""
        self.setWindowTitle("IDPM Menu")

        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 10, 30, 30)

        top_bar_layout = QHBoxLayout()

        self.profile_button = QPushButton("User")
        self.profile_button.setObjectName("profileButton")

        profile_icon_path = os.path.join(
            Config.ASSETS_PATH, "images", "default_profile.png"
        )
        if os.path.exists(profile_icon_path):
            self.profile_button.setIcon(QIcon(profile_icon_path))

        self.profile_button.setIconSize(QSize(32, 32))
        self.profile_button.setCursor(Qt.PointingHandCursor)

        profile_menu = QMenu(self)
        view_profile_action = profile_menu.addAction("View Profile")
        logout_action = profile_menu.addAction("Logout")
        self.profile_button.setMenu(profile_menu)

        view_profile_action.triggered.connect(self.open_profile_dialog)
        logout_action.triggered.connect(self.handle_logout)

        top_bar_layout.addWidget(self.profile_button)
        top_bar_layout.addStretch()

        controls_layout = self._create_window_controls()
        top_bar_layout.addLayout(controls_layout)

        main_layout.addLayout(top_bar_layout)
        main_layout.addStretch(1)

        content_layout = QVBoxLayout()
        content_layout.setAlignment(Qt.AlignCenter)

        logo_label = QLabel()
        logo_path = os.path.join(Config.ASSETS_PATH, "images", "klhk_logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(
                pixmap.scaled(
                    QSize(88, 88), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        logo_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("Hi User")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setFont(QFont("Montserrat", 22, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)

        subtitle_label = QLabel("Kelola dan Jelajahi Data Geospasial Anda")
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setFont(QFont("Montserrat", 28, QFont.Bold))
        subtitle_label.setAlignment(Qt.AlignCenter)

        description_label = QLabel(
            "Jelajahi fitur untuk kelola dan analisis data spasial"
        )
        description_label.setObjectName("descriptionLabel")
        description_label.setFont(QFont("Montserrat", 12))
        description_label.setAlignment(Qt.AlignCenter)

        content_layout.addWidget(logo_label)
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(subtitle_label)
        content_layout.addWidget(description_label)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(20)
        button_layout.setContentsMargins(0, 30, 0, 0)

        icon_path_raster = os.path.join(Config.ASSETS_PATH, "images", "image.svg")
        icon_path_potensi = os.path.join(Config.ASSETS_PATH, "images", "maps.svg")
        icon_path_existing = os.path.join(Config.ASSETS_PATH, "images", "world.svg")

        self.card_list_raster = ActionCard(
            icon_path_raster, "List Raster", "View Detail"
        )
        self.card_open_potensi = ActionCard(
            icon_path_potensi, "Open Data Potensi", "View Detail"
        )
        self.card_open_existing = ActionCard(
            icon_path_existing, "Open Data Existing", "View Detail"
        )

        self.card_list_raster.mouseReleaseEvent = self.open_image_list

        button_layout.addWidget(self.card_list_raster)
        button_layout.addWidget(self.card_open_potensi)
        button_layout.addWidget(self.card_open_existing)

        content_layout.addWidget(button_container)

        main_layout.addLayout(content_layout)
        main_layout.addStretch(2)

        self.apply_stylesheet()

    def _load_and_apply_profile(self):
        settings = QSettings()
        profile_json_str = settings.value("IDPMPlugin/user_profile", None)
        if not profile_json_str:
            QgsMessageLog.logMessage(
                "Could not find user profile in settings.", "IDPMPlugin", Qgis.Warning
            )
            return

        try:
            self.user_profile = json.loads(profile_json_str)
            username = self.user_profile.get("username", "User")
            roles = self.user_profile.get("roles", "User")

            self.title_label.setText(f"Hi {username}")
            self.profile_button.setText(roles)

        except json.JSONDecodeError:
            QgsMessageLog.logMessage(
                "Failed to parse user profile from settings.",
                "IDPMPlugin",
                Qgis.Critical,
            )

    def open_profile_dialog(self):
        if self.profile_dialog is None:
            self.profile_dialog = ProfileDialog(self.iface, self)

        self.hide()
        self.profile_dialog.exec_()
        self.show()

    def handle_logout(self):
        confirm = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to log out?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            settings = QSettings()
            settings.remove("IDPMPlugin/token")
            settings.remove("IDPMPlugin/user_profile")
            QgsMessageLog.logMessage("User logged out.", "IDPMPlugin", Qgis.Info)
            self.accept()

    def open_image_list(self, event=None):
        if not self.user_profile:
            QMessageBox.critical(self, "Error", "User profile not loaded.")
            return

        selected_wilker = None
        try:
            wilker_str = self.user_profile.get("wilker", "")
            wilker_list = sorted(
                [w.strip() for w in wilker_str.split(",") if w.strip()]
            )

            if not wilker_list:
                QMessageBox.warning(
                    self, "No Working Area", "No valid working area found."
                )
                return

            if len(wilker_list) == 1:
                selected_wilker = wilker_list[0]
            else:
                dialog = CustomInputDialog(
                    self,
                    "Select Working Area",
                    "Please select your working area:",
                    wilker_list,
                )
                if dialog.exec_() == QDialog.Accepted:
                    selected_wilker = dialog.selectedItem()
                else:
                    return

        except Exception as e:
            QMessageBox.critical(
                self, "Profile Error", f"Could not read user profile: {e}"
            )
            return

        if not selected_wilker:
            return

        settings = QSettings()
        token = settings.value("IDPMPlugin/token", None)
        if not token:
            QMessageBox.critical(self, "Authentication Error", "You are not logged in.")
            return

        if not self.loading_dialog:
            self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.start_animation()
        self.loading_dialog.show()

        request = QNetworkRequest(
            QUrl(f"{Config.API_URL}/geoportal/sentinel/catalog/{selected_wilker}")
        )
        request.setRawHeader(b"Authorization", f"Bearer {token}".encode())

        self.network_manager.finished.connect(self.handle_image_list_response)
        self.network_manager.get(request)

    def handle_image_list_response(self, reply: QNetworkReply):
        if self.loading_dialog:
            self.loading_dialog.stop_animation()
            self.loading_dialog.hide()

        try:
            self.network_manager.finished.disconnect(self.handle_image_list_response)
        except TypeError:
            pass

        if reply.error():
            QMessageBox.critical(
                self, "Error", f"Failed to fetch image list: {reply.errorString()}"
            )
            reply.deleteLater()
            return

        response_data = reply.readAll()
        reply.deleteLater()

        try:
            response = json.loads(response_data.data().decode("utf-8"))
            features = response.get("data", {}).get("features", [])

            if self.image_list_dialog:
                self.image_list_dialog.close()

            self.image_list_dialog = ImageListDialog(features, self.iface, parent=self)
            self.hide()
            self.image_list_dialog.exec_()
            self.show()

        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Invalid JSON response for image list.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def apply_stylesheet(self) -> None:
        """Applies the QSS to style the dialog."""
        arrow_icon_path = os.path.join(
            Config.ASSETS_PATH, "images", "arrow-down.svg"
        ).replace("\\", "/")

        bg_path = (
            self.main_bg_path.replace("\\", "/")
            if os.path.exists(self.main_bg_path)
            else ""
        )

        qss = f"""
            QDialog {{ background-color: transparent; }}
            #mainContainer {{
                border-image: url('{bg_path}') 0 0 0 0 stretch stretch;
                background-color: #5E765F; /* Fallback color */
                border-radius: 20px;
            }}
            QLabel {{ color: white; }}
            #titleLabel {{ font-size: 28px; font-weight: bold; }}
            #subtitleLabel {{ font-size: 36px; font-weight: bold; }}
            #descriptionLabel {{ font-size: 14px; color: #D0D0D0; }}
            
            #minimizeButton, #maximizeButton, #closeButton {{
                background-color: transparent; color: white; border: none;
                font-family: "Arial", sans-serif;
                font-weight: bold;
                border-radius: 4px;
            }}
            #minimizeButton {{ font-size: 16px; padding-bottom: 5px; }}
            #maximizeButton {{ font-size: 16px; padding-top: 1px; }}
            #closeButton {{ font-size: 24px; padding-bottom: 2px; }}

            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover {{ background-color: rgba(255, 255, 255, 0.2); }}
            #minimizeButton:pressed, #maximizeButton:pressed, #closeButton:pressed {{ background-color: rgba(255, 255, 255, 0.1); }}
            
            #profileButton {{
                background-color: transparent; color: white; border: 1px solid rgba(255, 255, 255, 0.4);
                padding: 8px 45px 8px 15px; border-radius: 25px; font-size: 12px;
                font-family: "Montserrat"; text-align: left;
            }}
            #profileButton:hover {{ background-color: rgba(255, 255, 255, 0.1); }}
            #profileButton::menu-indicator {{
                image: url({arrow_icon_path});
                width: 20px;
                height: 20px;
                subcontrol-position: center right;
                subcontrol-origin: padding;
                right: 15px;
            }}

            QMenu {{
                background-color: #5E765F;
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: rgba(255, 255, 255, 0.15);
            }}
            QMenu::separator {{
                height: 1px;
                background: rgba(255, 255, 255, 0.2);
                margin: 5px 0px;
            }}

            #actionCard {{
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 12px;
            }}
            #actionCard:hover {{
                background-color: rgba(255, 255, 255, 0.25);
            }}
            #cardTitle {{ font-size: 14px; font-weight: bold; }}
            #cardSubtitle {{ color: #D0D0D0; font-size: 11px;}}
        """
        self.setStyleSheet(qss)
