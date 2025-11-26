"""Tests for provider control API endpoints."""

import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings
from pc_client.providers.base import TaskResult, TaskStatus, TaskEnvelope, TaskType


@pytest.fixture
def test_client():
    """Create a test client with temporary cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        settings = Settings()
        cache = CacheManager(db_path=str(db_path))
        app = create_app(settings, cache)

        # Bypass startup event for testing
        app.state.rest_adapter = None
        app.state.zmq_subscriber = None

        client = TestClient(app)
        yield client, cache


@pytest.fixture
def text_client():
    """Client with mock text provider available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        settings = Settings(enable_text_offload=True)
        cache = CacheManager(db_path=str(db_path))
        app = create_app(settings, cache)

        class DummyTextProvider:
            async def process_task(self, task: TaskEnvelope) -> TaskResult:
                assert task.task_type == TaskType.TEXT_GENERATE
                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.COMPLETED,
                    result={"text": task.payload.get("prompt") + " response", "tokens_used": 2, "from_cache": False},
                    meta={"model": "mock-text"},
                )

        app.state.text_provider = DummyTextProvider()
        client = TestClient(app)
        yield client


def test_providers_state_endpoint(test_client):
    """Test GET /api/providers/state returns provider states."""
    client, cache = test_client

    response = client.get("/api/providers/state")

    assert response.status_code == 200
    data = response.json()

    assert "domains" in data
    assert "pc_health" in data
    for domain in ("voice", "text", "vision"):
        assert domain in data["domains"]
        entry = data["domains"][domain]
        assert "mode" in entry
        assert "status" in entry
        assert entry["mode"] in ["local", "pc"]


def test_providers_state_from_cache(test_client):
    """Test that providers state can be read from cache."""
    client, cache = test_client

    # Set custom state in cache
    custom_state = {
        "domains": {
            "voice": {"mode": "pc", "status": "pc_active", "changed_ts": 123.0},
            "text": {"mode": "local", "status": "local_only", "changed_ts": 120.0},
            "vision": {"mode": "pc", "status": "pc_active", "changed_ts": 121.0},
        },
        "pc_health": {"reachable": True, "latency_ms": 42},
    }
    cache.set("providers_state", custom_state)

    response = client.get("/api/providers/state")

    assert response.status_code == 200
    data = response.json()

    assert data["domains"]["voice"]["mode"] == "pc"
    assert data["domains"]["voice"]["status"] == "pc_active"
    assert data["domains"]["text"]["mode"] == "local"


def test_update_provider_valid_domain(test_client):
    """Test PATCH /api/providers/{domain} with valid domain."""
    client, cache = test_client

    response = client.patch("/api/providers/voice", json={"target": "pc"})

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["domain"] == "voice"
    assert "new_state" in data
    assert data["new_state"]["mode"] == "pc"


def test_update_provider_invalid_domain(test_client):
    """Test PATCH /api/providers/{domain} with invalid domain."""
    client, cache = test_client

    response = client.patch("/api/providers/invalid_domain", json={"target": "pc"})

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "Invalid domain" in data["error"]


def test_update_provider_updates_cache(test_client):
    """Test that updating provider modifies cache."""
    client, cache = test_client

    # Set initial state
    initial_state = {
        "domains": {
            "voice": {"mode": "local", "status": "local_only"},
            "text": {"mode": "local", "status": "local_only"},
            "vision": {"mode": "local", "status": "local_only"},
        },
        "pc_health": {"reachable": False},
    }
    cache.set("providers_state", initial_state)

    # Update voice provider
    response = client.patch("/api/providers/voice", json={"target": "pc"})

    assert response.status_code == 200

    # Verify cache was updated
    cached_state = cache.get("providers_state")
    assert cached_state["domains"]["voice"]["mode"] == "pc"
    assert cached_state["domains"]["text"]["mode"] == "local"  # Others unchanged


def test_providers_health_endpoint(test_client):
    """Test GET /api/providers/health returns health metrics."""
    client, cache = test_client

    response = client.get("/api/providers/health")

    assert response.status_code == 200
    data = response.json()

    assert set(data.keys()) == {"voice", "text", "vision"}
    assert "status" in data["voice"]


def test_providers_health_from_cache(test_client):
    """Test that provider health can be read from cache."""
    client, cache = test_client

    # Set custom health data in cache
    custom_health = {
        "voice": {
            "status": "degraded",
            "latency_ms": 250.5,
            "success_rate": 0.85,
            "last_check": "2025-11-12T15:30:00Z",
        },
        "text": {"status": "healthy", "latency_ms": 100.2, "success_rate": 0.99, "last_check": "2025-11-12T15:30:00Z"},
        "vision": {"status": "healthy", "latency_ms": 75.8, "success_rate": 0.97, "last_check": "2025-11-12T15:30:00Z"},
    }
    cache.set("providers_health", custom_health)

    response = client.get("/api/providers/health")

    assert response.status_code == 200
    data = response.json()

    assert data["voice"]["status"] == "degraded"
    assert data["voice"]["latency_ms"] == 250.5
    assert data["voice"]["success_rate"] == 0.85


def test_ai_mode_default(test_client):
    """GET /api/system/ai-mode should return default local mode when adapter missing."""
    client, _ = test_client
    response = client.get("/api/system/ai-mode")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "local"


def test_ai_mode_set_without_adapter(test_client):
    """PUT /api/system/ai-mode should fail when adapter not initialized."""
    client, _ = test_client
    response = client.put("/api/system/ai-mode", json={"mode": "pc_offload"})
    assert response.status_code == 503
    data = response.json()
    assert "error" in data


def test_services_graph_endpoint(test_client):
    """Test GET /api/services/graph returns system services."""
    client, cache = test_client

    response = client.get("/api/services/graph")

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "generated_at" in data
    assert "nodes" in data
    assert "edges" in data

    # Check nodes
    assert isinstance(data["nodes"], list)
    assert len(data["nodes"]) > 0

    # Check first node structure
    node = data["nodes"][0]
    assert "label" in node
    assert "unit" in node
    assert "status" in node
    assert "group" in node
    assert "description" in node

    # Verify expected services
    labels = [n["label"] for n in data["nodes"]]
    assert "FastAPI Server" in labels
    assert "Cache Manager" in labels
    assert "Voice Provider" in labels


def test_services_graph_from_service_manager(test_client):
    """Test that services graph is generated from ServiceManager."""
    client, cache = test_client

    response = client.get("/api/services/graph")

    assert response.status_code == 200
    data = response.json()

    # ServiceManager provides default local services
    assert len(data["nodes"]) > 0
    # Verify node structure
    node = data["nodes"][0]
    assert "label" in node
    assert "unit" in node
    assert "status" in node
    assert "is_local" in node


def test_all_provider_domains(test_client):
    """Test that all three provider domains are supported."""
    client, cache = test_client

    domains = ["voice", "text", "vision"]

    for domain in domains:
        response = client.patch(f"/api/providers/{domain}", json={"target": "pc"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["domain"] == domain


def test_providers_endpoints_cache_fallback(test_client):
    """Test that endpoints provide defaults when cache is empty."""
    client, cache = test_client

    # Ensure cache is empty
    cache.delete("providers_state")
    cache.delete("providers_health")
    cache.delete("services_graph")

    # Test state endpoint
    response = client.get("/api/providers/state")
    assert response.status_code == 200
    state = response.json()
    assert "domains" in state
    assert "voice" in state["domains"]

    # Test health endpoint
    response = client.get("/api/providers/health")
    assert response.status_code == 200
    assert "voice" in response.json()

    # Test graph endpoint
    response = client.get("/api/services/graph")
    assert response.status_code == 200
    assert "nodes" in response.json()


def test_provider_status_values(test_client):
    """Test that provider status values are valid."""
    client, cache = test_client

    valid_statuses = ["local_only", "pc_active", "pc_pending", "status_unknown"]

    response = client.get("/api/providers/state")
    assert response.status_code == 200

    data = response.json()
    for domain in ["voice", "text", "vision"]:
        assert data["domains"][domain]["status"] in valid_statuses


def test_service_graph_node_structure(test_client):
    """Test that service graph nodes have required fields."""
    client, cache = test_client

    response = client.get("/api/services/graph")
    assert response.status_code == 200

    data = response.json()
    required_fields = ["label", "unit", "status", "group", "description"]

    for node in data["nodes"]:
        for field in required_fields:
            assert field in node, f"Node missing required field: {field}"


def test_provider_capabilities_endpoint(test_client):
    """Ensure GET /providers/capabilities returns capability data."""
    client, _ = test_client

    response = client.get("/providers/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert "vision" in payload
    assert "voice" in payload
    assert "text" in payload
    assert payload["vision"]["features"]

    # Alias path
    response_alias = client.get("/api/providers/capabilities")
    assert response_alias.status_code == 200


def test_text_generate_without_provider(test_client):
    """POST /providers/text/generate should fail without provider."""
    client, _ = test_client
    resp = client.post("/providers/text/generate", json={"prompt": "Hello"})
    assert resp.status_code == 503


def test_text_generate_success(text_client):
    """POST /providers/text/generate should return text."""
    resp = text_client.post("/providers/text/generate", json={"prompt": "Hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"].startswith("Hello")
    assert data["meta"]["model"] == "mock-text"
