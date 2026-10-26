# UEV Phase 4 — Integrated Demand and Charging-Site Planning

## Purpose
Connect an OnSSET-inspired transition scenario (selected future year and fleet target), the EAE-inspired district/map explorer, and the Phase 3 station-location MILP into a single exploratory user workflow.

## Model sequence
1. Select district (or all synthetic demonstration districts), target year, EV fleet percentage, and charging technology.
2. Phase 1 `project()` estimates future fleet and its charging electricity input (kWh/day and MWh/year). Each vehicle category's travel and efficiency is taken from synthetic sample records.
3. Allocate **each district's** projected grid charging energy to its mobility points in proportion to their respective activity indices. This is a synthetic allocation proxy, NOT measured vehicle trip origin–destination or charging behavior. Demand not covered by valid mobility locations is reported as `unlocated_grid_kwh_per_day` and scenario is marked `incomplete_spatial_data`.
4. For each candidate, assign an illustrative fixed package of `modules_per_site` identical charger units. Daily grid-energy throughput = rated power × available hours × utilization × modules. Candidate site CAPEX proxy = synthetic site preparation allowance + module unit price × module count.
5. Phase 3 MILP selects site packages and dispatches projected charging demand to eligible sites within a great-circle radius. Alternative user purposes:
   - **least_cost:** minimize site CAPEX subject to minimum energy service coverage.
   - **max_coverage:** maximize served demand subject to a station investment budget.
   - **manual:** hold the chosen site portfolio fixed and calculate its cost and feasibility.
6. Report: selected stations, indication-only demand-to-station lines, daily served/unserved energy, percentage of charging energy served, site CAPEX, projected fleet, total annual charging energy, generic national charger hardware CAPEX proxy and a linear-share year-by-year EV/energy trajectory.

## Endpoint
`GET /api/v1/plans/run`

Parameters: `district`, `target_year` (2026–2200), `target_pct` (0–100), `technology` (SWAP/AC/DC), `mode` (least_cost/max_coverage/manual), `energy_coverage_pct` (0–100), `radius_km`, `budget_usd`, `modules_per_site` (1–100), `selected_site_ids` (comma separated; manual mode).

Examples:
```
/api/v1/plans/run?district=Jinja&target_year=2055&target_pct=100&technology=DC&mode=least_cost&radius_km=40&modules_per_site=80
/api/v1/plans/run?district=Kampala&target_year=2030&target_pct=20&mode=max_coverage&budget_usd=1000000&radius_km=50
/api/v1/plans/run?district=Kampala&target_year=2030&target_pct=10&mode=manual&selected_site_ids=ca-ka-1
```

## Cost boundaries
Selected-site CAPEX is a site **package estimate**, including synthetic site preparation and charger units. The Phase 1 generic charger hardware CAPEX is a different fleet-wide sizing reference; it overlaps site package costs. **Do not add both estimates.** Missing categories: cost of electric vehicles, battery replacement, detailed land and civil works, electricity purchase, energy generation, solar PV/storage, utility reinforcement, financing/OPEX, taxes and salvage value.

## Scientific limitations
- Every current demo dataset (vehicle counts, locations, activity index, estimated network readiness and dollar costs) is **SYNTHETIC**.
- No road-network shortest path, ride detour, traffic volume, queue simulation, station hours, actual distribution feeder headroom or measured electricity consumption.
- Same fixed charging package at every candidate for the selected technology; no multi-technology co-location or staged network upgrades.
- EV target is a minimum fleet share in the Phase 1 stock model; fleet stock turn-over, new sales policy, ICE retirement, EV supply constraints, maximum fleet-growth rate and actual achieving-100%-year are NOT modeled.
- Hourly peak load remains a simplistic capacity proxy and is not a distribution load-flow study.
- Annual trajectory assumes a *linear interpolated fleet-share* to the end-year target and does not optimize annual investments or keep track of installed station assets.
- Optimization may be infeasible. In that case costs are **not** reported as $0.

## Next technical priorities
1. Validate official and restricted data permissions; implement QA-ingested real spatial data with provenance.
2. Replace geodesic radius with road-routing/drive-time accessibility and introduce multi-technology candidate options.
3. Include engineering feeder constraints, technology-specific battery swaps and depot schedules.
4. Add dynamic multi-year optimization for full transition investment and scenario comparisons, and annual financing.
