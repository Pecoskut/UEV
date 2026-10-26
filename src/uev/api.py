"""UEV phase-two geospatial API: demo records only; no grid-capacity certification."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import geo
from . import location
from .model import Charger, Fleet, project

WEB = geo.ROOT / "web"
CHARGERS = {
    "AC": Charger("AC", 7, 10, .55, 2500),
    "DC": Charger("DC", 60, 12, .55, 36000),
    "SWAP": Charger("Battery swapping", 24, 18, .70, 18000),
}


def create_app(db_path: str | Path | None = None, seed_demo: bool = True) -> FastAPI:
    path = Path(db_path or os.environ.get("UEV_DB_PATH", Path.home() / ".uev" / "uev-demo.sqlite"))
    with geo.connect(path) as conn:
        if seed_demo:
            geo.seed_demo(conn)
    app = FastAPI(title="UEV Geospatial Explorer API", version="0.2.0",
                  description="Exploratory GIS and demand previews with explicitly synthetic demonstration data")
    app.mount("/static", StaticFiles(directory=WEB), name="static")

    def _db():
        return geo.connect(path)

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    @app.get("/api/v1/metadata")
    def metadata():
        return {"version": "0.2.0", "data_status": "SYNTHETIC DEMONSTRATION ONLY",
                "baseline_year": 2026,
                "layers": sorted(geo.LAYERS), "lenses": list(geo.WEIGHTS),
                "disclaimer": "Coordinates and asset descriptions are invented. No station is verified, approved or grid-ready."}

    @app.get("/api/v1/districts")
    def districts():
        with _db() as conn:
            return geo.districts(conn)

    @app.get("/api/v1/summary")
    def summary(district: str | None = None):
        with _db() as conn:
            if district is not None and district not in geo.districts(conn):
                raise HTTPException(status_code=404, detail="District not found in demo inventory")
            return geo.get_summary(conn, district)

    @app.get("/api/v1/layers/{layer}")
    def layer_data(layer: str, district: str | None = None,
                   lens: str = "balanced"):
        try:
            with _db() as conn:
                return geo.get_features(conn, layer, district, lens)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/sites/ranked")
    def sites(district: str | None = None, lens: str = "balanced"):
        try:
            with _db() as conn:
                return geo.ranked_sites(conn, district, lens)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/model/preview")
    def model_preview(district: str | None = None,
                      target_year: int = Query(2040, ge=2026, le=2200),
                      target_pct: float = Query(100, ge=0, le=100),
                      technology: str = "SWAP"):
        if technology not in CHARGERS:
            raise HTTPException(status_code=422, detail="Technology must be AC, DC or SWAP")
        with _db() as conn:
            if district is not None and district not in geo.districts(conn):
                raise HTTPException(status_code=404, detail="Unknown demo district")
            rows = geo.fleet_rows(conn, district)
        fleets = [Fleet(name=r["category"]+" / "+r["district"], total_vehicles=r["total_vehicles"],
                        electric_vehicles=r["electric_vehicles"], km_per_day=r["km_per_day"],
                        kwh_per_km=r["kwh_per_km"], growth_rate=r["growth_rate"])
                  for r in rows]
        result = project(fleets, 2026, target_year, target_pct / 100, CHARGERS[technology])
        return {**result, "status": "synthetic-demonstration", "selected_district": district,
                "warning": "Demand/cost preview only. Not a least-cost national plan or site-specific engineering analysis."}


    @app.get("/api/v1/location/optimize")
    def location_optimize(district: str | None = None, mode: str = "least_cost",
                          coverage_pct: float = Query(100, ge=0, le=100),
                          radius_km: float = Query(25, gt=0, le=1000),
                          budget_usd: float | None = Query(None, ge=0),
                          selected_site_ids: str = ""):
        with _db() as conn:
            mobility=geo.get_features(conn,"mobility",district)["features"]
            candidates=geo.get_features(conn,"candidates",district)["features"]
        ds=[location.Demand(f["id"],f["properties"]["name"],*f["geometry"]["coordinates"],
                            round(float(f["properties"].get("activity_index",0))*1000,2)) for f in mobility]
        ss=[location.Site(f["id"],f["properties"]["name"],*f["geometry"]["coordinates"],
                          capacity_kwh_day=round(900+float(f["properties"].get("grid_readiness_index",0))*1200),
                          capex_usd=round(25000+(1-float(f["properties"].get("grid_readiness_index",0)))*20000),
                          eligible=geo.score_candidate(f["properties"])["eligible"]) for f in candidates]
        try:
            result=location.optimize(ds,ss,mode=mode,coverage_pct=coverage_pct,
                                      radius_km=radius_km,budget_usd=budget_usd,
                                      selected_site_ids=selected_site_ids.split(",") if selected_site_ids else None)
            return {**result,"geojson":location.as_geojson(result),
                    "disclaimer":"ALL inputs are SYNTHETIC demonstration data; not a certified location investment model."}
        except ValueError as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc

    return app

app = create_app()
