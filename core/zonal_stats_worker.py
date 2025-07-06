from qgis.analysis import QgsZonalStatistics
from qgis.core import (
    QgsTask,
    QgsRasterLayer,
    QgsGeometry,
    QgsVectorLayer,
    QgsFeature,
    QgsFields,
    QgsCoordinateReferenceSystem,  # NEW: Import QgsCoordinateReferenceSystem
)
from PyQt5.QtCore import pyqtSignal


class ZonalStatsTask(QgsTask):
    """
    A QGIS task to calculate zonal statistics for a given polygon on a raster layer.
    This is used to analyze the content of an Area of Interest (AOI).
    """

    calculationFinished = pyqtSignal(dict)
    errorOccurred = pyqtSignal(str)

    # MODIFIED: The constructor now accepts the CRS of the AOI geometry
    def __init__(
        self,
        raster_path: str,
        aoi_geometry: QgsGeometry,
        aoi_crs: QgsCoordinateReferenceSystem,
    ):
        super().__init__("Zonal Statistics Calculation", QgsTask.CanCancel)
        self.raster_path = raster_path
        self.aoi_geometry = aoi_geometry
        self.aoi_crs = aoi_crs  # NEW: Store the CRS
        self.stats = {}
        self.exception = None

    def run(self):
        """
        Executes the zonal statistics calculation in a background thread.
        """
        try:
            self.setProgress(10)
            raster_layer = QgsRasterLayer(self.raster_path, "temp_stats_layer")
            if not raster_layer.isValid():
                self.exception = Exception(
                    f"Failed to load raster layer for statistics: {self.raster_path}"
                )
                return False

            if self.isCanceled():
                return False

            self.setProgress(40)

            # --- REFACTORED: Create an in-memory vector layer for the AOI ---
            # MODIFIED: Use the correct CRS for the temporary layer
            mem_layer = QgsVectorLayer(
                f"Polygon?crs={self.aoi_crs.authid()}", "temp_aoi_layer", "memory"
            )
            provider = mem_layer.dataProvider()

            # Add a feature with the AOI geometry to the memory layer
            feature = QgsFeature()
            feature.setGeometry(self.aoi_geometry)
            provider.addFeatures([feature])

            # Use the in-memory layer to calculate zonal statistics
            zonal_stats = QgsZonalStatistics(
                mem_layer, raster_layer, stats=QgsZonalStatistics.Mean
            )
            zonal_stats.calculateStatistics(None)

            self.setProgress(90)

            # The result is now attached as an attribute to the feature in our memory layer
            # We need to retrieve that feature to get the calculated mean.
            feat = next(mem_layer.getFeatures())

            # Find the actual field name for the mean value
            mean_value = None
            for field in feat.fields():
                if "mean" in field.name().lower():
                    mean_value = feat.attribute(field.name())
                    break

            if mean_value is not None:
                self.stats = {"mean": float(mean_value)}
            else:
                self.stats = {"mean": 0.0}

            return True

        except Exception as e:
            self.exception = e
            return False
        finally:
            self.setProgress(100)

    def finished(self, result):
        """
        Called on the main thread when the task is finished.
        """
        if result:
            self.calculationFinished.emit(self.stats)
        else:
            if self.exception:
                self.errorOccurred.emit(str(self.exception))
            else:
                self.errorOccurred.emit("Zonal statistics task was canceled or failed.")
