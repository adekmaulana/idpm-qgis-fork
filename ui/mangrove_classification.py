from typing import Optional
import os
import csv
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
)
from PyQt5.QtCore import QVariant
from PyQt5.QtGui import QColor

from qgis.gui import QgisInterface
from .base_dialog import BaseDialog
from .themed_message_box import ThemedMessageBox
from .loading import LoadingDialog
from ..core.mangrove_classifier import MangroveClassificationTask
from ..config import Config


class MangroveClassificationDialog(BaseDialog):
    """Dialog for mangrove classification workflow with updated UI design."""

    def __init__(self, iface: QgisInterface, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.iface = iface
        self.loading_dialog = None
        self.active_task = None
        self.latest_results = None

        self.init_mangrove_ui()
        self.populate_layers()

    def init_mangrove_ui(self):
        """Initialize the mangrove classification UI with updated design."""
        self.setWindowTitle("Mangrove Classification")

        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(40, 20, 40, 40)
        main_layout.setSpacing(0)

        # Top bar
        top_bar_layout = self._create_top_bar()
        main_layout.addLayout(top_bar_layout)
        main_layout.addSpacing(20)

        # Title section - more compact
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)
        title_label = QLabel("Mangrove Classification")
        title_label.setObjectName("mainTitle")
        subtitle_label = QLabel(
            "Classify mangrove and non-mangrove areas using machine learning"
        )
        subtitle_label.setObjectName("mainSubtitle")
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        main_layout.addLayout(title_layout)
        main_layout.addSpacing(30)

        # Main content in two columns
        content_layout = QHBoxLayout()
        content_layout.setSpacing(30)

        # Left column
        left_column = self._create_left_column()
        content_layout.addWidget(left_column, 3)

        # Right column
        right_column = self._create_right_column()
        content_layout.addWidget(right_column, 2)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()

        self.apply_stylesheet()

    def _safe_file_dialog(self, dialog_type, title, filters, default_suffix=""):
        """
        Safely handle file dialogs to prevent dialog hiding issues.

        Args:
            dialog_type: 'save' or 'open'
            title: Dialog title
            filters: File filters string
            default_suffix: Default file extension

        Returns:
            Selected file path or None if cancelled
        """
        # Store current position and ensure dialog is visible
        current_pos = self.pos()
        self.raise_()
        self.activateWindow()

        try:
            # Open appropriate dialog
            if dialog_type == "save":
                path, _ = QFileDialog.getSaveFileName(self, title, "", filters)
            else:  # open
                path, _ = QFileDialog.getOpenFileName(self, title, "", filters)

            # Ensure dialog returns to proper state
            self.show()
            self.raise_()
            self.activateWindow()
            self.move(current_pos)  # Restore position if moved

            return path if path else None

        except Exception as e:
            # Fallback: ensure dialog is visible
            self.show()
            self.raise_()
            self.activateWindow()
            self.log_text.append(f"File dialog error: {e}")
            return None

    def _create_top_bar(self) -> QHBoxLayout:
        """Create the top navigation bar."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.back_button = QPushButton("← Back to Menu")
        self.back_button.setObjectName("backButton")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.clicked.connect(self.accept)

        layout.addWidget(self.back_button)
        layout.addStretch()
        layout.addLayout(self._create_window_controls())

        return layout

    def _create_left_column(self) -> QWidget:
        """Create the left column with input controls."""
        column = QWidget()
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(25)

        # Input section
        input_section = self._create_input_section()
        column_layout.addWidget(input_section)

        # Digitization section
        digitization_section = self._create_digitization_section()
        column_layout.addWidget(digitization_section)

        # Layer selection section
        layer_section = self._create_layer_selection_section()
        column_layout.addWidget(layer_section)

        # Log section
        log_section = self._create_log_section()
        column_layout.addWidget(log_section)

        return column

    def _create_right_column(self) -> QWidget:
        """Create the right column with process controls."""
        column = QWidget()
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(25)

        # Process section
        process_section = self._create_process_section()
        column_layout.addWidget(process_section)

        # Output section
        output_section = self._create_output_section()
        column_layout.addWidget(output_section)

        # Report section
        report_section = self._create_report_section()
        column_layout.addWidget(report_section)

        column_layout.addStretch()

        return column

    def _create_input_section(self) -> QWidget:
        """Create the input section."""
        section = QWidget()
        section.setObjectName("sectionWidget")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(15)

        # Section header
        header = QLabel("Input")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # Geometry type and create shapefile
        geometry_layout = QHBoxLayout()
        geometry_layout.setSpacing(10)

        self.geometry_combo = QComboBox()
        self.geometry_combo.addItems(["Point", "Polygon"])
        self.geometry_combo.setObjectName("inputCombo")
        self.geometry_combo.setFixedHeight(32)

        self.browse_shp_button = QPushButton("Select File")
        self.browse_shp_button.setObjectName("selectButton")
        self.browse_shp_button.clicked.connect(self.browse_shp_path)
        self.browse_shp_button.setFixedHeight(32)

        geometry_layout.addWidget(self.geometry_combo, 1)
        geometry_layout.addWidget(self.browse_shp_button, 1)

        layout.addLayout(geometry_layout)

        # Path input (hidden by default, shown when file selected)
        self.shp_path_input = QLineEdit()
        self.shp_path_input.setPlaceholderText("Choose file save location")
        self.shp_path_input.setObjectName("pathInput")
        self.shp_path_input.setVisible(False)
        layout.addWidget(self.shp_path_input)

        # Create shapefile button
        self.create_shp_button = QPushButton("Create Sample Shapefile")
        self.create_shp_button.setObjectName("createButton")
        self.create_shp_button.clicked.connect(self.create_sample_shapefile)
        self.create_shp_button.setFixedHeight(35)
        layout.addWidget(self.create_shp_button)

        return section

    def _create_digitization_section(self) -> QWidget:
        """Create the digitization buttons section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Digitization buttons
        digit_layout = QHBoxLayout()
        digit_layout.setSpacing(15)

        self.digitize_mangrove_button = QPushButton("      Digitize Mangrove Sample")
        self.digitize_mangrove_button.setObjectName("mangroveButton")
        self.digitize_mangrove_button.clicked.connect(self.start_digitizing_mangrove)
        self.digitize_mangrove_button.setFixedHeight(45)

        # Add tree icon
        mangrove_icon_path = os.path.join(Config.ASSETS_PATH, "images", "tree.svg")
        if os.path.exists(mangrove_icon_path):
            self.digitize_mangrove_button.setIcon(QIcon(mangrove_icon_path))
            self.digitize_mangrove_button.setIconSize(QSize(20, 20))

        self.digitize_non_mangrove_button = QPushButton(
            "      Digitize Non-Mangrove Sample"
        )
        self.digitize_non_mangrove_button.setObjectName("nonMangroveButton")
        self.digitize_non_mangrove_button.clicked.connect(
            self.start_digitizing_non_mangrove
        )
        self.digitize_non_mangrove_button.setFixedHeight(45)

        # Add tree icon for non-mangrove (red version)
        if os.path.exists(mangrove_icon_path):
            self.digitize_non_mangrove_button.setIcon(QIcon(mangrove_icon_path))
            self.digitize_non_mangrove_button.setIconSize(QSize(20, 20))

        digit_layout.addWidget(self.digitize_mangrove_button)
        digit_layout.addWidget(self.digitize_non_mangrove_button)

        layout.addLayout(digit_layout)

        return section

    def _create_layer_selection_section(self) -> QWidget:
        """Create the layer selection section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # Raster layer selection
        raster_widget = QWidget()
        raster_widget.setObjectName("layerWidget")
        raster_layout = QVBoxLayout(raster_widget)
        raster_layout.setContentsMargins(20, 15, 20, 20)
        raster_layout.setSpacing(10)

        raster_label = QLabel("Raster Layer")
        raster_label.setObjectName("layerLabel")
        raster_layout.addWidget(raster_label)

        raster_input_layout = QHBoxLayout()
        raster_input_layout.setSpacing(10)

        self.raster_combo = QComboBox()
        self.raster_combo.setObjectName("inputCombo")
        self.raster_combo.setFixedHeight(32)

        self.browse_raster_button = QPushButton("Select File")
        self.browse_raster_button.setObjectName("selectButton")
        self.browse_raster_button.clicked.connect(self.browse_raster)
        self.browse_raster_button.setFixedHeight(32)

        raster_input_layout.addWidget(self.raster_combo, 2)
        raster_input_layout.addWidget(self.browse_raster_button, 1)

        raster_layout.addLayout(raster_input_layout)
        layout.addWidget(raster_widget)

        # ROI layer selection
        roi_widget = QWidget()
        roi_widget.setObjectName("layerWidget")
        roi_layout = QVBoxLayout(roi_widget)
        roi_layout.setContentsMargins(20, 15, 20, 20)
        roi_layout.setSpacing(10)

        roi_label = QLabel("Sample Shapefile")
        roi_label.setObjectName("layerLabel")
        roi_layout.addWidget(roi_label)

        roi_input_layout = QHBoxLayout()
        roi_input_layout.setSpacing(10)

        self.roi_combo = QComboBox()
        self.roi_combo.setObjectName("inputCombo")
        self.roi_combo.setFixedHeight(32)

        self.browse_roi_button = QPushButton("Select File")
        self.browse_roi_button.setObjectName("selectButton")
        self.browse_roi_button.clicked.connect(self.browse_roi)
        self.browse_roi_button.setFixedHeight(32)

        roi_input_layout.addWidget(self.roi_combo, 2)
        roi_input_layout.addWidget(self.browse_roi_button, 1)

        roi_layout.addLayout(roi_input_layout)
        layout.addWidget(roi_widget)

        return section

    def _create_log_section(self) -> QWidget:
        """Create the log section."""
        section = QWidget()
        section.setObjectName("sectionWidget")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(10)

        header = QLabel("Process Log")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setMaximumHeight(120)
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Process logs will appear here...")

        layout.addWidget(self.log_text)

        return section

    def _create_process_section(self) -> QWidget:
        """Create the process section."""
        section = QWidget()
        section.setObjectName("sectionWidget")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(15)

        header = QLabel("Process")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # Method and test size in grid layout
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        # Classification method
        method_label = QLabel("Classification Method")
        method_label.setObjectName("paramLabel")
        grid_layout.addWidget(method_label, 0, 0)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["SVM", "Random Forest", "Gradient Boosting"])
        self.method_combo.setObjectName("inputCombo")
        self.method_combo.setFixedHeight(32)
        grid_layout.addWidget(self.method_combo, 0, 1)

        # Test percentage
        test_label = QLabel("Test Percentage")
        test_label.setObjectName("paramLabel")
        grid_layout.addWidget(test_label, 1, 0)

        self.test_size_spin = QSpinBox()
        self.test_size_spin.setRange(20, 50)
        self.test_size_spin.setValue(30)
        self.test_size_spin.setSuffix("%")
        self.test_size_spin.setObjectName("inputSpin")
        self.test_size_spin.setFixedHeight(32)
        grid_layout.addWidget(self.test_size_spin, 1, 1)

        layout.addLayout(grid_layout)

        return section

    def _create_output_section(self) -> QWidget:
        """Create the output section."""
        section = QWidget()
        section.setObjectName("sectionWidget")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(15)

        header = QLabel("Output")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        # Output location
        location_label = QLabel("Classification Result Location")
        location_label.setObjectName("paramLabel")
        layout.addWidget(location_label)

        # Output path
        output_layout = QHBoxLayout()
        output_layout.setSpacing(10)

        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Choose file save location")
        self.output_path_input.setObjectName("pathInput")
        self.output_path_input.setFixedHeight(32)

        self.browse_output_button = QPushButton("Select File")
        self.browse_output_button.setObjectName("selectButton")
        self.browse_output_button.clicked.connect(self.browse_output_path)
        self.browse_output_button.setFixedHeight(32)

        output_layout.addWidget(self.output_path_input, 2)
        output_layout.addWidget(self.browse_output_button, 1)

        layout.addLayout(output_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        # Run button
        self.run_button = QPushButton("Run Classification")
        self.run_button.setObjectName("runButton")
        self.run_button.clicked.connect(self.run_classification)
        self.run_button.setFixedHeight(40)
        layout.addWidget(self.run_button)

        return section

    def _create_report_section(self) -> QWidget:
        """Create the report section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.view_report_button = QPushButton("View Report")
        self.view_report_button.setObjectName("reportButton")
        self.view_report_button.clicked.connect(self.view_detailed_report)
        self.view_report_button.setEnabled(False)
        self.view_report_button.setFixedHeight(35)

        self.save_report_button = QPushButton("Save Report")
        self.save_report_button.setObjectName("saveReportButton")
        self.save_report_button.clicked.connect(self.save_report)
        self.save_report_button.setEnabled(False)
        self.save_report_button.setFixedHeight(35)

        button_layout.addWidget(self.view_report_button)
        button_layout.addWidget(self.save_report_button)

        layout.addLayout(button_layout)

        return section

    # Keep all the existing methods from the previous implementation
    def populate_layers(self):
        """Populate layer combo boxes with loaded QGIS layers."""
        # Clear existing items and add default options
        self.raster_combo.clear()
        self.roi_combo.clear()

        # Count available layers
        raster_count = 0
        vector_count = 0

        # Populate raster layers (minimum 3 bands for classification)
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer) and layer.bandCount() >= 3:
                self.raster_combo.addItem(
                    f"{layer.name()} ({layer.bandCount()} bands)", layer.id()
                )
                raster_count += 1

        # Add default option for raster if no layers found
        if raster_count == 0:
            self.raster_combo.addItem("No suitable raster layers found", None)
        else:
            self.raster_combo.insertItem(
                0, f"Choose from {raster_count} loaded raster layers"
            )
            self.raster_combo.setCurrentIndex(0)

        # Populate vector layers with 'class' field for samples
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                field_names = [field.name().lower() for field in layer.fields()]
                if "class" in field_names:
                    geom_type = layer.geometryType()
                    if geom_type == QgsWkbTypes.PointGeometry:
                        geom_name = "Point"
                    elif geom_type == QgsWkbTypes.PolygonGeometry:
                        geom_name = "Polygon"
                    else:
                        geom_name = "Line"

                    feature_count = layer.featureCount()
                    self.roi_combo.addItem(
                        f"{layer.name()} ({geom_name}, {feature_count} features)",
                        layer.id(),
                    )
                    vector_count += 1

        # Add default option for vector if no layers found
        if vector_count == 0:
            self.roi_combo.addItem("No sample layers found (need 'class' field)", None)
        else:
            self.roi_combo.insertItem(
                0, f"Choose from {vector_count} loaded sample layers"
            )
            self.roi_combo.setCurrentIndex(0)

        # Log the layer status
        self.log_text.append(
            f"Found {raster_count} raster layers and {vector_count} sample layers"
        )

        # Connect to layer changes for automatic updates
        QgsProject.instance().layersAdded.connect(self.populate_layers)
        QgsProject.instance().layersRemoved.connect(self.populate_layers)

    def browse_shp_path(self):
        """Browse for shapefile path."""
        path = self._safe_file_dialog("save", "Save Shapefile", "Shapefile (*.shp)")

        if path:
            self.shp_path_input.setText(path)
            self.shp_path_input.setVisible(True)
            self.log_text.append(f"Shapefile path selected: {path}")
        else:
            self.log_text.append("Shapefile selection cancelled")

    def create_sample_shapefile(self):
        """Create a new shapefile for samples."""
        shp_path = self.shp_path_input.text().strip()
        if not shp_path:
            ThemedMessageBox.show_message(
                self, QMessageBox.Warning, "Error", "Please specify a shapefile path."
            )
            return

        geom_type = self.geometry_combo.currentText()
        if geom_type == "Point":
            wkb_type = QgsWkbTypes.Point
        else:
            wkb_type = QgsWkbTypes.Polygon

        self.log_text.append(f"Creating {geom_type} shapefile...")

        # Remove existing file
        if os.path.exists(shp_path):
            try:
                os.remove(shp_path)
                self.log_text.append("Removed existing file")
            except Exception as e:
                ThemedMessageBox.show_message(
                    self,
                    QMessageBox.Critical,
                    "Error",
                    f"Cannot remove existing file: {e}",
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
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Error",
                f"Failed to create shapefile: {writer.errorMessage()}",
            )
            return

        del writer

        # Load into QGIS
        layer_name = f"Mangrove Samples ({geom_type})"
        layer = QgsVectorLayer(shp_path, layer_name, "ogr")

        if layer.isValid():
            # Apply symbology
            categories = []
            symbol1 = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol1.setColor(QColor(0, 200, 0))
            categories.append(QgsRendererCategory(1, symbol1, "Mangrove"))

            symbol2 = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol2.setColor(QColor(200, 0, 0))
            categories.append(QgsRendererCategory(0, symbol2, "Non-Mangrove"))

            renderer = QgsCategorizedSymbolRenderer("class", categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

            QgsProject.instance().addMapLayer(layer)
            self.populate_layers()

            self.log_text.append(f"Sample shapefile created and loaded: {layer_name}")

            ThemedMessageBox.show_message(
                self,
                QMessageBox.Information,
                "Success",
                f"Sample shapefile created and loaded: {layer_name}",
            )
        else:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Critical,
                "Error",
                "Failed to load shapefile into QGIS.",
            )

    def start_digitizing_mangrove(self):
        """Start digitizing mangrove samples."""
        self._start_digitizing(1, "mangrove")

    def start_digitizing_non_mangrove(self):
        """Start digitizing non-mangrove samples."""
        self._start_digitizing(0, "non-mangrove")

    def _start_digitizing(self, class_value: int, class_name: str):
        """Start digitizing with specified class value."""
        layer_name = self.roi_combo.currentText()
        if not layer_name or layer_name == "Choose file":
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Error",
                "Please select a sample layer first.",
            )
            return

        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            ThemedMessageBox.show_message(
                self, QMessageBox.Warning, "Error", "Selected sample layer not found."
            )
            return

        layer = layers[0]
        self.iface.setActiveLayer(layer)

        if not layer.isEditable():
            layer.startEditing()

        # Set default value for class field
        idx = layer.fields().indexFromName("class")
        if idx != -1:
            layer.setDefaultValueDefinition(idx, QgsDefaultValue(str(class_value)))

        # Update button appearance
        if class_value == 1:
            self.digitize_mangrove_button.setStyleSheet(
                """
                QPushButton#mangroveButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 2px solid #45a049;
                }
            """
            )
            self.digitize_non_mangrove_button.setStyleSheet("")
        else:
            self.digitize_non_mangrove_button.setStyleSheet(
                """
                QPushButton#nonMangroveButton {
                    background-color: #f44336;
                    color: white;
                    border: 2px solid #da190b;
                }
            """
            )
            self.digitize_mangrove_button.setStyleSheet("")

        # Activate add feature tool
        self.iface.actionAddFeature().trigger()

        self.log_text.append(f"Digitizing mode active for {class_name} samples")

        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Digitizing Mode",
            f"Digitizing mode active for {class_name} samples. Add features to the map.",
        )

    def browse_raster(self):
        """Browse for raster file."""
        path = self._safe_file_dialog(
            "open",
            "Select Raster",
            "Raster Files (*.tif *.img *.asc *.bil *.nc);;All Files (*)",
        )

        if path:
            layer_name = os.path.basename(path)
            layer = QgsRasterLayer(path, layer_name)
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self.populate_layers()
                # Select the newly added layer
                for i in range(self.raster_combo.count()):
                    if self.raster_combo.itemText(i) == layer_name:
                        self.raster_combo.setCurrentIndex(i)
                        break
                self.log_text.append(f"Raster loaded: {layer_name}")
            else:
                self.log_text.append(f"Failed to load raster: {layer_name}")
        else:
            self.log_text.append("Raster selection cancelled")

    def browse_roi(self):
        """Browse for ROI/sample file."""
        path = self._safe_file_dialog(
            "open", "Select Sample File", "Shapefile (*.shp);;All Files (*)"
        )

        if path:
            layer_name = os.path.basename(path)
            layer = QgsVectorLayer(path, layer_name, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
                self.populate_layers()
                self.log_text.append(f"Sample layer loaded: {layer_name}")
            else:
                self.log_text.append(f"Failed to load sample layer: {layer_name}")
        else:
            self.log_text.append("Sample file selection cancelled")

    def browse_output_path(self):
        """Browse for output path."""
        path = self._safe_file_dialog(
            "save", "Save Classification Result", "GeoTIFF (*.tif);;All Files (*)"
        )

        if path:
            self.output_path_input.setText(path)
            self.log_text.append(f"Output path set: {path}")
        else:
            self.log_text.append("Output path selection cancelled")

    def run_classification(self):
        """Run the classification process."""
        # Validate inputs
        raster_layer = self._get_selected_raster_layer()
        roi_layer = self._get_selected_roi_layer()
        output_path = self.output_path_input.text().strip()
        method = self.method_combo.currentText()
        test_size = self.test_size_spin.value() / 100.0

        if not raster_layer:
            ThemedMessageBox.show_message(
                self, QMessageBox.Warning, "Error", "Please select a raster layer."
            )
            return

        if not roi_layer:
            ThemedMessageBox.show_message(
                self, QMessageBox.Warning, "Error", "Please select a sample layer."
            )
            return

        if not output_path:
            ThemedMessageBox.show_message(
                self, QMessageBox.Warning, "Error", "Please specify an output path."
            )
            return

        self.log_text.append(f"Starting {method} classification...")
        self.log_text.append(f"Test size: {self.test_size_spin.value()}%")

        # Create and run task
        self.active_task = MangroveClassificationTask(
            raster_layer, roi_layer, output_path, method, test_size
        )

        self.active_task.classificationFinished.connect(
            self._on_classification_finished
        )
        self.active_task.errorOccurred.connect(self._on_classification_error)
        self.active_task.progressChanged.connect(self._update_progress)

        # Show progress
        self.progress_bar.setVisible(True)
        self.run_button.setEnabled(False)
        self.run_button.setText("Processing...")

        QgsApplication.taskManager().addTask(self.active_task)

    def _get_selected_raster_layer(self):
        """Get the selected raster layer."""
        current_data = self.raster_combo.currentData()
        if not current_data:
            return None

        # Find layer by ID
        for layer in QgsProject.instance().mapLayers().values():
            if layer.id() == current_data and isinstance(layer, QgsRasterLayer):
                return layer
        return None

    def _get_selected_roi_layer(self):
        """Get the selected ROI layer."""
        current_data = self.roi_combo.currentData()
        if not current_data:
            return None

        # Find layer by ID
        for layer in QgsProject.instance().mapLayers().values():
            if layer.id() == current_data and isinstance(layer, QgsVectorLayer):
                return layer
        return None

    def _update_progress(self, value):
        """Update progress bar."""
        self.progress_bar.setValue(value)

    def _on_classification_finished(self, output_path: str, results: dict, method: str):
        """Handle classification completion."""
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Classification")

        self.latest_results = results

        # Display results
        cm = results["confusion_matrix"]
        acc = results["accuracy"]
        n_samples = results["n_samples"]

        self.log_text.append(f"Classification completed!")
        self.log_text.append(f"Method: {method}")
        self.log_text.append(f"Accuracy: {acc:.3f} ({acc*100:.1f}%)")
        self.log_text.append(f"Total samples: {n_samples}")

        self.view_report_button.setEnabled(True)
        self.save_report_button.setEnabled(True)

        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Success",
            f"Classification completed with {acc*100:.1f}% accuracy!",
        )

    def _on_classification_error(self, error_msg: str):
        """Handle classification error."""
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Classification")

        self.log_text.append(f"Error: {error_msg}")

        ThemedMessageBox.show_message(
            self, QMessageBox.Critical, "Error", f"Classification failed: {error_msg}"
        )

    def view_detailed_report(self):
        """View detailed classification report."""
        if not self.latest_results:
            return

        cm = self.latest_results["confusion_matrix"]
        acc = self.latest_results["accuracy"]
        report = self.latest_results["classification_report"]
        method = self.latest_results["method"]
        n_samples = self.latest_results["n_samples"]

        detailed_report = f"""
MANGROVE CLASSIFICATION REPORT
===============================

Method: {method}
Total Samples: {n_samples}
Overall Accuracy: {acc:.4f} ({acc*100:.2f}%)

CONFUSION MATRIX:
{cm}

True Positives (TP): {cm[1][1]}
True Negatives (TN): {cm[0][0]}
False Positives (FP): {cm[0][1]}
False Negatives (FN): {cm[1][0]}

CLASSIFICATION REPORT:
{report}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        ThemedMessageBox.show_message(
            self, QMessageBox.Information, "Detailed Report", detailed_report
        )

    def save_report(self):
        """Save classification report to file."""
        if not self.latest_results:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            "",
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)",
        )

        if path:
            try:
                cm = self.latest_results["confusion_matrix"]
                acc = self.latest_results["accuracy"]
                report = self.latest_results["classification_report"]
                method = self.latest_results["method"]
                n_samples = self.latest_results["n_samples"]

                if path.lower().endswith(".csv"):
                    with open(path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["Metric", "Value"])
                        writer.writerow(["Method", method])
                        writer.writerow(["Total Samples", n_samples])
                        writer.writerow(["Accuracy", f"{acc:.4f}"])
                        writer.writerow(["True Positives", cm[1][1]])
                        writer.writerow(["True Negatives", cm[0][0]])
                        writer.writerow(["False Positives", cm[0][1]])
                        writer.writerow(["False Negatives", cm[1][0]])
                else:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(
                            f"""MANGROVE CLASSIFICATION REPORT
===============================

Method: {method}
Total Samples: {n_samples}
Overall Accuracy: {acc:.4f} ({acc*100:.2f}%)

CONFUSION MATRIX:
{cm}

True Positives (TP): {cm[1][1]}
True Negatives (TN): {cm[0][0]}
False Positives (FP): {cm[0][1]}
False Negatives (FN): {cm[1][0]}

CLASSIFICATION REPORT:
{report}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                        )

                self.log_text.append(f"Report saved to: {path}")

                ThemedMessageBox.show_message(
                    self, QMessageBox.Information, "Success", f"Report saved to: {path}"
                )

            except Exception as e:
                ThemedMessageBox.show_message(
                    self, QMessageBox.Critical, "Error", f"Failed to save report: {e}"
                )

    def apply_stylesheet(self):
        """Apply the updated stylesheet matching the design."""
        qss = """
            #mainContainer {
                background-color: #FAFBFC;
                border-radius: 20px;
            }
            QLabel {
                color: #2C3E50;
                font-family: "Segoe UI", "Helvetica", "Arial", sans-serif;
            }
            #mainTitle {
                font-size: 24px;
                font-weight: bold;
                color: #2C3E50;
                margin-bottom: 5px;
            }
            #mainSubtitle {
                font-size: 14px;
                color: #7F8C8D;
                margin-bottom: 0px;
            }
            #backButton {
                background-color: transparent;
                color: #3498DB;
                border: none;
                font-size: 14px;
                padding: 8px 0px;
                text-align: left;
            }
            #backButton:hover {
                color: #2980B9; 
                text-decoration: underline;
            }
            #minimizeButton, #maximizeButton, #closeButton {
                background-color: transparent;
                color: #7F8C8D;
                border: none;
                font-family: "Arial", sans-serif;
                font-weight: bold;
                border-radius: 4px;
            }
            #minimizeButton:hover, #maximizeButton:hover, #closeButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
                color: #2C3E50;
            }
            #sectionWidget {
                background-color: white;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
            #layerWidget {
                background-color: white;
                border: 1px solid #E8E8E8;
                border-radius: 12px;
            }
            #sectionHeader {
                font-size: 16px;
                font-weight: bold;
                color: #2C3E50;
                margin-bottom: 5px;
            }
            #layerLabel {
                font-size: 13px;
                font-weight: 500;
                color: #34495E;
                margin-bottom: 5px;
            }
            #paramLabel {
                font-size: 13px;
                font-weight: 500;
                color: #34495E;
            }
            #inputCombo {
                background-color: #F8F9FA;
                border: 1px solid #E1E5E9;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                color: #495057;
            }
            #inputCombo:focus {
                border-color: #80BDFF;
                outline: none;
                box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
            }
            #inputCombo::drop-down {
                border: none;
                width: 20px;
            }
            #inputSpin {
                background-color: #F8F9FA;
                border: 1px solid #E1E5E9;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                color: #495057;
            }
            #inputSpin:focus {
                border-color: #80BDFF;
                outline: none;
            }
            #pathInput {
                background-color: #F8F9FA;
                border: 1px solid #E1E5E9;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                color: #6C757D;
                font-style: italic;
            }
            #pathInput:focus {
                border-color: #80BDFF;
                outline: none;
            }
            #selectButton {
                background-color: #F8F9FA;
                color: #495057;
                border: 1px solid #E1E5E9;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            #selectButton:hover {
                background-color: #E9ECEF;
                border-color: #ADB5BD;
            }
            #createButton {
                background-color: #28A745;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 14px;
            }
            #createButton:hover {
                background-color: #218838;
            }
            #mangroveButton {
                background-color: #E8F5E8;
                color: #2E7D32;
                border: 2px solid #C8E6C9;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 14px;
                text-align: left;
            }
            #mangroveButton:hover {
                background-color: #C8E6C9;
                border-color: #A5D6A7;
            }
            #nonMangroveButton {
                background-color: #FFEBEE;
                color: #C62828;
                border: 2px solid #FFCDD2;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 14px;
                text-align: left;
            }
            #nonMangroveButton:hover {
                background-color: #FFCDD2;
                border-color: #EF9A9A;
            }
            #runButton {
                background-color: #007BFF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: 600;
                font-size: 15px;
            }
            #runButton:hover {
                background-color: #0056B3;
            }
            #runButton:disabled {
                background-color: #CED4DA;
                color: #6C757D;
            }
            #reportButton {
                background-color: #F8F9FA;
                color: #495057;
                border: 1px solid #DEE2E6;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
            }
            #reportButton:hover {
                background-color: #E9ECEF;
                border-color: #ADB5BD;
            }
            #reportButton:disabled {
                background-color: #F8F9FA;
                color: #CED4DA;
                border-color: #E9ECEF;
            }
            #saveReportButton {
                background-color: #28A745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
            }
            #saveReportButton:hover {
                background-color: #218838;
            }
            #saveReportButton:disabled {
                background-color: #CED4DA;
                color: #6C757D;
            }
            #logText {
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 6px;
                padding: 8px;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 11px;
                color: #495057;
                line-height: 1.4;
            }
            #progressBar {
                border: none;
                border-radius: 4px;
                background-color: #E9ECEF;
                text-align: center;
            }
            #progressBar::chunk {
                background-color: #007BFF;
                border-radius: 4px;
            }
        """
        self.setStyleSheet(qss)
