from typing import Optional, Dict, Any

from qgis.core import (
    QgsTask,
    QgsVectorLayer,
    Qgis,
    QgsMessageLog,
    QgsEditorWidgetSetup,
    QgsProject,
)
from PyQt5.QtCore import pyqtSignal

from .database import (
    create_db_uri,
    get_existing_table_name,
    get_potensi_table_name,
)
from ..core.util import get_or_create_plugin_layer_group


class LayerLoaderTask(QgsTask):
    """
    A QGIS task to load a vector layer from PostGIS in the background.
    """

    # Signal to emit when the layer is successfully loaded
    # It passes the QgsVectorLayer object
    layerLoaded = pyqtSignal(QgsVectorLayer)

    # Signal to emit when an error occurs
    errorOccurred = pyqtSignal(str)

    def __init__(
        self,
        description: str,
        layer_type: str,
        wilker_name: str,
        year: int,
    ):
        super().__init__(description, QgsTask.CanCancel)
        self.layer_type = layer_type
        self.wilker_name = wilker_name
        self.year = year
        self.exception = None
        self.layer = None

    def run(self):
        """
        Executes the layer loading in a background thread.
        """
        try:
            if self.layer_type == "existing":
                table_name = get_existing_table_name(self.year)
                layer_name = f"Existing {self.year} - {self.wilker_name}"
            elif self.layer_type == "potensi":
                table_name = get_potensi_table_name(self.year)
                layer_name = f"Potensi {self.year} - {self.wilker_name}"
            else:
                self.exception = Exception(f"Unknown layer type: {self.layer_type}")
                return False

            if self.isCanceled():
                return False

            uri = create_db_uri(self.wilker_name, table_name, "geometry", "ogc_fid")
            if not uri:
                self.exception = Exception("Failed to create database URI.")
                return False

            self.layer = QgsVectorLayer(uri.uri(False), layer_name, "postgres")

            if self.isCanceled():
                return False

            if self.layer.isValid():
                # Apply custom form widgets if the layer is 'existing'
                if self.layer_type == "existing":
                    self.setup_existing_layer_form()
                return True
            else:
                self.exception = Exception(
                    f"Layer '{layer_name}' failed to load. "
                    f"QGIS error: {self.layer.error().summary()}"
                )
                return False

        except Exception as e:
            self.exception = e
            return False

    def setup_existing_layer_form(self):
        """Sets up the custom attribute form for the 'existing' layer."""
        field_index = self.layer.fields().indexOf("kttj")
        if field_index != -1:
            kttj_options = {
                "Mangrove Lebat": "Mangrove Lebat",
                "Mangrove Lebat": "Mangrove Lebat",
                "Mangrove Lebat": "Mangrove Lebat",
            }
            widget_setup = QgsEditorWidgetSetup("ValueMap", {"map": kttj_options})
            self.layer.setEditorWidgetSetup(field_index, widget_setup)

    def finished(self, result):
        """
        Called on the main thread when the task is finished.
        """
        if result:
            # Add the layer to the project in the main thread
            plugin_group = get_or_create_plugin_layer_group()
            QgsProject.instance().addMapLayer(self.layer, False)
            if plugin_group:
                plugin_group.insertLayer(0, self.layer)
            self.layerLoaded.emit(self.layer)
        else:
            if self.exception:
                self.errorOccurred.emit(str(self.exception))
            elif self.isCanceled():
                self.errorOccurred.emit("Layer loading was canceled.")
            else:
                self.errorOccurred.emit("Layer loading failed for an unknown reason.")
