import os
from typing import Dict, Optional, List
from qgis.core import (
    QgsTask,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    Qgis,
)
from PyQt5.QtCore import pyqtSignal


class AoiVisualProcessingTask(QgsTask):
    """Background task for processing visual assets with AOI - downloads directly from URL."""

    visualProcessed = pyqtSignal(str, str, str)  # output_path, asset_id, layer_name
    errorOccurred = pyqtSignal(str, str)  # error_msg, asset_id

    def __init__(
        self,
        asset_id: str,
        visual_url: str,
        aoi_rect: QgsRectangle,
        canvas_crs: QgsCoordinateReferenceSystem,
        cache_dir: str,
    ):
        task_name = f"Processing Visual AOI for {asset_id}"
        super().__init__(task_name, QgsTask.CanCancel)

        self.asset_id = asset_id
        self.visual_url = visual_url
        self.aoi_rect = aoi_rect
        self.canvas_crs = canvas_crs
        self.cache_dir = cache_dir
        self.exception = None

    def run(self):
        """Execute AOI visual processing - download directly from URL."""
        try:
            from ..core import CogAoiLoader

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Initialize COG loader
            cog_loader = CogAoiLoader()

            # Create output path
            visual_cache_path = os.path.join(
                self.cache_dir, f"cropped_{os.path.basename(self.visual_url)}"
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            # Download directly from URL with AOI
            QgsMessageLog.logMessage(
                "Downloading visual from URL for AOI", "AOIProcessing", Qgis.Info
            )

            self.setProgress(40)
            if self.isCanceled():
                return False

            cropped_path = cog_loader.load_cog_with_aoi(
                self.visual_url,
                self.aoi_rect,
                self.canvas_crs,
                cache_dir=self.cache_dir,
            )

            self.setProgress(80)
            if self.isCanceled():
                return False

            if cropped_path and cropped_path != visual_cache_path:
                # Rename to consistent cache name
                if os.path.exists(visual_cache_path):
                    os.remove(visual_cache_path)
                os.rename(cropped_path, visual_cache_path)
                cropped_path = visual_cache_path

            if not cropped_path or not os.path.exists(cropped_path):
                self.exception = Exception("Failed to download visual AOI from URL")
                return False

            self.setProgress(100)
            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """Called on main thread when task completes."""
        if result and not self.isCanceled():
            # Emit success
            visual_cache_path = os.path.join(
                self.cache_dir, f"cropped_{os.path.basename(self.visual_url)}"
            )
            layer_name = f"{self.asset_id}_Visual_AOI"
            self.visualProcessed.emit(visual_cache_path, self.asset_id, layer_name)
        else:
            # Emit error
            error_msg = (
                str(self.exception)
                if self.exception
                else "Visual AOI processing was canceled"
            )
            self.errorOccurred.emit(error_msg, self.asset_id)


class AoiNdviProcessingTask(QgsTask):
    """Background task for processing NDVI with AOI - downloads bands directly from URLs."""

    ndviProcessed = pyqtSignal(str, str, str)  # output_path, asset_id, layer_name
    errorOccurred = pyqtSignal(str, str)  # error_msg, asset_id

    def __init__(
        self,
        asset_id: str,
        nir_url: str,
        red_url: str,
        aoi_rect: QgsRectangle,
        canvas_crs: QgsCoordinateReferenceSystem,
        cache_dir: str,
    ):
        task_name = f"Processing NDVI AOI for {asset_id}"
        super().__init__(task_name, QgsTask.CanCancel)

        self.asset_id = asset_id
        self.nir_url = nir_url
        self.red_url = red_url
        self.aoi_rect = aoi_rect
        self.canvas_crs = canvas_crs
        self.cache_dir = cache_dir
        self.exception = None

    def run(self):
        """Execute AOI NDVI processing - download bands directly from URLs."""
        try:
            from ..core import CogBandProcessor

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Always download fresh - no cache checking
            ndvi_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_ndvi_aoi.tif"
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            # Initialize band processor
            band_processor = CogBandProcessor(self.cache_dir)

            # Prepare band URLs - download directly without checking local files
            band_urls = {"nir": self.nir_url, "red": self.red_url}

            self.setProgress(40)
            if self.isCanceled():
                return False

            QgsMessageLog.logMessage(
                "Downloading NIR and Red bands from URLs for NDVI AOI processing",
                "AOIProcessing",
                Qgis.Info,
            )

            # Process bands - download directly from URLs (no local files)
            result_paths = band_processor.process_bands_with_aoi(
                band_urls,
                self.aoi_rect,
                self.canvas_crs,
                self.asset_id,
                {},  # Empty local paths
            )

            self.setProgress(70)
            if self.isCanceled():
                return False

            if "nir" not in result_paths or "red" not in result_paths:
                self.exception = Exception(
                    "Failed to download required bands (NIR, Red)"
                )
                return False

            # Calculate NDVI
            QgsMessageLog.logMessage(
                "Calculating NDVI from downloaded bands...", "AOIProcessing", Qgis.Info
            )

            success = band_processor.calculate_ndvi_from_aoi_bands(
                result_paths["nir"], result_paths["red"], ndvi_output_path
            )

            self.setProgress(90)
            if self.isCanceled():
                return False

            if not success or not os.path.exists(ndvi_output_path):
                self.exception = Exception("Failed to calculate NDVI")
                return False

            self.setProgress(100)
            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """Called on main thread when task completes."""
        if result and not self.isCanceled():
            # Emit success
            ndvi_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_ndvi_aoi.tif"
            )
            layer_name = f"{self.asset_id}_NDVI_AOI"
            self.ndviProcessed.emit(ndvi_output_path, self.asset_id, layer_name)
        else:
            # Emit error
            error_msg = (
                str(self.exception)
                if self.exception
                else "NDVI AOI processing was canceled"
            )
            self.errorOccurred.emit(error_msg, self.asset_id)


class AoiFalseColorProcessingTask(QgsTask):
    """Background task for processing False Color with AOI - downloads bands directly from URLs."""

    falseColorProcessed = pyqtSignal(str, str, str)  # output_path, asset_id, layer_name
    errorOccurred = pyqtSignal(str, str)  # error_msg, asset_id

    def __init__(
        self,
        asset_id: str,
        band_urls: Dict[str, str],
        aoi_rect: QgsRectangle,
        canvas_crs: QgsCoordinateReferenceSystem,
        cache_dir: str,
    ):
        task_name = f"Processing False Color AOI for {asset_id}"
        super().__init__(task_name, QgsTask.CanCancel)

        self.asset_id = asset_id
        self.band_urls = band_urls
        self.aoi_rect = aoi_rect
        self.canvas_crs = canvas_crs
        self.cache_dir = cache_dir
        self.exception = None

    def run(self):
        """Execute AOI False Color processing - download bands directly from URLs."""
        try:
            from ..core import CogBandProcessor

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Always download fresh - no cache checking
            fc_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_falsecolor_aoi.tif"
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            # Initialize band processor
            band_processor = CogBandProcessor(self.cache_dir)

            self.setProgress(40)
            if self.isCanceled():
                return False

            QgsMessageLog.logMessage(
                "Downloading NIR, Red, and Green bands from URLs for False Color AOI processing",
                "AOIProcessing",
                Qgis.Info,
            )

            # Process bands - download directly from URLs (no local files)
            result_paths = band_processor.process_bands_with_aoi(
                self.band_urls,
                self.aoi_rect,
                self.canvas_crs,
                self.asset_id,
                {},  # Empty local paths
            )

            self.setProgress(70)
            if self.isCanceled():
                return False

            required_bands = ["nir", "red", "green"]
            missing_bands = [
                band for band in required_bands if band not in result_paths
            ]
            if missing_bands:
                self.exception = Exception(
                    f"Failed to download required bands: {', '.join(missing_bands)}"
                )
                return False

            # Create False Color composite
            QgsMessageLog.logMessage(
                "Creating False Color composite from downloaded bands...",
                "AOIProcessing",
                Qgis.Info,
            )

            success = band_processor.calculate_false_color_composite(
                result_paths["nir"],
                result_paths["red"],
                result_paths["green"],
                fc_output_path,
            )

            self.setProgress(90)
            if self.isCanceled():
                return False

            if not success or not os.path.exists(fc_output_path):
                self.exception = Exception("Failed to create False Color composite")
                return False

            self.setProgress(100)
            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """Called on main thread when task completes."""
        if result and not self.isCanceled():
            # Emit success
            fc_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_falsecolor_aoi.tif"
            )
            layer_name = f"{self.asset_id}_FalseColor_AOI"
            self.falseColorProcessed.emit(fc_output_path, self.asset_id, layer_name)
        else:
            # Emit error
            error_msg = (
                str(self.exception)
                if self.exception
                else "False Color AOI processing was canceled"
            )
            self.errorOccurred.emit(error_msg, self.asset_id)


class AoiCustomCalculationTask(QgsTask):
    """Background task for custom calculations with AOI - downloads bands directly from URLs."""

    calculationProcessed = pyqtSignal(
        str, str, str, str
    )  # output_path, asset_id, layer_name, formula
    errorOccurred = pyqtSignal(str, str)  # error_msg, asset_id

    def __init__(
        self,
        asset_id: str,
        band_urls: Dict[str, str],
        formula: str,
        output_name: str,
        coefficients: Dict,
        aoi_rect: QgsRectangle,
        canvas_crs: QgsCoordinateReferenceSystem,
        cache_dir: str,
    ):
        task_name = f"Processing {output_name} AOI for {asset_id}"
        super().__init__(task_name, QgsTask.CanCancel)

        self.asset_id = asset_id
        self.band_urls = band_urls
        self.formula = formula
        self.output_name = output_name
        self.coefficients = coefficients
        self.aoi_rect = aoi_rect
        self.canvas_crs = canvas_crs
        self.cache_dir = cache_dir
        self.exception = None

    def run(self):
        """Execute AOI custom calculation processing - download bands directly from URLs."""
        try:
            from ..core import CogBandProcessor

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Always download fresh - no cache checking
            output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_{self.output_name}_aoi.tif"
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            # Initialize band processor
            band_processor = CogBandProcessor(self.cache_dir)

            self.setProgress(40)
            if self.isCanceled():
                return False

            band_names = list(self.band_urls.keys())
            QgsMessageLog.logMessage(
                f"Downloading {', '.join(band_names)} bands from URLs for {self.output_name} AOI processing",
                "AOIProcessing",
                Qgis.Info,
            )

            # Process bands - download directly from URLs (no local files)
            result_paths = band_processor.process_bands_with_aoi(
                self.band_urls,
                self.aoi_rect,
                self.canvas_crs,
                self.asset_id,
                {},  # Empty local paths
            )

            self.setProgress(60)
            if self.isCanceled():
                return False

            # Check if all required bands were processed
            required_bands = list(self.band_urls.keys())
            missing_bands = [
                band for band in required_bands if band not in result_paths
            ]
            if missing_bands:
                self.exception = Exception(
                    f"Failed to download required bands: {', '.join(missing_bands)}"
                )
                return False

            # Calculate custom index using the modified method
            QgsMessageLog.logMessage(
                f"Calculating {self.output_name} from downloaded bands...",
                "AOIProcessing",
                Qgis.Info,
            )

            success = band_processor.calculate_custom_index(
                result_paths, self.formula, output_path, self.coefficients
            )

            self.setProgress(90)
            if self.isCanceled():
                return False

            if not success or not os.path.exists(output_path):
                self.exception = Exception(f"Failed to calculate {self.output_name}")
                return False

            self.setProgress(100)
            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """Called on main thread when task completes."""
        if result and not self.isCanceled():
            # Emit success
            output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_{self.output_name}_aoi.tif"
            )
            layer_name = f"{self.asset_id}_{self.output_name}_AOI"
            self.calculationProcessed.emit(
                output_path, self.asset_id, layer_name, self.formula
            )
        else:
            # Emit error
            error_msg = (
                str(self.exception)
                if self.exception
                else f"{self.output_name} AOI processing was canceled"
            )
            self.errorOccurred.emit(error_msg, self.asset_id)
