from typing import Optional
from datetime import datetime
from qgis.core import (
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsProject,
    Qgis,
    QgsMessageLog,
    QgsEditorWidgetSetup,
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


def get_existing_qc_table_name(year: int) -> str:
    """
    Returns the table name for the 'Existing QC' layer, e.g., 'existing_2024_qc'.
    """
    return f"existing_{year}_qc"


def load_existing_layer(wilker_name: str, year: int) -> Optional[QgsVectorLayer]:
    """
    Loads the main 'Existing' vector layer for viewing and sets it up
    with default values and a non-destructive save workflow.
    """
    table_name = get_existing_table_name(year)
    layer_name = f"Existing {year} - {wilker_name}"

    plugin_group = get_or_create_plugin_layer_group()
    if plugin_group:
        for child in plugin_group.children():
            if hasattr(child, "name") and child.name() == layer_name:
                QgsMessageLog.logMessage(
                    f"Layer '{layer_name}' is already loaded.", "IDPMPlugin", Qgis.Info
                )
                return child.layer()

    uri = create_db_uri(wilker_name, table_name, "geometry", "ogc_fid")
    if not uri:
        return None

    layer = QgsVectorLayer(uri.uri(False), layer_name, "postgres")

    if layer.isValid():
        QgsProject.instance().addMapLayer(layer, False)
        if plugin_group:
            plugin_group.insertLayer(0, layer)
        else:
            QgsProject.instance().addMapLayer(layer)

        QgsMessageLog.logMessage(
            f"Successfully loaded layer: {layer_name} with default form values and QC workflow enabled.",
            "IDPMPlugin",
            Qgis.Success,
        )
        return layer
    else:
        QgsMessageLog.logMessage(
            f"Layer '{layer_name}' failed to load. Please check your DB credentials, "
            f"your network connection, and if table '{table_name}' exists in database '{wilker_name.lower().replace(' ', '_')}'. "
            f"QGIS error: {layer.error().summary()}",
            "IDPMPlugin",
            Qgis.Critical,
        )
        return None
