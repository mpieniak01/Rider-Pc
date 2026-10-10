from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.adapters.mock_rest_adapter import MockRestAdapter


def make_client(demo=False) -> TestClient:
    settings = Settings(test_mode=demo)
    cache = CacheManager()
    app = create_app(settings, cache)
    if demo:
        app.state.rest_adapter = MockRestAdapter()
    return TestClient(app)


def test_logic_summary_explicit_demo():
    client = make_client(demo=True)
    resp = client.get("/api/logic/summary")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    summary = payload["summary"]

    assert summary["counts"]["total"] >= 1
    assert isinstance(summary["features"], list)
    names = {feature["name"] for feature in summary["features"]}
    assert {"s0_manual", "s3_follow_me_face", "s9_navigation"}.issubset(names)


def test_logic_features_explicit_demo():
    client = make_client(demo=True)
    resp = client.get("/api/logic/features")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert isinstance(payload["features"], list)
    assert any(feature["name"] == "s3_follow_me_face" for feature in payload["features"])


def test_missing_adapter_never_falls_back_to_demo():
    client = make_client()
    for endpoint in ("/api/logic/features", "/api/logic/summary"):
        payload = client.get(endpoint).json()
        assert payload["ok"] is False
        assert payload["offline"] is True
        assert payload["features"] == []
