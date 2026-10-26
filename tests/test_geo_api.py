from fastapi.testclient import TestClient
from uev.api import create_app


def test_api_and_preview(tmp_path):
    app = create_app(tmp_path / "api.sqlite")
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/v1/metadata").json()["data_status"] == "SYNTHETIC DEMONSTRATION ONLY"
        assert len(client.get("/api/v1/districts").json()) == 5
        a = client.get("/api/v1/summary", params={"district": "Jinja"}).json()
        assert a["electric_vehicles"] > 0 and a["is_demo"]
        feats = client.get("/api/v1/layers/candidates", params={"district": "Jinja"}).json()
        assert feats["type"] == "FeatureCollection"
        assert all(f["properties"]["is_demo"] for f in feats["features"])
        res = client.get("/api/v1/model/preview", params={"district": "Jinja", "target_year": 2049,
                                                             "target_pct": 100, "technology": "DC"})
        assert res.status_code == 200 and res.json()["grid_mwh_per_year"] > 0
        assert client.get("/api/v1/model/preview", params={"target_pct":101}).status_code == 422
        assert client.get("/api/v1/summary", params={"district":"nonexistent"}).status_code == 404
        assert client.get("/api/v1/layers/unknown").status_code == 422
