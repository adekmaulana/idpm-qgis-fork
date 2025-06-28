import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from ..config import Config


@dataclass
class RasterAsset:
    """
    A data class to represent a single raster asset from the GeoPortal API.
    It centralizes property access and path management.
    """

    properties: Dict[str, Any]
    stac_id: str = field(init=False)
    capture_date: Optional[datetime] = field(init=False)
    cloud_cover: float = field(init=False)
    thumbnail_url: Optional[str] = field(init=False)
    visual_url: Optional[str] = field(init=False)
    nir_url: Optional[str] = field(init=False)
    red_url: Optional[str] = field(init=False)
    green_url: Optional[str] = field(init=False)

    def __post_init__(self):
        """
        Initializes calculated fields after the main dataclass initialization.
        """
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
        """Safely parses an ISO format date string."""
        if not date_str:
            return None
        try:
            # Handle 'Z' for UTC timezone info by replacing it
            if date_str.endswith("Z"):
                date_str = date_str.replace("Z", "+00:00")
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None

    def get_local_path(self, asset_type: str) -> str:
        """
        Constructs the expected local file path for a given asset type.

        Args:
            asset_type: The type of asset ('visual', 'nir', 'red', 'green', or 'ndvi').

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

        if not file_name:
            return ""

        return os.path.join(folder_path, file_name)
