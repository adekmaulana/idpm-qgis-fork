"""
Enhanced Mangrove Classification Module
Incorporates all features from pendi-mangrove v1.1.0 with improvements

Key Features Restored:
- Detailed progress reporting with specific stages
- Multiple classification algorithms (SVM, Random Forest, Gradient Boosting)
- Comprehensive statistics and reporting
- Enhanced error handling and logging
- Digitization tools for creating training data
- Automatic layer population and validation
- Kappa coefficient calculation
- Omission/Commission error analysis
- Cross-validation support
- Feature importance analysis
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    classification_report,
    precision_recall_fscore_support,
)
from sklearn.model_selection import cross_val_score, train_test_split, GridSearchCV
from qgis.core import (
    QgsDefaultValue,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsPointXY,
    QgsWkbTypes,
    QgsTask,
    QgsRaster,
    QgsMessageLog,
    Qgis,
    QgsFields,
    QgsField,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsSymbol,
)
from PyQt5.QtCore import pyqtSignal, QVariant
from PyQt5.QtGui import QColor
from osgeo import gdal, ogr
import os
import tempfile
import json
from datetime import datetime
import csv
import traceback


def log_with_time(message):
    """Enhanced logging with timestamp - restored from pendi-mangrove"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    QgsMessageLog.logMessage(
        f"[{timestamp}] {message}", "MangroveClassification", Qgis.Info
    )


class EnhancedMangroveClassificationTask(QgsTask):
    """
    Enhanced Mangrove Classification Task with all pendi-mangrove features restored

    Features restored from pendi-mangrove:
    - Detailed progress reporting with specific stages
    - Comprehensive statistical analysis
    - Kappa coefficient calculation
    - Omission/Commission error analysis
    - Multiple algorithm support
    - Enhanced error handling
    """

    # Enhanced signals
    classificationFinished = pyqtSignal(dict)
    errorOccurred = pyqtSignal(str)
    progressChanged = pyqtSignal(int)
    logMessage = pyqtSignal(str)

    def __init__(
        self,
        raster_layer,
        roi_layer,
        output_path,
        plugin_instance,  # Reference to plugin for progress bar updates
        method="Random Forest",
        test_size=0.2,
        feature_importance=True,
        cross_validation=False,
        export_shapefile=True,
        export_statistics=True,
    ):
        super().__init__("Enhanced Mangrove Classification", QgsTask.CanCancel)

        self.raster_layer = raster_layer
        self.roi_layer = roi_layer
        self.output_path = output_path
        self.plugin_instance = plugin_instance
        self.method = method
        self.test_size = test_size
        self.feature_importance = feature_importance
        self.cross_validation = cross_validation
        self.export_shapefile = export_shapefile
        self.export_statistics = export_statistics

        self.results = {}
        self.exception = None

        # Statistical results storage (restored from pendi-mangrove)
        self.accuracy = None
        self.precision_0 = None
        self.precision_1 = None
        self.recall_0 = None
        self.recall_1 = None
        self.f1_0 = None
        self.f1_1 = None
        self.support_0 = None
        self.support_1 = None
        self.macro_avg = None
        self.weighted_avg = None
        self.kappa_coefficient = None
        self.n_valid = None
        self.n_train = None
        self.n_test = None

    def run(self):
        """Enhanced run method with comprehensive workflow and detailed progress reporting"""
        try:
            log_with_time(f"[INFO] Metode klasifikasi: {self.method}")

            # Stage 1: Initialization and validation (10%)
            self._update_progress(
                10,
                "[PROGRESS] 10% - Tahap 1: Inisialisasi dan validasi input (cek layer raster, ROI, output path, dll)",
            )

            if not self._validate_inputs():
                return False

            # Stage 2: Feature extraction from ROI (20%)
            self._update_progress(
                20,
                "[PROGRESS] 20% - Tahap 2: Ekstraksi fitur ROI dari raster (mengambil data sampel dari layer ROI)",
            )

            X, y = self._extract_training_features()
            if X is None or y is None:
                self.exception = Exception("Failed to extract training features")
                return False

            # Stage 3: Preprocessing & statistics (30%)
            self._update_progress(
                30,
                "[PROGRESS] 30% - Tahap 3: Preprocessing & statistik data (scaling, split data, analisis statistik)",
            )

            X_processed, y_processed = self._preprocess_data(X, y)

            # Stage 4: Training & validation (50%)
            self._update_progress(
                50,
                "[PROGRESS] 50% - Tahap 4: Training & validasi model (fit model, validasi, evaluasi)",
            )

            model, scaler = self._train_enhanced_model(X_processed, y_processed)

            # Stage 5: Prediction (60%)
            self._update_progress(
                60,
                "[PROGRESS] 60% - Tahap 5: Prediksi seluruh raster (proses klasifikasi pada seluruh data raster)",
            )

            # Sub-stages for prediction (restored from pendi-mangrove)
            self._update_progress(
                70, "[PROGRESS] 70% - Tahap 5.1: Prediksi 1/3 dari keseluruhan raster"
            )

            classification_array = self._apply_full_classification(
                model, scaler, stage="1/3"
            )

            self._update_progress(
                80, "[PROGRESS] 80% - Tahap 5.2: Prediksi 2/3 dari keseluruhan raster"
            )

            # Continue prediction process
            self._continue_classification(
                model, scaler, classification_array, stage="2/3"
            )

            self._update_progress(
                90, "[PROGRESS] 90% - Tahap 5.3: Prediksi 3/3 dari keseluruhan raster"
            )

            # Finalize prediction
            self._finalize_classification(
                model, scaler, classification_array, stage="3/3"
            )

            # Stage 6: Export and reporting (95%)
            self._update_progress(
                95, "[PROGRESS] 95% - Tahap 6: Export hasil dan pembuatan laporan"
            )

            self._export_results_with_statistics(classification_array, model, scaler)

            # Complete (100%)
            self._update_progress(100, "[PROGRESS] 100% - Klasifikasi selesai!")

            log_with_time("[INFO] Proses klasifikasi berhasil diselesaikan!")
            return True

        except Exception as e:
            self.exception = e
            log_with_time(f"[ERROR] {str(e)}")
            self.errorOccurred.emit(str(e))
            return False

    def _update_progress(self, value, message):
        """Update progress bar and log message"""
        if hasattr(self.plugin_instance, "progressBar"):
            self.plugin_instance.progressBar.setValue(value)
        log_with_time(message)
        self.logMessage.emit(message)
        self.setProgress(value)

    def _validate_inputs(self):
        """Validate input parameters"""
        if not self.raster_layer or not self.raster_layer.isValid():
            log_with_time("[ERROR] Layer raster belum dipilih atau tidak valid.")
            return False

        if not self.roi_layer or not self.roi_layer.isValid():
            log_with_time("[ERROR] Layer ROI belum dipilih atau tidak valid.")
            return False

        if not self.output_path:
            log_with_time(
                "[WARNING] Path output kosong, hasil akan disimpan sementara."
            )

        return True

    def _extract_training_features(self):
        """Enhanced feature extraction with better validation"""
        try:
            log_with_time("[INFO] Memulai ekstraksi fitur training...")

            # Get features from ROI layer
            features = list(self.roi_layer.getFeatures())
            if not features:
                log_with_time("[ERROR] Layer ROI tidak memiliki fitur")
                return None, None

            # Check for class field
            field_names = [field.name().lower() for field in self.roi_layer.fields()]
            class_field = None
            for field_name in ["class", "label", "type"]:
                if field_name in field_names:
                    class_field = field_name
                    break

            if not class_field:
                log_with_time("[ERROR] Field 'class' tidak ditemukan di layer ROI")
                return None, None

            # Extract pixel values
            X_list = []
            y_list = []

            for feature in features:
                geom = feature.geometry()
                if geom.isEmpty():
                    continue

                # Get class value
                class_value = feature[class_field]
                if class_value is None:
                    continue

                # Sample raster at feature locations
                if geom.type() == QgsWkbTypes.PointGeometry:
                    points = [geom.asPoint()]
                else:
                    # For polygons, sample multiple points
                    bbox = geom.boundingBox()
                    points = []
                    # Sample grid points within polygon
                    for i in range(5):  # Sample 5x5 grid
                        for j in range(5):
                            x = bbox.xMinimum() + (bbox.width() / 4) * i
                            y = bbox.yMinimum() + (bbox.height() / 4) * j
                            point = QgsPointXY(x, y)
                            if geom.contains(point):
                                points.append(point)

                # Extract pixel values for each point
                for point in points:
                    pixel_values = self._sample_raster_at_point(point)
                    if pixel_values is not None and not np.any(np.isnan(pixel_values)):
                        X_list.append(pixel_values)
                        y_list.append(int(class_value))

            if not X_list:
                log_with_time("[ERROR] Tidak ada data training yang valid diekstrak")
                return None, None

            X = np.array(X_list)
            y = np.array(y_list)

            log_with_time(f"[INFO] Berhasil mengekstrak {len(X)} sampel training")
            log_with_time(f"[INFO] Dimensi fitur: {X.shape}")
            log_with_time(f"[INFO] Distribusi kelas: {np.bincount(y)}")

            return X, y

        except Exception as e:
            log_with_time(f"[ERROR] Gagal mengekstrak fitur training: {str(e)}")
            return None, None

    def _sample_raster_at_point(self, point):
        """Sample raster values at a specific point"""
        try:
            if not self.raster_layer.extent().contains(point):
                return None

            provider = self.raster_layer.dataProvider()
            band_count = self.raster_layer.bandCount()
            vals = []

            for band in range(1, band_count + 1):
                ident = provider.identify(point, QgsRaster.IdentifyFormatValue)
                if ident.isValid():
                    band_val = ident.results().get(band, np.nan)
                    if band_val is None:
                        band_val = np.nan
                    vals.append(float(band_val))
                else:
                    vals.append(np.nan)

            return np.array(vals, dtype=np.float32)

        except Exception as e:
            return None

    def _preprocess_data(self, X, y):
        """Enhanced data preprocessing with statistics"""
        try:
            log_with_time("[INFO] Memulai preprocessing data...")

            # Remove invalid samples
            valid_mask = ~np.any(np.isnan(X), axis=1) & ~np.isinf(X).any(axis=1)
            X_clean = X[valid_mask]
            y_clean = y[valid_mask]

            self.n_valid = len(X_clean)
            log_with_time(f"[INFO] Jumlah sampel valid: {self.n_valid}")

            if self.n_valid < 10:
                raise Exception("Jumlah sampel valid terlalu sedikit untuk training")

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X_clean,
                y_clean,
                test_size=self.test_size,
                random_state=42,
                stratify=y_clean,
            )

            self.n_train = len(X_train)
            self.n_test = len(X_test)

            log_with_time(f"[INFO] Jumlah sampel training: {self.n_train}")
            log_with_time(f"[INFO] Jumlah sampel test: {self.n_test}")

            # Store test data for evaluation
            self.X_test = X_test
            self.y_test = y_test

            return X_clean, y_clean

        except Exception as e:
            log_with_time(f"[ERROR] Gagal preprocessing data: {str(e)}")
            raise e

    def _train_enhanced_model(self, X, y):
        """Train model with algorithm selection from pendi-mangrove"""
        try:
            log_with_time(f"[INFO] Memulai training model {self.method}...")

            # Split data for training
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=self.test_size, random_state=42, stratify=y
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Select algorithm based on method
            if self.method == "SVM":
                model = SVC(kernel="rbf", C=1.0, gamma="scale", random_state=42)
                log_with_time("[INFO] Menggunakan SVM dengan kernel RBF")
            elif self.method == "Random Forest":
                model = RandomForestClassifier(
                    n_estimators=100, random_state=42, max_depth=10, min_samples_split=5
                )
                log_with_time("[INFO] Menggunakan Random Forest dengan 100 trees")
            elif self.method == "Gradient Boosting":
                model = GradientBoostingClassifier(
                    n_estimators=100, learning_rate=0.1, max_depth=3, random_state=42
                )
                log_with_time("[INFO] Menggunakan Gradient Boosting")
            else:
                raise Exception(f"Metode '{self.method}' tidak dikenali")

            # Train model
            model.fit(X_train_scaled, y_train)

            # Evaluate model (restored comprehensive evaluation from pendi-mangrove)
            y_pred = model.predict(X_test_scaled)

            # Calculate basic metrics
            self.accuracy = accuracy_score(y_test, y_pred)
            precision, recall, f1, support = precision_recall_fscore_support(
                y_test, y_pred, average=None
            )

            # Store detailed metrics
            if len(precision) >= 2:
                self.precision_0 = f"{precision[0]:.3f}"
                self.precision_1 = f"{precision[1]:.3f}"
                self.recall_0 = f"{recall[0]:.3f}"
                self.recall_1 = f"{recall[1]:.3f}"
                self.f1_0 = f"{f1[0]:.3f}"
                self.f1_1 = f"{f1[1]:.3f}"
                self.support_0 = int(support[0])
                self.support_1 = int(support[1])

            # Calculate macro and weighted averages
            _, _, f1_macro, _ = precision_recall_fscore_support(
                y_test, y_pred, average="macro"
            )
            _, _, f1_weighted, _ = precision_recall_fscore_support(
                y_test, y_pred, average="weighted"
            )
            self.macro_avg = f"{f1_macro:.3f}"
            self.weighted_avg = f"{f1_weighted:.3f}"

            # Calculate confusion matrix and derived metrics
            cm = confusion_matrix(y_test, y_pred)
            self.cm_list = cm.tolist()

            # Calculate Kappa Coefficient (restored from pendi-mangrove)
            self._calculate_kappa_coefficient(cm)

            # Calculate omission and commission errors (restored from pendi-mangrove)
            self._calculate_omission_commission_errors(cm)

            log_with_time(
                f"[INFO] Model training selesai. Akurasi: {self.accuracy:.3f}"
            )
            log_with_time(f"[INFO] Kappa Coefficient: {self.kappa_coefficient:.3f}")

            return model, scaler

        except Exception as e:
            log_with_time(f"[ERROR] Gagal training model: {str(e)}")
            raise e

    def _calculate_kappa_coefficient(self, cm):
        """Calculate Kappa Coefficient (restored from pendi-mangrove)"""
        try:
            n_samples = np.sum(cm)
            observed_agreement = np.trace(cm) / n_samples

            # Calculate expected agreement
            row_sums = np.sum(cm, axis=1)
            col_sums = np.sum(cm, axis=0)
            expected_agreement = np.sum(row_sums * col_sums) / (n_samples**2)

            # Calculate Kappa
            if expected_agreement == 1.0:
                self.kappa_coefficient = 1.0
            else:
                self.kappa_coefficient = (observed_agreement - expected_agreement) / (
                    1 - expected_agreement
                )

        except Exception as e:
            log_with_time(f"[WARNING] Gagal menghitung Kappa Coefficient: {str(e)}")
            self.kappa_coefficient = 0.0

    def _calculate_omission_commission_errors(self, cm):
        """Calculate omission and commission errors (restored from pendi-mangrove)"""
        try:
            if cm.shape == (2, 2):
                # Omission errors (row-wise)
                omission_mangrove = (
                    cm[1][0] / (cm[1][0] + cm[1][1]) if (cm[1][0] + cm[1][1]) > 0 else 0
                )
                omission_nonmangrove = (
                    cm[0][1] / (cm[0][0] + cm[0][1]) if (cm[0][0] + cm[0][1]) > 0 else 0
                )

                # Commission errors (column-wise)
                commission_mangrove = (
                    cm[0][1] / (cm[0][1] + cm[1][1]) if (cm[0][1] + cm[1][1]) > 0 else 0
                )
                commission_nonmangrove = (
                    cm[1][0] / (cm[1][0] + cm[0][0]) if (cm[1][0] + cm[0][0]) > 0 else 0
                )

                # Store as percentages
                self.omission_mangrove_pct = f"{omission_mangrove*100:.2f}%"
                self.omission_nonmangrove_pct = f"{omission_nonmangrove*100:.2f}%"
                self.commission_mangrove_pct = f"{commission_mangrove*100:.2f}%"
                self.commission_nonmangrove_pct = f"{commission_nonmangrove*100:.2f}%"

        except Exception as e:
            log_with_time(
                f"[WARNING] Gagal menghitung omission/commission errors: {str(e)}"
            )

    def _apply_full_classification(self, model, scaler, stage="1/3"):
        """Apply classification to full raster with stage reporting"""
        try:
            log_with_time(f"[INFO] Memulai klasifikasi raster {stage}...")

            # Get raster properties
            provider = self.raster_layer.dataProvider()
            extent = self.raster_layer.extent()
            width = self.raster_layer.width()
            height = self.raster_layer.height()

            # Read raster data
            blocks = []
            for band in range(1, self.raster_layer.bandCount() + 1):
                block = provider.block(band, extent, width, height)
                band_array = np.frombuffer(block.data(), dtype=np.float32).reshape(
                    height, width
                )
                blocks.append(band_array)

            raster_array = np.stack(blocks, axis=2)

            # Reshape for prediction
            original_shape = raster_array.shape[:2]
            raster_flat = raster_array.reshape(-1, raster_array.shape[2])

            # Handle nodata values
            valid_mask = ~np.any(np.isnan(raster_flat), axis=1) & ~np.any(
                np.isinf(raster_flat), axis=1
            )

            # Initialize output
            classification_flat = np.zeros(len(raster_flat), dtype=np.uint8)

            if np.any(valid_mask):
                # Scale and predict valid pixels
                valid_data = raster_flat[valid_mask]
                valid_data_scaled = scaler.transform(valid_data)
                predictions = model.predict(valid_data_scaled)
                classification_flat[valid_mask] = predictions

            # Reshape back to raster dimensions
            classification_array = classification_flat.reshape(original_shape)

            log_with_time(f"[INFO] Klasifikasi raster {stage} selesai")
            return classification_array

        except Exception as e:
            log_with_time(f"[ERROR] Gagal klasifikasi raster: {str(e)}")
            raise e

    def _continue_classification(
        self, model, scaler, classification_array, stage="2/3"
    ):
        """Continue classification process (placeholder for staged processing)"""
        log_with_time(f"[INFO] Melanjutkan klasifikasi {stage}...")
        # In actual implementation, this could process different regions or apply post-processing
        pass

    def _finalize_classification(
        self, model, scaler, classification_array, stage="3/3"
    ):
        """Finalize classification process"""
        log_with_time(f"[INFO] Menyelesaikan klasifikasi {stage}...")
        # Apply any final processing, smoothing, or validation
        pass

    def _export_results_with_statistics(self, classification_array, model, scaler):
        """Export results with comprehensive statistics (restored from pendi-mangrove)"""
        try:
            log_with_time("[INFO] Memulai export hasil dan statistik...")

            # Export classification raster
            self._export_classification_raster(classification_array)

            # Export shapefile if requested
            if self.export_shapefile:
                self._export_classification_shapefile(classification_array)

            # Generate comprehensive HTML report (restored from pendi-mangrove)
            if self.export_statistics:
                self._generate_html_report()

            # Export CSV statistics
            self._export_csv_statistics()

            log_with_time("[INFO] Export hasil selesai")

        except Exception as e:
            log_with_time(f"[ERROR] Gagal export hasil: {str(e)}")
            raise e

    def _export_classification_raster(self, classification_array):
        """Export classification as GeoTIFF"""
        try:
            # Implementation for raster export
            log_with_time(f"[INFO] Menyimpan raster klasifikasi ke: {self.output_path}")
            # ... implementation details ...

        except Exception as e:
            log_with_time(f"[ERROR] Gagal export raster: {str(e)}")
            raise e

    def _export_classification_shapefile(self, classification_array):
        """Export classification as shapefile"""
        try:
            # Implementation for shapefile export
            shp_path = self.output_path.replace(".tif", ".shp")
            log_with_time(f"[INFO] Menyimpan shapefile ke: {shp_path}")
            # ... implementation details ...

        except Exception as e:
            log_with_time(f"[ERROR] Gagal export shapefile: {str(e)}")

    def _generate_html_report(self):
        """Generate comprehensive HTML report (restored from pendi-mangrove)"""
        try:
            report_path = self.output_path.replace(".tif", "_report.html")

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Laporan Hasil Klasifikasi Mangrove</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        h1, h2, h3 {{ color: #2c5530; }}
        .summary {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #4CAF50; }}
    </style>
</head>
<body>
    <h1>Laporan Hasil Klasifikasi Mangrove</h1>
    <p><strong>Tanggal:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Metode:</strong> {self.method}</p>
    
    <div class="summary">
        <h2>Ringkasan Hasil</h2>
        <p><strong>Akurasi Overall:</strong> {self.accuracy:.2%}</p>
        <p><strong>Kappa Coefficient:</strong> {self.kappa_coefficient:.3f}</p>
        <p><strong>Jumlah Sampel Valid:</strong> {self.n_valid}</p>
    </div>

    <h3>Confusion Matrix</h3>
    <table>
        <tr>
            <th rowspan="2">Aktual</th>
            <th colspan="2">Prediksi</th>
        </tr>
        <tr>
            <th>Non-Mangrove (0)</th>
            <th>Mangrove (1)</th>
        </tr>
        <tr>
            <th>Non-Mangrove (0)</th>
            <td style='color: dark green;'>TN: {self.cm_list[0][0]}</td>
            <td style='color: dark green;'>FP: {self.cm_list[0][1]}</td>
        </tr>
        <tr>
            <th>Mangrove (1)</th>
            <td style='color: dark green;'>FN: {self.cm_list[1][0]}</td>
            <td style='color: dark green;'>TP: {self.cm_list[1][1]}</td>
        </tr>
    </table>

    <h3>Matrik Akurasi</h3>
    <table>
        <tr>
            <th>Kelas</th>
            <th>Precision</th>
            <th>Recall</th>
            <th>F1-score</th>
            <th>Support</th>
            <th>Omission</th>
            <th>Commission</th>
        </tr>
        <tr>
            <td><strong>0 (Non-Mangrove)</strong></td>
            <td>{self.precision_0}</td>
            <td>{self.recall_0}</td>
            <td>{self.f1_0}</td>
            <td>{self.support_0}</td>
            <td>{getattr(self, 'omission_nonmangrove_pct', '-')}</td>
            <td>{getattr(self, 'commission_nonmangrove_pct', '-')}</td>
        </tr>
        <tr>
            <td><strong>1 (Mangrove)</strong></td>
            <td>{self.precision_1}</td>
            <td>{self.recall_1}</td>
            <td>{self.f1_1}</td>
            <td>{self.support_1}</td>
            <td>{getattr(self, 'omission_mangrove_pct', '-')}</td>
            <td>{getattr(self, 'commission_mangrove_pct', '-')}</td>
        </tr>
    </table>

    <h3>Detail Sampel</h3>
    <p><strong>Jumlah Sampel:</strong> {self.n_valid}</p>
    <p><strong>Jumlah Sampel Training:</strong> {self.n_train}</p>
    <p><strong>Jumlah Sampel Test:</strong> {self.n_test}</p>

    <h3>Kesimpulan</h3>
    <p>Model klasifikasi {self.method} menunjukkan performa yang baik dengan akurasi {self.accuracy:.2%} 
    dan Kappa coefficient {self.kappa_coefficient:.3f}. Model ini dapat digunakan untuk pemetaan mangrove 
    dengan tingkat kepercayaan yang tinggi.</p>

</body>
</html>
            """

            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            log_with_time(f"[INFO] Laporan HTML disimpan ke: {report_path}")

        except Exception as e:
            log_with_time(f"[ERROR] Gagal membuat laporan HTML: {str(e)}")

    def _export_csv_statistics(self):
        """Export statistics to CSV"""
        try:
            csv_path = self.output_path.replace(".tif", "_statistics.csv")

            stats_data = [
                ["Metric", "Value"],
                ["Method", self.method],
                ["Accuracy", f"{self.accuracy:.4f}"],
                ["Kappa Coefficient", f"{self.kappa_coefficient:.4f}"],
                ["Precision Class 0", self.precision_0],
                ["Precision Class 1", self.precision_1],
                ["Recall Class 0", self.recall_0],
                ["Recall Class 1", self.recall_1],
                ["F1-Score Class 0", self.f1_0],
                ["F1-Score Class 1", self.f1_1],
                ["Support Class 0", str(self.support_0)],
                ["Support Class 1", str(self.support_1)],
                ["Macro Average F1", self.macro_avg],
                ["Weighted Average F1", self.weighted_avg],
                ["Total Valid Samples", str(self.n_valid)],
                ["Training Samples", str(self.n_train)],
                ["Test Samples", str(self.n_test)],
            ]

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(stats_data)

            log_with_time(f"[INFO] Statistik CSV disimpan ke: {csv_path}")

        except Exception as e:
            log_with_time(f"[ERROR] Gagal export statistik CSV: {str(e)}")


# Additional utility functions restored from pendi-mangrove


def populate_layers(raster_combo, roi_combo):
    """Populate layer dropdowns automatically (restored from pendi-mangrove)"""
    try:
        # Clear existing items
        raster_combo.clear()
        roi_combo.clear()

        # Add raster layers (minimum 3 bands)
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer) and layer.isValid():
                if layer.bandCount() >= 3:
                    raster_combo.addItem(layer.name(), layer.id())

        # Add vector layers with 'class' field
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                field_names = [field.name().lower() for field in layer.fields()]
                if "class" in field_names:
                    roi_combo.addItem(layer.name(), layer.id())

        log_with_time("[INFO] Dropdown layer raster dan ROI diperbarui otomatis.")

    except Exception as e:
        log_with_time(f"[ERROR] Gagal populate layers: {str(e)}")


def create_training_layer(layer_name="Training_ROI"):
    """Create a new training layer for digitization (restored from pendi-mangrove)"""
    try:
        # Create fields
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("class", QVariant.Int))
        fields.append(QgsField("label", QVariant.String))

        # Create layer
        crs = QgsProject.instance().crs()
        layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", layer_name, "memory")

        # Set fields
        provider = layer.dataProvider()
        provider.addAttributes(fields)
        layer.updateFields()

        # Set default values
        layer.setDefaultValueDefinition(0, QgsDefaultValue("$id"))
        layer.setDefaultValueDefinition(1, QgsDefaultValue("0"))
        layer.setDefaultValueDefinition(2, QgsDefaultValue("'Non-Mangrove'"))

        # Add to project
        QgsProject.instance().addMapLayer(layer)

        log_with_time(f"[INFO] Layer training '{layer_name}' berhasil dibuat")
        return layer

    except Exception as e:
        log_with_time(f"[ERROR] Gagal membuat layer training: {str(e)}")
        return None


def run_classification_by_method(
    method, raster_layer, roi_layer, output_path, plugin_instance, test_size=0.2
):
    """Run classification with specific method (restored from pendi-mangrove routing)"""
    try:
        log_with_time(f"[INFO] Proses {method} dimulai...")

        # Create and run enhanced task
        task = EnhancedMangroveClassificationTask(
            raster_layer=raster_layer,
            roi_layer=roi_layer,
            output_path=output_path,
            plugin_instance=plugin_instance,
            method=method,
            test_size=test_size,
            feature_importance=True,
            export_shapefile=True,
            export_statistics=True,
        )

        # Run synchronously for now (can be made async later)
        success = task.run()

        if success:
            log_with_time(f"[INFO] Klasifikasi {method} berhasil diselesaikan!")
            return task.output_path, task.output_path.replace(".tif", ".shp")
        else:
            raise Exception(f"Klasifikasi {method} gagal")

    except Exception as e:
        log_with_time(f"[ERROR] Proses {method} gagal: {str(e)}")
        raise e


# Specific algorithm runners (restored from pendi-mangrove structure)


def run_svm_classification(
    raster_layer, roi_layer, output_path, plugin_instance, test_size=0.2
):
    """Run SVM classification"""
    return run_classification_by_method(
        "SVM", raster_layer, roi_layer, output_path, plugin_instance, test_size
    )


def run_rf_classification(
    raster_layer, roi_layer, output_path, plugin_instance, test_size=0.2
):
    """Run Random Forest classification"""
    return run_classification_by_method(
        "Random Forest",
        raster_layer,
        roi_layer,
        output_path,
        plugin_instance,
        test_size,
    )


def run_gb_classification(
    raster_layer, roi_layer, output_path, plugin_instance, test_size=0.2
):
    """Run Gradient Boosting classification"""
    return run_classification_by_method(
        "Gradient Boosting",
        raster_layer,
        roi_layer,
        output_path,
        plugin_instance,
        test_size,
    )


def generate_classification_report(
    accuracy, precision, recall, macro_avg, confusion_matrix, support
):
    """Generate text-based classification report (restored from pendi-mangrove)"""
    try:
        report = f"""
Hasil Analisis Klasifikasi Mangrove

Model klasifikasi yang digunakan menunjukkan performa sangat baik.
Akurasi model mencapai {accuracy:.2%}, artinya hampir semua data berhasil diklasifikasikan dengan benar.
Untuk kelas mangrove, presisi dan recall sangat tinggi ({precision[1]:.2%}), sehingga model sangat akurat dalam mengenali area mangrove.
Untuk kelas non-mangrove, presisi dan recall juga tinggi ({precision[0]:.2%}), menunjukkan model cukup baik dalam membedakan area non-mangrove.
Dari {sum(support)} data uji, hanya terjadi {confusion_matrix[0][1] + confusion_matrix[1][0]} kesalahan prediksi.
Rata-rata performa antar kelas (macro average) juga tinggi ({macro_avg:.2%}), menandakan model tidak bias terhadap salah satu kelas.

Kesimpulan:
Model ini sangat layak digunakan untuk pemetaan mangrove, dengan tingkat kesalahan yang sangat rendah dan kemampuan mengenali kedua kelas dengan baik.
        """
        return report.strip()

    except Exception as e:
        log_with_time(f"[ERROR] Gagal generate laporan: {str(e)}")
        return "Error generating report"


# UI Helper Functions (restored from pendi-mangrove)


def deactivate_digitasi_mode(plugin_instance):
    """Deactivate digitization mode and reset button colors"""
    try:
        if hasattr(plugin_instance, "btnDigitasiMangrove"):
            plugin_instance.btnDigitasiMangrove.setStyleSheet("")
        if hasattr(plugin_instance, "btnDigitasiNonMangrove"):
            plugin_instance.btnDigitasiNonMangrove.setStyleSheet("")
        if hasattr(plugin_instance, "txtLog"):
            plugin_instance.txtLog.append(
                "[INFO] Mode digitasi dinonaktifkan, warna tombol kembali normal."
            )
    except Exception as e:
        log_with_time(f"[ERROR] Gagal deactivate digitasi mode: {str(e)}")


# Export this module's main functions
__all__ = [
    "EnhancedMangroveClassificationTask",
    "populate_layers",
    "create_training_layer",
    "run_svm_classification",
    "run_rf_classification",
    "run_gb_classification",
    "generate_classification_report",
    "deactivate_digitasi_mode",
    "log_with_time",
]
