from typing import Optional
import os
import json
from datetime import datetime

from qgis.PyQt.QtWidgets import QGraphicsDropShadowEffect

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QDialog,
    QMenu,
    QStyleOption,
    QStyle,
)
from PyQt5.QtGui import QFont, QHideEvent, QPixmap, QIcon, QPainter, QMouseEvent
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import QTimer, Qt, QSize, QUrl, QSettings, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from qgis.gui import QgisInterface
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsProject,
    QgsRectangle,
)

from ..config import Config
from .aoi_map_tool import AoiMapTool
from .base_dialog import BaseDialog
from .profile import ProfileDialog
from .loading import LoadingDialog
from .custom_input_dialog import CustomInputDialog
from .themed_message_box import ThemedMessageBox
from ..core.util import add_basemap_global_osm
from ..core.layer_loader_worker import LayerLoaderTask


class ActionCard(QWidget):
    """A custom card-like button with an icon, title, and subtitle."""

    clicked = pyqtSignal()

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
        self.setFixedSize(206, 126)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
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

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.rect().contains(event.pos()):
            self.setCursor(Qt.ArrowCursor)
            return

        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        pass

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.rect().contains(event.pos()):
            self.clicked.emit()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)


class MenuWidget(BaseDialog):
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
        self.active_loader_task = None

        self.aoi_tool = None
        self.previous_map_tool = None
        self.selected_aoi: Optional[QgsRectangle] = None

        self.init_menu_ui()
        self._load_and_apply_profile()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        active_modal = QApplication.activeModalWidget()
        if active_modal and active_modal != self:
            return
        super().mousePressEvent(event)

    def init_menu_ui(self) -> None:
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
        self.title_label.setFont(QFont("Montserrat", 14, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        subtitle_label = QLabel("Kelola dan Jelajahi Data Geospasial Anda")
        subtitle_label.setWordWrap(True)
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setFont(QFont("Montserrat", 16, QFont.Bold))
        subtitle_label.setAlignment(Qt.AlignCenter)
        description_label = QLabel(
            "Jelajahi fitur untuk kelola dan analisis data spasial"
        )
        description_label.setObjectName("descriptionLabel")
        description_label.setFont(QFont("Montserrat", 12, QFont.Light))
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
        icon_path_aoi = os.path.join(Config.ASSETS_PATH, "images", "focus.svg")

        self.card_list_raster = ActionCard(
            icon_path_raster, "Citra Satelit", "View Detail"
        )
        self.card_open_potensi = ActionCard(
            icon_path_potensi, "Open Data Potensi", "View Detail"
        )
        self.card_open_existing = ActionCard(
            icon_path_existing, "Open Data Existing", "View Detail"
        )
        self.card_select_aoi = ActionCard(
            icon_path_aoi, "Select AOI for Search", "Define Area"
        )

        self.card_list_raster.clicked.connect(self.open_image_list)
        self.card_open_potensi.clicked.connect(self.open_potensi_data)
        self.card_open_existing.clicked.connect(self.open_existing_data)
        self.card_select_aoi.clicked.connect(self._handle_select_aoi_for_search)

        button_layout.addWidget(self.card_list_raster)
        button_layout.addWidget(self.card_open_potensi)
        button_layout.addWidget(self.card_open_existing)
        button_layout.addWidget(self.card_select_aoi)
        content_layout.addWidget(button_container)

        aoi_status_layout = QHBoxLayout()
        aoi_status_layout.setAlignment(Qt.AlignCenter)
        self.aoi_status_label = QLabel("No Area of Interest (AOI) selected.")
        self.aoi_status_label.setObjectName("aoiStatusLabel")
        self.clear_aoi_button = QPushButton("Clear AOI")
        self.clear_aoi_button.setObjectName("clearAoiButton")
        self.clear_aoi_button.setCursor(Qt.PointingHandCursor)
        self.clear_aoi_button.setVisible(False)
        self.clear_aoi_button.clicked.connect(self._clear_aoi)
        aoi_status_layout.addStretch()
        aoi_status_layout.addWidget(self.aoi_status_label)
        aoi_status_layout.addWidget(self.clear_aoi_button)
        aoi_status_layout.addStretch()
        content_layout.addSpacing(20)
        content_layout.addLayout(aoi_status_layout)

        main_layout.addLayout(content_layout)
        main_layout.addStretch(2)
        self.apply_stylesheet()

    def _handle_select_aoi_for_search(self):
        add_basemap_global_osm(self.iface, zoom=False)

        self.hide()
        self.iface.messageBar().pushMessage(
            "Info",
            "Draw a rectangle on the map to define your search area. Press ESC to cancel.",
            level=Qgis.Info,
            duration=5,
        )

        self.aoi_tool = AoiMapTool(self.iface.mapCanvas())
        self.aoi_tool.aoiSelected.connect(self._on_aoi_selected_for_search)
        self.aoi_tool.cancelled.connect(self._on_aoi_cancelled)

        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.iface.mapCanvas().setMapTool(self.aoi_tool)
        self.iface.mapCanvas().setFocus()

    def _on_aoi_selected_for_search(self, aoi_rect: QgsRectangle):
        self.selected_aoi = aoi_rect
        self._restore_map_tool_and_show()
        self.aoi_status_label.setText("Area of Interest has been set.")
        self.clear_aoi_button.setVisible(True)
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "AOI Set",
            "The search area has been defined. Now click 'List Raster' to find intersecting images.",
        )

    def _on_aoi_cancelled(self):
        self._restore_map_tool_and_show()
        self.iface.messageBar().pushMessage(
            "Info", "AOI selection cancelled.", level=Qgis.Info, duration=3
        )

    def _restore_map_tool_and_show(self):
        self.iface.mapCanvas().setMapTool(self.previous_map_tool)
        self.aoi_tool = None
        self.previous_map_tool = None
        self.show()
        self.raise_()
        self.activateWindow()

    def _clear_aoi(self):
        self.selected_aoi = None
        self.aoi_status_label.setText("No Area of Interest (AOI) selected.")
        self.clear_aoi_button.setVisible(False)

    def _get_selected_wilker(self) -> Optional[str]:
        if not self.user_profile:
            ThemedMessageBox.show_message(
                self, QMessageBox.Critical, "Error", "User profile not loaded."
            )
            return None
        try:
            wilker_str = self.user_profile.get("wilker", "")
            wilker_list = sorted(
                [w.strip() for w in wilker_str.split(",") if w.strip()]
            )
            if not wilker_list:
                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Warning,
                    "No Working Area",
                    "Your user profile does not have a working area ('wilker') assigned.",
                )
                return None
            if len(wilker_list) == 1:
                return wilker_list[0]
            else:
                dialog = CustomInputDialog(
                    self,
                    "Select Working Area",
                    "Please select your working area:",
                    wilker_list,
                )
                if dialog.exec_() == QDialog.Accepted:
                    return dialog.selectedItem()
                else:
                    return None
        except Exception as e:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Profile Error",
                f"Could not read user profile 'wilker' attribute: {e}",
            )
            return None

    def open_image_list(self):
        selected_wilker = self._get_selected_wilker()
        if not selected_wilker:
            return

        settings = QSettings()
        token = settings.value("IDPMPlugin/token", None)
        if not token:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Authentication Error",
                "You are not logged in.",
            )
            return

        if self.loading_dialog is None:
            self.loading_dialog = LoadingDialog(self)
        self.setEnabled(False)
        self.loading_dialog.show()
        self.hide()

        request_url = f"{Config.API_URL}/geoportal/sentinel/catalog/{selected_wilker}"
        request = QNetworkRequest(QUrl(request_url))
        request.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        self.network_manager.finished.connect(self.handle_catalog_list_response)
        self.network_manager.get(request)

    def handle_catalog_list_response(self, reply: QNetworkReply):
        from .list_raster import ImageListDialog

        self.setEnabled(True)
        if self.loading_dialog:
            self.loading_dialog.close()

        try:
            self.network_manager.finished.disconnect(self.handle_catalog_list_response)
        except TypeError:
            pass

        if reply.error():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Error",
                f"Failed to fetch image list: {reply.errorString()}",
            )
            self.show()
            return

        response_data = reply.readAll().data()
        try:
            response = json.loads(response_data.decode("utf-8"))
            features = response.get("data", {}).get("features", [])

            if self.image_list_dialog is None:
                self.image_list_dialog = ImageListDialog(
                    features, self.iface, self.iface.mainWindow(), aoi=self.selected_aoi
                )
                self.image_list_dialog.finished.connect(self._on_image_list_closed)
                self.image_list_dialog.show()
            else:
                self.image_list_dialog.raise_()
                self.image_list_dialog.activateWindow()

        except (json.JSONDecodeError, Exception) as e:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Error",
                f"An unexpected error occurred: {e}",
            )
            self.show()
        finally:
            reply.deleteLater()

    def _on_image_list_closed(self):
        self.show()
        self.image_list_dialog = None

    def _start_layer_load_task(
        self, layer_type: str, selected_wilker: str, selected_year: int
    ):
        if self.loading_dialog is None:
            self.loading_dialog = LoadingDialog(self.parent())
        self.setEnabled(False)
        self.loading_dialog.show()

        add_basemap_global_osm(self.iface)

        self.active_loader_task = LayerLoaderTask(
            f"Loading {layer_type} data...",
            layer_type,
            selected_wilker,
            selected_year,
        )

        self.active_loader_task.layerLoaded.connect(self._on_layer_loaded)
        self.active_loader_task.errorOccurred.connect(self._on_layer_load_error)

        QgsApplication.taskManager().addTask(self.active_loader_task)

    def _on_layer_loaded(self, layer: QgsVectorLayer):
        self.setEnabled(True)
        if self.loading_dialog:
            self.loading_dialog.close()

        if layer and layer.isValid():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Information,
                "Success",
                f"Layer '{layer.name()}' loaded successfully.",
            )
            self.iface.setActiveLayer(layer)

            # --- START: RELIABLE ZOOM IMPLEMENTATION ---
            def perform_zoom():
                canvas = self.iface.mapCanvas()
                source_crs = layer.crs()
                dest_crs = canvas.mapSettings().destinationCrs()
                transform = QgsCoordinateTransform(
                    source_crs, dest_crs, QgsProject.instance()
                )
                transformed_extent = transform.transform(layer.extent())

                canvas.setExtent(transformed_extent)
                canvas.refresh()

            QTimer.singleShot(100, perform_zoom)
            # --- END: RELIABLE ZOOM IMPLEMENTATION ---

        else:
            self._on_layer_load_error("Loaded layer is invalid.")

        self.active_loader_task = None

    def _on_layer_load_error(self, error_message: str):
        self.setEnabled(True)
        if self.loading_dialog:
            self.loading_dialog.close()
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Critical,
            "Load Failed",
            f"Could not load the layer: {error_message}",
        )
        self.active_loader_task = None

    def open_existing_data(self):
        selected_wilker = self._get_selected_wilker()
        if not selected_wilker:
            return

        current_year = datetime.now().year
        years = [str(year) for year in range(2021, current_year + 1)]

        dialog = CustomInputDialog(
            self,
            "Select Year",
            f"Select a year for the 'Existing' data in {selected_wilker}:",
            years,
        )

        if dialog.exec_() == QDialog.Accepted:
            selected_year_str = dialog.selectedItem()
            selected_year = int(selected_year_str)
            self._start_layer_load_task("existing", selected_wilker, selected_year)

    def open_potensi_data(self):
        selected_wilker = self._get_selected_wilker()
        if not selected_wilker:
            return

        current_year = datetime.now().year
        years = [str(year) for year in range(2021, current_year + 1)]

        dialog = CustomInputDialog(
            self,
            "Select Year",
            f"Select a year for the 'Potensi' data in {selected_wilker}:",
            years,
        )

        if dialog.exec_() == QDialog.Accepted:
            selected_year_str = dialog.selectedItem()
            selected_year = int(selected_year_str)
            self._start_layer_load_task("potensi", selected_wilker, selected_year)

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
        saved_pos = self.pos()
        self.hide()
        self.profile_dialog.exec_()
        self.move(saved_pos)
        self.show()

    def handle_logout(self):
        confirm = ThemedMessageBox.show_message(
            parent=self,
            icon=QMessageBox.Question,
            title="Confirm Logout",
            text="Are you sure you want to log out?",
            buttons=QMessageBox.Yes | QMessageBox.No,
            default_button=QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            settings = QSettings()
            settings.remove("IDPMPlugin/token")
            settings.remove("IDPMPlugin/user_profile")
            QgsMessageLog.logMessage("User logged out.", "IDPMPlugin", Qgis.Info)
            self.accept()

    def hideEvent(self, event):
        super().hideEvent(event)

        def do_initial_zoom():
            if not any(
                layer.name().endswith(("_Visual", "_NDVI", "_FalseColor", "_Custom"))
                for layer in QgsProject.instance().mapLayers().values()
            ):
                indonesia_bbox = QgsRectangle(95.0, -11.0, 141.0, 6.0)
                dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")
                source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                transform = QgsCoordinateTransform(
                    source_crs, dest_crs, QgsProject.instance()
                )
                indonesia_bbox_transformed = transform.transform(indonesia_bbox)
                self.iface.mapCanvas().setExtent(indonesia_bbox_transformed)
                self.iface.mapCanvas().refresh()

        QTimer.singleShot(0, do_initial_zoom)

    def apply_stylesheet(self) -> None:
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
            #titleLabel {{ font-size: 18px; font-weight: 600; }}
            #subtitleLabel {{ font-size: 22px; font-weight: 600; }}
            #descriptionLabel {{ font-size: 16px; color: #FFFFFF; font-weight: 300; }}
            #aoiStatusLabel {{ font-size: 12px; color: #FFFFFF; font-style: italic; font-weight: 300; }}
            
            #clearAoiButton {{
                background-color: transparent;
                color: #FFDAB9;
                border: none;
                text-decoration: underline;
                font-size: 12px;
                padding: 2px;
            }}
            #clearAoiButton:hover {{ color: white; }}
            
            #minimizeButton, #maximizeButton, #closeButton {{
                background-color: transparent; color: white; border: none;
                font-family: "Arial", sans-serif; font-weight: bold; border-radius: 4px;
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
                width: 20px; height: 20px;
                subcontrol-position: center right; subcontrol-origin: padding; right: 15px;
            }}
            QMenu {{
                background-color: #5E765F; color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px; padding: 6px;
            }}
            QMenu::item {{ padding: 8px 20px; border-radius: 4px; }}
            QMenu::item:selected {{ background-color: rgba(255, 255, 255, 0.15); }}
            QMenu::separator {{ height: 1px; background: rgba(255, 255, 255, 0.2); margin: 6px 0px; }}
            #actionCard {{
                background-color: rgba(255, 255, 255, 0.4);
                border-radius: 14px;
            }}
            #actionCard:hover {{ background-color: rgba(255, 255, 255, 0.6); box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.2); }}
            #cardTitle {{ font-size: 14px; font-weight: bold; color: #FFFFFF; }}
            #cardSubtitle {{ color: #D0D0D0; font-size: 11px; color: #FFFFFF; }}
        """
        self.setStyleSheet(qss)
