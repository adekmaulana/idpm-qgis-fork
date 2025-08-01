from .main import IDPMPlugin
from .ndvi_worker import NdviTask
from .asset_model import RasterAsset
from .aoi_processing_tasks import (
    AoiVisualProcessingTask,
    AoiNdviProcessingTask,
    AoiFalseColorProcessingTask,
    AoiCustomCalculationTask,
)
from .cog_aio_loader import (
    CogAoiLoader,
    CogBandProcessor,
    QgisPluginIntegration,
    check_rasterio_installation,
)
from .false_color_worker import FalseColorTask
from .raster_calculator_worker import RasterCalculatorTask
from .zonal_stats_worker import ZonalStatsTask
from .mangrove_classifier import MangroveClassificationTask  # NEW: Import mangrove task
from .util import (
    get_or_create_plugin_layer_group,
    add_basemap_global_osm,
)


__all__ = [
    "IDPMPlugin",
    "NdviTask",
    "FalseColorTask",
    "RasterAsset",
    "RasterCalculatorTask",
    "ZonalStatsTask",
    "MangroveClassificationTask",  # NEW: Export mangrove task
    "CogAoiLoader",  # Add placeholder to prevent import errors
    "CogBandProcessor",  # Add placeholder to prevent import errors
    "QgisPluginIntegration",  # Add placeholder to prevent import errors
    "check_rasterio_installation",  # Add placeholder to prevent import errors
    "AoiVisualProcessingTask",
    "AoiNdviProcessingTask",
    "AoiFalseColorProcessingTask",
    "AoiCustomCalculationTask",
]
