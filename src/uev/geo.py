"""UEV geospatial catalogue: locally executable SQLite/WGS84 foundation.

This is *not* a utility GIS or engineering-approved site location model.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

LAYERS = {"charging", "candidates", "grid", "mobility"}
WEIGHTS = {
    "balanced": {"demand": .35, "road": .20, "grid": .25, "equity": .20},
    "grid_ready": {"demand": .25, "road": .15, "grid": .50, "equity": .10},
    "coverage": {"demand": .25, "road": .15, "grid": .15, "equity": .45},
}
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "db" / "sqlite.sql"
DEMO_GEO = ROOT / "data" / "demo_assets.geojson"
DEMO_FLEET = ROOT / "data" / "demo_fleets.csv"


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def score_candidate(props: dict[str, Any], lens: str = "balanced") -> dict[str, Any]:
    """Transparent weighted *screening* score, not network/least-cost optimization."""
    if lens not in WEIGHTS:
        raise ValueError("Unknown planning lens")
    if not props.get("land_available", False) or props.get("protected_area", True):
        return {"eligible": False, "suitability_score": None,
                "reason": "Excluded: land unavailable or location restricted"}
    measures = {"demand": "demand_index", "road": "road_access_index",
                "grid": "grid_readiness_index", "equity": "underserved_index"}
    try:
        values = {key: float(props[field]) for key, field in measures.items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Incomplete candidate-site screening inputs") from exc
    if any(not 0 <= x <= 1 for x in values.values()):
        raise ValueError("Candidate indices must be in [0,1]")
    score = sum(values[k] * weight for k, weight in WEIGHTS[lens].items())
    return {"eligible": True, "suitability_score": round(100 * score, 1),
            "reason": "Illustrative weighted screening; grid capacity not certified"}


def _clean_feature(feature: dict[str, Any]) -> tuple:
    if feature.get("type") != "Feature" or not isinstance(feature.get("properties"), dict):
        raise ValueError("Expected a GeoJSON Feature with properties")
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if geom.get("type") != "Point" or not isinstance(coords, list) or len(coords) != 2:
        raise ValueError("Stage 2 import supports only WGS84 Point geometry")
    lon, lat = coords
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lon, lat)):
        raise ValueError("Invalid coordinate values")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("Coordinates must be WGS84 longitude/latitude")
    props = dict(feature["properties"])
    if props.get("layer") not in LAYERS:
        raise ValueError("Unrecognized spatial data layer")
    if not isinstance(props.get("district"), str) or not props["district"].strip():
        raise ValueError("A district label is required")
    if not isinstance(props.get("name"), str) or not props["name"].strip():
        raise ValueError("A feature name is required")
    if props["layer"] == "candidates":
        score_candidate(props)
    feature_id = str(feature.get("id") or "").strip()
    if not feature_id:
        raise ValueError("Each feature must have a stable ID")
    return (feature_id, props["layer"], props["name"], props["district"],
            float(lon), float(lat), json.dumps(props, sort_keys=True))


def import_geojson(conn: sqlite3.Connection, document: dict[str, Any], source_id: str) -> int:
    if document.get("type") != "FeatureCollection" or not isinstance(document.get("features"), list):
        raise ValueError("Expected a GeoJSON FeatureCollection")
    # Validate all records before writing to avoid partially imported datasets.
    rows = [_clean_feature(feature) for feature in document["features"]]
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError("Duplicate IDs in imported GeoJSON")
    with conn:
        for row in rows:
            conn.execute("INSERT OR REPLACE INTO geo_features "
                         "(id,layer,name,district,lon,lat,properties_json,source_id) "
                         "VALUES (?,?,?,?,?,?,?,?)", (*row, source_id))
    return len(rows)


def seed_demo(conn: sqlite3.Connection, geo_path: Path = DEMO_GEO,
              fleet_path: Path = DEMO_FLEET) -> None:
    if conn.execute("SELECT COUNT(*) FROM geo_features").fetchone()[0]:
        return
    with conn:
        conn.execute("INSERT OR IGNORE INTO sources "
                     "(id,title,reference_year,license,confidence,is_demo) VALUES (?,?,?,?,?,?)",
                     ("synthetic-v1", "UEV fictional demonstration records", 2026,
                      "CC0-1.0 (illustrative sample only)", "synthetic", 1))
    import_geojson(conn, json.loads(geo_path.read_text(encoding="utf-8")), "synthetic-v1")
    with fleet_path.open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    with conn:
        for r in records:
            total, electric = int(r["total_vehicles"]), int(r["electric_vehicles"])
            if not 0 <= electric <= total:
                raise ValueError("Invalid demo fleet record")
            conn.execute("INSERT OR REPLACE INTO fleets "
                         "(district,category,total_vehicles,electric_vehicles,km_per_day,kwh_per_km,growth_rate,source_id) "
                         "VALUES (?,?,?,?,?,?,?,?)",
                         (r["district"], r["category"], total, electric,
                          float(r["km_per_day"]), float(r["kwh_per_km"]),
                          float(r["growth_rate"]), "synthetic-v1"))


def districts(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT district FROM fleets ORDER BY district")]


def get_features(conn: sqlite3.Connection, layer: str, district: str | None = None,
                 lens: str = "balanced") -> dict[str, Any]:
    if layer not in LAYERS:
        raise ValueError("Unknown layer")
    if lens not in WEIGHTS:
        raise ValueError("Unknown screening lens")
    rows = conn.execute("SELECT g.*,s.title AS source_title,s.reference_year,s.confidence,s.is_demo "
                        "FROM geo_features g JOIN sources s ON g.source_id=s.id "
                        "WHERE g.layer=? AND (? IS NULL OR g.district=?) ORDER BY g.id",
                        (layer, district, district)).fetchall()
    features = []
    for r in rows:
        props = json.loads(r["properties_json"])
        props.update({"id": r["id"], "source": r["source_title"],
                      "reference_year": r["reference_year"],
                      "confidence": r["confidence"], "is_demo": bool(r["is_demo"])})
        if layer == "candidates":
            props.update(score_candidate(props, lens))
        features.append({"type": "Feature", "id": r["id"],
                         "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                         "properties": props})
    return {"type": "FeatureCollection", "features": features}


def ranked_sites(conn: sqlite3.Connection, district: str | None = None,
                 lens: str = "balanced") -> list[dict[str, Any]]:
    feats = get_features(conn, "candidates", district, lens)["features"]
    feasible = [{**f["properties"], "longitude": f["geometry"]["coordinates"][0],
                 "latitude": f["geometry"]["coordinates"][1]}
                for f in feats if f["properties"]["eligible"]]
    return sorted(feasible, key=lambda p: (-p["suitability_score"], p["name"]))


def fleet_rows(conn: sqlite3.Connection, district: str | None = None) -> list[dict]:
    rows = conn.execute("SELECT * FROM fleets WHERE (? IS NULL OR district=?) "
                        "ORDER BY district, category", (district, district)).fetchall()
    return [dict(r) for r in rows]


def get_summary(conn: sqlite3.Connection, district: str | None = None) -> dict[str, Any]:
    fleets = fleet_rows(conn, district)
    total = sum(r["total_vehicles"] for r in fleets)
    electric = sum(r["electric_vehicles"] for r in fleets)
    counts = {layer: len(get_features(conn, layer, district)["features"]) for layer in sorted(LAYERS)}
    return {"district": district or "All demo districts", "total_vehicles": total,
            "electric_vehicles": electric,
            "electric_share_pct": round(electric / total * 100, 2) if total else 0,
            "category_count": len(fleets), "layers": counts, "is_demo": True,
            "disclaimer": "All fleet and asset quantities are synthetic. No grid headroom is certified."}
