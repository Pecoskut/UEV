# UEV — E-Mobility Energy Planning and Modelling

Open-source geospatial, techno-economic modelling platform for Uganda's electric mobility transition, designed to scale internationally.

## Vision
Combine accessible, EAE-inspired mapping with OnSSET-inspired multi-year infrastructure and investment planning. UEV will answer:
1. Where are electric and conventional vehicle fleets?
2. How much electricity will electrified transport use, including hourly peaks?
3. Where are grid constraints and required upgrades?
4. Where and how many charging and swapping stations should be built?
5. What transition year, costs, and investments are required to meet user-selected e-mobility targets, up to 100%?

## Stage 1: working modelling foundation
This first prototype estimates fleet growth, user-defined EV transition targets, daily/annual charging energy, and indicative charging capacity and costs. It offers a **cost estimation pathway and a simple constrained least-cost comparison** for technology packages. This is **not** yet a validated national forecast, electrical load-flow, station-siting optimizer, or full vehicle lifecycle financial model. Demo values are synthetic.

## Run locally
Requires Python 3.11 or newer.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[demo,test]"
streamlit run app.py
```

Run tests: `pytest -q`.

## Roadmap
- **Phase 1**: mathematical foundations, data schema, scenario engine, simple interface, tests.
- **Phase 2**: geospatial vehicle/demand baselines and actual Uganda district data with confidence labels.
- **Phase 3**: site location-allocation, feeder constraints, batteries and bus-route operations.
- **Phase 4**: dynamic multi-year optimization, infrastructure investments, financing and policy scenarios.
- **Phase 5**: production EAE-style map interface, stakeholder validation, documentation and deployment.

## Data and scientific integrity
Never represent demonstration vehicle counts, costs, site coordinates or transformer ratings as official Ugandan data. Every imported dataset should carry source, observation year, coverage, licensing and confidence metadata.

## Development
See [architecture](docs/ARCHITECTURE.md). Contributions and issue reports welcome. Licensed under the repository's MIT license.
