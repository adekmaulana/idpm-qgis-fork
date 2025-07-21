# Changelog

All notable changes to the IDPM QGIS Plugin project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-07-21

### Added

- **QC (Quality Control) System**: Added comprehensive QC status tracking for existing and potensi layers
  - QC status is now displayed in feature information as raw JSON data
  - Features with QC issues are automatically highlighted on the map
  - QC data is loaded from dedicated QC tables (`existing_YYYY_qc`, `potensi_YYYY_qc`)
- **SWIR Asset Support**: Added Short-Wave Infrared (SWIR) asset support in the raster list functionality
- **Calculator Presets**: Added more preset calculations for the raster calculator
- **Automatic Field Calculations**:
  - Shape area, shape length, and LSMGR are now calculated automatically for existing layers
  - Area (luas) is calculated automatically for potensi layers
- **Province Auto-Population**: Province and province code are now automatically set for existing and potensi layers
- **Minimum Area Validation**: Polygons smaller than 0.0625 hectares are no longer accepted for existing and potensi layers
- **Field Aliases**: Added user-friendly aliases for existing and potensi layer fields
- **Cloud Cover Display**: Added cloud cover percentage text for better readability in raster listings

### Changed

- **API URL**: Updated the API endpoint URL configuration
- **Field Visibility**:
  - Hidden "keterangan" field in potensi, now uses "ktrgn" instead
  - Hidden "objectid" field from potensi forms as it's not needed for user input
  - Set shape_area, shape_length, luas, and lsmgr fields to read-only mode
- **Default Values**: Improved default value determination for various fields in existing and potensi layers
- **Database Connection**: Added connection timeout configuration for improved reliability

### Fixed

- **Menu Behavior**: Menu no longer hides when opening existing or potensi layer dialogs
- **Process Cancellation**: Improved handling of cancelled processes when closing the raster list menu
- **Default SRS**: Fixed default spatial reference system ID for existing layers
- **Performance**: Moved database connections to background tasks to prevent QGIS freezing/unresponsiveness

### Performance

- **Background Processing**: Database connections are now handled in background threads, significantly improving UI responsiveness and preventing application freezing

### Documentation

- Updated README with latest project information and usage instructions

---

## Previous Releases

### [Initial Release] - 2025-07-13

- **feat(existing)**: Initial implementation to handle new schemes for existing forest data management

---

## Commit Range

This changelog covers commits from `daa4781` (2025-07-13) to `61e5f26` (2025-07-21).

## Contributors

- **Adek Maulana** - Primary developer and maintainer

---

_Generated on July 21, 2025_
