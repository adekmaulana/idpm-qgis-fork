import os
import numpy as np
from osgeo import gdal
from qgis.core import Qgis, QgsMessageLog, QgsTask
from PyQt5.QtCore import pyqtSignal


class FalseColorTask(QgsTask):
    """
    A QGIS task to create a False Color image from NIR, Red, and Green bands.
    """

    calculationFinished = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, nir_path, red_path, green_path, folder_path, raster_id):
        super().__init__(f"Create False Color: {raster_id}", QgsTask.CanCancel)
        self.nir_path = nir_path
        self.red_path = red_path
        self.green_path = green_path
        self.folder_path = folder_path
        self.raster_id = raster_id
        self.false_color_path = None
        self.exception = None

    def _scale_to_uint8(self, band_array, min_val=0, max_val=4000):
        """
        Scales a raster band array to an 8-bit integer range (0-255)
        for visualization. This performs a linear contrast stretch.
        """
        band_array = band_array.astype(np.float32)
        clipped_array = np.clip(band_array, min_val, max_val)
        if max_val == min_val:
            return np.zeros_like(band_array, dtype=np.uint8)
        scaled_array = ((clipped_array - min_val) / (max_val - min_val)) * 255.0
        return scaled_array.astype(np.uint8)

    def run(self):
        try:
            self.setProgress(10)
            nir_ds = gdal.Open(self.nir_path)
            red_ds = gdal.Open(self.red_path)
            green_ds = gdal.Open(self.green_path)

            if self.isCanceled():
                return False
            if not nir_ds or not red_ds or not green_ds:
                self.exception = Exception(
                    "Could not open one or more required bands (NIR, Red, Green)."
                )
                return False

            nir_band = nir_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            red_band = red_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            green_band = green_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

            self.setProgress(50)
            if self.isCanceled():
                return False

            driver = gdal.GetDriverByName("GTiff")
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

            # *** FIX: Scale bands to 0-255 before writing to the 8-bit file ***
            nir_scaled = self._scale_to_uint8(nir_band)
            red_scaled = self._scale_to_uint8(red_band)
            green_scaled = self._scale_to_uint8(green_band)

            fc_ds.GetRasterBand(1).WriteArray(nir_scaled)  # NIR -> Red channel
            fc_ds.GetRasterBand(2).WriteArray(red_scaled)  # Red -> Green channel
            fc_ds.GetRasterBand(3).WriteArray(green_scaled)  # Green -> Blue channel

            fc_ds.SetProjection(red_ds.GetProjection())
            fc_ds.SetGeoTransform(red_ds.GetGeoTransform())
            fc_ds.FlushCache()
            fc_ds = None
            self.setProgress(90)

            return True

        except Exception as e:
            self.exception = e
            return False
        finally:
            nir_ds = None
            red_ds = None
            green_ds = None
            self.setProgress(100)

    def finished(self, result):
        if result:
            self.calculationFinished.emit(self.false_color_path)
        else:
            if self.exception:
                self.errorOccurred.emit(str(self.exception))
            else:
                self.errorOccurred.emit("False Color task was canceled or failed.")
