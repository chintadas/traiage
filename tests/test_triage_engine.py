import pytest
from pathlib import Path
from src.triage_engine import TriageEngine, Incident

@pytest.fixture
def engine():
    return TriageEngine()

def test_correlate_reduces_raw_alerts_to_incidents(engine):
    incidents = engine.correlate()
    assert len(incidents) > 0
    # 20 raw alerts should collapse into 8 or fewer correlated incidents!
    assert len(incidents) <= 8
    
    # Priority sorting check: P1 must be first
    assert incidents[0].priority == "P1"

def test_liquid_cooling_p1_incident(engine):
    incidents = engine.correlate()
    cooling_inc = next((inc for inc in incidents if inc.category == "LiquidCooling"), None)
    assert cooling_inc is not None
    assert cooling_inc.priority == "P1"
    assert "Rack-04" in cooling_inc.title
    assert "EVT-20260908-0001" in cooling_inc.alert_ids
    assert "EVT-20260908-0002" in cooling_inc.alert_ids
    assert "EVT-20260908-0003" in cooling_inc.alert_ids
    assert "EVT-20260908-0004" in cooling_inc.alert_ids
    assert cooling_inc.alerts_count == 4
    assert "XID 79" in cooling_inc.root_cause_hypothesis
    assert "CDU" in cooling_inc.root_cause_location

def test_power_breaker_p2_incident(engine):
    incidents = engine.correlate()
    power_inc = next((inc for inc in incidents if inc.category == "Power"), None)
    assert power_inc is not None
    assert power_inc.priority == "P2"
    assert "Rack-08" in power_inc.title
    assert "EVT-20260908-0005" == power_inc.root_cause_alert_id
    assert "EVT-20260908-0006" in power_inc.alert_ids
    assert "EVT-20260908-0007" in power_inc.alert_ids
    assert "EVT-20260908-0008" in power_inc.alert_ids
    assert "EVT-20260908-0009" in power_inc.alert_ids
    assert power_inc.alerts_count == 5
    # 4 servers affected
    assert len(power_inc.affected_nodes) >= 4
    # Redundancy state evaluated
    assert power_inc.redundancy_state.get("status") == "Degraded"
    assert power_inc.redundancy_state.get("redundancy_lost") is True

def test_network_flap_incident(engine):
    incidents = engine.correlate()
    net_inc = next((inc for inc in incidents if inc.category == "NetworkFabric"), None)
    assert net_inc is not None
    assert net_inc.priority == "P2"
    assert "Rack-12" in net_inc.title
    assert "EVT-20260908-0010" in net_inc.alert_ids
    assert "EVT-20260908-0011" in net_inc.alert_ids
    assert "EVT-20260908-0012" in net_inc.alert_ids
    assert "EVT-20260908-0013" in net_inc.alert_ids
    assert net_inc.alerts_count == 4

def test_save_incidents_to_file(engine, tmp_path):
    engine.correlate()
    out_file = tmp_path / "test_incidents.json"
    engine.save_to_file(out_file)
    assert out_file.exists()
    
    import json
    with open(out_file, "r") as f:
        data = json.load(f)
    assert "incidents" in data
    assert len(data["incidents"]) == len(engine.incidents)
