from typing import Optional
from qgis.core import (
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsProject,
    Qgis,
    QgsMessageLog,
)

from ..config import Config
from ..core.util import get_or_create_plugin_layer_group


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

    # Load credentials from the central Config object
    db_host = Config.DB_HOST
    db_port = Config.DB_PORT
    db_user = Config.DB_USER
    db_password = Config.DB_PASSWORD

    # Improved check to ensure all required DB variables were loaded from .env
    if not all([db_host, db_port, db_user, db_password]):
        QgsMessageLog.logMessage(
            "Database configuration is missing. "
            "Please ensure DB_HOST, DB_PORT, DB_USER, and DB_PASSWORD are set correctly in the .env file.",
            "IDPMPlugin",
            Qgis.Critical,
        )
        return None

    uri = QgsDataSourceUri()
    db_name_lower = wilker_name.lower().replace(" ", "")  # Sanitize name

    uri.setConnection(db_host, db_port, db_name_lower, db_user, db_password)
    uri.setDataSource("public", table, geom_col, "", pkey)

    # QgsMessageLog.logMessage(
    #     f"Attempting connection to db: '{db_name_lower}' on host: '{db_host}'",
    #     "IDPMPlugin",
    #     Qgis.Info,
    # )

    return uri


def get_existing_table_name(year: int) -> str:
    """
    Returns the table name for the main 'Existing' layer, e.g., 'eksisting_2024'.
    """
    return f"eksisting_{year}"


def get_existing_qc_table_name(year: int) -> str:
    """
    Returns the table name for the 'Existing QC' layer, e.g., 'eksisting_2024_qc'.
    """
    return f"eksisting_{year}_qc"


def load_existing_layer(wilker_name: str, year: int) -> Optional[QgsVectorLayer]:
    """
    Loads the main 'Existing' vector layer for viewing.
    """
    table_name = get_existing_table_name(year)
    layer_name = f"Existing {year} - {wilker_name}"

    # Check if layer is already loaded
    plugin_group = get_or_create_plugin_layer_group()
    if plugin_group:
        for child in plugin_group.children():
            if hasattr(child, "name") and child.name() == layer_name:
                QgsMessageLog.logMessage(
                    f"Layer '{layer_name}' is already loaded.", "IDPMPlugin", Qgis.Info
                )
                return child.layer()

    # Define DB connection details
    uri = create_db_uri(wilker_name, table_name, "geometry", "ogc_fid")
    if not uri:
        return None

    layer = QgsVectorLayer(uri.uri(False), layer_name, "postgres")

    if layer.isValid():
        QgsProject.instance().addMapLayer(layer, False)
        if plugin_group:
            plugin_group.insertLayer(0, layer)
        else:
            QgsProject.instance().addMapLayer(layer)  # Fallback

        QgsMessageLog.logMessage(
            f"Successfully loaded layer: {layer_name}", "IDPMPlugin", Qgis.Success
        )
        return layer
    else:
        QgsMessageLog.logMessage(
            f"Layer '{layer_name}' failed to load. Please check your DB credentials in the .env file, "
            f"your network connection, and if table '{table_name}' exists in database '{wilker_name.lower().replace(' ', '_')}'. "
            f"QGIS error: {layer.error().summary()}",
            "IDPMPlugin",
            Qgis.Critical,
        )
        return None
