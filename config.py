import os
from qgis.core import Qgis, QgsMessageLog
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This will search for the .env file in the plugin's root directory
# and load its values into the environment for os.getenv() to use.
try:
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(plugin_dir, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    else:
        # Check .env from Documents directory as a fallback
        fallback_path = os.path.join(os.path.expanduser("~"), "Documents", "idpm.env")
        if os.path.exists(fallback_path):
            load_dotenv(dotenv_path=fallback_path)
        else:

            QgsMessageLog.logMessage(
                f"Configuration file not found at {dotenv_path}. Please create a .env file.",
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
    Values are loaded from the .env file in the plugin's root directory.
    """

    # --- File/Path Settings ---
    ASSETS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets"))
    DOWNLOAD_DIR = os.path.join(
        os.path.expanduser("~"), "Downloads", "IDPM_Raster_Assets"
    )

    # --- API Settings ---
    API_URL = os.getenv("API_URL", "https://demo.ptnaghayasha.com/api")

    # --- QGIS Settings ---
    IDPM_PLUGIN_GROUP_NAME = "IDPM Layers"

    # --- Database Configuration (from .env) ---
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
