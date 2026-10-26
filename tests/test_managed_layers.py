"""Two-interface UEV contract: private imports, explicit publication and public visibility."""
from __future__ import annotations

from base64 import b64encode

import pytest
from fastapi.testclient import TestClient

from uev import geo, managed_layers
from uev.admin_api import create_admin_app
from uev.api import create_app

USER="planner"
PASS="correct-horse-example-123456"
AUTH={"Authorization":"Basic "+b64encode((USER+":"+PASS).encode()).decode()}
JSON_HEADERS={**AUTH,"Content-Type":"application/json"}

GEOJSON={"type":"FeatureCollection","features":[
    {"type":"Feature","properties":{"voltage_kv":33,"name":"Test distribution"},
     "geometry":{"type":"LineString","coordinates":[[32.45,.31],[32.51,.38]]}},
    {"type":"Feature","properties":{"name":"Test transformer"},
     "geometry":{"type":"Point","coordinates":[32.5,.32]}}
]}

def valid_upload():
    return {"name":"33 kV pilot feeder dataset","description":"Test only, not an actual grid line",
            "source":"Fictional user-supplied test source","license":"Permission granted for synthetic testing",
            "category":"Electricity infrastructure","reference_year":2026,
            "color":"#ff9900","geojson":GEOJSON}

@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv("UEV_ADMIN_USER",USER)
    monkeypatch.setenv("UEV_ADMIN_PASSWORD",PASS)
    path=tmp_path/"shared.sqlite"
    with TestClient(create_admin_app(path)) as admin, TestClient(create_app(path)) as public:
        yield admin,public

def test_private_requires_auth(clients):
    admin,public=clients
    assert admin.get("/").status_code==401
    assert admin.get("/api/admin/layers").status_code==401
    assert admin.get("/api/admin/layers",auth=("planner","incorrect")).status_code==401
    assert public.get("/api/admin/layers").status_code==404
    assert admin.get("/",headers=AUTH).status_code==200
    assert "PRIVATE BACKEND" in admin.get("/",headers=AUTH).text

def test_no_admin_password_disables_writes(tmp_path,monkeypatch):
    monkeypatch.delenv("UEV_ADMIN_PASSWORD",raising=False)
    monkeypatch.setenv("UEV_ADMIN_USER","planner")
    with TestClient(create_admin_app(tmp_path/"test.sqlite")) as admin:
        assert admin.get("/api/admin/layers",headers={"Authorization":"Basic "+b64encode(b"planner:ignored").decode()}).status_code==503

def test_import_is_draft_until_published(clients):
    admin,public=clients
    uploaded=admin.post("/api/admin/layers",headers=JSON_HEADERS,json=valid_upload())
    assert uploaded.status_code==201,uploaded.text
    ident=uploaded.json()["id"]
    assert uploaded.json()["published"] is False
    assert uploaded.json()["feature_count"]==2
    assert public.get("/api/v1/managed/"+ident).status_code==404
    assert ident not in {x["id"] for x in public.get("/api/v1/catalog").json()["layers"]}
    assert admin.get("/api/admin/layers/"+ident+"/geojson",headers=AUTH).json()["features"][0]["properties"]["voltage_kv"]==33
    published=admin.put("/api/admin/layers/"+ident+"/publication",headers=JSON_HEADERS,json={"published":True})
    assert published.status_code==200, published.text
    assert published.json()["published"] is True
    metadata={x["id"]:x for x in public.get("/api/v1/catalog").json()["layers"]}
    assert metadata[ident]["kind"]=="managed"
    assert metadata[ident]["status"]=="uploaded_unverified"
    assert metadata[ident]["group"]=="Electricity infrastructure"
    assert metadata[ident]["color"]=="#ff9900"
    public_geojson=public.get("/api/v1/managed/"+ident)
    assert public_geojson.status_code==200
    assert public_geojson.json()["features"][0]["properties"]["voltage_kv"]==33
    assert public_geojson.headers["content-type"].startswith("application/geo+json")
    closed=admin.put("/api/admin/layers/"+ident+"/publication",headers=JSON_HEADERS,json={"published":False})
    assert closed.status_code==200
    assert public.get("/api/v1/managed/"+ident).status_code==404
    assert ident not in {x["id"] for x in public.get("/api/v1/catalog").json()["layers"]}

def test_mutation_protected_and_deletion(clients):
    admin,public=clients
    assert admin.post("/api/admin/layers",json=valid_upload()).status_code==401
    assert admin.post("/api/admin/layers",headers={**AUTH,"Content-Type":"text/plain"},
                      content="not JSON").status_code==415
    created=admin.post("/api/admin/layers",headers=JSON_HEADERS,json=valid_upload())
    ident=created.json()["id"]
    assert admin.put("/api/admin/layers/"+ident+"/publication",headers=JSON_HEADERS,json={"published":"yes"}).status_code==422
    assert admin.put("/api/admin/layers/"+ident+"/publication",headers={
        **JSON_HEADERS,"Origin":"http://evil.example"},json={"published":True}).status_code==403
    assert admin.delete("/api/admin/layers/"+ident).status_code==401
    assert admin.delete("/api/admin/layers/"+ident,headers=AUTH).status_code==204
    assert admin.delete("/api/admin/layers/"+ident,headers=AUTH).status_code==404

@pytest.mark.parametrize("invalid",[
    {"type":"FeatureCollection","features":[]},
    {"type":"FeatureCollection","features":[{"type":"Feature",
        "geometry":{"type":"Point","coordinates":[212,0]},"properties":{}}]},
    {"type":"FeatureCollection","features":[{"type":"Feature",
        "geometry":{"type":"GeometryCollection","geometries":[]},"properties":{}}]},
    {"type":"FeatureCollection","crs":{"type":"name","properties":{"name":"EPSG:3857"}},
        "features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[32,.3]},
                     "properties":{}}]}
])
def test_geojson_validation(invalid):
    with pytest.raises(ValueError):
        managed_layers.clean_geojson(invalid)

def test_import_rejects_bad_geometry_no_db_insert(clients):
    admin,_=clients
    bad=valid_upload()
    bad["geojson"]={"type":"FeatureCollection","features":[
        {"type":"Feature","geometry":{"type":"Point","coordinates":[1800,0]},"properties":{}}]}
    assert admin.post("/api/admin/layers",headers=JSON_HEADERS,json=bad).status_code==422
    assert admin.get("/api/admin/layers",headers=AUTH).json()["layers"]==[]

def test_shared_environment_path_contract():
    from pathlib import Path
    import inspect
    from uev import admin_api,api
    # Both applications must have the same default DB path and each support UEV_DB_PATH.
    assert 'UEV_DB_PATH' in inspect.getsource(admin_api.create_admin_app)
    assert 'UEV_DB_PATH' in inspect.getsource(api.create_app)

def test_frontend_control_and_admin_files():
    root=geo.ROOT/"web"
    html=(root/"index.html").read_text(encoding="utf-8")
    js=(root/"layers.js").read_text(encoding="utf-8")
    assert 'id="reload-catalog"' in html
    assert '"/api/v1/managed/"' in js
    admin=(root/"admin.html").read_text(encoding="utf-8")
    assert 'id="layer-form"' in admin and 'id="layer-list"' in admin
    assert (root/"admin.js").is_file() and (root/"admin.css").is_file()
