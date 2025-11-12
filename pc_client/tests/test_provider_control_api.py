"""Tests for provider control API endpoints."""

import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from pc_client.api.server import create_app
from pc_client.cache import CacheManager
from pc_client.config import Settings


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


def test_providers_state_endpoint(test_client):
    """Test GET /api/providers/state returns provider states."""
    client, cache = test_client
    
    response = client.get("/api/providers/state")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check structure
    assert "voice" in data
    assert "text" in data
    assert "vision" in data
    
    # Check voice provider structure
    assert "current" in data["voice"]
    assert "status" in data["voice"]
    assert "last_health_check" in data["voice"]
    
    # Check default values
    assert data["voice"]["current"] in ["local", "pc"]
    assert data["voice"]["status"] in ["online", "degraded", "offline"]


def test_providers_state_from_cache(test_client):
    """Test that providers state can be read from cache."""
    client, cache = test_client
    
    # Set custom state in cache
    custom_state = {
        "voice": {
            "current": "pc",
            "status": "degraded",
            "last_health_check": "2025-11-12T15:00:00Z"
        },
        "text": {
            "current": "local",
            "status": "online",
            "last_health_check": "2025-11-12T15:00:00Z"
        },
        "vision": {
            "current": "pc",
            "status": "online",
            "last_health_check": "2025-11-12T15:00:00Z"
        }
    }
    cache.set("providers_state", custom_state)
    
    response = client.get("/api/providers/state")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["voice"]["current"] == "pc"
    assert data["voice"]["status"] == "degraded"
    assert data["text"]["current"] == "local"


def test_update_provider_valid_domain(test_client):
    """Test PATCH /api/providers/{domain} with valid domain."""
    client, cache = test_client
    
    response = client.patch(
        "/api/providers/voice",
        json={"target": "pc"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["domain"] == "voice"
    assert "new_state" in data
    assert data["new_state"]["current"] == "pc"


def test_update_provider_invalid_domain(test_client):
    """Test PATCH /api/providers/{domain} with invalid domain."""
    client, cache = test_client
    
    response = client.patch(
        "/api/providers/invalid_domain",
        json={"target": "pc"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "Invalid domain" in data["error"]


def test_update_provider_updates_cache(test_client):
    """Test that updating provider modifies cache."""
    client, cache = test_client
    
    # Set initial state
    initial_state = {
        "voice": {"current": "local", "status": "online"},
        "text": {"current": "local", "status": "online"},
        "vision": {"current": "local", "status": "online"}
    }
    cache.set("providers_state", initial_state)
    
    # Update voice provider
    response = client.patch(
        "/api/providers/voice",
        json={"target": "pc"}
    )
    
    assert response.status_code == 200
    
    # Verify cache was updated
    cached_state = cache.get("providers_state")
    assert cached_state["voice"]["current"] == "pc"
    assert cached_state["text"]["current"] == "local"  # Others unchanged


def test_providers_health_endpoint(test_client):
    """Test GET /api/providers/health returns health metrics."""
    client, cache = test_client
    
    response = client.get("/api/providers/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check structure
    assert "voice" in data
    assert "text" in data
    assert "vision" in data
    
    # Check voice health structure
    assert "status" in data["voice"]
    assert "latency_ms" in data["voice"]
    assert "success_rate" in data["voice"]
    assert "last_check" in data["voice"]
    
    # Check data types
    assert isinstance(data["voice"]["latency_ms"], (int, float))
    assert isinstance(data["voice"]["success_rate"], (int, float))
    assert 0 <= data["voice"]["success_rate"] <= 1


def test_providers_health_from_cache(test_client):
    """Test that provider health can be read from cache."""
    client, cache = test_client
    
    # Set custom health data in cache
    custom_health = {
        "voice": {
            "status": "degraded",
            "latency_ms": 250.5,
            "success_rate": 0.85,
            "last_check": "2025-11-12T15:30:00Z"
        },
        "text": {
            "status": "healthy",
            "latency_ms": 100.2,
            "success_rate": 0.99,
            "last_check": "2025-11-12T15:30:00Z"
        },
        "vision": {
            "status": "healthy",
            "latency_ms": 75.8,
            "success_rate": 0.97,
            "last_check": "2025-11-12T15:30:00Z"
        }
    }
    cache.set("providers_health", custom_health)
    
    response = client.get("/api/providers/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["voice"]["status"] == "degraded"
    assert data["voice"]["latency_ms"] == 250.5
    assert data["voice"]["success_rate"] == 0.85


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


def test_services_graph_from_cache(test_client):
    """Test that services graph can be read from cache."""
    client, cache = test_client
    
    # Set custom graph data in cache
    import time
    custom_graph = {
        "generated_at": time.time(),
        "nodes": [
            {
                "label": "Test Service",
                "unit": "test.service",
                "status": "active",
                "group": "test",
                "since": "2025-11-12 15:00:00",
                "description": "Test service description",
                "edges_out": []
            }
        ],
        "edges": []
    }
    cache.set("services_graph", custom_graph)
    
    response = client.get("/api/services/graph")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["label"] == "Test Service"
    assert data["nodes"][0]["unit"] == "test.service"


def test_all_provider_domains(test_client):
    """Test that all three provider domains are supported."""
    client, cache = test_client
    
    domains = ["voice", "text", "vision"]
    
    for domain in domains:
        response = client.patch(
            f"/api/providers/{domain}",
            json={"target": "pc"}
        )
        
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
    assert "voice" in response.json()
    
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
    
    valid_statuses = ["online", "degraded", "offline"]
    
    response = client.get("/api/providers/state")
    assert response.status_code == 200
    
    data = response.json()
    for domain in ["voice", "text", "vision"]:
        assert data[domain]["status"] in valid_statuses


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
