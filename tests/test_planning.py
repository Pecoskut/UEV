import pytest
from fastapi.testclient import TestClient

from uev import geo
from uev.api import create_app
from uev.planning import run_plan


@pytest.fixture
def db(tmp_path):
    with geo.connect(tmp_path / "plans.sqlite") as conn:
        geo.seed_demo(conn)
        yield conn


def test_district_forecast_drives_site_demand(db):
    plan = run_plan(db, district="Kampala", target_year=2026,
                    target_pct=10, energy_coverage_pct=90,
                    radius_km=30, modules_per_site=100)
    assert plan["status"] == "optimal"
    assert plan["location"]["coverage_pct"] >= 90
    assert plan["fleet"]["future_evs"] > 0
    assert plan["location"]["total_demand_kwh_day"] == pytest.approx(
        plan["fleet"]["grid_kwh_per_day"], abs=.1)
    assert plan["location"]["selected_sites"]
    assert plan["location"]["site_capex_usd"] > 0
    assert plan["unlocated_grid_kwh_per_day"] == 0
    assert all(f["properties"]["kind"] in ("selected_station", "indicative_assignment")
               for f in plan["location"]["geojson"]["features"])


def test_planning_year_and_linear_trajectory(db):
    plan=run_plan(db,district="Jinja",target_year=2065,target_pct=100,
                  modules_per_site=100,energy_coverage_pct=40,radius_km=100)
    assert len(plan["trajectory"]) == 40
    assert plan["trajectory"][0]["year"]==2026
    assert plan["trajectory"][-1]["year"]==2065
    assert plan["fleet"]["target_year"]==2065
    assert plan["fleet"]["future_evs"] >= plan["trajectory"][0]["electric_vehicles"]


def test_user_defined_portfolio_costed_even_if_nonleast_cost(db):
    plan=run_plan(db,district="Kampala",target_year=2026,target_pct=10,
                  mode="manual",selected_site_ids=["ca-ka-2"],modules_per_site=100,
                  radius_km=100,energy_coverage_pct=10)
    assert plan["status"]=="optimal"
    assert [s["id"] for s in plan["location"]["selected_sites"]]==["ca-ka-2"]


def test_budget_limits_investment(db):
    plan=run_plan(db,district="Kampala",target_year=2026,target_pct=10,
                  mode="max_coverage",budget_usd=0,modules_per_site=100,
                  radius_km=100)
    assert plan["status"]=="optimal"
    assert plan["location"]["site_capex_usd"]==0
    assert plan["location"]["coverage_pct"]==0


def test_failure_does_not_claim_no_fleet_demand(db):
    plan=run_plan(db,district="Kampala",target_year=2026,target_pct=100,
                  radius_km=1,modules_per_site=1)
    assert plan["status"]=="infeasible"
    assert plan["fleet"]["grid_kwh_per_day"]>0
    assert plan["location"].get("site_capex_usd") is None


def test_unlocated_demand_is_explicit(db):
    db.execute("DELETE FROM geo_features WHERE layer='mobility' AND district='Kampala'")
    db.commit()
    plan=run_plan(db,district="Kampala",target_year=2026,target_pct=20)
    assert plan["status"]=="incomplete_spatial_data"
    assert plan["unlocated_grid_kwh_per_day"]>0


def test_invalid_config(db):
    with pytest.raises(ValueError):run_plan(db,technology="NONSENSE")
    with pytest.raises(ValueError):run_plan(db,district="Missing")
    with pytest.raises(ValueError):run_plan(db,modules_per_site=101)
    with pytest.raises(ValueError):run_plan(db,mode="manual")
    with pytest.raises(ValueError):run_plan(db,mode="max_coverage")


def test_integrated_api(tmp_path):
    app=create_app(tmp_path/"web.sqlite")
    with TestClient(app) as client:
        ok=client.get("/api/v1/plans/run",params={
            "district":"Kampala","target_year":2027,"target_pct":10,
            "energy_coverage_pct":30,"radius_km":100,"modules_per_site":100})
        assert ok.status_code==200,ok.text
        payload=ok.json()
        assert "trajectory" in payload and "location" in payload
        assert payload["scenario"]["district"]=="Kampala"
        assert client.get("/api/v1/plans/run",params={"target_pct":101}).status_code==422
        assert client.get("/api/v1/plans/run",params={"mode":"manual"}).status_code==422
