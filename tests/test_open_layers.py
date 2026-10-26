"""Public map-layer catalogue, bounding and integrity tests (network-independent)."""
import pytest
from fastapi.testclient import TestClient
from uev import open_layers
from uev.api import create_app
from uev import geo

def test_catalog_has_population_transport_and_power():
    catalog={d["id"]:d for d in open_layers.CATALOG}
    for key in ("population_2020","population_2026","osm_roads",
                "osm_transmission","osm_distribution","osm_substations"):
        assert key in catalog
    assert catalog["population_2020"]["year"]==2020
    assert catalog["population_2026"]["status"]=="download"
    assert catalog["osm_distribution"]["description"].find("NOT a utility")>=0
    assert catalog["grid"]["status"]=="synthetic"

def test_osm_bbox_valid_and_restricted():
    bbox=open_layers.validate_bbox("32.5,0.2,32.7,0.4")
    assert bbox==(32.5,0.2,32.7,0.4)
    for bad in ("32.5,0.2,40,2","1,2,3","33,2,32,1",
                "nan,0,1,1","30,-4,31,-2"):
        with pytest.raises(ValueError):
            open_layers.validate_bbox(bad)
    with pytest.raises(ValueError):
        open_layers.validate_bbox("32,0,33,1")

def test_osm_query_is_small_bbox_and_fixed_allowlist():
    query=open_layers.build_osm_query("osm_distribution",(32.5,.2,32.7,.4))
    assert 'power"="minor_line"' in query
    assert "(0.200000,32.500000,0.400000,32.700000)" in query
    with pytest.raises(ValueError):
        open_layers.build_osm_query("arbitrary-remote-url",(32.5,.2,32.7,.4))

def test_osm_geometries_and_tags_preserved():
    elements=[
        {"type":"way","id":100,"tags":{"power":"line","voltage":"132000","name":"Sample"},
         "geometry":[{"lon":32.5,"lat":.1},{"lon":32.6,"lat":.2}]},
        {"type":"node","id":200,"lon":32.51,"lat":.21,
         "tags":{"power":"substation"}}
    ]
    result=open_layers.convert_osm(elements,"osm_transmission")
    assert result["type"]=="FeatureCollection"
    assert result["features"][0]["geometry"]["type"]=="LineString"
    assert result["features"][0]["properties"]["voltage"]=="132000"
    assert result["features"][1]["geometry"]["type"]=="Point"
    assert result["metadata"]["verified_electrical_assets"] is False
    with pytest.raises(ValueError):
        open_layers.convert_osm([], "url")

def test_catalog_route_and_static_ui(tmp_path):
    with TestClient(create_app(tmp_path/"layers.sqlite")) as client:
        response=client.get("/api/v1/catalog")
        assert response.status_code==200
        names={x["id"] for x in response.json()["layers"]}
        assert {"osm_roads","osm_transmission","osm_distribution","population_2020"}<=names
        html=client.get("/").text
        assert 'id="view-layers"' in html and 'id="view-scenarios"' in html
        assert 'id="refresh-layers"' in html
        assert client.get("/static/layers.js").status_code==200

def test_public_api_does_not_fetch_network_when_bbox_invalid(tmp_path):
    with TestClient(create_app(tmp_path/"layers.sqlite")) as client:
        assert client.get("/api/v1/public/osm/osm_roads",
                          params={"bbox":"32,0,34,2"}).status_code==422
        assert client.get("/api/v1/public/population.png",
                          params={"bbox":"32,0,34,4"}).status_code==422

def test_live_osm_returns_mocked_public_data(tmp_path,monkeypatch):
    async def fake_fetch(layer,bbox):
        return {"type":"FeatureCollection","features":[],"metadata":{"source":"OSM","is_demo":False}}
    monkeypatch.setattr(open_layers,"load_osm",fake_fetch)
    with TestClient(create_app(tmp_path/"layers.sqlite")) as client:
        response=client.get("/api/v1/public/osm/osm_roads",params={"bbox":"32.5,0.2,32.7,0.4"})
        assert response.status_code==200
        assert response.json()["metadata"]["is_demo"] is False

def test_population_proxy_mock(tmp_path,monkeypatch):
    async def fake_image(bbox):
        return b"\x89PNG\r\n\x1a\n" + b"test"
    monkeypatch.setattr(open_layers,"population_png",fake_image)
    with TestClient(create_app(tmp_path/"layers.sqlite")) as client:
        response=client.get("/api/v1/public/population.png",params={"bbox":"32.5,0.2,32.7,0.4"})
        assert response.status_code==200
        assert response.headers["content-type"].startswith("image/png")
        assert response.content.startswith(b"\x89PNG")

def test_layer_frontend_elements_are_present():
    html=(geo.ROOT/"web"/"index.html").read_text(encoding="utf-8")
    js=(geo.ROOT/"web"/"layers.js").read_text(encoding="utf-8")
    for element in ("layer-search","layer-catalog","custom-geojson","custom-list",
                    "layer-status","active-map-legend","view-scenarios","view-layers"):
        assert f'id="{element}"' in html
        assert element in js
