from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)

def test_get_stats():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 20
    assert data["critical"] == 6
    assert data["warning"] == 12
    assert data["ok"] == 2
    assert data["racks_affected"] == 7
    assert data["subsystems_affected"] == 11
    assert "DirectLiquidCooling" in data["subsystems"]
    assert "Power" in data["subsystems"]
    assert "Rack-04" in data["racks"]
    assert "Rack-08" in data["racks"]

def test_get_all_alerts():
    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 20
    assert data["count"] == 20
    assert len(data["alerts"]) == 20

def test_filter_by_severity_critical():
    response = client.get("/api/alerts?severity=Critical")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 6
    for alert in data["alerts"]:
        assert alert["Severity"] == "Critical"

def test_filter_by_severity_warning():
    response = client.get("/api/alerts?severity=Warning")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 12
    for alert in data["alerts"]:
        assert alert["Severity"] == "Warning"

def test_filter_by_subsystem():
    response = client.get("/api/alerts?subsystem=Power")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    for alert in data["alerts"]:
        assert alert["Subsystem"] == "Power"

def test_filter_by_rack():
    response = client.get("/api/alerts?rack=Rack-04")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 4
    for alert in data["alerts"]:
        assert alert["Location"]["Rack"] == "Rack-04"

def test_search_query():
    # Search for leak detection
    response = client.get("/api/alerts?search=leak")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["alerts"][0]["EventId"] == "EVT-20260908-0001"

    # Search for PDU breaker
    response = client.get("/api/alerts?search=breaker")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["alerts"][0]["EventId"] == "EVT-20260908-0005"

def test_sort_by_timestamp():
    response = client.get("/api/alerts?sort_by=Timestamp&order=desc")
    assert response.status_code == 200
    alerts = response.json()["alerts"]
    timestamps = [a["Timestamp"] for a in alerts]
    assert timestamps == sorted(timestamps, reverse=True)

def test_sort_by_severity():
    response = client.get("/api/alerts?sort_by=Severity&order=desc")
    assert response.status_code == 200
    alerts = response.json()["alerts"]
    severity_order = {"critical": 3, "warning": 2, "ok": 1}
    scores = [severity_order[a["Severity"].lower()] for a in alerts]
    assert scores == sorted(scores, reverse=True)

def test_get_single_alert_success():
    response = client.get("/api/alerts/EVT-20260908-0001")
    assert response.status_code == 200
    data = response.json()
    assert data["EventId"] == "EVT-20260908-0001"
    assert data["Severity"] == "Critical"
    assert "CDU manifold" in data["Message"]

def test_get_single_alert_not_found():
    response = client.get("/api/alerts/EVT-NON-EXISTENT")
    assert response.status_code == 404

def test_static_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "TRAIAGE" in response.text
    assert "Raw Alerts View" in response.text
