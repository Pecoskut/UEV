# UEV 0.6 — Two-interface architecture: private Data Manager + public Planning Explorer

UEV has **two separate web applications** sharing the same SQLite file. This is not merely a visual tab: the privileged administration HTTP routes are unavailable on the public web process.

| User experience | Default local URL | Python ASGI application | Who can use it |
|---|---|---|---|
| **Backend / Private Data Manager** | http://127.0.0.1:8002 | uev.admin_api:app | Authenticated administrator only |
| **Frontend / Planning Explorer** | http://127.0.0.1:8001 | uev.api:app | Read-only public exploration + demo modelling |

Both use the same default database, ~/.uev/uev-demo.sqlite. To choose a different database, set the **same** UEV_DB_PATH environment variable in BOTH terminals. Do not put passwords into source files or the public GitHub repository.

## 1. Start on Windows / Anaconda Prompt

Download and extract the **latest main branch** after merging the Phase 6 development pull request. Then open the first Anaconda Prompt:

```cmd
conda activate uev
cd /d "C:\Users\user\Desktop\Personal\Projects\EV Uganda\UEV 2\UEV-main\UEV-main"
python -m pip install -e ".[geo,test]"
python -m pytest -q
python -m uvicorn uev.api:app --host 127.0.0.1 --port 8001 --reload
```

Open http://127.0.0.1:8001 — this is the public explorer with Layers and Scenarios.

**Keep that window running** and open a SECOND Anaconda Prompt (do not close the frontend prompt):

```cmd
conda activate uev
cd /d "C:\Users\user\Desktop\Personal\Projects\EV Uganda\UEV 2\UEV-main\UEV-main"
set UEV_ADMIN_USER=planner
set UEV_ADMIN_PASSWORD=REPLACE_WITH_YOUR_LONG_PRIVATE_PASSWORD
python -m uvicorn uev.admin_api:app --host 127.0.0.1 --port 8002 --reload
```

**Important:** Replace the placeholder with your own **unique password at least 12 characters long**. Do not share it in chat, commit it to GitHub or put it in a screen recording. It is a local development credential and basic authentication is only acceptable on localhost / a trusted connection; public deployment must use HTTPS, hardened authentication, secure sessions, permissions, backups and logging.

Now open http://127.0.0.1:8002. Your browser will request your administrator username/password (set in the second prompt). This is the separate backend portal.

## 2. Upload, preview, publish and activate

1. In the **Data Manager**, choose a licensed **GeoJSON FeatureCollection**, with WGS84 longitude/latitude coordinates. Supported geometries: Point, MultiPoint, LineString, MultiLineString, Polygon and MultiPolygon. Import limits: 5 MB, 5,000 features per dataset.
2. Enter name, group, original data owner/source, date, licence or permission, optional description and map colour. Click **Import as private draft**. Dataset remains in the shared SQLite file **without public visibility**.
3. Click **Preview** to inspect the map, source and features. Confirm that publishing the entire file, **including feature properties**, is legally permitted and doesn't reveal protected network infrastructure or personal location records.
4. Click **Publish** to make it available in the read-only public API, or **Unpublish** to withdraw it. You can delete datasets in the backend.
5. In the **Planning Explorer**, go to **LAYERS → Check for published layers**. Your new dataset appears in its category with an **UPLOADED / UNVERIFIED** label. Check it to render on the map; uncheck to hide.
6. Go to **SCENARIOS** to run the existing charging and EV electrification calculation. **The newly uploaded overlay is display-only until explicitly mapped, validated, and integrated into the scientific models.**

## 3. Data governance, scientific integrity and security

- Drafts are not returned from public catalogue or public GeoJSON endpoints. Admin API reads/writes require HTTP Basic authentication on **port 8002**, with environment-based credentials; the public application on **port 8001** does not expose admin routes.
- Dataset metadata stores the original source, reference year, selected category, reported licence, feature count, and publication state.
- Publishing exposes the full geometry and all properties through /api/v1/managed/{layer_id}. **Never publish restricted utility networks, exact passenger GPS trails, personal data or proprietary data without permission.**
- The layer's presence on the map does not constitute verification of electricity network completeness, hosting capacity, road coverage, population correctness or right to develop charging sites.
- Public OpenStreetMap/WorldPop visual layers remain separate from administrator-uploaded datasets and from synthetic Phase 1–4 planning inputs.
- No CSV tables, GeoPackage, shapefile ZIP, TIFF, PostGIS import, geospatial CRS reprojection, auditing, multi-admin accounts or object storage yet. Those are production roadmap items.
- This prototype is **not secure for public hosting** without an authenticated server behind HTTPS, secure cookies/session handling or a full identity provider, request rate limits, network isolation and access logs.

## 4. What changes for UEV modelling later

The platform now has the critical infrastructure/data-governance separation:
- **Private management** for curated population, road, administrative, grid and charging datasets;
- **Public geospatial visualisation** for published sources;
- **Existing scenario calculator** with synthetic input data while calibration is pending.

Future development: dataset-role mapping to modelling inputs (e.g. distribution feeder → true kVA/kW hosting limit, road link → routable travel times, population raster → demand proxy), schema validations and model-version lineage. Merely selecting a map layer never implies the solver used it.

## API endpoints

Admin on port 8002 (HTTP Basic required):
- GET /api/admin/layers — list all owned layers including unpublished drafts
- POST /api/admin/layers — import and validate JSON with GeoJSON FeatureCollection + metadata
- GET /api/admin/layers/{id}/geojson — preview, including private drafts
- PUT /api/admin/layers/{id}/publication — set {"published":true|false}
- DELETE /api/admin/layers/{id} — permanent deletion

Public on port 8001 (read-only):
- GET /api/v1/catalog — built-in plus **published** datasets
- GET /api/v1/managed/{id} — GeoJSON available **only if published**
- Existing /api/v1/plans/run, /api/v1/public/osm/... etc.

## Troubleshooting

If new data is missing, ensure both servers use the same file under UEV_DB_PATH, the dataset is PUBLISHED, and click **Check for published layers** in the front end. Use different ports (8001 and 8002) to avoid serving an old front-end version from port 8000.

Running the applications in two Anaconda Prompt windows does not copy the GIS data: both read/write the shared SQLite file automatically.
