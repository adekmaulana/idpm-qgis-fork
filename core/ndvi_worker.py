import os
import numpy as np
from osgeo import gdal
from qgis.core import Qgis, QgsMessageLog, QgsTask
from PyQt5.QtCore import pyqtSignal


class NdvITask(QgsTask):
    calculationFinished = pyqtSignal(str, str)  # Emit paths for NDVI and False Color
    errorOccurred = pyqtSignal(str)

    def __init__(self, red_path, nir_path, green_path, folder_path, raster_id):
        super().__init__(f"Process Rasters: {raster_id}", QgsTask.CanCancel)
        self.red_path = red_path
        self.nir_path = nir_path
        self.green_path = green_path
        self.folder_path = folder_path
        self.raster_id = raster_id
        self.ndvi_path = None
        self.false_color_path = None
        self.exception = None

    def run(self):
        try:
            # --- NDVI Calculation ---
            self.setProgress(5)
            red_ds = gdal.Open(self.red_path)
            nir_ds = gdal.Open(self.nir_path)

            if self.isCanceled():
                return False
            if not red_ds or not nir_ds:
                self.exception = Exception("Could not open Red or NIR bands for NDVI.")
                return False

            red_band = red_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            nir_band = nir_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

            self.setProgress(25)
            if self.isCanceled():
                return False

            ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10)

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
            self.setProgress(50)

            # --- False Color Composite ---
            if self.green_path and os.path.exists(self.green_path):
                self.setProgress(55)
                green_ds = gdal.Open(self.green_path)
                if self.isCanceled():
                    return False
                if not green_ds:
                    # Don't fail the whole task, just skip false color
                    QgsMessageLog.logMessage(
                        f"Could not open Green band for {self.raster_id}, skipping False Color.",
                        "IDPMPlugin",
                        Qgis.Warning,
                    )
                else:
                    green_band = green_ds.GetRasterBand(1).ReadAsArray()

                    self.setProgress(75)
                    self.false_color_path = os.path.join(
                        self.folder_path, f"{self.raster_id}_FalseColor.tif"
                    )
                    fc_ds = driver.Create(
                        self.false_color_path,
                        red_ds.RasterXSize,
                        red_ds.RasterYSize,
                        3,
                        gdal.GDT_Byte,
                    )

                    fc_ds.GetRasterBand(1).WriteArray(nir_band.astype(np.uint8))  # NIR
                    fc_ds.GetRasterBand(2).WriteArray(red_band.astype(np.uint8))  # Red
                    fc_ds.GetRasterBand(3).WriteArray(
                        green_band.astype(np.uint8)
                    )  # Green

                    fc_ds.SetProjection(red_ds.GetProjection())
                    fc_ds.SetGeoTransform(red_ds.GetGeoTransform())
                    fc_ds.FlushCache()
                    fc_ds = None
                    green_ds = None

            self.setProgress(95)
            return True

        except Exception as e:
            self.exception = e
            return False
        finally:
            red_ds = None
            nir_ds = None
            ndvi_ds = None
            self.setProgress(100)

    def finished(self, result):
        if result:
            self.calculationFinished.emit(self.ndvi_path, self.false_color_path)
        else:
            if self.exception:
                self.errorOccurred.emit(str(self.exception))
            else:
                self.errorOccurred.emit("Task was canceled or failed.")
