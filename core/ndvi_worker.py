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

    def _scale_to_uint8(self, band_array, min_val=0, max_val=4000):
        """
        Scales a raster band array to an 8-bit integer range (0-255)
        for visualization. This performs a linear contrast stretch.
        """
        # Ensure the array is float to avoid overflow issues during calculations
        band_array = band_array.astype(np.float32)
        # Clip the data to the desired range to handle outliers
        clipped_array = np.clip(band_array, min_val, max_val)
        # Avoid division by zero if max and min are the same
        if max_val == min_val:
            return np.zeros_like(band_array, dtype=np.uint8)
        # Scale the clipped data to the 0-255 range
        scaled_array = ((clipped_array - min_val) / (max_val - min_val)) * 255.0
        return scaled_array.astype(np.uint8)

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

            # Add a small epsilon to the denominator to avoid division by zero
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
                        gdal.GDT_Byte,  # Create an 8-bit raster
                    )

                    # *** FIX: Scale bands to 0-255 before writing to the 8-bit file ***
                    nir_scaled = self._scale_to_uint8(nir_band)
                    red_scaled = self._scale_to_uint8(red_band)
                    green_scaled = self._scale_to_uint8(green_band)

                    fc_ds.GetRasterBand(1).WriteArray(nir_scaled)  # NIR -> Red channel
                    fc_ds.GetRasterBand(2).WriteArray(
                        red_scaled
                    )  # Red -> Green channel
                    fc_ds.GetRasterBand(3).WriteArray(
                        green_scaled
                    )  # Green -> Blue channel

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
