from typing import Optional, List, Dict, Any
import os
import re

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
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QScrollArea,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QComboBox,
    QFrame,
)
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath, QBrush, QColor
from PyQt5.QtCore import Qt, QUrl, QRectF, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..config import Config
from .base_dialog import BaseDialog
from .ndvi_style_dialog import NdviStyleDialog
from .raster_calculator_dialog import RasterCalculatorDialog
from ..core import NdviTask, FalseColorTask, RasterAsset
from ..core.database import add_basemap_global_osm
from .themed_message_box import ThemedMessageBox


class RoundedImageLabel(QLabel):
    """A custom label for displaying pixmaps with rounded corners."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.radius = 8
        self.placeholder_color = QColor(0, 0, 0, 51)
        self.setCursor(Qt.PointingHandCursor)

    def setPixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

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
    """A widget to display a single raster asset with its details and actions."""

    downloadVisualRequested = pyqtSignal(RasterAsset)
    openVisualRequested = pyqtSignal(RasterAsset)
    processNdviRequested = pyqtSignal(RasterAsset, list)
    processFalseColorRequested = pyqtSignal(RasterAsset)
    openNdviRequested = pyqtSignal(RasterAsset)
    openFalseColorRequested = pyqtSignal(RasterAsset)
    customCalculationRequested = pyqtSignal(RasterAsset, str, str, dict)
    classifyCustomRequested = pyqtSignal(str, str)
    zoomToExtentRequested = pyqtSignal(dict)

    def __init__(
        self,
        asset: RasterAsset,
        dialog: "ImageListDialog",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.asset = asset
        self.dialog = dialog
        self.setObjectName("rasterItem")
        self.setAutoFillBackground(True)
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._handle_thumbnail_loaded)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        self.thumb_label = RoundedImageLabel()
        self.thumb_label.setFixedSize(202, 148)
        self.thumb_label.clicked.connect(self._on_thumbnail_clicked)
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

    def _on_thumbnail_clicked(self):
        if self.asset.geometry:
            self.zoomToExtentRequested.emit(self.asset.geometry)

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

        self.btn_false_color = QPushButton()
        self.btn_false_color.setObjectName("actionButton")
        self.btn_false_color.clicked.connect(self._on_false_color_button_clicked)
        buttons_layout.addWidget(self.btn_false_color)

        self.btn_calculator = QPushButton("Calculator")
        self.btn_calculator.setObjectName("actionButton")
        self.btn_calculator.clicked.connect(self._on_calculator_button_clicked)
        buttons_layout.addWidget(self.btn_calculator)

        layout.addLayout(buttons_layout)
        self.custom_outputs_layout = QVBoxLayout()
        layout.addLayout(self.custom_outputs_layout)
        self.progress_bar_visual = self._create_progress_bar()
        layout.addWidget(self.progress_bar_visual)
        self.bands_progress_container = QWidget()
        bands_progress_layout = QHBoxLayout(self.bands_progress_container)
        bands_progress_layout.setContentsMargins(0, 0, 0, 0)
        bands_progress_layout.setSpacing(5)
        self.progress_bar_nir = self._create_progress_bar()
        self.progress_bar_red = self._create_progress_bar()
        self.progress_bar_green = self._create_progress_bar()
        bands_progress_layout.addWidget(self.progress_bar_nir)
        bands_progress_layout.addWidget(self.progress_bar_red)
        bands_progress_layout.addWidget(self.progress_bar_green)
        layout.addWidget(self.bands_progress_container)

        self.status_label = QLabel("")
        self.status_label.setObjectName("rasterStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        return layout

    def _on_calculator_button_clicked(self):
        available_bands = []
        if self.asset.nir_url:
            available_bands.append("nir")
        if self.asset.red_url:
            available_bands.append("red")
        if self.asset.green_url:
            available_bands.append("green")

        dialog = RasterCalculatorDialog(available_bands, self)
        if dialog.exec_() == QDialog.Accepted:
            formula, output_name, coefficients = dialog.get_calculation_details()
            self.customCalculationRequested.emit(
                self.asset, formula, output_name, coefficients
            )

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
        if self.btn_ndvi.text() == "Open NDVI":
            self.openNdviRequested.emit(self.asset)
        else:
            style_dialog = NdviStyleDialog(self)
            if style_dialog.exec_() == QDialog.Accepted:
                classification_items = style_dialog.get_classification_items()
                self.set_buttons_enabled(False)
                self.status_label.setVisible(True)
                self.status_label.setText("Downloading bands for NDVI...")
                self.bands_progress_container.setVisible(True)
                self.processNdviRequested.emit(self.asset, classification_items)

    def _on_false_color_button_clicked(self):
        if self.btn_false_color.text() == "Open False Color":
            self.openFalseColorRequested.emit(self.asset)
        else:
            self.set_buttons_enabled(False)
            self.status_label.setVisible(True)
            self.status_label.setText("Downloading bands for False Color...")
            self.bands_progress_container.setVisible(True)
            self.processFalseColorRequested.emit(self.asset)

    def set_buttons_enabled(self, enabled: bool):
        self.btn_visual.setEnabled(enabled)
        self.btn_ndvi.setEnabled(enabled)
        self.btn_false_color.setEnabled(enabled)
        self.btn_calculator.setEnabled(enabled)

    def update_download_progress(
        self, bytes_received: int, bytes_total: int, band: str
    ):
        if bytes_total > 0:
            progress = int((bytes_received / bytes_total) * 100)
            pbar = None
            if band == "visual":
                pbar = self.progress_bar_visual
            elif band == "nir":
                pbar = self.progress_bar_nir
            elif band == "red":
                pbar = self.progress_bar_red
            elif band == "green":
                pbar = self.progress_bar_green

            if pbar:
                pbar.setVisible(True)
                pbar.setValue(progress)
                pbar.setFormat(f"{band.upper()}: {progress}%")

    def update_ui_based_on_local_files(self):
        """Updates UI based on local files and checks for ongoing operations."""
        # --- 1. Set the text for all buttons unconditionally ---
        visual_path = self.asset.get_local_path("visual")
        if os.path.exists(visual_path) and os.path.getsize(visual_path) > 0:
            self.btn_visual.setText("Open Visual")
        else:
            self.btn_visual.setText("Download Visual")

        ndvi_path = self.asset.get_local_path("ndvi")
        if os.path.exists(ndvi_path) and os.path.getsize(ndvi_path) > 0:
            self.btn_ndvi.setText("Open NDVI")
        else:
            self.btn_ndvi.setText("Process NDVI")

        fc_path = self.asset.get_local_path("false_color")
        if os.path.exists(fc_path) and os.path.getsize(fc_path) > 0:
            self.btn_false_color.setText("Open False Color")
        else:
            self.btn_false_color.setText("Process False Color")

        # --- 2. Reset UI state ---
        self.progress_bar_visual.setVisible(False)
        self.bands_progress_container.setVisible(False)
        self.progress_bar_nir.setVisible(False)
        self.progress_bar_red.setVisible(False)
        self.progress_bar_green.setVisible(False)
        self.status_label.setVisible(False)
        self.set_buttons_enabled(True)

        # --- 3. Check for active operations and override UI state if necessary ---
        is_operation_active = False
        if self.dialog and hasattr(self.dialog, "active_operations"):
            for op_key in self.dialog.active_operations.keys():
                if op_key.startswith(self.asset.stac_id):
                    is_operation_active = True
                    break

        if is_operation_active:
            self.set_buttons_enabled(False)
            self.status_label.setText("Operation in progress...")
            self.status_label.setVisible(True)
        else:
            # --- 4. Set enabled state only if not in an active operation ---
            self.btn_ndvi.setEnabled(
                bool(self.asset.nir_url) and bool(self.asset.red_url)
            )
            self.btn_false_color.setEnabled(
                bool(self.asset.nir_url)
                and bool(self.asset.red_url)
                and bool(self.asset.green_url)
            )
            self.btn_calculator.setEnabled(
                bool(self.asset.nir_url) and bool(self.asset.red_url)
            )

        self._update_custom_output_buttons()

    def _update_custom_output_buttons(self):
        while self.custom_outputs_layout.count():
            child = self.custom_outputs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        folder_path = os.path.join(Config.DOWNLOAD_DIR, self.asset.stac_id)
        if not os.path.isdir(folder_path):
            return

        for filename in os.listdir(folder_path):
            if filename.startswith(f"{self.asset.stac_id}_") and filename.endswith(
                ".tif"
            ):
                if (
                    "_NDVI." in filename
                    or "_FalseColor." in filename
                    or "_Visual." in filename
                ):
                    continue
                layer_name = filename.replace(f"{self.asset.stac_id}_", "").replace(
                    ".tif", ""
                )
                layer_path = os.path.join(folder_path, filename)
                btn_layout = QHBoxLayout()
                label = QLabel(f"'{layer_name}' exists.")
                btn_classify = QPushButton("Classify")
                btn_classify.setObjectName("actionButton")
                btn_classify.clicked.connect(
                    lambda ch, ln=layer_name, lp=layer_path: self.classifyCustomRequested.emit(
                        ln, lp
                    )
                )
                btn_layout.addWidget(label)
                btn_layout.addWidget(btn_classify)
                self.custom_outputs_layout.addLayout(btn_layout)


class ImageListDialog(BaseDialog):
    """Dialog to display a list of raster assets with filtering and pagination."""

    def __init__(
        self,
        data: List[Dict[str, Any]],
        iface: QgisInterface,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.iface = iface
        self.all_assets = [RasterAsset(feature) for feature in data]
        self.filtered_assets: List[RasterAsset] = []
        self.download_network_manager = QNetworkAccessManager(self)
        self.active_operations: Dict[str, Any] = {}
        self.current_page = 1
        self.items_per_page = 5
        self.init_list_ui()
        self._apply_filters()
        add_basemap_global_osm(self.iface)

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
                "Select raster data to download or process.", objectName="pageSubtitle"
            )
        )
        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

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
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.viewport().setObjectName("scrollAreaViewport")
        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        self.list_layout = QVBoxLayout(scroll_content)
        self.list_layout.setContentsMargins(20, 20, 20, 20)
        self.list_layout.setSpacing(15)
        self.list_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        main_layout.addLayout(self._create_pagination_controls())
        self.apply_stylesheet()

    def _apply_filters(self):
        filter_text = self.cloud_filter_combo.currentText()
        if filter_text == "All":
            self.filtered_assets = self.all_assets
        elif filter_text == "0 - 10%":
            self.filtered_assets = [
                a for a in self.all_assets if 0 <= a.cloud_cover <= 10
            ]
        elif filter_text == "10 - 20%":
            self.filtered_assets = [
                a for a in self.all_assets if 10 < a.cloud_cover <= 20
            ]
        elif filter_text == "20 - 30%":
            self.filtered_assets = [
                a for a in self.all_assets if 20 < a.cloud_cover <= 30
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
            if widget := item.widget():
                widget.setParent(None)
                widget.deleteLater()

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
            item_widget = RasterItemWidget(asset, self, self.list_layout.parentWidget())
            item_widget.downloadVisualRequested.connect(
                self._handle_download_visual_requested
            )
            item_widget.openVisualRequested.connect(self._handle_open_visual_requested)
            item_widget.processNdviRequested.connect(
                self._handle_process_ndvi_requested
            )
            item_widget.processFalseColorRequested.connect(
                self._handle_process_false_color_requested
            )
            item_widget.openNdviRequested.connect(self._handle_open_ndvi_requested)
            item_widget.openFalseColorRequested.connect(
                self._handle_open_false_color_requested
            )
            item_widget.customCalculationRequested.connect(
                self._handle_custom_calculation_requested
            )
            item_widget.classifyCustomRequested.connect(
                self._handle_classify_custom_requested
            )
            item_widget.zoomToExtentRequested.connect(self._handle_zoom_to_extent)
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
        group_node = root.findGroup(Config.IDPM_PLUGIN_GROUP_NAME)
        if group_node is None:
            group_node = root.addGroup(Config.IDPM_PLUGIN_GROUP_NAME)
        return group_node

    def add_basemap_global_osm(self, iface: QgisInterface):
        layer_name = "OpenStreetMap (IDPM Basemap)"
        if not QgsProject.instance().mapLayersByName(layer_name):
            url = "type=xyz&url=https://a.tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0&cache=yes&max-age=2592000"
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

    def _zoom_to_geometry(self, geometry_dict: Optional[Dict[str, Any]]):
        """Zooms the map canvas to the extent of a given geometry dictionary."""
        if not geometry_dict or "coordinates" not in geometry_dict:
            return

        try:
            coords = geometry_dict["coordinates"][0]
            if not coords:
                return

            x_coords = [p[0] for p in coords]
            y_coords = [p[1] for p in coords]
            bbox = QgsRectangle(
                min(x_coords), min(y_coords), max(x_coords), max(y_coords)
            )

            source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            dest_crs = self.iface.mapCanvas().mapSettings().destinationCrs()

            transform = QgsCoordinateTransform(
                source_crs, dest_crs, QgsProject.instance()
            )
            bbox_transformed = transform.transform(bbox)

            self.iface.mapCanvas().setExtent(bbox_transformed)
            self.iface.mapCanvas().refresh()
        except (IndexError, TypeError, Exception) as e:
            QgsMessageLog.logMessage(
                f"Could not zoom to geometry. Error: {e}", "IDPMPlugin", Qgis.Warning
            )

    def _handle_zoom_to_extent(self, geometry_dict: dict):
        self._zoom_to_geometry(geometry_dict)

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

        op_key = f"{asset.stac_id}_visual"
        self.active_operations[op_key] = {
            "type": "visual",
            "expected": 1,
            "completed": {},
            "asset": asset,
        }
        self._start_download(
            asset, "visual", asset.visual_url, asset.get_local_path("visual"), op_key
        )

    def _handle_open_visual_requested(self, asset: RasterAsset):
        layer = self._load_raster_into_qgis(
            asset, asset.get_local_path("visual"), f"{asset.stac_id}_Visual"
        )
        if layer:
            self._zoom_to_geometry(asset.geometry)

    def _handle_process_ndvi_requested(
        self, asset: RasterAsset, classification_items: list
    ):
        bands_to_download = {}
        if asset.nir_url:
            bands_to_download["nir"] = (asset.nir_url, asset.get_local_path("nir"))
        if asset.red_url:
            bands_to_download["red"] = (asset.red_url, asset.get_local_path("red"))
        if not all(k in bands_to_download for k in ["nir", "red"]):
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Missing Assets",
                f"NIR or Red bands not found for {asset.stac_id}.",
            )
            return
        op_key = f"{asset.stac_id}_ndvi"
        self.active_operations[op_key] = {
            "type": "ndvi",
            "expected": len(bands_to_download),
            "completed": {},
            "style": classification_items,
            "asset": asset,
        }
        for band_type, (url, save_path) in bands_to_download.items():
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self._on_band_download_complete(op_key, band_type, save_path)
            else:
                self._start_download(asset, band_type, url, save_path, op_key)

    def _handle_process_false_color_requested(self, asset: RasterAsset):
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
        if not all(k in bands_to_download for k in ["nir", "red", "green"]):
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Missing Assets",
                f"NIR, Red, or Green bands not found for {asset.stac_id}.",
            )
            return
        op_key = f"{asset.stac_id}_false_color"
        self.active_operations[op_key] = {
            "type": "false_color",
            "expected": len(bands_to_download),
            "completed": {},
            "asset": asset,
        }
        for band_type, (url, save_path) in bands_to_download.items():
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self._on_band_download_complete(op_key, band_type, save_path)
            else:
                self._start_download(asset, band_type, url, save_path, op_key)

    def _handle_open_ndvi_requested(self, asset: RasterAsset):
        style_dialog = NdviStyleDialog(self)
        if style_dialog.exec_() == QDialog.Accepted:
            items = style_dialog.get_classification_items()
            layer = self._load_ndvi_into_qgis_layer(
                asset, asset.get_local_path("ndvi"), items
            )
            if layer:
                self._zoom_to_geometry(asset.geometry)

    def _handle_open_false_color_requested(self, asset: RasterAsset):
        path = asset.get_local_path("false_color")
        name = f"{asset.stac_id}_FalseColor"
        layer = self._load_raster_into_qgis(asset, path, name, is_false_color=True)
        if layer:
            self._zoom_to_geometry(asset.geometry)

    def _start_download(
        self, asset: RasterAsset, band: str, url: str, save_path: str, op_key: str
    ):
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        request = QNetworkRequest(QUrl(url))
        reply = self.download_network_manager.get(request)
        reply.setProperty("stac_id", asset.stac_id)
        reply.setProperty("band", band)
        reply.setProperty("save_path", save_path)
        reply.setProperty("op_key", op_key)
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
        op_key = reply.property("op_key")
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
            if op_key in self.active_operations:
                del self.active_operations[op_key]
            if item_widget := self._get_item_widget(stac_id):
                item_widget.update_ui_based_on_local_files()
        else:
            if op_key:
                self._on_band_download_complete(op_key, band, save_path)
        reply.deleteLater()

    def _handle_custom_calculation_requested(
        self, asset: RasterAsset, formula: str, output_name: str, coefficients: dict
    ):
        found_vars = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", formula))
        available_bands = {"nir", "red", "green", "blue"}
        required_bands = found_vars.intersection(available_bands)
        bands_to_download = {}
        for band in required_bands:
            url_attr = f"{band}_url"
            if hasattr(asset, url_attr) and getattr(asset, url_attr):
                bands_to_download[band] = (
                    getattr(asset, url_attr),
                    asset.get_local_path(band),
                )
            else:
                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Warning,
                    "Missing Band",
                    f"The asset is missing the required '{band}' band for this formula.",
                )
                return
        op_key = f"{asset.stac_id}_{output_name}"
        self.active_operations[op_key] = {
            "type": "custom",
            "expected": len(bands_to_download),
            "completed": {},
            "formula": formula,
            "output_name": output_name,
            "coefficients": coefficients,
            "asset": asset,
        }
        if item_widget := self._get_item_widget(asset.stac_id):
            item_widget.set_buttons_enabled(False)
            item_widget.status_label.setText(
                f"Downloading bands for '{output_name}'..."
            )
            item_widget.status_label.setVisible(True)
            item_widget.bands_progress_container.setVisible(True)
        for band_type, (url, save_path) in bands_to_download.items():
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self._on_band_download_complete(op_key, band_type, save_path)
            else:
                self._start_download(asset, band_type, url, save_path, op_key)

    def _on_band_download_complete(self, op_key: str, band: str, save_path: str):
        op = self.active_operations.get(op_key)
        if not op:
            return
        op["completed"][band] = save_path

        if len(op["completed"]) == op["expected"]:
            asset = op["asset"]
            if op["type"] == "visual":
                if op_key in self.active_operations:
                    del self.active_operations[op_key]
                layer = self._load_raster_into_qgis(
                    asset, save_path, f"{asset.stac_id}_Visual"
                )
                if layer:
                    self._zoom_to_geometry(asset.geometry)
                if item_widget := self._get_item_widget(asset.stac_id):
                    item_widget.update_ui_based_on_local_files()
            elif op["type"] == "custom":
                if op_key in self.active_operations:
                    del self.active_operations[op_key]
                if item_widget := self._get_item_widget(asset.stac_id):
                    item_widget.update_ui_based_on_local_files()
                self._run_custom_calculation(
                    asset,
                    op["formula"],
                    op["output_name"],
                    op["completed"],
                    op["coefficients"],
                )
            elif op["type"] == "ndvi":
                self._calculate_ndvi(asset, op["style"])
            elif op["type"] == "false_color":
                self._calculate_false_color(asset)

    def _run_custom_calculation(
        self,
        asset: RasterAsset,
        formula: str,
        output_name: str,
        band_paths: dict,
        coefficients: dict,
    ):
        folder_path = os.path.join(Config.DOWNLOAD_DIR, asset.stac_id)
        output_path = os.path.join(folder_path, f"{asset.stac_id}_{output_name}.tif")
        entries = []
        ref_layer = None
        layers_to_keep_alive = []
        for band_name, path in band_paths.items():
            layer = QgsRasterLayer(path, band_name)
            if not layer.isValid():
                self._on_task_error(
                    f"Could not load band: {band_name}", output_name, asset.stac_id
                )
                return
            layers_to_keep_alive.append(layer)
            entry = QgsRasterCalculatorEntry()
            entry.ref = f"{band_name}@1"
            entry.raster = layer
            entry.bandNumber = 1
            entries.append(entry)
            if ref_layer is None:
                ref_layer = layer
        if not ref_layer:
            self._on_task_error(
                "No valid reference layer for calculation.", output_name, asset.stac_id
            )
            return
        calc_formula = formula
        for band_name in band_paths.keys():
            calc_formula = calc_formula.replace(band_name, f'"{band_name}@1"')
        for coeff_name, coeff_value in coefficients.items():
            calc_formula = calc_formula.replace(coeff_name, str(coeff_value))
        calc = QgsRasterCalculator(
            calc_formula,
            output_path,
            "GTiff",
            ref_layer.extent(),
            ref_layer.width(),
            ref_layer.height(),
            entries,
        )
        result = calc.processCalculation()
        if result == QgsRasterCalculator.Success:
            self._on_custom_calculation_finished(
                output_path, output_name, asset.stac_id
            )
        else:
            self._on_task_error(
                f"Raster calculation failed with error code: {result}",
                output_name,
                asset.stac_id,
            )

    def _on_custom_calculation_finished(self, path: str, name: str, stac_id: str):
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Calculation Complete",
            f"Successfully created '{name}'.",
        )
        layer = self._load_raster_into_qgis(None, path, name)
        if layer:
            asset = next((a for a in self.all_assets if a.stac_id == stac_id), None)
            if asset:
                self._zoom_to_geometry(asset.geometry)
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _handle_classify_custom_requested(self, layer_name: str, layer_path: str):
        """Handles request to classify a custom raster layer."""
        style_dialog = NdviStyleDialog(self)
        if style_dialog.exec_() == QDialog.Accepted:
            items = style_dialog.get_classification_items()
            self._load_raster_into_qgis(
                None, layer_path, layer_name, classification_items=items
            )

    def _on_task_error(
        self, error_msg: str, task_name: str, stac_id: Optional[str] = None
    ):
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Critical,
            "Error",
            f"Failed to process '{task_name}': {error_msg}",
        )
        if not stac_id:
            return

        op_key_ndvi = f"{stac_id}_ndvi"
        if op_key_ndvi in self.active_operations:
            del self.active_operations[op_key_ndvi]

        op_key_fc = f"{stac_id}_false_color"
        if op_key_fc in self.active_operations:
            del self.active_operations[op_key_fc]

        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _calculate_ndvi(self, asset: RasterAsset, style_items: list):
        task = NdviTask(
            asset.get_local_path("red"),
            asset.get_local_path("nir"),
            os.path.dirname(asset.get_local_path("red")),
            asset.stac_id,
        )
        progress = QProgressDialog(
            f"Processing NDVI for {asset.stac_id}...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        task.progressChanged.connect(progress.setValue)
        task.calculationFinished.connect(
            lambda path: self._on_ndvi_processing_finished(
                path, asset.stac_id, style_items
            )
        )
        task.errorOccurred.connect(
            lambda err: self._on_task_error(err, "NDVI", asset.stac_id)
        )
        progress.canceled.connect(task.cancel)
        QgsApplication.taskManager().addTask(task)

    def _calculate_false_color(self, asset: RasterAsset):
        task = FalseColorTask(
            asset.get_local_path("nir"),
            asset.get_local_path("red"),
            asset.get_local_path("green"),
            os.path.dirname(asset.get_local_path("red")),
            asset.stac_id,
        )
        progress = QProgressDialog(
            f"Processing False Color for {asset.stac_id}...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        task.progressChanged.connect(progress.setValue)
        task.calculationFinished.connect(
            lambda path: self._on_fc_processing_finished(path, asset.stac_id)
        )
        task.errorOccurred.connect(
            lambda err: self._on_task_error(err, "False Color", asset.stac_id)
        )
        progress.canceled.connect(task.cancel)
        QgsApplication.taskManager().addTask(task)

    def _on_ndvi_processing_finished(
        self, ndvi_path: str, stac_id: str, style_items: list
    ):
        op_key = f"{stac_id}_ndvi"
        if op_key in self.active_operations:
            del self.active_operations[op_key]

        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Processing Complete",
            f"NDVI created for {stac_id}.",
        )
        asset = next((a for a in self.all_assets if a.stac_id == stac_id), None)
        if asset:
            layer = self._load_ndvi_into_qgis_layer(asset, ndvi_path, style_items)
            if layer:
                self._zoom_to_geometry(asset.geometry)

        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _on_fc_processing_finished(self, fc_path: str, stac_id: str):
        op_key = f"{stac_id}_false_color"
        if op_key in self.active_operations:
            del self.active_operations[op_key]

        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Processing Complete",
            f"False Color created for {stac_id}.",
        )
        asset = next((a for a in self.all_assets if a.stac_id == stac_id), None)
        if asset:
            layer = self._load_raster_into_qgis(
                asset, fc_path, f"{stac_id}_FalseColor", is_false_color=True
            )
            if layer:
                self._zoom_to_geometry(asset.geometry)

        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _load_raster_into_qgis(
        self,
        asset: Optional[RasterAsset],
        path: str,
        name: str,
        is_false_color: bool = False,
        classification_items: Optional[list] = None,
    ) -> Optional[QgsRasterLayer]:
        if layers := QgsProject.instance().mapLayersByName(name):
            QgsProject.instance().removeMapLayer(layers[0].id())
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Invalid Layer",
                f"Failed to load layer: {path}.",
            )
            return None
        if is_false_color:
            renderer = QgsMultiBandColorRenderer(layer.dataProvider(), 1, 2, 3)
            layer.setRenderer(renderer)
        elif classification_items:
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

    def _load_ndvi_into_qgis_layer(
        self, asset: RasterAsset, ndvi_path: str, classification_items: list
    ) -> Optional[QgsRasterLayer]:
        return self._load_raster_into_qgis(
            asset,
            ndvi_path,
            f"{asset.stac_id}_NDVI",
            classification_items=classification_items,
        )

    def apply_stylesheet(self) -> None:
        qss = """
            #mainContainer { background-color: #F8F9FA; border-radius: 20px; }
            QLabel { color: #212529; font-family: "Montserrat"; }
            #pageTitle { font-size: 28px; font-weight: bold; color: #212529; }
            #pageSubtitle { font-size: 14px; color: #808080; }
            #backButton { background-color: transparent; color: #274423; border: none; font-size: 14px; padding: 8px; }
            #backButton:hover { text-decoration: underline; }
            #minimizeButton, #maximizeButton, #closeButton {
                background-color: transparent; color: #274423; border: none;
                font-family: "Arial", sans-serif; font-weight: bold; border-radius: 4px;
            }
            #minimizeButton { font-size: 16px; padding-bottom: 5px; }
            #maximizeButton { font-size: 16px; padding-top: 1px; }
            #closeButton { font-size: 24px; padding-bottom: 2px; }
            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover { background-color: rgba(0,0,0, 0.1); }
            #rasterItem { background-color: white; border: 1px solid #E9ECEF; border-radius: 12px; }
            #rasterTitle { font-weight: bold; font-size: 16px; }
            #rasterSubtitle { color: #6C757D; font-size: 12px; }
            #rasterCloud { font-weight: bold; color: #274423; font-size: 12px; }
            #rasterStatus { font-weight: bold; font-size: 10px; color: #007BFF; }
            #noResultsLabel { color: #808080; font-size: 16px; font-style: italic; padding: 40px; }
            #actionButton { 
                background-color: white; color: #495057; border: 1px solid #CED4DA; 
                padding: 8px 12px; border-radius: 8px; font-weight: bold; 
            }
            #actionButton:hover { background-color: #F1F3F5; }
            #actionButton:disabled { background-color: #E9ECEF; color: #ADB5BD; border-color: #DEE2E6; }
            QScrollArea, #scrollAreaViewport, #scrollContent { border: none; background-color: #F8F9FA; }
            #paginationButton { background-color: white; color: #274423; border: 1px solid #274423; padding: 8px 16px; border-radius: 8px; }
            #paginationButton:disabled { background-color: #E9ECEF; color: #6C757D; border: 1px solid #CED4DA; }
            #pageLabel { color: #274423; font-size: 14px; }
            #filterLabel { color: #274423; font-weight: bold; font-size: 14px; }
            QComboBox#filterComboBox { font-family: "Montserrat"; padding: 5px; min-width: 120px; }
        """
        self.setStyleSheet(qss)

    def closeEvent(self, event):
        try:
            self.download_network_manager.finished.disconnect()
        except TypeError:
            pass
        super().closeEvent(event)
