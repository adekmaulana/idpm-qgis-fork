from typing import Optional
from qgis.core import (
    QgsDataSourceUri,
    Qgis,
    QgsMessageLog,
)
from ..config import Config


def create_db_uri(
    wilker_name: str, table: str, geom_col: str, pkey: str = ""
) -> Optional[QgsDataSourceUri]:
    """
    Creates a QgsDataSourceUri for the PostGIS connection using
    settings from the Config class.
    """
    if not wilker_name:
        QgsMessageLog.logMessage(
            "Cannot create DB URI: wilker_name is empty.", "IDPMPlugin", Qgis.Critical
        )
        return None

    db_host = Config.DB_HOST
    db_port = Config.DB_PORT
    db_user = Config.DB_USER
    db_password = Config.DB_PASSWORD

    if not all([db_host, db_port, db_user, db_password]):
        QgsMessageLog.logMessage(
            "Database configuration is missing. "
            "Please ensure DB_HOST, DB_PORT, DB_USER, and DB_PASSWORD are set correctly in the .env file.",
            "IDPMPlugin",
            Qgis.Critical,
        )
        return None

    uri = QgsDataSourceUri()
    db_name_lower = wilker_name.lower().replace(" ", "")

    uri.setConnection(db_host, db_port, db_name_lower, db_user, db_password)
    uri.setDataSource("public", table, geom_col, "", pkey)

    return uri


def get_existing_table_name(year: int) -> str:
    """
    Returns the table name for the main 'Existing' layer, e.g., 'existing_2024'.
    """
    return f"existing_{year}"


def get_potensi_table_name(year: int) -> str:
    """
    Returns the table name for the main 'Potensi' layer, e.g., 'potensi_2024'.
    """
    return f"potensi_{year}"


def get_existing_qc_table_name(year: int) -> str:
    """
    Returns the table name for the 'Existing QC' layer, e.g., 'existing_2024_qc'.
    """
    return f"existing_{year}_qc"
