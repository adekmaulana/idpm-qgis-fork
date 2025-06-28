import os


class Config:
    """Configuration settings for the application."""

    ASSETS_PATH = os.path.abspath(os.path.dirname(__file__) + "/assets")
    DOWNLOAD_DIR = os.path.join(
        os.path.expanduser("~"), "Downloads", "IDPM_Raster_Assets"
    )
    API_URL = "https://demo.ptnaghayasha.com/api"

    DB_HOST = "localhost"
    DB_PORT = 5432
    DB_NAME = "idpm_db"
    DB_USER = "idpm_user"
    DB_PASSWORD = "idpm_password"
