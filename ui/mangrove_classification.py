"""
Complete Mangrove Classification Dialog UI
Incorporates ALL features from pendi-mangrove with a modernized UI/UX.

Key UI/UX Changes:
- Two-column layout for better organization (Input | Process/Output).
- Modern styling with a clean, green-themed color palette.
- Added a QScrollArea to ensure content is not cut off on smaller screens.
- Large, icon-driven buttons for digitization.
- Redesigned and regrouped controls to match the screenshot.
"""

from typing import Optional
import os
import csv
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QFrame,
    QScrollArea,  # <-- Import QScrollArea
    QGridLayout,
    QSpacerItem,
    QSizePolicy,
    QGroupBox,
    QCheckBox,
    QDoubleSpinBox,
    QMenu,
    QApplication,
)
from PyQt5.QtGui import QFont, QIcon, QColor
from PyQt5.QtCore import Qt, QSize, QVariant

from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsFields,
    QgsField,
    QgsVectorFileWriter,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsDefaultValue,
    QgsEditFormConfig,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsSymbol,
    QgsApplication,
    Qgis,
    QgsMessageLog,
    QgsPointXY,
)

from qgis.gui import QgisInterface

# These imports assume a specific project structure. Adjust if necessary.
from .base_dialog import BaseDialog
from .themed_message_box import ThemedMessageBox
from .loading import LoadingDialog
from ..core.mangrove_classifier import EnhancedMangroveClassificationTask
from ..config import Config


class CompleteMangroveClassificationDialog(BaseDialog):
    """
    Complete Mangrove Classification Dialog with a modernized UI/UX.
    Features from pendi-mangrove are preserved and presented in the new design.
    """

    def __init__(self, iface: QgisInterface, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.iface = iface
        self.loading_dialog = None
        self.active_task = None
        self.latest_results = None
        self.active_digitasi_mode = None

        self.init_complete_mangrove_ui()
        self.setup_buttons()
        self.populate_layers()
        self.log_message("[INFO] Mangrove Classification UI ready.")

    def init_complete_mangrove_ui(self):
        """Initialize the complete mangrove classification UI with ALL features"""
        self.setWindowTitle("Mangrove Classification")
        self.setMinimumSize(900, 800)

        # Main layout
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setObjectName("mainLayout")
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        top_bar = self._create_top_bar()
        main_layout.addLayout(top_bar)

        # --- Top Section (Fixed) ---
        title_label = QLabel("Mangrove Classification")
        title_label.setObjectName("titleLabel")
        subtitle_label = QLabel(
            "Digitasi sampel mangrove dan non-mangrove, lalu klasifikasikan menggunakan algoritma machine learning."
        )
        subtitle_label.setObjectName("subtitleLabel")
        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        # --- Center Section (Scrollable) ---
        scroll_area = QScrollArea()
        scroll_area.setObjectName("scrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content_widget = (
            QWidget()
        )  # A container for the layout that will be scrolled
        column_layout = QHBoxLayout(scroll_content_widget)
        column_layout.setSpacing(20)
        column_layout.setContentsMargins(
            0, 0, 5, 0
        )  # Add a small margin to prevent scrollbar overlap

        # Left Column (Input)
        left_column = self._create_left_column()
        column_layout.addWidget(left_column)

        # Right Column (Process & Output)
        right_column = self._create_right_column()
        column_layout.addWidget(right_column)

        scroll_area.setWidget(
            scroll_content_widget
        )  # Set the widget containing the columns as the scroll area's content
        main_layout.addWidget(scroll_area)  # Add the scroll area to the main layout

        # --- Bottom Section (Fixed) ---
        report_layout = QHBoxLayout()
        report_layout.setContentsMargins(10, 10, 10, 0)
        report_layout.addStretch()
        self.btnViewReport = QPushButton("Lihat Report")
        self.btnViewReport.setObjectName("secondaryButton")
        self.btnViewReport.setEnabled(False)
        self.btnSimpanReport = QPushButton("Simpan Report")
        self.btnSimpanReport.setObjectName("primaryButton")
        self.btnSimpanReport.setEnabled(False)
        report_layout.addWidget(self.btnViewReport)
        report_layout.addWidget(self.btnSimpanReport)
        main_layout.addLayout(report_layout)

        log_section = self._create_log_section()
        main_layout.addWidget(log_section)

        # Set a stretch factor to prioritize the scroll area's space
        main_layout.setStretchFactor(scroll_area, 1)
        main_layout.setStretchFactor(log_section, 0)

        self.apply_stylesheet()

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

    def _create_card(self, title):
        """Helper function to create a styled card widget."""
        card = QWidget()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(25, 25, 25, 25)
        card_layout.setSpacing(20)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("cardTitleLabel")
            card_layout.addWidget(title_label)

        return card, card_layout

    def _create_left_column(self):
        """Create the left column for all input controls."""
        card, layout = self._create_card("Input")

        # --- ShapeFile Creation ---
        shp_path_layout = QHBoxLayout()
        self.cmbGeometry = QComboBox()
        self.cmbGeometry.setObjectName("inputField")
        self.cmbGeometry.addItem("Point")
        self.cmbGeometry.addItem("Polygon")

        self.txtShpPath = QLineEdit()
        self.txtShpPath.setObjectName("inputField")
        self.txtShpPath.setPlaceholderText("-- Choose file save location --")

        self.btnBrowseShp = QPushButton("Select File")
        self.btnBrowseShp.setObjectName("selectFileButton")

        shp_path_layout.addWidget(self.cmbGeometry)
        shp_path_layout.addWidget(self.txtShpPath, 1)
        shp_path_layout.addWidget(self.btnBrowseShp)
        layout.addLayout(shp_path_layout)

        self.btnCreateShp = QPushButton("Buat SHP Sampel")
        self.btnCreateShp.setObjectName("primaryButton")
        layout.addWidget(self.btnCreateShp)

        layout.addWidget(self._create_separator())

        # --- Digitization Tools ---
        digitization_layout = QHBoxLayout()
        digitization_layout.setSpacing(15)

        self.btnDigitasiMangrove = QPushButton("  Digitasi Sampel Mangrove")
        self.btnDigitasiMangrove.setObjectName("digitizationButtonActive")
        icon_path = os.path.join(os.path.dirname(__file__), "..", "asset", "tree.svg")
        if os.path.exists(icon_path):
            self.btnDigitasiMangrove.setIcon(QIcon(icon_path))
            self.btnDigitasiMangrove.setIconSize(QSize(32, 32))

        self.btnDigitasiNonMangrove = QPushButton("  Digitasi Sampel Non Mangrove")
        self.btnDigitasiNonMangrove.setObjectName("digitizationButtonInactive")
        icon_path_non = os.path.join(
            os.path.dirname(__file__), "..", "asset", "tree_nonmangrove.svg"
        )
        if os.path.exists(icon_path_non):
            self.btnDigitasiNonMangrove.setIcon(QIcon(icon_path_non))
            self.btnDigitasiNonMangrove.setIconSize(QSize(32, 32))

        digitization_layout.addWidget(self.btnDigitasiMangrove)
        digitization_layout.addWidget(self.btnDigitasiNonMangrove)
        layout.addLayout(digitization_layout)

        self.digitization_status_label = QLabel("Mode digitasi Mangrove aktif")
        self.digitization_status_label.setObjectName("statusLabel")
        self.digitization_status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.digitization_status_label)

        layout.addWidget(self._create_separator())

        # --- Layer Selection ---
        layout.addWidget(QLabel("Pilih Layer Raster"))
        raster_layout = QHBoxLayout()
        self.cmbRaster = QComboBox()
        self.cmbRaster.setObjectName("inputField")
        self.btnBrowseRaster = QPushButton("Select File")
        self.btnBrowseRaster.setObjectName("selectFileButton")
        raster_layout.addWidget(self.cmbRaster, 1)
        raster_layout.addWidget(self.btnBrowseRaster)
        layout.addLayout(raster_layout)

        layout.addWidget(QLabel("Pilih Layer ROI"))  # Corrected from screenshot
        roi_layout = QHBoxLayout()
        self.cmbROI = QComboBox()
        self.cmbROI.setObjectName("inputField")
        self.btnBrowseROI = QPushButton("Select File")
        self.btnBrowseROI.setObjectName("selectFileButton")
        roi_layout.addWidget(self.cmbROI, 1)
        roi_layout.addWidget(self.btnBrowseROI)
        layout.addLayout(roi_layout)

        layout.addStretch()
        return card

    def _create_right_column(self):
        """Create the right column for process and output controls."""
        card, layout = self._create_card("")  # Empty title as per design

        # --- Proses ---
        proses_title = QLabel("Proses")
        proses_title.setObjectName("cardTitleLabel")
        layout.addWidget(proses_title)

        proses_grid = QGridLayout()
        proses_grid.setSpacing(15)
        proses_grid.addWidget(QLabel("Metode Klasifikasi"), 0, 0)
        proses_grid.addWidget(QLabel("Persentase Test"), 0, 1)

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.setObjectName("inputField")
        self.algorithm_combo.addItems(["Random Forest", "SVM", "Gradient Boosting"])
        proses_grid.addWidget(self.algorithm_combo, 1, 0)

        self.spinTestSize = QSpinBox()
        self.spinTestSize.setObjectName("inputField")
        self.spinTestSize.setMinimum(10)
        self.spinTestSize.setMaximum(50)
        self.spinTestSize.setValue(20)
        self.spinTestSize.setSuffix("%")
        proses_grid.addWidget(self.spinTestSize, 1, 1)

        layout.addLayout(proses_grid)

        layout.addWidget(self._create_separator())

        # --- Output ---
        output_title = QLabel("Output")
        output_title.setObjectName("cardTitleLabel")
        layout.addWidget(output_title)

        layout.addWidget(QLabel("Lokasi Penyimpanan Hasil Klasifikasi"))
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setObjectName("inputField")
        self.output_path_edit.setPlaceholderText("-- Choose file save location --")
        self.btnBrowseOutput = QPushButton("Select File")
        self.btnBrowseOutput.setObjectName("selectFileButton")
        output_layout.addWidget(self.output_path_edit, 1)
        output_layout.addWidget(self.btnBrowseOutput)
        layout.addLayout(output_layout)

        self.progressBar = QProgressBar()
        self.progressBar.setObjectName("progressBar")
        self.progressBar.setTextVisible(False)
        layout.addWidget(self.progressBar)

        self.btnRunKlasifikasi = QPushButton("Jalankan Klasifikasi")
        self.btnRunKlasifikasi.setObjectName("primaryButton")
        layout.addWidget(self.btnRunKlasifikasi)

        layout.addStretch()
        return card

    def _create_log_section(self):
        """Create the log section at the bottom."""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)

        log_title = QLabel("Log Proses")
        log_title.setObjectName("cardTitleLabel")
        log_layout.addWidget(log_title)

        self.txtLog = QTextEdit()
        self.txtLog.setObjectName("logTextEdit")
        self.txtLog.setReadOnly(True)
        self.txtLog.setFixedHeight(120)  # Give the log a fixed height
        log_layout.addWidget(self.txtLog)

        return log_widget

    def _create_separator(self):
        """Creates a horizontal line separator."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setObjectName("separator")
        return line

    def setup_buttons(self):
        """Setup button connections."""
        try:
            self.btnBrowseShp.clicked.connect(self.browse_shp_path)
            self.btnCreateShp.clicked.connect(self.create_shapefile_roi)
            self.btnDigitasiMangrove.clicked.connect(self.start_digitasi_mangrove)
            self.btnDigitasiMangrove.setContextMenuPolicy(Qt.CustomContextMenu)
            self.btnDigitasiMangrove.customContextMenuRequested.connect(
                self.show_stop_menu
            )
            self.btnDigitasiNonMangrove.clicked.connect(
                self.start_digitasi_non_mangrove
            )
            self.btnDigitasiNonMangrove.setContextMenuPolicy(Qt.CustomContextMenu)
            self.btnDigitasiNonMangrove.customContextMenuRequested.connect(
                self.show_stop_menu
            )
            self.btnBrowseRaster.clicked.connect(self.browse_raster)
            self.btnBrowseROI.clicked.connect(self.browse_roi)
            self.btnBrowseOutput.clicked.connect(self.browse_output_path)
            self.btnRunKlasifikasi.clicked.connect(self.run_klasifikasi)
            self.btnViewReport.clicked.connect(self.show_report)
            self.btnSimpanReport.clicked.connect(self.save_report)
            self.cmbRaster.currentIndexChanged.connect(self._update_layer_info)
            self.cmbROI.currentIndexChanged.connect(self._update_layer_info)
        except Exception as e:
            self.log_message(f"[ERROR] Failed to setup buttons: {str(e)}")

    # ============ SHAPEFILE CREATION & DIGITIZATION (Functionality restored from old UI) ============

    def browse_shp_path(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Shapefile", "", "Shapefile (*.shp)"
        )
        if file_path:
            self.txtShpPath.setText(file_path)

    def create_shapefile_roi(self):
        shp_path = self.txtShpPath.text().strip()
        if not shp_path:
            self.log_message("[ERROR] Path shapefile belum ditentukan.")
            return

        geom_type_map = {"Point": QgsWkbTypes.Point, "Polygon": QgsWkbTypes.Polygon}
        wkb_type = geom_type_map.get(self.cmbGeometry.currentText())
        if not wkb_type:
            self.log_message("[ERROR] Tipe geometri tidak valid.")
            return

        fields = QgsFields()
        fields.append(QgsField("class", QVariant.Int))
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        writer = QgsVectorFileWriter(
            shp_path, "UTF-8", fields, wkb_type, crs, "ESRI Shapefile"
        )

        if writer.hasError() != QgsVectorFileWriter.NoError:
            self.log_message(
                f"[ERROR] Gagal membuat shapefile: {writer.errorMessage()}"
            )
            return
        del writer
        self.log_message(f"[INFO] Shapefile ROI berhasil dibuat di: {shp_path}")

        layer_name = f"Sampel Mangrove {self.cmbGeometry.currentText()}"
        layer = QgsVectorLayer(shp_path, layer_name, "ogr")
        if layer.isValid():
            categories = [
                QgsRendererCategory(
                    1,
                    QgsSymbol.defaultSymbol(layer.geometryType()).setColor(
                        QColor(0, 200, 0)
                    ),
                    "Mangrove",
                ),
                QgsRendererCategory(
                    0,
                    QgsSymbol.defaultSymbol(layer.geometryType()).setColor(
                        QColor(200, 0, 0)
                    ),
                    "Non Mangrove",
                ),
            ]
            renderer = QgsCategorizedSymbolRenderer("class", categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
            QgsProject.instance().addMapLayer(layer)
            self.log_message(f"[INFO] Layer '{layer_name}' dimuat dan disimbolisasi.")
            self.populate_layers()
        else:
            self.log_message("[ERROR] Gagal memuat shapefile ROI ke QGIS.")

    def show_stop_menu(self, position):
        menu = QMenu()
        stop_action = menu.addAction("Berhenti Digitasi")
        stop_action.triggered.connect(self.stop_digitasi)
        menu.exec_(self.sender().mapToGlobal(position))

    def stop_digitasi(self):
        self.set_active_mode(None)
        self.iface.actionPan().trigger()
        layer = self.iface.activeLayer()
        if layer and layer.isEditable():
            layer.commitChanges()
        self.log_message("[INFO] Mode digitasi dihentikan manual.")

    def set_active_mode(self, mode):
        self.active_digitasi_mode = mode
        self.btnDigitasiMangrove.setObjectName("digitizationButtonInactive")
        self.btnDigitasiNonMangrove.setObjectName("digitizationButtonInactive")

        if mode == "mangrove":
            self.btnDigitasiMangrove.setObjectName("digitizationButtonActive")
            self.digitization_status_label.setText(
                "Mode digitasi Mangrove aktif (Class = 1)"
            )
        elif mode == "non_mangrove":
            self.btnDigitasiNonMangrove.setObjectName("digitizationButtonActive")
            self.digitization_status_label.setText(
                "Mode digitasi Non-Mangrove aktif (Class = 0)"
            )
        else:
            self.digitization_status_label.setText("Pilih mode untuk memulai digitasi")

        # Re-apply stylesheet to reflect object name changes for active/inactive state
        self.btnDigitasiMangrove.style().unpolish(self.btnDigitasiMangrove)
        self.btnDigitasiMangrove.style().polish(self.btnDigitasiMangrove)
        self.btnDigitasiNonMangrove.style().unpolish(self.btnDigitasiNonMangrove)
        self.btnDigitasiNonMangrove.style().polish(self.btnDigitasiNonMangrove)

    def start_digitasi(self, mode, class_value):
        layer = self.get_selected_roi_layer()
        if not layer:
            self.log_message("[ERROR] Layer ROI belum dimuat.")
            return
        if not layer.isEditable():
            layer.startEditing()
        self.set_active_mode(mode)
        self.log_message(
            f"[INFO] Mode digitasi {mode.replace('_',' ')} aktif. Class otomatis {class_value}."
        )

        idx = layer.fields().indexFromName("class")
        if idx != -1:
            layer.setDefaultValueDefinition(idx, QgsDefaultValue(str(class_value)))

        try:
            layer.featureAdded.disconnect()
        except:
            pass
        layer.featureAdded.connect(
            lambda fid: layer.changeAttributeValue(fid, idx, class_value)
        )

        self.iface.actionAddFeature().trigger()
        QApplication.setOverrideCursor(Qt.CrossCursor)

    def start_digitasi_mangrove(self):
        self.start_digitasi("mangrove", 1)

    def start_digitasi_non_mangrove(self):
        self.start_digitasi("non_mangrove", 0)

    def populate_layers(self):
        self.cmbRaster.clear()
        self.cmbRaster.addItem("-- Choose file --", None)
        self.cmbROI.clear()
        self.cmbROI.addItem("-- Choose file --", None)

        for layer in QgsProject.instance().mapLayers().values():
            if (
                isinstance(layer, QgsRasterLayer)
                and layer.isValid()
                and layer.bandCount() >= 3
            ):
                self.cmbRaster.addItem(layer.name(), layer.id())
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.isValid()
                and "class" in [f.name().lower() for f in layer.fields()]
            ):
                self.cmbROI.addItem(layer.name(), layer.id())
        self.log_message("[INFO] Layer lists updated.")

    def get_selected_raster_layer(self):
        layer_id = self.cmbRaster.currentData()
        return QgsProject.instance().mapLayer(layer_id) if layer_id else None

    def get_selected_roi_layer(self):
        layer_id = self.cmbROI.currentData()
        return QgsProject.instance().mapLayer(layer_id) if layer_id else None

    # ============ CLASSIFICATION & OTHER METHODS (Unchanged Logic) ============

    def browse_raster(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Raster File",
            "",
            "Raster Files (*.tif *.tiff *.img *.jp2);;All Files (*)",
        )
        if file_path:
            layer = QgsRasterLayer(file_path, os.path.basename(file_path))
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self.populate_layers()

    def browse_roi(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ROI/Sample File",
            "",
            "Vector Files (*.shp *.geojson *.gpkg);;All Files (*)",
        )
        if file_path:
            layer = QgsVectorLayer(file_path, os.path.basename(file_path), "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self.populate_layers()

    def browse_output_path(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Output Path", "", "GeoTIFF Files (*.tif);;All Files (*)"
        )
        if file_path:
            self.output_path_edit.setText(file_path)

    def run_klasifikasi(self):
        raster_layer = self.get_selected_raster_layer()
        roi_layer = self.get_selected_roi_layer()
        output_path = self.output_path_edit.text().strip()
        method = self.algorithm_combo.currentText()
        test_size = self.spinTestSize.value() / 100.0

        if not all([raster_layer, roi_layer, output_path]):
            self.log_message("[ERROR] Please specify all inputs, outputs, and layers.")
            return

        self.log_message(f"[INFO] Starting {method} classification...")
        self.btnRunKlasifikasi.setEnabled(False)
        self.progressBar.setVisible(True)

        try:
            # This part assumes the backend functions exist and work as before
            from ..core.mangrove_classifier import run_classification_by_method

            result = run_classification_by_method(
                method, raster_layer, roi_layer, output_path, self, test_size
            )
            if result:
                self.btnViewReport.setEnabled(True)
                self.btnSimpanReport.setEnabled(True)
                self.log_message(
                    "[SUCCESS] Classification finished! Report is available."
                )
        except Exception as e:
            self.log_message(f"[ERROR] Classification failed: {e}")
        finally:
            self.btnRunKlasifikasi.setEnabled(True)

    def show_report(self):
        self.log_message("[INFO] Showing report...")  # Placeholder

    def save_report(self):
        self.log_message("[INFO] Saving report...")  # Placeholder

    def _update_layer_info(self):
        pass  # Can be expanded if needed

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txtLog.append(f"[{timestamp}] {message}")
        self.txtLog.verticalScrollBar().setValue(
            self.txtLog.verticalScrollBar().maximum()
        )
        QgsMessageLog.logMessage(message, "MangroveClassification", Qgis.Info)

    def apply_stylesheet(self):
        """Apply the modern, two-column UI style."""
        style = """
        /* Main Background */
        #mainLayout { background-color: #F8F9FA; border-radius: 20px; }
        QWidget#mainLayout {
            background-color: #F8F9FA; /* Use light grey for the main dialog background */
        }

        /* Make the container inside transparent */
        #mainContainer { background-color: #F8F9FA; }
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
        
        /* Titles */
        QLabel#titleLabel { font-size: 22px; font-weight: 600; color: #333; }
        QLabel#subtitleLabel { font-size: 14px; color: #777; margin-bottom: 10px; }
        QLabel#cardTitleLabel { font-size: 16px; font-weight: 600; color: #1a512e; margin-bottom: 5px; }
        
        /* Cards */
        QWidget#card {
            background-color: white;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }
        
        /* Scroll Area */
        QScrollArea#scrollArea { border: none; background: transparent; }

        /* Input Fields */
        QLineEdit#inputField, QComboBox#inputField, QSpinBox#inputField {
            background-color: #f7f7f7;
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px;
            font-size: 14px;
        }
        QLineEdit#inputField:focus, QComboBox#inputField:focus, QSpinBox#inputField:focus {
            border-color: #2c5530;
        }
        QComboBox::drop-down { border: none; }
        QComboBox::down-arrow { image: url(:/plugins/mangrove_monitor/asset/arrow-down.svg); }

        /* Buttons */
        QPushButton { font-size: 14px; font-weight: 500; border-radius: 5px; padding: 10px 15px; }
        
        QPushButton#primaryButton {
            background-color: #2c5530; /* Dark Green */
            color: white;
            border: none;
        }
        QPushButton#primaryButton:hover { background-color: #386b3d; }
        QPushButton#primaryButton:pressed { background-color: #214024; }
        
        QPushButton#secondaryButton {
            background-color: transparent;
            color: #2c5530;
            border: 1px solid #2c5530;
        }
        QPushButton#secondaryButton:hover { background-color: #eaf1eb; }
        QPushButton#secondaryButton:pressed { background-color: #d5e3da; }
        
        QPushButton#selectFileButton {
            background-color: #f0f0f0;
            color: #333;
            border: 1px solid #ccc;
        }
        QPushButton#selectFileButton:hover { background-color: #e5e5e5; }
        
        /* Digitization Buttons */
        .QPushButton { text-align: left; padding: 15px; }
        QPushButton#digitizationButtonActive {
            background-color: #2c5530;
            color: white;
            border: 2px solid #2c5530;
            font-weight: bold;
        }
        QPushButton#digitizationButtonInactive {
            background-color: white;
            color: #2c5530;
            border: 2px solid #dcdcdc;
        }
        QPushButton#digitizationButtonInactive:hover { border-color: #2c5530; }
        
        /* Other Widgets */
        QLabel { font-size: 14px; color: #333; }
        QLabel#statusLabel { font-size: 12px; color: #555; }
        QFrame#separator { background-color: #e0e0e0; max-height: 1px; }
        
        QProgressBar#progressBar {
            border: none;
            background-color: #e0e0e0;
            border-radius: 4px;
            text-align: center;
            height: 8px;
        }
        QProgressBar#progressBar::chunk {
            background-color: #4caf50; /* Bright Green */
            border-radius: 4px;
        }
        
        QTextEdit#logTextEdit {
            background-color: #2b2b2b;
            color: #f0f0f0;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
        }
        """
        self.setStyleSheet(style)


# Alias for backward compatibility
MangroveClassificationDialog = CompleteMangroveClassificationDialog
