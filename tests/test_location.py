from uev.location import Demand,Site,optimize,as_geojson
import pytest
D=[Demand("d1","Demand",32.5,0.3,100),Demand("d2","Other",32.51,0.3,80)]
S=[Site("s1","Cheap",32.5,0.3,180,1200),Site("s2","Expensive",32.51,0.3,200,3500),
   Site("s3","Excluded",32.51,0.3,200,1,False)]
def test_least_cost():
    x=optimize(D,S,radius_km=5)
    assert x["status"]=="optimal" and x["site_capex_usd"]==1200 and x["coverage_pct"]==100
    assert len(as_geojson(x)["features"])>=1
def test_max_coverage():
    assert optimize(D,S,mode="max_coverage",budget_usd=1300,radius_km=5)["coverage_pct"]==100
def test_manual_cost():
    assert optimize(D,S,mode="manual",selected_site_ids=["s2"],radius_km=5)["site_capex_usd"]==3500
def test_infeasible():
    assert optimize(D,S,radius_km=.01,budget_usd=1200)["status"]=="infeasible"
def test_invalid():
    with pytest.raises(ValueError):optimize(D,S,mode="max_coverage")
    with pytest.raises(ValueError):optimize(D,S,mode="manual",selected_site_ids=["s3"])
def test_location_api(tmp_path):
    from uev.api import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(tmp_path/"test.sqlite")) as client:
        assert client.get("/api/v1/location/optimize",params={"radius_km":100}).status_code==200
        assert client.get("/api/v1/location/optimize",params={"mode":"bad"}).status_code==422
