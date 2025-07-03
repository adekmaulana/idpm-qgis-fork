import os

from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
from qgis.core import (
    QgsTask,
    QgsRasterLayer,
)
from PyQt5.QtCore import pyqtSignal


class RasterCalculatorTask(QgsTask):
    """
    A QGIS task to perform a custom raster calculation in the background.
    """

    calculationFinished = pyqtSignal(str, str, str)  # path, name, stac_id
    errorOccurred = pyqtSignal(str, str)  # error_msg, stac_id

    def __init__(
        self,
        formula: str,
        band_paths: dict,
        coefficients: dict,
        output_path: str,
        stac_id: str,
    ):
        task_name = f"Calculating '{os.path.basename(output_path)}'"
        super().__init__(task_name, QgsTask.CanCancel)
        self.formula = formula
        self.band_paths = band_paths
        self.coefficients = coefficients
        self.output_path = output_path
        self.stac_id = stac_id
        self.exception = None

    def run(self):
        """
        Executes the raster calculation. This method runs on a background thread.
        """
        try:
            self.setProgress(10)
            if self.isCanceled():
                return False

            entries = []
            ref_layer = None
            layers_to_keep_alive = []

            total_bands = len(self.band_paths)
            for i, (band_name, path) in enumerate(self.band_paths.items()):
                if self.isCanceled():
                    return False

                layer = QgsRasterLayer(path, band_name)
                if not layer.isValid():
                    self.exception = Exception(f"Could not load band: {band_name}")
                    return False
                layers_to_keep_alive.append(layer)

                entry = QgsRasterCalculatorEntry()
                entry.ref = f"{band_name}@1"
                entry.raster = layer
                entry.bandNumber = 1
                entries.append(entry)
                if ref_layer is None:
                    ref_layer = layer

                # Update progress as bands are loaded
                self.setProgress(10 + ((i + 1) / total_bands) * 40)

            if not ref_layer:
                self.exception = Exception("No valid reference layer for calculation.")
                return False

            if self.isCanceled():
                return False
            self.setProgress(50)

            # Prepare the formula string for QGIS by quoting bands and substituting coefficients
            calc_formula = self.formula
            for band_name in self.band_paths.keys():
                calc_formula = calc_formula.replace(band_name, f'"{band_name}@1"')
            for coeff_name, coeff_value in self.coefficients.items():
                calc_formula = calc_formula.replace(str(coeff_name), str(coeff_value))

            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

            # Create and run the calculator
            calc = QgsRasterCalculator(
                calc_formula,
                self.output_path,
                "GTiff",
                ref_layer.extent(),
                ref_layer.width(),
                ref_layer.height(),
                entries,
            )

            result = calc.processCalculation()
            self.setProgress(95)

            if result != QgsRasterCalculator.Success:
                self.exception = Exception(
                    f"Raster calculation failed with error code: {result}"
                )
                return False

            return True

        except Exception as e:
            self.exception = e
            return False
        finally:
            self.setProgress(100)

    def finished(self, result):
        """
        This method is called on the main thread when the task is finished.
        """
        if result:
            # Emit success signal with necessary info
            output_name = (
                os.path.basename(self.output_path)
                .replace(f"{self.stac_id}_", "")
                .replace(".tif", "")
            )
            self.calculationFinished.emit(self.output_path, output_name, self.stac_id)
        else:
            # Emit error signal
            error_msg = (
                str(self.exception)
                if self.exception
                else "Calculation task was canceled."
            )
            self.errorOccurred.emit(error_msg, self.stac_id)
