from typing import Optional, List, Dict, Any
import sys
import os
import json
from datetime import datetime

from qgis.gui import QgisInterface
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsRasterLayer,
    QgsProject,
    QgsMessageLog,
    QgsRasterShader,
    QgsColorRampShader,
    QgsSingleBandPseudoColorRenderer,
    QgsLayerTreeGroup,
    QgsAuthMethodConfig,
)
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QScrollArea,
    QMessageBox,
    QApplication,
    QLineEdit,
    QStyleOption,
    QStyle,
    QProgressBar,
    QProgressDialog,
)
from PyQt5.QtGui import QFont, QPixmap, QIcon, QPainter, QPainterPath, QBrush, QColor
from PyQt5.QtCore import Qt, QSize, QUrl, QRectF, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..config import Config
from .base_dialog import BaseDialog
from ..core import NdvITask, RasterAsset

PLUGIN_LAYER_GROUP_NAME = "IDPM Layers"


class RoundedImageLabel(QLabel):
    """A QLabel that displays a pixmap with rounded corners and a placeholder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.radius = 8
        self.placeholder_color = QColor(0, 0, 0, 51)  # 20% opaque black

    def setPixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.radius, self.radius)

        if self._pixmap.isNull():
            painter.fillPath(path, QBrush(self.placeholder_color))
        else:
            painter.setClipPath(path)
            scaled_pixmap = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = (self.width() - scaled_pixmap.width()) / 2
            y = (self.height() - scaled_pixmap.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled_pixmap)


class RasterItemWidget(QWidget):
    """A custom widget to display a single raster item in the list."""

    downloadVisualRequested = pyqtSignal(RasterAsset)
    openVisualRequested = pyqtSignal(RasterAsset)
    processNdviRequested = pyqtSignal(RasterAsset)
    openNdviRequested = pyqtSignal(RasterAsset)

    def __init__(self, asset: RasterAsset, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.asset = asset
        self.setObjectName("rasterItem")
        self.setAutoFillBackground(True)

        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._handle_thumbnail_loaded)

        self.downloaded_bands = {}

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Thumbnail
        self.thumb_label = RoundedImageLabel()
        self.thumb_label.setFixedSize(202, 148)
        main_layout.addWidget(self.thumb_label)
        self.load_thumbnail()

        # Details Layout
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)

        self.stac_id_label = QLabel(self.asset.stac_id)
        self.stac_id_label.setObjectName("rasterTitle")

        date_str = "N/A"
        if self.asset.capture_date:
            date_str = self.asset.capture_date.strftime("%d %b %Y %H:%M:%S")
        published_label = QLabel(f"Published on: {date_str}")
        published_label.setObjectName("rasterSubtitle")

        cloud_label = QLabel(f"{self.asset.cloud_cover:.2f}%")
        cloud_label.setObjectName("rasterCloud")

        details_layout.addWidget(self.stac_id_label)
        details_layout.addWidget(published_label)
        details_layout.addWidget(cloud_label)
        details_layout.addStretch()

        main_layout.addLayout(details_layout)
        main_layout.addStretch()

        # --- Action Buttons and Progress Bars ---
        right_column_layout = self._create_actions_layout()
        main_layout.addLayout(right_column_layout)

        self.update_ui_based_on_local_files()

    def _create_actions_layout(self) -> QVBoxLayout:
        """Creates the layout for buttons and progress bars."""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.btn_visual = QPushButton()
        self.btn_visual.setObjectName("actionButton")
        download_icon_path = os.path.join(Config.ASSETS_PATH, "images", "download.png")
        if os.path.exists(download_icon_path):
            self.btn_visual.setIcon(QIcon(download_icon_path))
        self.btn_visual.clicked.connect(self._on_visual_button_clicked)
        layout.addWidget(self.btn_visual)

        self.progress_bar_visual = self._create_progress_bar()
        layout.addWidget(self.progress_bar_visual)

        self.btn_ndvi = QPushButton()
        self.btn_ndvi.setObjectName("actionButton")
        self.btn_ndvi.clicked.connect(self._on_ndvi_button_clicked)
        layout.addWidget(self.btn_ndvi)

        ndvi_progress_layout = QHBoxLayout()
        self.progress_bar_nir = self._create_progress_bar()
        self.progress_bar_red = self._create_progress_bar()
        ndvi_progress_layout.addWidget(self.progress_bar_nir)
        ndvi_progress_layout.addWidget(self.progress_bar_red)
        layout.addLayout(ndvi_progress_layout)

        self.status_label = QLabel("")
        self.status_label.setObjectName("rasterStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        return layout

    def _create_progress_bar(self) -> QProgressBar:
        pbar = QProgressBar()
        pbar.setTextVisible(True)
        pbar.setVisible(False)
        pbar.setFixedHeight(12)
        pbar.setStyleSheet(
            """
            QProgressBar { border: 1px solid #C0C0C0; border-radius: 5px; background-color: #E0E0E0; text-align: center; color: black; font-size: 8px; }
            QProgressBar::chunk { background-color: #2E4434; }
            """
        )
        return pbar

    def load_thumbnail(self):
        if self.asset.thumbnail_url:
            request = QNetworkRequest(QUrl(self.asset.thumbnail_url))
            self.network_manager.get(request)

    def _handle_thumbnail_loaded(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            self.thumb_label.setPixmap(pixmap)
        reply.deleteLater()

    def _on_visual_button_clicked(self):
        visual_path = self.asset.get_local_path("visual")
        if os.path.exists(visual_path) and os.path.getsize(visual_path) > 0:
            self.openVisualRequested.emit(self.asset)
        else:
            self.btn_visual.setEnabled(False)
            self.btn_ndvi.setEnabled(False)
            self.progress_bar_visual.setVisible(True)
            self.status_label.setVisible(True)
            self.status_label.setText("Downloading visual...")
            self.downloadVisualRequested.emit(self.asset)

    def _on_ndvi_button_clicked(self):
        ndvi_path = self.asset.get_local_path("ndvi")
        if os.path.exists(ndvi_path) and os.path.getsize(ndvi_path) > 0:
            self.openNdviRequested.emit(self.asset)
        else:
            self.btn_visual.setEnabled(False)
            self.btn_ndvi.setEnabled(False)
            self.progress_bar_nir.setVisible(True)
            self.progress_bar_red.setVisible(True)
            self.status_label.setVisible(True)
            self.status_label.setText("Downloading bands...")
            self.processNdviRequested.emit(self.asset)

    def update_download_progress(
        self, bytes_received: int, bytes_total: int, band: str
    ):
        if bytes_total > 0:
            progress = int((bytes_received / bytes_total) * 100)
            pbar = getattr(self, f"progress_bar_{band}", None)
            if pbar:
                pbar.setValue(progress)
                if band == "visual":
                    self.status_label.setText(f"Downloading Visual: {progress}%")
                else:
                    pbar.setFormat(f"{band.upper()}: {progress}%")

    def update_ui_based_on_local_files(self):
        visual_path = self.asset.get_local_path("visual")
        if os.path.exists(visual_path) and os.path.getsize(visual_path) > 0:
            self.btn_visual.setText("Open Visual")
            self.stac_id_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.btn_visual.setText("Download Visual")
            self.stac_id_label.setStyleSheet("")

        ndvi_path = self.asset.get_local_path("ndvi")
        if os.path.exists(ndvi_path) and os.path.getsize(ndvi_path) > 0:
            self.btn_ndvi.setText("Open NDVI")
            self.btn_ndvi.setProperty("highlight", False)
            self.stac_id_label.setStyleSheet("color: darkblue; font-weight: bold;")
        else:
            self.btn_ndvi.setText("Process NDVI")
            self.btn_ndvi.setProperty("highlight", True)

        self.btn_visual.setEnabled(True)
        self.btn_ndvi.setEnabled(True)
        self.progress_bar_visual.setVisible(False)
        self.progress_bar_nir.setVisible(False)
        self.progress_bar_red.setVisible(False)
        self.status_label.setVisible(False)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)


class ImageListDialog(BaseDialog):
    """The dialog to display a list of raster images."""

    def __init__(
        self,
        data: List[Dict[str, Any]],
        iface: QgisInterface,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.iface = iface
        self.all_assets = [
            RasterAsset(feature.get("properties", {}))
            for feature in data
            if "properties" in feature
        ]
        self.download_network_manager = QNetworkAccessManager(self)

        if not os.path.exists(Config.DOWNLOAD_DIR):
            os.makedirs(Config.DOWNLOAD_DIR)

        self.active_operations: Dict[str, Any] = {}
        self.current_page = 1
        self.items_per_page = 5

        self.init_list_ui()
        self.update_list_and_pagination()
        self.add_basemap_global_osm(self.iface)

    def init_list_ui(self):
        self.setWindowTitle("List Raster")
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 10, 30, 30)
        main_layout.addLayout(self._create_top_bar())
        main_layout.addSpacing(20)

        header_layout = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title = QLabel("List Raster")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Select raster data to download or process into NDVI.")
        subtitle.setObjectName("pageSubtitle")
        title_vbox.addWidget(title)
        title_vbox.addWidget(subtitle)
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(20)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("scrollArea")
        scroll_content = QWidget()
        self.list_layout = QVBoxLayout(scroll_content)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        main_layout.addLayout(self._create_pagination_controls())
        self.apply_stylesheet()

    def _create_top_bar(self) -> QHBoxLayout:
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 10)
        self.back_button = QPushButton("← Back to Menu")
        self.back_button.setObjectName("backButton")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.clicked.connect(self.accept)
        top_bar_layout.addWidget(self.back_button)
        top_bar_layout.addStretch()
        controls_layout = self._create_window_controls()
        top_bar_layout.addLayout(controls_layout)
        return top_bar_layout

    def _create_pagination_controls(self) -> QHBoxLayout:
        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("← Previous")
        self.prev_button.setObjectName("paginationButton")
        self.prev_button.clicked.connect(self.prev_page)

        self.page_label = QLabel("Page 1")
        self.page_label.setObjectName("pageLabel")

        self.next_button = QPushButton("Next →")
        self.next_button.setObjectName("paginationButton")
        self.next_button.clicked.connect(self.next_page)

        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_button)
        return pagination_layout

    def update_list_and_pagination(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                # Cancel any ongoing downloads for the item being removed
                if isinstance(item.widget(), RasterItemWidget):
                    # Ensure RasterItemWidget has a method to cancel its network requests if any
                    pass
                item.widget().deleteLater()

        start_index = (self.current_page - 1) * self.items_per_page
        paginated_assets = self.all_assets[
            start_index : start_index + self.items_per_page
        ]

        for asset in paginated_assets:
            item_widget = RasterItemWidget(asset, self)
            item_widget.downloadVisualRequested.connect(
                self._handle_download_visual_requested
            )
            item_widget.openVisualRequested.connect(self._handle_open_visual_requested)
            item_widget.processNdviRequested.connect(
                self._handle_process_ndvi_requested
            )
            item_widget.openNdviRequested.connect(self._handle_open_ndvi_requested)
            self.list_layout.insertWidget(self.list_layout.count() - 1, item_widget)

        total_pages = (
            len(self.all_assets) + self.items_per_page - 1
        ) // self.items_per_page
        self.page_label.setText(f"Page {self.current_page} of {max(1, total_pages)}")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < total_pages)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.update_list_and_pagination()

    def next_page(self):
        total_pages = (
            len(self.all_assets) + self.items_per_page - 1
        ) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.update_list_and_pagination()

    def get_or_create_plugin_layer_group(self) -> Optional[QgsLayerTreeGroup]:
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        if not root:
            return None
        group_node = root.findGroup(PLUGIN_LAYER_GROUP_NAME)
        if group_node is None:
            group_node = root.addGroup(PLUGIN_LAYER_GROUP_NAME)
        return group_node

    def add_basemap_global_osm(self, iface: QgisInterface):
        layer_name = "OpenStreetMap (IDPM Basemap)"
        log_tag = "IDPMPlugin"
        plugin_group = self.get_or_create_plugin_layer_group()

        if plugin_group:
            for child_node in plugin_group.children():
                if hasattr(child_node, "name") and child_node.name() == layer_name:
                    if hasattr(child_node, "layer"):
                        return
                    return

        url = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
        layer_source = f"type=xyz&url={url}&zmax=19&zmin=0"
        layer = QgsRasterLayer(layer_source, layer_name, "wms")

        if layer.isValid():
            QgsProject.instance().addMapLayer(layer, False)
            if plugin_group:
                plugin_group.addLayer(layer)
        else:
            QgsMessageLog.logMessage(
                f"Failed to load basemap '{layer_name}'. Error: {layer.error().summary()}",
                log_tag,
                Qgis.Critical,
            )

    def _get_item_widget(self, stac_id: str) -> Optional[RasterItemWidget]:
        for i in range(self.list_layout.count()):
            widget = self.list_layout.itemAt(i).widget()
            if isinstance(widget, RasterItemWidget) and widget.asset.stac_id == stac_id:
                return widget
        return None

    def _handle_download_visual_requested(self, asset: RasterAsset):
        if not asset.visual_url:
            QMessageBox.warning(
                self, "Missing Asset", f"No 'visual' asset found for {asset.stac_id}."
            )
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()
            return
        self._start_download(
            asset, "visual", asset.visual_url, asset.get_local_path("visual")
        )

    def _handle_open_visual_requested(self, asset: RasterAsset):
        self._load_raster_into_qgis(
            asset.get_local_path("visual"), f"{asset.stac_id}_Visual"
        )

    def _handle_process_ndvi_requested(self, asset: RasterAsset):
        if not asset.nir_url or not asset.red_url:
            QMessageBox.warning(
                self,
                "Missing Assets",
                f"NIR or RED bands not found for {asset.stac_id}.",
            )
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()
            return

        self.active_operations[asset.stac_id] = {"expected": 2, "completed": {}}
        for band_type, url in [("nir", asset.nir_url), ("red", asset.red_url)]:
            save_path = asset.get_local_path(band_type)
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self._on_band_download_complete(asset.stac_id, band_type, save_path)
            else:
                self._start_download(asset, band_type, url, save_path)

    def _handle_open_ndvi_requested(self, asset: RasterAsset):
        self._load_ndvi_into_qgis_layer(asset.get_local_path("ndvi"), asset.stac_id)

    def _start_download(self, asset: RasterAsset, band: str, url: str, save_path: str):
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        request = QNetworkRequest(QUrl(url))
        reply = self.download_network_manager.get(request)
        reply.setProperty("stac_id", asset.stac_id)
        reply.setProperty("band", band)
        reply.setProperty("save_path", save_path)
        file_handle = open(save_path, "wb")
        reply.setProperty("file_handle", file_handle)
        reply.downloadProgress.connect(self._on_download_progress)
        reply.finished.connect(lambda r=reply: self._on_download_finished(r))
        reply.readyRead.connect(
            lambda r=reply: r.property("file_handle").write(r.readAll())
        )

    def _on_download_progress(self, bytes_received: int, bytes_total: int):
        reply = self.sender()
        stac_id = reply.property("stac_id")
        band = reply.property("band")
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_download_progress(bytes_received, bytes_total, band)

    def _on_download_finished(self, reply: QNetworkReply):
        stac_id = reply.property("stac_id")
        band = reply.property("band")
        save_path = reply.property("save_path")
        reply.property("file_handle").close()

        if reply.error() != QNetworkReply.NoError:
            QMessageBox.critical(
                self,
                "Download Failed",
                f"Failed to download {band} for {stac_id}: {reply.errorString()}",
            )
            if os.path.exists(save_path):
                os.remove(save_path)
            if item_widget := self._get_item_widget(stac_id):
                item_widget.update_ui_based_on_local_files()
        else:
            if band == "visual":
                self._load_raster_into_qgis(save_path, f"{stac_id}_Visual")
                if item_widget := self._get_item_widget(stac_id):
                    item_widget.update_ui_based_on_local_files()
            else:
                self._on_band_download_complete(stac_id, band, save_path)
        reply.deleteLater()

    def _on_band_download_complete(self, stac_id: str, band: str, save_path: str):
        op = self.active_operations.get(stac_id, {})
        op["completed"][band] = save_path
        if len(op["completed"]) == op.get("expected", 0):
            self._calculate_ndvi(
                stac_id, op["completed"]["red"], op["completed"]["nir"]
            )
            del self.active_operations[stac_id]

    def _calculate_ndvi(self, stac_id: str, red_path: str, nir_path: str):
        folder_path = os.path.dirname(red_path)
        task = NdvITask(red_path, nir_path, folder_path, stac_id)
        progress = QProgressDialog(
            f"Calculating NDVI: {stac_id}...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        task.progressChanged.connect(progress.setValue)
        task.calculationFinished.connect(
            lambda path: self._on_ndvi_task_finished(path, stac_id)
        )
        task.errorOccurred.connect(lambda err: self._on_ndvi_task_error(err, stac_id))
        progress.canceled.connect(task.cancel)
        QgsApplication.taskManager().addTask(task)

    def _on_ndvi_task_finished(self, ndvi_path: str, stac_id: str):
        QgsApplication.taskManager().allTasksFinished.emit()  # Helps close progress dialog
        QMessageBox.information(
            self, "NDVI Calculated", f"NDVI calculation completed for {stac_id}."
        )
        self._load_ndvi_into_qgis_layer(ndvi_path, stac_id)
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _on_ndvi_task_error(self, error_msg: str, stac_id: str):
        QgsApplication.taskManager().allTasksFinished.emit()
        QMessageBox.critical(
            self, "Error", f"Failed to calculate NDVI for {stac_id}: {error_msg}"
        )
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _load_raster_into_qgis(self, path: str, name: str):
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            QMessageBox.warning(self, "Invalid Layer", f"Failed to load layer: {path}")
            return
        QgsProject.instance().addMapLayer(layer, False)
        if group := self.get_or_create_plugin_layer_group():
            group.insertLayer(0, layer)
        self.iface.mapCanvas().setExtent(layer.extent())
        self.iface.mapCanvas().refresh()

    def _load_ndvi_into_qgis_layer(self, ndvi_path: str, raster_id: str) -> bool:
        layer = QgsRasterLayer(ndvi_path, f"{raster_id}_NDVI")
        if not layer.isValid():
            QMessageBox.warning(
                self, "Invalid Layer", f"Failed to load NDVI layer from {ndvi_path}"
            )
            return False

        color_ramp = QgsColorRampShader()
        color_ramp.setColorRampType(QgsColorRampShader.Discrete)
        items = [
            QgsColorRampShader.ColorRampItem(
                0.0, QColor(0, 0, 255), "Water/Non-Vegetation"
            ),
            QgsColorRampShader.ColorRampItem(
                0.2, QColor(255, 255, 0), "Jarang (Sparse)"
            ),
            QgsColorRampShader.ColorRampItem(0.5, QColor(0, 255, 0), "Sedang (Medium)"),
            QgsColorRampShader.ColorRampItem(1.0, QColor(0, 100, 0), "Rapat (Dense)"),
        ]
        color_ramp.setColorRampItemList(items)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(color_ramp)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

        QgsProject.instance().addMapLayer(layer, False)
        if group := self.get_or_create_plugin_layer_group():
            group.insertLayer(0, layer)

        self.iface.mapCanvas().setExtent(layer.extent())
        self.iface.mapCanvas().refresh()
        return True

    def apply_stylesheet(self) -> None:
        qss = f"""
            #mainContainer {{ background-color: #F8F9FA; border-radius: 20px; }}
            QLabel {{ color: #212529; font-family: "Montserrat"; }}
            #pageTitle {{ font-size: 28px; font-weight: bold; color: #212529; }}
            #pageSubtitle {{ font-size: 14px; color: #808080; }}
            #backButton {{ background-color: transparent; color: #274423; border: none; font-size: 14px; padding: 8px; }}
            #backButton:hover {{ text-decoration: underline; }}
            #minimizeButton, #maximizeButton, #closeButton {{ color: #274423; }}
            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover {{ background-color: #E9ECEF; }}
            #scrollArea {{ border: none; background-color: transparent; }}
            #rasterItem {{ background-color: white; border: 1px solid #DEE2E6; border-radius: 12px; }}
            #rasterTitle {{ font-weight: bold; font-size: 16px; }}
            #rasterSubtitle {{ color: #808080; font-size: 14px; font-style: italic; }}
            #rasterCloud {{ font-weight: bold; color: #274423; font-size: 12px; }}
            #rasterStatus {{ font-weight: bold; font-size: 10px; }}
            #actionButton {{ background-color: white; color: #495057; border: 1px solid #DEE2E6; padding: 8px 12px; border-radius: 12px; font-weight: bold; icon-spacing: 6px; }}
            #actionButton:hover {{ background-color: #F8F9FA; }}
            #actionButton[highlight="true"] {{ background-color: #2E4434; color: white; border: none; }}
            #actionButton[highlight="true"]:hover {{ background-color: #3D5A43; }}
            #paginationButton {{ background-color: white; color: #274423; border: 1px solid #274423; padding: 8px 16px; border-radius: 12px; }}
            #paginationButton:disabled {{ background-color: #E9ECEF; color: #6C757D; border: 1px solid #CED4DA; }}
            #pageLabel {{ color: #274423; font-size: 14px; }}
        """
        self.setStyleSheet(qss)

    def closeEvent(self, event):
        # Disconnect signals to prevent issues on close
        try:
            self.download_network_manager.finished.disconnect()
        except TypeError:
            pass
        super().closeEvent(event)
