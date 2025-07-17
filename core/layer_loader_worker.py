from qgis.core import (
    QgsFieldConstraints,
    QgsTask,
    QgsVectorLayer,
    QgsEditorWidgetSetup,
    QgsProject,
    QgsDefaultValue,
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

    layerLoaded = pyqtSignal(QgsVectorLayer)
    errorOccurred = pyqtSignal(str)

    layer: QgsVectorLayer

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
                form_config = self.layer.editFormConfig()

                # --- START: SET ALL FIELDS TO NOT NULL ---
                for field in self.layer.fields():
                    field_name = field.name()
                    idx = self.layer.fields().indexOf(field_name)
                    alias_map = {
                        "ogc_fid": "FID",
                        "bpdas": "BPDAS",
                        "kttj": "Kelas Tutupan Tajuk",
                        "smbdt": "Sumber Data",
                        "thnbuat": "Tahun Buat",
                        "ints": "Institusi",
                        "remark": "Catatan (Remark)",
                        "struktur_v": "Struktur Vegetasi",
                        "lsmgr": "Luas Mangrove",
                        "shape_leng": "Panjang Garis",
                        "shape_area": "Luas Area",
                        "namobj": "Nama Objek",
                        "fcode": "Kode Fitur",
                        "lcode": "Kode Lokasi",
                        "srs_id": "SRS ID",
                        "metadata": "Metadata",
                        "kode_prov": "Kode Provinsi",
                        "fungsikws": "Fungsi Kawasan",
                        "noskkws": "Nomor SK Kawasan",
                        "tglskkws": "Tanggal SK Kawasan",
                        "lskkws": "Luas SK Kawasan",
                        "kawasan": "Kawasan",
                        "konservasi": "Kawasan Konservasi",
                        "kab": "Kabupaten",
                        "prov": "Provinsi",  # End of alias Existing
                        "tahun": "Tahun",
                        "smbrdt": "Sumber Data",
                        "ktrgn": "Keterangan",
                        "keterangan": "Keterangan",
                        "alasan": "Alasan",
                        "klshtn": "Kelas Hutan",
                        "kws": "Kawasan",
                        "luas": "Luas",
                    }

                    if alias_map.get(field_name) is not None:
                        self.layer.setFieldAlias(idx, alias_map[field_name])

                    # Skip certain fields from being set to NOT NULL
                    # as they may not be applicable or required.
                    if field_name in [
                        "ogc_fid",
                        "remark",
                        "alasan",
                        "klshtn",
                        "namobj",
                        "fcode",
                        "lcode",
                        "srs_id",
                        "metadata",
                        "kode_prov",
                        "fungsikws",
                        "noskkws",
                        "tglskkws",
                        "lskkws",
                        "kawasan",
                        "konservasi",
                        "kab",
                        "prov",
                        "objectid",
                        "ktrgn",
                        "keterangan",
                        "klshtn",
                        "kws",
                        "tahun",
                    ]:
                        continue

                    self.layer.setFieldConstraint(
                        idx, QgsFieldConstraints.ConstraintNotNull
                    )
                # --- END: SET ALL FIELDS TO NOT NULL ---

                # --- Configure ogc_fid field ---
                ogc_fid_index = self.layer.fields().indexOf("ogc_fid")
                if ogc_fid_index != -1:
                    expression = (
                        'IF ("ogc_fid" is NULL, maximum("ogc_fid") + 1, "ogc_fid")'
                    )
                    default_value_definition = QgsDefaultValue()
                    default_value_definition.setExpression(expression=expression)
                    default_value_definition.setApplyOnUpdate(True)
                    self.layer.setDefaultValueDefinition(
                        ogc_fid_index, default_value_definition
                    )
                    widget_setup = QgsEditorWidgetSetup(
                        "TextEdit", {"isEditable": False, "showClearButton": False}
                    )
                    self.layer.setEditorWidgetSetup(ogc_fid_index, widget_setup)
                    form_config.setReadOnly(ogc_fid_index, True)

                # --- START: BPDAS AUTO-FILL IMPLEMENTATION ---
                bpdas_index = self.layer.fields().indexOf("bpdas")
                if bpdas_index != -1:
                    # 1. Set the default value to the wilker name. Note the single quotes.
                    default_value_definition = QgsDefaultValue(f"'{self.wilker_name}'")

                    # 2. Apply the default value definition to the field.
                    self.layer.setDefaultValueDefinition(
                        bpdas_index, default_value_definition
                    )

                    # 3. Make the field non-editable in the form.
                    widget_setup = QgsEditorWidgetSetup(
                        "TextEdit", {"isEditable": False, "showClearButton": False}
                    )
                    self.layer.setEditorWidgetSetup(bpdas_index, widget_setup)
                    form_config.setReadOnly(bpdas_index, True)
                # --- END: BPDAS AUTO-FILL IMPLEMENTATION ---

                # --- START: Remark Field Configuration ---
                remark_index = self.layer.fields().indexOf("remark")
                if remark_index != -1:
                    # 1. Set the default value to the wilker name. Note the single quotes.
                    default_value_definition = QgsDefaultValue(f"'TIDAK ADA CATATAN'")

                    # 2. Apply the default value definition to the field.
                    self.layer.setDefaultValueDefinition(
                        remark_index, default_value_definition
                    )
                    widget_setup = QgsEditorWidgetSetup(
                        "TextEdit", {"isEditable": True, "showClearButton": True}
                    )
                    self.layer.setEditorWidgetSetup(remark_index, widget_setup)
                # --- END: Remark Field Configuration ---

                # --- START: INTS FIELD CONFIGURATION ---
                ints_index = self.layer.fields().indexOf("ints")
                if ints_index != -1:
                    # 1. Set the default value to the wilker name. Note the single quotes.
                    default_value_definition = QgsDefaultValue(f"'KLHK'")

                    # 2. Apply the default value definition to the field.
                    self.layer.setDefaultValueDefinition(
                        ints_index, default_value_definition
                    )
                    widget_setup = QgsEditorWidgetSetup(
                        "TextEdit", {"isEditable": True, "showClearButton": True}
                    )
                    self.layer.setEditorWidgetSetup(ints_index, widget_setup)
                # --- END: INTS FIELD CONFIGURATION ---

                if self.layer_type == "existing":
                    self.setup_existing_layer_form()
                elif self.layer_type == "potensi":
                    self.setup_potensi_layer_form()

                self.layer.setEditFormConfig(form_config)
                return True

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
        kttj_index = self.layer.fields().indexOf("kttj")
        if kttj_index != -1:
            kttj_options = {
                "Mangrove Lebat": "Mangrove Lebat",
                "Mangrove Sedang": "Mangrove Sedang",
                "Mangrove Jarang": "Mangrove Jarang",
            }
            widget_setup = QgsEditorWidgetSetup("ValueMap", {"map": kttj_options})
            self.layer.setEditorWidgetSetup(kttj_index, widget_setup)

        struktur_v_index = self.layer.fields().indexOf("struktur_v")
        if struktur_v_index != -1:
            struktur_v_options = {
                "Dominasi Pohon": "DOMINASI POHON",
                "Dominasi Non Pohon": "DOMINASI NON POHON",
            }
            widget_setup = QgsEditorWidgetSetup("ValueMap", {"map": struktur_v_options})
            self.layer.setEditorWidgetSetup(struktur_v_index, widget_setup)

        konservasi_index = self.layer.fields().indexOf("konservasi")
        if konservasi_index != -1:
            konservasi_options = {
                "Bukan Kawasan Konservasi": "Bukan Kawasan Konservasi",
                "Kawasan Konservasi": "Kawasan Konservasi",
            }
            widget_setup = QgsEditorWidgetSetup("ValueMap", {"map": konservasi_options})
            self.layer.setEditorWidgetSetup(konservasi_index, widget_setup)

        # # Define a common UTM zone for Indonesia for accurate measurements
        # # EPSG:32748 is WGS 84 / UTM zone 48S, suitable for much of Indonesia.
        # # This can be adjusted if a different zone is more appropriate for all BPDAS areas.
        # utm_zone_crs = "EPSG:32748"
        # source_crs = self.layer.crs().authid()

        # # Configure shape_leng
        # shape_leng_index = self.layer.fields().indexOf("shape_leng")
        # if shape_leng_index != -1:
        #     expression = (
        #         f"perimeter(transform($geometry, '{source_crs}', '{utm_zone_crs}'))"
        #     )
        #     default_value = QgsDefaultValue(expression)
        #     self.layer.setDefaultValueDefinition(shape_leng_index, default_value)

        # # Configure shape_area
        # shape_area_index = self.layer.fields().indexOf("shape_area")
        # if shape_area_index != -1:
        #     expression = (
        #         f"area(transform($geometry, '{source_crs}', '{utm_zone_crs}')) / 10000"
        #     )
        #     default_value = QgsDefaultValue(expression)
        #     self.layer.setDefaultValueDefinition(shape_area_index, default_value)

        # # Configure lsmgr
        # lsmgr_index = self.layer.fields().indexOf("lsmgr")
        # if lsmgr_index != -1:
        #     expression = (
        #         f"area(transform($geometry, '{source_crs}', '{utm_zone_crs}')) / 10000"
        #     )
        #     default_value = QgsDefaultValue(expression)
        #     self.layer.setDefaultValueDefinition(lsmgr_index, default_value)

    def setup_potensi_layer_form(self):
        objectid_index = self.layer.fields().indexOf("objectid")
        if objectid_index != -1:
            # Hide the objectid field in the form
            widget_setup = QgsEditorWidgetSetup("Hidden", {})
            self.layer.setEditorWidgetSetup(objectid_index, widget_setup)

        utm_zone_crs = "EPSG:32748"
        source_crs = self.layer.crs().authid()

        # Configure luas
        luas_index = self.layer.fields().indexOf("luas")
        if luas_index != -1:
            expression = (
                f"area(transform($geometry, '{source_crs}', '{utm_zone_crs}')) / 10000"
            )
            default_value = QgsDefaultValue(expression)
            self.layer.setDefaultValueDefinition(luas_index, default_value)

        # Configure ktrgn
        ktrgn_index = self.layer.fields().indexOf("ktrgn")
        if ktrgn_index != -1:
            ktrgn_options = {
                "Mangrove Terabrasi": "MANGROVE TERABRASI",
                "Tanah Timbul": "TANAH TIMBUL",
                "Lahan Terbuka": "LAHAN TERBUKA",
                "Tambak": "TAMBAK",
                "Area Terabrasi": "AREA TERABRASI",
            }
            widget_setup = QgsEditorWidgetSetup("ValueMap", {"map": ktrgn_options})
            self.layer.setEditorWidgetSetup(ktrgn_index, widget_setup)

    def finished(self, result):
        """
        Called on the main thread when the task is finished.
        """
        if result:
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
