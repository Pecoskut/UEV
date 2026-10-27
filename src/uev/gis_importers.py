"""Convert a single local GIS vector file into validated WGS84 GeoJSON.

Support GeoJSON, CSV points, zipped Esri Shapefile (one layer), GeoPackage
(one WGS84 feature table). Input files are restricted to 20 MB. Resulting
GeoJSON still obeys the managed layer's 5 MB / 5,000-feature safeguards.

Uploaded data is never put on GitHub or published automatically.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sqlite3
import zipfile
from pathlib import Path

from . import managed_layers

MAX_UPLOAD_BYTES = 20_000_000
MAX_ARCHIVE_UNPACKED = 60_000_000
ACCEPTED_EXTENSIONS = {".geojson", ".json", ".csv", ".zip", ".gpkg"}

def _geojson(filename: str, raw: bytes) -> dict:
    try:
        value=json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError,ValueError) as exc:
        raise ValueError("This file is not valid UTF-8 GeoJSON. Export from QGIS as GeoJSON (EPSG:4326).") from exc
    if isinstance(value,dict) and value.get("type")=="Feature":
        value={"type":"FeatureCollection","features":[value]}
    return value

def _csv(filename: str, raw: bytes) -> dict:
    try:
        stream=io.StringIO(raw.decode("utf-8-sig"),newline="")
        reader=csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        names={field.strip().lower():field for field in reader.fieldnames if field}
        lon_col=next((names[k] for k in ("longitude","lon","lng","long","x") if k in names),None)
        lat_col=next((names[k] for k in ("latitude","lat","y") if k in names),None)
        if not lon_col or not lat_col:
            raise ValueError("CSV point layers need longitude and latitude columns (or lon/lat)")
        features=[]
        for row in reader:
            if len(features)>=managed_layers.MAX_FEATURES:
                raise ValueError("Too many CSV points (maximum 5,000 per uploaded layer)")
            try:
                lon=float(row[lon_col])
                lat=float(row[lat_col])
            except (ValueError,TypeError) as exc:
                raise ValueError(f"Invalid longitude/latitude in CSV row {len(features)+2}") from exc
            if not math.isfinite(lon) or not math.isfinite(lat) or not -180<=lon<=180 or not -90<=lat<=90:
                raise ValueError(f"Invalid WGS84 coordinate in CSV row {len(features)+2}")
            features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
                             "properties":{k:(v if v is not None else "") for k,v in row.items() if k}})
        return {"type":"FeatureCollection","features":features}
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc

def _wgs84_prj(prj: str) -> bool:
    # Do not silently pretend a national-grid projected shapefile is WGS84.
    normalized=prj.upper().replace(" ","").replace("_","")
    return "WGS84" in normalized and ("GEOGCS[" in normalized or "GEOGCRS[" in normalized or "GEODCRS[" in normalized)

def _safe_props(values: dict) -> dict:
    result={}
    for k,v in values.items():
        if hasattr(v,"isoformat"):
            v=v.isoformat()
        elif isinstance(v,bytes):
            v=v.decode("utf-8",errors="replace")
        result[str(k)]=v
    return result

def _zipped_shapefile(filename: str, raw: bytes) -> dict:
    try:
        import shapefile
    except ImportError as exc:
        raise ValueError("Shapefile import dependency missing. Reinstall with pip install -e \".[geo,test]\".") from exc
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos=[f for f in z.infolist() if not f.is_dir()]
            if any(f.file_size>MAX_ARCHIVE_UNPACKED for f in infos) or sum(f.file_size for f in infos)>MAX_ARCHIVE_UNPACKED:
                raise ValueError("Shapefile ZIP uncompressed contents exceed 60 MB")
            shpfiles=[p.filename for p in infos if Path(p.filename).suffix.lower()==".shp"]
            if len(shpfiles)!=1:
                raise ValueError("ZIP must contain exactly one Shapefile (.shp, .dbf, .shx, .prj)")
            base=shpfiles[0][:-4]
            archive={p.filename.lower():p.filename for p in infos}
            required=[base+ext for ext in (".shp",".dbf",".shx",".prj")]
            if any(p.lower() not in archive for p in required):
                raise ValueError("Shapefile ZIP needs matching .shp, .dbf, .shx and .prj files")
            projection=z.read(archive[(base+".prj").lower()]).decode("utf-8-sig",errors="replace")
            if not _wgs84_prj(projection):
                raise ValueError("Shapefile is not confirmed as WGS84 (EPSG:4326). Reproject to EPSG:4326 in QGIS before uploading.")
            def component(ext):
                return io.BytesIO(z.read(archive[(base+ext).lower()]))
            with shapefile.Reader(shp=component(".shp"),shx=component(".shx"),dbf=component(".dbf")) as reader:
                if len(reader)>managed_layers.MAX_FEATURES:
                    raise ValueError("Too many Shapefile features (maximum 5,000)")
                features=[]
                for item in reader.iterShapeRecords():
                    geometry=json.loads(json.dumps(item.shape.__geo_interface__))
                    if geometry is None or geometry.get("type")=="Null":
                        raise ValueError("Shapefile has null or unsupported geometry")
                    features.append({"type":"Feature","geometry":geometry,
                                     "properties":_safe_props(item.record.as_dict())})
            return {"type":"FeatureCollection","features":features}
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("ZIP is corrupt or is not a zipped ESRI Shapefile.") from exc

def _geopackage(filename: str, raw: bytes) -> dict:
    try:
        from shapely import wkb
        from shapely.geometry import mapping
    except ImportError as exc:
        raise ValueError("GeoPackage import dependency missing. Reinstall with pip install -e \".[geo,test]\".") from exc
    try:
        conn=sqlite3.connect(":memory:")
        conn.deserialize(raw)
        conn.row_factory=sqlite3.Row
        tables=conn.execute("SELECT table_name,column_name,srs_id FROM gpkg_geometry_columns").fetchall()
        if len(tables)!=1:
            raise ValueError("GeoPackage must contain exactly one spatial layer. Export a single layer from QGIS.")
        table=tables[0]["table_name"]
        column=tables[0]["column_name"]
        if tables[0]["srs_id"]!=4326:
            raise ValueError("GeoPackage layer must be EPSG:4326. Reproject it in QGIS before upload.")
        quote=lambda s:'"'+s.replace('"','""')+'"'
        count=conn.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0]
        if count>managed_layers.MAX_FEATURES:
            raise ValueError("GeoPackage layer has more than 5,000 features. Export a smaller study area.")
        rows=conn.execute(f"SELECT * FROM {quote(table)}")
        features=[]
        for record in rows:
            blob=record[column]
            if blob is None:raise ValueError("GeoPackage contains empty geometries")
            if not isinstance(blob,bytes) or blob[:2]!=b"GP" or len(blob)<8:
                raise ValueError("Invalid GeoPackage geometry header")
            flags=blob[3]
            envelope=(flags>>1)&7
            if envelope not in (0,1,2,3,4):
                raise ValueError("Unsupported GeoPackage geometry envelope")
            offset=8+{0:0,1:32,2:48,3:48,4:64}[envelope]
            if len(blob)<=offset:raise ValueError("Invalid GeoPackage geometry length")
            g=wkb.loads(blob[offset:])
            features.append({"type":"Feature","geometry":json.loads(json.dumps(mapping(g))),
                             "properties":_safe_props({k:record[k] for k in record.keys() if k!=column})})
        return {"type":"FeatureCollection","features":features}
    except sqlite3.Error as exc:
        raise ValueError("Invalid GeoPackage SQLite structure or geometry table") from exc
    finally:
        if "conn" in locals():conn.close()

def parse_uploaded_layer(filename: str, raw: bytes) -> tuple[dict,str]:
    extension=Path(filename or "").suffix.lower()
    if extension not in ACCEPTED_EXTENSIONS:
        if extension in (".tif",".tiff",".geotiff"):
            raise ValueError("GeoTIFF is a raster, not a vector layer. Use QGIS to prepare a vector layer; population raster publishing needs the upcoming raster pipeline.")
        raise ValueError("Unsupported file type. Upload .geojson, .json, .csv, .zip (zipped Shapefile), or .gpkg.")
    if not raw or len(raw)>MAX_UPLOAD_BYTES:
        raise ValueError("GIS file must be between 1 byte and 20 MB")
    parsers={".geojson":_geojson,".json":_geojson,".csv":_csv,
             ".zip":_zipped_shapefile,".gpkg":_geopackage}
    result=parsers[extension](filename,raw)
    # Same authoritative validation for every supported source format.
    cleaned,encoded=managed_layers.clean_geojson(result)
    return cleaned,f"{len(cleaned['features'])} vector features; {len(encoded.encode('utf-8')):,} bytes prepared for storage"
