"""Persistent, provenance-labelled geospatial layers managed by UEV administrators.

Not an official spatial-data registry or a validated optimization data loader.
Separate draft storage from explicitly published, read-only map resources.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

MAX_BYTES = 5_000_000
MAX_FEATURES = 5000
GROUPS = {
    "Population & settlements", "Transport & accessibility",
    "Electricity infrastructure", "EV & mobility",
    "Boundaries & environment", "Other uploaded layers"
}
GEOMETRIES = {"Point":0,"MultiPoint":1,"LineString":1,"MultiLineString":2,
              "Polygon":2,"MultiPolygon":3}

SQL = """
CREATE TABLE IF NOT EXISTS managed_layers (
 id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 description TEXT NOT NULL,
 category TEXT NOT NULL,
 source TEXT NOT NULL,
 license TEXT NOT NULL,
 reference_year INTEGER,
 color TEXT NOT NULL,
 feature_count INTEGER NOT NULL,
 geojson_json TEXT NOT NULL,
 published INTEGER NOT NULL DEFAULT 0 CHECK (published IN (0,1)),
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_managed_published ON managed_layers(published);
"""

def ensure_schema(conn: sqlite3.Connection):
    conn.executescript(SQL)

def _text(value, field: str, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{field} is required and must be at most {maximum} characters")
    return value.strip()

def _coordinate_pair(item):
    if not isinstance(item, list) or len(item) < 2 or len(item) > 3:
        raise ValueError("Invalid WGS84 longitude/latitude pair")
    for n in item:
        if not isinstance(n,(int,float)) or isinstance(n,bool) or not math.isfinite(n):
            raise ValueError("Invalid WGS84 coordinate")
    if not -180 <= item[0] <= 180 or not -90 <= item[1] <= 90:
        raise ValueError("GeoJSON coordinates must be longitude/latitude EPSG:4326")

def _coordinates(value, depth: int, geometry_type: str):
    if depth == 0:
        _coordinate_pair(value)
        return
    if not isinstance(value, list) or not value:
        raise ValueError(f"Invalid {geometry_type} coordinates")
    for child in value:
        _coordinates(child, depth-1, geometry_type)

def clean_geojson(document: dict):
    if not isinstance(document,dict) or document.get("type")!="FeatureCollection":
        raise ValueError("GeoJSON must be a FeatureCollection")
    if "crs" in document:
        raise ValueError("Reproject GeoJSON to EPSG:4326 (WGS84), then remove custom CRS")
    feats=document.get("features")
    if not isinstance(feats,list) or len(feats)==0 or len(feats)>MAX_FEATURES:
        raise ValueError("GeoJSON needs 1 to 5,000 features")
    validated=[]
    for feat in feats:
        if not isinstance(feat,dict) or feat.get("type")!="Feature":
            raise ValueError("Every entry must be a GeoJSON Feature")
        geom=feat.get("geometry")
        if not isinstance(geom,dict) or geom.get("type") not in GEOMETRIES:
            raise ValueError("Supported geometries: Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon")
        kind=geom["type"]
        _coordinates(geom.get("coordinates"),GEOMETRIES[kind],kind)
        props=feat.get("properties")
        if props is None: props={}
        if not isinstance(props,dict):
            raise ValueError("GeoJSON feature properties must be an object")
        validated.append({"type":"Feature","geometry":{"type":kind,"coordinates":geom["coordinates"]},
                          "properties":props})
    result={"type":"FeatureCollection","features":validated}
    encoded=json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(",",":"))
    if len(encoded.encode("utf-8"))>MAX_BYTES:
        raise ValueError("GeoJSON content exceeds 5 MB limit")
    return result,encoded

def _row_dict(row):
    return {key:row[key] for key in (
        "id","name","description","category","source","license",
        "reference_year","color","feature_count","created_at"
    )} | {"published":bool(row["published"]),"data_status":"user_uploaded_unverified"}

def create_layer(conn: sqlite3.Connection, payload: dict):
    if not isinstance(payload,dict): raise ValueError("Expected a layer object")
    name=_text(payload.get("name"),"Layer name")
    description=payload.get("description") or "User-provided geospatial overlay"
    description=_text(description,"Description",2000)
    source=_text(payload.get("source"),"Dataset source")
    license_name=_text(payload.get("license"),"Dataset license / permission")
    category=payload.get("category") or "Other uploaded layers"
    if category not in GROUPS:raise ValueError("Unknown layer category")
    year=payload.get("reference_year")
    if year is not None and (type(year) is not int or not 1900 <= year <= 2200):
        raise ValueError("Reference year must be 1900–2200 or blank")
    color=payload.get("color") or "#2fc7c9"
    if not isinstance(color,str) or not re.fullmatch(r"#[0-9a-fA-F]{6}",color):
        raise ValueError("Colour must be a 6-digit hex value")
    features,encoded=clean_geojson(payload.get("geojson"))
    ident="layer-"+uuid4().hex[:20]
    created=datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""INSERT INTO managed_layers
           (id,name,description,category,source,license,reference_year,color,
            feature_count,geojson_json,published,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,0,?)""",
           (ident,name,description,category,source,license_name,year,color,
            len(features["features"]),encoded,created))
    return get_metadata(conn,ident)

def list_layers(conn: sqlite3.Connection, published_only=False):
    query="SELECT * FROM managed_layers "
    if published_only:query+="WHERE published=1 "
    query+="ORDER BY created_at DESC"
    return [_row_dict(row) for row in conn.execute(query)]

def get_metadata(conn, ident):
    row=conn.execute("SELECT * FROM managed_layers WHERE id=?",(ident,)).fetchone()
    return _row_dict(row) if row else None

def get_layer(conn, ident, published_only=True):
    row=conn.execute("SELECT * FROM managed_layers WHERE id=?"+(" AND published=1" if published_only else ""), (ident,)).fetchone()
    if row is None:return None
    return json.loads(row["geojson_json"])

def set_publication(conn, ident, published):
    if type(published) is not bool:raise ValueError("Publication setting must be true or false")
    with conn:
        cur=conn.execute("UPDATE managed_layers SET published=? WHERE id=?",(int(published),ident))
    return get_metadata(conn,ident) if cur.rowcount else None

def remove_layer(conn, ident):
    with conn:
        cursor=conn.execute("DELETE FROM managed_layers WHERE id=?",(ident,))
    return cursor.rowcount>0

def catalog_entries(conn):
    return [{
        "id":row["id"], "name":row["name"], "description":row["description"],
        "group":row["category"],"kind":"managed","status":"uploaded_unverified",
        "source":row["source"],"license":row["license"],"year":row["reference_year"],
        "color":row["color"],"feature_count":row["feature_count"],"default":False
    } for row in list_layers(conn,True)]
