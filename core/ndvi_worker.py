import os

import numpy as np
from osgeo import gdal
from qgis.core import QgsTask

from PyQt5.QtCore import pyqtSignal


class NdvITask(QgsTask):
    # Rename the signal to avoid conflict with QgsTask's finished() method
    calculationFinished = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, red_path, nir_path, folder_path, raster_id):
        super().__init__(f"Calculate NDVI: {raster_id}", QgsTask.CanCancel)
        self.red_path = red_path
        self.nir_path = nir_path
        self.folder_path = folder_path
        self.raster_id = raster_id
        self.ndvi_path = None
        self.exception = None

    def run(self):
        try:
            # Open datasets
            self.setProgress(10)
            red_ds = gdal.Open(self.red_path)
            nir_ds = gdal.Open(self.nir_path)

            if self.isCanceled():
                return False

            # Read bands
            self.setProgress(30)
            red_band = red_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            nir_band = nir_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

            if self.isCanceled():
                return False

            # Calculate NDVI
            self.setProgress(50)
            ndvi = (nir_band - red_band) / (
                nir_band + red_band + 1e-10  # < Dynamic
            )  # Avoid division by zero

            if self.isCanceled():
                return False

            # Save result
            self.setProgress(70)
            driver = gdal.GetDriverByName("GTiff")
            self.ndvi_path = os.path.join(
                self.folder_path, f"{self.raster_id}_NDVI.tif"
            )
            ndvi_ds = driver.Create(
                self.ndvi_path,
                red_ds.RasterXSize,
                red_ds.RasterYSize,
                1,
                gdal.GDT_Float32,
            )

            ndvi_ds.GetRasterBand(1).WriteArray(ndvi)
            ndvi_ds.SetProjection(red_ds.GetProjection())
            ndvi_ds.SetGeoTransform(red_ds.GetGeoTransform())
            ndvi_ds.FlushCache()

            self.setProgress(90)
            return True

        except Exception as e:
            self.exception = e
            return False
        finally:
            # Cleanup
            red_ds = None
            nir_ds = None
            ndvi_ds = None
            self.setProgress(100)

    # Override the finished() method but use a different name for our signal
    def finished(self, result):
        if result:
            self.calculationFinished.emit(self.ndvi_path)
        else:
            if self.exception:
                self.errorOccurred.emit(str(self.exception))
            else:
                self.errorOccurred.emit("Task was canceled")
