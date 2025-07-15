# IDPM QGIS Plugin

An integrated QGIS plugin designed to streamline the management, visualization, and analysis of geospatial data for BPDAS (Balai Pengelolaan Daerah Aliran Sungai) and KLHK (Kementerian Lingkungan Hidup dan Kehutanan) staff. This tool connects directly to a PostGIS database and an external GeoPortal API to provide a seamless data workflow.

### Core Features

This plugin is built with a focus on user experience and performance, featuring a modern interface and asynchronous processing to keep QGIS responsive.

- **Secure User Authentication**: A robust login system connects to the API to authenticate users and manage sessions securely.
- **Dynamic Data Loading**:
  - Load vector layers for **Potensi** and **Existing** areas directly from the PostGIS database.
  - Data is filtered based on the user's selected working area (`wilker`) and year, ensuring only relevant data is loaded.
- **Advanced Raster Imagery Tools**:
  - **Browse Satellite Imagery**: Fetch and view a catalog of available Sentinel satellite images from the GeoPortal API.
  - **On-the-Fly Processing**: Perform complex raster operations without needing to pre-process data:
    - **NDVI Analysis**: Automatically calculate and style NDVI (Normalized Difference Vegetation Index).
    - **False Color Composites**: Generate False Color images to enhance vegetation analysis.
    - **Custom Raster Calculator**: A powerful tool to create your own raster indices and models. It includes presets for common indices like GNDVI, NDWI, SAVI, and EVI, and allows for custom coefficients.
- **Area of Interest (AOI) Functionality**:
  - **Filter by AOI**: Draw a rectangle on the map to filter the satellite imagery search to a specific area.
- **Automated Form Configuration**:
  - Attribute forms for vector layers are automatically configured with "Not Null" constraints, default values, and user-friendly dropdown menus to improve data quality and consistency.
- **Responsive and Modern UI**:
  - A custom user interface built from the ground up to be intuitive and visually appealing.
  - All long-running tasks (data loading, raster processing) are executed in the background, so the QGIS interface never freezes.

### Prerequisites

Before installing, please ensure your system meets the following requirements:

1.  **QGIS Version**: QGIS 3.40 LTR or a more recent version is required.
2.  **QGIS Plugin Dependency**: The **`qpip`** plugin must be installed. This plugin is used to manage Python package dependencies.
3.  **Python Dependency**:
    - `python-dotenv`

### Configuration

The plugin requires a configuration file to connect to the database and API. You can create this file in one of two locations:

1.  A file named `.env` in the root directory of the plugin.
2.  A file named `idpm.env` in your computer's `Documents` folder.

The configuration file must contain the following variables:

```
# --- API Settings ---
API_URL=[https://your-api-endpoint.com/api](https://your-api-endpoint.com/api)

# --- Database Configuration ---
DB_HOST=your_database_host
DB_PORT=5432
DB_USER=your_database_user
DB_PASSWORD=your_database_password
```

### How to Use

1.  **Login**: Start the plugin from the QGIS toolbar. You will be prompted to log in with your credentials.
2.  **Main Menu**: After logging in, the main menu provides access to all features.
3.  **Load Vector Data**:
    - Click "Open Data Potensi" or "Open Data Existing".
    - If you are assigned to multiple working areas (`wilker`), you will be asked to choose one.
    - Select the desired year for the data. The layer will be loaded into QGIS.
4.  **Analyze Raster Data**:
    - **(Optional) Select AOI for Search**: To narrow your search, click this option and draw a rectangle on the map.
    - **Citra Satelit**: This opens a dialog listing available satellite images. If you set an AOI, this list will be filtered.
    - From the list, you can:
      - Download and view the `Visual` (RGB) image.
      - Process and display `NDVI` or `False Color` composites.
      - Use the `Calculator` for custom raster analysis.

---

---

# Plugin QGIS IDPM

Plugin QGIS terintegrasi yang dirancang untuk menyederhanakan pengelolaan, visualisasi, dan analisis data geospasial bagi staf BPDAS (Balai Pengelolaan Daerah Aliran Sungai) dan KLHK (Kementerian Lingkungan Hidup dan Kehutanan). Alat ini terhubung langsung ke basis data PostGIS dan API GeoPortal eksternal untuk menyediakan alur kerja data yang lancar.

### Fitur Utama

Plugin ini dibangun dengan fokus pada pengalaman pengguna dan kinerja, menampilkan antarmuka modern dan pemrosesan asinkron untuk menjaga QGIS tetap responsif.

- **Autentikasi Pengguna yang Aman**: Sistem login yang kuat terhubung ke API untuk mengautentikasi pengguna dan mengelola sesi dengan aman.
- **Pemuatan Data Dinamis**:
  - Memuat layer vektor untuk area **Potensi** dan **Existing** langsung dari basis data PostGIS.
  - Data difilter berdasarkan wilayah kerja (`wilker`) dan tahun yang dipilih pengguna, memastikan hanya data yang relevan yang dimuat.
- **Alat Citra Raster Canggih**:
  - **Jelajahi Citra Satelit**: Ambil dan lihat katalog citra satelit Sentinel yang tersedia dari API GeoPortal.
  - **Pemrosesan On-the-Fly**: Lakukan operasi raster yang kompleks tanpa perlu melakukan pra-pemrosesan data:
    - **Analisis NDVI**: Secara otomatis menghitung dan menata gaya NDVI (Normalized Difference Vegetation Index).
    - **Komposit Warna Semu (False Color)**: Hasilkan gambar False Color untuk meningkatkan analisis vegetasi.
    - **Kalkulator Raster Kustom**: Alat canggih untuk membuat indeks dan model raster Anda sendiri. Termasuk preset untuk indeks umum seperti GNDVI, NDWI, SAVI, dan EVI, serta memungkinkan koefisien kustom.
- **Fungsionalitas Area of Interest (AOI)**:
  - **Filter berdasarkan AOI**: Gambar persegi panjang di peta untuk memfilter pencarian citra satelit ke area tertentu.
- **Konfigurasi Formulir Otomatis**:
  - Formulir atribut untuk layer vektor dikonfigurasi secara otomatis dengan batasan "Not Null", nilai default, dan menu dropdown yang ramah pengguna untuk meningkatkan kualitas dan konsistensi data.
- **UI Modern dan Responsif**:
  - Antarmuka pengguna kustom yang dibangun dari awal agar intuitif dan menarik secara visual.
  - Semua tugas yang berjalan lama (pemuatan data, pemrosesan raster) dieksekusi di latar belakang, sehingga antarmuka QGIS tidak pernah macet.

### Prasyarat

Sebelum menginstal, pastikan sistem Anda memenuhi persyaratan berikut:

1.  **Versi QGIS**: QGIS 3.40 LTR atau versi yang lebih baru diperlukan.
2.  **Dependensi Plugin QGIS**: Plugin **`qpip`** harus diinstal. Plugin ini digunakan untuk mengelola dependensi paket Python.
3.  **Dependensi Python**:
    - `python-dotenv`

### Konfigurasi

Plugin ini memerlukan file konfigurasi untuk terhubung ke basis data dan API. Anda dapat membuat file ini di salah satu dari dua lokasi berikut:

1.  File bernama `.env` di direktori root plugin.
2.  File bernama `idpm.env` di folder `Documents` komputer Anda.

File konfigurasi harus berisi variabel-variabel berikut:

```
# --- Pengaturan API ---
API_URL=[https://your-api-endpoint.com/api](https://your-api-endpoint.com/api)

# --- Konfigurasi Basis Data ---
DB_HOST=your_database_host
DB_PORT=5432
DB_USER=your_database_user
DB_PASSWORD=your_database_password
```

### Cara Menggunakan

1.  **Login**: Jalankan plugin dari toolbar QGIS. Anda akan diminta untuk login dengan kredensial Anda.
2.  **Menu Utama**: Setelah login, menu utama menyediakan akses ke semua fitur.
3.  **Muat Data Vektor**:
    - Klik "Open Data Potensi" atau "Open Data Existing".
    - Jika Anda ditugaskan di beberapa wilayah kerja (`wilker`), Anda akan diminta untuk memilih salah satunya.
    - Pilih tahun yang diinginkan untuk data tersebut. Layer akan dimuat ke QGIS.
4.  **Analisis Data Raster**:
    - **(Opsional) Pilih AOI untuk Pencarian**: Untuk mempersempit pencarian Anda, klik opsi ini dan gambar persegi panjang di peta.
    - **Citra Satelit**: Ini akan membuka dialog yang menampilkan daftar citra satelit yang tersedia. Jika Anda mengatur AOI, daftar ini akan difilter.
    - Dari daftar tersebut, Anda dapat:
      - Mengunduh dan melihat citra `Visual` (RGB).
      - Memproses dan menampilkan komposit `NDVI` atau `False Color`.
      - Menggunakan `Kalkulator` untuk analisis raster kustom.
