# idpm-qgis/core/__init__.py

from .main import IDPMPlugin
from .ndvi_worker import NdviTask
from .asset_model import RasterAsset
from .false_color_worker import FalseColorTask
from .raster_calculator_worker import RasterCalculatorTask
from .zonal_stats_worker import ZonalStatsTask  # NEW: Import the new task
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
    "ZonalStatsTask",  # NEW: Export the new task
]
