# UEV — E-Mobility Energy Planning and Modelling

UEV is an open-source geospatial and techno-economic planning project for Uganda's transition toward electric mobility, designed for future expansion beyond Uganda. Its long-term goal combines accessible EAE-inspired map exploration with OnSSET-inspired multi-year investment analysis, including **least-cost and user-defined non-least-cost transition pathways**.

## Project questions

1. Where are electric and internal-combustion fleets operating?
2. How much charging energy and peak power will electrification require?
3. Which electricity networks can accommodate future charging demand?
4. Where should charging and battery-swapping infrastructure be deployed?
5. What investments and timelines are required for user-defined electrification targets, up to 100%?

## Current development release — Phase 6 dual-interface GIS data management

- **Phase 1:** baseline fleet and charging energy calculator and simplified charging CAPEX comparisons.
- **Phase 2:** SQLite spatial inventory, source catalogue, GeoJSON, FastAPI, MapLibre explorer and district filters.
- **Phase 3:** capacitated station location-allocation (candidate-site CAPEX, maximum service coverage for a budget, user-defined site portfolios).
- **Phase 4:** integrated scenario workflow joining year-specific fleet energy demand to candidate-site allocation, interactive selected-site and link map overlays, annual EV/energy trajectory and downloadable JSON.
- **Phase 5:** GEP/EAE-inspired Layers / Scenarios tabs; searchable geospatial catalogue, OSM road/power layers, historical WorldPop population overlay and local GIS previews.
- **Phase 6:** separate password-protected GIS Data Manager on port 8002 and public Planning Explorer on port 8001, sharing a SQLite data catalogue. Administrator uploads and previews licensed GeoJSON as PRIVATE drafts; explicitly publishing creates reusable toggleable layers on the public map. Model inputs remain unaltered until validated integration.

**The built-in UEV demonstration asset coordinates, fleet sizes, grid labels and site scores are SYNTHETIC.** Public OpenStreetMap/WorldPop overlays are separate and not fed into optimization. This remains a software demonstration, NOT a Uganda EV census, an engineering-approved charging-location recommendation, a national least-cost investment pathway or a grid power-flow model. Full grid engineering, actual station sizing and lifecycle investment optimization are future milestones.

## Importing vector GIS data (v0.6.1)

The private backend imports GeoJSON, CSV coordinate tables, EPSG:4326 zipped Shapefile, and single-layer EPSG:4326 GeoPackage. Every import starts as a private draft, with clear error messages and source/licence metadata. GeoTIFF rasters require a future separate pipeline. See [GIS import troubleshooting](docs/GIS_IMPORTS_PHASE6_1.md).

## Private backend and public frontend

**Two separate running web applications share one data store.** Only administrators may upload or publish layers. Public users can only explore published layers and run existing scenarios. See [Windows installation and workflows](docs/DUAL_INTERFACE_PHASE6.md) for exact commands and security cautions.

- **Public Planning Explorer:** `python -m uvicorn uev.api:app --host 127.0.0.1 --port 8001 --reload` → http://127.0.0.1:8001
- **Private Data Manager:** set `UEV_ADMIN_USER` and an independent `UEV_ADMIN_PASSWORD` (12+ characters) in another terminal; run `python -m uvicorn uev.admin_api:app --host 127.0.0.1 --port 8002 --reload` → http://127.0.0.1:8002
- Both applications must read the same `UEV_DB_PATH` (they share the same default if unset). Only GeoJSON vector files are importable through the admin UI at present. Newly imported layers are private until published.

## Run the interactive GIS prototype

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[geo,test]"
uvicorn uev.api:app --reload
```

Open http://127.0.0.1:8000 for the explorer or http://127.0.0.1:8000/docs for API documentation. MapLibre JS and OpenStreetMap basemap tiles require internet access; all demo spatial/model API data is served locally.

For the earlier Phase 1 Streamlit demo, install `pip install -e ".[demo]"` and run `streamlit run app.py`.

Run tests: `pytest -q`.

See [Phase 5 layers and data guidance](docs/LAYER_EXPLORER_PHASE5.md), [Phase 2 technical documentation](docs/GEOSPATIAL_PHASE2.md), [architecture](docs/ARCHITECTURE.md) and the MIT [license](LICENSE).

## Layer explorer and integrated modelling workflow

Open **Layers** to turn on road, mapped transmission and distribution, substations/transformers, historical population or synthetic EV datasets. Zoom to a Ugandan town before turning on public OSM layers; re-query after map pan with the **Refresh public layers** control. **Add your own layer** accepts GeoJSON only in your browser session (not stored and not used for the solver). Official district boundaries and 2026 population raster are presently source catalogue entries, not integrated nationwide overlays. Public utility data is incomplete; enabling an OSM layer does not certify its completeness or fitness for network analysis.

Open **Scenarios** to use the existing EV modelling tools.

## Current integrated workflow
Visit the web explorer at http://127.0.0.1:8000 and configure the year, fleet transition target, technology, site modules, distance radius, and infrastructure investment mode; click **Run integrated scenario**. View the selected sites and allocation links, coverage feasibility, separate charging hardware and candidate-site costs, and year-by-year EV/energy pathway. Download full scenario JSON.

API: `GET /api/v1/plans/run?district=Kampala&target_year=2030&target_pct=20&technology=SWAP&mode=least_cost&radius_km=35&modules_per_site=48`.

Three alternative objectives currently supported: (1) lowest selected-site CAPEX at user-defined energy coverage, (2) maximum served energy within site budget, (3) user-selected non-least-cost station portfolio.

**Scientific caution:** EV fleet penetration and fraction of charging electricity served are DIFFERENT. Site CAPEX and generic charging equipment CAPEX are overlapping alternative estimates and **must not be added**. A model can correctly return infeasible; the result does not mean EV charging demand is zero. The target-year trajectory uses linear-share interpolation, not an empirical adoption model. Only synthetic fleet, mobility, site and cost inputs are used.

Detailed methodology: [integrated model](docs/INTEGRATED_PHASE4.md).

## Roadmap

- **Next:** verified Ugandan vehicle and charging datasets, official district polygons, source QA/permissions, spatial joins and road-network travel times.
- **Phase 6:** feeder loads, transformer headroom, infrastructure reinforcement and hourly charging.
- **Phase 7:** full least-cost and non-least-cost **multi-year** system optimization, including vehicle investments, charging assets, grid, solar, financing, OPEX and replacement.
- **Phase 8:** national planning reports, validation, deployments and access-control for sensitive utility/operator data.

Development contributions welcome. **Do not commit private utility network details, personal GPS traces or restricted operator datasets to this public repository.**
