import os
from datetime import datetime
from typing import Dict, Optional, List
from qgis.core import (
    QgsTask,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsMessageLog,
    Qgis,
)
from PyQt5.QtCore import pyqtSignal


def _generate_timestamp() -> str:
    """Generate timestamp string for unique file naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class AoiVisualProcessingTask(QgsTask):
    """Background task for processing visual assets with AOI - with timestamped files."""

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
        self.timestamp = _generate_timestamp()
        self.exception = None

    def run(self):
        """Execute AOI visual processing - download with timestamped filename."""
        try:
            from ..core import CogAoiLoader

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Initialize COG loader
            cog_loader = CogAoiLoader()

            # Create timestamped output path
            base_name = os.path.basename(self.visual_url).replace(".tif", "")
            visual_cache_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_visual_aoi_{self.timestamp}.tif"
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            QgsMessageLog.logMessage(
                f"Downloading visual from URL for AOI with timestamp {self.timestamp}",
                "AOIProcessing",
                Qgis.Info,
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
                # Rename to timestamped filename
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
            # Emit success with timestamped path
            visual_cache_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_visual_aoi_{self.timestamp}.tif"
            )
            layer_name = f"{self.asset_id}_Visual_AOI_{self.timestamp}"
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
    """Background task for processing NDVI with AOI - with timestamped files."""

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
        self.timestamp = _generate_timestamp()
        self.exception = None

    def run(self):
        """Execute AOI NDVI processing - with timestamped band files."""
        try:
            from ..core import CogBandProcessor

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Create timestamped NDVI output path
            ndvi_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_ndvi_aoi_{self.timestamp}.tif"
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            # Initialize band processor with timestamp
            band_processor = TimestampedCogBandProcessor(self.cache_dir, self.timestamp)

            # Prepare band URLs
            band_urls = {"nir": self.nir_url, "red": self.red_url}

            self.setProgress(40)
            if self.isCanceled():
                return False

            QgsMessageLog.logMessage(
                f"Downloading NIR and Red bands with timestamp {self.timestamp}",
                "AOIProcessing",
                Qgis.Info,
            )

            # Process bands with timestamp
            result_paths = band_processor.process_bands_with_aoi(
                band_urls, self.aoi_rect, self.canvas_crs, self.asset_id, {}
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
            # Emit success with timestamped path
            ndvi_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_ndvi_aoi_{self.timestamp}.tif"
            )
            layer_name = f"{self.asset_id}_NDVI_AOI_{self.timestamp}"
            self.ndviProcessed.emit(ndvi_output_path, self.asset_id, layer_name)
        else:
            error_msg = (
                str(self.exception)
                if self.exception
                else "NDVI AOI processing was canceled"
            )
            self.errorOccurred.emit(error_msg, self.asset_id)


class AoiFalseColorProcessingTask(QgsTask):
    """Background task for processing False Color with AOI - with timestamped files."""

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
        self.timestamp = _generate_timestamp()
        self.exception = None

    def run(self):
        """Execute AOI False Color processing - with timestamped band files."""
        try:
            from ..core import CogBandProcessor

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Create timestamped False Color output path
            fc_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_falsecolor_aoi_{self.timestamp}.tif"
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            # Initialize band processor with timestamp
            band_processor = TimestampedCogBandProcessor(self.cache_dir, self.timestamp)

            self.setProgress(40)
            if self.isCanceled():
                return False

            QgsMessageLog.logMessage(
                f"Downloading NIR, Red, and Green bands with timestamp {self.timestamp}",
                "AOIProcessing",
                Qgis.Info,
            )

            # Process bands with timestamp
            result_paths = band_processor.process_bands_with_aoi(
                self.band_urls, self.aoi_rect, self.canvas_crs, self.asset_id, {}
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
            # Emit success with timestamped path
            fc_output_path = os.path.join(
                self.cache_dir, f"{self.asset_id}_falsecolor_aoi_{self.timestamp}.tif"
            )
            layer_name = f"{self.asset_id}_FalseColor_AOI_{self.timestamp}"
            self.falseColorProcessed.emit(fc_output_path, self.asset_id, layer_name)
        else:
            error_msg = (
                str(self.exception)
                if self.exception
                else "False Color AOI processing was canceled"
            )
            self.errorOccurred.emit(error_msg, self.asset_id)


class AoiCustomCalculationTask(QgsTask):
    """Background task for custom calculations with AOI - with timestamped files."""

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
        self.timestamp = _generate_timestamp()
        self.exception = None

    def run(self):
        """Execute AOI custom calculation processing - with timestamped band files."""
        try:
            from ..core import CogBandProcessor

            self.setProgress(10)
            if self.isCanceled():
                return False

            # Create timestamped calculation output path
            output_path = os.path.join(
                self.cache_dir,
                f"{self.asset_id}_{self.output_name}_aoi_{self.timestamp}.tif",
            )

            self.setProgress(20)
            if self.isCanceled():
                return False

            # Initialize band processor with timestamp
            band_processor = TimestampedCogBandProcessor(self.cache_dir, self.timestamp)

            self.setProgress(40)
            if self.isCanceled():
                return False

            band_names = list(self.band_urls.keys())
            QgsMessageLog.logMessage(
                f"Downloading {', '.join(band_names)} bands with timestamp {self.timestamp}",
                "AOIProcessing",
                Qgis.Info,
            )

            # Process bands with timestamp
            result_paths = band_processor.process_bands_with_aoi(
                self.band_urls, self.aoi_rect, self.canvas_crs, self.asset_id, {}
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

            # Calculate custom index
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
            # Emit success with timestamped path
            output_path = os.path.join(
                self.cache_dir,
                f"{self.asset_id}_{self.output_name}_aoi_{self.timestamp}.tif",
            )
            layer_name = f"{self.asset_id}_{self.output_name}_AOI_{self.timestamp}"
            self.calculationProcessed.emit(
                output_path, self.asset_id, layer_name, self.formula
            )
        else:
            error_msg = (
                str(self.exception)
                if self.exception
                else f"{self.output_name} AOI processing was canceled"
            )
            self.errorOccurred.emit(error_msg, self.asset_id)


class TimestampedCogBandProcessor:
    """
    CogBandProcessor that adds timestamps to all band files to prevent conflicts.
    """

    def __init__(self, cache_dir: str, timestamp: str):
        self.cache_dir = cache_dir
        self.timestamp = timestamp
        os.makedirs(cache_dir, exist_ok=True)

        # Import the original loader
        from ..core import CogAoiLoader

        self.cog_loader = CogAoiLoader()

    def process_bands_with_aoi(
        self,
        band_urls: Dict[str, str],
        aoi_rect: QgsRectangle,
        aoi_crs: QgsCoordinateReferenceSystem,
        stac_id: str,
        local_band_paths: Optional[Dict[str, str]] = None,
        target_resolution: Optional[float] = None,
    ) -> Dict[str, str]:
        """
        Download and process multiple bands with timestamps to prevent file conflicts.
        """
        downloaded_bands = {}

        QgsMessageLog.logMessage(
            f"Starting timestamped AOI band processing ({self.timestamp}) - downloading from URLs",
            "COGProcessor",
            Qgis.Info,
        )

        for band_name, band_url in band_urls.items():
            try:
                # Create timestamped cache filename
                cache_filename = f"{stac_id}_{band_name}_aoi_{self.timestamp}.tif"
                cache_path = os.path.join(self.cache_dir, cache_filename)

                QgsMessageLog.logMessage(
                    f"Downloading {band_name} with timestamp {self.timestamp}",
                    "COGProcessor",
                    Qgis.Info,
                )

                # Always download from URL
                result_path = self.cog_loader.load_cog_with_aoi(
                    band_url, aoi_rect, aoi_crs, target_resolution, self.cache_dir
                )

                if result_path:
                    # Rename to timestamped filename
                    if result_path != cache_path:
                        os.rename(result_path, cache_path)

                    downloaded_bands[band_name] = cache_path

                    # Log success with file size
                    file_size_mb = os.path.getsize(cache_path) / (1024 * 1024)
                    QgsMessageLog.logMessage(
                        f"Downloaded {band_name} with timestamp ({file_size_mb:.2f} MB)",
                        "COGProcessor",
                        Qgis.Info,
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Failed to download {band_name} for AOI",
                        "COGProcessor",
                        Qgis.Warning,
                    )

            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error downloading band {band_name}: {str(e)}",
                    "COGProcessor",
                    Qgis.Critical,
                )

        return downloaded_bands

    def calculate_ndvi_from_aoi_bands(
        self, nir_path: str, red_path: str, output_path: str
    ) -> bool:
        """Calculate NDVI from timestamped band files."""
        # Import the original processor methods
        from ..core import CogBandProcessor

        # Create temporary processor to use existing calculation methods
        temp_processor = CogBandProcessor(self.cache_dir)
        return temp_processor.calculate_ndvi_from_aoi_bands(
            nir_path, red_path, output_path
        )

    def calculate_false_color_composite(
        self, nir_path: str, red_path: str, green_path: str, output_path: str
    ) -> bool:
        """Create False Color composite from timestamped band files."""
        from ..core import CogBandProcessor

        temp_processor = CogBandProcessor(self.cache_dir)
        return temp_processor.calculate_false_color_composite(
            nir_path, red_path, green_path, output_path
        )

    def calculate_custom_index(
        self,
        band_paths: Dict[str, str],
        formula: str,
        output_path: str,
        coefficients: Optional[Dict] = None,
    ) -> bool:
        """Calculate custom index from timestamped band files."""
        from ..core import CogBandProcessor

        temp_processor = CogBandProcessor(self.cache_dir)
        return temp_processor.calculate_custom_index(
            band_paths, formula, output_path, coefficients
        )
