# GIS Data Manager import troubleshooting and supported formats (UEV v0.6.1)

The Backend Data Manager runs at http://127.0.0.1:8002 (or another port you choose), with HTTP Basic credentials set in the SAME terminal that launches the backend. The public Explorer is a different application and port.

## Formats for administrator imports

| Input | What is supported | Important limitations |
|---|---|---|
| GeoJSON (.geojson or .json) | FeatureCollection and single Feature | WGS84 (longitude, latitude), output <=5 MB / 5,000 features |
| CSV (.csv) | Point datasets with **longitude/latitude** (or lon/lat) columns | UTF-8; coordinates in decimal degrees, not UTM |
| Zipped Shapefile (.zip) | A single Shapefile (.shp, .dbf, .shx, .prj inside ZIP) | Must have WGS84/EPSG:4326 .prj |
| GeoPackage (.gpkg) | A single vector feature table in EPSG:4326 | Export multi-table GeoPackages to one layer first |
| GeoTIFF (.tif, .tiff) | **Not supported in the vector importer** | Raster / population map tiling will require a separate pipeline |

Original file max 20 MB, converted GeoJSON max 5 MB and 5,000 features. No truncation: oversized inputs are rejected to prevent misleading incomplete maps. Keep national road/population datasets for the future PostGIS + raster tiling backend.

**An accepted upload becomes a PRIVATE draft, never automatically a public dataset.** Administrators can preview, explicitly publish and unpublish the layer. Publishing exposes the entire GeoJSON geometry and all feature attributes to public users.

## QGIS preparation

For Shapefiles or GeoPackages with other coordinate systems, open in QGIS → right-click layer → Export → Save Features As… → select **GeoJSON** or **ESRI Shapefile**, set **CRS EPSG:4326**, and if needed filter to a reasonable geographic area. For Shapefile, compress the four matching .shp, .shx, .dbf and .prj files into one ZIP.

For population GeoTIFF, do not pretend a point/line importer is appropriate. Keep the original raster; UEV needs a separate raster storage/tiling pipeline.

## Expected workflow

1. Open Backend Data Manager; select supported file type. A status line will describe what the importer expects.
2. Enter **Display name**, **Data owner/source**, and **License/permission**. Set category, date, description and layer colour.
3. Click **Import as private draft**. The status box shows success or a detailed error returned from server. The new dataset appears in **Dataset library** and can be previewed.
4. Check geographic extent and sensitive feature attributes. Click **Publish** only if you have permission and wish it visible to other users.
5. In the public Explorer (8001), open **LAYERS → Check for published layers**, then check the corresponding new GIS layer.

## If upload still fails

- **GeoTIFF is a raster:** unsupported in this version.
- **Unsupported file type:** use GeoJSON / CSV / zipped Shapefile / GeoPackage.
- **WGS84 / EPSG:4326:** reproject before importing.
- **Over 5 MB or 5,000 features:** simplify/split into smaller layers; future national-scale import will be separate.
- **Missing column:** CSV requires explicit longitude/latitude fields.
- **401 unauthorized / 503 configure password:** revisit backend credentials; they must be set in the terminal running the admin API.
- **500 server error:** share the traceback displayed in the backend terminal, omitting credentials and sensitive dataset records, for debugging.

## Setup on Windows (newer branch)

Open an Anaconda Prompt in the updated project folder and run:

```cmd
conda activate uev
cd /d "C:\Users\user\Desktop\Personal\Projects\EV Uganda\EV Modeling\UEV-main\UEV-main"
python -m pip install -e ".[geo,test]"
python -m pytest -q
```

Run frontend and backend in separate terminals as documented in [Phase 6 architecture](DUAL_INTERFACE_PHASE6.md), with the same UEV_DB_PATH for both processes.

## Modelling boundary

New layers are **published for display** in this release. The EV energy model does not yet use uploaded population/road/distribution layers to calculate demand, grid hosting, site feasibility or optimized costs. This next milestone requires explicit dataset-role assignment and scientific input validation.
