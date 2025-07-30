import tempfile
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
    QgsGeometry,
)

from PyQt5.QtWidgets import (
    QCheckBox,
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
from PyQt5.QtCore import QSettings, QTimer, Qt, QUrl, QRectF, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..config import Config
from .base_dialog import BaseDialog
from .ndvi_style_dialog import NdviStyleDialog
from .raster_calculator_dialog import RasterCalculatorDialog
from .spinner_widget import SpinnerWidget
from .aoi_map_tool import AoiMapTool
from ..core import (
    NdviTask,
    FalseColorTask,
    RasterAsset,
    RasterCalculatorTask,
    ZonalStatsTask,
    CogAoiLoader,
    CogBandProcessor,
    QgisPluginIntegration,
    check_rasterio_installation,
)
from ..core.util import add_basemap_global_osm
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
    cancelOperationRequested = pyqtSignal(str)
    selectAoiRequested = pyqtSignal(RasterAsset)

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

        title_layout = QHBoxLayout()
        self.stac_id_label = QLabel(self.asset.stac_id)
        self.stac_id_label.setObjectName("rasterTitle")

        self.spinner_widget = SpinnerWidget(self)
        self.spinner_widget.setFixedSize(16, 16)

        title_layout.addWidget(self.stac_id_label)
        title_layout.addWidget(self.spinner_widget)
        title_layout.addStretch()

        details_layout.addStretch(1)
        details_layout.addLayout(title_layout)
        details_layout.addStretch(1)

        date_str = "N/A"
        if self.asset.capture_date:
            date_str = self.asset.capture_date.strftime("%d %b %Y %H:%M:%S")
        published_label = QLabel(f"Published on: {date_str}")
        published_label.setObjectName("rasterSubtitle")
        cloud_label = QLabel(f"Cloud Cover: {self.asset.cloud_cover:.2f}%")
        cloud_label.setObjectName("rasterCloud")

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

        self.buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(self.buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
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
        layout.addWidget(self.buttons_widget)

        self.btn_select_aoi = QPushButton("Select AOI")
        self.btn_select_aoi.setObjectName("actionButton")
        self.btn_select_aoi.clicked.connect(
            lambda: self.selectAoiRequested.emit(self.asset)
        )
        self.btn_select_aoi.setVisible(False)
        layout.addWidget(self.btn_select_aoi, 0, Qt.AlignRight)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(
            lambda: self.cancelOperationRequested.emit(self.asset.stac_id)
        )
        self.cancel_button.setVisible(False)
        layout.addWidget(self.cancel_button, 0, Qt.AlignRight)

        self.custom_outputs_container = QWidget()
        self.custom_outputs_layout = QVBoxLayout(self.custom_outputs_container)
        self.custom_outputs_layout.setContentsMargins(0, 5, 0, 0)
        self.custom_outputs_layout.setSpacing(5)
        layout.addWidget(self.custom_outputs_container)

        self.progress_bar_visual = self._create_progress_bar()
        layout.addWidget(self.progress_bar_visual)
        self.bands_progress_container = QWidget()
        bands_progress_layout = QHBoxLayout(self.bands_progress_container)
        bands_progress_layout.setContentsMargins(0, 0, 0, 0)
        bands_progress_layout.setSpacing(5)
        self.progress_bar_nir = self._create_progress_bar()
        self.progress_bar_red = self._create_progress_bar()
        self.progress_bar_green = self._create_progress_bar()
        self.progress_bar_blue = self._create_progress_bar()
        self.progress_bar_swir_b11 = self._create_progress_bar()
        self.progress_bar_swir_b12 = self._create_progress_bar()
        bands_progress_layout.addWidget(self.progress_bar_nir)
        bands_progress_layout.addWidget(self.progress_bar_red)
        bands_progress_layout.addWidget(self.progress_bar_green)
        bands_progress_layout.addWidget(self.progress_bar_blue)
        bands_progress_layout.addWidget(self.progress_bar_swir_b11)
        bands_progress_layout.addWidget(self.progress_bar_swir_b12)
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
        if self.asset.blue_url:
            available_bands.append("blue")
        if self.asset.swir_b11_url:
            available_bands.append("swir_b11")
        if self.asset.swir_b12_url:
            available_bands.append("swir_b12")

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
            self.downloadVisualRequested.emit(self.asset)

    def _on_ndvi_button_clicked(self):
        if self.btn_ndvi.text() == "Open NDVI":
            self.openNdviRequested.emit(self.asset)
        else:
            style_dialog = NdviStyleDialog(self)
            if style_dialog.exec_() == QDialog.Accepted:
                classification_items = style_dialog.get_classification_items()
                self.processNdviRequested.emit(self.asset, classification_items)

    def _on_false_color_button_clicked(self):
        if self.btn_false_color.text() == "Open False Color":
            self.openFalseColorRequested.emit(self.asset)
        else:
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
            elif band == "blue":
                pbar = self.progress_bar_blue
            elif band == "swir_b11":
                pbar = self.progress_bar_swir_b11
            elif band == "swir_b12":
                pbar = self.progress_bar_swir_b12

            if pbar:
                pbar.setVisible(True)
                pbar.setValue(progress)
                pbar.setFormat(f"{band.upper()}: {progress}%")

    def update_ui_based_on_local_files(self):
        """Updates UI based on local files and checks for ongoing operations."""
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

        # always hide the AOI button
        self.btn_select_aoi.setVisible(False)

        self.progress_bar_visual.setVisible(False)
        self.bands_progress_container.setVisible(False)
        self.progress_bar_nir.setVisible(False)
        self.progress_bar_red.setVisible(False)
        self.progress_bar_green.setVisible(False)
        self.progress_bar_blue.setVisible(False)
        self.progress_bar_swir_b11.setVisible(False)
        self.progress_bar_swir_b12.setVisible(False)
        self.status_label.setVisible(False)
        self.buttons_widget.setVisible(True)
        self.cancel_button.setVisible(False)
        self.spinner_widget.setVisible(False)
        self.set_buttons_enabled(True)
        self.custom_outputs_container.setVisible(True)

        active_op = None
        if self.dialog and hasattr(self.dialog, "active_operations"):
            for op_key, op_data in self.dialog.active_operations.items():
                if op_key.startswith(self.asset.stac_id):
                    active_op = op_data
                    break

        if active_op:
            self.buttons_widget.setVisible(False)
            self.btn_select_aoi.setVisible(False)
            self.cancel_button.setVisible(True)
            self.spinner_widget.setVisible(True)
            self.status_label.setText("Operation in progress...")
            self.status_label.setVisible(True)
            self.custom_outputs_container.setVisible(False)

            op_type = active_op.get("type")
            if op_type == "visual":
                self.progress_bar_visual.setVisible(True)
            elif op_type in ["ndvi", "false_color", "custom"]:
                self.bands_progress_container.setVisible(True)
        else:
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

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clear_layout(item.layout())

    def _update_custom_output_buttons(self):
        self._clear_layout(self.custom_outputs_layout)
        folder_path = os.path.join(Config.DOWNLOAD_DIR, self.asset.stac_id)
        if not os.path.isdir(folder_path):
            self.custom_outputs_container.setVisible(False)
            return
        has_custom_outputs = False
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
                has_custom_outputs = True
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
        self.custom_outputs_container.setVisible(has_custom_outputs)


class ImageListDialog(BaseDialog):
    """Dialog to display a list of raster assets with filtering and pagination."""

    def __init__(
        self,
        data: List[Dict[str, Any]],
        iface: QgisInterface,
        parent: Optional[QWidget] = None,
        aoi: Optional[QgsRectangle] = None,
    ):
        super().__init__(parent)
        self.aoi = aoi

        # Check if rasterio is available for AOI optimization
        if not check_rasterio_installation():
            QgsMessageLog.logMessage(
                "Rasterio not found. AOI optimization will be disabled. "
                "Install rasterio for better performance: pip install rasterio",
                "IDPMPlugin",
                Qgis.Warning,
            )
            self.rasterio_available = False
        else:
            self.rasterio_available = True
            self.cog_loader = CogAoiLoader()

        # Determine if AOI processing should be used
        self.aoi_processing_enabled = (
            self.rasterio_available and self.aoi is not None and not self.aoi.isEmpty()
        )

        # Log AOI status
        if self.aoi_processing_enabled:
            aoi_area = self.aoi.width() * self.aoi.height()
            QgsMessageLog.logMessage(
                f"ImageListDialog initialized with AOI optimization enabled. "
                f"AOI area: {aoi_area:.4f} square degrees",
                "IDPMPlugin",
                Qgis.Info,
            )
        else:
            QgsMessageLog.logMessage(
                "ImageListDialog initialized with full raster processing",
                "IDPMPlugin",
                Qgis.Info,
            )

        self.iface = iface
        self.all_assets = [RasterAsset(feature) for feature in data]
        self.filtered_assets: List[RasterAsset] = []
        self.download_network_manager = QNetworkAccessManager(self)
        self.active_operations: Dict[str, Any] = {}
        self.current_page = 1
        self.items_per_page = 5
        self.aoi_tool = None
        self.previous_map_tool = None

        self.init_list_ui()
        self._apply_filters()
        add_basemap_global_osm(self.iface, zoom=False)

    def init_list_ui(self):
        self.setWindowTitle("Citra Satelit")
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 10, 30, 30)
        top_bar = self._create_top_bar()
        main_layout.addLayout(top_bar)
        main_layout.addSpacing(20)

        header_layout = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title_vbox.addWidget(QLabel("Citra Satelit", objectName="pageTitle"))
        title_vbox.addWidget(
            QLabel(
                "Pilih citra data untuk download atau proses.",
                objectName="pageSubtitle",
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

    def _add_aoi_controls(self):
        """Add controls for AOI-based processing."""
        # Add this to your existing UI setup
        aoi_layout = QHBoxLayout()

        self.aoi_checkbox = QCheckBox("Use AOI for Downloads")
        self.aoi_checkbox.setChecked(self.aoi_processing_enabled)
        self.aoi_checkbox.toggled.connect(self._on_aoi_processing_toggled)

        self.aoi_info_label = QLabel("No AOI selected")
        self.aoi_info_label.setStyleSheet("color: #666; font-size: 11px;")

        aoi_layout.addWidget(self.aoi_checkbox)
        aoi_layout.addWidget(self.aoi_info_label)
        aoi_layout.addStretch()

        return aoi_layout

    def _apply_filters(self):
        assets_to_filter = self.all_assets

        if self.aoi:
            aoi_filtered_assets = []

            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            asset_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(
                canvas_crs, asset_crs, QgsProject.instance()
            )

            aoi_geom = QgsGeometry.fromRect(self.aoi)
            aoi_geom.transform(transform)

            for asset in assets_to_filter:
                if not asset.geometry:
                    continue

                try:
                    asset_geom = QgsGeometry.fromWkt(
                        "POLYGON(("
                        + ", ".join(
                            [f"{p[0]} {p[1]}" for p in asset.geometry["coordinates"][0]]
                        )
                        + "))"
                    )
                    if asset_geom.intersects(aoi_geom):
                        aoi_filtered_assets.append(asset)
                except Exception:
                    continue

            assets_to_filter = aoi_filtered_assets

        filter_text = self.cloud_filter_combo.currentText()
        if filter_text == "All":
            self.filtered_assets = assets_to_filter
        elif filter_text == "0 - 10%":
            self.filtered_assets = [
                a for a in assets_to_filter if 0 <= a.cloud_cover <= 10
            ]
        elif filter_text == "10 - 20%":
            self.filtered_assets = [
                a for a in assets_to_filter if 10 < a.cloud_cover <= 20
            ]
        elif filter_text == "20 - 30%":
            self.filtered_assets = [
                a for a in assets_to_filter if 20 < a.cloud_cover <= 30
            ]
        else:
            self.filtered_assets = assets_to_filter

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
        self.prev_button = QPushButton(
            "← Previous", objectName="paginationButton", cursor=Qt.PointingHandCursor
        )
        self.prev_button.clicked.connect(self.prev_page)
        self.page_label = QLabel("Page 1", objectName="pageLabel")
        self.next_button = QPushButton(
            "Next →", objectName="paginationButton", cursor=Qt.PointingHandCursor
        )
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
            item_widget.cancelOperationRequested.connect(
                self._handle_cancel_operation_requested
            )
            item_widget.selectAoiRequested.connect(self._handle_select_aoi_requested)
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

    def _on_aoi_processing_error(self, error_msg: str, asset_id: str):
        """Handle AOI processing errors."""
        try:
            # Clean up operation tracking
            op_keys_to_remove = [
                key for key in self.active_operations.keys() if key.startswith(asset_id)
            ]
            for op_key in op_keys_to_remove:
                if op_key in self.active_operations:
                    if progress := self.active_operations[op_key].get("progress"):
                        progress.close()
                    del self.active_operations[op_key]

            # Show error message
            self.iface.messageBar().pushMessage(
                "Processing Error",
                f"AOI processing failed for {asset_id}: {error_msg}",
                level=Qgis.Critical,
                duration=8,
            )

            QgsMessageLog.logMessage(
                f"AOI processing error for {asset_id}: {error_msg}",
                "IDPMPlugin",
                Qgis.Critical,
            )

            # Update UI
            if item_widget := self._get_item_widget(asset_id):
                item_widget.update_ui_based_on_local_files()

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error handling AOI processing error: {str(e)}",
                "IDPMPlugin",
                Qgis.Critical,
            )

    def set_aoi_from_menu(self, aoi_rect: QgsRectangle):
        """Set AOI from the main menu selection."""
        self.selected_aoi = aoi_rect
        if aoi_rect:
            # Calculate AOI area for display
            area_km2 = (aoi_rect.width() * aoi_rect.height()) / 1e6  # Rough conversion
            self.aoi_info_label.setText(f"AOI set (~{area_km2:.1f} km²)")
        else:
            self.aoi_info_label.setText("No AOI selected")

    def _should_use_aoi_processing(self) -> bool:
        """Check if AOI processing should be used."""
        return self.aoi_processing_enabled

    def _handle_select_aoi_requested(self, asset: RasterAsset):
        self.hide()
        self.iface.messageBar().pushMessage(
            "Info",
            "Draw a rectangle on the map to define your Area of Interest. Press ESC to cancel.",
            level=Qgis.Info,
            duration=5,
        )

        self.aoi_tool = AoiMapTool(self.iface.mapCanvas())
        self.aoi_tool.aoiSelected.connect(
            lambda rect: self._on_aoi_selected(rect, asset)
        )
        self.aoi_tool.cancelled.connect(self._on_aoi_cancelled)

        self.previous_map_tool = self.iface.mapCanvas().mapTool()
        self.iface.mapCanvas().setMapTool(self.aoi_tool)
        self.iface.mapCanvas().setFocus()

    def _on_aoi_selected(self, aoi_rect: QgsRectangle, asset: RasterAsset):
        self._restore_map_tool_and_show()

        ndvi_layer_name = f"{asset.stac_id}_NDVI"
        layers = QgsProject.instance().mapLayersByName(ndvi_layer_name)

        if not layers:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Layer Not Found",
                f"The processed NDVI layer '{ndvi_layer_name}' could not be found in the project.",
            )
            return

        ndvi_layer = layers[0]

        try:
            layer_extent_geom = QgsGeometry.fromRect(ndvi_layer.extent())
            layer_crs = ndvi_layer.crs()

            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()

            aoi_geom = QgsGeometry.fromRect(aoi_rect)
            if canvas_crs.authid() != layer_crs.authid():
                transform = QgsCoordinateTransform(
                    canvas_crs, layer_crs, QgsProject.instance()
                )
                aoi_geom.transform(transform)

            if layer_extent_geom.contains(aoi_geom):
                self._run_zonal_stats_task(ndvi_layer.source(), aoi_geom, layer_crs)
            else:
                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Warning,
                    "AOI Invalid",
                    "The selected Area of Interest is outside the raster bounds.",
                )

        except Exception as e:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Geometry Error",
                f"Could not perform AOI check: {e}",
            )

    def _run_zonal_stats_task(
        self,
        raster_path: str,
        aoi_geometry: QgsGeometry,
        aoi_crs: QgsCoordinateReferenceSystem,
    ):
        task = ZonalStatsTask(raster_path, aoi_geometry, aoi_crs)

        progress = QProgressDialog(
            "Analyzing Vegetation in AOI...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)

        task.progressChanged.connect(lambda value: progress.setValue(int(value)))
        task.calculationFinished.connect(self._on_zonal_stats_finished)
        task.errorOccurred.connect(
            lambda err: ThemedMessageBox.show_message(
                self, QMessageBox.Critical, "Analysis Error", err
            )
        )
        progress.canceled.connect(task.cancel)

        QgsApplication.taskManager().addTask(task)

    def _on_zonal_stats_finished(self, stats: dict):
        if not stats:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Analysis Result",
                "Could not calculate statistics for the selected AOI.",
            )
            return

        mean_ndvi = stats.get("mean", 0.0)

        if mean_ndvi > 0.4:
            message = f"Dense vegetation found!\n\nAverage NDVI in the selected area: {mean_ndvi:.3f}"
            ThemedMessageBox.show_message(
                self, QMessageBox.Information, "Analysis Complete", message
            )
        else:
            message = f"No dense vegetation found.\n\nAverage NDVI in the selected area: {mean_ndvi:.3f}"
            ThemedMessageBox.show_message(
                self, QMessageBox.Warning, "Analysis Complete", message
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

    # ... (rest of the file is unchanged)
    def get_or_create_plugin_layer_group(self) -> Optional[QgsLayerTreeGroup]:
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        if not root:
            return None
        group_node = root.findGroup(Config.IDPM_PLUGIN_GROUP_NAME)
        if group_node is None:
            group_node = root.addGroup(Config.IDPM_PLUGIN_GROUP_NAME)
        return group_node

    def _get_item_widget(self, stac_id: str) -> Optional[RasterItemWidget]:
        for i in range(self.list_layout.count()):
            widget = self.list_layout.itemAt(i).widget()
            if isinstance(widget, RasterItemWidget) and widget.asset.stac_id == stac_id:
                return widget
        return None

    def _zoom_to_geometry(self, geometry_dict: Optional[Dict[str, Any]]):
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

    def _handle_download_visual_requested(self, asset):
        """Modified visual download with AOI support."""
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

        # Check if AOI processing should be used
        if self._should_use_aoi_processing():
            self._download_visual_with_aoi(asset)
        else:
            # Use original download method
            self._download_visual_original(asset)

    def _download_visual_with_aoi(self, asset):
        """Download or crop visual asset to AOI with improved progress handling."""
        try:
            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            cache_dir = self._get_cache_directory(asset.stac_id)

            # Check if we have local visual file to crop from
            visual_cache_path = os.path.join(
                cache_dir, f"cropped_{os.path.basename(asset.visual_url)}"
            )

            # Skip if AOI cache already exists
            if (
                os.path.exists(visual_cache_path)
                and os.path.getsize(visual_cache_path) > 0
            ):
                QgsMessageLog.logMessage(
                    f"Using existing AOI visual cache: {os.path.basename(visual_cache_path)}",
                    "IDPMPlugin",
                    Qgis.Info,
                )
                self._load_visual_layer(asset, visual_cache_path)
                return

            # Check for local visual file first
            local_visual_path = None
            if hasattr(asset, "get_local_path"):
                try:
                    local_visual_path = asset.get_local_path("visual")
                except:
                    pass

            cropped_path = None

            if (
                local_visual_path
                and os.path.exists(local_visual_path)
                and os.path.getsize(local_visual_path) > 0
            ):
                # Crop from local file - much faster!
                QgsMessageLog.logMessage(
                    f"Cropping visual from local file: {os.path.basename(local_visual_path)}",
                    "IDPMPlugin",
                    Qgis.Info,
                )

                success = self.cog_loader.crop_local_file_to_aoi(
                    local_visual_path, self.aoi, canvas_crs, visual_cache_path
                )

                if success:
                    cropped_path = visual_cache_path
                    QgsMessageLog.logMessage(
                        "Successfully cropped visual from local file",
                        "IDPMPlugin",
                        Qgis.Info,
                    )
                else:
                    QgsMessageLog.logMessage(
                        "Failed to crop from local file, will download",
                        "IDPMPlugin",
                        Qgis.Warning,
                    )

            if not cropped_path:
                # Download from URL with progress
                QgsMessageLog.logMessage(
                    "Downloading visual from URL for AOI", "IDPMPlugin", Qgis.Info
                )

                cropped_path = self.cog_loader.load_cog_with_aoi(
                    asset.visual_url, self.aoi, canvas_crs, cache_dir=cache_dir
                )

                if cropped_path and cropped_path != visual_cache_path:
                    # Rename to consistent cache name
                    if os.path.exists(visual_cache_path):
                        os.remove(visual_cache_path)
                    os.rename(cropped_path, visual_cache_path)
                    cropped_path = visual_cache_path

            if cropped_path:
                self._load_visual_layer(asset, cropped_path)
            else:
                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Warning,
                    "Download Failed",
                    "Failed to load visual data for the specified AOI.",
                )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error downloading visual with AOI: {str(e)}",
                "IDPMPlugin",
                Qgis.Critical,
            )
            # Fallback to original method
            self._download_visual_original(asset)

    def _load_visual_layer(self, asset, file_path: str):
        """Load visual layer into QGIS with proper handling."""
        try:
            layer_name = f"{asset.stac_id}_Visual_AOI"
            layer = QgsRasterLayer(file_path, layer_name)

            if layer.isValid():
                # Add to project
                QgsProject.instance().addMapLayer(layer)

                # Zoom to AOI
                self.iface.mapCanvas().setExtent(self.aoi)
                self.iface.mapCanvas().refresh()

                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

                # Quick success message without dialog to avoid freezing
                self.iface.messageBar().pushMessage(
                    "Success",
                    f"Visual loaded ({file_size_mb:.1f} MB) - {layer_name}",
                    level=Qgis.Success,
                    duration=5,
                )

                QgsMessageLog.logMessage(
                    f"Visual layer loaded successfully: {layer_name} ({file_size_mb:.1f} MB)",
                    "IDPMPlugin",
                    Qgis.Info,
                )
            else:
                self.iface.messageBar().pushMessage(
                    "Warning",
                    f"Could not create layer from {file_path}",
                    level=Qgis.Warning,
                    duration=5,
                )

            # Update UI
            if hasattr(self, "_get_item_widget"):
                if item_widget := self._get_item_widget(asset.stac_id):
                    item_widget.update_ui_based_on_local_files()

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading visual layer: {str(e)}", "IDPMPlugin", Qgis.Critical
            )

    def _download_visual_original(self, asset):
        """Original visual download method (fallback)."""
        # Your existing _handle_download_visual_requested logic here
        op_key = f"{asset.stac_id}_visual"
        if hasattr(self, "active_operations"):
            self.active_operations[op_key] = {
                "type": "visual",
                "expected": 1,
                "completed": {},
                "asset": asset,
            }
        if hasattr(self, "_get_item_widget"):
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()

        if hasattr(self, "_start_download"):
            self._start_download(
                asset,
                "visual",
                asset.visual_url,
                asset.get_local_path("visual"),
                op_key,
            )

    def _handle_process_ndvi_requested(self, asset, classification_items: list):
        """Modified NDVI processing with AOI support."""
        if not asset.nir_url or not asset.red_url:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Missing Assets",
                f"NIR or Red bands not found for {asset.stac_id}.",
            )
            return

        if self._should_use_aoi_processing():
            self._process_ndvi_with_aoi(asset, classification_items)
        else:
            self._process_ndvi_original(asset, classification_items)

    def _process_ndvi_with_aoi(self, asset, classification_items: list = None):
        """Process NDVI using AOI-cropped bands with improved performance."""
        try:
            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            cache_dir = self._get_cache_directory(asset.stac_id)

            # Check if NDVI already exists in cache
            ndvi_output_path = os.path.join(cache_dir, f"{asset.stac_id}_ndvi_aoi.tif")
            if (
                os.path.exists(ndvi_output_path)
                and os.path.getsize(ndvi_output_path) > 0
            ):
                QgsMessageLog.logMessage(
                    f"Using existing NDVI cache: {os.path.basename(ndvi_output_path)}",
                    "IDPMPlugin",
                    Qgis.Info,
                )
                self._load_ndvi_layer(asset, ndvi_output_path)
                return

            # Validate AOI size
            aoi_area = self.aoi.width() * self.aoi.height()
            if aoi_area > 1.0:  # 1 square degree
                reply = QMessageBox.question(
                    self,
                    "Large AOI Warning",
                    f"The AOI is quite large ({aoi_area:.2f} square degrees). "
                    f"NDVI processing may take some time. Continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply != QMessageBox.Yes:
                    return

            # Initialize band processor
            band_processor = CogBandProcessor(cache_dir)

            # Get band URLs and check for local files
            band_urls = {"nir": asset.nir_url, "red": asset.red_url}

            # Get local band paths if available
            local_band_paths = self._get_local_band_paths(asset)

            # Show processing status in message bar (non-blocking)
            self.iface.messageBar().pushMessage(
                "Processing",
                f"Processing NDVI for AOI ({aoi_area:.4f}°²)...",
                level=Qgis.Info,
                duration=0,  # Duration 0 = until manually cleared
            )

            QgsMessageLog.logMessage(
                f"Starting NDVI processing for AOI. Local files available: {list(local_band_paths.keys())}",
                "IDPMPlugin",
                Qgis.Info,
            )

            # Process bands (will use local files when available)
            result_paths = band_processor.process_bands_with_aoi(
                band_urls, self.aoi, canvas_crs, asset.stac_id, local_band_paths
            )

            if "nir" in result_paths and "red" in result_paths:
                # Calculate NDVI
                QgsMessageLog.logMessage(
                    "Calculating NDVI from processed bands...", "IDPMPlugin", Qgis.Info
                )

                success = band_processor.calculate_ndvi_from_aoi_bands(
                    result_paths["nir"], result_paths["red"], ndvi_output_path
                )

                # Clear processing message
                self.iface.messageBar().clearWidgets()

                if success:
                    self._load_ndvi_layer(asset, ndvi_output_path)
                else:
                    self.iface.messageBar().pushMessage(
                        "Error",
                        "Failed to calculate NDVI from AOI bands",
                        level=Qgis.Critical,
                        duration=5,
                    )
            else:
                self.iface.messageBar().clearWidgets()
                self.iface.messageBar().pushMessage(
                    "Error",
                    "Failed to process required bands for AOI",
                    level=Qgis.Critical,
                    duration=5,
                )

        except Exception as e:
            self.iface.messageBar().clearWidgets()
            QgsMessageLog.logMessage(
                f"Error processing NDVI with AOI: {str(e)}", "IDPMPlugin", Qgis.Critical
            )
            # Fallback to original method
            self._process_ndvi_original(asset, classification_items)

    def _load_ndvi_layer(self, asset, ndvi_path: str):
        """Load NDVI layer without any styling (natural grayscale)."""
        try:
            layer_name = f"{asset.stac_id}_NDVI_AOI"
            layer = QgsRasterLayer(ndvi_path, layer_name)

            if layer.isValid():
                # Add to project without any styling
                QgsProject.instance().addMapLayer(layer)

                # Zoom to AOI
                self.iface.mapCanvas().setExtent(self.aoi)
                self.iface.mapCanvas().refresh()

                file_size_mb = os.path.getsize(ndvi_path) / (1024 * 1024)
                aoi_area = self.aoi.width() * self.aoi.height()

                # Success message in message bar (non-blocking)
                self.iface.messageBar().pushMessage(
                    "Success",
                    f"NDVI processed ({file_size_mb:.1f} MB, {aoi_area:.4f}°²) - {layer_name}",
                    level=Qgis.Success,
                    duration=8,
                )

                QgsMessageLog.logMessage(
                    f"NDVI layer loaded successfully: {layer_name} ({file_size_mb:.1f} MB)",
                    "IDPMPlugin",
                    Qgis.Info,
                )
            else:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Could not create NDVI layer from {ndvi_path}",
                    level=Qgis.Critical,
                    duration=5,
                )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading NDVI layer: {str(e)}", "IDPMPlugin", Qgis.Critical
            )

    def _apply_default_ndvi_styling(self, layer: QgsRasterLayer):
        """Apply simple default NDVI styling without user dialog."""
        try:
            # Create simple NDVI color ramp
            shader = QgsRasterShader()
            color_ramp = QgsColorRampShader()
            color_ramp.setColorRampType(QgsColorRampShader.Interpolated)

            # Default NDVI color scheme
            ramp_items = [
                QgsColorRampShader.ColorRampItem(
                    -1.0, QColor(165, 0, 38), "-1.0"
                ),  # Dark red
                QgsColorRampShader.ColorRampItem(
                    -0.2, QColor(215, 48, 39), "-0.2"
                ),  # Red
                QgsColorRampShader.ColorRampItem(
                    0.0, QColor(254, 224, 139), "0.0"
                ),  # Yellow
                QgsColorRampShader.ColorRampItem(
                    0.2, QColor(217, 239, 139), "0.2"
                ),  # Light green
                QgsColorRampShader.ColorRampItem(
                    0.4, QColor(166, 217, 106), "0.4"
                ),  # Green
                QgsColorRampShader.ColorRampItem(
                    0.6, QColor(102, 189, 99), "0.6"
                ),  # Dark green
                QgsColorRampShader.ColorRampItem(
                    1.0, QColor(26, 152, 80), "1.0"
                ),  # Very dark green
            ]

            color_ramp.setColorRampItemList(ramp_items)
            shader.setRasterShaderFunction(color_ramp)

            # Apply renderer
            renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

            QgsMessageLog.logMessage(
                "Applied default NDVI styling", "IDPMPlugin", Qgis.Info
            )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error applying NDVI styling: {str(e)}", "IDPMPlugin", Qgis.Warning
            )

    def _process_ndvi_original(self, asset, classification_items: list):
        """Original NDVI processing method (fallback)."""
        # Your existing _handle_process_ndvi_requested logic here
        bands_to_download = {}
        if asset.nir_url:
            bands_to_download["nir"] = (asset.nir_url, asset.get_local_path("nir"))
        if asset.red_url:
            bands_to_download["red"] = (asset.red_url, asset.get_local_path("red"))

        op_key = f"{asset.stac_id}_ndvi"
        if hasattr(self, "active_operations"):
            self.active_operations[op_key] = {
                "type": "ndvi",
                "expected": len(bands_to_download),
                "completed": {},
                "style": classification_items,
                "asset": asset,
            }

        if hasattr(self, "_get_item_widget"):
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()

        if hasattr(self, "_start_download"):
            for band_type, (url, save_path) in bands_to_download.items():
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    if hasattr(self, "_on_band_download_complete"):
                        self._on_band_download_complete(op_key, band_type, save_path)
                else:
                    self._start_download(asset, band_type, url, save_path, op_key)

    def _handle_process_false_color_requested(self, asset):
        """Modified False Color processing with AOI support."""
        required_bands = ["nir", "red", "green"]
        band_urls = {}

        if asset.nir_url:
            band_urls["nir"] = asset.nir_url
        if asset.red_url:
            band_urls["red"] = asset.red_url
        if asset.green_url:
            band_urls["green"] = asset.green_url

        if not all(band in band_urls for band in required_bands):
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Missing Assets",
                f"NIR, Red, or Green bands not found for {asset.stac_id}.",
            )
            return

        if self._should_use_aoi_processing():
            self._process_false_color_with_aoi(asset, band_urls)
        else:
            self._process_false_color_original(asset)

    def _process_false_color_with_aoi(self, asset, band_urls: Dict[str, str]):
        """Process False Color composite using AOI-cropped bands with improved performance."""
        try:
            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            cache_dir = self._get_cache_directory(asset.stac_id)

            # Check if False Color already exists in cache
            fc_output_path = os.path.join(
                cache_dir, f"{asset.stac_id}_falsecolor_aoi.tif"
            )
            if os.path.exists(fc_output_path) and os.path.getsize(fc_output_path) > 0:
                QgsMessageLog.logMessage(
                    f"Using existing False Color cache: {os.path.basename(fc_output_path)}",
                    "IDPMPlugin",
                    Qgis.Info,
                )
                self._load_false_color_layer(asset, fc_output_path)
                return

            # Initialize band processor
            band_processor = CogBandProcessor(cache_dir)

            # Get local band paths if available
            local_band_paths = self._get_local_band_paths(asset)

            # Show processing status in message bar (non-blocking)
            aoi_area = self.aoi.width() * self.aoi.height()
            self.iface.messageBar().pushMessage(
                "Processing",
                f"Processing False Color for AOI ({aoi_area:.4f}°²)...",
                level=Qgis.Info,
                duration=0,  # Duration 0 = until manually cleared
            )

            QgsMessageLog.logMessage(
                f"Starting False Color processing for AOI. Local files available: {list(local_band_paths.keys())}",
                "IDPMPlugin",
                Qgis.Info,
            )

            # Process bands (will use local files when available)
            result_paths = band_processor.process_bands_with_aoi(
                band_urls, self.aoi, canvas_crs, asset.stac_id, local_band_paths
            )

            if all(band in result_paths for band in ["nir", "red", "green"]):
                # Create False Color composite
                QgsMessageLog.logMessage(
                    "Creating False Color composite from processed bands...",
                    "IDPMPlugin",
                    Qgis.Info,
                )

                success = band_processor.calculate_false_color_composite(
                    result_paths["nir"],
                    result_paths["red"],
                    result_paths["green"],
                    fc_output_path,
                )

                # Clear processing message
                self.iface.messageBar().clearWidgets()

                if success:
                    self._load_false_color_layer(asset, fc_output_path)
                else:
                    self.iface.messageBar().pushMessage(
                        "Error",
                        "Failed to create False Color composite",
                        level=Qgis.Critical,
                        duration=5,
                    )
            else:
                self.iface.messageBar().clearWidgets()
                missing_bands = [
                    band for band in ["nir", "red", "green"] if band not in result_paths
                ]
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Failed to process bands: {', '.join(missing_bands)}",
                    level=Qgis.Critical,
                    duration=5,
                )

        except Exception as e:
            self.iface.messageBar().clearWidgets()
            QgsMessageLog.logMessage(
                f"Error processing False Color with AOI: {str(e)}",
                "IDPMPlugin",
                Qgis.Critical,
            )
            # Fallback to original method
            self._process_false_color_original(asset)

    def _load_false_color_layer(self, asset, fc_path: str):
        """Load False Color layer into QGIS."""
        try:
            layer_name = f"{asset.stac_id}_FalseColor_AOI"
            layer = QgsRasterLayer(fc_path, layer_name)

            if layer.isValid():
                # Add to project
                QgsProject.instance().addMapLayer(layer)

                # Zoom to AOI
                self.iface.mapCanvas().setExtent(self.aoi)
                self.iface.mapCanvas().refresh()

                file_size_mb = os.path.getsize(fc_path) / (1024 * 1024)
                aoi_area = self.aoi.width() * self.aoi.height()

                # Success message in message bar (non-blocking)
                self.iface.messageBar().pushMessage(
                    "Success",
                    f"False Color processed ({file_size_mb:.1f} MB, {aoi_area:.4f}°²) - {layer_name}",
                    level=Qgis.Success,
                    duration=8,
                )

                QgsMessageLog.logMessage(
                    f"False Color layer loaded successfully: {layer_name} ({file_size_mb:.1f} MB)",
                    "IDPMPlugin",
                    Qgis.Info,
                )
            else:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Could not create False Color layer from {fc_path}",
                    level=Qgis.Critical,
                    duration=5,
                )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading False Color layer: {str(e)}",
                "IDPMPlugin",
                Qgis.Critical,
            )

    def _process_false_color_original(self, asset):
        """Original False Color processing method (fallback)."""
        # Your existing _handle_process_false_color_requested logic here
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

        op_key = f"{asset.stac_id}_false_color"
        if hasattr(self, "active_operations"):
            self.active_operations[op_key] = {
                "type": "false_color",
                "expected": len(bands_to_download),
                "completed": {},
                "asset": asset,
            }

        if hasattr(self, "_get_item_widget"):
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()

        if hasattr(self, "_start_download"):
            for band_type, (url, save_path) in bands_to_download.items():
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    if hasattr(self, "_on_band_download_complete"):
                        self._on_band_download_complete(op_key, band_type, save_path)
                else:
                    self._start_download(asset, band_type, url, save_path, op_key)

    def _handle_open_visual_requested(self, asset):
        """Enhanced to prioritize AOI-processed version if available."""
        # Check AOI cache first
        if self._should_use_aoi_processing():
            cache_dir = self._get_cache_directory(asset.stac_id)
            aoi_visual_path = os.path.join(
                cache_dir, f"cropped_{os.path.basename(asset.visual_url)}"
            )

            if os.path.exists(aoi_visual_path) and os.path.getsize(aoi_visual_path) > 0:
                self._load_visual_layer(asset, aoi_visual_path)
                return

        # Check if local visual file exists
        if hasattr(asset, "get_local_path"):
            try:
                local_visual_path = asset.get_local_path("visual")
                if (
                    local_visual_path
                    and os.path.exists(local_visual_path)
                    and os.path.getsize(local_visual_path) > 0
                ):
                    # If AOI is selected, crop from local file
                    if self._should_use_aoi_processing():
                        cache_dir = self._get_cache_directory(asset.stac_id)
                        aoi_visual_path = os.path.join(
                            cache_dir, f"cropped_{os.path.basename(asset.visual_url)}"
                        )

                        # Show quick processing status
                        self.iface.messageBar().pushMessage(
                            "Processing",
                            "Cropping visual to AOI from local file...",
                            level=Qgis.Info,
                            duration=3,
                        )

                        canvas_crs = (
                            self.iface.mapCanvas().mapSettings().destinationCrs()
                        )
                        success = self.cog_loader.crop_local_file_to_aoi(
                            local_visual_path, self.aoi, canvas_crs, aoi_visual_path
                        )

                        if success:
                            self._load_visual_layer(asset, aoi_visual_path)
                            return
                    else:
                        # Load full local file
                        layer_name = f"{asset.stac_id}_Visual"
                        layer = QgsRasterLayer(local_visual_path, layer_name)
                        if layer.isValid():
                            QgsProject.instance().addMapLayer(layer)
                            if hasattr(asset, "geometry") and asset.geometry:
                                if hasattr(self, "_zoom_to_geometry"):
                                    self._zoom_to_geometry(asset.geometry)

                            file_size_mb = os.path.getsize(local_visual_path) / (
                                1024 * 1024
                            )
                            self.iface.messageBar().pushMessage(
                                "Success",
                                f"Visual opened ({file_size_mb:.1f} MB) - {layer_name}",
                                level=Qgis.Success,
                                duration=5,
                            )
                            return
            except:
                pass

        # No visual data available
        self.iface.messageBar().pushMessage(
            "Info",
            f"No visual data available for {asset.stac_id}. Download first.",
            level=Qgis.Info,
            duration=5,
        )

    def _handle_open_ndvi_requested(self, asset):
        """Enhanced to prioritize AOI-processed NDVI if available."""
        # Check AOI cache first
        if self._should_use_aoi_processing():
            cache_dir = self._get_cache_directory(asset.stac_id)
            aoi_ndvi_path = os.path.join(cache_dir, f"{asset.stac_id}_ndvi_aoi.tif")

            if os.path.exists(aoi_ndvi_path) and os.path.getsize(aoi_ndvi_path) > 0:
                self._load_ndvi_layer(asset, aoi_ndvi_path)
                return

        # Check for full NDVI file
        if hasattr(asset, "get_local_path"):
            try:
                full_ndvi_path = asset.get_local_path("ndvi")
                if (
                    full_ndvi_path
                    and os.path.exists(full_ndvi_path)
                    and os.path.getsize(full_ndvi_path) > 0
                ):
                    # Load full NDVI without styling (natural grayscale)
                    layer_name = f"{asset.stac_id}_NDVI"
                    layer = QgsRasterLayer(full_ndvi_path, layer_name)
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)

                        if hasattr(asset, "geometry") and asset.geometry:
                            if hasattr(self, "_zoom_to_geometry"):
                                self._zoom_to_geometry(asset.geometry)

                        file_size_mb = os.path.getsize(full_ndvi_path) / (1024 * 1024)
                        self.iface.messageBar().pushMessage(
                            "Success",
                            f"NDVI opened ({file_size_mb:.1f} MB) - {layer_name}",
                            level=Qgis.Success,
                            duration=5,
                        )
                        return
            except:
                pass

        # No NDVI data available
        self.iface.messageBar().pushMessage(
            "Info",
            f"No NDVI data available for {asset.stac_id}. Process NDVI first.",
            level=Qgis.Info,
            duration=5,
        )

    def _handle_open_false_color_requested(self, asset):
        """Enhanced to prioritize AOI-processed False Color if available."""
        # Check AOI cache first
        if self._should_use_aoi_processing():
            cache_dir = self._get_cache_directory(asset.stac_id)
            aoi_fc_path = os.path.join(cache_dir, f"{asset.stac_id}_falsecolor_aoi.tif")

            if os.path.exists(aoi_fc_path) and os.path.getsize(aoi_fc_path) > 0:
                self._load_false_color_layer(asset, aoi_fc_path)
                return

        # Check for full False Color file
        if hasattr(asset, "get_local_path"):
            try:
                full_fc_path = asset.get_local_path("false_color")
                if (
                    full_fc_path
                    and os.path.exists(full_fc_path)
                    and os.path.getsize(full_fc_path) > 0
                ):
                    # Load full False Color
                    layer_name = f"{asset.stac_id}_FalseColor"
                    layer = QgsRasterLayer(full_fc_path, layer_name)
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)

                        if hasattr(asset, "geometry") and asset.geometry:
                            if hasattr(self, "_zoom_to_geometry"):
                                self._zoom_to_geometry(asset.geometry)

                        file_size_mb = os.path.getsize(full_fc_path) / (1024 * 1024)
                        self.iface.messageBar().pushMessage(
                            "Success",
                            f"False Color opened ({file_size_mb:.1f} MB) - {layer_name}",
                            level=Qgis.Success,
                            duration=5,
                        )
                        return
            except:
                pass

        # No False Color data available
        self.iface.messageBar().pushMessage(
            "Info",
            f"No False Color data available for {asset.stac_id}. Process False Color first.",
            level=Qgis.Info,
            duration=5,
        )

    def _handle_custom_calculation_requested(
        self, asset, formula: str, output_name: str, coefficients: dict
    ):
        """
        Main entry point for custom calculations with AOI support.
        """
        if self._should_use_aoi_processing():
            self._handle_custom_calculation_with_aoi(
                asset, formula, output_name, coefficients
            )
        else:
            self._handle_custom_calculation_original(
                asset, formula, output_name, coefficients
            )

    def _handle_custom_calculation_with_aoi(
        self, asset, formula: str, output_name: str, coefficients: dict
    ):
        """Handle custom calculation using AOI-cropped bands with improved performance."""
        try:
            import re

            # Find required bands from formula
            found_vars = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", formula))
            available_bands = {"nir", "red", "green", "blue", "swir_b11", "swir_b12"}
            required_bands = found_vars.intersection(available_bands)

            if not required_bands:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"No valid band names found in formula: {formula}",
                    level=Qgis.Critical,
                    duration=8,
                )
                return

            # Prepare band URLs - check that asset has all required bands
            band_urls = {}
            missing_bands = []

            for band in required_bands:
                url_attr = f"{band}_url"
                if hasattr(asset, url_attr) and getattr(asset, url_attr):
                    band_urls[band] = getattr(asset, url_attr)
                else:
                    missing_bands.append(band)

            if missing_bands:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Missing required bands: {', '.join(missing_bands)}",
                    level=Qgis.Critical,
                    duration=8,
                )
                return

            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            cache_dir = self._get_cache_directory(asset.stac_id)

            # Check if custom calculation already exists in cache
            output_path = os.path.join(
                cache_dir, f"{asset.stac_id}_{output_name}_aoi.tif"
            )
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                QgsMessageLog.logMessage(
                    f"Using existing {output_name} cache: {os.path.basename(output_path)}",
                    "IDPMPlugin",
                    Qgis.Info,
                )
                self._load_custom_calculation_layer(
                    asset, output_path, output_name, formula
                )
                return

            # Initialize band processor
            band_processor = CogBandProcessor(cache_dir)

            # Get local band paths if available
            local_band_paths = self._get_local_band_paths(asset)

            # Show processing status in message bar (non-blocking)
            aoi_area = self.aoi.width() * self.aoi.height()
            self.iface.messageBar().pushMessage(
                "Processing",
                f"Processing {output_name} for AOI ({aoi_area:.4f}°²)...",
                level=Qgis.Info,
                duration=0,
            )

            QgsMessageLog.logMessage(
                f"Starting {output_name} calculation for AOI. Local files available: {list(local_band_paths.keys())}",
                "IDPMPlugin",
                Qgis.Info,
            )

            # Process bands (will use local files when available)
            result_paths = band_processor.process_bands_with_aoi(
                band_urls, self.aoi, canvas_crs, asset.stac_id, local_band_paths
            )

            # Check if all required bands were successfully processed
            failed_bands = [band for band in required_bands if band not in result_paths]
            if failed_bands:
                self.iface.messageBar().clearWidgets()
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Failed to process bands: {', '.join(failed_bands)}",
                    level=Qgis.Critical,
                    duration=5,
                )
                return

            # Calculate custom index
            QgsMessageLog.logMessage(
                f"Calculating {output_name} from processed bands...",
                "IDPMPlugin",
                Qgis.Info,
            )

            # Apply coefficients if provided
            effective_coefficients = coefficients if coefficients else {}

            success = band_processor.calculate_custom_index(
                result_paths, formula, output_path, effective_coefficients
            )

            # Clear processing message
            self.iface.messageBar().clearWidgets()

            if success and os.path.exists(output_path):
                self._load_custom_calculation_layer(
                    asset, output_path, output_name, formula
                )
            else:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Failed to calculate {output_name}",
                    level=Qgis.Critical,
                    duration=5,
                )

        except Exception as e:
            self.iface.messageBar().clearWidgets()
            QgsMessageLog.logMessage(
                f"Error processing custom calculation with AOI: {str(e)}",
                "IDPMPlugin",
                Qgis.Critical,
            )
            # Fallback to original method if AOI processing fails
            self._handle_custom_calculation_original(
                asset, formula, output_name, coefficients
            )

    def _load_custom_calculation_layer(
        self, asset, file_path: str, output_name: str, formula: str
    ):
        """Load custom calculation layer into QGIS."""
        try:
            layer_name = f"{asset.stac_id}_{output_name}_AOI"
            layer = QgsRasterLayer(file_path, layer_name)

            if layer.isValid():
                # Add to project
                QgsProject.instance().addMapLayer(layer)

                # Zoom to AOI
                self.iface.mapCanvas().setExtent(self.aoi)
                self.iface.mapCanvas().refresh()

                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                aoi_area = self.aoi.width() * self.aoi.height()

                # Success message in message bar (non-blocking)
                self.iface.messageBar().pushMessage(
                    "Success",
                    f"{output_name} calculated ({file_size_mb:.1f} MB, {aoi_area:.4f}°²) - {layer_name}",
                    level=Qgis.Success,
                    duration=8,
                )

                QgsMessageLog.logMessage(
                    f"Custom calculation layer loaded: {layer_name} ({file_size_mb:.1f} MB) - Formula: {formula}",
                    "IDPMPlugin",
                    Qgis.Info,
                )
            else:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"Could not create layer for {output_name}",
                    level=Qgis.Critical,
                    duration=5,
                )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading custom calculation layer: {str(e)}",
                "IDPMPlugin",
                Qgis.Critical,
            )

    def _handle_custom_calculation_original(
        self, asset, formula: str, output_name: str, coefficients: dict
    ):
        """
        Original custom calculation method (fallback for when AOI is not used or fails).
        """
        found_vars = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", formula))
        available_bands = {"nir", "red", "green", "blue", "swir_b11", "swir_b12"}
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
            item_widget.update_ui_based_on_local_files()
        for band_type, (url, save_path) in bands_to_download.items():
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self._on_band_download_complete(op_key, band_type, save_path)
            else:
                self._start_download(asset, band_type, url, save_path, op_key)

    def _start_download(
        self, asset: RasterAsset, band: str, url: str, save_path: str, op_key: str
    ):
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        request = QNetworkRequest(QUrl(url))
        reply = self.download_network_manager.get(request)
        if op_key in self.active_operations:
            self.active_operations[op_key]["replies"] = self.active_operations[
                op_key
            ].get("replies", [])
            self.active_operations[op_key]["replies"].append(reply)
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
        if not reply:
            return
        stac_id = reply.property("stac_id")
        band = reply.property("band")
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_download_progress(bytes_received, bytes_total, band)

    def _on_download_finished(self, reply: QNetworkReply):
        if not reply:
            return
        stac_id = reply.property("stac_id")
        band = reply.property("band")
        save_path = reply.property("save_path")
        op_key = reply.property("op_key")
        if file_handle := reply.property("file_handle"):
            file_handle.close()
        if reply.error() == QNetworkReply.OperationCanceledError:
            QgsMessageLog.logMessage(
                f"Download canceled for {band} of {stac_id}", "IDPMPlugin", Qgis.Info
            )
            if os.path.exists(save_path):
                os.remove(save_path)
        elif reply.error() != QNetworkReply.NoError:
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

    # Hook into your existing band download completion workflow
    def _on_band_download_complete(self, op_key: str, band: str, save_path: str):
        """
        Enhanced version of your existing _on_band_download_complete method
        to handle custom calculations.
        """
        op = self.active_operations.get(op_key)
        if not op:
            return

        # Mark this band as completed
        op["completed"][band] = save_path

        QgsMessageLog.logMessage(
            f"Band {band} download complete for {op_key}. Progress: {len(op['completed'])}/{op['expected']}",
            "IDPMPlugin",
            Qgis.Info,
        )

        # Check if all bands are downloaded
        if len(op["completed"]) == op["expected"]:
            asset = op["asset"]

            if op["type"] == "custom":
                # Handle custom calculation completion
                self._process_custom_calculation_from_bands(
                    asset,
                    op["completed"],
                    op["formula"],
                    op["output_name"],
                    op["coefficients"],
                )
            elif op["type"] == "ndvi":
                self._calculate_ndvi(asset, op["style"])
            elif op["type"] == "false_color":
                self._calculate_false_color(asset)
            elif op["type"] == "visual":
                layer = self._load_raster_into_qgis(
                    asset, save_path, f"{asset.stac_id}_Visual"
                )
                if layer:
                    self._zoom_to_geometry(asset.geometry)
                if item_widget := self._get_item_widget(asset.stac_id):
                    item_widget.update_ui_based_on_local_files()

            # Clean up operation
            if op_key in self.active_operations:
                del self.active_operations[op_key]

            # Update UI
            if item_widget := self._get_item_widget(asset.stac_id):
                item_widget.update_ui_based_on_local_files()

    def _process_custom_calculation_from_bands(
        self,
        asset: RasterAsset,
        band_paths: Dict[str, str],
        formula: str,
        output_name: str,
        coefficients: dict,
    ):
        """
        Process custom calculation from downloaded full raster bands.
        This integrates with your existing full-raster workflow.
        """
        try:
            # Create output path
            output_dir = os.path.dirname(
                list(band_paths.values())[0]
            )  # Use same dir as downloaded bands
            output_path = os.path.join(output_dir, f"{asset.stac_id}_{output_name}.tif")

            # Use rasterio processor for calculation (but with full rasters)
            cache_dir = self._get_cache_directory(asset.stac_id)
            band_processor = CogBandProcessor(cache_dir)

            # Calculate custom index using full raster bands
            success = band_processor.calculate_custom_index(
                band_paths, formula, output_path, coefficients
            )

            if success and os.path.exists(output_path):
                # Load result layer
                layer_name = f"{asset.stac_id}_{output_name}"
                layer = self._load_raster_into_qgis(asset, output_path, layer_name)

                if layer:
                    # Zoom to full geometry (not AOI since this is full raster)
                    if hasattr(asset, "geometry") and asset.geometry:
                        self._zoom_to_geometry(asset.geometry)

                    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

                    ThemedMessageBox.show_message(
                        self,
                        QMessageBox.Information,
                        "Calculation Complete",
                        f"Custom calculation '{output_name}' completed!\n\n"
                        f"Formula: {formula}\n"
                        f"Output size: {file_size_mb:.1f} MB\n"
                        f"Layer: {layer_name}",
                    )
                else:
                    ThemedMessageBox.show_message(
                        self,
                        QMessageBox.Warning,
                        "Layer Creation Failed",
                        f"Calculation completed but failed to create layer.\nResult: {output_path}",
                    )
            else:
                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Warning,
                    "Calculation Failed",
                    f"Failed to calculate '{output_name}' using formula: {formula}",
                )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error processing custom calculation from bands: {str(e)}",
                "IDPMPlugin",
                Qgis.Critical,
            )
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Processing Error",
                f"Error during custom calculation: {str(e)}",
            )

    # Additional utility methods for cache management
    def _cleanup_old_cache_files(self, max_age_hours: int = 24):
        """Clean up old cache files to manage disk space."""
        try:
            import time

            settings = QSettings()
            cache_base = settings.value("IDPMPlugin/cache_dir", tempfile.gettempdir())
            cache_root = os.path.join(cache_base, "idpm_aoi_cache")

            if not os.path.exists(cache_root):
                return

            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for root, dirs, files in os.walk(cache_root):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            QgsMessageLog.logMessage(
                                f"Removed old cache file: {file}",
                                "IDPMPlugin",
                                Qgis.Info,
                            )
                    except Exception as e:
                        QgsMessageLog.logMessage(
                            f"Error removing cache file {file}: {str(e)}",
                            "IDPMPlugin",
                            Qgis.Warning,
                        )

            # Remove empty directories
            for root, dirs, files in os.walk(cache_root, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Directory is empty
                            os.rmdir(dir_path)
                    except:
                        pass

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error during cache cleanup: {str(e)}", "IDPMPlugin", Qgis.Warning
            )

    def _get_cache_size_info(self) -> Dict[str, float]:
        """Get information about cache usage."""
        try:
            settings = QSettings()
            cache_base = settings.value("IDPMPlugin/cache_dir", tempfile.gettempdir())
            cache_root = os.path.join(cache_base, "idpm_aoi_cache")

            if not os.path.exists(cache_root):
                return {"total_size_mb": 0, "file_count": 0}

            total_size = 0
            file_count = 0

            for root, dirs, files in os.walk(cache_root):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                    except:
                        pass

            return {
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": file_count,
            }

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error getting cache info: {str(e)}", "IDPMPlugin", Qgis.Warning
            )
            return {"total_size_mb": 0, "file_count": 0}

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
        op_key = f"{asset.stac_id}_{output_name}"
        task = RasterCalculatorTask(
            formula, band_paths, coefficients, output_path, asset.stac_id
        )
        if op_key in self.active_operations:
            self.active_operations[op_key]["task"] = task
        progress = QProgressDialog(
            f"Calculating '{output_name}' for {asset.stac_id}...",
            "Cancel",
            0,
            100,
            self,
        )
        progress.setWindowModality(Qt.WindowModal)
        task.progressChanged.connect(lambda value: progress.setValue(int(value)))
        task.calculationFinished.connect(self._on_custom_calculation_finished)
        task.errorOccurred.connect(self._on_task_error)
        progress.canceled.connect(task.cancel)
        QgsApplication.taskManager().addTask(task)

    def _on_custom_calculation_finished(self, path: str, name: str, stac_id: str):
        op_key = f"{stac_id}_{name}"
        if op_key in self.active_operations:
            del self.active_operations[op_key]
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Calculation Complete",
            f"Successfully created '{name}'.",
        )
        asset = next((a for a in self.all_assets if a.stac_id == stac_id), None)
        layer = self._load_raster_into_qgis(asset, path, name)
        if layer and asset:
            self._zoom_to_geometry(asset.geometry)
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _handle_classify_custom_requested(self, layer_name: str, layer_path: str):
        style_dialog = NdviStyleDialog(self)
        if style_dialog.exec_() == QDialog.Accepted:
            items = style_dialog.get_classification_items()
            self._load_raster_into_qgis(
                None, layer_path, layer_name, classification_items=items
            )

    def _handle_cancel_operation_requested(self, stac_id: str):
        op_key_to_cancel = None
        for key in self.active_operations:
            if key.startswith(stac_id):
                op_key_to_cancel = key
                break
        if op_key_to_cancel and op_key_to_cancel in self.active_operations:
            op = self.active_operations[op_key_to_cancel]
            if "replies" in op:
                for reply in op["replies"]:
                    if reply.isRunning():
                        reply.abort()
            if "task" in op and op["task"]:
                op["task"].cancel()
            del self.active_operations[op_key_to_cancel]
            if widget := self._get_item_widget(stac_id):
                widget.update_ui_based_on_local_files()
            QgsMessageLog.logMessage(
                f"Operation {op_key_to_cancel} cancelled by user.",
                "IDPMPlugin",
                Qgis.Info,
            )

    def _on_task_error(self, error_msg: str, stac_id: str):
        ThemedMessageBox.show_message(
            self, QMessageBox.Critical, "Processing Error", error_msg
        )
        keys_to_remove = [
            key for key in self.active_operations if key.startswith(stac_id)
        ]
        for key in keys_to_remove:
            del self.active_operations[key]
        if item_widget := self._get_item_widget(stac_id):
            item_widget.update_ui_based_on_local_files()

    def _calculate_ndvi(self, asset: RasterAsset, style_items: list):
        op_key = f"{asset.stac_id}_ndvi"
        task = NdviTask(
            asset.get_local_path("red"),
            asset.get_local_path("nir"),
            os.path.dirname(asset.get_local_path("red")),
            asset.stac_id,
        )
        if op_key in self.active_operations:
            self.active_operations[op_key]["task"] = task
        progress = QProgressDialog(
            f"Processing NDVI for {asset.stac_id}...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        task.progressChanged.connect(lambda value: progress.setValue(int(value)))
        task.calculationFinished.connect(
            lambda path: self._on_ndvi_processing_finished(
                path, asset.stac_id, style_items
            )
        )
        task.errorOccurred.connect(lambda err: self._on_task_error(err, asset.stac_id))
        progress.canceled.connect(task.cancel)
        QgsApplication.taskManager().addTask(task)

    def _calculate_false_color(self, asset: RasterAsset):
        op_key = f"{asset.stac_id}_false_color"
        task = FalseColorTask(
            asset.get_local_path("nir"),
            asset.get_local_path("red"),
            asset.get_local_path("green"),
            os.path.dirname(asset.get_local_path("red")),
            asset.stac_id,
        )
        if op_key in self.active_operations:
            self.active_operations[op_key]["task"] = task
        progress = QProgressDialog(
            f"Processing False Color for {asset.stac_id}...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModal)
        task.progressChanged.connect(lambda value: progress.setValue(int(value)))
        task.calculationFinished.connect(
            lambda path: self._on_fc_processing_finished(path, asset.stac_id)
        )
        task.errorOccurred.connect(lambda err: self._on_task_error(err, asset.stac_id))
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
                asset, fc_path, f"{asset.stac_id}_FalseColor", is_false_color=True
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

    def _get_cache_directory(self, stac_id: str) -> str:
        """Get cache directory for processed AOI data."""
        settings = QSettings()
        cache_base = settings.value("IDPMPlugin/cache_dir", tempfile.gettempdir())
        cache_dir = os.path.join(cache_base, "idpm_aoi_cache", stac_id)
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    def _get_local_band_paths(self, asset) -> Dict[str, str]:
        """Get local file paths for bands if they exist."""
        local_paths = {}

        band_mapping = {
            "nir": "nir",
            "red": "red",
            "green": "green",
            "blue": "blue",
            "swir_b11": "swir_b11",
            "swir_b12": "swir_b12",
        }

        for band_name, band_key in band_mapping.items():
            if hasattr(asset, "get_local_path"):
                try:
                    local_path = asset.get_local_path(band_key)
                    if (
                        local_path
                        and os.path.exists(local_path)
                        and os.path.getsize(local_path) > 0
                    ):
                        local_paths[band_name] = local_path
                        QgsMessageLog.logMessage(
                            f"Found local {band_name} file: {os.path.basename(local_path)}",
                            "IDPMPlugin",
                            Qgis.Info,
                        )
                except:
                    # Skip if get_local_path fails for this band
                    pass

        return local_paths

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
            #rasterTitle { font-weight: bold; font-size: 16px; color: #333333; }
            #rasterSubtitle { color: #808080; font-size: 12px; font-style: italic; }
            #rasterCloud { font-weight: bold; color: #274423; font-size: 12px; }
            #rasterStatus { font-weight: bold; font-size: 10px; color: #007BFF; }
            #noResultsLabel { color: #808080; font-size: 16px; font-style: italic; padding: 40px; }
            #actionButton { 
                background-color: white; color: #495057; border: 1px solid #CED4DA; 
                padding: 8px 12px; border-radius: 8px; font-weight: bold; 
            }
            #actionButton:hover { background-color: #F1F3F5; }
            #actionButton:disabled { background-color: #E9ECEF; color: #ADB5BD; border-color: #DEE2E6; }
            #cancelButton {
                background-color: #FFC55A; color: black; border: none;
                padding: 4px 12px; border-radius: 6px; font-weight: bold;
            }
            #cancelButton:hover { background-color: #e0a800; }
            QScrollArea, #scrollAreaViewport, #scrollContent { border: none; background-color: #F8F9FA; }
            #paginationButton { background-color: white; color: #274423; border: 1px solid #274423; padding: 8px 16px; border-radius: 8px; }
            #paginationButton:disabled { background-color: #E9ECEF; color: #6C757D; border: 1px solid #CED4DA; }
            #pageLabel { color: #274423; font-size: 14px; }
            #filterLabel { color: #274423; font-weight: bold; font-size: 14px; }
            QComboBox#filterComboBox { font-family: "Montserrat"; padding: 5px; min-width: 120px; }
        """
        self.setStyleSheet(qss)

    def _cancel_all_operations(self):
        """Enhanced operation cancellation that handles AOI background tasks."""
        if self.aoi_tool:
            self._on_aoi_cancelled()

        op_keys_to_cancel = list(self.active_operations.keys())

        if op_keys_to_cancel:
            QgsMessageLog.logMessage(
                f"Closing dialog. Cancelling {len(op_keys_to_cancel)} active operations.",
                "IDPMPlugin",
                Qgis.Info,
            )

        for op_key in op_keys_to_cancel:
            op = self.active_operations.get(op_key)
            if op:
                # Cancel background tasks
                if task := op.get("task"):
                    if hasattr(task, "cancel"):
                        task.cancel()

                # Close progress dialogs
                if progress := op.get("progress"):
                    progress.close()

                # Cancel network requests (for non-AOI operations)
                if "replies" in op:
                    for reply in op["replies"]:
                        if reply.isRunning():
                            reply.abort()

            # Remove from tracking
            if op_key in self.active_operations:
                del self.active_operations[op_key]

        # Update all widget UIs
        for i in range(self.list_layout.count()):
            widget = self.list_layout.itemAt(i).widget()
            if hasattr(widget, "update_ui_based_on_local_files"):
                QTimer.singleShot(100, widget.update_ui_based_on_local_files)

    def reject(self):
        """
        Override reject() to ensure operations are cancelled when the dialog is
        closed via the 'X' button or ESC key.
        """
        self._cancel_all_operations()
        super().reject()

    def closeEvent(self, event):
        """
        Override closeEvent to handle closing from sources other than buttons
        (e.g., system close).
        """
        self._cancel_all_operations()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)

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


# Add this to the bottom of your file to make sure ThemedMessageBox is available
try:
    from .themed_message_box import ThemedMessageBox
except ImportError:
    # Fallback if ThemedMessageBox not available
    class ThemedMessageBox:
        @staticmethod
        def show_message(parent, icon, title, message):
            QMessageBox(icon, title, message, parent=parent).exec_()
