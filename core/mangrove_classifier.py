"""
Enhanced Mangrove Classification Core Module (mangrove_classifier.py)
Incorporates latest improvements from pendi-mangrove v1.1.0 repositories

This module replaces the existing mangrove_classifier.py with enhanced features:
- Advanced machine learning algorithms (SVM, Random Forest, Gradient Boosting)
- Feature importance analysis
- Cross-validation support
- Enhanced error handling and progress reporting
- Shapefile export functionality
- Comprehensive statistics and reporting
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
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsPointXY,
    QgsWkbTypes,
    QgsTask,
    QgsRaster,
    QgsMessageLog,
    Qgis,
    QgsRasterShader,
    QgsColorRampShader,
    QgsSingleBandPseudoColorRenderer,
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


def sample_raster_at_point(raster_layer, pt, nodata=None):
    """
    Enhanced raster sampling with better error handling.
    Sample raster values at a specific point with improved validation.
    """
    try:
        if not raster_layer.extent().contains(pt):
            return np.array([np.nan] * raster_layer.bandCount(), dtype=np.float32)

        provider = raster_layer.dataProvider()
        band_count = raster_layer.bandCount()
        vals = []

        for band in range(1, band_count + 1):
            ident = provider.identify(pt, QgsRaster.IdentifyFormatValue)
            if ident.isValid():
                band_val = ident.results().get(band, np.nan)
                # Handle potential None values
                if band_val is None:
                    band_val = np.nan
                vals.append(float(band_val))
            else:
                vals.append(np.nan)

        arr = np.array(vals, dtype=np.float32)

        # Handle nodata values
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)

        return arr

    except Exception as e:
        # Return NaN array on any error
        return np.array([np.nan] * raster_layer.bandCount(), dtype=np.float32)


def export_classification_shapefile(
    classification_array,
    raster_layer,
    output_path,
    layer_name="Mangrove_Classification",
):
    """
    Enhanced shapefile export with improved geometry handling and styling.
    Export classification results as a styled shapefile.
    """
    try:
        # Get raster properties
        extent = raster_layer.extent()
        width = classification_array.shape[1]
        height = classification_array.shape[0]
        x_res = (extent.xMaximum() - extent.xMinimum()) / width
        y_res = (extent.yMaximum() - extent.yMinimum()) / height

        # Create shapefile path
        base_path = os.path.splitext(output_path)[0]
        shapefile_path = f"{base_path}_{layer_name}.shp"

        # Define fields
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("class", QVariant.Int))
        fields.append(QgsField("class_name", QVariant.String))
        fields.append(QgsField("area_m2", QVariant.Double))

        # Get CRS from raster
        crs = raster_layer.crs()

        # Create vector file writer
        writer = QgsVectorFileWriter(
            shapefile_path, "utf-8", fields, QgsWkbTypes.Polygon, crs, "ESRI Shapefile"
        )

        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise Exception(f"Error creating shapefile: {writer.errorMessage()}")

        feature_id = 1

        # Convert classification pixels to polygons
        for row in range(height):
            for col in range(width):
                class_value = classification_array[row, col]

                # Only export mangrove pixels (class = 1)
                if class_value == 1:
                    # Calculate pixel bounds
                    x_min = extent.xMinimum() + col * x_res
                    x_max = x_min + x_res
                    y_max = extent.yMaximum() - row * y_res
                    y_min = y_max - y_res

                    # Create polygon geometry
                    polygon_points = [
                        QgsPointXY(x_min, y_min),
                        QgsPointXY(x_max, y_min),
                        QgsPointXY(x_max, y_max),
                        QgsPointXY(x_min, y_max),
                        QgsPointXY(x_min, y_min),  # Close polygon
                    ]

                    geometry = QgsGeometry.fromPolygonXY([polygon_points])

                    # Calculate area in square meters
                    area_m2 = geometry.area()

                    # Create feature
                    feature = QgsFeature()
                    feature.setGeometry(geometry)
                    feature.setAttributes(
                        [
                            feature_id,
                            int(class_value),
                            "Mangrove" if class_value == 1 else "Non-Mangrove",
                            area_m2,
                        ]
                    )

                    writer.addFeature(feature)
                    feature_id += 1

        del writer  # Close the file

        # Load and style the shapefile
        shapefile_layer = QgsVectorLayer(shapefile_path, layer_name, "ogr")
        if shapefile_layer.isValid():
            # Apply styling
            symbol = QgsSymbol.defaultSymbol(shapefile_layer.geometryType())
            symbol.setColor(QColor(34, 139, 34, 180))  # Forest green with transparency
            symbol.symbolLayer(0).setStrokeColor(QColor(0, 100, 0))
            symbol.symbolLayer(0).setStrokeWidth(0.5)

            renderer = QgsCategorizedSymbolRenderer()
            renderer.setClassAttribute("class")

            category = QgsRendererCategory(1, symbol, "Mangrove")
            renderer.addCategory(category)

            shapefile_layer.setRenderer(renderer)

            # Add to project
            QgsProject.instance().addMapLayer(shapefile_layer)

        return shapefile_path

    except Exception as e:
        raise Exception(f"Failed to export shapefile: {str(e)}")


class EnhancedMangroveClassificationTask(QgsTask):
    """
    Enhanced task for running mangrove classification with advanced features.

    Improvements from pendi-mangrove v1.1.0:
    - Feature importance analysis
    - Cross-validation support
    - Advanced parameter tuning
    - Better progress reporting
    - Enhanced error handling
    - Comprehensive statistics
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
        self.method = method
        self.test_size = test_size
        self.feature_importance = feature_importance
        self.cross_validation = cross_validation
        self.export_shapefile = export_shapefile
        self.export_statistics = export_statistics

        self.results = {}
        self.exception = None

    def run(self):
        """Enhanced run method with comprehensive workflow."""
        try:
            self.logMessage.emit("Starting enhanced mangrove classification...")
            self.setProgress(0)

            # Stage 1: Extract and validate training data
            self.logMessage.emit("Stage 1: Extracting training features...")
            X, y = self._extract_training_features()
            if X is None or y is None:
                self.exception = Exception("Failed to extract training features")
                return False

            self.setProgress(15)

            # Stage 2: Data preprocessing and validation
            self.logMessage.emit("Stage 2: Preprocessing and validating data...")
            X_processed, y_processed = self._preprocess_data(X, y)

            self.setProgress(25)

            # Stage 3: Model training with hyperparameter tuning
            self.logMessage.emit("Stage 3: Training classification model...")
            model, scaler = self._train_enhanced_model(X_processed, y_processed)

            self.setProgress(50)

            # Stage 4: Model validation and evaluation
            self.logMessage.emit("Stage 4: Evaluating model performance...")
            evaluation_results = self._evaluate_model(
                model, scaler, X_processed, y_processed
            )

            self.setProgress(65)

            # Stage 5: Apply classification to full raster
            self.logMessage.emit("Stage 5: Applying classification to raster...")
            classification_array = self._apply_full_classification(model, scaler)

            self.setProgress(85)

            # Stage 6: Export results and generate reports
            self.logMessage.emit("Stage 6: Exporting results and generating reports...")
            self._export_results(classification_array, evaluation_results)

            self.setProgress(100)
            self.logMessage.emit("Classification completed successfully!")

            return True

        except Exception as e:
            self.exception = e
            self.errorOccurred.emit(str(e))
            return False

    def _extract_training_features(self):
        """Enhanced feature extraction with better validation."""
        try:
            X_features = []
            y_labels = []

            # Find class field
            roi_fields = self.roi_layer.fields()
            class_field = None
            for field in roi_fields:
                if field.name().lower() in ["class", "label", "type"]:
                    class_field = field.name()
                    break

            if not class_field:
                raise Exception("No class field found in ROI layer")

            # Extract features from each ROI feature
            feature_count = 0
            total_features = self.roi_layer.featureCount()

            for feature in self.roi_layer.getFeatures():
                if self.isCanceled():
                    return None, None

                # Get class label
                class_value = feature[class_field]
                if class_value is None:
                    continue

                # Convert class value to integer
                try:
                    class_int = int(class_value)
                except (ValueError, TypeError):
                    continue

                # Sample raster at feature centroid
                geom = feature.geometry()
                if geom.isEmpty():
                    continue

                centroid = geom.centroid().asPoint()
                raster_values = sample_raster_at_point(self.raster_layer, centroid)

                # Check for valid values
                if not np.any(np.isnan(raster_values)):
                    X_features.append(raster_values)
                    y_labels.append(class_int)

                feature_count += 1
                if feature_count % 100 == 0:
                    progress = int(15 * feature_count / total_features)
                    self.setProgress(progress)

            if len(X_features) == 0:
                raise Exception("No valid training samples found")

            self.logMessage.emit(f"Extracted {len(X_features)} valid training samples")

            return np.array(X_features), np.array(y_labels)

        except Exception as e:
            raise Exception(f"Feature extraction failed: {str(e)}")

    def _preprocess_data(self, X, y):
        """Enhanced data preprocessing with validation."""
        try:
            # Remove samples with NaN values
            valid_indices = ~np.isnan(X).any(axis=1)
            X_clean = X[valid_indices]
            y_clean = y[valid_indices]

            if len(X_clean) == 0:
                raise Exception("No valid samples after cleaning")

            # Validate class distribution
            unique_classes, class_counts = np.unique(y_clean, return_counts=True)
            self.logMessage.emit(
                f"Class distribution: {dict(zip(unique_classes, class_counts))}"
            )

            # Ensure we have at least 2 classes
            if len(unique_classes) < 2:
                raise Exception("Need at least 2 classes for classification")

            # Ensure minimum samples per class
            min_samples_per_class = max(5, int(len(X_clean) * self.test_size))
            for i, count in enumerate(class_counts):
                if count < min_samples_per_class:
                    raise Exception(
                        f"Class {unique_classes[i]} has only {count} samples, need at least {min_samples_per_class}"
                    )

            return X_clean, y_clean

        except Exception as e:
            raise Exception(f"Data preprocessing failed: {str(e)}")

    def _train_enhanced_model(self, X, y):
        """Enhanced model training with hyperparameter tuning."""
        try:
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Split data
            X_train, X_val, y_train, y_val = train_test_split(
                X_scaled, y, test_size=self.test_size, random_state=42, stratify=y
            )

            # Train model with hyperparameter tuning
            if self.method == "Random Forest":
                model = self._train_random_forest(X_train, y_train)
            elif self.method == "Gradient Boosting":
                model = self._train_gradient_boosting(X_train, y_train)
            elif self.method == "SVM":
                model = self._train_svm(X_train, y_train)
            else:
                raise Exception(f"Unknown method: {self.method}")

            self.logMessage.emit(f"Model training completed with {self.method}")

            return model, scaler

        except Exception as e:
            raise Exception(f"Model training failed: {str(e)}")

    def _train_random_forest(self, X_train, y_train):
        """Train Random Forest with hyperparameter tuning."""
        param_grid = {
            "n_estimators": [50, 100, 200],
            "max_depth": [10, 20, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4],
        }

        rf = RandomForestClassifier(random_state=42)
        grid_search = GridSearchCV(rf, param_grid, cv=3, scoring="accuracy", n_jobs=-1)
        grid_search.fit(X_train, y_train)

        self.logMessage.emit(f"Best RF parameters: {grid_search.best_params_}")
        return grid_search.best_estimator_

    def _train_gradient_boosting(self, X_train, y_train):
        """Train Gradient Boosting with hyperparameter tuning."""
        param_grid = {
            "n_estimators": [50, 100, 150],
            "learning_rate": [0.05, 0.1, 0.2],
            "max_depth": [3, 5, 7],
            "min_samples_split": [2, 5, 10],
        }

        gb = GradientBoostingClassifier(random_state=42)
        grid_search = GridSearchCV(gb, param_grid, cv=3, scoring="accuracy", n_jobs=-1)
        grid_search.fit(X_train, y_train)

        self.logMessage.emit(f"Best GB parameters: {grid_search.best_params_}")
        return grid_search.best_estimator_

    def _train_svm(self, X_train, y_train):
        """Train SVM with hyperparameter tuning."""
        param_grid = {
            "C": [0.1, 1, 10, 100],
            "gamma": ["scale", "auto", 0.001, 0.01, 0.1, 1],
            "kernel": ["rbf", "poly"],
        }

        svm = SVC(random_state=42)
        grid_search = GridSearchCV(svm, param_grid, cv=3, scoring="accuracy", n_jobs=-1)
        grid_search.fit(X_train, y_train)

        self.logMessage.emit(f"Best SVM parameters: {grid_search.best_params_}")
        return grid_search.best_estimator_

    def _evaluate_model(self, model, scaler, X, y):
        """Comprehensive model evaluation."""
        try:
            # Split data for evaluation
            X_scaled = scaler.transform(X)
            X_train, X_val, y_train, y_val = train_test_split(
                X_scaled, y, test_size=self.test_size, random_state=42, stratify=y
            )

            # Make predictions
            y_pred = model.predict(X_val)

            # Calculate metrics
            cm = confusion_matrix(y_val, y_pred)
            accuracy = accuracy_score(y_val, y_pred)
            precision, recall, f1, support = precision_recall_fscore_support(
                y_val, y_pred
            )
            classification_rep = classification_report(y_val, y_pred)

            results = {
                "confusion_matrix": cm,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "support": support,
                "classification_report": classification_rep,
                "method": self.method,
                "n_samples": len(X),
                "n_features": X.shape[1],
            }

            # Feature importance analysis
            if self.feature_importance and hasattr(model, "feature_importances_"):
                importance_scores = model.feature_importances_
                feature_names = [f"Band_{i+1}" for i in range(len(importance_scores))]

                # Create feature importance DataFrame
                importance_df = pd.DataFrame(
                    {"feature": feature_names, "importance": importance_scores}
                ).sort_values("importance", ascending=False)

                results["feature_importance"] = importance_df.to_dict("records")

                # Log top features
                self.logMessage.emit("Top 5 most important features:")
                for _, row in importance_df.head(5).iterrows():
                    self.logMessage.emit(f"  {row['feature']}: {row['importance']:.4f}")

            # Cross-validation
            if self.cross_validation:
                cv_scores = cross_val_score(
                    model, X_scaled, y, cv=5, scoring="accuracy"
                )
                results["cv_scores"] = cv_scores.tolist()
                results["cv_mean"] = cv_scores.mean()
                results["cv_std"] = cv_scores.std()

                self.logMessage.emit(
                    f"Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})"
                )

            # Log evaluation results
            self.logMessage.emit(f"Validation accuracy: {accuracy:.3f}")
            self.logMessage.emit(
                f"Confusion matrix: TN={cm[0,0]}, FP={cm[0,1]}, FN={cm[1,0]}, TP={cm[1,1]}"
            )

            return results

        except Exception as e:
            raise Exception(f"Model evaluation failed: {str(e)}")

    def _apply_full_classification(self, model, scaler):
        """Apply classification to full raster with memory optimization."""
        try:
            provider = self.raster_layer.dataProvider()
            extent = self.raster_layer.extent()
            width = self.raster_layer.width()
            height = self.raster_layer.height()
            band_count = self.raster_layer.bandCount()

            # Initialize result array
            classification_result = np.zeros((height, width), dtype=np.uint8)

            # Process in chunks to manage memory
            chunk_size = min(1000, height // 10 + 1)

            for start_row in range(0, height, chunk_size):
                if self.isCanceled():
                    return None

                end_row = min(start_row + chunk_size, height)
                chunk_height = end_row - start_row

                # Read raster chunk
                chunk_data = np.zeros((chunk_height, width, band_count))

                for band in range(band_count):
                    band_data = provider.block(band + 1, extent, width, chunk_height)

                    # Convert to numpy array
                    if hasattr(band_data, "data"):
                        band_array = np.frombuffer(band_data.data(), dtype=np.float32)
                        band_array = band_array.reshape((chunk_height, width))
                    else:
                        # Fallback method
                        band_array = np.zeros((chunk_height, width))
                        for row in range(chunk_height):
                            for col in range(width):
                                x = (
                                    extent.xMinimum()
                                    + (col + 0.5)
                                    * (extent.xMaximum() - extent.xMinimum())
                                    / width
                                )
                                y = (
                                    extent.yMaximum()
                                    - (start_row + row + 0.5)
                                    * (extent.yMaximum() - extent.yMinimum())
                                    / height
                                )
                                point = QgsPointXY(x, y)

                                ident = provider.identify(
                                    point, QgsRaster.IdentifyFormatValue
                                )
                                if ident.isValid():
                                    band_array[row, col] = ident.results().get(
                                        band + 1, 0
                                    )

                    chunk_data[:, :, band] = band_array

                # Reshape for prediction
                chunk_pixels = chunk_data.reshape(-1, band_count)

                # Remove invalid pixels
                valid_mask = ~np.isnan(chunk_pixels).any(axis=1)

                # Predict valid pixels
                chunk_predictions = np.zeros(len(chunk_pixels), dtype=np.uint8)
                if np.any(valid_mask):
                    valid_pixels = chunk_pixels[valid_mask]
                    scaled_pixels = scaler.transform(valid_pixels)
                    predictions = model.predict(scaled_pixels)
                    chunk_predictions[valid_mask] = predictions

                # Reshape back to chunk
                chunk_result = chunk_predictions.reshape(chunk_height, width)
                classification_result[start_row:end_row, :] = chunk_result

                # Update progress
                progress = 65 + int(20 * (start_row + chunk_height) / height)
                self.setProgress(progress)

            return classification_result

        except Exception as e:
            raise Exception(f"Full classification failed: {str(e)}")

    def _export_results(self, classification_array, evaluation_results):
        """Export classification results and generate reports."""
        try:
            # Save classification raster
            self._save_classification_raster(classification_array)

            # Export shapefile if requested
            if self.export_shapefile:
                self.logMessage.emit("Exporting classification shapefile...")
                shapefile_path = export_classification_shapefile(
                    classification_array,
                    self.raster_layer,
                    self.output_path,
                    f"{self.method.replace(' ', '_')}_Classification",
                )
                evaluation_results["shapefile_path"] = shapefile_path

            # Export statistics if requested
            if self.export_statistics:
                self.logMessage.emit("Generating classification statistics...")
                stats = self._generate_classification_statistics(classification_array)
                evaluation_results.update(stats)

            # Store all results
            self.results = evaluation_results

            # Emit completion signal
            self.classificationFinished.emit(evaluation_results)

        except Exception as e:
            raise Exception(f"Results export failed: {str(e)}")

    def _save_classification_raster(self, classification_array):
        """Save classification result as GeoTIFF."""
        try:
            # Get raster properties
            extent = self.raster_layer.extent()
            crs = self.raster_layer.crs()

            height, width = classification_array.shape
            x_res = (extent.xMaximum() - extent.xMinimum()) / width
            y_res = (extent.yMaximum() - extent.yMinimum()) / height

            # Create GeoTIFF
            driver = gdal.GetDriverByName("GTiff")
            dataset = driver.Create(self.output_path, width, height, 1, gdal.GDT_Byte)

            # Set geotransform
            geotransform = [extent.xMinimum(), x_res, 0, extent.yMaximum(), 0, -y_res]
            dataset.SetGeoTransform(geotransform)

            # Set projection
            dataset.SetProjection(crs.toWkt())

            # Write data
            band = dataset.GetRasterBand(1)
            band.WriteArray(classification_array)
            band.SetNoDataValue(255)

            # Close dataset
            dataset = None

            # Load result into QGIS
            result_layer = QgsRasterLayer(
                self.output_path, f"{self.method} Classification"
            )
            if result_layer.isValid():
                # Apply color styling
                self._style_classification_raster(result_layer)
                QgsProject.instance().addMapLayer(result_layer)

        except Exception as e:
            raise Exception(f"Failed to save classification raster: {str(e)}")

    def _style_classification_raster(self, layer):
        """Apply color styling to classification raster."""
        try:
            # Create color ramp
            color_list = [
                QgsColorRampShader.ColorRampItem(
                    0, QColor(139, 69, 19), "Non-Mangrove"
                ),
                QgsColorRampShader.ColorRampItem(1, QColor(34, 139, 34), "Mangrove"),
            ]

            # Create shader
            shader = QgsRasterShader()
            color_ramp = QgsColorRampShader()
            color_ramp.setColorRampItemList(color_list)
            color_ramp.setColorRampType(QgsColorRampShader.Exact)
            shader.setRasterShaderFunction(color_ramp)

            # Create renderer
            renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
            layer.setRenderer(renderer)

        except Exception as e:
            self.logMessage.emit(f"Warning: Failed to style raster: {str(e)}")

    def _generate_classification_statistics(self, classification_array):
        """Generate comprehensive classification statistics."""
        try:
            unique, counts = np.unique(classification_array, return_counts=True)
            total_pixels = classification_array.size

            stats = {
                "total_pixels": int(total_pixels),
                "class_distribution": dict(zip(unique.astype(int), counts.astype(int))),
                "class_percentages": dict(
                    zip(unique.astype(int), (counts / total_pixels * 100).round(2))
                ),
            }

            # Calculate areas if we have spatial information
            try:
                extent = self.raster_layer.extent()
                x_res = (
                    extent.xMaximum() - extent.xMinimum()
                ) / classification_array.shape[1]
                y_res = (
                    extent.yMaximum() - extent.yMinimum()
                ) / classification_array.shape[0]
                pixel_area_m2 = abs(x_res * y_res)

                class_areas = {}
                for class_val, pixel_count in zip(unique, counts):
                    area_m2 = pixel_count * pixel_area_m2
                    area_ha = area_m2 / 10000  # Convert to hectares
                    class_areas[int(class_val)] = {
                        "area_m2": round(area_m2, 2),
                        "area_ha": round(area_ha, 2),
                    }

                stats["class_areas"] = class_areas

            except Exception as e:
                self.logMessage.emit(f"Warning: Could not calculate areas: {str(e)}")

            return stats

        except Exception as e:
            raise Exception(f"Statistics generation failed: {str(e)}")

    def finished(self, result):
        """Called when task is finished."""
        if self.exception:
            self.errorOccurred.emit(str(self.exception))
        elif result:
            self.logMessage.emit("Classification task completed successfully")
        else:
            self.errorOccurred.emit("Classification task failed")
