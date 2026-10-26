# Phase 5 — UEV spatial layer explorer

## What was added
A GEP/EAE-inspired **Layers / Scenarios** switch beside the existing EV planning model. Users may independently enable mapped transport/electricity assets, historical population, synthetic EV planning data or a **local** GeoJSON point/line/polygon overlay. Layers are also searchable. A legend reports source type; enabling a public layer queries the *currently visible map area*. Zoom into the district/town for Overpass API queries.

The **Scenarios** tab remains functional: district, EV fleet target, planning year, technology, charging units/site, service radius, budget-limited maximum coverage, lowest site-CAPEX deployment and user-selected candidate portfolios. The plotted selected stations and allocation links remain synthetic.

## Dataset catalogue

| Layer | Actual map function | Source / year | Coverage / limitation |
| --- | --- | --- | --- |
| Population archive | Toggle georeferenced population image overlay | WorldPop / Esri archived series, through 2020 | Historical estimated data; may require internet/third-party service |
| Population 2026 | Source link only for downloading GeoTIFF | WorldPop Global2 2026 | Source available, **not yet a live renderable tile layer** |
| Roads | Toggle road geometry query at current map view | OpenStreetMap live | Mapped roads only; incomplete and not calibrated travel speeds |
| Transmission | Toggle `power=line` geometry query | OpenStreetMap live | OSM power lines may have unknown voltage; NOT certified HV utility assets |
| Distribution | Toggle `power=minor_line` geometry query | OpenStreetMap live | Often incomplete; DOES NOT represent the operator's MV/LV network |
| Substations/transformers | Toggle mapped public nodes and substation ways | OpenStreetMap live | No spare feeder power or transformer hosting capacity |
| Existing chargers, candidate sites, grid nodes, activity points | Toggle synthetic local GeoJSON | UEV demonstration, 2026 | Completely fictional, only for testing UI and scenario code |
| District boundaries | Data procurement/import needed | Uganda government / UBOS | No official polygons currently bundled |
| Solar resource | Source link only | Global Solar Atlas | Further preparation needed |
| Local GeoJSON | Choose local file in browser | User-supplied | Display-only, not uploaded; no validation of source provenance |

## Data sources and scientific controls
- [WorldPop Uganda 2026 population 100m](https://hub.worldpop.org/geodata/summary?id=75840): modelled grid-cell counts, not an official Uganda census; the 2026 dataset is an R2025A alpha product.
- [WorldPop archived ArcGIS raster](https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Total_Population_100m/ImageServer): accessible public historical population imagery; online provider may sometimes be unavailable.
- [OpenStreetMap / Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API): requests are limited to a Uganda bounding box <= 0.30 square degrees. Attribution **© OpenStreetMap contributors, ODbL**; requests are intentionally user-triggered to limit shared-server use. **Public OSM mapping coverage is incomplete and not a source of distribution-line engineering confidence**.
- [Global Solar Atlas](https://globalsolaratlas.info): public source entry pending GIS integration.

**Layer activation is currently visualization and exploratory inspection ONLY. It does NOT dynamically alter charging demand, grid constraints, site eligibility, facility-location objective coefficients, or investment totals.** Those computations still use the synthetic Phase 1–4 inputs. Do not infer model calibration just because a real population / distribution layer is visible.

## Launch
```cmd
conda activate uev
cd /d "C:\Users\user\Desktop\Personal\Projects\EV Uganda\UEV-main\UEV-main"
python -m pip install -e ".[geo,test]"
python -m pytest -q
python -m uvicorn uev.api:app --reload
```

Open http://127.0.0.1:8000 and choose **Layers**. Zoom into Kampala, Jinja or another district, tick **Road network** or **Transmission (OSM mapped)**, then use **Refresh public layers** when you pan. Select **Scenarios** for calculations. The application requires a working network connection to use OpenStreetMap / WorldPop remote services.

## Next implementation priorities
1. Load verified, licensed Uganda distribution and transmission lines, substation capacities and complete administrative polygons using controlled GeoJSON/GeoPackage or PostGIS imports; do not publish restricted data to a public repo.
2. Integrate 2026 WorldPop population rasters as map tiles and disaggregate actual vehicle/charging loads with a calibrated OD/network transport model.
3. Network-aware road travel times, geospatial joins and verifiable distance-to-feeder inputs to candidate-site constraints.
4. Add time-series distribution hosting capacity, transformer/feeder upgrades and multiple charging/swapping technologies.
5. Annual system investment optimization with vehicle replacement, solar/battery, charger lifecycle, OPEX and finance scenarios; scalable Uganda-to-global data sources.
