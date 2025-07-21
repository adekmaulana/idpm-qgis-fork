from typing import Optional
from qgis.core import (
    QgsDataSourceUri,
    Qgis,
    QgsMessageLog,
    QgsVectorLayer,
    QgsField,
    QgsProject,
)
from PyQt5.QtCore import QVariant
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

    uri.setParam("connect_timeout", "90")

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


def get_qc_table_name(type_data: str, year: int) -> str:
    """
    Returns the table name for the 'Existing QC' layer, e.g., 'existing_2024_qc'.
    """
    return f"{type_data}_{year}_qc"


def check_changes(
    wilker_name: str,
    layer: QgsVectorLayer,
    type_data: str,
    year: int,
    add_qc_layer_to_map: bool = False,
):
    """
    Checks the '_qc' table for changes and highlights them on the provided Type Data layer.

    Args:
        wilker_name: The wilker name
        layer: The main layer to highlight features on
        type_data: The type of data (existing/potensi)
        year: The year
        add_qc_layer_to_map: Whether to add the QC layer to the map for visualization
    """
    if not layer.isValid() or layer is None:
        return

    qc_table_name = get_qc_table_name(type_data, year)

    uri_logger = create_db_uri(wilker_name, qc_table_name, "geometry", "ogc_fid")
    if not uri_logger:
        return

    layer_logger = QgsVectorLayer(
        uri_logger.uri(False), f"QC Log - {wilker_name} {year}", "postgres"
    )

    if not layer_logger.isValid():
        QgsMessageLog.logMessage(
            f"Failed to load QC table '{qc_table_name}' for wilker '{wilker_name}'!",
            "IDPMPlugin",
            Qgis.Warning,
        )
        return

    # Debug information about the loaded layer
    QgsMessageLog.logMessage(
        f"QC Layer loaded successfully: '{layer_logger.name()}' "
        f"Features: {layer_logger.featureCount()}, "
        f"CRS: {layer_logger.crs().authid()}, "
        f"Extent: {layer_logger.extent().toString()}",
        "IDPMPlugin",
        Qgis.Info,
    )

    # Optionally add the QC layer to the map for visualization
    if add_qc_layer_to_map and layer_logger.featureCount() > 0:
        # Check if layer is already in project
        existing_layers = [
            layer.name() for layer in QgsProject.instance().mapLayers().values()
        ]
        if layer_logger.name() not in existing_layers:
            QgsProject.instance().addMapLayer(layer_logger)
            QgsMessageLog.logMessage(
                f"Added QC layer '{layer_logger.name()}' to map",
                "IDPMPlugin",
                Qgis.Info,
            )
        else:
            QgsMessageLog.logMessage(
                f"QC layer '{layer_logger.name()}' already exists in map",
                "IDPMPlugin",
                Qgis.Info,
            )

    if layer_logger.featureCount() > 0:
        # Create a dictionary to store QC status for each feature
        qc_data = {}
        for qc_feature in layer_logger.getFeatures():
            ogc_fid = qc_feature["ogc_fid"]
            qc_status_raw = (
                qc_feature.attribute("qcstatus")
                if qc_feature.fields().indexOf("qcstatus") != -1
                else None
            )

            # Parse QC status from JSON format - just use the raw data
            qc_status_display = "Unknown"
            if qc_status_raw:
                # Just convert to string representation
                qc_status_display = str(qc_status_raw)

            qc_data[ogc_fid] = qc_status_display

        # Highlight the features with QC changes
        feature_ids = list(qc_data.keys())
        expression = f'"ogc_fid" IN ({",".join(map(str, feature_ids))})'

        # Debug information about the selection
        QgsMessageLog.logMessage(
            f"Attempting to select features with expression: {expression}",
            "IDPMPlugin",
            Qgis.Info,
        )

        # Check if the main layer has the ogc_fid field
        main_layer_fields = [field.name() for field in layer.fields()]
        QgsMessageLog.logMessage(
            f"Main layer '{layer.name()}' fields: {', '.join(main_layer_fields)}",
            "IDPMPlugin",
            Qgis.Info,
        )

        layer.selectByExpression(expression, QgsVectorLayer.SetSelection)

        # Check how many features were actually selected
        selected_count = layer.selectedFeatureCount()
        QgsMessageLog.logMessage(
            f"Selected {selected_count} features out of {len(feature_ids)} QC records",
            "IDPMPlugin",
            Qgis.Info,
        )

        # Add QC status information to the main layer as a virtual field
        qc_field_name = "qc_status"

        # Remove existing QC field if it exists
        field_index = layer.fields().indexOf(qc_field_name)
        if field_index != -1:
            layer.dataProvider().deleteAttributes([field_index])
            layer.updateFields()

        # Create a CASE expression to map ogc_fid to QC status (failed criteria)
        case_conditions = []

        # Use the already parsed qc_data which contains the failed criteria
        for fid, status in qc_data.items():
            # Escape single quotes in the status text for SQL
            escaped_status = status.replace("'", "''")
            case_conditions.append(f"WHEN \"ogc_fid\" = {fid} THEN '{escaped_status}'")

        if case_conditions:
            # Add QC status field showing failed criteria directly
            case_expression = f"CASE {' '.join(case_conditions)} ELSE 'No QC' END"
            layer.addExpressionField(
                case_expression, QgsField(qc_field_name, QVariant.String)
            )

            QgsMessageLog.logMessage(
                f"Added QC status field '{qc_field_name}' to layer '{layer.name()}'",
                "IDPMPlugin",
                Qgis.Info,
            )

        # Get unique QC statuses safely
        unique_statuses = list(set(qc_data.values()))
        QgsMessageLog.logMessage(
            f"Highlighted {len(feature_ids)} QC changes on layer '{layer.name()}'.",
            "IDPMPlugin",
            Qgis.Info,
        )
    else:
        QgsMessageLog.logMessage(
            f"No changes found in '{qc_table_name}' for wilker '{wilker_name}'.",
            "IDPMPlugin",
            Qgis.Info,
        )
