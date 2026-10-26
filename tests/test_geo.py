import json
import pytest
from uev import geo


def test_demo_inventory_and_lineage(tmp_path):
    with geo.connect(tmp_path / "test.sqlite") as conn:
        geo.seed_demo(conn)
        geo.seed_demo(conn)
        assert geo.districts(conn) == ["Gulu", "Iganga", "Jinja", "Kampala", "Wakiso"]
        features = geo.get_features(conn, "charging", "Jinja")
        assert len(features["features"]) == 1
        assert features["features"][0]["properties"]["is_demo"] is True
        assert geo.get_summary(conn, "Kampala")["total_vehicles"] > 0


def test_suitability_weighting_and_exclusion(tmp_path):
    with geo.connect(tmp_path / "geo.sqlite") as conn:
        geo.seed_demo(conn)
        balanced = geo.ranked_sites(conn, lens="balanced")
        coverage = geo.ranked_sites(conn, lens="coverage")
        assert len(balanced) == 6
        assert len(coverage) == 6
        assert balanced[0]["suitability_score"] >= balanced[-1]["suitability_score"]
        excluded = geo.get_features(conn, "candidates", "Wakiso")["features"]
        assert any(not f["properties"]["eligible"] for f in excluded)


def test_invalid_coordinates_and_duplicate_ids_do_not_partially_import(tmp_path):
    with geo.connect(tmp_path / "geo.sqlite") as conn:
        conn.execute("INSERT INTO sources VALUES (?,?,?,?,?,?)", ("test", "Test", 2026, "MIT", "synthetic", 1))
        conn.commit()
        good = {"type": "Feature", "id": "good", "geometry": {"type":"Point", "coordinates": [32.2, 0.3]},
                "properties": {"layer": "charging", "name": "A", "district": "Demo"}}
        bad = json.loads(json.dumps(good)); bad["id"] = "bad"; bad["geometry"]["coordinates"][0] = 280.0
        with pytest.raises(ValueError):
            geo.import_geojson(conn, {"type": "FeatureCollection", "features": [good, bad]}, "test")
        assert conn.execute("SELECT COUNT(*) FROM geo_features").fetchone()[0] == 0
        with pytest.raises(ValueError):
            geo.import_geojson(conn, {"type": "FeatureCollection", "features": [good, good]}, "test")


def test_candidate_missing_inputs_rejected():
    with pytest.raises(ValueError):
        geo.score_candidate({"land_available": True, "protected_area": False, "demand_index": .5})
    assert not geo.score_candidate({"land_available": False, "protected_area": False})["eligible"]
