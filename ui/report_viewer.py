"""
Enhanced Report Viewer for Mangrove Classification Results
Provides comprehensive visualization of classification results with modern UI design
"""

from typing import Dict, Any, Optional
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QFrame,
    QGridLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QGroupBox,
)
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QPainter
from PyQt5.QtCore import Qt, QSize

from .base_dialog import BaseDialog


class ReportViewerDialog(BaseDialog):
    """
    Modern report viewer for enhanced mangrove classification results.

    Features:
    - Tabbed interface for different report sections
    - Interactive charts and visualizations
    - Detailed metrics and statistics
    - Export capabilities
    - Modern card-based design
    """

    def __init__(self, report_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.report_data = report_data
        self.setMinimumSize(1000, 700)

        self.init_report_ui()
        self.populate_report_data()

    def init_report_ui(self):
        """Initialize the modern report viewer UI."""
        self.setWindowTitle("Classification Report Viewer")

        # Main layout
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(30, 20, 30, 30)
        main_layout.setSpacing(0)

        # Top bar
        top_bar_layout = self._create_top_bar()
        main_layout.addLayout(top_bar_layout)
        main_layout.addSpacing(20)

        # Title section
        title_layout = self._create_title_section()
        main_layout.addLayout(title_layout)
        main_layout.addSpacing(25)

        # Main content area with tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("reportTabs")

        # Create tabs
        self._create_overview_tab()
        self._create_metrics_tab()
        self._create_features_tab()
        self._create_statistics_tab()
        self._create_raw_data_tab()

        main_layout.addWidget(self.tab_widget)

        # Action buttons
        button_layout = self._create_action_buttons()
        main_layout.addLayout(button_layout)

        self.apply_stylesheet()

    def _create_title_section(self):
        """Create report title section."""
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)

        title_label = QLabel("Classification Report")
        title_label.setObjectName("reportTitle")

        method = self.report_data.get("method", "Unknown")
        accuracy = self.report_data.get("accuracy", 0)
        timestamp = self.report_data.get("timestamp", "")

        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%B %d, %Y at %I:%M %p")
            except:
                formatted_time = timestamp
        else:
            formatted_time = "Unknown time"

        subtitle_label = QLabel(
            f"{method} • {accuracy*100:.1f}% Accuracy • {formatted_time}"
        )
        subtitle_label.setObjectName("reportSubtitle")

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        return title_layout

    def _create_overview_tab(self):
        """Create overview tab with summary cards."""
        overview_widget = QScrollArea()
        overview_content = QWidget()
        layout = QVBoxLayout(overview_content)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Key metrics cards
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(15)

        # Accuracy card
        accuracy_card = self._create_metric_card(
            "Overall Accuracy",
            f"{self.report_data.get('accuracy', 0)*100:.2f}%",
            "Model's overall classification accuracy",
            "#2ecc71",
        )
        metrics_grid.addWidget(accuracy_card, 0, 0)

        # Samples card
        samples_card = self._create_metric_card(
            "Training Samples",
            str(self.report_data.get("n_samples", 0)),
            "Total samples used for training",
            "#3498db",
        )
        metrics_grid.addWidget(samples_card, 0, 1)

        # Features card
        features_card = self._create_metric_card(
            "Features",
            str(self.report_data.get("n_features", 0)),
            "Number of input features (bands)",
            "#9b59b6",
        )
        metrics_grid.addWidget(features_card, 0, 2)

        # Method card
        method_card = self._create_metric_card(
            "Algorithm",
            self.report_data.get("method", "Unknown"),
            "Classification method used",
            "#e67e22",
        )
        metrics_grid.addWidget(method_card, 1, 0)

        # Cross-validation card (if available)
        cv_scores = self.report_data.get("cv_scores", [])
        if cv_scores:
            cv_mean = self.report_data.get("cv_mean", 0)
            cv_card = self._create_metric_card(
                "Cross-Validation",
                f"{cv_mean*100:.2f}%",
                "5-fold cross-validation accuracy",
                "#1abc9c",
            )
            metrics_grid.addWidget(cv_card, 1, 1)

        layout.addLayout(metrics_grid)

        # Confusion matrix visualization
        if "confusion_matrix" in self.report_data:
            cm_section = self._create_confusion_matrix_section()
            layout.addWidget(cm_section)

        # Class distribution chart
        if "class_distribution" in self.report_data:
            distribution_section = self._create_class_distribution_section()
            layout.addWidget(distribution_section)

        layout.addStretch()
        overview_widget.setWidget(overview_content)
        overview_widget.setWidgetResizable(True)

        self.tab_widget.addTab(overview_widget, "Overview")

    def _create_metrics_tab(self):
        """Create detailed metrics tab."""
        metrics_widget = QScrollArea()
        metrics_content = QWidget()
        layout = QVBoxLayout(metrics_content)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Performance metrics table
        metrics_table = self._create_performance_metrics_table()
        layout.addWidget(metrics_table)

        # Per-class metrics
        if "precision" in self.report_data and "recall" in self.report_data:
            class_metrics_section = self._create_class_metrics_section()
            layout.addWidget(class_metrics_section)

        layout.addStretch()
        metrics_widget.setWidget(metrics_content)
        metrics_widget.setWidgetResizable(True)

        self.tab_widget.addTab(metrics_widget, "Detailed Metrics")

    def _create_features_tab(self):
        """Create feature importance tab."""
        features_widget = QScrollArea()
        features_content = QWidget()
        layout = QVBoxLayout(features_content)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        feature_importance = self.report_data.get("feature_importance", [])

        if feature_importance:
            # Feature importance chart
            importance_chart = self._create_feature_importance_chart()
            layout.addWidget(importance_chart)

            # Feature importance table
            importance_table = self._create_feature_importance_table()
            layout.addWidget(importance_table)
        else:
            no_data_label = QLabel(
                "Feature importance data not available for this model."
            )
            no_data_label.setObjectName("noDataLabel")
            no_data_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(no_data_label)

        layout.addStretch()
        features_widget.setWidget(features_content)
        features_widget.setWidgetResizable(True)

        self.tab_widget.addTab(features_widget, "Feature Importance")

    def _create_statistics_tab(self):
        """Create classification statistics tab."""
        stats_widget = QScrollArea()
        stats_content = QWidget()
        layout = QVBoxLayout(stats_content)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Area statistics (if available)
        if "class_areas" in self.report_data:
            area_section = self._create_area_statistics_section()
            layout.addWidget(area_section)

        # Pixel statistics
        if "class_distribution" in self.report_data:
            pixel_section = self._create_pixel_statistics_section()
            layout.addWidget(pixel_section)

        layout.addStretch()
        stats_widget.setWidget(stats_content)
        stats_widget.setWidgetResizable(True)

        self.tab_widget.addTab(stats_widget, "Statistics")

    def _create_raw_data_tab(self):
        """Create raw data tab with full classification report."""
        raw_widget = QScrollArea()
        raw_content = QWidget()
        layout = QVBoxLayout(raw_content)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Classification report text
        if "classification_report" in self.report_data:
            report_group = QGroupBox("Detailed Classification Report")
            report_group.setObjectName("dataGroup")
            report_layout = QVBoxLayout(report_group)

            report_text = QTextEdit()
            report_text.setObjectName("rawDataText")
            report_text.setPlainText(self.report_data["classification_report"])
            report_text.setReadOnly(True)
            report_text.setFont(QFont("Consolas", 10))
            report_layout.addWidget(report_text)

            layout.addWidget(report_group)

        # Raw JSON data
        json_group = QGroupBox("Raw Report Data (JSON)")
        json_group.setObjectName("dataGroup")
        json_layout = QVBoxLayout(json_group)

        json_text = QTextEdit()
        json_text.setObjectName("rawDataText")
        json_text.setPlainText(json.dumps(self.report_data, indent=2, default=str))
        json_text.setReadOnly(True)
        json_text.setFont(QFont("Consolas", 9))
        json_layout.addWidget(json_text)

        layout.addWidget(json_group)

        raw_widget.setWidget(raw_content)
        raw_widget.setWidgetResizable(True)

        self.tab_widget.addTab(raw_widget, "Raw Data")

    def _create_metric_card(self, title: str, value: str, description: str, color: str):
        """Create a metric display card."""
        card = QFrame()
        card.setObjectName("metricCard")
        card.setFixedHeight(120)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)

        # Value (large)
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        value_label.setStyleSheet(
            f"color: {color}; font-size: 24px; font-weight: bold;"
        )

        # Title
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")

        # Description
        desc_label = QLabel(description)
        desc_label.setObjectName("metricDescription")
        desc_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()

        return card

    def _create_confusion_matrix_section(self):
        """Create confusion matrix visualization section."""
        section = QGroupBox("Confusion Matrix")
        section.setObjectName("reportSection")
        layout = QVBoxLayout(section)

        cm = self.report_data["confusion_matrix"]

        # Create confusion matrix table
        cm_table = QTableWidget(2, 2)
        cm_table.setObjectName("confusionMatrix")

        # Set headers
        cm_table.setHorizontalHeaderLabels(
            ["Predicted Non-Mangrove", "Predicted Mangrove"]
        )
        cm_table.setVerticalHeaderLabels(["Actual Non-Mangrove", "Actual Mangrove"])

        # Populate matrix
        for i in range(2):
            for j in range(2):
                item = QTableWidgetItem(str(cm[i][j]))
                item.setTextAlignment(Qt.AlignCenter)
                if i == j:  # Diagonal (correct predictions)
                    item.setBackground(QColor(200, 255, 200))
                else:  # Off-diagonal (errors)
                    item.setBackground(QColor(255, 200, 200))
                cm_table.setItem(i, j, item)

        cm_table.resizeColumnsToContents()
        cm_table.resizeRowsToContents()
        cm_table.setMaximumHeight(150)

        layout.addWidget(cm_table)

        # Add interpretation
        tn, fp, fn, tp = cm.ravel()
        interpretation = QLabel(
            f"""
        <b>Matrix Interpretation:</b><br>
        • True Negatives (TN): {tn} - Correctly identified non-mangrove<br>
        • False Positives (FP): {fp} - Incorrectly identified as mangrove<br>
        • False Negatives (FN): {fn} - Missed mangrove areas<br>
        • True Positives (TP): {tp} - Correctly identified mangrove
        """
        )
        interpretation.setObjectName("interpretationText")
        layout.addWidget(interpretation)

        return section

    def _create_class_distribution_section(self):
        """Create class distribution visualization."""
        section = QGroupBox("Class Distribution")
        section.setObjectName("reportSection")
        layout = QVBoxLayout(section)

        distribution = self.report_data.get("class_distribution", {})
        percentages = self.report_data.get("class_percentages", {})

        # Create distribution table
        dist_table = QTableWidget(len(distribution), 3)
        dist_table.setObjectName("distributionTable")
        dist_table.setHorizontalHeaderLabels(["Class", "Pixel Count", "Percentage"])

        class_names = {0: "Non-Mangrove", 1: "Mangrove"}

        for i, (class_val, count) in enumerate(distribution.items()):
            # Class name
            class_item = QTableWidgetItem(
                class_names.get(int(class_val), f"Class {class_val}")
            )
            class_item.setTextAlignment(Qt.AlignCenter)
            dist_table.setItem(i, 0, class_item)

            # Count
            count_item = QTableWidgetItem(f"{count:,}")
            count_item.setTextAlignment(Qt.AlignCenter)
            dist_table.setItem(i, 1, count_item)

            # Percentage
            pct = percentages.get(int(class_val), 0)
            pct_item = QTableWidgetItem(f"{pct:.2f}%")
            pct_item.setTextAlignment(Qt.AlignCenter)
            dist_table.setItem(i, 2, pct_item)

        dist_table.resizeColumnsToContents()
        dist_table.setMaximumHeight(120)

        layout.addWidget(dist_table)

        return section

    def _create_performance_metrics_table(self):
        """Create performance metrics table."""
        section = QGroupBox("Performance Metrics")
        section.setObjectName("reportSection")
        layout = QVBoxLayout(section)

        metrics_table = QTableWidget(5, 2)
        metrics_table.setObjectName("metricsTable")
        metrics_table.setHorizontalHeaderLabels(["Metric", "Value"])

        # Add metrics
        metrics = [
            ("Overall Accuracy", f"{self.report_data.get('accuracy', 0)*100:.3f}%"),
            ("Total Samples", str(self.report_data.get("n_samples", 0))),
            ("Number of Features", str(self.report_data.get("n_features", 0))),
            ("Test Set Size", f"{(self.report_data.get('test_size', 0.2)*100):.0f}%"),
            ("Algorithm", self.report_data.get("method", "Unknown")),
        ]

        # Add cross-validation if available
        if "cv_mean" in self.report_data:
            cv_mean = self.report_data["cv_mean"]
            cv_std = self.report_data.get("cv_std", 0)
            metrics.append(
                ("Cross-Validation", f"{cv_mean*100:.3f}% (±{cv_std*100:.3f}%)")
            )

        metrics_table.setRowCount(len(metrics))

        for i, (metric, value) in enumerate(metrics):
            metric_item = QTableWidgetItem(metric)
            value_item = QTableWidgetItem(value)
            value_item.setTextAlignment(Qt.AlignCenter)

            metrics_table.setItem(i, 0, metric_item)
            metrics_table.setItem(i, 1, value_item)

        metrics_table.resizeColumnsToContents()
        layout.addWidget(metrics_table)

        return section

    def _create_class_metrics_section(self):
        """Create per-class metrics section."""
        section = QGroupBox("Per-Class Performance")
        section.setObjectName("reportSection")
        layout = QVBoxLayout(section)

        precision = self.report_data.get("precision", [])
        recall = self.report_data.get("recall", [])
        f1_score = self.report_data.get("f1_score", [])
        support = self.report_data.get("support", [])

        if len(precision) >= 2:
            class_table = QTableWidget(2, 5)
            class_table.setObjectName("classMetricsTable")
            class_table.setHorizontalHeaderLabels(
                ["Class", "Precision", "Recall", "F1-Score", "Support"]
            )

            class_names = ["Non-Mangrove", "Mangrove"]

            for i in range(2):
                # Class name
                class_item = QTableWidgetItem(class_names[i])
                class_item.setTextAlignment(Qt.AlignCenter)
                class_table.setItem(i, 0, class_item)

                # Metrics
                precision_item = QTableWidgetItem(f"{precision[i]:.3f}")
                precision_item.setTextAlignment(Qt.AlignCenter)
                class_table.setItem(i, 1, precision_item)

                recall_item = QTableWidgetItem(f"{recall[i]:.3f}")
                recall_item.setTextAlignment(Qt.AlignCenter)
                class_table.setItem(i, 2, recall_item)

                f1_item = QTableWidgetItem(f"{f1_score[i]:.3f}")
                f1_item.setTextAlignment(Qt.AlignCenter)
                class_table.setItem(i, 3, f1_item)

                support_item = QTableWidgetItem(str(support[i]))
                support_item.setTextAlignment(Qt.AlignCenter)
                class_table.setItem(i, 4, support_item)

            class_table.resizeColumnsToContents()
            layout.addWidget(class_table)

        return section

    def _create_feature_importance_table(self):
        """Create feature importance table."""
        section = QGroupBox("Feature Importance Rankings")
        section.setObjectName("reportSection")
        layout = QVBoxLayout(section)

        feature_importance = self.report_data.get("feature_importance", [])

        if feature_importance:
            importance_table = QTableWidget(len(feature_importance), 3)
            importance_table.setObjectName("importanceTable")
            importance_table.setHorizontalHeaderLabels(
                ["Rank", "Feature", "Importance"]
            )

            for i, feature_data in enumerate(feature_importance):
                # Rank
                rank_item = QTableWidgetItem(str(i + 1))
                rank_item.setTextAlignment(Qt.AlignCenter)
                importance_table.setItem(i, 0, rank_item)

                # Feature name
                feature_item = QTableWidgetItem(feature_data["feature"])
                feature_item.setTextAlignment(Qt.AlignCenter)
                importance_table.setItem(i, 1, feature_item)

                # Importance score
                importance_item = QTableWidgetItem(f"{feature_data['importance']:.4f}")
                importance_item.setTextAlignment(Qt.AlignCenter)
                importance_table.setItem(i, 2, importance_item)

            importance_table.resizeColumnsToContents()
            layout.addWidget(importance_table)

        return section

    def _create_area_statistics_section(self):
        """Create area statistics section."""
        section = QGroupBox("Area Statistics")
        section.setObjectName("reportSection")
        layout = QVBoxLayout(section)

        class_areas = self.report_data.get("class_areas", {})

        if class_areas:
            area_table = QTableWidget(len(class_areas), 4)
            area_table.setObjectName("areaTable")
            area_table.setHorizontalHeaderLabels(
                ["Class", "Area (m²)", "Area (ha)", "Percentage"]
            )

            total_area_m2 = sum(
                area_data["area_m2"] for area_data in class_areas.values()
            )
            class_names = {0: "Non-Mangrove", 1: "Mangrove"}

            for i, (class_val, area_data) in enumerate(class_areas.items()):
                # Class name
                class_item = QTableWidgetItem(
                    class_names.get(int(class_val), f"Class {class_val}")
                )
                class_item.setTextAlignment(Qt.AlignCenter)
                area_table.setItem(i, 0, class_item)

                # Area in m²
                area_m2_item = QTableWidgetItem(f"{area_data['area_m2']:,.2f}")
                area_m2_item.setTextAlignment(Qt.AlignCenter)
                area_table.setItem(i, 1, area_m2_item)

                # Area in hectares
                area_ha_item = QTableWidgetItem(f"{area_data['area_ha']:,.2f}")
                area_ha_item.setTextAlignment(Qt.AlignCenter)
                area_table.setItem(i, 2, area_ha_item)

                # Percentage
                percentage = (area_data["area_m2"] / total_area_m2) * 100
                pct_item = QTableWidgetItem(f"{percentage:.2f}%")
                pct_item.setTextAlignment(Qt.AlignCenter)
                area_table.setItem(i, 3, pct_item)

            area_table.resizeColumnsToContents()
            layout.addWidget(area_table)

        return section

    def _create_pixel_statistics_section(self):
        """Create pixel statistics section."""
        section = QGroupBox("Pixel Statistics")
        section.setObjectName("reportSection")
        layout = QVBoxLayout(section)

        total_pixels = self.report_data.get("total_pixels", 0)
        distribution = self.report_data.get("class_distribution", {})

        stats_text = f"""
        <b>Total Pixels:</b> {total_pixels:,}<br>
        <b>Image Dimensions:</b> {self.report_data.get('image_width', 'N/A')} × {self.report_data.get('image_height', 'N/A')}<br>
        <b>Classification Summary:</b><br>
        """

        class_names = {0: "Non-Mangrove", 1: "Mangrove"}
        for class_val, count in distribution.items():
            percentage = (count / total_pixels) * 100 if total_pixels > 0 else 0
            class_name = class_names.get(int(class_val), f"Class {class_val}")
            stats_text += f"• {class_name}: {count:,} pixels ({percentage:.2f}%)<br>"

        stats_label = QLabel(stats_text)
        stats_label.setObjectName("statsText")
        layout.addWidget(stats_label)

        return section

    def _create_action_buttons(self):
        """Create action buttons layout."""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # Export buttons
        export_html_btn = QPushButton("Export as HTML")
        export_html_btn.setObjectName("secondaryButton")

        export_pdf_btn = QPushButton("Export as PDF")
        export_pdf_btn.setObjectName("secondaryButton")

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)

        button_layout.addStretch()
        button_layout.addWidget(export_html_btn)
        button_layout.addWidget(export_pdf_btn)
        button_layout.addWidget(close_btn)

        return button_layout

    def populate_report_data(self):
        """Populate the report with data."""
        # This method is called after UI initialization
        # Additional population logic can be added here if needed
        pass

    def apply_stylesheet(self):
        """Apply modern styling to the report viewer."""
        qss = f"""
            /* Main container */
            #mainContainer {{
                background-color: #f8f9fa;
                border-radius: 12px;
            }}

            /* Title styling */
            #reportTitle {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 5px;
            }}

            #reportSubtitle {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 14px;
                color: #7f8c8d;
                margin-bottom: 10px;
            }}

            /* Tab widget styling */
            #reportTabs {{
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e9ecef;
            }}

            #reportTabs::pane {{
                border: 1px solid #e9ecef;
                border-radius: 8px;
                background-color: white;
            }}

            #reportTabs::tab-bar {{
                alignment: center;
            }}

            QTabBar::tab {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 500;
                color: #495057;
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-bottom: none;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}

            QTabBar::tab:selected {{
                background-color: white;
                color: #5E765F;
                border-color: #e9ecef;
                border-bottom: 2px solid #5E765F;
            }}

            QTabBar::tab:hover:!selected {{
                background-color: #e9ecef;
            }}

            /* Metric cards */
            #metricCard {{
                background-color: white;
                border: 2px solid #e9ecef;
                border-radius: 12px;
                margin: 5px;
            }}

            #metricCard:hover {{
                border-color: #5E765F;
                box-shadow: 0 4px 12px rgba(94, 118, 95, 0.1);
            }}

            #metricValue {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 28px;
                font-weight: bold;
                margin-bottom: 5px;
            }}

            #metricTitle {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 14px;
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 3px;
            }}

            #metricDescription {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 11px;
                color: #6c757d;
                line-height: 1.3;
            }}

            /* Group boxes */
            #reportSection, #dataGroup {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 600;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 15px;
                background-color: white;
            }}

            #reportSection::title, #dataGroup::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                background-color: white;
            }}

            /* Tables */
            #confusionMatrix, #distributionTable, #metricsTable, 
            #classMetricsTable, #importanceTable, #areaTable {{
                font-family: 'Montserrat', Arial, sans-serif;
                gridline-color: #e9ecef;
                background-color: white;
                alternate-background-color: #f8f9fa;
                selection-background-color: #5E765F;
            }}

            QTableWidget::item {{
                padding: 8px;
                border: none;
                border-bottom: 1px solid #e9ecef;
            }}

            QTableWidget::item:selected {{
                background-color: #5E765F;
                color: white;
            }}

            QHeaderView::section {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 600;
                background-color: #f8f9fa;
                color: #495057;
                border: 1px solid #e9ecef;
                padding: 8px;
            }}

            /* Text areas */
            #rawDataText {{
                font-family: 'Consolas', 'Monaco', monospace;
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                padding: 12px;
                color: #495057;
            }}

            /* Labels */
            #interpretationText, #statsText {{
                font-family: 'Montserrat', Arial, sans-serif;
                color: #495057;
                background-color: #f8f9fa;
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid #5E765F;
                line-height: 1.4;
            }}

            #noDataLabel {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-size: 16px;
                color: #6c757d;
                background-color: #f8f9fa;
                padding: 40px;
                border-radius: 8px;
                border: 2px dashed #dee2e6;
            }}

            /* Buttons */
            #primaryButton {{
                font-family: 'Montserrat', Arial, sans-serif;
                font-weight: 600;
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

            /* Scroll areas */
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}

            QScrollBar:vertical {{
                background-color: #f8f9fa;
                width: 8px;
                border-radius: 4px;
            }}

            QScrollBar::handle:vertical {{
                background-color: #dee2e6;
                border-radius: 4px;
                min-height: 20px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: #5E765F;
            }}
        """
        self.setStyleSheet(qss)
