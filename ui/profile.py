from typing import Optional
import json
from datetime import datetime

from qgis.gui import QgisInterface
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGridLayout,
    QMessageBox,
)
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath
from PyQt5.QtCore import Qt, QSize, QUrl, QSettings
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from .base_dialog import BaseDialog
from .themed_message_box import ThemedMessageBox


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
        """Sets up the profile-specific UI components in a 2x2 grid."""
        self.setWindowTitle("User Profile")

        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 10, 30, 30)

        # --- Top bar with back button and window controls ---
        top_bar_layout = self._create_top_bar()
        main_layout.addLayout(top_bar_layout)
        main_layout.addSpacing(20)

        # --- Main Content Area (2x2 Grid) ---
        # We will use two horizontal layouts stacked vertically.
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(30)

        bottom_row_layout = QHBoxLayout()
        bottom_row_layout.setSpacing(30)

        # Create and add the four main widgets to the rows
        profile_card_widget = self._create_profile_card_widget()
        working_area_widget = self._create_working_area_widget()
        profile_info_widget = self._create_profile_info_widget()
        recent_activity_widget = self._create_recent_activity_widget()

        top_row_layout.addWidget(profile_card_widget, 1)
        top_row_layout.addWidget(working_area_widget, 2)

        bottom_row_layout.addWidget(profile_info_widget, 1)
        bottom_row_layout.addWidget(recent_activity_widget, 2)

        # Add the rows to the main layout
        main_layout.addLayout(top_row_layout)
        main_layout.addSpacing(30)
        main_layout.addLayout(bottom_row_layout)
        main_layout.addStretch()

        self.apply_stylesheet()

    def _create_top_bar(self) -> QHBoxLayout:
        """Creates the top navigation bar."""
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 10)

        self.back_button = QPushButton("← Back to Menu")
        self.back_button.setObjectName("backButton")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.clicked.connect(self.accept)

        app_bar_title = QLabel("Profile")
        app_bar_title.setObjectName("appBarTitle")
        app_bar_title.setAlignment(
            Qt.AlignCenter
        )  # Center align the text within the label

        top_bar_layout.addWidget(self.back_button)
        top_bar_layout.addWidget(
            app_bar_title, 1
        )  # Add title with a stretch factor of 1

        controls_layout = self._create_window_controls()
        top_bar_layout.addLayout(controls_layout)

        return top_bar_layout

    def _create_profile_card_widget(self) -> QWidget:
        """Creates the top-left widget with profile picture, name, and role."""
        profile_card = QWidget()
        profile_card.setObjectName("profileCard")
        layout = QVBoxLayout(profile_card)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        self.profile_pic_label = QLabel()
        pic_size = 88
        self.profile_pic_label.setFixedSize(pic_size, pic_size)
        self.profile_pic_label.setAlignment(Qt.AlignCenter)
        self.profile_pic_label.setObjectName("profilePicture")

        self.profile_name_label = QLabel("Username")
        self.profile_name_label.setObjectName("profileCardName")
        self.profile_name_label.setAlignment(Qt.AlignCenter)

        self.profile_role_label = QLabel("Role")
        self.profile_role_label.setObjectName("profileCardRole")
        self.profile_role_label.setAlignment(Qt.AlignCenter)

        # Create a separate horizontal layout for the picture to center it independently
        pic_layout = QHBoxLayout()
        pic_layout.addStretch()
        pic_layout.addWidget(self.profile_pic_label)
        pic_layout.addStretch()

        # Create a separate horizontal layout for the role to constrain its width
        role_layout = QHBoxLayout()
        role_layout.addStretch()
        role_layout.addWidget(self.profile_role_label)
        role_layout.addStretch()

        layout.addStretch()
        layout.addLayout(pic_layout)  # Add the centered picture layout
        layout.addWidget(self.profile_name_label)
        layout.addLayout(role_layout)  # Add the centered role layout
        layout.addStretch()

        return profile_card

    def _create_profile_info_widget(self) -> QWidget:
        """Creates the bottom-left widget for detailed profile information."""
        info_card = QWidget()
        info_card.setObjectName("infoCard")
        layout = QVBoxLayout(info_card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignTop)

        info_title = QLabel("Profile Information")
        info_title.setObjectName("cardHeader")

        self.full_name_label = QLabel("N/A")
        self.full_name_label.setObjectName("infoField")
        self.email_label = QLabel("N/A")
        self.email_label.setObjectName("infoField")
        self.phone_label = QLabel("N/A")
        self.phone_label.setObjectName("infoField")

        layout.addWidget(info_title)
        layout.addSpacing(10)

        layout.addWidget(QLabel("Full Name"))
        layout.addWidget(self.full_name_label)
        layout.addSpacing(5)

        layout.addWidget(QLabel("Email"))
        layout.addWidget(self.email_label)
        layout.addSpacing(5)

        layout.addWidget(QLabel("Phone Number"))
        layout.addWidget(self.phone_label)

        layout.addStretch()
        return info_card

    def _create_working_area_widget(self) -> QWidget:
        """Creates the top-right widget to display working area tags."""
        working_area_card = QWidget()
        working_area_card.setObjectName("infoCard")

        # Main vertical layout for the card
        v_layout = QVBoxLayout(working_area_card)
        v_layout.setContentsMargins(20, 20, 20, 20)
        v_layout.setSpacing(10)
        v_layout.setAlignment(Qt.AlignTop)

        wa_title = QLabel("Working Area")
        wa_title.setObjectName("cardHeader")

        # A horizontal layout to contain the grid and a stretch, ensuring the grid doesn't expand
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(
            0, 0, 0, 0
        )  # No extra margins for this internal layout

        self.wa_grid_layout = QGridLayout()
        self.wa_grid_layout.setSpacing(10)

        h_layout.addLayout(self.wa_grid_layout)
        h_layout.addStretch(1)  # Add a spacer that will take all extra horizontal space

        v_layout.addWidget(wa_title)
        v_layout.addLayout(h_layout)
        v_layout.addStretch(1)  # Keep the vertical stretch to push everything up

        return working_area_card

    def _create_recent_activity_widget(self) -> QWidget:
        """Creates the bottom-right widget for recent activity logs."""
        activity_card = QWidget()
        activity_card.setObjectName("infoCard")
        layout = QVBoxLayout(activity_card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        ac_title = QLabel("Recent Activity")
        ac_title.setObjectName("cardHeader")

        self.activity_grid_layout = QGridLayout()
        self.activity_grid_layout.setSpacing(10)
        # Set column stretch to make 'Detail' column wider
        self.activity_grid_layout.setColumnStretch(1, 1)

        layout.addWidget(ac_title)
        layout.addLayout(self.activity_grid_layout)
        layout.addStretch()

        return activity_card

    def _load_and_apply_profile(self):
        """Loads user profile from QSettings and updates the UI."""
        settings = QSettings()
        profile_json_str = settings.value("IDPMPlugin/user_profile", None)
        if not profile_json_str:
            return

        try:
            self.user_profile = json.loads(profile_json_str)

            # Populate profile card and info fields
            username = self.user_profile.get("username", "N/A")
            roles = self.user_profile.get("roles", "N/A")
            if isinstance(roles, list):
                roles = ", ".join(roles)

            self.profile_name_label.setText(username)
            self.profile_role_label.setText(roles)
            self.full_name_label.setText(self.user_profile.get("fullname", username))
            self.email_label.setText(self.user_profile.get("email", "N/A"))
            self.phone_label.setText(self.user_profile.get("phone", "N/A"))

            # --- Populate Working Area ---
            wilker_list = self.user_profile.get("allowed", [])
            for i in reversed(range(self.wa_grid_layout.count())):
                self.wa_grid_layout.itemAt(i).widget().setParent(None)

            row, col, max_cols = 0, 0, 4
            for wilker in wilker_list:
                tag = QLabel(wilker)
                tag.setObjectName("tagLabel")
                self.wa_grid_layout.addWidget(tag, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            # --- Populate Recent Activity ---
            last_login_str = self.user_profile.get("last_login")

            for i in reversed(range(self.activity_grid_layout.count())):
                self.activity_grid_layout.itemAt(i).widget().setParent(None)

            headers = ["Date", "Detail", "Time"]
            for i, text in enumerate(headers):
                header_label = QLabel(text)
                header_label.setObjectName("activityHeader")
                self.activity_grid_layout.addWidget(header_label, 0, i)

            if last_login_str:
                try:
                    if last_login_str.endswith("Z"):
                        last_login_str = last_login_str.replace("Z", "+00:00")
                    dt_obj = datetime.fromisoformat(last_login_str)
                    date_str = dt_obj.strftime("%Y/%m/%d")
                    time_str = dt_obj.strftime("%H:%M:%S")
                    detail_str = f"{username} logged in."

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
            ThemedMessageBox.show_message(
                self, QMessageBox.Critical, "Error", "Failed to parse user profile."
            )

    def _on_profile_picture_loaded(self, reply: QNetworkReply):
        """Handles the response from the profile picture download."""
        if reply.error() == QNetworkReply.NoError:
            image_data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                # Create a circular pixmap
                size = self.profile_pic_label.width()
                circular_pixmap = QPixmap(size, size)
                circular_pixmap.fill(Qt.transparent)

                painter = QPainter(circular_pixmap)
                painter.setRenderHint(QPainter.Antialiasing)

                path = QPainterPath()
                path.addEllipse(0, 0, size, size)
                painter.setClipPath(path)

                scaled_image = pixmap.scaled(
                    QSize(size, size), Qt.KeepAspectRatio, Qt.SmoothTransformation
                )

                x = (size - scaled_image.width()) / 2
                y = (size - scaled_image.height()) / 2
                painter.drawPixmap(int(x), int(y), scaled_image)
                painter.end()

                self.profile_pic_label.setPixmap(circular_pixmap)
            else:
                self.profile_pic_label.setText("Load failed")
        else:
            self.profile_pic_label.setText("Net error")
        reply.deleteLater()

    def apply_stylesheet(self) -> None:
        """Applies the QSS to style the dialog."""
        # Using a light theme to more closely match the screenshot
        qss = f"""
            #mainContainer {{
                background-color: #F8F9FA; 
                border-radius: 20px;
            }}
            QLabel {{
                color: #212529; 
                font-family: "Montserrat";
            }}
            #appBarTitle {{
                font-size: 18px;
                font-weight: bold;
            }}
            #backButton {{
                background-color: transparent;
                color: #274423;
                border: none;
                font-size: 14px;
                padding: 8px;
            }}
            #backButton:hover {{ text-decoration: underline; }}

            #minimizeButton, #maximizeButton, #closeButton {{
                background-color: transparent; color: #274423; border: none;
                font-family: "Arial", sans-serif; font-weight: bold; border-radius: 4px;
            }}
            #minimizeButton {{ font-size: 16px; padding-bottom: 5px; }}
            #maximizeButton {{ font-size: 16px; padding-top: 1px; }}
            #closeButton {{ font-size: 24px; padding-bottom: 2px; }}
            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover {{ background-color: rgba(255, 255, 255, 0.2); }}
            #minimizeButton:pressed, #maximizeButton:pressed, #closeButton:pressed {{ background-color: rgba(255, 255, 255, 0.1); }}

            #profileCard, #infoCard {{
                background-color: white;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #E9ECEF;
            }}

            #profilePicture {{
                border: 2px solid #E9ECEF;
                border-radius: 44px; /* (height/2) to make it circular */
            }}

            #profileCardName {{
                font-size: 18px;
                font-weight: bold;
            }}
            #profileCardRole {{
                font-size: 12px;
                color: white;
                background-color: #274423;
                padding: 4px 12px;
                border-radius: 10px; /* (height/2) for a pill shape */
            }}
            #cardHeader {{
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            
            QLabel#infoField {{
                background-color: #F8F9FA;
                color: #495057;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
            }}

            #tagLabel {{
                background-color: #F1F3F5;
                color: #495057;
                padding: 5px 10px;
                border-radius: 10px;
                font-size: 11px;
            }}
            #activityHeader {{
                font-weight: bold;
                color: #6C757D;
            }}
        """
        self.setStyleSheet(qss)
