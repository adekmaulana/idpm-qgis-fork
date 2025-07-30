# cog_aoi_loader.py - Complete COG AOI-Based Loading Implementation using Rasterio
import os
import tempfile
from PyQt5.QtCore import QEventLoop, QTimer
import numpy as np
from typing import Optional, Dict, Tuple, List, Union
from qgis.core import (
    QgsApplication,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRasterLayer,
    QgsMessageLog,
    Qgis,
)

from .raster_calculator_worker import RasterCalculatorTask

try:
    import rasterio
    from rasterio.windows import from_bounds, Window
    from rasterio.warp import transform_bounds, reproject, calculate_default_transform
    from rasterio.enums import Resampling
    from rasterio.crs import CRS
    from rasterio.profiles import default_gtiff_profile

    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


class CogAoiLoader:
    """
    Handles loading COG rasters based on Area of Interest (AOI) selections using rasterio.
    Optimizes bandwidth and processing time by only downloading/processing the required portion.
    """

    def __init__(self):
        if not RASTERIO_AVAILABLE:
            raise ImportError(
                "rasterio is required for COG processing. Install with: pip install rasterio"
            )

        # Configure rasterio environment for optimal COG access
        rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff",
            GDAL_HTTP_CONNECTTIMEOUT="30",
            GDAL_HTTP_TIMEOUT="60",
            CPL_VSIL_CURL_CACHE_SIZE="200000000",  # 200MB cache
        )

    def load_cog_with_aoi(
        self,
        cog_url: str,
        aoi_rect: QgsRectangle,
        aoi_crs: QgsCoordinateReferenceSystem,
        target_resolution: Optional[float] = None,
        cache_dir: Optional[str] = None,
    ) -> Optional[str]:
        """
        Load a COG raster cropped to the specified AOI using rasterio.

        Args:
            cog_url: URL to the COG file
            aoi_rect: Area of Interest rectangle
            aoi_crs: CRS of the AOI rectangle
            target_resolution: Target pixel resolution in target CRS units
            cache_dir: Directory to cache the cropped result

        Returns:
            Path to the cropped raster file, or None if failed
        """
        try:
            with rasterio.open(cog_url) as src:
                # Convert QGIS CRS to rasterio CRS
                aoi_crs_rasterio = CRS.from_epsg(int(aoi_crs.authid().split(":")[1]))
                src_crs = src.crs

                # Transform AOI bounds to source CRS if needed
                if aoi_crs_rasterio != src_crs:
                    aoi_bounds_src = transform_bounds(
                        aoi_crs_rasterio,
                        src_crs,
                        aoi_rect.xMinimum(),
                        aoi_rect.yMinimum(),
                        aoi_rect.xMaximum(),
                        aoi_rect.yMaximum(),
                    )
                else:
                    aoi_bounds_src = (
                        aoi_rect.xMinimum(),
                        aoi_rect.yMinimum(),
                        aoi_rect.xMaximum(),
                        aoi_rect.yMaximum(),
                    )

                # Create window from bounds
                window = from_bounds(*aoi_bounds_src, src.transform)

                # Ensure window is within raster bounds
                window = window.intersection(Window(0, 0, src.width, src.height))

                if window.width <= 0 or window.height <= 0:
                    QgsMessageLog.logMessage(
                        "AOI doesn't intersect with raster", "COGLoader", Qgis.Warning
                    )
                    return None

                # Determine output path
                if cache_dir:
                    os.makedirs(cache_dir, exist_ok=True)
                    output_path = os.path.join(
                        cache_dir, f"cropped_{os.path.basename(cog_url)}"
                    )
                else:
                    output_path = tempfile.NamedTemporaryFile(
                        suffix=".tif", delete=False
                    ).name

                # Read data for the window
                data = src.read(window=window)

                # Calculate transform for the windowed data
                window_transform = src.window_transform(window)

                # Create output profile
                profile = src.profile.copy()
                profile.update(
                    {
                        "height": window.height,
                        "width": window.width,
                        "transform": window_transform,
                        "compress": "lzw",
                        "tiled": True,
                    }
                )

                # Handle resampling if target resolution is specified
                if target_resolution and target_resolution != abs(src.transform.a):
                    data, profile = self._resample_data(
                        data, profile, target_resolution, aoi_crs_rasterio
                    )

                # Write cropped raster
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(data)
                    # Copy metadata
                    dst.update_tags(**src.tags())

                return output_path

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error loading COG with AOI: {str(e)}", "COGLoader", Qgis.Critical
            )
            return None

    def _resample_data(
        self, data: np.ndarray, profile: dict, target_resolution: float, target_crs: CRS
    ) -> Tuple[np.ndarray, dict]:
        """Resample data to target resolution."""
        try:
            # Calculate new dimensions
            current_resolution = abs(profile["transform"].a)
            scale_factor = current_resolution / target_resolution

            new_width = int(profile["width"] * scale_factor)
            new_height = int(profile["height"] * scale_factor)

            # Calculate new transform
            transform, width, height = calculate_default_transform(
                profile["crs"],
                profile["crs"],
                profile["width"],
                profile["height"],
                *rasterio.transform.array_bounds(
                    profile["height"], profile["width"], profile["transform"]
                ),
                resolution=target_resolution,
            )

            # Create output array
            resampled_data = np.empty((data.shape[0], height, width), dtype=data.dtype)

            # Reproject each band
            reproject(
                data,
                resampled_data,
                src_transform=profile["transform"],
                src_crs=profile["crs"],
                dst_transform=transform,
                dst_crs=profile["crs"],
                resampling=Resampling.bilinear,
            )

            # Update profile
            profile.update({"height": height, "width": width, "transform": transform})

            return resampled_data, profile

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error resampling data: {str(e)}", "COGLoader", Qgis.Warning
            )

    def crop_local_file_to_aoi(
        self,
        local_file_path: str,
        aoi_rect: QgsRectangle,
        aoi_crs: QgsCoordinateReferenceSystem,
        output_path: str,
    ) -> bool:
        """
        Crop an already downloaded local raster file to AOI.
        This avoids re-downloading if the band is already available locally.

        Args:
            local_file_path: Path to the local raster file
            aoi_rect: Area of Interest rectangle
            aoi_crs: CRS of the AOI rectangle
            output_path: Where to save the cropped result

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(local_file_path):
                return False

            with rasterio.open(local_file_path) as src:
                # Convert QGIS CRS to rasterio CRS
                aoi_crs_rasterio = CRS.from_epsg(int(aoi_crs.authid().split(":")[1]))
                src_crs = src.crs

                # Transform AOI bounds to source CRS if needed
                if aoi_crs_rasterio != src_crs:
                    aoi_bounds_src = transform_bounds(
                        aoi_crs_rasterio,
                        src_crs,
                        aoi_rect.xMinimum(),
                        aoi_rect.yMinimum(),
                        aoi_rect.xMaximum(),
                        aoi_rect.yMaximum(),
                    )
                else:
                    aoi_bounds_src = (
                        aoi_rect.xMinimum(),
                        aoi_rect.yMinimum(),
                        aoi_rect.xMaximum(),
                        aoi_rect.yMaximum(),
                    )

                # Create window from bounds
                window = from_bounds(*aoi_bounds_src, src.transform)

                # Ensure window is within raster bounds
                window = window.intersection(Window(0, 0, src.width, src.height))

                if window.width <= 0 or window.height <= 0:
                    QgsMessageLog.logMessage(
                        "AOI doesn't intersect with local raster",
                        "COGLoader",
                        Qgis.Warning,
                    )
                    return False

                # Read data for the window
                data = src.read(window=window)

                # Calculate transform for the windowed data
                window_transform = src.window_transform(window)

                # Create output profile
                profile = src.profile.copy()
                profile.update(
                    {
                        "height": window.height,
                        "width": window.width,
                        "transform": window_transform,
                        "compress": "lzw",
                        "tiled": True,
                    }
                )

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Write cropped raster
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(data)
                    # Copy metadata
                    dst.update_tags(**src.tags())

                QgsMessageLog.logMessage(
                    f"Successfully cropped local file to AOI: {os.path.basename(output_path)}",
                    "COGLoader",
                    Qgis.Info,
                )
                return True

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error cropping local file to AOI: {str(e)}",
                "COGLoader",
                Qgis.Critical,
            )
            return False


class CogBandProcessor:
    """
    Processes multiple COG bands for NDVI, False Color, and custom calculations
    using rasterio and AOI-based loading.
    """

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.cog_loader = CogAoiLoader()
        os.makedirs(cache_dir, exist_ok=True)

    def process_bands_with_aoi(
        self,
        band_urls: Dict[str, str],
        aoi_rect: QgsRectangle,
        aoi_crs: QgsCoordinateReferenceSystem,
        stac_id: str,
        local_band_paths: Optional[
            Dict[str, str]
        ] = None,  # IGNORED - kept for compatibility
        target_resolution: Optional[float] = None,
    ) -> Dict[str, str]:
        """
        Download and process multiple bands for a given AOI using rasterio.
        ALWAYS downloads from URLs - ignores local files completely.

        Args:
            band_urls: Dictionary mapping band names to URLs
            aoi_rect: Area of Interest rectangle
            aoi_crs: CRS of the AOI
            stac_id: Identifier for the asset
            local_band_paths: IGNORED - kept for backward compatibility only
            target_resolution: Target resolution for resampling

        Returns:
            Dictionary mapping band names to local file paths
        """
        downloaded_bands = {}

        QgsMessageLog.logMessage(
            f"Starting AOI band processing for STAC ID: {stac_id}",
            "COGProcessor",
            Qgis.Info,
        )

        for band_name, band_url in band_urls.items():
            try:
                # Create cache filename
                cache_filename = f"{stac_id}_{band_name}_aoi.tif"
                cache_path = os.path.join(self.cache_dir, cache_filename)

                QgsMessageLog.logMessage(
                    f"Downloading {band_name} from URL for AOI: {band_url}",
                    "COGProcessor",
                    Qgis.Info,
                )

                # ALWAYS download from URL - no cache checking, no local file usage
                result_path = self.cog_loader.load_cog_with_aoi(
                    band_url, aoi_rect, aoi_crs, target_resolution, self.cache_dir
                )

                if result_path:
                    # Rename to consistent filename if needed
                    if result_path != cache_path:
                        # Remove existing cache if it exists
                        if os.path.exists(cache_path):
                            os.remove(cache_path)
                            QgsMessageLog.logMessage(
                                f"Removed existing cache for {band_name}",
                                "COGProcessor",
                                Qgis.Info,
                            )

                        # Rename new download to cache path
                        os.rename(result_path, cache_path)

                    downloaded_bands[band_name] = cache_path

                    # Log success with file size
                    file_size_mb = os.path.getsize(cache_path) / (1024 * 1024)
                    QgsMessageLog.logMessage(
                        f"Successfully downloaded {band_name} for AOI ({file_size_mb:.2f} MB)",
                        "COGProcessor",
                        Qgis.Info,
                    )
                else:
                    QgsMessageLog.logMessage(
                        f"Failed to download {band_name} for AOI from URL",
                        "COGProcessor",
                        Qgis.Warning,
                    )

            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error downloading band {band_name} from URL: {str(e)}",
                    "COGProcessor",
                    Qgis.Critical,
                )

        QgsMessageLog.logMessage(
            f"AOI band processing completed. Downloaded {len(downloaded_bands)}/{len(band_urls)} bands",
            "COGProcessor",
            Qgis.Info,
        )

        return downloaded_bands

    def _is_valid_raster(self, file_path: str) -> bool:
        """Check if a raster file is valid and readable using rasterio."""
        try:
            with rasterio.open(file_path) as src:
                return src.width > 0 and src.height > 0 and src.count > 0
        except:
            return False

    def calculate_ndvi_from_aoi_bands(
        self, nir_path: str, red_path: str, output_path: str
    ) -> bool:
        """Calculate NDVI from AOI-cropped NIR and Red bands using rasterio."""
        try:
            with rasterio.open(nir_path) as nir_src, rasterio.open(red_path) as red_src:
                # Read data
                nir_data = nir_src.read(1).astype(np.float32)
                red_data = red_src.read(1).astype(np.float32)

                # Get nodata values
                nir_nodata = nir_src.nodata
                red_nodata = red_src.nodata

                # Create masks for nodata values
                nir_mask = (
                    (nir_data == nir_nodata)
                    if nir_nodata is not None
                    else np.zeros_like(nir_data, dtype=bool)
                )
                red_mask = (
                    (red_data == red_nodata)
                    if red_nodata is not None
                    else np.zeros_like(red_data, dtype=bool)
                )

                # Combined mask for any nodata pixels
                nodata_mask = nir_mask | red_mask | (nir_data + red_data == 0)

                # Calculate NDVI: (NIR - Red) / (NIR + Red)
                # Add small epsilon to avoid division by zero
                epsilon = 1e-10
                denominator = nir_data + red_data + epsilon
                ndvi_data = (nir_data - red_data) / denominator

                # Set nodata pixels to -9999
                ndvi_data[nodata_mask] = -9999

                # Clip NDVI values to valid range [-1, 1]
                ndvi_data = np.clip(ndvi_data, -1, 1)

                # Create output profile
                profile = nir_src.profile.copy()
                profile.update(
                    {
                        "dtype": rasterio.float32,
                        "nodata": -9999,
                        "compress": "lzw",
                        "tiled": True,
                    }
                )

                # Write NDVI data
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(ndvi_data, 1)
                    dst.set_band_description(1, "NDVI")
                    dst.update_tags(
                        1, STATISTICS_MINIMUM=str(np.min(ndvi_data[~nodata_mask]))
                    )
                    dst.update_tags(
                        1, STATISTICS_MAXIMUM=str(np.max(ndvi_data[~nodata_mask]))
                    )

            return True

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error calculating NDVI: {str(e)}", "COGProcessor", Qgis.Critical
            )
            return False

    def calculate_false_color_composite(
        self, nir_path: str, red_path: str, green_path: str, output_path: str
    ) -> bool:
        """Create False Color composite (NIR-Red-Green) from individual bands using rasterio."""
        try:
            # Open all bands
            with rasterio.open(nir_path) as nir_src, rasterio.open(
                red_path
            ) as red_src, rasterio.open(green_path) as green_src:

                # Read arrays
                nir_data = nir_src.read(1)
                red_data = red_src.read(1)
                green_data = green_src.read(1)

                # Normalize and stretch to 0-255 range
                def normalize_band(data):
                    # Convert to float and handle nodata
                    data = data.astype(np.float32)

                    # Get percentiles for contrast stretching (2% and 98%)
                    valid_data = data[data > 0]
                    if len(valid_data) == 0:
                        return np.zeros_like(data, dtype=np.uint8)

                    p2, p98 = np.percentile(valid_data, [2, 98])

                    # Stretch to 0-255
                    if p98 > p2:
                        stretched = np.clip((data - p2) / (p98 - p2) * 255, 0, 255)
                    else:
                        stretched = np.clip(data, 0, 255)

                    return stretched.astype(np.uint8)

                # Normalize bands (False Color: NIR=Red, Red=Green, Green=Blue)
                band1 = normalize_band(nir_data)  # Red channel = NIR
                band2 = normalize_band(red_data)  # Green channel = Red
                band3 = normalize_band(green_data)  # Blue channel = Green

                # Create output profile for RGB
                profile = nir_src.profile.copy()
                profile.update(
                    {
                        "dtype": rasterio.uint8,
                        "count": 3,
                        "nodata": None,
                        "compress": "lzw",
                        "tiled": True,
                        "photometric": "RGB",
                    }
                )

                # Write False Color composite
                with rasterio.open(output_path, "w", **profile) as dst:
                    dst.write(band1, 1)  # Red = NIR
                    dst.write(band2, 2)  # Green = Red
                    dst.write(band3, 3)  # Blue = Green

                    # Set band descriptions
                    dst.set_band_description(1, "NIR")
                    dst.set_band_description(2, "Red")
                    dst.set_band_description(3, "Green")

            return True

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error creating false color composite: {str(e)}",
                "COGProcessor",
                Qgis.Critical,
            )
            return False

    def calculate_custom_index(
        self,
        band_paths: Dict[str, str],
        formula: str,
        output_path: str,
        coefficients: Optional[Dict] = None,
        timeout_seconds: int = 300,
    ) -> bool:
        """
        Calculate custom vegetation index using QGIS RasterCalculator instead of eval.

        Args:
            band_paths: Dictionary mapping band names to file paths
            formula: Mathematical formula (e.g., "(nir - red) / (nir + red)")
            output_path: Output file path
            coefficients: Optional coefficients for the formula
            timeout_seconds: Maximum time to wait for calculation completion

        Returns:
            True if calculation successful
        """
        try:
            # Validate that all band files exist and are readable
            for band_name, path in band_paths.items():
                if not os.path.exists(path):
                    QgsMessageLog.logMessage(
                        f"Band file does not exist: {band_name} -> {path}",
                        "COGProcessor",
                        Qgis.Critical,
                    )
                    return False

                # Test if the file is a valid raster
                if not self._is_valid_raster(path):
                    QgsMessageLog.logMessage(
                        f"Invalid raster file: {band_name} -> {path}",
                        "COGProcessor",
                        Qgis.Critical,
                    )
                    return False

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Generate a unique STAC ID for this calculation
            import hashlib

            stac_id = hashlib.md5(
                (formula + str(sorted(band_paths.items()))).encode()
            ).hexdigest()[:8]

            # Create the raster calculator task
            task = RasterCalculatorTask(
                formula=formula,
                band_paths=band_paths,
                coefficients=coefficients or {},
                output_path=output_path,
                stac_id=stac_id,
            )

            # Set up result tracking
            calculation_result = {"success": False, "error_message": ""}

            def on_calculation_finished(path: str, name: str, task_stac_id: str):
                """Handle successful calculation completion."""
                if task_stac_id == stac_id:
                    calculation_result["success"] = True
                    QgsMessageLog.logMessage(
                        f"Custom index calculation completed: {name}",
                        "COGProcessor",
                        Qgis.Info,
                    )

            def on_error_occurred(error_msg: str, task_stac_id: str):
                """Handle calculation error."""
                if task_stac_id == stac_id:
                    calculation_result["success"] = False
                    calculation_result["error_message"] = error_msg
                    QgsMessageLog.logMessage(
                        f"Custom index calculation failed: {error_msg}",
                        "COGProcessor",
                        Qgis.Critical,
                    )

            # Connect signals
            task.calculationFinished.connect(on_calculation_finished)
            task.errorOccurred.connect(on_error_occurred)

            # Add task to QGIS task manager
            task_manager = QgsApplication.taskManager()
            task_id = task_manager.addTask(task)

            if task_id == 0:
                QgsMessageLog.logMessage(
                    "Failed to add raster calculation task to task manager",
                    "COGProcessor",
                    Qgis.Critical,
                )
                return False

            # Wait for task completion with timeout
            success = self._wait_for_task_completion(
                task_manager, task_id, timeout_seconds, calculation_result
            )

            if not success:
                QgsMessageLog.logMessage(
                    f"Custom index calculation timed out or failed: {calculation_result.get('error_message', 'Unknown error')}",
                    "COGProcessor",
                    Qgis.Critical,
                )
                return False

            # Verify output file was created and is valid
            if not os.path.exists(output_path) or not self._is_valid_raster(
                output_path
            ):
                QgsMessageLog.logMessage(
                    "Output raster file was not created or is invalid",
                    "COGProcessor",
                    Qgis.Critical,
                )
                return False

            QgsMessageLog.logMessage(
                f"Successfully calculated custom index using formula: {formula}",
                "COGProcessor",
                Qgis.Info,
            )
            return True

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error calculating custom index: {str(e)}",
                "COGProcessor",
                Qgis.Critical,
            )
            return False

    def _wait_for_task_completion(
        self,
        task_manager,
        task_id: int,
        timeout_seconds: int,
        result_dict: dict,
    ) -> bool:
        """
        Wait for a QGIS task to complete with timeout.

        Args:
            task_manager: QGIS task manager instance
            task_id: ID of the task to wait for
            timeout_seconds: Maximum time to wait
            result_dict: Dictionary to store results (modified by signal handlers)

        Returns:
            True if task completed successfully, False otherwise
        """
        # Create event loop for waiting
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)

        # Track completion
        completed = {"finished": False, "success": False}

        def check_task_status():
            """Periodically check task status."""
            task = task_manager.task(task_id)
            if task is None or task.status() in [task.Complete, task.Terminated]:
                completed["finished"] = True
                completed["success"] = result_dict.get("success", False)
                loop.quit()

        def on_timeout():
            """Handle timeout."""
            completed["finished"] = True
            completed["success"] = False
            loop.quit()

            # Try to cancel the task
            task = task_manager.task(task_id)
            if task and task.canCancel():
                task.cancel()

        # Set up periodic checking (every 100ms)
        check_timer = QTimer()
        check_timer.timeout.connect(check_task_status)
        check_timer.start(100)

        # Set up timeout
        timer.timeout.connect(on_timeout)
        timer.start(timeout_seconds * 1000)

        # Start event loop
        loop.exec_()

        # Clean up timers
        check_timer.stop()
        timer.stop()

        return completed["finished"] and completed["success"]

    def calculate_predefined_index(
        self, band_paths: Dict[str, str], index_name: str, output_path: str
    ) -> bool:
        """
        Calculate predefined vegetation indices using QGIS RasterCalculator.

        Args:
            band_paths: Dictionary with band paths (should contain required bands)
            index_name: Name of the index (NDVI, NDWI, SAVI, EVI, GNDVI)
            output_path: Output file path

        Returns:
            True if calculation successful
        """
        # Define predefined indices and their requirements
        indices = {
            "NDVI": {
                "formula": "(nir - red) / (nir + red)",
                "required_bands": ["nir", "red"],
            },
            "NDWI": {
                "formula": "(green - nir) / (green + nir)",
                "required_bands": ["green", "nir"],
            },
            "SAVI": {
                "formula": "((nir - red) / (nir + red + 0.5)) * 1.5",
                "required_bands": ["nir", "red"],
            },
            "EVI": {
                "formula": "2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))",
                "required_bands": ["nir", "red", "blue"],
            },
            "GNDVI": {
                "formula": "(nir - green) / (nir + green)",
                "required_bands": ["nir", "green"],
            },
        }

        if index_name not in indices:
            QgsMessageLog.logMessage(
                f"Unknown index: {index_name}. Available indices: {list(indices.keys())}",
                "COGProcessor",
                Qgis.Warning,
            )
            return False

        index_info = indices[index_name]

        # Check if all required bands are available
        missing_bands = [
            band for band in index_info["required_bands"] if band not in band_paths
        ]
        if missing_bands:
            QgsMessageLog.logMessage(
                f"Missing required bands for {index_name}: {missing_bands}",
                "COGProcessor",
                Qgis.Warning,
            )
            return False

        # Filter band_paths to only include required bands for this index
        filtered_band_paths = {
            band: path
            for band, path in band_paths.items()
            if band in index_info["required_bands"]
        }

        # Calculate the index using QGIS RasterCalculator
        return self.calculate_custom_index(
            filtered_band_paths, index_info["formula"], output_path
        )


# Integration helper for existing QGIS plugin
class QgisPluginIntegration:
    """
    Helper class to integrate COG AOI loading with existing QGIS plugin architecture using rasterio.
    """

    @staticmethod
    def modify_asset_download_workflow(asset, aoi_rect: Optional[QgsRectangle] = None):
        """
        Modified workflow for downloading assets with AOI support using rasterio.
        """
        if not aoi_rect:
            return None

        # Get AOI CRS (usually from map canvas)
        canvas_crs = QgsProject.instance().crs()

        # Initialize processors
        cache_dir = os.path.join(tempfile.gettempdir(), "idpm_cog_cache", asset.stac_id)
        band_processor = CogBandProcessor(cache_dir)

        # Prepare band URLs
        band_urls = {}
        if hasattr(asset, "nir_url") and asset.nir_url:
            band_urls["nir"] = asset.nir_url
        if hasattr(asset, "red_url") and asset.red_url:
            band_urls["red"] = asset.red_url
        if hasattr(asset, "green_url") and asset.green_url:
            band_urls["green"] = asset.green_url
        if hasattr(asset, "blue_url") and asset.blue_url:
            band_urls["blue"] = asset.blue_url

        # Process bands with AOI
        result_paths = band_processor.process_bands_with_aoi(
            band_urls, aoi_rect, canvas_crs, asset.stac_id
        )

        return result_paths

    @staticmethod
    def create_aoi_aware_layer_loader(
        asset, aoi_rect: QgsRectangle, layer_name: str
    ) -> Optional[QgsRasterLayer]:
        """
        Create a QGIS raster layer from COG using AOI optimization with rasterio.
        """
        try:
            canvas_crs = QgsProject.instance().crs()
            cog_loader = CogAoiLoader()

            # Load visual/TCI band with AOI
            if hasattr(asset, "visual_url") and asset.visual_url:
                cropped_path = cog_loader.load_cog_with_aoi(
                    asset.visual_url, aoi_rect, canvas_crs
                )

                if cropped_path:
                    layer = QgsRasterLayer(cropped_path, layer_name)
                    if layer.isValid():
                        return layer

            return None

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error creating AOI-aware layer: {str(e)}",
                "COGIntegration",
                Qgis.Critical,
            )
            return None


# Installation check and requirements
def check_rasterio_installation():
    """Check if rasterio is properly installed and configured."""
    if RASTERIO_AVAILABLE:
        try:
            QgsMessageLog.logMessage(
                f"Rasterio version {rasterio.__version__} is available",
                "COGLoader",
                Qgis.Info,
            )
            return True
        except:
            return False
    else:
        QgsMessageLog.logMessage(
            "Rasterio is not installed. Please install with: pip install rasterio",
            "COGLoader",
            Qgis.Critical,
        )
        return False
