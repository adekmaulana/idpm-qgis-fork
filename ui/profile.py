from typing import Optional
import sys
import os
import json
from datetime import datetime

from qgis.gui import QgisInterface
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QGridLayout,
    QMessageBox,
)
from PyQt5.QtGui import QFont, QPixmap, QIcon, QPainter
from PyQt5.QtCore import Qt, QSize, QUrl, QSettings
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..config import Config
from .base_dialog import BaseDialog


class ProfileDialog(BaseDialog):
    """
    The user profile dialog. Inherits all frameless window
    functionality from BaseDialog.
    """

    iface: "QgisInterface"
    parent: Optional["QWidget"]

    def __init__(self, iface: "QgisInterface", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.iface = iface
        self.user_profile = {}
        self.pic_network_manager = QNetworkAccessManager(self)
        self.pic_network_manager.finished.connect(self._on_profile_picture_loaded)

        self.init_profile_ui()
        self._load_and_apply_profile()

    def init_profile_ui(self) -> None:
        """Sets up the profile-specific UI components."""
        self.setWindowTitle("User Profile")

        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 10, 30, 30)

        # --- Top bar with back button, profile, and window controls ---
        top_bar_layout = self._create_top_bar()
        main_layout.addLayout(top_bar_layout)
        main_layout.addSpacing(20)

        # --- Main Content Area ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(30)

        left_column = self._create_left_column()
        right_column = self._create_right_column()

        content_layout.addLayout(left_column, 1)  # Stretch factor 1
        content_layout.addLayout(right_column, 2)  # Stretch factor 2

        main_layout.addLayout(content_layout)
        self.apply_stylesheet()

    def _create_top_bar(self) -> QHBoxLayout:
        """Creates the top navigation bar."""
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 10)

        self.back_button = QPushButton("← Back to Menu")
        self.back_button.setObjectName("backButton")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.clicked.connect(self.accept)  # Closes the dialog

        top_bar_layout.addWidget(self.back_button)

        controls_layout = self._create_window_controls()
        top_bar_layout.addLayout(controls_layout)

        return top_bar_layout

    def _create_left_column(self) -> QVBoxLayout:
        """Creates the left column with profile picture and info."""
        left_layout = QVBoxLayout()
        left_layout.setAlignment(Qt.AlignTop)

        profile_title = QLabel("Profile")
        profile_title.setObjectName("pageTitle")

        profile_subtitle = QLabel(
            "Review your personal data, role, and contact information."
        )
        profile_subtitle.setObjectName("pageSubtitle")
        profile_subtitle.setWordWrap(True)

        # --- Profile Picture Card ---
        profile_card = QWidget()
        profile_card.setObjectName("infoCard")
        profile_card_layout = QVBoxLayout(profile_card)
        profile_card_layout.setAlignment(Qt.AlignCenter)
        profile_card_layout.setSpacing(10)

        self.profile_pic_label = QLabel()
        pic_size = 100
        self.profile_pic_label.setFixedSize(pic_size, pic_size)
        self.profile_pic_label.setAlignment(Qt.AlignCenter)

        self.profile_name_label = QLabel("Username")
        self.profile_name_label.setObjectName("profileCardName")

        self.profile_role_label = QLabel("Role")
        self.profile_role_label.setObjectName("profileCardRole")

        profile_card_layout.addWidget(self.profile_pic_label)
        profile_card_layout.addWidget(self.profile_name_label)
        profile_card_layout.addWidget(self.profile_role_label)

        # --- Profile Information Card ---
        info_card = QWidget()
        info_card.setObjectName("infoCard")
        info_layout = QGridLayout(info_card)
        info_layout.setContentsMargins(20, 20, 20, 20)
        info_layout.setSpacing(15)

        info_title = QLabel("Profile Information")
        info_title.setObjectName("cardHeader")

        self.full_name_label = QLabel("N/A")
        self.email_label = QLabel("N/A")
        self.phone_label = QLabel("N/A")

        info_layout.addWidget(info_title, 0, 0, 1, 2)
        info_layout.addWidget(QLabel("Full Name"), 1, 0)
        info_layout.addWidget(self.full_name_label, 1, 1)
        info_layout.addWidget(QLabel("Email"), 2, 0)
        info_layout.addWidget(self.email_label, 2, 1)
        info_layout.addWidget(QLabel("Phone Number"), 3, 0)
        info_layout.addWidget(self.phone_label, 3, 1)

        left_layout.addWidget(profile_title)
        left_layout.addWidget(profile_subtitle)
        left_layout.addSpacing(20)
        left_layout.addWidget(profile_card)
        left_layout.addSpacing(20)
        left_layout.addWidget(info_card)
        left_layout.addStretch()

        return left_layout

    def _create_right_column(self) -> QVBoxLayout:
        """Creates the right column with working area and activity."""
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignTop)

        # --- Working Area Card ---
        working_area_card = QWidget()
        working_area_card.setObjectName("infoCard")
        wa_main_layout = QVBoxLayout(working_area_card)
        wa_main_layout.setSpacing(10)
        wa_title = QLabel("Working Area")
        wa_title.setObjectName("cardHeader")
        self.wa_grid_layout = QGridLayout()  # Grid to hold the tags
        self.wa_grid_layout.setSpacing(10)
        wa_main_layout.addWidget(wa_title)
        wa_main_layout.addLayout(self.wa_grid_layout)
        wa_main_layout.addStretch()

        # --- Recent Activity Card ---
        activity_card = QWidget()
        activity_card.setObjectName("infoCard")
        ac_layout = QVBoxLayout(activity_card)
        ac_title = QLabel("Recent Activity")
        ac_title.setObjectName("cardHeader")
        self.activity_grid_layout = QGridLayout()  # Grid for table-like layout
        self.activity_grid_layout.setSpacing(10)
        ac_layout.addWidget(ac_title)
        ac_layout.addLayout(self.activity_grid_layout)
        ac_layout.addStretch()

        right_layout.addWidget(working_area_card)
        right_layout.addSpacing(20)
        right_layout.addWidget(activity_card)
        right_layout.addStretch()

        return right_layout

    def _load_and_apply_profile(self):
        """Loads user profile from QSettings and updates the UI."""
        settings = QSettings()
        profile_json_str = settings.value("IDPMPlugin/user_profile", None)
        if not profile_json_str:
            return

        try:
            self.user_profile = json.loads(profile_json_str)

            # Populate left column
            username = self.user_profile.get("username", "N/A")
            roles = self.user_profile.get("roles", "N/A")

            self.profile_name_label.setText(username)
            self.profile_role_label.setText(roles)
            self.full_name_label.setText(self.user_profile.get("fullname", username))
            self.email_label.setText(self.user_profile.get("email", "N/A"))
            self.phone_label.setText(self.user_profile.get("phone", "N/A"))

            # --- Populate Working Area ---
            wilker_str = self.user_profile.get("wilker", "")
            wilker_list = [w.strip() for w in wilker_str.split(",") if w.strip()]

            # Clear previous widgets
            for i in reversed(range(self.wa_grid_layout.count())):
                self.wa_grid_layout.itemAt(i).widget().setParent(None)

            # Add new tags to the grid
            row, col = 0, 0
            for wilker in wilker_list:
                tag = QLabel(wilker)
                tag.setObjectName("tagLabel")
                self.wa_grid_layout.addWidget(tag, row, col)
                col += 1
                if col > 3:  # Max 4 columns
                    col = 0
                    row += 1

            # --- Populate Recent Activity ---
            last_login_str = self.user_profile.get("last_login")

            # Clear previous widgets
            for i in reversed(range(self.activity_grid_layout.count())):
                self.activity_grid_layout.itemAt(i).widget().setParent(None)

            # Add headers
            headers = ["Date", "Detail", "Time"]
            for i, text in enumerate(headers):
                header_label = QLabel(text)
                header_label.setObjectName("activityHeader")
                self.activity_grid_layout.addWidget(header_label, 0, i)

            if last_login_str:
                try:
                    # Handle the 'Z' for UTC timezone info
                    if last_login_str.endswith("Z"):
                        last_login_str = last_login_str.replace("Z", "+00:00")

                    dt_obj = datetime.fromisoformat(last_login_str)

                    date_str = dt_obj.strftime("%Y/%m/%d")
                    time_str = dt_obj.strftime("%H:%M:%S")
                    detail_str = f"{username} logged in"

                    # Add the single activity row
                    self.activity_grid_layout.addWidget(QLabel(date_str), 1, 0)
                    self.activity_grid_layout.addWidget(QLabel(detail_str), 1, 1)
                    self.activity_grid_layout.addWidget(QLabel(time_str), 1, 2)

                except (ValueError, TypeError):
                    self.activity_grid_layout.addWidget(
                        QLabel(last_login_str), 1, 0, 1, 3
                    )

            # --- Profile Picture ---
            pic_url = self.user_profile.get("profilePicture")
            if pic_url:
                self.pic_network_manager.get(QNetworkRequest(QUrl(pic_url)))
            else:
                self.profile_pic_label.setText("No picture")

        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Failed to parse user profile.")

    def _on_profile_picture_loaded(self, reply: QNetworkReply):
        """Handles the response from the profile picture download."""
        if reply.error() == QNetworkReply.NoError:
            image_data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                self.profile_pic_label.setPixmap(
                    pixmap.scaled(
                        self.profile_pic_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
            else:
                self.profile_pic_label.setText("Load failed")
        else:
            self.profile_pic_label.setText("Net error")
        reply.deleteLater()

    def apply_stylesheet(self) -> None:
        """Applies the QSS to style the dialog."""
        qss = f"""
            #mainContainer {{ background-color: #5E765F; border-radius: 20px; }}
            QLabel {{ color: white; font-family: "Montserrat"; }}
            #pageTitle {{ font-size: 28px; font-weight: bold; }}
            #pageSubtitle {{ font-size: 14px; color: #D0D0D0; }}
            
            #profileCard, #infoCard {{
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 20px;
            }}
            #profileCardName {{ font-size: 18px; font-weight: bold; }}
            #profileCardRole {{ font-size: 14px; color: #D0D0D0; }}
            #cardHeader {{ font-size: 16px; font-weight: bold; margin-bottom: 10px; }}

            #backButton {{
                background-color: transparent; color: white; border: none;
                font-size: 14px; padding: 8px;
            }}
            #backButton:hover {{ text-decoration: underline; }}
            
            #profileButton {{
                background-color: transparent; color: white; border: 1px solid rgba(255, 255, 255, 0.4);
                padding: 6px 15px; border-radius: 18px; font-size: 12px;
            }}

            #minimizeButton, #maximizeButton, #closeButton {{
                background-color: transparent; color: white; border: none;
                font-family: "Arial", sans-serif; font-weight: bold; border-radius: 4px;
            }}
            #minimizeButton {{ font-size: 16px; padding-bottom: 5px; }}
            #maximizeButton {{ font-size: 16px; padding-top: 1px; }}
            #closeButton {{ font-size: 24px; padding-bottom: 2px; }}
            
            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover {{ background-color: rgba(255, 255, 255, 0.2); }}
            #minimizeButton:pressed, #maximizeButton:pressed, #closeButton:pressed {{ background-color: rgba(255, 255, 255, 0.1); }}
        
            #tagLabel {{
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
                padding: 5px 10px;
                border-radius: 12px;
                font-size: 11px;
            }}
            #activityHeader {{
                font-weight: bold;
                color: #D0D0D0;
            }}
        """
        self.setStyleSheet(qss)
