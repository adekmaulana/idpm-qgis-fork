import os
import numpy as np
from osgeo import gdal
from qgis.core import QgsTask
from PyQt5.QtCore import pyqtSignal


class FalseColorTask(QgsTask):
    """
    A QGIS task to create a False Color composite image from NIR, Red, and Green bands.
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

    def run(self):
        try:
            self.setProgress(10)
            if self.isCanceled():
                return False

            # Open datasets
            nir_ds = gdal.Open(self.nir_path)
            red_ds = gdal.Open(self.red_path)
            green_ds = gdal.Open(self.green_path)

            if nir_ds is None or red_ds is None or green_ds is None:
                self.exception = Exception(
                    "One or more band files could not be opened."
                )
                return False

            # Read bands as arrays
            self.setProgress(30)
            nir_band = nir_ds.GetRasterBand(1).ReadAsArray()
            red_band = red_ds.GetRasterBand(1).ReadAsArray()
            green_band = green_ds.GetRasterBand(1).ReadAsArray()

            if self.isCanceled():
                return False

            # Create the output file
            self.setProgress(50)
            driver = gdal.GetDriverByName("GTiff")
            self.false_color_path = os.path.join(
                self.folder_path, f"{self.raster_id}_FalseColor.tif"
            )

            out_ds = driver.Create(
                self.false_color_path,
                red_ds.RasterXSize,
                red_ds.RasterYSize,
                3,  # 3 bands for False Color
                gdal.GDT_Byte,
            )

            if out_ds is None:
                self.exception = Exception("Failed to create output dataset.")
                return False

            # Write bands to the new file (NIR, Red, Green)
            self.setProgress(70)
            out_ds.GetRasterBand(1).WriteArray(nir_band)
            out_ds.GetRasterBand(2).WriteArray(red_band)
            out_ds.GetRasterBand(3).WriteArray(green_band)

            # Set projection and geotransform
            out_ds.SetProjection(red_ds.GetProjection())
            out_ds.SetGeoTransform(red_ds.GetGeoTransform())

            out_ds.FlushCache()
            self.setProgress(90)
            return True

        except Exception as e:
            self.exception = e
            return False
        finally:
            # Clean up datasets
            nir_ds = None
            red_ds = None
            green_ds = None
            out_ds = None
            self.setProgress(100)

    def finished(self, result):
        if result:
            self.calculationFinished.emit(self.false_color_path)
        else:
            if self.exception:
                self.errorOccurred.emit(
                    f"False Color task failed: {str(self.exception)}"
                )
            else:
                self.errorOccurred.emit("False Color task was canceled.")
