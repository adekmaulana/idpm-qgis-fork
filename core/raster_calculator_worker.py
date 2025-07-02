import os
import re
import numpy as np
from osgeo import gdal
from qgis.core import Qgis, QgsMessageLog, QgsTask
from PyQt5.QtCore import pyqtSignal


class RasterCalculatorTask(QgsTask):
    """
    A QGIS task to perform a custom calculation on a set of raster bands.
    """

    calculationFinished = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(
        self,
        formula: str,
        band_paths: dict,
        coefficients: dict,
        output_path: str,
        raster_id: str,
    ):
        super().__init__(
            f"Calculating '{os.path.basename(output_path)}'", QgsTask.CanCancel
        )
        self.formula = formula
        self.band_paths = band_paths
        self.coefficients = coefficients
        self.output_path = output_path
        self.raster_id = raster_id
        self.exception = None

    def run(self):
        try:
            self.setProgress(10)
            if self.isCanceled():
                return False

            # --- Load band arrays ---
            band_arrays = {}
            ref_ds = None
            for band_name, path in self.band_paths.items():
                ds = gdal.Open(path)
                if ds is None:
                    self.exception = Exception(f"Could not open band file: {path}")
                    return False
                if ref_ds is None:
                    ref_ds = ds
                band_arrays[band_name] = (
                    ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
                )

            if ref_ds is None:
                self.exception = Exception("No valid bands were loaded.")
                return False

            self.setProgress(40)
            if self.isCanceled():
                return False

            # --- Evaluate the formula ---
            namespace = band_arrays
            namespace["np"] = np
            # *** ADDED: Add custom coefficients to the calculation namespace ***
            namespace.update(self.coefficients)

            # Sanitize formula to only allow specific variable names and basic math
            # *** ADDED: Include coefficient keys in the set of allowed names ***
            allowed_names = (
                set(self.band_paths.keys()) | {"np"} | set(self.coefficients.keys())
            )
            found_names = set(re.findall("[a-zA-Z_][a-zA-Z0-9_]*", self.formula))

            if not found_names.issubset(allowed_names):
                invalid_names = found_names - allowed_names
                self.exception = Exception(
                    f"Formula contains invalid terms: {', '.join(invalid_names)}"
                )
                return False

            result_array = eval(self.formula, {"__builtins__": {}}, namespace)

            self.setProgress(70)
            if self.isCanceled():
                return False

            # --- Save the result ---
            driver = gdal.GetDriverByName("GTiff")
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            out_ds = driver.Create(
                self.output_path,
                ref_ds.RasterXSize,
                ref_ds.RasterYSize,
                1,
                gdal.GDT_Float32,
            )
            if out_ds is None:
                self.exception = Exception("Failed to create output dataset.")
                return False

            out_ds.GetRasterBand(1).WriteArray(result_array)
            out_ds.SetProjection(ref_ds.GetProjection())
            out_ds.SetGeoTransform(ref_ds.GetGeoTransform())
            out_ds.FlushCache()

            self.setProgress(95)
            return True

        except Exception as e:
            self.exception = e
            return False
        finally:
            band_arrays = None
            ref_ds = None
            out_ds = None
            self.setProgress(100)

    def finished(self, result):
        if result:
            self.calculationFinished.emit(self.output_path)
        else:
            if self.exception:
                self.errorOccurred.emit(f"Calculation failed: {str(self.exception)}")
            else:
                self.errorOccurred.emit("Calculation task was canceled.")
