import json
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsFieldConstraints,
    QgsTask,
    QgsVectorLayer,
    QgsEditorWidgetSetup,
    QgsProject,
    QgsDefaultValue,
)
from PyQt5.QtCore import QUrl, QSettings, QEventLoop, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from ..config import Config
from .database import (
    create_db_uri,
    get_existing_table_name,
    get_potensi_table_name,
    get_qc_table_name,
    check_changes,
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

    def _fetch_province(self) -> tuple[str, int]:
        """
        Synchronously fetches the province name and ID from the API.
        This runs in the worker thread.

        Returns:
            A tuple containing the province name (str) and province ID (int).
        """
        settings = QSettings()
        token = settings.value("IDPMPlugin/token", None)
        if not token:
            QgsMessageLog.logMessage(
                "No auth token found, cannot fetch province.",
                "IDPMPlugin",
                Qgis.Warning,
            )
            return "", 0

        url = f"{Config.API_URL}/bpdas/{self.wilker_name}/province"
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"Authorization", f"Bearer {token}".encode())

        manager = QNetworkAccessManager()
        loop = QEventLoop()
        manager.finished.connect(loop.quit)

        reply = manager.get(req)
        loop.exec_()  # Blocks until the request is finished

        province_name = ""
        province_id = 0
        if reply.error() == QNetworkReply.NoError:
            response_data = reply.readAll().data()
            try:
                response_json = json.loads(response_data.decode("utf-8"))
                if (
                    response_json.get("status")
                    or response_json.get("status_code") == 200
                ):
                    data = response_json.get("data", {})
                    province_name = data.get("provinsi_name", "")
                    province_id = data.get("provinsi_id", 0)
                else:
                    msg = response_json.get("msg", "Unknown API error")
                    QgsMessageLog.logMessage(
                        f"API error fetching province: {msg}",
                        "IDPMPlugin",
                        Qgis.Warning,
                    )
            except json.JSONDecodeError as e:
                QgsMessageLog.logMessage(
                    f"Failed to parse province response: {e}",
                    "IDPMPlugin",
                    Qgis.Warning,
                )
        else:
            QgsMessageLog.logMessage(
                f"Network error fetching province: {reply.errorString()}",
                "IDPMPlugin",
                Qgis.Warning,
            )

        reply.deleteLater()
        manager.deleteLater()
        return province_name, province_id

    def run(self):
        """
        Executes the layer loading in a background thread.
        """
        try:
            # --- START: FETCH PROVINCE FROM API ---
            province_name, province_id = self._fetch_province()
            # --- END: FETCH PROVINCE FROM API ---

            if self.layer_type == "existing":
                table_name = get_existing_table_name(self.year)
                table_qc_name = get_qc_table_name("existing", self.year)
                layer_name = f"Existing {self.year} - {self.wilker_name}"
            elif self.layer_type == "potensi":
                table_name = get_potensi_table_name(self.year)
                table_qc_name = get_qc_table_name("potensi", self.year)
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

                    if field_name in ["shape_area", "lsmgr"]:
                        expression = f'"{field_name}" >= 0.0625'
                        self.layer.setConstraintExpression(
                            idx,
                            expression,
                            description="Luas minimum adalah 0.0625 ha",
                        )

                        # Set Read-Only for shape_area and lsmgr
                        form_config.setReadOnly(idx, True)
                    elif field_name in ["shape_leng", "luas"]:
                        expression = f'"{field_name}" >= 0'
                        self.layer.setConstraintExpression(
                            idx,
                            expression,
                            description="Panjang/Luas tidak boleh negatif",
                        )
                        form_config.setReadOnly(idx, True)
                # --- END: SET ALL FIELDS TO NOT NULL ---

                # --- Configure ogc_fid field ---
                ogc_fid_index = self.layer.fields().indexOf("ogc_fid")
                if ogc_fid_index != -1:
                    widget_setup = QgsEditorWidgetSetup(
                        "TextEdit", {"isEditable": False, "showClearButton": False}
                    )
                    self.layer.setEditorWidgetSetup(ogc_fid_index, widget_setup)
                    form_config.setReadOnly(ogc_fid_index, True)

                # --- START: BPDAS AUTO-FILL IMPLEMENTATION ---
                bpdas_index = self.layer.fields().indexOf("bpdas")
                if bpdas_index != -1:
                    default_value_definition = QgsDefaultValue(f"'{self.wilker_name}'")
                    self.layer.setDefaultValueDefinition(
                        bpdas_index, default_value_definition
                    )
                    widget_setup = QgsEditorWidgetSetup(
                        "TextEdit", {"isEditable": False, "showClearButton": False}
                    )
                    self.layer.setEditorWidgetSetup(bpdas_index, widget_setup)
                    form_config.setReadOnly(bpdas_index, True)
                # --- END: BPDAS AUTO-FILL IMPLEMENTATION ---

                # --- START: PROVINCE AUTO-FILL IMPLEMENTATION ---
                prov_index = self.layer.fields().indexOf("prov")
                if prov_index != -1 and province_name:
                    default_value_definition = QgsDefaultValue(
                        f"'{province_name.upper()}'"
                    )
                    self.layer.setDefaultValueDefinition(
                        prov_index, default_value_definition
                    )
                    widget_setup = QgsEditorWidgetSetup(
                        "TextEdit", {"isEditable": False, "showClearButton": False}
                    )
                    self.layer.setEditorWidgetSetup(prov_index, widget_setup)
                    form_config.setReadOnly(prov_index, True)
                # --- END: PROVINCE AUTO-FILL IMPLEMENTATION ---

                # --- START: KODE_PROV AUTO-FILL IMPLEMENTATION ---
                if self.layer_type == "existing":
                    kode_prov_index = self.layer.fields().indexOf("kode_prov")
                    if kode_prov_index != -1 and province_id:
                        # QgsDefaultValue expects a string expression.
                        # For numeric fields, just the number as a string is sufficient.
                        default_value_definition = QgsDefaultValue(f"{province_id}")
                        self.layer.setDefaultValueDefinition(
                            kode_prov_index, default_value_definition
                        )
                        widget_setup = QgsEditorWidgetSetup(
                            "TextEdit", {"isEditable": False, "showClearButton": False}
                        )
                        self.layer.setEditorWidgetSetup(kode_prov_index, widget_setup)
                        form_config.setReadOnly(kode_prov_index, True)
                # --- END: KODE_PROV AUTO-FILL IMPLEMENTATION ---

                # --- START: Remark Field Configuration ---
                remark_index = self.layer.fields().indexOf("remark")
                if remark_index != -1:
                    default_value_definition = QgsDefaultValue(f"'TIDAK ADA CATATAN'")
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
                    default_value_definition = QgsDefaultValue(f"'KLHK'")
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
                check_changes(self.wilker_name, self.layer, self.layer_type, self.year)
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

        srs_id_index = self.layer.fields().indexOf("srs_id")
        if srs_id_index != -1:
            default_value = QgsDefaultValue("'4326'")
            self.layer.setDefaultValueDefinition(srs_id_index, default_value)

        # Define a common UTM zone for Indonesia for accurate measurements
        # EPSG:32748 is WGS 84 / UTM zone 48S, suitable for much of Indonesia.
        # This can be adjusted if a different zone is more appropriate for all BPDAS areas.
        utm_zone_crs = "EPSG:32748"
        source_crs = self.layer.crs().authid()

        # Configure shape_leng
        shape_leng_index = self.layer.fields().indexOf("shape_leng")
        if shape_leng_index != -1:
            expression = f"perimeter(transform($geometry, '{source_crs}', '{utm_zone_crs}')) / 1000"
            default_value = QgsDefaultValue(expression)
            self.layer.setDefaultValueDefinition(shape_leng_index, default_value)

        # Configure shape_area
        shape_area_index = self.layer.fields().indexOf("shape_area")
        if shape_area_index != -1:
            expression = (
                f"area(transform($geometry, '{source_crs}', '{utm_zone_crs}')) / 10000"
            )
            default_value = QgsDefaultValue(expression)
            self.layer.setDefaultValueDefinition(shape_area_index, default_value)

        # Configure lsmgr
        lsmgr_index = self.layer.fields().indexOf("lsmgr")
        if lsmgr_index != -1:
            expression = (
                f"area(transform($geometry, '{source_crs}', '{utm_zone_crs}')) / 10000"
            )
            default_value = QgsDefaultValue(expression)
            self.layer.setDefaultValueDefinition(lsmgr_index, default_value)

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

        # Configure keterangan we hide the field in the form
        keterangan_index = self.layer.fields().indexOf("keterangan")
        if keterangan_index != -1:
            widget_setup = QgsEditorWidgetSetup("Hidden", {})
            self.layer.setEditorWidgetSetup(keterangan_index, widget_setup)

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
