import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, accuracy_score, classification_report
from sklearn.model_selection import train_test_split
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
)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from osgeo import gdal
import os


def sample_raster_at_point(raster_layer, pt, nodata=None):
    """Sample raster values at a specific point."""
    if not raster_layer.extent().contains(pt):
        return np.array([np.nan] * raster_layer.bandCount(), dtype=np.float32)

    provider = raster_layer.dataProvider()
    band_count = raster_layer.bandCount()
    vals = []

    for band in range(1, band_count + 1):
        ident = provider.identify(pt, QgsRaster.IdentifyFormatValue)
        if ident.isValid():
            band_val = ident.results().get(band, np.nan)
            vals.append(band_val)
        else:
            vals.append(np.nan)

    arr = np.array(vals, dtype=np.float32)
    if nodata is not None and np.any(arr == nodata):
        return np.array([np.nan] * band_count, dtype=np.float32)

    return arr


def pixel_to_map(raster_layer, col, row):
    """Convert pixel coordinates to map coordinates."""
    extent = raster_layer.extent()
    xres = raster_layer.rasterUnitsPerPixelX()
    yres = raster_layer.rasterUnitsPerPixelY()
    x = extent.xMinimum() + col * xres + xres / 2.0
    y = extent.yMaximum() - row * yres - yres / 2.0
    return (x, y)


def get_geotransform_from_layer(raster_layer):
    """Get geotransform parameters from raster layer."""
    extent = raster_layer.extent()
    cols = raster_layer.width()
    rows = raster_layer.height()
    xres = (extent.xMaximum() - extent.xMinimum()) / float(cols)
    yres = (extent.yMaximum() - extent.yMinimum()) / float(rows)
    return (
        extent.xMinimum(),  # top left x
        xres,  # w-e pixel resolution
        0,  # rotation, 0 if image is "north up"
        extent.yMaximum(),  # top left y
        0,  # rotation, 0 if image is "north up"
        -yres,  # n-s pixel resolution (negative value)
    )


class MangroveClassificationTask(QgsTask):
    """Task for running mangrove classification in background."""

    # Signals
    classificationFinished = pyqtSignal(str, dict, str)  # output_path, results, method
    errorOccurred = pyqtSignal(str)

    def __init__(self, raster_layer, roi_layer, output_path, method, test_size=0.3):
        super().__init__(f"Mangrove Classification - {method}", QgsTask.CanCancel)
        self.raster_layer = raster_layer
        self.roi_layer = roi_layer
        self.output_path = output_path
        self.method = method
        self.test_size = test_size
        self.exception = None
        self.results = {}

    def run(self):
        """Execute the classification task."""
        try:
            self.setProgress(10)

            # Extract features from ROI
            X, y = self._extract_features()
            if X is None or len(X) == 0:
                self.exception = Exception("No valid training samples found.")
                return False

            self.setProgress(30)

            # Prepare data
            X = np.array(X)
            y = np.array(y)
            valid_indices = ~np.isnan(X).any(axis=1)
            X = X[valid_indices]
            y = y[valid_indices]

            if len(X) == 0:
                self.exception = Exception(
                    "No valid samples after filtering NaN values."
                )
                return False

            self.setProgress(50)

            # Scale and split data
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            X_train, X_val, y_train, y_val = train_test_split(
                X_scaled, y, test_size=self.test_size, random_state=42, stratify=y
            )

            # Train classifier
            if self.method == "SVM":
                clf = SVC(kernel="rbf", C=1, gamma="scale")
            elif self.method == "Random Forest":
                clf = RandomForestClassifier(n_estimators=100, random_state=42)
            elif self.method == "Gradient Boosting":
                clf = GradientBoostingClassifier(n_estimators=100, random_state=42)
            else:
                self.exception = Exception(f"Unknown method: {self.method}")
                return False

            clf.fit(X_train, y_train)

            self.setProgress(70)

            # Validate model
            y_pred = clf.predict(X_val)
            cm = confusion_matrix(y_val, y_pred)
            acc = accuracy_score(y_val, y_pred)
            report = classification_report(y_val, y_pred)

            self.results = {
                "confusion_matrix": cm,
                "accuracy": acc,
                "classification_report": report,
                "n_samples": len(X),
                "method": self.method,
            }

            self.setProgress(90)

            # Apply to full raster
            success = self._apply_classification(clf, scaler)
            if not success:
                return False

            self.setProgress(100)
            return True

        except Exception as e:
            self.exception = e
            return False

    def _extract_features(self):
        """Extract training features from ROI layer."""
        X = []
        y = []

        # Get nodata value
        gdal_ds = gdal.Open(self.raster_layer.source())
        band = gdal_ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()

        roi_feats = list(self.roi_layer.getFeatures())

        for feat in roi_feats:
            geom = feat.geometry()

            # Get class label
            if "Class" in feat.fields().names():
                label = feat["Class"]
            elif "class" in feat.fields().names():
                label = feat["class"]
            elif "label" in feat.fields().names():
                label = feat["label"]
            else:
                label = 1

            try:
                label = int(label)
            except Exception:
                label = 0

            # Extract samples based on geometry type
            if (
                self.roi_layer.geometryType() == QgsWkbTypes.PointGeometry
                and geom.type() == QgsWkbTypes.PointGeometry
            ):
                pt = geom.asPoint()
                if self.raster_layer.extent().contains(pt):
                    vals = sample_raster_at_point(self.raster_layer, pt, nodata)
                    if not np.isnan(vals).any():
                        X.append(vals)
                        y.append(label)

            elif (
                self.roi_layer.geometryType() == QgsWkbTypes.PolygonGeometry
                and geom.type() == QgsWkbTypes.PolygonGeometry
            ):
                bbox = geom.boundingBox()
                xmin, xmax = bbox.xMinimum(), bbox.xMaximum()
                ymin, ymax = bbox.yMinimum(), bbox.yMaximum()

                xres = self.raster_layer.rasterUnitsPerPixelX()
                yres = self.raster_layer.rasterUnitsPerPixelY()

                col_start = int((xmin - self.raster_layer.extent().xMinimum()) / xres)
                col_end = int((xmax - self.raster_layer.extent().xMinimum()) / xres)
                row_start = int((self.raster_layer.extent().yMaximum() - ymax) / yres)
                row_end = int((self.raster_layer.extent().yMaximum() - ymin) / yres)

                for row in range(row_start, row_end + 1):
                    for col in range(col_start, col_end + 1):
                        x, y_coord = pixel_to_map(self.raster_layer, col, row)
                        pt = QgsPointXY(x, y_coord)
                        if geom.contains(pt):
                            vals = sample_raster_at_point(self.raster_layer, pt, nodata)
                            if not np.isnan(vals).any():
                                X.append(vals)
                                y.append(label)

        return X, y

    def _apply_classification(self, clf, scaler):
        """Apply classification to full raster."""
        try:
            provider = self.raster_layer.dataProvider()
            cols = self.raster_layer.width()
            rows = self.raster_layer.height()
            band_count = provider.bandCount()

            result_array = np.zeros((rows, cols), dtype=np.uint8)
            block_size = 100

            # Get nodata value
            gdal_ds = gdal.Open(self.raster_layer.source())
            band = gdal_ds.GetRasterBand(1)
            nodata = band.GetNoDataValue()

            for row_block in range(0, rows, block_size):
                for col_block in range(0, cols, block_size):
                    if self.isCanceled():
                        return False

                    row_end = min(row_block + block_size, rows)
                    col_end = min(col_block + block_size, cols)
                    block_rows = row_end - row_block
                    block_cols = col_end - col_block

                    block_data = np.zeros(
                        (block_rows, block_cols, band_count), dtype=np.float32
                    )

                    for i in range(block_rows):
                        for j in range(block_cols):
                            x, y_coord = pixel_to_map(
                                self.raster_layer, col_block + j, row_block + i
                            )
                            pt = QgsPointXY(x, y_coord)
                            ident = provider.identify(pt, QgsRaster.IdentifyFormatValue)

                            if ident.isValid():
                                vals = list(ident.results().values())
                                vals_np = np.array(vals, dtype=np.float32)
                                if nodata is not None and np.any(vals_np == nodata):
                                    block_data[i, j, :] = np.nan
                                else:
                                    block_data[i, j, :] = vals_np
                            else:
                                block_data[i, j, :] = np.nan

                    block_data_reshaped = block_data.reshape(-1, band_count)
                    valid_mask = ~np.isnan(block_data_reshaped).any(axis=1)

                    if np.any(valid_mask):
                        block_scaled = scaler.transform(block_data_reshaped[valid_mask])
                        preds = clf.predict(block_scaled)
                        result_block = np.zeros(
                            block_data_reshaped.shape[0], dtype=np.uint8
                        )
                        result_block[valid_mask] = preds.astype(np.uint8)
                        result_block[~valid_mask] = 0
                    else:
                        result_block = np.zeros(
                            block_data_reshaped.shape[0], dtype=np.uint8
                        )

                    result_block_2d = result_block.reshape(block_rows, block_cols)
                    result_array[row_block:row_end, col_block:col_end] = result_block_2d

            # Save result
            if self.output_path:
                driver = gdal.GetDriverByName("GTiff")
                out_raster = driver.Create(
                    self.output_path, cols, rows, 1, gdal.GDT_Byte
                )
                geo = get_geotransform_from_layer(self.raster_layer)
                out_raster.SetGeoTransform(geo)
                out_raster.SetProjection(self.raster_layer.crs().toWkt())
                out_band = out_raster.GetRasterBand(1)
                out_band.WriteArray(result_array)
                out_band.SetNoDataValue(0)
                out_band.FlushCache()
                out_raster = None

                # Load result into QGIS
                result_layer = QgsRasterLayer(
                    self.output_path, f"Mangrove Classification - {self.method}"
                )
                if result_layer.isValid():
                    # Apply symbology
                    shader = QgsRasterShader()
                    color_ramp = QgsColorRampShader()
                    color_ramp.setColorRampType(QgsColorRampShader.Discrete)
                    color_ramp.setColorRampItemList(
                        [
                            QgsColorRampShader.ColorRampItem(
                                0, QColor(255, 0, 0, 255), "Non-Mangrove"
                            ),
                            QgsColorRampShader.ColorRampItem(
                                1, QColor(0, 255, 0, 255), "Mangrove"
                            ),
                        ]
                    )
                    shader.setRasterShaderFunction(color_ramp)
                    renderer = QgsSingleBandPseudoColorRenderer(
                        result_layer.dataProvider(), 1, shader
                    )
                    result_layer.setRenderer(renderer)

                    QgsProject.instance().addMapLayer(result_layer)

            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """Called when task finishes."""
        if result:
            self.classificationFinished.emit(
                self.output_path, self.results, self.method
            )
        else:
            if self.exception:
                self.errorOccurred.emit(str(self.exception))
            else:
                self.errorOccurred.emit("Classification task was canceled or failed.")
