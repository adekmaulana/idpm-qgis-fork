from typing import Optional
from qgis.core import (
    QgsVectorLayer,
    QgsDataSourceUri,
    QgsProject,
    QgsRasterLayer,
    Qgis,
    QgsMessageLog,
    QgsLayerTreeGroup,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
)
from qgis.gui import QgisInterface

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
    db_name_lower = wilker_name.lower().replace(" ", "_")  # Sanitize name

    uri.setConnection(db_host, db_port, db_name_lower, db_user, db_password)
    uri.setDataSource("public", table, geom_col, "", pkey)

    QgsMessageLog.logMessage(
        f"Attempting connection to db: '{db_name_lower}' on host: '{db_host}'",
        "IDPMPlugin",
        Qgis.Info,
    )

    return uri


def get_existing_table_name(year: int) -> str:
    """Returns the table name for the 'Existing' layer, e.g., 'eksisting_2024'."""
    return f"eksisting_{year}"


def get_or_create_plugin_layer_group() -> Optional[QgsLayerTreeGroup]:
    """Finds or creates the main layer group for this plugin."""
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    if not root:
        return None
    group_node = root.findGroup(Config.IDPM_PLUGIN_GROUP_NAME)
    if group_node is None:
        group_node = root.addGroup(Config.IDPM_PLUGIN_GROUP_NAME)
    return group_node


def add_basemap_global_osm(iface: QgisInterface) -> Optional[QgsRasterLayer]:
    """
    Adds OpenStreetMap as a basemap layer and zooms to Indonesia's extent
    if no other project layers are present.
    """
    layer_name = "OpenStreetMap (IDPM Basemap)"
    plugin_group = get_or_create_plugin_layer_group()
    basemap_layer = None

    # Check if basemap already exists in the group
    if plugin_group:
        for child_node in plugin_group.children():
            if hasattr(child_node, "name") and child_node.name() == layer_name:
                basemap_layer = child_node.layer()
                break

    if basemap_layer is None:
        url = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
        layer_source = f"type=xyz&url={url}&zmax=19&zmin=0"
        basemap_layer = QgsRasterLayer(layer_source, layer_name, "wms")

        if basemap_layer.isValid():
            QgsProject.instance().addMapLayer(basemap_layer, False)
            if plugin_group:
                # Add to the bottom of the group
                plugin_group.insertLayer(-1, basemap_layer)
            else:
                QgsProject.instance().addMapLayer(basemap_layer, True)
        else:
            QgsMessageLog.logMessage(
                f"Failed to load basemap '{layer_name}'. Error: {basemap_layer.error().summary()}",
                "IDPMPlugin",
                Qgis.Critical,
            )
            return None

    # Zoom to Indonesia extent only if there are no other layers apart from the basemap
    if len(QgsProject.instance().mapLayers()) <= 1:
        indonesia_bbox = QgsRectangle(95.0, -11.0, 141.0, 6.0)
        dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
        indonesia_bbox_transformed = transform.transform(indonesia_bbox)
        iface.mapCanvas().setExtent(indonesia_bbox_transformed)
        iface.mapCanvas().refresh()

    return basemap_layer


def load_existing_layer(wilker_name: str, year: int) -> Optional[QgsVectorLayer]:
    """
    Loads the 'Existing' vector layer for a specific wilker and year.
    Checks if the layer already exists before loading.
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
