"""Integrated exploratory planning workflow for synthetic data.

Combines annual fleet charging demand with spatial demand allocation and the
candidate-site MILP. This is NOT a utility load flow or national investment model.
"""
from __future__ import annotations
from collections import defaultdict
from math import isfinite

from . import geo, location
from .model import Charger, Fleet, project

BASELINE_YEAR = 2026
TECHNOLOGIES = {
    "AC": Charger("AC charging", 7, 10, 0.55, 2500),
    "DC": Charger("DC charging", 60, 12, 0.55, 36000),
    "SWAP": Charger("Battery swapping", 24, 18, 0.70, 18000),
}

def _fleet(r: dict) -> Fleet:
    return Fleet(name=f'{r["category"]} / {r["district"]}',
                 total_vehicles=r["total_vehicles"],
                 electric_vehicles=r["electric_vehicles"],
                 km_per_day=r["km_per_day"], kwh_per_km=r["kwh_per_km"],
                 growth_rate=r["growth_rate"])

def run_plan(conn, *, district: str | None = None, target_year: int = 2030,
             target_pct: float = 20, technology: str = "SWAP",
             mode: str = "least_cost", energy_coverage_pct: float = 100,
             radius_km: float = 35, budget_usd: float | None = None,
             modules_per_site: int = 48,
             selected_site_ids: list[str] | None = None) -> dict:
    """Estimate projected EV demand, geolocate it and cost feasible site choices.

    Charging-energy coverage is DIFFERENT from EV fleet electrification.
    Cost outputs are independent hardware and site-CAPEX proxies; never added
    together as a purported system total. Data is entirely synthetic in v0.4.
    """
    if not isinstance(target_year, int) or not BASELINE_YEAR <= target_year <= 2200:
        raise ValueError("Planning year must be between 2026 and 2200")
    if not isfinite(target_pct) or not 0 <= target_pct <= 100:
        raise ValueError("EV fleet target must be between 0 and 100 percent")
    if technology not in TECHNOLOGIES:
        raise ValueError("Unknown charging technology")
    if not isinstance(modules_per_site, int) or not 1 <= modules_per_site <= 100:
        raise ValueError("Charging units per site must be between 1 and 100")
    if district is not None and district not in geo.districts(conn):
        raise ValueError("Unknown demonstration district")
    if mode not in ("least_cost", "max_coverage", "manual"):
        raise ValueError("Unknown investment scenario")
    if mode == "max_coverage" and budget_usd is None:
        raise ValueError("Budget-constrained scenarios require a budget")
    if mode == "manual" and not selected_site_ids:
        raise ValueError("Manual deployment requires selected eligible site IDs")
    charger = TECHNOLOGIES[technology]
    records = geo.fleet_rows(conn, district)
    fleets = [_fleet(r) for r in records]
    forecast = project(fleets, BASELINE_YEAR, target_year, target_pct/100, charger)
    # Allocate *grid input* energy across hotspots separately for each district.
    # Do not allocate one district's energy to another district.
    by_district: dict[str, list[Fleet]] = defaultdict(list)
    for record in records:
        by_district[record["district"]].append(_fleet(record))
    all_hotspots = geo.get_features(conn, "mobility", district)["features"]
    demand_nodes = []
    unlocated_kwh = 0.0
    for area, area_fleets in sorted(by_district.items()):
        area_demand = project(area_fleets, BASELINE_YEAR, target_year,
                              target_pct/100, charger)["grid_kwh_per_day"]
        hotspots = [h for h in all_hotspots if h["properties"]["district"] == area]
        weights = [max(0.0, float(h["properties"].get("activity_index", 0))) for h in hotspots]
        if not hotspots or sum(weights) <= 0:
            unlocated_kwh += area_demand
            continue
        for h, weight in zip(hotspots, weights):
            if weight <= 0:
                continue
            lon, lat = h["geometry"]["coordinates"]
            demand_nodes.append(location.Demand(h["id"], h["properties"]["name"], lon, lat,
                                                area_demand * weight / sum(weights)))
    candidate_features = geo.get_features(conn, "candidates", district)["features"]
    # Synthetic station configuration: same chosen charger package at each
    # eligible site, plus a fictional site-preparation allowance.
    site_throughput = (charger.rated_kw * charger.usable_hours_per_day *
                       charger.utilization * modules_per_site)
    sites = []
    for feature in candidate_features:
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        readiness = float(props.get("grid_readiness_index", 0))
        fixed_site_allowance = 25000 + (1-readiness)*20000
        sites.append(location.Site(
            feature["id"], props["name"], lon, lat,
            capacity_kwh_day=site_throughput,
            capex_usd=round(fixed_site_allowance + modules_per_site*charger.installed_cost, 2),
            eligible=geo.score_candidate(props)["eligible"]))
    result = location.optimize(
        demand_nodes, sites, mode=mode, coverage_pct=energy_coverage_pct,
        radius_km=radius_km, budget_usd=budget_usd, selected_site_ids=selected_site_ids)
    # A fleet-demand forecast with missing mobility coordinates is not fully
    # geolocated and cannot be called fully serviceable.
    if unlocated_kwh > 1e-7:
        result["status"] = "incomplete_spatial_data"
        result["reason"] = "At least one district's vehicle demand has no valid mobility locations"
    baseline_total = sum(r["total_vehicles"] for r in records)
    baseline_evs = sum(r["electric_vehicles"] for r in records)
    baseline_share = 100*baseline_evs/baseline_total if baseline_total else 0
    years = range(BASELINE_YEAR, target_year+1)
    trajectory = []
    for yr in years:
        fraction = ((yr-BASELINE_YEAR)/(target_year-BASELINE_YEAR)
                    if target_year > BASELINE_YEAR else 1)
        interim_pct = baseline_share + (target_pct-baseline_share)*fraction
        snapshot = project(fleets, BASELINE_YEAR, yr, max(0,interim_pct)/100, charger)
        trajectory.append({"year":yr,"electric_vehicles":snapshot["future_evs"],
                           "grid_mwh_per_year":snapshot["grid_mwh_per_year"],
                           "assumed_target_pct":round(interim_pct,2)})
    return {
        "scenario": {"district":district or "All demonstration districts",
                     "target_year":target_year, "ev_fleet_target_pct":target_pct,
                     "technology":technology, "mode":mode,
                     "energy_service_target_pct":energy_coverage_pct,
                     "radius_km":radius_km, "modules_per_site":modules_per_site,
                     "budget_usd":budget_usd},
        "fleet":forecast,
        "location":{**result,"geojson":location.as_geojson(result)},
        "unlocated_grid_kwh_per_day":round(unlocated_kwh,2),
        "status":result["status"],
        "trajectory":trajectory,
        "cost_note":"Station-site CAPEX and generic charging-equipment CAPEX are separate illustrative estimates; do not sum them.",
        "limitations":["All asset and fleet data are SYNTHETIC and not measured Uganda statistics",
                       "Station distances are straight-line, not road-network access",
                       "No verified feeder headroom, hourly peaks or electricity supply balance",
                       "Site throughput and site CAPEX are hypothetical fixed packages",
                       "No vehicle purchase, finance, land tenure, grid reinforcement, OPEX or replacement cost model",
                       "The annual fleet trajectory is a linear-target illustration, not a calibrated uptake forecast or an annual investment program"],
    }
