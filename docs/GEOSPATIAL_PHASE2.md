# UEV Phase 2 — Geographic explorer

## What is implemented

- Local persistent **SQLite** inventory containing source lineage, WGS84 point layers and fleet table.
- Optional future **PostGIS** schema in `db/postgis.sql` (migration/sync not yet implemented).
- Seeded, clearly **synthetic** demo records across five Ugandan districts; all site coordinates and assets are fictional and must never be labelled verified.
- Read-only **FastAPI** GeoJSON endpoints, district summaries, candidate suitability rankings and a preview using the Phase 1 demand engine.
- Responsive **MapLibre** map interface with four toggleable layers, district filtering, three screening lenses and selectable target year/electrification share.
- API tests, import validation and rejection of duplicate GeoJSON identifiers and invalid WGS84 point coordinates.

## Start the geospatial explorer

```shell
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[geo,test]"
uvicorn uev.api:app --reload
```

Open `http://127.0.0.1:8000` for the map and `http://127.0.0.1:8000/docs` for API documentation. The **basemap needs internet access** (MapLibre JS and OpenStreetMap tiles) but the geo-data and modelling endpoints remain local. For a production deployment, use an appropriate vector-tile provider rather than relying on the public OSM raster tile service.

### API routes

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/metadata` | Dataset status, warnings, supported layers |
| GET | `/api/v1/districts` | Available demonstration district names |
| GET | `/api/v1/summary?district=Jinja` | District / all-demo inventory summary |
| GET | `/api/v1/layers/candidates?district=Jinja&lens=balanced` | GeoJSON point features with provenance |
| GET | `/api/v1/sites/ranked?lens=coverage` | Ranked eligible sample candidates |
| GET | `/api/v1/model/preview?district=Jinja&target_year=2050&target_pct=100&technology=SWAP` | Demand and charger-size proxy scenario |

### Local database

By default UEV stores the demo SQLite data at `~/.uev/uev-demo.sqlite`. Use `UEV_DB_PATH` to specify another local path. SQLite is appropriate for a small reproducible prototype, **not** the long-term national multiuser geospatial database. `db/postgis.sql` provides an initial architecture for the production PostGIS deployment.

### Input contract

Current GeoJSON loader requires `FeatureCollection` of WGS84 `Point` features, each with a stable `id`, `properties.layer` (`charging`, `candidates`, `grid`, `mobility`), `name` and `district`. All ingested records reference a mandatory provenance entry in `sources`; fields include observation year, license, confidence and whether demo data.

Candidate sites also contain normalized indices in `[0,1]`: `demand_index`, `road_access_index`, `grid_readiness_index` and `underserved_index`, plus `land_available` and `protected_area` flags. Excluded sites are not ranked.

### Screening score

`score = 100 × (w_demand × demand + w_road × road + w_grid × grid + w_equity × equity)`

| Lens | Demand | Road | Grid | Equity |
|---|---:|---:|---:|---:|
| Balanced | 35% | 20% | 25% | 20% |
| Grid readiness | 25% | 15% | 50% | 10% |
| Coverage | 25% | 15% | 15% | 45% |

**This is a heuristic screening score, not least-cost station siting.** The grid index is a fictional demo input, not transformer spare capacity. Next phases will require true transport OD, feeder loads/ratings, charger waiting-time constraints, service-area coverage, land screening and an explicit multi-period objective function.

## Data governance

- Do not commit personally identifying location traces, utility internal records or commercially restricted operator data to a public repository.
- Real datasets must be reviewed for license, commercial confidentiality, coordinate precision, observation date and confidence before publication.
- Fleet operations should be spatially assigned to where charging is expected to occur, not automatically to vehicle registration district.
- Verified station suitability requires field checks, land rights and utility engineering review.

## Next milestone

Import official district polygons, provenance-checked fleet and station inventories, geospatial joins, road network reachability and technically constrained station location-allocation optimization. This phase intentionally implements only *point layers*, not full polygon GIS or power-flow studies.
