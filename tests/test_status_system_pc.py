from fastapi.testclient import TestClient

from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings


def make_client(monkeypatch, sample, db_path):
    settings = Settings()
    cache = CacheManager(db_path=str(db_path))
    app = create_app(settings, cache)

    def fake_metrics():
        return sample

    monkeypatch.setattr(
        "pc_client.api.routers.status_router.collect_system_metrics",
        fake_metrics,
    )

    client = TestClient(app)
    return client


def test_status_system_pc(monkeypatch, tmp_path):
    sample = {
        "cpu_pct": 42.0,
        "mem_total_mb": 1024.0,
        "mem_used_mb": 512.0,
        "disk_total_gb": 10.0,
        "disk_used_gb": 5.0,
    }
    client = make_client(monkeypatch, sample, tmp_path / "cache.db")

    resp = client.get("/status/system-pc")
    assert resp.status_code == 200
    data = resp.json()
    for key, value in sample.items():
        assert data[key] == value

    # second request should hit cache (no additional monkeypatch)
    resp = client.get("/status/system-pc")
    assert resp.status_code == 200
