from typing import Optional

from qgis.PyQt.QtCore import QTimer
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsLayerTreeGroup,
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
)
from qgis.gui import QgisInterface

from ..config import Config


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


def add_basemap_global_osm(
    iface: QgisInterface, zoom: bool = True
) -> Optional[QgsRasterLayer]:
    """
    Adds OpenStreetMap as a basemap layer and zooms to Indonesia's extent
    if no other project layers are present. This version enables caching.
    """

    def do_initial_zoom():
        """Performs the initial zoom to Indonesia if no other layers are present."""
        # Zoom to Indonesia extent only if there are no other layers apart from the basemap
        if (
            not any(
                layer.name().endswith(("_Visual", "_NDVI", "_FalseColor", "_Custom"))
                for layer in QgsProject.instance().mapLayers().values()
            )
            and zoom
        ):
            indonesia_bbox = QgsRectangle(95.0, -11.0, 141.0, 6.0)
            dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")
            source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(
                source_crs, dest_crs, QgsProject.instance()
            )
            indonesia_bbox_transformed = transform.transform(indonesia_bbox)
            iface.mapCanvas().setExtent(indonesia_bbox_transformed)
            iface.mapCanvas().refresh()

    # Use a single-shot timer to ensure the zoom happens after the event loop is idle
    QTimer.singleShot(0, do_initial_zoom)

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
        # Added cache=yes and max-age parameters to the URL
        # max-age is in seconds (30 days = 2592000 seconds)
        url = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
        layer_source = f"type=xyz&url={url}&zmax=19&zmin=0&cache=yes&max-age=2592000"
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

    return basemap_layer
