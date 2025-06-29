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
    QgsMultiBandColorRenderer,
    QgsLayerTreeGroup,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
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
    QComboBox,
)
from PyQt5.QtGui import QFont, QPixmap, QIcon, QPainter, QPainterPath, QBrush, QColor
from PyQt5.QtCore import Qt, QSize, QUrl, QRectF, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..config import Config
from .base_dialog import BaseDialog
from .ndvi_style_dialog import NdviStyleDialog
from ..core import NdvITask, RasterAsset
from .themed_message_box import ThemedMessageBox


PLUGIN_LAYER_GROUP_NAME = "IDPM Layers"


class RoundedImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.radius = 8
        self.placeholder_color = QColor(0, 0, 0, 51)

    def setPixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

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
    downloadVisualRequested = pyqtSignal(RasterAsset)
    openVisualRequested = pyqtSignal(RasterAsset)
    processNdviRequested = pyqtSignal(RasterAsset, list)
    openNdviRequested = pyqtSignal(RasterAsset)
    openFalseColorRequested = pyqtSignal(RasterAsset)

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
        self.thumb_label = RoundedImageLabel()
        self.thumb_label.setFixedSize(202, 148)
        main_layout.addWidget(self.thumb_label)
        self.load_thumbnail()
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)
        self.stac_id_label = QLabel(self.asset.stac_id)
        self.stac_id_label.setObjectName("rasterTitle")
        date_str = "N/A"
        if self.asset.capture_date:
            date_str = self.asset.capture_date.strftime("%d %b %Y %H:%M:%S")
        published_label = QLabel(f"Published on: {date_str}")
        published_label.setObjectName("rasterSubtitle")
        cloud_label = QLabel(f"Cloud Cover: {self.asset.cloud_cover:.2f}%")
        cloud_label.setObjectName("rasterCloud")
        details_layout.addWidget(self.stac_id_label)
        details_layout.addStretch(1)
        details_layout.addWidget(published_label)
        details_layout.addStretch(1)
        details_layout.addWidget(cloud_label)
        details_layout.addStretch(2)
        main_layout.addLayout(details_layout)
        main_layout.addStretch()
        right_column_layout = self._create_actions_layout()
        main_layout.addLayout(right_column_layout)
        self.update_ui_based_on_local_files()

    def _create_actions_layout(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        self.btn_visual = QPushButton()
        self.btn_visual.setObjectName("actionButton")
        self.btn_visual.clicked.connect(self._on_visual_button_clicked)
        buttons_layout.addWidget(self.btn_visual)
        self.btn_ndvi = QPushButton()
        self.btn_ndvi.setObjectName("actionButton")
        self.btn_ndvi.clicked.connect(self._on_ndvi_button_clicked)
        buttons_layout.addWidget(self.btn_ndvi)
        self.btn_false_color = QPushButton("Open False Color")
        self.btn_false_color.setObjectName("actionButton")
        self.btn_false_color.clicked.connect(self._on_false_color_button_clicked)
        buttons_layout.addWidget(self.btn_false_color)
        layout.addLayout(buttons_layout)
        self.progress_bar_visual = self._create_progress_bar()
        layout.addWidget(self.progress_bar_visual)
        ndvi_progress_layout = QHBoxLayout()
        self.progress_bar_nir = self._create_progress_bar()
        self.progress_bar_red = self._create_progress_bar()
        self.progress_bar_green = self._create_progress_bar()
        ndvi_progress_layout.addWidget(self.progress_bar_nir)
        ndvi_progress_layout.addWidget(self.progress_bar_red)
        ndvi_progress_layout.addWidget(self.progress_bar_green)
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
            self.set_buttons_enabled(False)
            self.progress_bar_visual.setVisible(True)
            self.status_label.setVisible(True)
            self.status_label.setText("Downloading visual...")
            self.downloadVisualRequested.emit(self.asset)

    def _on_ndvi_button_clicked(self):
        ndvi_path = self.asset.get_local_path("ndvi")
        if os.path.exists(ndvi_path) and os.path.getsize(ndvi_path) > 0:
            self.openNdviRequested.emit(self.asset)
        else:
            style_dialog = NdviStyleDialog(self)
            if style_dialog.exec_() == QDialog.Accepted:
                classification_items = style_dialog.get_classification_items()
                self.set_buttons_enabled(False)
                self.progress_bar_nir.setVisible(True)
                self.progress_bar_red.setVisible(True)
                if self.asset.green_url:
                    self.progress_bar_green.setVisible(True)
                self.status_label.setVisible(True)
                self.status_label.setText("Downloading bands...")
                self.processNdviRequested.emit(self.asset, classification_items)

    def _on_false_color_button_clicked(self):
        self.openFalseColorRequested.emit(self.asset)

    def set_buttons_enabled(self, enabled: bool):
        self.btn_visual.setEnabled(enabled)
        self.btn_ndvi.setEnabled(enabled)
        self.btn_false_color.setEnabled(enabled)

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
        """
        Updates the text and state of buttons based on whether the final
        or source files exist locally.
        """
        visual_path = self.asset.get_local_path("visual")
        ndvi_path = self.asset.get_local_path("ndvi")
        fc_path = self.asset.get_local_path("false_color")

        # Reset visibility of progress bars and status label
        self.progress_bar_visual.setVisible(False)
        self.progress_bar_nir.setVisible(False)
        self.progress_bar_red.setVisible(False)
        self.progress_bar_green.setVisible(False)
        self.status_label.setVisible(False)

        # Enable buttons by default, then disable them based on logic
        self.btn_visual.setEnabled(True)
        self.btn_ndvi.setEnabled(True)

        # --- Configure Visual Button ---
        if os.path.exists(visual_path) and os.path.getsize(visual_path) > 0:
            self.btn_visual.setText("Open Visual")
        else:
            self.btn_visual.setText("Download Visual")

        # --- Configure NDVI / Processing Button ---
        if os.path.exists(ndvi_path) and os.path.getsize(ndvi_path) > 0:
            self.btn_ndvi.setText("Open NDVI")
            self.btn_ndvi.setProperty("highlight", False)
        else:
            # Check for source bands if final product doesn't exist
            has_nir = bool(self.asset.nir_url)
            has_red = bool(self.asset.red_url)

            if has_nir and has_red:
                has_green = bool(self.asset.green_url)
                if has_green:
                    self.btn_ndvi.setText("Process NDVI & False Color")
                else:
                    self.btn_ndvi.setText("Process NDVI")
                self.btn_ndvi.setProperty("highlight", True)
            else:
                self.btn_ndvi.setText("Bands Missing")
                self.btn_ndvi.setProperty("highlight", False)
                self.btn_ndvi.setEnabled(False)

        # --- Configure False Color Button ---
        self.btn_false_color.setVisible(
            os.path.exists(fc_path) and os.path.getsize(fc_path) > 0
        )

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, painter, self)


class ImageListDialog(BaseDialog):
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
        self.filtered_assets: List[RasterAsset] = []
        self.download_network_manager = QNetworkAccessManager(self)
        self.active_operations: Dict[str, Any] = {}
        self.current_page = 1
        self.items_per_page = 5
        self.init_list_ui()
        self._apply_filters()  # Initial filter
        self.add_basemap_global_osm(self.iface)

    def init_list_ui(self):
        self.setWindowTitle("List Raster")
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 10, 30, 30)
        main_layout.addLayout(self._create_top_bar())
        main_layout.addSpacing(20)

        header_layout = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title_vbox.addWidget(QLabel("List Raster", objectName="pageTitle"))
        title_vbox.addWidget(
            QLabel(
                "Select raster data to download or process into NDVI.",
                objectName="pageSubtitle",
            )
        )
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        # Cloud Cover Filter
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        filter_layout.addWidget(QLabel("Cloud Cover:", objectName="filterLabel"))
        self.cloud_filter_combo = QComboBox()
        self.cloud_filter_combo.setObjectName("filterComboBox")
        self.cloud_filter_combo.addItems(["All", "0 - 10%", "10 - 20%", "20 - 30%"])
        self.cloud_filter_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.cloud_filter_combo)
        header_layout.addLayout(filter_layout)

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

    def _apply_filters(self):
        """Filters the list of assets based on the selected criteria."""
        filter_text = self.cloud_filter_combo.currentText()

        if filter_text == "All":
            self.filtered_assets = self.all_assets
        elif filter_text == "0 - 10%":
            self.filtered_assets = [
                asset for asset in self.all_assets if 0 <= asset.cloud_cover <= 10
            ]
        elif filter_text == "10 - 20%":
            self.filtered_assets = [
                asset for asset in self.all_assets if 10 < asset.cloud_cover <= 20
            ]
        elif filter_text == "20 - 30%":
            self.filtered_assets = [
                asset for asset in self.all_assets if 20 < asset.cloud_cover <= 30
            ]
        else:
            self.filtered_assets = self.all_assets

        self.current_page = 1
        self.update_list_and_pagination()

    def _create_top_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 10)
        self.back_button = QPushButton(
            "← Back to Menu", objectName="backButton", cursor=Qt.PointingHandCursor
        )
        self.back_button.clicked.connect(self.accept)
        layout.addWidget(self.back_button)
        layout.addStretch()
        layout.addLayout(self._create_window_controls())
        return layout

    def _create_pagination_controls(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.prev_button = QPushButton("← Previous", objectName="paginationButton")
        self.prev_button.clicked.connect(self.prev_page)
        self.page_label = QLabel("Page 1", objectName="pageLabel")
        self.next_button = QPushButton("Next →", objectName="paginationButton")
        self.next_button.clicked.connect(self.next_page)
        layout.addWidget(self.prev_button)
        layout.addStretch()
        layout.addWidget(self.page_label)
        layout.addStretch()
        layout.addWidget(self.next_button)
        return layout

    def update_list_and_pagination(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Clear "No results" message if it exists
        if self.list_layout.count() > 1 and isinstance(
            self.list_layout.itemAt(0).widget(), QLabel
        ):
            self.list_layout.itemAt(0).widget().deleteLater()

        if not self.filtered_assets:
            no_results_label = QLabel("No assets match the current filter.")
            no_results_label.setObjectName("noResultsLabel")
            no_results_label.setAlignment(Qt.AlignCenter)
            self.list_layout.insertWidget(0, no_results_label)

        start_index = (self.current_page - 1) * self.items_per_page
        paginated_assets = self.filtered_assets[
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
            item_widget.openFalseColorRequested.connect(
                self._handle_open_false_color_requested
            )
            self.list_layout.insertWidget(self.list_layout.count() - 1, item_widget)

        total_pages = (
            len(self.filtered_assets) + self.items_per_page - 1
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
            len(self.filtered_assets) + self.items_per_page - 1
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
        if not QgsProject.instance().mapLayersByName(layer_name):
            url = "type=xyz&url=https://a.tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
            layer = QgsRasterLayer(url, layer_name, "wms")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer, False)
                if group := self.get_or_create_plugin_layer_group():
                    group.addLayer(layer)
        if not any(
            layer.name().endswith(("_Visual", "_NDVI", "_FalseColor"))
            for layer in QgsProject.instance().mapLayers().values()
        ):
            indonesia_bbox = QgsRectangle(95.0, -11.0, 141.0, 6.0)
            dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")
            source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(
                source_crs, dest_crs, QgsProject.instance()
            )
            indonesia_bbox_transformed = transform.transform(indonesia_bbox)
            iface.mapCanvas().setExtent(indonesia_bbox_transformed)
            iface.mapCanvas().refresh()

    def _get_item_widget(self, stac_id: str) -> Optional[RasterItemWidget]:
        for i in range(self.list_layout.count()):
            widget = self.list_layout.itemAt(i).widget()
            if isinstance(widget, RasterItemWidget) and widget.asset.stac_id == stac_id:
                return widget
        return None

    def _handle_download_visual_requested(self, asset: RasterAsset):
        if not asset.visual_url:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Missing Asset",
                f"No 'visual' asset found for {asset.stac_id}.",
            )
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()
            return
        self._start_download(
            asset, "visual", asset.visual_url, asset.get_local_path("visual")
        )

    def _handle_open_visual_requested(self, asset: RasterAsset):
        layer = self._load_raster_into_qgis(
            asset.get_local_path("visual"), f"{asset.stac_id}_Visual"
        )
        if layer:
            self.iface.mapCanvas().setExtent(layer.extent())
            self.iface.mapCanvas().refresh()

    def _handle_process_ndvi_requested(
        self, asset: RasterAsset, classification_items: list
    ):
        bands_to_download = {}
        if asset.nir_url:
            bands_to_download["nir"] = (asset.nir_url, asset.get_local_path("nir"))
        if asset.red_url:
            bands_to_download["red"] = (asset.red_url, asset.get_local_path("red"))
        if asset.green_url:
            bands_to_download["green"] = (
                asset.green_url,
                asset.get_local_path("green"),
            )

        if "nir" not in bands_to_download or "red" not in bands_to_download:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Missing Assets",
                f"NIR or Red bands not found for {asset.stac_id}.",
            )
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()
            return

        self.active_operations[asset.stac_id] = {
            "expected": len(bands_to_download),
            "completed": {},
            "style": classification_items,
        }
        for band_type, (url, save_path) in bands_to_download.items():
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self._on_band_download_complete(asset.stac_id, band_type, save_path)
            else:
                self._start_download(asset, band_type, url, save_path)

    def _handle_open_ndvi_requested(self, asset: RasterAsset):
        style_dialog = NdviStyleDialog(self)
        if style_dialog.exec_() == QDialog.Accepted:
            items = style_dialog.get_classification_items()
            layer = self._load_ndvi_into_qgis_layer(
                asset.get_local_path("ndvi"), asset.stac_id, items
            )
            if layer:
                self.iface.mapCanvas().setExtent(layer.extent())
                self.iface.mapCanvas().refresh()

    def _handle_open_false_color_requested(self, asset: RasterAsset):
        path = asset.get_local_path("false_color")
        name = f"{asset.stac_id}_FalseColor"
        layer = self._load_raster_into_qgis(path, name, is_false_color=True)
        if layer:
            self.iface.mapCanvas().setExtent(layer.extent())
            self.iface.mapCanvas().refresh()

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
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Download Failed",
                f"Failed to download {band} for {stac_id}: {reply.errorString()}",
            )
            if os.path.exists(save_path):
                os.remove(save_path)
            if item_widget := self._get_item_widget(stac_id):
                item_widget.update_ui_based_on_local_files()
        else:
            if band == "visual":
                layer = self._load_raster_into_qgis(save_path, f"{stac_id}_Visual")
                if layer:
                    self.iface.mapCanvas().setExtent(layer.extent())
                    self.iface.mapCanvas().refresh()
                if item_widget := self._get_item_widget(stac_id):
                    item_widget.update_ui_based_on_local_files()
            else:
                self._on_band_download_complete(stac_id, band, save_path)
        reply.deleteLater()

    def _on_band_download_complete(self, stac_id: str, band: str, save_path: str):
        op = self.active_operations.get(stac_id)
        if not op:
            return
        op["completed"][band] = save_path
        if len(op["completed"]) == op["expected"]:
            asset = next((a for a in self.all_assets if a.stac_id == stac_id), None)
            if asset:
                self._calculate_ndvi_and_fc(asset, op["style"])
            del self.active_operations[stac_id]

    def _calculate_ndvi_and_fc(self, asset: RasterAsset, style_items: list):
        red_path = asset.get_local_path("red")
        nir_path = asset.get_local_path("nir")
        green_path = asset.get_local_path("green")
        folder_path = os.path.dirname(red_path)

        task = NdvITask(red_path, nir_path, green_path, folder_path, asset.stac_id)

        progress = QProgressDialog(
            f"Processing Rasters for {asset.stac_id}...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        task.progressChanged.connect(progress.setValue)
        task.calculationFinished.connect(
            lambda ndvi_path, fc_path: self._on_processing_finished(
                ndvi_path, fc_path, asset.stac_id, style_items
            )
        )
        task.errorOccurred.connect(lambda err: self._on_task_error(err, asset.stac_id))
        progress.canceled.connect(task.cancel)
        QgsApplication.taskManager().addTask(task)

    def _on_processing_finished(
        self, ndvi_path: str, fc_path: str, stac_id: str, style_items: list
    ):
        QgsApplication.taskManager().allTasksFinished.emit()
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Processing Complete",
            f"NDVI and False Color created for {stac_id}.",
        )

        last_layer_extent = None
        if ndvi_path:
            layer = self._load_ndvi_into_qgis_layer(ndvi_path, stac_id, style_items)
            if layer:
                last_layer_extent = layer.extent()
        if fc_path:
            layer = self._load_raster_into_qgis(
                fc_path, f"{stac_id}_FalseColor", is_false_color=True
            )
            if layer:
                last_layer_extent = layer.extent()

        if last_layer_extent:
            self.iface.mapCanvas().setExtent(last_layer_extent)
            self.iface.mapCanvas().refresh()

        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _on_task_error(self, error_msg: str, stac_id: str):
        QgsApplication.taskManager().allTasksFinished.emit()
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Critical,
            "Error",
            f"Failed to process rasters for {stac_id}: {error_msg}",
        )
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _load_raster_into_qgis(
        self, path: str, name: str, is_false_color: bool = False
    ) -> Optional[QgsRasterLayer]:
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Invalid Layer",
                f"Failed to load layer: {path}",
            )
            return None
        if is_false_color:
            renderer = QgsMultiBandColorRenderer(layer.dataProvider(), 1, 2, 3)
            layer.setRenderer(renderer)
        QgsProject.instance().addMapLayer(layer, False)
        if group := self.get_or_create_plugin_layer_group():
            group.insertLayer(0, layer)
        return layer

    def _load_ndvi_into_qgis_layer(
        self, ndvi_path: str, raster_id: str, classification_items: list
    ) -> Optional[QgsRasterLayer]:
        layer = QgsRasterLayer(ndvi_path, f"{raster_id}_NDVI")
        if not layer.isValid():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Invalid Layer",
                f"Failed to load NDVI layer from {ndvi_path}",
            )
            return None

        color_ramp = QgsColorRampShader()
        color_ramp.setColorRampType(QgsColorRampShader.Discrete)
        color_ramp.setColorRampItemList(classification_items)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(color_ramp)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

        QgsProject.instance().addMapLayer(layer, False)
        if group := self.get_or_create_plugin_layer_group():
            group.insertLayer(0, layer)
        return layer

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
            #noResultsLabel {{ color: #808080; font-size: 16px; font-style: italic; padding: 40px; }}
            #actionButton {{ background-color: white; color: #495057; border: 1px solid #DEE2E6; padding: 8px 12px; border-radius: 12px; font-weight: bold; }}
            #actionButton:hover {{ background-color: #F8F9FA; }}
            #actionButton[highlight="true"] {{ background-color: #2E4434; color: white; border: none; }}
            #actionButton[highlight="true"]:hover {{ background-color: #3D5A43; }}
            #paginationButton {{ background-color: white; color: #274423; border: 1px solid #274423; padding: 8px 16px; border-radius: 12px; }}
            #paginationButton:disabled {{ background-color: #E9ECEF; color: #6C757D; border: 1px solid #CED4DA; }}
            #pageLabel {{ color: #274423; font-size: 14px; }}
            #filterLabel {{ color: #274423; font-weight: bold; font-size: 14px; }}
            QComboBox#filterComboBox {{
                font-family: "Montserrat";
                padding: 5px;
                min-width: 120px;
            }}
        """
        self.setStyleSheet(qss)

    def closeEvent(self, event):
        try:
            self.download_network_manager.finished.disconnect()
        except TypeError:
            pass
        super().closeEvent(event)
