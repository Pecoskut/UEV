# UEV — E-Mobility Energy Planning and Modelling

UEV is an open-source geospatial and techno-economic planning project for Uganda's transition toward electric mobility, designed for future expansion beyond Uganda. Its long-term goal combines accessible EAE-inspired map exploration with OnSSET-inspired multi-year investment analysis, including **least-cost and user-defined non-least-cost transition pathways**.

## Project questions

1. Where are electric and internal-combustion fleets operating?
2. How much charging energy and peak power will electrification require?
3. Which electricity networks can accommodate future charging demand?
4. Where should charging and battery-swapping infrastructure be deployed?
5. What investments and timelines are required for user-defined electrification targets, up to 100%?

## Current release — Phase 2 geospatial prototype

- **Phase 1:** baseline fleet and charging energy calculator and simplified charging CAPEX comparisons.
- **Phase 2:** SQLite geospatial source catalogue, GeoJSON/WGS84 point data, candidate-site screening, FastAPI endpoints, MapLibre EAE-inspired web map, district selection and target-year model preview.

**All map coordinates, fleet sizes, grid asset labels and scores in the sample database are SYNTHETIC.** This version is a software demonstration, NOT a Uganda EV census, not a validated charging-location recommendation, and not a least-cost infrastructure optimizer. Full grid engineering, actual station sizing and lifecycle investment optimization are future milestones.

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

See [Phase 2 technical documentation](docs/GEOSPATIAL_PHASE2.md), [architecture](docs/ARCHITECTURE.md) and the MIT [license](LICENSE).

## Roadmap

- **Phase 3:** verified and licensed Uganda datasets, official district polygons, spatial joins, road accessibility and network-constrained location-allocation.
- **Phase 4:** energy network simulations, vehicle supply and replacement rates, least-cost **and alternate-cost** investment pathways across user-selected years.
- **Phase 5:** advanced geospatial interface, stakeholder validation and deployment.

Development contributions welcome. **Do not commit private utility network details, personal GPS traces or restricted operator datasets to this public repository.**
