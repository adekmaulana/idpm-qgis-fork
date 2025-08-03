"""
Complete Mangrove Classification Dialog UI
Incorporates ALL features from pendi-mangrove including:
- ShapeFile creation and input functionality
- Mangrove/Non-Mangrove digitization buttons
- Complete UI elements that were missing
- Enhanced functionality with modern design
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
    QScrollArea,
    QGridLayout,
    QSpacerItem,
    QSizePolicy,
    QGroupBox,
    QCheckBox,
    QDoubleSpinBox,
    QMenu,
    QApplication,
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt, QSize

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
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor

from qgis.gui import QgisInterface
from .base_dialog import BaseDialog
from .themed_message_box import ThemedMessageBox
from .loading import LoadingDialog
from ..core.mangrove_classifier import EnhancedMangroveClassificationTask
from ..config import Config


class CompleteMangroveClassificationDialog(BaseDialog):
    """
    Complete Mangrove Classification Dialog with ALL pendi-mangrove features restored.

    Features:
    - ShapeFile creation and management
    - Digitization buttons for Mangrove/Non-Mangrove
    - Complete layer management
    - Enhanced UI with all missing elements
    - Modern design integrated with classic functionality
    """

    def __init__(self, iface: QgisInterface, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.iface = iface
        self.loading_dialog = None
        self.active_task = None
        self.latest_results = None

        # Digitization state management (restored from pendi-mangrove)
        self.active_digitasi_mode = None

        # Initialize UI and populate data
        self.init_complete_mangrove_ui()
        self.setup_buttons()
        self.populate_layers()

    def init_complete_mangrove_ui(self):
        """Initialize the complete mangrove classification UI with ALL features"""
        self.setWindowTitle("Enhanced Mangrove Classification - Complete Version")
        self.setMinimumSize(900, 800)

        # Main layout
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setObjectName("mainContainer")
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title section
        title_layout = self._create_title_section()
        main_layout.addLayout(title_layout)

        # Create main content area
        content_widget = self._create_main_content()
        main_layout.addWidget(content_widget)

        self.apply_stylesheet()

    def _create_title_section(self):
        """Create title section"""
        layout = QVBoxLayout()

        title_label = QLabel("Enhanced Mangrove Classification")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignCenter)

        subtitle_label = QLabel(
            "Complete version with ShapeFile creation and digitization tools"
        )
        subtitle_label.setObjectName("subtitleLabel")
        subtitle_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        return layout

    def _create_main_content(self):
        """Create main content area with all sections"""
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(20)

        # Layer Selection Section
        layer_section = self._create_layer_selection_section()
        layout.addWidget(layer_section)

        # ShapeFile Creation Section (RESTORED from pendi-mangrove)
        shapefile_section = self._create_shapefile_creation_section()
        layout.addWidget(shapefile_section)

        # Digitization Section (RESTORED from pendi-mangrove)
        digitization_section = self._create_digitization_section()
        layout.addWidget(digitization_section)

        # Algorithm Configuration Section
        algorithm_section = self._create_algorithm_section()
        layout.addWidget(algorithm_section)

        # Output Configuration Section
        output_section = self._create_output_section()
        layout.addWidget(output_section)

        # Action Buttons Section
        actions_section = self._create_action_buttons_section()
        layout.addWidget(actions_section)

        # Log Section
        log_section = self._create_log_section()
        layout.addWidget(log_section)

        return content_widget

    def _create_layer_selection_section(self):
        """Create layer selection section with browse buttons"""
        group = QGroupBox("Input Layers")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Raster layer selection
        raster_layout = QHBoxLayout()
        raster_label = QLabel("Raster Layer:")
        raster_label.setObjectName("fieldLabel")

        self.cmbRaster = QComboBox()
        self.cmbRaster.setObjectName("inputCombo")

        self.btnBrowseRaster = QPushButton("Browse")
        self.btnBrowseRaster.setObjectName("browseButton")
        self.btnBrowseRaster.setToolTip("Load Raster (minimal 3 band)")

        raster_layout.addWidget(raster_label)
        raster_layout.addWidget(self.cmbRaster, 1)
        raster_layout.addWidget(self.btnBrowseRaster)
        layout.addLayout(raster_layout)

        # ROI layer selection
        roi_layout = QHBoxLayout()
        roi_label = QLabel("ROI/Samples:")
        roi_label.setObjectName("fieldLabel")

        self.cmbROI = QComboBox()
        self.cmbROI.setObjectName("inputCombo")

        self.btnBrowseROI = QPushButton("Browse")
        self.btnBrowseROI.setObjectName("browseButton")
        self.btnBrowseROI.setToolTip("Load file Sampel")

        roi_layout.addWidget(roi_label)
        roi_layout.addWidget(self.cmbROI, 1)
        roi_layout.addWidget(self.btnBrowseROI)
        layout.addLayout(roi_layout)

        # Layer info display
        self.layer_info_label = QLabel("Select layers to view information")
        self.layer_info_label.setObjectName("infoLabel")
        self.layer_info_label.setWordWrap(True)
        layout.addWidget(self.layer_info_label)

        return group

    def _create_shapefile_creation_section(self):
        """Create shapefile creation section (RESTORED from pendi-mangrove)"""
        group = QGroupBox("ShapeFile Creation")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Geometry type selection
        geom_layout = QHBoxLayout()
        geom_label = QLabel("Geometry Type:")
        geom_label.setObjectName("fieldLabel")

        self.cmbGeometry = QComboBox()
        self.cmbGeometry.setObjectName("inputCombo")
        self.cmbGeometry.addItem("Point")
        self.cmbGeometry.addItem("Polygon")

        geom_layout.addWidget(geom_label)
        geom_layout.addWidget(self.cmbGeometry)
        geom_layout.addStretch()
        layout.addLayout(geom_layout)

        # Shapefile path selection
        shp_path_layout = QHBoxLayout()

        self.btnBrowseShp = QPushButton("...")
        self.btnBrowseShp.setObjectName("browseButton")
        self.btnBrowseShp.setMaximumSize(30, 25)
        self.btnBrowseShp.setToolTip(
            "Tentukan lokasi penyimpanan shapefile sampel yang akan dibuat"
        )

        self.txtShpPath = QLineEdit()
        self.txtShpPath.setObjectName("pathEdit")
        self.txtShpPath.setPlaceholderText("Path Shapefile Sampel")

        self.btnCreateShp = QPushButton("Buat SHP Sampel")
        self.btnCreateShp.setObjectName("primaryButton")
        self.btnCreateShp.setMinimumSize(120, 25)
        self.btnCreateShp.setToolTip("Buat shapefile sampel baru untuk digitasi")

        shp_path_layout.addWidget(self.btnBrowseShp)
        shp_path_layout.addWidget(self.txtShpPath, 1)
        shp_path_layout.addWidget(self.btnCreateShp)
        layout.addLayout(shp_path_layout)

        return group

    def _create_digitization_section(self):
        """Create digitization section (RESTORED from pendi-mangrove)"""
        group = QGroupBox("Digitization Tools")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Info label
        info_label = QLabel(
            "Use these tools to create training samples by digitizing on the map:"
        )
        info_label.setObjectName("infoLabel")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Digitization buttons
        digitization_layout = QHBoxLayout()

        self.btnDigitasiMangrove = QPushButton("Digitize Mangrove")
        self.btnDigitasiMangrove.setObjectName("mangroveButton")
        self.btnDigitasiMangrove.setMinimumSize(150, 40)
        self.btnDigitasiMangrove.setToolTip(
            "Klik untuk menambah sampel Mangrove (klik kanan: berhenti digitasi)"
        )
        # Try to set icon if available
        icon_path = os.path.join(os.path.dirname(__file__), "..", "asset", "tree.svg")
        if os.path.exists(icon_path):
            self.btnDigitasiMangrove.setIcon(QIcon(icon_path))

        self.btnDigitasiNonMangrove = QPushButton("Digitize Non-Mangrove")
        self.btnDigitasiNonMangrove.setObjectName("nonMangroveButton")
        self.btnDigitasiNonMangrove.setMinimumSize(150, 40)
        self.btnDigitasiNonMangrove.setToolTip(
            "Klik untuk menambah sampel Non-Mangrove (klik kanan: berhenti digitasi)"
        )
        # Try to set icon if available
        icon_path = os.path.join(
            os.path.dirname(__file__), "..", "asset", "tree_nonmangrove.svg"
        )
        if os.path.exists(icon_path):
            self.btnDigitasiNonMangrove.setIcon(QIcon(icon_path))

        digitization_layout.addWidget(self.btnDigitasiMangrove)
        digitization_layout.addWidget(self.btnDigitasiNonMangrove)
        digitization_layout.addStretch()
        layout.addLayout(digitization_layout)

        # Digitization status
        self.digitization_status_label = QLabel("Ready for digitization")
        self.digitization_status_label.setObjectName("statusLabel")
        layout.addWidget(self.digitization_status_label)

        return group

    def _create_algorithm_section(self):
        """Create algorithm selection section"""
        group = QGroupBox("Classification Algorithm")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Algorithm selection
        algo_layout = QHBoxLayout()
        algo_label = QLabel("Algorithm:")
        algo_label.setObjectName("fieldLabel")

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.setObjectName("inputCombo")
        self.algorithm_combo.addItems(["Random Forest", "SVM", "Gradient Boosting"])

        algo_layout.addWidget(algo_label)
        algo_layout.addWidget(self.algorithm_combo)
        algo_layout.addStretch()
        layout.addLayout(algo_layout)

        # Test size configuration
        test_layout = QHBoxLayout()
        test_label = QLabel("Test Size (%):")
        test_label.setObjectName("fieldLabel")

        self.spinTestSize = QSpinBox()
        self.spinTestSize.setObjectName("inputSpin")
        self.spinTestSize.setMinimum(10)
        self.spinTestSize.setMaximum(50)
        self.spinTestSize.setValue(20)
        self.spinTestSize.setSuffix("%")

        test_layout.addWidget(test_label)
        test_layout.addWidget(self.spinTestSize)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        # Algorithm description
        self.algorithm_description = QLabel()
        self.algorithm_description.setObjectName("descriptionLabel")
        self.algorithm_description.setWordWrap(True)
        self.algorithm_description.setText(
            self._get_algorithm_description("Random Forest")
        )
        layout.addWidget(self.algorithm_description)

        return group

    def _create_output_section(self):
        """Create output configuration section"""
        group = QGroupBox("Output Configuration")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Output path selection
        output_layout = QHBoxLayout()
        output_label = QLabel("Output Path:")
        output_label.setObjectName("fieldLabel")

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setObjectName("pathEdit")
        self.output_path_edit.setPlaceholderText("Select output path...")

        self.btnBrowseOutput = QPushButton("Browse")
        self.btnBrowseOutput.setObjectName("browseButton")
        self.btnBrowseOutput.setToolTip("Tentukan Folder Penyimpanan Hasil Klasifikasi")

        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_path_edit, 1)
        output_layout.addWidget(self.btnBrowseOutput)
        layout.addLayout(output_layout)

        # Export options
        self.export_shapefile_cb = QCheckBox("Export classification as shapefile")
        self.export_shapefile_cb.setObjectName("advancedCheckBox")
        self.export_shapefile_cb.setChecked(True)
        layout.addWidget(self.export_shapefile_cb)

        self.export_statistics_cb = QCheckBox("Export detailed statistics")
        self.export_statistics_cb.setObjectName("advancedCheckBox")
        self.export_statistics_cb.setChecked(True)
        layout.addWidget(self.export_statistics_cb)

        return group

    def _create_action_buttons_section(self):
        """Create action buttons section"""
        group = QGroupBox("Actions")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Primary action button
        self.btnRunKlasifikasi = QPushButton("Run Classification")
        self.btnRunKlasifikasi.setObjectName("primaryButton")
        self.btnRunKlasifikasi.setMinimumSize(200, 40)
        self.btnRunKlasifikasi.setToolTip(
            "Klik untuk Jalankan proses klasifikasi mangrove sesuai parameter yang dipilih"
        )
        layout.addWidget(self.btnRunKlasifikasi)

        # Progress bar
        self.progressBar = QProgressBar()
        self.progressBar.setObjectName("progressBar")
        self.progressBar.setVisible(False)
        layout.addWidget(self.progressBar)

        # Secondary action buttons
        secondary_layout = QHBoxLayout()

        self.btnViewReport = QPushButton("View Report")
        self.btnViewReport.setObjectName("secondaryButton")
        self.btnViewReport.setEnabled(False)
        self.btnViewReport.setToolTip("Lihat report klasifikasi")

        self.btnSimpanReport = QPushButton("Save Report")
        self.btnSimpanReport.setObjectName("secondaryButton")
        self.btnSimpanReport.setEnabled(False)
        self.btnSimpanReport.setToolTip("Simpan report ke HTML")

        secondary_layout.addWidget(self.btnViewReport)
        secondary_layout.addWidget(self.btnSimpanReport)
        secondary_layout.addStretch()
        layout.addLayout(secondary_layout)

        return group

    def _create_log_section(self):
        """Create log section"""
        group = QGroupBox("Process Log")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)

        self.txtLog = QTextEdit()
        self.txtLog.setObjectName("logTextEdit")
        self.txtLog.setMaximumHeight(150)
        self.txtLog.setReadOnly(True)
        self.txtLog.append("[INFO] Mangrove Classification ready.")

        layout.addWidget(self.txtLog)
        return group

    def setup_buttons(self):
        """Setup button connections (RESTORED from pendi-mangrove)"""
        try:
            # ShapeFile creation buttons
            if hasattr(self, "btnBrowseShp"):
                self.btnBrowseShp.clicked.connect(self.browse_shp_path)

            if hasattr(self, "btnCreateShp"):
                self.btnCreateShp.clicked.connect(self.create_shapefile_roi)

            # Digitization buttons with context menus
            if hasattr(self, "btnDigitasiMangrove"):
                self.btnDigitasiMangrove.clicked.connect(self.start_digitasi_mangrove)
                self.btnDigitasiMangrove.setContextMenuPolicy(Qt.CustomContextMenu)
                self.btnDigitasiMangrove.customContextMenuRequested.connect(
                    self.show_stop_menu
                )

            if hasattr(self, "btnDigitasiNonMangrove"):
                self.btnDigitasiNonMangrove.clicked.connect(
                    self.start_digitasi_non_mangrove
                )
                self.btnDigitasiNonMangrove.setContextMenuPolicy(Qt.CustomContextMenu)
                self.btnDigitasiNonMangrove.customContextMenuRequested.connect(
                    self.show_stop_menu
                )

            # Browse buttons
            if hasattr(self, "btnBrowseRaster"):
                self.btnBrowseRaster.clicked.connect(self.browse_raster)

            if hasattr(self, "btnBrowseROI"):
                self.btnBrowseROI.clicked.connect(self.browse_roi)

            if hasattr(self, "btnBrowseOutput"):
                self.btnBrowseOutput.clicked.connect(self.browse_output_path)

            # Action buttons
            if hasattr(self, "btnRunKlasifikasi"):
                self.btnRunKlasifikasi.clicked.connect(self.run_klasifikasi)

            if hasattr(self, "btnViewReport"):
                self.btnViewReport.clicked.connect(self.show_report)

            if hasattr(self, "btnSimpanReport"):
                self.btnSimpanReport.clicked.connect(self.save_report)

            # Algorithm combo change
            if hasattr(self, "algorithm_combo"):
                self.algorithm_combo.currentTextChanged.connect(
                    self._update_algorithm_description
                )

            # Layer combo changes
            if hasattr(self, "cmbRaster"):
                self.cmbRaster.currentTextChanged.connect(self._update_layer_info)

            if hasattr(self, "cmbROI"):
                self.cmbROI.currentTextChanged.connect(self._update_layer_info)

        except Exception as e:
            self.log_message(f"[ERROR] Failed to setup buttons: {str(e)}")

    # ============ SHAPEFILE CREATION METHODS (RESTORED) ============

    def browse_shp_path(self):
        """Browse for shapefile path"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Shapefile", "", "Shapefile (*.shp)"
            )
            if file_path:
                self.txtShpPath.setText(file_path)
        except Exception as e:
            self.log_message(f"[ERROR] Failed to browse shapefile path: {str(e)}")

    def create_shapefile_roi(self):
        """Create shapefile for ROI (RESTORED from pendi-mangrove)"""
        try:
            shp_path = self.txtShpPath.text().strip()
            if not shp_path:
                self.log_message("[ERROR] Path shapefile belum ditentukan.")
                return

            geom_type = self.cmbGeometry.currentText()
            if geom_type == "Point":
                wkb_type = QgsWkbTypes.Point
            elif geom_type == "Polygon":
                wkb_type = QgsWkbTypes.Polygon
            else:
                self.log_message(
                    "[ERROR] Tipe geometri tidak valid. Pilih Point atau Polygon."
                )
                return

            # Create fields
            fields = QgsFields()
            fields.append(QgsField("class", QVariant.Int))

            # Create shapefile
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

            if not os.path.exists(shp_path):
                self.log_message(
                    f"[ERROR] File shapefile tidak ditemukan setelah pembuatan: {shp_path}"
                )
                return

            self.log_message(f"[INFO] Shapefile ROI berhasil dibuat di: {shp_path}")

            # Load and style the layer
            layer_name = f"Sampel Mangrove {geom_type}"
            layer = QgsVectorLayer(shp_path, layer_name, "ogr")

            if layer.isValid():
                # Apply automatic symbolization: 1 green (Mangrove), 0 red (Non Mangrove)
                categories = []

                # Mangrove symbol (green)
                symbol1 = QgsSymbol.defaultSymbol(layer.geometryType())
                symbol1.setColor(QColor(0, 200, 0))
                categories.append(QgsRendererCategory(1, symbol1, "Mangrove"))

                # Non-Mangrove symbol (red)
                symbol2 = QgsSymbol.defaultSymbol(layer.geometryType())
                symbol2.setColor(QColor(200, 0, 0))
                categories.append(QgsRendererCategory(0, symbol2, "Non Mangrove"))

                renderer = QgsCategorizedSymbolRenderer("class", categories)
                layer.setRenderer(renderer)
                layer.triggerRepaint()

                # Add to project
                QgsProject.instance().addMapLayer(layer)

                self.log_message(
                    f"[INFO] Shapefile ROI berhasil dimuat sebagai '{layer_name}' dan tersimbolisasi di QGIS."
                )

                # Refresh layer lists
                self.populate_layers()

            else:
                self.log_message("[ERROR] Gagal memuat shapefile ROI ke QGIS.")

        except Exception as e:
            self.log_message(f"[ERROR] Failed to create shapefile: {str(e)}")

    # ============ DIGITIZATION METHODS (RESTORED) ============

    def show_stop_menu(self, position):
        """Show context menu for stopping digitization"""
        try:
            menu = QMenu()
            stop_action = menu.addAction("Berhenti Digitasi")
            stop_action.triggered.connect(self.stop_digitasi)
            menu.exec_(self.sender().mapToGlobal(position))
        except Exception as e:
            self.log_message(f"[ERROR] Failed to show stop menu: {str(e)}")

    def stop_digitasi(self):
        """Stop digitization mode and reset button colors"""
        try:
            self.set_active_mode(None)

            # Return to pan mode
            self.iface.actionPan().trigger()

            # Commit changes on active layer
            layer = self.iface.activeLayer()
            if layer and layer.isEditable():
                layer.commitChanges()

            self.log_message("[INFO] Mode digitasi dihentikan manual.")

        except Exception as e:
            self.log_message(f"[ERROR] Gagal menghentikan digitasi: {str(e)}")

    def set_active_mode(self, mode):
        """Set active digitization mode and update button colors (RESTORED from pendi-mangrove)"""
        try:
            self.active_digitasi_mode = mode

            # Update button colors based on active mode
            if hasattr(self, "btnDigitasiMangrove"):
                if mode == "mangrove":
                    self.btnDigitasiMangrove.setStyleSheet(
                        "background-color: #2ecc40; color: white; font-weight: bold;"
                    )
                    self.digitization_status_label.setText(
                        "Digitizing MANGROVE areas (Class = 1)"
                    )
                    self.digitization_status_label.setStyleSheet(
                        "color: #2ecc40; font-weight: bold;"
                    )
                else:
                    self.btnDigitasiMangrove.setStyleSheet("")

            if hasattr(self, "btnDigitasiNonMangrove"):
                if mode == "non_mangrove":
                    self.btnDigitasiNonMangrove.setStyleSheet(
                        "background-color: #ff4136; color: white; font-weight: bold;"
                    )
                    self.digitization_status_label.setText(
                        "Digitizing NON-MANGROVE areas (Class = 0)"
                    )
                    self.digitization_status_label.setStyleSheet(
                        "color: #ff4136; font-weight: bold;"
                    )
                else:
                    self.btnDigitasiNonMangrove.setStyleSheet("")

            if mode is None:
                self.digitization_status_label.setText("Ready for digitization")
                self.digitization_status_label.setStyleSheet("")

        except Exception as e:
            self.log_message(f"[ERROR] Failed to set active mode: {str(e)}")

    def start_digitasi_mangrove(self):
        """Start mangrove digitization mode (RESTORED from pendi-mangrove)"""
        try:
            layer = self.get_selected_roi_layer()
            if not layer:
                self.log_message("[ERROR] Layer ROI belum dimuat.")
                return

            if not layer.isEditable():
                layer.startEditing()

            # Set active mode
            self.set_active_mode("mangrove")

            self.log_message(
                "[INFO] Mode digitasi Mangrove aktif. Tambahkan fitur, kolom class otomatis 1."
            )

            # Set default value for class field
            idx = layer.fields().indexFromName("class")
            if idx != -1:
                layer.setDefaultValueDefinition(idx, QgsDefaultValue("1"))

            # Setup feature added handler
            def on_feature_added(fid):
                layer.changeAttributeValue(fid, idx, 1)
                QApplication.restoreOverrideCursor()

            # Disconnect previous connections
            try:
                layer.featureAdded.disconnect()
            except:
                pass

            layer.featureAdded.connect(on_feature_added)

            # Setup editing stopped handler
            def on_editing_stopped():
                self.deactivate_digitasi_mode()
                QApplication.restoreOverrideCursor()

            try:
                layer.editingStopped.disconnect(on_editing_stopped)
            except:
                pass

            layer.editingStopped.connect(on_editing_stopped)

            QApplication.setOverrideCursor(Qt.CrossCursor)

            # Activate appropriate digitization tool
            if layer.geometryType() == QgsWkbTypes.PointGeometry:
                self.iface.actionAddFeature().trigger()
                self.log_message(
                    "[INFO] Mode digitasi Point aktif. Klik pada peta untuk menambahkan point."
                )
            elif layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                self.iface.actionAddFeature().trigger()
                self.log_message(
                    "[INFO] Mode digitasi Polygon aktif. Klik berurutan untuk membuat polygon, klik kanan untuk selesai."
                )

        except Exception as e:
            self.log_message(f"[ERROR] Failed to start mangrove digitization: {str(e)}")

    def start_digitasi_non_mangrove(self):
        """Start non-mangrove digitization mode (RESTORED from pendi-mangrove)"""
        try:
            layer = self.get_selected_roi_layer()
            if not layer:
                self.log_message("[ERROR] Layer ROI belum dimuat.")
                return

            if not layer.isEditable():
                layer.startEditing()

            # Set active mode
            self.set_active_mode("non_mangrove")

            self.log_message(
                "[INFO] Mode digitasi Non-Mangrove aktif. Tambahkan fitur, kolom class otomatis 0."
            )

            # Set default value for class field
            idx = layer.fields().indexFromName("class")
            if idx != -1:
                layer.setDefaultValueDefinition(idx, QgsDefaultValue("0"))

            # Setup feature added handler
            def on_feature_added(fid):
                layer.changeAttributeValue(fid, idx, 0)
                QApplication.restoreOverrideCursor()

            # Disconnect previous connections
            try:
                layer.featureAdded.disconnect()
            except:
                pass

            layer.featureAdded.connect(on_feature_added)

            # Setup editing stopped handler
            def on_editing_stopped():
                self.deactivate_digitasi_mode()
                QApplication.restoreOverrideCursor()

            try:
                layer.editingStopped.disconnect(on_editing_stopped)
            except:
                pass

            layer.editingStopped.connect(on_editing_stopped)

            QApplication.setOverrideCursor(Qt.CrossCursor)

            # Activate appropriate digitization tool
            if layer.geometryType() == QgsWkbTypes.PointGeometry:
                self.iface.actionAddFeature().trigger()
                self.log_message(
                    "[INFO] Mode digitasi Point aktif. Klik pada peta untuk menambahkan point."
                )
            elif layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                self.iface.actionAddFeature().trigger()
                self.log_message(
                    "[INFO] Mode digitasi Polygon aktif. Klik berurutan untuk membuat polygon, klik kanan untuk selesai."
                )

        except Exception as e:
            self.log_message(
                f"[ERROR] Failed to start non-mangrove digitization: {str(e)}"
            )

    def deactivate_digitasi_mode(self, silent=False):
        """Deactivate digitization mode and reset button colors (RESTORED from pendi-mangrove)"""
        try:
            self.active_digitasi_mode = None

            if hasattr(self, "btnDigitasiMangrove"):
                self.btnDigitasiMangrove.setStyleSheet("")

            if hasattr(self, "btnDigitasiNonMangrove"):
                self.btnDigitasiNonMangrove.setStyleSheet("")

            if hasattr(self, "digitization_status_label"):
                self.digitization_status_label.setText("Ready for digitization")
                self.digitization_status_label.setStyleSheet("")

            if not silent:
                self.log_message(
                    "[INFO] Mode digitasi dinonaktifkan, warna tombol kembali normal."
                )

        except Exception as e:
            self.log_message(
                f"[ERROR] Failed to deactivate digitization mode: {str(e)}"
            )

    # ============ LAYER MANAGEMENT METHODS (RESTORED) ============

    def populate_layers(self):
        """Populate layer dropdowns automatically (RESTORED from pendi-mangrove)"""
        try:
            if hasattr(self, "cmbRaster"):
                self.cmbRaster.clear()
                self.cmbRaster.addItem("Select raster layer...", None)
                for layer in QgsProject.instance().mapLayers().values():
                    if isinstance(layer, QgsRasterLayer) and layer.isValid():
                        if layer.bandCount() >= 3:
                            self.cmbRaster.addItem(layer.name(), layer.id())

            if hasattr(self, "cmbROI"):
                self.cmbROI.clear()
                self.cmbROI.addItem("Select ROI layer...", None)
                for layer in QgsProject.instance().mapLayers().values():
                    if isinstance(layer, QgsVectorLayer) and layer.isValid():
                        field_names = [field.name().lower() for field in layer.fields()]
                        if "class" in field_names:
                            self.cmbROI.addItem(layer.name(), layer.id())

            self.log_message(
                "[INFO] Dropdown layer raster dan ROI diperbarui otomatis."
            )

        except Exception as e:
            self.log_message(f"[ERROR] Failed to populate layers: {str(e)}")

    def get_selected_raster_layer(self):
        """Get selected raster layer"""
        try:
            if not hasattr(self, "cmbRaster"):
                return None

            layer_id = self.cmbRaster.currentData()
            if layer_id:
                return QgsProject.instance().mapLayer(layer_id)
            return None
        except Exception as e:
            self.log_message(f"[ERROR] Failed to get raster layer: {str(e)}")
            return None

    def get_selected_roi_layer(self):
        """Get selected ROI layer"""
        try:
            if not hasattr(self, "cmbROI"):
                return None

            layer_id = self.cmbROI.currentData()
            if layer_id:
                layer = QgsProject.instance().mapLayer(layer_id)
                if layer:
                    self.iface.setActiveLayer(layer)
                return layer
            return None
        except Exception as e:
            self.log_message(f"[ERROR] Failed to get ROI layer: {str(e)}")
            return None

    # ============ BROWSE METHODS ============

    def browse_raster(self):
        """Browse for raster file"""
        try:
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
                    self.log_message(
                        f"[INFO] Raster loaded: {os.path.basename(file_path)}"
                    )
                else:
                    self.log_message("[ERROR] Failed to load raster file")
        except Exception as e:
            self.log_message(f"[ERROR] Failed to browse raster: {str(e)}")

    def browse_roi(self):
        """Browse for ROI file"""
        try:
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
                    self.log_message(
                        f"[INFO] ROI layer loaded: {os.path.basename(file_path)}"
                    )
                else:
                    self.log_message("[ERROR] Failed to load ROI file")
        except Exception as e:
            self.log_message(f"[ERROR] Failed to browse ROI: {str(e)}")

    def browse_output_path(self):
        """Browse for output path"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Select Output Path", "", "GeoTIFF Files (*.tif);;All Files (*)"
            )
            if file_path:
                self.output_path_edit.setText(file_path)
        except Exception as e:
            self.log_message(f"[ERROR] Failed to browse output path: {str(e)}")

    # ============ CLASSIFICATION METHODS ============

    def run_klasifikasi(self):
        """Run classification process"""
        try:
            # Get parameters
            raster_layer = self.get_selected_raster_layer()
            roi_layer = self.get_selected_roi_layer()
            output_path = self.output_path_edit.text().strip()
            method = self.algorithm_combo.currentText()
            test_size = (
                self.spinTestSize.value() / 100.0
            )  # Convert percentage to fraction

            # Validate inputs
            if not raster_layer:
                self.log_message("[ERROR] Layer raster belum dipilih atau tidak valid.")
                return

            if not roi_layer:
                self.log_message("[ERROR] Layer ROI belum dipilih atau tidak valid.")
                return

            if not output_path:
                self.log_message(
                    "[WARNING] Path output kosong, hasil akan disimpan sementara."
                )

            self.log_message(f"[INFO] Metode klasifikasi: {method}")

            # Disable UI during processing
            self.btnRunKlasifikasi.setEnabled(False)
            self.progressBar.setVisible(True)
            self.progressBar.setValue(0)

            # Import and run classification based on method
            if method == "SVM":
                from ..core.mangrove_classifier import run_svm_classification

                self.log_message("[INFO] Proses SVM dimulai...")
                result = run_svm_classification(
                    raster_layer, roi_layer, output_path, self, test_size
                )
            elif method == "Random Forest":
                from ..core.mangrove_classifier import run_rf_classification

                self.log_message("[INFO] Proses Random Forest dimulai...")
                result = run_rf_classification(
                    raster_layer, roi_layer, output_path, self, test_size
                )
            elif method == "Gradient Boosting":
                from ..core.mangrove_classifier import run_gb_classification

                self.log_message("[INFO] Proses Gradient Boosting dimulai...")
                result = run_gb_classification(
                    raster_layer, roi_layer, output_path, self, test_size
                )
            else:
                self.log_message(
                    f"[ERROR] Metode klasifikasi '{method}' tidak dikenali."
                )
                return

            # Enable report buttons if successful
            if result:
                self.btnViewReport.setEnabled(True)
                self.btnSimpanReport.setEnabled(True)
                self.log_message("[INFO] Klasifikasi selesai! Report tersedia.")

        except Exception as e:
            self.log_message(f"[ERROR] Classification failed: {str(e)}")
        finally:
            # Re-enable UI
            self.btnRunKlasifikasi.setEnabled(True)
            self.progressBar.setVisible(False)

    def show_report(self):
        """Show classification report"""
        try:
            self.log_message("[INFO] Menampilkan report klasifikasi...")
            # Implementation for showing report
        except Exception as e:
            self.log_message(f"[ERROR] Failed to show report: {str(e)}")

    def save_report(self):
        """Save classification report"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Report", "", "HTML Files (*.html);;All Files (*)"
            )
            if file_path:
                self.log_message(f"[INFO] Report saved to: {file_path}")
        except Exception as e:
            self.log_message(f"[ERROR] Failed to save report: {str(e)}")

    # ============ UTILITY METHODS ============

    def _get_algorithm_description(self, algorithm):
        """Get algorithm description"""
        descriptions = {
            "Random Forest": "Ensemble method using multiple decision trees. Robust and handles overfitting well. Good for large datasets with mixed data types.",
            "Gradient Boosting": "Sequential ensemble method that builds models iteratively. Often achieves high accuracy but can overfit on small datasets.",
            "SVM": "Support Vector Machine with RBF kernel. Effective for complex, non-linear classification problems with smaller datasets.",
        }
        return descriptions.get(algorithm, "Select an algorithm to see description")

    def _update_algorithm_description(self, algorithm):
        """Update algorithm description when selection changes"""
        if hasattr(self, "algorithm_description"):
            self.algorithm_description.setText(
                self._get_algorithm_description(algorithm)
            )

    def _update_layer_info(self):
        """Update layer information display"""
        try:
            raster_layer = self.get_selected_raster_layer()
            roi_layer = self.get_selected_roi_layer()

            info_parts = []

            if raster_layer:
                bands = raster_layer.bandCount()
                width = raster_layer.width()
                height = raster_layer.height()
                info_parts.append(f"Raster: {bands} bands, {width}x{height} pixels")

            if roi_layer:
                feature_count = roi_layer.featureCount()
                info_parts.append(f"Training samples: {feature_count} features")

            info_text = (
                " | ".join(info_parts)
                if info_parts
                else "Select layers to view information"
            )

            if hasattr(self, "layer_info_label"):
                self.layer_info_label.setText(info_text)

        except Exception as e:
            self.log_message(f"[ERROR] Failed to update layer info: {str(e)}")

    def log_message(self, message):
        """Add message to log"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"

            if hasattr(self, "txtLog"):
                self.txtLog.append(formatted_message)
                # Auto-scroll to bottom
                self.txtLog.verticalScrollBar().setValue(
                    self.txtLog.verticalScrollBar().maximum()
                )

            # Also log to QGIS
            QgsMessageLog.logMessage(
                formatted_message, "MangroveClassification", Qgis.Info
            )

        except Exception as e:
            print(f"Logging error: {str(e)}")

    def apply_stylesheet(self):
        """Apply enhanced styling"""
        style = """
        /* Main dialog styling */
        #mainContainer {{
            background-color: #5E765F; /* Fallback color */
            border-radius: 20px;
        }}
        
        /* Title styling */
        QLabel#titleLabel {
            font-size: 24px;
            font-weight: bold;
            color: #2c5530;
            margin: 10px 0;
        }
        
        QLabel#subtitleLabel {
            font-size: 14px;
            color: #6c757d;
            margin-bottom: 20px;
        }
        
        /* Section groups */
        QGroupBox#sectionGroup {
            font-weight: bold;
            border: 2px solid #d1ecf1;
            border-radius: 8px;
            margin-top: 10px;
            padding-top: 15px;
            background-color: white;
        }
        
        QGroupBox#sectionGroup::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 10px;
            color: #0c5460;
            background-color: white;
        }
        
        /* Input fields */
        QComboBox#inputCombo, QLineEdit#pathEdit {
            padding: 8px 12px;
            border: 2px solid #ced4da;
            border-radius: 6px;
            background-color: white;
            font-size: 13px;
        }
        
        QComboBox#inputCombo:focus, QLineEdit#pathEdit:focus {
            border-color: #80bdff;
            outline: none;
        }
        
        /* Buttons */
        QPushButton#primaryButton {
            background-color: #28a745;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        
        QPushButton#primaryButton:hover {
            background-color: #218838;
        }
        
        QPushButton#primaryButton:pressed {
            background-color: #1e7e34;
        }
        
        QPushButton#secondaryButton {
            background-color: #6c757d;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: bold;
        }
        
        QPushButton#secondaryButton:hover {
            background-color: #5a6268;
        }
        
        QPushButton#browseButton {
            background-color: #17a2b8;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: bold;
        }
        
        QPushButton#browseButton:hover {
            background-color: #138496;
        }
        
        /* Specialized buttons */
        QPushButton#mangroveButton {
            background-color: #28a745;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 14px;
        }
        
        QPushButton#mangroveButton:hover {
            background-color: #218838;
        }
        
        QPushButton#nonMangroveButton {
            background-color: #dc3545;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 14px;
        }
        
        QPushButton#nonMangroveButton:hover {
            background-color: #c82333;
        }
        
        /* Labels */
        QLabel#fieldLabel {
            font-weight: bold;
            color: #495057;
            min-width: 120px;
        }
        
        QLabel#infoLabel {
            color: #6c757d;
            font-style: italic;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }
        
        QLabel#statusLabel {
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            background-color: #e9ecef;
        }
        
        QLabel#descriptionLabel {
            color: #495057;
            padding: 10px;
            background-color: #f1f3f4;
            border-left: 4px solid #007bff;
            border-radius: 4px;
        }
        
        /* Progress bar */
        QProgressBar#progressBar {
            border: 2px solid #ced4da;
            border-radius: 6px;
            text-align: center;
            font-weight: bold;
        }
        
        QProgressBar#progressBar::chunk {
            background-color: #28a745;
            border-radius: 4px;
        }
        
        /* Text edit for logs */
        QTextEdit#logTextEdit {
            border: 2px solid #ced4da;
            border-radius: 6px;
            background-color: #f8f9fa;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        
        /* Checkboxes */
        QCheckBox#advancedCheckBox {
            font-weight: bold;
            color: #495057;
        }
        
        QCheckBox#advancedCheckBox::indicator:checked {
            background-color: #28a745;
        }
        
        /* Spin boxes */
        QSpinBox#inputSpin {
            padding: 6px;
            border: 2px solid #ced4da;
            border-radius: 4px;
            background-color: white;
        }
        """

        self.setStyleSheet(style)


# Alias for backward compatibility
MangroveClassificationDialog = CompleteMangroveClassificationDialog
