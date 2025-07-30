# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an integrated QGIS plugin designed for BPDAS (Balai Pengelolaan Daerah Aliran Sungai) and KLHK (Kementerian Lingkungan Hidup dan Kehutanan) staff to manage, visualize, and analyze geospatial data. The plugin connects to a PostGIS database and an external GeoPortal API for satellite imagery.

### Key Features

- Secure user authentication via API
- Dynamic vector layer loading (Potensi/Existing data) from PostGIS
- Satellite imagery browsing and processing (NDVI, False Color, custom raster calculations)
- Area of Interest (AOI) functionality
- QC (Quality Control) data highlighting
- Asynchronous background processing to keep QGIS responsive

## Dependencies and Installation

### Python Dependencies

- Python 3.9 for MacOS, Python 3.12 for Windows
- `python-dotenv` - Required for environment configuration
- QGIS 3.40 LTR or newer
- `qpip` plugin (for managing Python packages within QGIS)

### Configuration

The plugin requires a `.env` file in the plugin root or `idpm.env` in the user's Documents folder with:

```
API_URL=https://your-api-endpoint.com/api
DB_HOST=your_database_host
DB_PORT=5432
DB_USER=your_database_user
DB_PASSWORD=your_database_password
```

## Architecture

### Core Structure

- `core/main.py` - Main plugin class (IDPMPlugin) handling initialization, login flow, and menu management
- `config.py` - Configuration management using environment variables
- `core/database.py` - PostGIS database connections and layer management
- `ui/` - All user interface components including login, menu, and dialogs
- `assets/` - Static resources (images, fonts)

### Key Components

#### Authentication Flow

1. Plugin checks for existing token in QSettings
2. If no token, fetches form token from API
3. Shows login dialog (`ui/login.py`)
4. On successful login, stores token and user profile
5. Shows main menu (`ui/menu.py`)

#### Data Loading

- Uses `LayerLoaderTask` for asynchronous vector layer loading
- Database connections created via `create_db_uri()` in `core/database.py`
- Supports filtering by wilker (working area) and year
- QC data highlighting via `check_changes()` function

#### UI Architecture

- Inherits from `BaseDialog` for consistent frameless window behavior
- Custom `ActionCard` widgets for menu actions
- Themed message boxes via `ThemedMessageBox`
- Custom input dialogs for user selections

### Database Schema

- Main tables: `existing_{year}`, `potensi_{year}`
- QC tables: `{type}_{year}_qc` (for quality control data)
- Tables are per-wilker (working area) database

## Development Workflow

### Running the Plugin

The plugin is designed to be installed in QGIS via the Plugin Manager. For development:

1. Ensure QGIS 3.40+ is installed
2. Install `qpip` plugin first
3. Configure `.env` file with database and API credentials
4. Load plugin in QGIS

### Code Style

- Uses PyQt5 for UI components
- Type hints are used throughout (`typing` module)
- Asynchronous operations use QTimer and QgsApplication.taskManager()
- Error handling with QgsMessageLog for debugging
- Network requests via QNetworkAccessManager

### Key Patterns

- Singleton pattern for main menu dialog
- Worker tasks for long-running operations (data loading, raster processing)
- Signal/slot connections for UI interactions
- Settings persistence via QSettings

### Important Functions

- `core/main.py:IDPMPlugin.run()` - Main entry point
- `core/database.py:create_db_uri()` - Database connection setup
- `core/database.py:check_changes()` - QC data highlighting
- `ui/menu.py:MenuWidget._start_layer_load_task()` - Async layer loading

## Common Tasks

### Adding New UI Components

- Inherit from `BaseDialog` for consistent styling
- Use Montserrat font family (loaded from assets)
- Apply green forest theme (#5E765F primary color)
- Implement proper cleanup in dialog close handlers

### Database Operations

- Always use `create_db_uri()` for connections
- Handle missing configuration gracefully
- Use parameterized table names (`{type}_{year}` pattern)
- Implement proper error handling for database failures

### API Integration

- Use QNetworkAccessManager for HTTP requests
- Include Bearer token from QSettings in Authorization header
- Handle network errors and JSON parsing failures
- Different endpoints use different base URLs (API_URL vs FRONT_END_URL)

### Worker Tasks

- Inherit from QgsTask for background operations
- Emit signals for progress and completion
- Handle cleanup in task completion/failure handlers
- Use QgsApplication.taskManager() for task management

## Plugin Metadata

- Name: IDPM QGIS Plugin
- Version: 1.0
- Minimum QGIS: 3.0
- Author: Adek Maulana
- Dependencies: qpip plugin
