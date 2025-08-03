"""
Updated Mangrove Classification Dialog with latest pendi-mangrove improvements
and idpm-qgis-fork UI/UX design.

Version 1.1.0 - Incorporates latest machine learning improvements
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
from ..core.mangrove_classifier import EnhancedMangroveClassificationTask
from ..config import Config


class MangroveClassificationDialog(BaseDialog):
    """
    Enhanced Mangrove Classification Dialog with improved UI/UX and latest ML algorithms.

    Features:
    - Modern card-based interface design from idpm-qgis-fork
    - Enhanced machine learning algorithms from pendi-mangrove v1.1.0
    - Support for SVM, Random Forest, and Gradient Boosting
    - Feature importance analysis
    - Advanced reporting and statistics
    - Improved error handling and validation
    """

    def __init__(self, iface: QgisInterface, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.iface = iface
        self.loading_dialog = None
        self.active_task = None
        self.latest_results = None

        # Initialize UI and populate data
        self.init_mangrove_ui()
        self.populate_layers()

    def init_mangrove_ui(self):
        """Initialize the enhanced mangrove classification UI with modern design."""
        # Main layout with proper margins matching idpm design
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(40, 20, 40, 40)
        main_layout.setSpacing(0)

        # Top bar with back button and window controls
        top_bar_layout = self._create_top_bar()
        main_layout.addLayout(top_bar_layout)
        main_layout.addSpacing(20)

        # Title section with modern typography
        title_layout = self._create_title_section()
        main_layout.addLayout(title_layout)
        main_layout.addSpacing(30)

        # Main content in responsive two-column layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(30)

        # Left column - Configuration panel
        left_column = self._create_configuration_panel()
        content_layout.addWidget(left_column, 3)

        # Right column - Results and logs panel
        right_column = self._create_results_panel()
        content_layout.addWidget(right_column, 2)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()

        # Apply modern styling
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

    def _create_title_section(self):
        """Create modern title section."""
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)

        title_label = QLabel("Mangrove Classification")
        title_label.setObjectName("mainTitle")

        subtitle_label = QLabel(
            "Advanced machine learning classification for mangrove and non-mangrove areas"
        )
        subtitle_label.setObjectName("mainSubtitle")

        # Version badge
        # version_label = QLabel("v1.1.0 - Enhanced Edition")
        # version_label.setObjectName("versionBadge")

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        # title_layout.addWidget(version_label)

        return title_layout

    def _create_configuration_panel(self):
        """Create enhanced configuration panel with modern card design."""
        panel = QFrame()
        panel.setObjectName("configPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)

        # Input layers section
        input_section = self._create_input_layers_section()
        layout.addWidget(input_section)

        # Algorithm configuration section
        algorithm_section = self._create_algorithm_section()
        layout.addWidget(algorithm_section)

        # Advanced parameters section
        advanced_section = self._create_advanced_parameters_section()
        layout.addWidget(advanced_section)

        # Output configuration section
        output_section = self._create_output_section()
        layout.addWidget(output_section)

        # Action buttons
        buttons_section = self._create_action_buttons()
        layout.addWidget(buttons_section)

        layout.addStretch()
        return panel

    def _create_input_layers_section(self):
        """Create input layers configuration section."""
        group = QGroupBox("Input Layers")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Raster layer selection
        raster_layout = QHBoxLayout()
        raster_label = QLabel("Satellite Image:")
        raster_label.setObjectName("fieldLabel")
        self.raster_combo = QComboBox()
        self.raster_combo.setObjectName("inputCombo")
        raster_layout.addWidget(raster_label)
        raster_layout.addWidget(self.raster_combo, 1)
        layout.addLayout(raster_layout)

        # ROI layer selection
        roi_layout = QHBoxLayout()
        roi_label = QLabel("Training Samples:")
        roi_label.setObjectName("fieldLabel")
        self.roi_combo = QComboBox()
        self.roi_combo.setObjectName("inputCombo")
        roi_layout.addWidget(roi_label)
        roi_layout.addWidget(self.roi_combo, 1)
        layout.addLayout(roi_layout)

        # Layer info display
        self.layer_info_label = QLabel("Select layers to view information")
        self.layer_info_label.setObjectName("infoLabel")
        self.layer_info_label.setWordWrap(True)
        layout.addWidget(self.layer_info_label)

        return group

    def _create_algorithm_section(self):
        """Create enhanced algorithm selection section."""
        group = QGroupBox("Classification Algorithm")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Algorithm selection
        algo_layout = QHBoxLayout()
        algo_label = QLabel("Method:")
        algo_label.setObjectName("fieldLabel")
        self.method_combo = QComboBox()
        self.method_combo.setObjectName("inputCombo")
        self.method_combo.addItems(["Random Forest", "Gradient Boosting", "SVM"])
        algo_layout.addWidget(algo_label)
        algo_layout.addWidget(self.method_combo, 1)
        layout.addLayout(algo_layout)

        # Algorithm description
        self.algo_description = QLabel(self._get_algorithm_description("Random Forest"))
        self.algo_description.setObjectName("descriptionLabel")
        self.algo_description.setWordWrap(True)
        layout.addWidget(self.algo_description)

        # Connect signal for dynamic description
        self.method_combo.currentTextChanged.connect(self._update_algorithm_description)

        return group

    def _create_advanced_parameters_section(self):
        """Create advanced parameters section."""
        group = QGroupBox("Advanced Parameters")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Test size parameter
        test_layout = QHBoxLayout()
        test_label = QLabel("Test Size (%):")
        test_label.setObjectName("fieldLabel")
        self.test_size_spin = QSpinBox()
        self.test_size_spin.setObjectName("parameterSpin")
        self.test_size_spin.setRange(10, 50)
        self.test_size_spin.setValue(20)
        self.test_size_spin.setSuffix("%")
        test_layout.addWidget(test_label)
        test_layout.addWidget(self.test_size_spin)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        # Feature importance analysis
        self.feature_importance_cb = QCheckBox("Enable Feature Importance Analysis")
        self.feature_importance_cb.setObjectName("advancedCheckBox")
        self.feature_importance_cb.setChecked(True)
        layout.addWidget(self.feature_importance_cb)

        # Cross-validation
        self.cross_validation_cb = QCheckBox("Enable Cross-Validation")
        self.cross_validation_cb.setObjectName("advancedCheckBox")
        self.cross_validation_cb.setChecked(False)
        layout.addWidget(self.cross_validation_cb)

        return group

    def _create_output_section(self):
        """Create output configuration section."""
        group = QGroupBox("Output Configuration")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Output path selection
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setObjectName("pathEdit")
        self.output_path_edit.setPlaceholderText("Select output path...")
        self.output_browse_btn = QPushButton("Browse")
        self.output_browse_btn.setObjectName("browseButton")
        self.output_browse_btn.clicked.connect(self._browse_output_path)
        output_layout.addWidget(self.output_path_edit, 1)
        output_layout.addWidget(self.output_browse_btn)
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

    def _create_action_buttons(self):
        """Create action buttons section."""
        buttons_widget = QWidget()
        layout = QVBoxLayout(buttons_widget)
        layout.setSpacing(15)

        # Primary action button
        self.run_button = QPushButton("Run Classification")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self._run_classification)
        layout.addWidget(self.run_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Secondary action buttons
        secondary_layout = QHBoxLayout()

        self.view_report_button = QPushButton("View Report")
        self.view_report_button.setObjectName("secondaryButton")
        self.view_report_button.setEnabled(False)
        self.view_report_button.clicked.connect(self.view_detailed_report)

        self.save_report_button = QPushButton("Save Report")
        self.save_report_button.setObjectName("secondaryButton")
        self.save_report_button.setEnabled(False)
        self.save_report_button.clicked.connect(self.save_report)

        secondary_layout.addWidget(self.view_report_button)
        secondary_layout.addWidget(self.save_report_button)
        layout.addLayout(secondary_layout)

        return buttons_widget

    def _create_results_panel(self):
        """Create results and logs panel."""
        panel = QFrame()
        panel.setObjectName("resultsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Results summary section
        results_group = QGroupBox("Classification Results")
        results_group.setObjectName("sectionGroup")
        results_layout = QVBoxLayout(results_group)

        self.results_summary = QLabel("No classification results yet")
        self.results_summary.setObjectName("resultsLabel")
        self.results_summary.setWordWrap(True)
        results_layout.addWidget(self.results_summary)

        layout.addWidget(results_group)

        # Process log section
        log_group = QGroupBox("Process Log")
        log_group.setObjectName("sectionGroup")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("logText")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)
        layout.addStretch()

        return panel

    def _get_algorithm_description(self, algorithm):
        """Get description for selected algorithm."""
        descriptions = {
            "Random Forest": "Ensemble method using multiple decision trees. Excellent for handling high-dimensional data and provides feature importance rankings.",
            "Gradient Boosting": "Sequential ensemble method that builds models iteratively. Often provides highest accuracy but may require more computation time.",
            "SVM": "Support Vector Machine with RBF kernel. Effective for complex, non-linear classification problems with smaller datasets.",
        }
        return descriptions.get(algorithm, "Select an algorithm to see description")

    def _update_algorithm_description(self, algorithm):
        """Update algorithm description when selection changes."""
        self.algo_description.setText(self._get_algorithm_description(algorithm))

    def populate_layers(self):
        """Populate layer comboboxes with available layers."""
        # Clear existing items
        self.raster_combo.clear()
        self.roi_combo.clear()

        # Add default option
        self.raster_combo.addItem("Select raster layer...", None)
        self.roi_combo.addItem("Select vector layer...", None)

        # Populate with available layers
        for layer_id, layer in QgsProject.instance().mapLayers().items():
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                self.raster_combo.addItem(layer.name(), layer_id)
            elif isinstance(layer, QgsVectorLayer) and layer.isValid():
                # Check if layer has appropriate fields for training
                fields = layer.fields()
                if any(
                    field.name().lower() in ["class", "label", "type"]
                    for field in fields
                ):
                    self.roi_combo.addItem(layer.name(), layer_id)

        # Connect signals for layer info updates
        self.raster_combo.currentTextChanged.connect(self._update_layer_info)
        self.roi_combo.currentTextChanged.connect(self._update_layer_info)

    def _update_layer_info(self):
        """Update layer information display."""
        raster_layer = self._get_selected_raster_layer()
        roi_layer = self._get_selected_roi_layer()

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
        self.layer_info_label.setText(info_text)

    def _browse_output_path(self):
        """Browse for output file path."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output Path",
            "",
            "GeoTIFF Files (*.tif);;All Files (*)",
        )
        if path:
            self.output_path_edit.setText(path)

    def _run_classification(self):
        """Run the enhanced classification process."""
        # Validate inputs
        if not self._validate_inputs():
            return

        # Get parameters
        raster_layer = self._get_selected_raster_layer()
        roi_layer = self._get_selected_roi_layer()
        output_path = self.output_path_edit.text().strip()
        method = self.method_combo.currentText()
        test_size = self.test_size_spin.value() / 100.0

        # Additional parameters
        feature_importance = self.feature_importance_cb.isChecked()
        cross_validation = self.cross_validation_cb.isChecked()
        export_shapefile = self.export_shapefile_cb.isChecked()
        export_statistics = self.export_statistics_cb.isChecked()

        self.log_text.append(f"Starting enhanced {method} classification...")
        self.log_text.append(f"Test size: {test_size*100:.1f}%")
        self.log_text.append(
            f"Feature importance: {'Enabled' if feature_importance else 'Disabled'}"
        )

        # Create enhanced classification task
        self.active_task = EnhancedMangroveClassificationTask(
            raster_layer=raster_layer,
            roi_layer=roi_layer,
            output_path=output_path,
            method=method,
            test_size=test_size,
            feature_importance=feature_importance,
            cross_validation=cross_validation,
            export_shapefile=export_shapefile,
            export_statistics=export_statistics,
        )

        # Connect signals
        self.active_task.classificationFinished.connect(
            self._on_classification_finished
        )
        self.active_task.errorOccurred.connect(self._on_classification_error)
        self.active_task.progressChanged.connect(self._update_progress)
        self.active_task.logMessage.connect(self._add_log_message)

        # Update UI state
        self.progress_bar.setVisible(True)
        self.run_button.setEnabled(False)
        self.run_button.setText("Processing...")

        # Start task
        QgsApplication.taskManager().addTask(self.active_task)

    def _validate_inputs(self):
        """Enhanced input validation."""
        if not self._get_selected_raster_layer():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Error",
                "Please select a satellite image layer.",
            )
            return False

        if not self._get_selected_roi_layer():
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Error",
                "Please select a training samples layer.",
            )
            return False

        if not self.output_path_edit.text().strip():
            ThemedMessageBox.show_message(
                self, QMessageBox.Warning, "Error", "Please specify an output path."
            )
            return False

        # Validate ROI layer has appropriate class field
        roi_layer = self._get_selected_roi_layer()
        fields = roi_layer.fields()
        class_fields = [
            field.name()
            for field in fields
            if field.name().lower() in ["class", "label", "type"]
        ]

        if not class_fields:
            ThemedMessageBox.show_message(
                self,
                QMessageBox.Warning,
                "Error",
                "Training samples layer must contain a 'class', 'label', or 'type' field.",
            )
            return False

        return True

    def _get_selected_raster_layer(self):
        """Get the selected raster layer."""
        current_data = self.raster_combo.currentData()
        if not current_data:
            return None

        for layer in QgsProject.instance().mapLayers().values():
            if layer.id() == current_data and isinstance(layer, QgsRasterLayer):
                return layer
        return None

    def _get_selected_roi_layer(self):
        """Get the selected ROI layer."""
        current_data = self.roi_combo.currentData()
        if not current_data:
            return None

        for layer in QgsProject.instance().mapLayers().values():
            if layer.id() == current_data and isinstance(layer, QgsVectorLayer):
                return layer
        return None

    def _update_progress(self, value):
        """Update progress bar."""
        self.progress_bar.setValue(value)

    def _add_log_message(self, message):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def _on_classification_finished(self, results: dict):
        """Handle classification completion with enhanced results."""
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Classification")

        self.latest_results = results

        # Update results summary
        accuracy = results.get("accuracy", 0)
        method = results.get("method", "Unknown")
        n_samples = results.get("n_samples", 0)

        summary = f"""
Classification completed successfully!

Method: {method}
Overall Accuracy: {accuracy*100:.2f}%
Total Samples: {n_samples}
Feature Count: {results.get("n_features", "N/A")}
        """.strip()

        if "feature_importance" in results:
            summary += f"\nFeature Importance: Available"

        self.results_summary.setText(summary)

        # Enable report buttons
        self.view_report_button.setEnabled(True)
        self.save_report_button.setEnabled(True)

        # Show completion message
        ThemedMessageBox.show_message(
            self,
            QMessageBox.Information,
            "Success",
            f"Classification completed with {accuracy*100:.1f}% accuracy!",
        )

    def _on_classification_error(self, error_msg: str):
        """Handle classification error."""
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self.run_button.setText("Run Classification")

        self.log_text.append(f"ERROR: {error_msg}")

        ThemedMessageBox.show_message(
            self, QMessageBox.Critical, "Error", f"Classification failed: {error_msg}"
        )

    def view_detailed_report(self):
        """View detailed classification report with enhanced metrics."""
        if not self.latest_results:
            return

        # Generate comprehensive report
        report = self._generate_detailed_report()

        # Create and show report dialog
        from .report_viewer import ReportViewerDialog

        report_dialog = ReportViewerDialog(report, self)
        report_dialog.exec_()

    def save_report(self):
        """Save enhanced classification report to file."""
        if not self.latest_results:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            f"mangrove_classification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "HTML Files (*.html);;Text Files (*.txt);;CSV Files (*.csv);;JSON Files (*.json)",
        )

        if path:
            try:
                if path.lower().endswith(".html"):
                    self._save_html_report(path)
                elif path.lower().endswith(".json"):
                    self._save_json_report(path)
                elif path.lower().endswith(".csv"):
                    self._save_csv_report(path)
                else:
                    self._save_text_report(path)

                self.log_text.append(f"Report saved to: {path}")
                ThemedMessageBox.show_message(
                    self, QMessageBox.Information, "Success", f"Report saved to: {path}"
                )

            except Exception as e:
                ThemedMessageBox.show_message(
                    self, QMessageBox.Critical, "Error", f"Failed to save report: {e}"
                )

    def _generate_detailed_report(self):
        """Generate comprehensive classification report."""
        results = self.latest_results
        cm = results["confusion_matrix"]
        accuracy = results["accuracy"]
        method = results["method"]
        n_samples = results["n_samples"]

        report = {
            "title": "Enhanced Mangrove Classification Report",
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "accuracy": accuracy,
            "n_samples": n_samples,
            "confusion_matrix": cm.tolist() if hasattr(cm, "tolist") else cm,
            "classification_report": results.get("classification_report", ""),
            "feature_importance": results.get("feature_importance", []),
            "cross_validation_scores": results.get("cv_scores", []),
            "model_parameters": results.get("model_parameters", {}),
        }

        return report

    def _save_html_report(self, path):
        """Save HTML formatted report."""
        results = self.latest_results
        html_content = self._generate_html_report_content(results)

        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _save_json_report(self, path):
        """Save JSON formatted report."""
        report = self._generate_detailed_report()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def _save_csv_report(self, path):
        """Save CSV formatted report."""
        results = self.latest_results
        cm = results["confusion_matrix"]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Method", results["method"]])
            writer.writerow(["Accuracy", f"{results['accuracy']:.4f}"])
            writer.writerow(["Total Samples", results["n_samples"]])
            writer.writerow(["True Positives", cm[1][1]])
            writer.writerow(["True Negatives", cm[0][0]])
            writer.writerow(["False Positives", cm[0][1]])
            writer.writerow(["False Negatives", cm[1][0]])

    def _save_text_report(self, path):
        """Save text formatted report."""
        results = self.latest_results
        report_text = self._generate_text_report_content(results)

        with open(path, "w", encoding="utf-8") as f:
            f.write(report_text)

    def apply_stylesheet(self):
        """Apply enhanced stylesheet matching idpm-qgis-fork design."""
        top_bar_style = """
            #backButton { background-color: transparent; color: #274423; border: none; font-size: 14px; padding: 8px; }
            #backButton:hover { text-decoration: underline; }
            #minimizeButton, #maximizeButton, #closeButton {
                background-color: transparent; color: #274423; border: none;
                font-family: "Arial", sans-serif; font-weight: bold; border-radius: 4px;
            }
            """
        qss = f"""
            /* Main container with modern design */
            #mainContainer {{
                background-color: #F9FAFC; /* Fallback color */
                border-radius: 20px;
            }}

            /* Top bar styling */
            {top_bar_style}

            /* Title styling */
            #mainTitle {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 5px;
            }}

            #mainSubtitle {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 14px;
                color: #7f8c8d;
                margin-bottom: 10px;
            }}

            #versionBadge {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 12px;
                color: #5E765F;
                background-color: #e8f5e8;
                padding: 4px 12px;
                border-radius: 12px;
                margin-bottom: 5px;
                width: fit-content;
            }}

            /* Panel styling */
            #configPanel, #resultsPanel {{
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e9ecef;
            }}

            /* Group box styling */
            QGroupBox {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 600;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: white;
            }}

            /* Input field styling */
            #fieldLabel {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 500;
                color: #495057;
                min-width: 120px;
            }}

            #inputCombo, #pathEdit {{
                font-family: 'Montserrat', Arial, sans-serif;
                padding: 8px 12px;
                border: 2px solid #e9ecef;
                border-radius: 6px;
                background-color: white;
                min-height: 20px;
            }}

            #inputCombo:focus, #pathEdit:focus {{
                border-color: #5E765F;
                outline: none;
            }}

            /* Button styling */
            #primaryButton {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 600;
                font-size: 14px;
                color: white;
                background-color: #5E765F;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                min-height: 20px;
            }}

            #primaryButton:hover {{
                background-color: #4a5d4b;
            }}

            #primaryButton:pressed {{
                background-color: #3d4a3e;
            }}

            #primaryButton:disabled {{
                background-color: #95a5a6;
            }}

            #secondaryButton {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 500;
                color: #5E765F;
                background-color: white;
                border: 2px solid #5E765F;
                border-radius: 6px;
                padding: 8px 16px;
                min-height: 20px;
            }}

            #secondaryButton:hover {{
                background-color: #f8f9fa;
            }}

            #browseButton {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 500;
                color: #5E765F;
                background-color: #e8f5e8;
                border: 1px solid #5E765F;
                border-radius: 6px;
                padding: 8px 16px;
                min-height: 20px;
            }}

            /* Progress bar styling */
            #progressBar {{
                border: 1px solid #e9ecef;
                border-radius: 6px;
                text-align: center;
                background-color: #f8f9fa;
            }}

            #progressBar::chunk {{
                background-color: #5E765F;
                border-radius: 5px;
            }}

            /* Log text styling */
            #logText {{
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 12px;
            }}

            /* Info labels */
            #infoLabel, #descriptionLabel {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 12px;
                color: #6c757d;
                background-color: #f8f9fa;
                padding: 8px;
                border-radius: 4px;
            }}

            #resultsLabel {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 13px;
                color: #2c3e50;
                background-color: #e8f5e8;
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid #5E765F;
            }}

            /* Checkbox styling */
            #advancedCheckBox {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 13px;
                color: #495057;
                spacing: 8px;
            }}

            #advancedCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #e9ecef;
                background-color: white;
            }}

            #advancedCheckBox::indicator:checked {{
                background-color: #5E765F;
                border-color: #5E765F;
            }}

            /* Spinbox styling */
            #parameterSpin {{
                font-family: 'Montserrat', Arial, sans-serif;
                padding: 6px 8px;
                border: 2px solid #e9ecef;
                border-radius: 6px;
                background-color: white;
                min-width: 80px;
            }}

            #parameterSpin:focus {{
                border-color: #5E765F;
            }}
        """
        self.setStyleSheet(qss)
