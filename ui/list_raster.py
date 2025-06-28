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
from ..core.ndvi_worker import NdvITask  # Updated import path

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

    downloadVisualRequested = pyqtSignal(dict)
    processNdviRequested = pyqtSignal(dict)

    def __init__(self, raster_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.raster_data = raster_data
        self.setObjectName("rasterItem")
        self.setAutoFillBackground(True)

        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self._handle_download_finished)

        self.active_downloads_count = (
            0  # To track how many downloads are active for this item
        )
        self.expected_downloads = (
            0  # How many downloads are expected (1 for visual, 2 for NDVI)
        )
        self.downloaded_bands = {}  # To store paths of downloaded bands for NDVI

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

        stac_id_label = QLabel(raster_data["properties"].get("stac_id", "N/A"))
        stac_id_label.setObjectName("rasterTitle")
        self.raster_id_label = stac_id_label  # Store reference to update status

        date_str = raster_data["properties"].get("tanggal", "")
        try:
            if "." in date_str:
                dt_obj = datetime.strptime(date_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")
            else:
                dt_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
            published_label = QLabel(
                f"Published on: {dt_obj.strftime('%d %b %Y %H:%M:%S')}"
            )
        except (ValueError, TypeError):
            published_label = QLabel(f"Published on: {date_str}")
        published_label.setObjectName("rasterSubtitle")

        cloud_cover = raster_data["properties"].get("cloud", 0)
        cloud_label = QLabel(f"Cloud Cover: {cloud_cover:.2f}%")
        cloud_label.setObjectName("rasterCloud")

        details_layout.addWidget(stac_id_label)
        details_layout.addWidget(published_label)
        details_layout.addWidget(cloud_label)
        details_layout.addStretch()

        main_layout.addLayout(details_layout)
        main_layout.addStretch()

        # --- Action Buttons and Progress Bars ---
        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(10)
        right_column_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Visual Download button
        self.btn_download_visual = QPushButton("Download Visual")
        self.btn_download_visual.setObjectName("actionButton")
        download_icon_path = os.path.join(Config.ASSETS_PATH, "images", "download.png")
        if os.path.exists(download_icon_path):
            self.btn_download_visual.setIcon(QIcon(download_icon_path))
            self.btn_download_visual.setIconSize(QSize(16, 16))
        self.btn_download_visual.clicked.connect(self._on_download_visual_clicked)
        right_column_layout.addWidget(self.btn_download_visual)

        # Visual Download Progress Bar
        self.progress_bar_visual = QProgressBar()
        self.progress_bar_visual.setTextVisible(True)
        self.progress_bar_visual.setVisible(False)
        self.progress_bar_visual.setFixedHeight(12)
        self.progress_bar_visual.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #C0C0C0;
                border-radius: 5px;
                background-color: #E0E0E0;
                text-align: center;
                color: black;
                font-size: 8px;
            }
            QProgressBar::chunk {
                background-color: #2E4434;
            }
        """
        )
        right_column_layout.addWidget(self.progress_bar_visual)

        # Process NDVI button
        self.btn_process_ndvi = QPushButton("Process NDVI")
        self.btn_process_ndvi.setObjectName("actionButton")
        self.btn_process_ndvi.setProperty("highlight", True)
        self.btn_process_ndvi.clicked.connect(self._on_process_ndvi_clicked)
        right_column_layout.addWidget(self.btn_process_ndvi)

        # NDVI Download Progress Bars (NIR and RED)
        ndvi_progress_layout = QHBoxLayout()
        self.progress_bar_nir = QProgressBar()
        self.progress_bar_nir.setTextVisible(True)
        self.progress_bar_nir.setVisible(False)
        self.progress_bar_nir.setFixedHeight(12)
        self.progress_bar_nir.setStyleSheet(
            self.progress_bar_visual.styleSheet()
        )  # Apply same style

        self.progress_bar_red = QProgressBar()
        self.progress_bar_red.setTextVisible(True)
        self.progress_bar_red.setVisible(False)
        self.progress_bar_red.setFixedHeight(12)
        self.progress_bar_red.setStyleSheet(
            self.progress_bar_visual.styleSheet()
        )  # Apply same style

        ndvi_progress_layout.addWidget(self.progress_bar_nir)
        ndvi_progress_layout.addWidget(self.progress_bar_red)
        right_column_layout.addLayout(ndvi_progress_layout)

        # Status Label (for general status messages)
        self.status_label = QLabel("")
        self.status_label.setObjectName("rasterStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        right_column_layout.addWidget(self.status_label)

        main_layout.addLayout(right_column_layout)

        self.update_ui_based_on_local_files()

    def load_thumbnail(self):
        # Corrected: Access 'thumb' directly from 'properties'
        thumb_url = self.raster_data["properties"].get("thumb")
        if thumb_url:
            request = QNetworkRequest(QUrl(thumb_url))
            reply = self.network_manager.get(request)
            reply.setProperty(
                "download_type", "thumbnail"
            )  # Custom property to identify reply
            reply.setProperty("target_label", self.thumb_label)

    def _on_download_visual_clicked(self):
        self.downloadVisualRequested.emit(self.raster_data)
        self.btn_download_visual.setEnabled(False)
        self.btn_process_ndvi.setEnabled(False)
        self.progress_bar_visual.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Downloading visual...")

    def _on_process_ndvi_clicked(self):
        self.processNdviRequested.emit(self.raster_data)
        self.btn_download_visual.setEnabled(False)
        self.btn_process_ndvi.setEnabled(False)
        self.progress_bar_nir.setVisible(True)
        self.progress_bar_red.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Downloading bands for NDVI...")

    def _handle_download_finished(self, reply: QNetworkReply):
        download_type = reply.property("download_type")
        target_label = reply.property("target_label")
        save_path = reply.property("save_path")
        file_handle = reply.property("file_handle")

        if file_handle:
            file_handle.close()  # Ensure file is closed after writing

        if download_type == "thumbnail":
            if reply.error() == QNetworkReply.NoError:
                image_data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(image_data):
                    target_label.setPixmap(pixmap)
            else:
                QgsMessageLog.logMessage(
                    f"Failed to load thumbnail for {self.raster_data['properties'].get('stac_id', 'N/A')}: {reply.errorString()}",
                    "IDPMPlugin",
                    Qgis.Warning,
                )
        elif download_type in ["visual", "nir", "red"]:
            if reply.error() == QNetworkReply.NoError:
                QgsMessageLog.logMessage(
                    f"Successfully downloaded {download_type} for {self.raster_data['properties'].get('stac_id', 'N/A')} to {save_path}",
                    "IDPMPlugin",
                    Qgis.Info,
                )
                self.downloaded_bands[download_type] = save_path
                self.active_downloads_count -= 1
                if download_type == "visual":
                    self.progress_bar_visual.setVisible(False)
                    self.status_label.setText("Visual download complete.")
                    self.update_ui_after_completion("visual")
                elif download_type == "nir":
                    self.progress_bar_nir.setVisible(False)
                    if "red" in self.downloaded_bands:  # Check if red is also done
                        self.status_label.setText(
                            "NIR and RED bands downloaded. Ready for NDVI."
                        )
                elif download_type == "red":
                    self.progress_bar_red.setVisible(False)
                    if "nir" in self.downloaded_bands:  # Check if nir is also done
                        self.status_label.setText(
                            "NIR and RED bands downloaded. Ready for NDVI."
                        )
            else:
                QMessageBox.critical(
                    self.parentWidget(),  # Assuming parent is ImageListDialog
                    f"Download Failed: {download_type}",
                    f"Failed to download {download_type} for {self.raster_data['properties'].get('stac_id', 'N/A')}: {reply.errorString()}",
                )
                self.status_label.setText(f"Download failed: {reply.errorString()}")
                self.status_label.setStyleSheet("color: red;")
                self.btn_download_visual.setEnabled(True)
                self.btn_process_ndvi.setEnabled(True)
                self.progress_bar_visual.setVisible(False)
                self.progress_bar_nir.setVisible(False)
                self.progress_bar_red.setVisible(False)
                if save_path and os.path.exists(save_path):
                    os.remove(save_path)  # Clean up incomplete file
                self.active_downloads_count -= 1  # Decrement even on error

        reply.deleteLater()

    def update_download_progress(self, bytes_received, bytes_total, download_type: str):
        if bytes_total > 0:
            progress = int((bytes_received / bytes_total) * 100)
            if download_type == "visual":
                self.progress_bar_visual.setValue(progress)
                self.status_label.setText(f"Downloading Visual: {progress}%")
            elif download_type == "nir":
                self.progress_bar_nir.setValue(progress)
                self.progress_bar_nir.setFormat(f"NIR: {progress}%")
            elif download_type == "red":
                self.progress_bar_red.setValue(progress)
                self.progress_bar_red.setFormat(f"RED: {progress}%")

    def update_ui_after_completion(self, completion_type: str):
        self.btn_download_visual.setEnabled(True)
        self.btn_process_ndvi.setEnabled(True)
        self.raster_id_label.setStyleSheet("color: green; font-weight: bold;")
        self.status_label.setVisible(False)  # Hide status label after success

    def update_ui_based_on_local_files(self):
        # Access the download_dir from the Config class (reverted change)
        download_dir = Config.DOWNLOAD_DIR

        # Check if visual asset exists locally
        # Corrected: Access 'visual' from 'properties'
        visual_url_prop = self.raster_data["properties"].get("visual")
        if visual_url_prop and download_dir:
            folder_path = os.path.join(
                download_dir, self.raster_data["properties"].get("stac_id", "UNKNOWN")
            )  # Use stac_id for folder
            file_name = os.path.basename(
                visual_url_prop.split("?")[0]
            )  # Handle potential query params
            save_path = os.path.join(folder_path, file_name)
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                self.raster_id_label.setStyleSheet("color: green; font-weight: bold;")
                self.btn_download_visual.setText("Visual Downloaded")
                self.btn_download_visual.setEnabled(False)

        # Check if processed NDVI exists locally
        if self.raster_data["properties"].get("has_proses") and self.raster_data[
            "properties"
        ].get("output_data"):
            ndvi_tif_url = self.raster_data["properties"]["output_data"]["result"].get(
                "ndvi_class_tif_url"
            )
            if ndvi_tif_url and download_dir:
                # A more robust check would involve checking if the actual NDVI file exists locally.
                ndvi_local_filename = f"{self.raster_data['properties'].get('stac_id', 'UNKNOWN')}_NDVI.tif"  # Use stac_id for filename
                ndvi_local_path = os.path.join(
                    download_dir,
                    self.raster_data["properties"].get("stac_id", "UNKNOWN"),
                    ndvi_local_filename,
                )
                if (
                    os.path.exists(ndvi_local_path)
                    and os.path.getsize(ndvi_local_path) > 0
                ):
                    self.btn_process_ndvi.setText("NDVI Processed")
                    self.btn_process_ndvi.setEnabled(False)
                    self.btn_process_ndvi.setProperty("highlight", False)
                    self.raster_id_label.setStyleSheet(
                        "color: darkblue; font-weight: bold;"
                    )  # Different color for processed

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
        self.all_features = data
        self.download_network_manager = QNetworkAccessManager(self)
        self.download_network_manager.finished.connect(
            self._handle_any_download_finished
        )

        # Ensure download directory exists (reverted to Config.DOWNLOAD_DIR)
        Config.DOWNLOAD_DIR = os.path.join(  # Reverted to Config.DOWNLOAD_DIR
            os.path.expanduser("~"), "Downloads", "IDPM_Raster_Assets"
        )
        if not os.path.exists(Config.DOWNLOAD_DIR):
            os.makedirs(Config.DOWNLOAD_DIR)

        self.active_item_downloads: Dict[str, RasterItemWidget] = (
            {}
        )  # Map raster_id to RasterItemWidget

        self.current_page = 1
        self.items_per_page = 5

        self.init_list_ui()
        self.update_list_and_pagination()
        self.add_basemap_global_osm(self.iface)

    def init_list_ui(self):
        self.setWindowTitle("List Raster")

        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 10, 30, 30)

        top_bar_layout = self._create_top_bar()
        main_layout.addLayout(top_bar_layout)
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

        pagination_layout = self._create_pagination_controls()
        main_layout.addLayout(pagination_layout)

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
        # Clear existing items
        while (
            self.list_layout.count() > 0
        ):  # Change to > 0 because of addStretch() at the end
            item = self.list_layout.takeAt(0)
            if item.widget():
                # Cancel any ongoing downloads for the item being removed
                if isinstance(item.widget(), RasterItemWidget):
                    # Ensure RasterItemWidget has a method to cancel its network requests if any
                    pass
                item.widget().deleteLater()
            elif item.layout():
                # If it's a nested layout, delete its widgets recursively
                self._clear_layout(item.layout())

        # Re-add the stretch if it was removed in the loop
        self.list_layout.addStretch()

        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_features = self.all_features[start_index:end_index]

        for feature in paginated_features:
            item_widget = RasterItemWidget(feature, self)
            item_widget.downloadVisualRequested.connect(
                self._handle_download_visual_requested
            )
            item_widget.processNdviRequested.connect(
                self._handle_process_ndvi_requested
            )
            self.list_layout.insertWidget(
                self.list_layout.count() - 1, item_widget
            )  # Insert before the stretch
            # Corrected: Use stac_id for the dictionary key
            self.active_item_downloads[feature["properties"]["stac_id"]] = (
                item_widget  # Store reference to update later
            )

        total_pages = (
            len(self.all_features) + self.items_per_page - 1
        ) // self.items_per_page
        if total_pages == 0:
            total_pages = 1  # At least one page even if no items
        self.page_label.setText(f"Page {self.current_page} of {total_pages}")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < total_pages)

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clear_layout(item.layout())

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.update_list_and_pagination()

    def next_page(self):
        total_pages = (
            len(self.all_features) + self.items_per_page - 1
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
        layer_name = (
            "OpenStreetMap (IDPM Basemap)"  # Make name slightly unique if desired
        )
        log_tag = "IDPMPlugin"  # Your existing log tag
        plugin_group = self.get_or_create_plugin_layer_group()

        if plugin_group:
            for child_node in plugin_group.children():
                if hasattr(child_node, "name") and child_node.name() == layer_name:
                    QgsMessageLog.logMessage(
                        f"Basemap '{layer_name}' already in group '{PLUGIN_LAYER_GROUP_NAME}'.",
                        log_tag,
                        Qgis.Info,
                    )
                    if hasattr(child_node, "layer"):
                        return child_node.layer()
                    return None  # Should not happen

        # ... (URL and layer_source setup as before) ...
        url = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
        layer_source = f"type=xyz&url={url}&zmax=19&zmin=0"
        layer = QgsRasterLayer(layer_source, layer_name, "wms")

        if layer.isValid():
            QgsProject.instance().addMapLayer(
                layer, False
            )  # Don't add to legend root directly
            if plugin_group:
                plugin_group.addLayer(layer)
                QgsMessageLog.logMessage(
                    f"Basemap '{layer_name}' added to group '{PLUGIN_LAYER_GROUP_NAME}'.",
                    log_tag,
                    Qgis.Info,
                )
            else:
                QgsProject.instance().addMapLayer(layer, True)
                QgsMessageLog.logMessage(
                    f"Basemap '{layer_name}' added to root as group was not available.",
                    log_tag,
                    Qgis.Warning,
                )

            return layer
        else:
            QgsMessageLog.logMessage(
                f"Failed to load basemap '{layer_name}'. Error: {layer.error().summary()}",
                log_tag,
                Qgis.Critical,
            )
            return None

    def _get_item_widget_by_raster_id(
        self, raster_id: str
    ) -> Optional[RasterItemWidget]:
        # Corrected: Lookup using the stac_id
        return self.active_item_downloads.get(raster_id)

    def _handle_download_visual_requested(self, raster_data: Dict[str, Any]):
        # Corrected: Pass stac_id consistently
        raster_stac_id = raster_data["properties"].get("stac_id", "UNKNOWN")
        item_widget = self._get_item_widget_by_raster_id(raster_stac_id)
        if not item_widget:
            return

        # Corrected: Access 'visual' directly from 'properties'
        visual_url = raster_data["properties"].get("visual")
        if not visual_url:
            QMessageBox.warning(
                self, "Missing Asset", f"No 'visual' asset found for {raster_stac_id}."
            )
            item_widget.btn_download_visual.setEnabled(True)
            item_widget.btn_process_ndvi.setEnabled(True)
            item_widget.progress_bar_visual.setVisible(False)
            item_widget.status_label.setVisible(False)
            return

        download_url = visual_url  # No need for ["href"]
        # Handle s3:// URLs if they might appear in 'visual' field directly
        if download_url and download_url.startswith("s3://"):
            bucket_name, object_key = download_url[5:].split("/", 1)
            download_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"

        folder_path = os.path.join(
            Config.DOWNLOAD_DIR, raster_stac_id
        )  # Changed back to Config.DOWNLOAD_DIR and uses stac_id
        os.makedirs(folder_path, exist_ok=True)
        file_name = os.path.basename(
            download_url.split("?")[0]
        )  # Handle potential query parameters
        save_path = os.path.join(folder_path, file_name)

        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            QMessageBox.information(
                self,
                "Already Downloaded",
                f"The visual file '{file_name}' is already downloaded in folder '{raster_stac_id}'.",
            )
            item_widget.update_ui_after_completion("visual")
            return

        request = QNetworkRequest(QUrl(download_url))
        reply = self.download_network_manager.get(request)
        reply.setProperty("raster_id", raster_stac_id)  # Set raster_id to stac_id
        reply.setProperty("download_type", "visual")
        reply.setProperty("save_path", save_path)

        # Open file in write-binary mode
        file_handle = open(save_path, "wb")
        reply.setProperty("file_handle", file_handle)

        reply.downloadProgress.connect(
            lambda bytes_received, bytes_total: item_widget.update_download_progress(
                bytes_received, bytes_total, "visual"
            )
        )
        reply.readyRead.connect(lambda r=reply: self._stream_data(r))

    def _handle_process_ndvi_requested(self, raster_data: Dict[str, Any]):
        # Corrected: Pass stac_id consistently
        raster_stac_id = raster_data["properties"].get("stac_id", "UNKNOWN")
        item_widget = self._get_item_widget_by_raster_id(raster_stac_id)
        if not item_widget:
            return

        # Define local NDVI path
        folder_path = os.path.join(Config.DOWNLOAD_DIR, raster_stac_id)
        local_ndvi_path = os.path.join(folder_path, f"{raster_stac_id}_NDVI.tif")

        # --- NEW: Check if local NDVI file already exists and is valid ---
        if os.path.exists(local_ndvi_path) and os.path.getsize(local_ndvi_path) > 0:
            QgsMessageLog.logMessage(
                f"Locally processed NDVI found for '{raster_stac_id}'. Attempting to load.",
                "IDPMPlugin",
                Qgis.Info,
            )
            if self._load_ndvi_into_qgis_layer(local_ndvi_path, raster_stac_id):
                QMessageBox.information(
                    self,
                    "Local NDVI Loaded",
                    f"Locally processed NDVI loaded for '{raster_stac_id}'.",
                )
                item_widget.btn_process_ndvi.setText("NDVI Processed")
                item_widget.btn_process_ndvi.setEnabled(False)
                item_widget.btn_process_ndvi.setProperty("highlight", False)
                item_widget.raster_id_label.setStyleSheet(
                    "color: darkblue; font-weight: bold;"
                )
                item_widget.status_label.setVisible(False)
                return  # Exit as local NDVI is loaded successfully
            else:
                QMessageBox.warning(
                    self,
                    "Local Load Failed",
                    f"Failed to load local NDVI for '{raster_stac_id}'. Proceeding to API/Band download check.",
                )
                # Fall through to API/Band download check if local load fails
                item_widget.btn_download_visual.setEnabled(True)
                item_widget.btn_process_ndvi.setEnabled(True)
                item_widget.progress_bar_nir.setVisible(False)
                item_widget.progress_bar_red.setVisible(False)
                item_widget.status_label.setVisible(False)

        # Corrected: Access 'asset_nir' and 'asset_red' directly from 'properties'
        nir_url = raster_data["properties"].get("asset_nir")
        red_url = raster_data["properties"].get("asset_red")

        if not nir_url or not red_url:
            QMessageBox.warning(
                self,
                "Missing Assets",
                f"NIR or RED band assets not found for {raster_stac_id}.",
            )
            item_widget.btn_download_visual.setEnabled(True)
            item_widget.btn_process_ndvi.setEnabled(True)
            item_widget.progress_bar_nir.setVisible(False)
            item_widget.progress_bar_red.setVisible(False)
            item_widget.status_label.setVisible(False)
            return

        os.makedirs(folder_path, exist_ok=True)

        item_widget.downloaded_bands = {}  # Reset for new process request
        item_widget.expected_downloads = 0

        # NIR band download
        # Handle s3:// URLs if they might appear in 'asset_nir' field directly
        if nir_url and nir_url.startswith("s3://"):
            bucket_name, object_key = nir_url[5:].split("/", 1)
            nir_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
        nir_file_name = os.path.basename(nir_url.split("?")[0])
        nir_save_path = os.path.join(folder_path, nir_file_name)

        # RED band download
        # Handle s3:// URLs if they might appear in 'asset_red' field directly
        if red_url and red_url.startswith("s3://"):
            bucket_name, object_key = red_url[5:].split("/", 1)
            red_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
        red_file_name = os.path.basename(red_url.split("?")[0])
        red_save_path = os.path.join(folder_path, red_file_name)

        # Check if NDVI is already processed (from API) - This logic is now AFTER local check
        if raster_data["properties"].get("has_proses"):
            api_ndvi_url = None
            if raster_data["properties"].get("output_data") and raster_data[
                "properties"
            ]["output_data"]["result"].get("ndvi_class_tif_url"):
                api_ndvi_url = f"{Config.API_URL.split('/api')[0]}{raster_data['properties']['output_data']['result']['ndvi_class_tif_url']}"

            if api_ndvi_url:
                QgsMessageLog.logMessage(
                    f"Attempting to load API processed NDVI for {raster_stac_id} from {api_ndvi_url}",
                    "IDPMPlugin",
                    Qgis.Info,
                )
                if self._load_ndvi_into_qgis_layer(api_ndvi_url, raster_stac_id):
                    QMessageBox.information(
                        self,
                        "Already Processed (API)",
                        f"NDVI for '{raster_stac_id}' loaded from API.",
                    )
                    item_widget.update_ui_after_completion("ndvi")
                    return  # Successfully loaded from API, no local processing needed
                else:
                    QMessageBox.warning(
                        self,
                        "API Load Failed",
                        f"Failed to load API processed NDVI for '{raster_stac_id}'. Falling back to local processing (bands).",
                    )
                    # Fallback: re-enable button and proceed to local download logic below
                    item_widget.btn_download_visual.setEnabled(True)
                    item_widget.btn_process_ndvi.setEnabled(True)
                    item_widget.progress_bar_nir.setVisible(False)
                    item_widget.progress_bar_red.setVisible(False)
                    item_widget.status_label.setVisible(False)
            else:
                QMessageBox.warning(
                    self,
                    "No API URL",
                    f"No NDVI output URL found for processed data for '{raster_stac_id}'. Falling back to local processing (bands).",
                )
                # Fallback: re-enable button and proceed to local download logic below
                item_widget.btn_download_visual.setEnabled(True)
                item_widget.btn_process_ndvi.setEnabled(True)
                item_widget.progress_bar_nir.setVisible(False)
                item_widget.progress_bar_red.setVisible(False)
                item_widget.status_label.setVisible(False)

        # Start downloads for NIR and RED bands
        for band_type, url, save_path in [
            ("nir", nir_url, nir_save_path),
            ("red", red_url, red_save_path),
        ]:
            item_widget.expected_downloads += (
                1  # Increment expected downloads for each band
            )
            if not (os.path.exists(save_path) and os.path.getsize(save_path) > 0):
                request = QNetworkRequest(QUrl(url))
                reply = self.download_network_manager.get(request)
                reply.setProperty(
                    "raster_id", raster_stac_id
                )  # Set raster_id to stac_id
                reply.setProperty("download_type", band_type)
                reply.setProperty("save_path", save_path)

                file_handle = open(save_path, "wb")
                reply.setProperty("file_handle", file_handle)

                reply.downloadProgress.connect(
                    lambda bytes_received, bytes_total, bt=band_type: item_widget.update_download_progress(
                        bytes_received, bytes_total, bt
                    )
                )
                reply.readyRead.connect(lambda r=reply: self._stream_data(r))
                item_widget.active_downloads_count += 1
            else:
                QgsMessageLog.logMessage(
                    f"{band_type.upper()} band for {raster_stac_id} already exists locally.",
                    "IDPMPlugin",
                    Qgis.Info,
                )
                item_widget.downloaded_bands[band_type] = save_path
                # Check if all downloads finished (including pre-existing files)
                if len(item_widget.downloaded_bands) == item_widget.expected_downloads:
                    QgsMessageLog.logMessage(
                        "All bands (including pre-existing) are ready. Proceeding to NDVI calculation.",
                        "IDPMPlugin",
                        Qgis.Info,
                    )
                    self._calculate_ndvi(
                        item_widget.downloaded_bands["red"],
                        item_widget.downloaded_bands["nir"],
                        folder_path,
                        raster_stac_id,
                    )
                    item_widget.status_label.setText("Starting NDVI calculation...")
                    item_widget.progress_bar_nir.setVisible(False)
                    item_widget.progress_bar_red.setVisible(False)
                    return  # Exit as calculation is triggered

        # If after checking, no new downloads were initiated, but not all bands were present, handle it
        if (
            item_widget.active_downloads_count == 0
            and len(item_widget.downloaded_bands) < item_widget.expected_downloads
        ):
            QMessageBox.warning(
                self,
                "Download Error",
                "Could not initiate band downloads. Ensure assets are available and paths are correct.",
            )
            item_widget.btn_download_visual.setEnabled(True)
            item_widget.btn_process_ndvi.setEnabled(True)
            item_widget.progress_bar_nir.setVisible(False)
            item_widget.progress_bar_red.setVisible(False)
            item_widget.status_label.setVisible(False)
            return

    def _stream_data(self, reply: QNetworkReply):
        """Stream data incrementally and write it to the file."""
        file_handle = reply.property("file_handle")
        if file_handle and reply.bytesAvailable() > 0:
            data = reply.readAll()
            file_handle.write(data.data())  # .data() is needed for QByteArray to bytes

    def _handle_any_download_finished(self, reply: QNetworkReply):
        raster_id = reply.property("raster_id")  # This is now stac_id
        download_type = reply.property("download_type")
        save_path = reply.property("save_path")
        file_handle = reply.property("file_handle")

        item_widget = self._get_item_widget_by_raster_id(raster_id)
        if not item_widget:
            reply.deleteLater()
            return

        if file_handle:
            file_handle.close()

        if reply.error() == QNetworkReply.NoError:
            QgsMessageLog.logMessage(
                f"Download complete: {download_type} for {raster_id}",
                "IDPMPlugin",
                Qgis.Info,
            )

            if download_type == "visual":
                item_widget.update_ui_after_completion("visual")
            elif download_type in ["nir", "red"]:
                item_widget.downloaded_bands[download_type] = save_path
                # Check if both NIR and RED are downloaded and ready for processing
                if len(item_widget.downloaded_bands) == item_widget.expected_downloads:
                    item_widget.status_label.setText(
                        "All bands downloaded. Starting NDVI calculation..."
                    )
                    item_widget.progress_bar_nir.setVisible(False)
                    item_widget.progress_bar_red.setVisible(False)
                    self._calculate_ndvi(
                        item_widget.downloaded_bands["red"],
                        item_widget.downloaded_bands["nir"],
                        os.path.dirname(save_path),  # Folder path
                        raster_id,
                    )
        else:
            QMessageBox.critical(
                self,
                "Download Failed",
                f"Failed to download {download_type} for {raster_id}: {reply.errorString()}",
            )
            if save_path and os.path.exists(save_path):
                os.remove(save_path)  # Clean up incomplete file

            item_widget.status_label.setText(
                f"Download failed for {download_type}: {reply.errorString()}"
            )
            item_widget.status_label.setStyleSheet("color: red;")
            item_widget.btn_download_visual.setEnabled(True)
            item_widget.btn_process_ndvi.setEnabled(True)
            item_widget.progress_bar_visual.setVisible(False)
            item_widget.progress_bar_nir.setVisible(False)
            item_widget.progress_bar_red.setVisible(False)
            item_widget.downloaded_bands.clear()  # Clear downloaded state on error
            item_widget.expected_downloads = 0  # Reset expected downloads

        reply.deleteLater()

    def _calculate_ndvi(
        self, red_path: str, nir_path: str, folder_path: str, raster_id: str
    ):
        item_widget = self._get_item_widget_by_raster_id(raster_id)
        if not item_widget:
            return

        task = NdvITask(red_path, nir_path, folder_path, raster_id)

        self.progress_dialog = QProgressDialog(
            "Calculating NDVI...", "Cancel", 0, 100, self
        )
        self.progress_dialog.setWindowTitle(f"NDVI Calculation for {raster_id}")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)  # Show immediately
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()

        task.progressChanged.connect(
            lambda progress_float: self.progress_dialog.setValue(int(progress_float))
        )
        task.calculationFinished.connect(
            lambda ndvi_path: self._handle_ndvi_task_finished(ndvi_path, raster_id)
        )
        task.errorOccurred.connect(
            lambda error_msg: self._handle_ndvi_error(error_msg, raster_id)
        )
        self.progress_dialog.canceled.connect(task.cancel)

        QgsApplication.taskManager().addTask(task)
        item_widget.status_label.setText("NDVI calculation in progress...")

    def _handle_ndvi_task_finished(self, ndvi_path: str, raster_id: str):
        self.progress_dialog.close()
        item_widget = self._get_item_widget_by_raster_id(raster_id)
        if item_widget:
            item_widget.update_ui_after_completion("ndvi")
            item_widget.status_label.setVisible(False)  # Hide status label
            item_widget.btn_process_ndvi.setText("NDVI Processed")
            item_widget.btn_process_ndvi.setEnabled(False)
            item_widget.btn_process_ndvi.setProperty("highlight", False)
            item_widget.raster_id_label.setStyleSheet(
                "color: darkblue; font-weight: bold;"
            )

        QMessageBox.information(
            self,
            "NDVI Calculated",
            f"NDVI calculation completed for {raster_id}. File saved at: {ndvi_path}",
        )
        self._load_ndvi_into_qgis_layer(ndvi_path, raster_id)

    def _handle_ndvi_error(self, error_msg: str, raster_id: str):
        self.progress_dialog.close()
        item_widget = self._get_item_widget_by_raster_id(raster_id)
        if item_widget:
            item_widget.btn_download_visual.setEnabled(True)
            item_widget.btn_process_ndvi.setEnabled(True)
            item_widget.progress_bar_nir.setVisible(False)
            item_widget.progress_bar_red.setVisible(False)
            item_widget.status_label.setText(f"NDVI calculation failed: {error_msg}")
            item_widget.status_label.setStyleSheet("color: red;")
            item_widget.downloaded_bands.clear()  # Clear downloaded state on error
            item_widget.expected_downloads = 0  # Reset expected downloads

        QMessageBox.critical(
            self, "Error", f"Failed to calculate NDVI for {raster_id}: {error_msg}"
        )

    def _load_ndvi_into_qgis_layer(self, ndvi_path: str, raster_id: str) -> bool:
        """Load the NDVI GeoTIFF into QGIS with classification and grouping.
        Returns True on success, False on failure.
        """
        layer = QgsRasterLayer(ndvi_path, f"{raster_id}_NDVI")
        if not layer.isValid():
            QMessageBox.warning(
                self, "Invalid Layer", f"Failed to load NDVI layer from {ndvi_path}"
            )
            return False  # Indicate failure

        # Define NDVI classification for mangroves (example ranges)
        # These values are approximate and might need fine-tuning based on specific data characteristics
        # Source: General knowledge in remote sensing for vegetation indices, often adapted for specific ecosystems like mangroves.
        color_ramp = QgsColorRampShader()
        color_ramp.setColorRampType(QgsColorRampShader.Discrete)

        items = []
        # Non-vegetation/Water
        items.append(
            QgsColorRampShader.ColorRampItem(
                0.0, QColor(0, 0, 255), "Water/Non-Vegetation"
            )
        )  # Blue (up to 0.0)
        # Sparse Mangrove (Jarang)
        items.append(
            QgsColorRampShader.ColorRampItem(
                0.2, QColor(255, 255, 0), "Jarang (Sparse)"
            )
        )  # Yellow (up to 0.2)
        # Medium Mangrove (Sedang)
        items.append(
            QgsColorRampShader.ColorRampItem(0.5, QColor(0, 255, 0), "Sedang (Medium)")
        )  # Green (up to 0.5)
        # Dense Mangrove (Rapat)
        items.append(
            QgsColorRampShader.ColorRampItem(1.0, QColor(0, 100, 0), "Rapat (Dense)")
        )  # Dark Green (up to 1.0)

        # Corrected: Use setColorRampItemList
        color_ramp.setColorRampItemList(items)

        shader = QgsRasterShader()
        # Corrected: Use setShaderFunction to assign the color_ramp shader
        shader.setRasterShaderFunction(color_ramp)

        provider = layer.dataProvider()
        band = 1
        renderer = QgsSingleBandPseudoColorRenderer(provider, band, shader)

        layer.setRenderer(renderer)
        layer.triggerRepaint()

        # Add layer to QGIS project
        existing = QgsProject.instance().mapLayersByName(layer.name())
        if not existing:
            QgsProject.instance().addMapLayer(layer, addToLegend=False)
            QgsMessageLog.logMessage(
                f"NDVI layer '{layer.name()}' loaded and styled.",
                "IDPMPlugin",
                Qgis.Info,
            )
        else:
            QgsMessageLog.logMessage(
                f"NDVI layer '{layer.name()}' already loaded.", "IDPMPlugin", Qgis.Info
            )

        # Group layer under "IDPM" group
        root = QgsProject.instance().layerTreeRoot()
        tree_layer = root.findLayer(layer.id())
        if tree_layer:
            tree_layer_parent = tree_layer.parent()
            tree_layer_parent.removeChildNode(tree_layer)

        idpm_group = self.get_or_create_plugin_layer_group()
        if not idpm_group:
            idpm_group = root.addGroup(PLUGIN_LAYER_GROUP_NAME)
            QgsMessageLog.logMessage(
                f"Created layer group: '{PLUGIN_LAYER_GROUP_NAME}'",
                "IDPMPlugin",
                Qgis.Info,
            )
        idpm_group.insertLayer(0, layer)

        QgsMessageLog.logMessage(
            f"Layer '{layer.name()}' added to group '{PLUGIN_LAYER_GROUP_NAME}'",
            "IDPMPlugin",
            Qgis.Info,
        )

        # Zoom to layer extent (optional, but good for user experience)
        self.iface.mapCanvas().setExtent(layer.extent())
        self.iface.mapCanvas().refresh()
        return True  # Indicate success

    def apply_stylesheet(self) -> None:
        qss = f"""
            #mainContainer {{ background-color: #F8F9FA; border-radius: 20px; }}
            QLabel {{ color: #212529; font-family: "Montserrat"; }}
            #pageTitle {{ font-size: 28px; font-weight: bold; color: #212529; }}
            #pageSubtitle {{ font-size: 14px; color: #808080; }}
            
            #backButton {{ background-color: transparent; color: #274423; border: none; font-size: 14px; padding: 8px; }}
            #backButton:hover {{ text-decoration: underline; }}
            
            #profileButton {{ background-color: transparent; color: #212529; border: 1px solid #DEE2E6; padding: 6px 15px; border-radius: 18px; font-size: 12px; }}
            
            #minimizeButton, #maximizeButton, #closeButton {{ color: #274423; }}
            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover {{ background-color: #E9ECEF; }}
            
            #scrollArea {{ border: none; background-color: transparent; }}
            #rasterItem {{ background-color: white; border: 1px solid #DEE2E6; border-radius: 12px; }}
            #rasterTitle {{ font-weight: bold; font-size: 16px; }}
            #rasterSubtitle {{ color: #808080; font-size: 14px; font-style: italic; }}
            #rasterCloud {{ font-weight: normal; color: #274423; font-size: 12px; }}
            #rasterStatus {{ font-weight: bold; font-size: 10px; }}

            #actionButton {{
                background-color: white; 
                color: #495057; 
                border: 1px solid #DEE2E6;
                padding: 8px 12px; 
                border-radius: 12px; 
                font-weight: bold;
                icon-spacing: 6px;
            }}
            #actionButton:hover {{
                background-color: #F8F9FA;
            }}
            #actionButton[highlight="true"] {{ 
                background-color: #2E4434; 
                color: white; 
                border: none;
            }}
            #actionButton[highlight="true"]:hover {{ 
                background-color: #3D5A43;
            }}
            
            #paginationButton {{ background-color: white; color: #274423; border: 1px solid #274423; padding: 8px 16px; border-radius: 12px; }}
            #paginationButton:disabled {{ background-color: white; color: #6C757D; border: 1px solid #808080; }}
            #pageLabel {{ color: #274423; font-size: 14px; }}
        """
        self.setStyleSheet(qss)

    def closeEvent(self, event):
        """Handle cleanup when the widget is closed."""
        # Abort any ongoing downloads when the dialog is closed
        for item_widget in self.active_item_downloads.values():
            if item_widget.network_manager:
                item_widget.network_manager.clearAccessCache()
                item_widget.network_manager.clearConnectionCache()

        super().closeEvent(event)
