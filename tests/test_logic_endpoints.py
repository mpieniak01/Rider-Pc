from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings


def make_client() -> TestClient:
    settings = Settings()
    cache = CacheManager()
    app = create_app(settings, cache)
    return TestClient(app)


def test_logic_summary_local_fallback():
    client = make_client()
    resp = client.get("/api/logic/summary")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    summary = payload["summary"]

    assert summary["counts"]["total"] >= 1
    assert isinstance(summary["features"], list)
    names = {feature["name"] for feature in summary["features"]}
    assert {"s0_manual", "s3_follow_me_face", "s4_recon"}.issubset(names)


def test_logic_features_local_fallback():
    client = make_client()
    resp = client.get("/api/logic/features")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert isinstance(payload["features"], list)
    assert any(feature["name"] == "s3_follow_me_face" for feature in payload["features"])
