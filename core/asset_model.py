import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from qgis.core import Qgis, QgsMessageLog

from ..config import Config


@dataclass
class RasterAsset:
    """
    A data class to represent a single raster asset from the GeoPortal API.
    It centralizes property access and path management.
    """

    feature: Dict[str, Any]  # The GeoJSON feature containing the asset data
    stac_id: str = field(init=False)
    capture_date: Optional[datetime] = field(init=False)
    cloud_cover: float = field(init=False)
    thumbnail_url: Optional[str] = field(init=False)
    visual_url: Optional[str] = field(init=False)
    nir_url: Optional[str] = field(init=False)
    red_url: Optional[str] = field(init=False)
    green_url: Optional[str] = field(init=False)
    properties: Dict[str, Any] = field(init=False)
    geometry: Optional[Dict[str, Any]] = field(init=False)

    def __post_init__(self):
        """
        Initializes calculated fields after the main dataclass initialization.
        """
        self.properties = self.feature.get("properties", {})
        if not self.properties:
            QgsMessageLog.logMessage(
                "RasterAsset initialized with empty properties.",
                "IDPMPlugin",
                Qgis.Warning,
            )

        # Parse the geometry from the feature
        self.geometry = self.feature.get("geometry")

        self.stac_id = self.properties.get("stac_id", "UNKNOWN")
        self.cloud_cover = float(self.properties.get("cloud", 0.0))
        self.thumbnail_url = self.properties.get("thumb")
        self.visual_url = self.properties.get("visual")
        self.nir_url = self.properties.get("asset_nir")
        self.red_url = self.properties.get("asset_red")
        self.green_url = self.properties.get("asset_green")

        # Parse the capture date safely
        date_str = self.properties.get("tanggal", "")
        self.capture_date = self._parse_date(date_str)

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """
        Safely parses various ISO 8601 format date strings.
        It tries multiple formats to handle variations from the API.
        """
        if not date_str:
            return None

        # List of possible formats to try, from most to least specific.
        # Handles formats with and without timezone information or fractional seconds.
        formats_to_try = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # With 'Z' and microseconds
            "%Y-%m-%dT%H:%M:%S%z",  # With timezone offset
            "%Y-%m-%dT%H:%M:%S.%f",  # With microseconds, no timezone
            "%Y-%m-%dT%H:%M:%S",  # No microseconds, no timezone
        ]

        # First, try Python's built-in, more general ISO parser
        try:
            # Handle 'Z' for UTC timezone info by replacing it
            if date_str.endswith("Z"):
                date_str = date_str.replace("Z", "+00:00")
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            # If fromisoformat fails, try our list of specific formats
            for fmt in formats_to_try:
                try:
                    return datetime.strptime(date_str, fmt)
                except (ValueError, TypeError):
                    continue

        # If all parsing attempts fail, log it and return None
        QgsMessageLog.logMessage(
            f"Could not parse date string: '{date_str}' with any known format.",
            "IDPMPlugin",
            Qgis.Warning,
        )
        return None

    def get_local_path(self, asset_type: str) -> str:
        """
        Constructs the expected local file path for a given asset type.

        Args:
            asset_type: The type of asset ('visual', 'nir', 'red', 'green', 'ndvi', or 'false_color').

        Returns:
            The full local file path as a string.
        """
        folder_path = os.path.join(Config.DOWNLOAD_DIR, self.stac_id)
        file_name = ""

        if asset_type == "visual" and self.visual_url:
            file_name = os.path.basename(self.visual_url.split("?")[0])
        elif asset_type == "nir" and self.nir_url:
            file_name = os.path.basename(self.nir_url.split("?")[0])
        elif asset_type == "red" and self.red_url:
            file_name = os.path.basename(self.red_url.split("?")[0])
        elif asset_type == "green" and self.green_url:
            file_name = os.path.basename(self.green_url.split("?")[0])
        elif asset_type == "ndvi":
            file_name = f"{self.stac_id}_NDVI.tif"
        elif asset_type == "false_color":
            file_name = f"{self.stac_id}_FalseColor.tif"

        if not file_name:
            return ""

        return os.path.join(folder_path, file_name)
