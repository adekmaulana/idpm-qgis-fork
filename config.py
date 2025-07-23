import os
from qgis.core import Qgis, QgsMessageLog
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This will search for the .env file in the Documents directory first,
# then fallback to the plugin's root directory.
try:
    # Check Documents directory first (preferred location)
    primary_path = os.path.join(os.path.expanduser("~"), "Documents", "idpm.env")
    if os.path.exists(primary_path):
        load_dotenv(dotenv_path=primary_path)
    else:
        # Fallback to plugin root directory
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        fallback_path = os.path.join(plugin_dir, ".env")
        if os.path.exists(fallback_path):
            load_dotenv(dotenv_path=fallback_path)
        else:
            QgsMessageLog.logMessage(
                f"Configuration file not found at {primary_path} or {fallback_path}. Please create an .env file.",
                "IDPMPlugin",
                Qgis.Warning,
            )
except ImportError:
    QgsMessageLog.logMessage(
        "The 'python-dotenv' package is required but not found. Please install it.",
        "IDPMPlugin",
        Qgis.Critical,
    )


class Config:
    """
    Configuration settings for the application.
    Values are loaded from the .env file (Documents/idpm.env preferred, fallback to plugin/.env).
    """

    # --- File/Path Settings ---
    ASSETS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets"))
    DOWNLOAD_DIR = os.path.join(
        os.path.expanduser("~"), "Downloads", "IDPM_Raster_Assets"
    )

    # --- API Settings ---
    API_URL = os.getenv("API_URL", "https://api-idpm.vercel.app/api")
    FRONT_END_URL = os.getenv("FRONT_END_URL", "https://demo.ptnaghayasha.com")

    # --- QGIS Settings ---
    IDPM_PLUGIN_GROUP_NAME = "IDPM Layers"

    # --- Database Configuration (from .env) ---
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
