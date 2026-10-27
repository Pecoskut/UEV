"""File import regression tests: CSV, GeoJSON, zipped Shapefile, GeoPackage."""
import io
import json
import sqlite3
import struct
import zipfile
from base64 import b64encode

import pytest
import shapefile
from shapely.geometry import Point
from fastapi.testclient import TestClient

from uev import gis_importers, managed_layers
from uev.admin_api import create_admin_app
from uev.api import create_app

LOGIN={"Authorization":"Basic "+b64encode(b"planner:valid-password-123456").decode()}
FORM={
 "name":"Test import", "source":"Synthetic unit-test data",
 "license":"Synthetic data; publication permitted", "category":"Electricity infrastructure",
 "description":"Private upload test","reference_year":"2026","color":"#118877"
}

def sample_geojson():
    return {"type":"FeatureCollection","features":[{"type":"Feature",
             "properties":{"name":"Demo test point"},
             "geometry":{"type":"Point","coordinates":[32.5,.3]}}]}

def zipped_shapefile():
    shp,shx,dbf=io.BytesIO(),io.BytesIO(),io.BytesIO()
    with shapefile.Writer(shp=shp,shx=shx,dbf=dbf,shapeType=shapefile.POINT) as writer:
        writer.field("name","C")
        writer.point(32.5,.3);writer.record("Demo point")
    z=io.BytesIO()
    with zipfile.ZipFile(z,"w") as archive:
        archive.writestr("roads.shp",shp.getvalue())
        archive.writestr("roads.shx",shx.getvalue())
        archive.writestr("roads.dbf",dbf.getvalue())
        archive.writestr("roads.prj",'GEOGCS["WGS_1984",DATUM["D_WGS_1984"],UNIT["Degree",0.0174532925199433]]')
    return z.getvalue()

def geopackage_bytes():
    connection=sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE gpkg_geometry_columns(table_name TEXT,column_name TEXT,srs_id INTEGER)")
        connection.execute("CREATE TABLE example (id INTEGER, geom BLOB, name TEXT)")
        connection.execute("INSERT INTO gpkg_geometry_columns VALUES ('example','geom',4326)")
        geometry=b"GP"+bytes([0,1])+struct.pack("<I",4326)+Point(32.5,.3).wkb
        connection.execute("INSERT INTO example VALUES (?,?,?)",(1,geometry,"Test point"))
        return connection.serialize()
    finally:connection.close()

@pytest.mark.parametrize(("filename","payload","count"),[
 ("sample.geojson",json.dumps(sample_geojson()).encode(),1),
 ("points.csv",b"longitude,latitude,name\n32.5,0.3,Demo charger\n32.6,0.4,Other\n",2),
 ("roads.zip",zipped_shapefile(),1),
 ("area.gpkg",geopackage_bytes(),1),
])
def test_supported_files(filename,payload,count):
    data,message=gis_importers.parse_uploaded_layer(filename,payload)
    assert len(data["features"])==count
    assert "vector features" in message
    assert all(f["geometry"]["coordinates"] for f in data["features"])

def test_geojson_single_feature():
    feature=sample_geojson()["features"][0]
    parsed,_=gis_importers.parse_uploaded_layer("sample.json",json.dumps(feature).encode())
    assert len(parsed["features"])==1

def test_reject_wrong_coordinate_and_rasters():
    with pytest.raises(ValueError,match="WGS84"):
        gis_importers.parse_uploaded_layer("points.csv",b"lon,lat\n400,0\n")
    with pytest.raises(ValueError,match="GeoTIFF"):
        gis_importers.parse_uploaded_layer("population.tif",b"some raster")
    with pytest.raises(ValueError,match="longitude and latitude"):
        gis_importers.parse_uploaded_layer("points.csv",b"xname,yname\n3,4\n")
    with pytest.raises(ValueError,match="Unsupported file type"):
        gis_importers.parse_uploaded_layer("unknown.exe",b"whatever")

def test_shapefile_requires_projection():
    raw=zipped_shapefile()
    memory=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(memory,"w") as output:
        for name in source.namelist():
            if not name.endswith(".prj"):output.writestr(name,source.read(name))
    with pytest.raises(ValueError,match=".prj"):
        gis_importers.parse_uploaded_layer("roads.zip",memory.getvalue())

def test_gpkg_rejects_wrong_crs():
    conn=sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE gpkg_geometry_columns(table_name TEXT,column_name TEXT,srs_id INTEGER)")
        conn.execute("CREATE TABLE example(id INTEGER,geom BLOB)")
        conn.execute("INSERT INTO gpkg_geometry_columns VALUES ('example','geom',3857)")
        raw=conn.serialize()
    finally:conn.close()
    with pytest.raises(ValueError,match="EPSG:4326"):
        gis_importers.parse_uploaded_layer("map.gpkg",raw)

@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv("UEV_ADMIN_USER","planner")
    monkeypatch.setenv("UEV_ADMIN_PASSWORD","valid-password-123456")
    db=tmp_path/"import.sqlite"
    with TestClient(create_admin_app(db)) as admin, TestClient(create_app(db)) as public:
        yield admin,public

def test_multipart_ingest_draft_and_publish(clients):
    admin,public=clients
    result=admin.post("/api/admin/files",headers=LOGIN,data=FORM,
                      files={"file":("roads.zip",zipped_shapefile(),"application/zip")})
    assert result.status_code==201,result.text
    row=result.json()
    assert row["published"] is False
    assert row["feature_count"]==1
    assert row["original_filename"]=="roads.zip"
    assert public.get("/api/v1/managed/"+row["id"]).status_code==404
    pub=admin.put("/api/admin/layers/"+row["id"]+"/publication",
                  headers={**LOGIN,"Content-Type":"application/json"},json={"published":True})
    assert pub.status_code==200,pub.text
    assert public.get("/api/v1/managed/"+row["id"]).status_code==200

def test_multipart_validation_message(clients):
    admin,_=clients
    result=admin.post("/api/admin/files",headers=LOGIN,data=FORM,
                      files={"file":("population.tif",b"test","image/tiff")})
    assert result.status_code==422,result.text
    assert "GeoTIFF" in result.json()["detail"]

def test_no_auth_admin_upload(clients):
    admin,_=clients
    result=admin.post("/api/admin/files",data=FORM,
                      files={"file":("points.csv",b"lon,lat\n32.5,.3\n","text/csv")})
    assert result.status_code==401

def test_frontend_form_allows_new_formats():
    from uev import geo
    html=(geo.ROOT/"web"/"admin.html").read_text(encoding="utf-8")
    script=(geo.ROOT/"web"/"admin.js").read_text(encoding="utf-8")
    assert "id=\"import-status\"" in html
    assert ".gpkg" in html and ".csv" in html and ".zip" in html
    assert '"/api/admin/files"' in script
    assert "FormData()" in script
