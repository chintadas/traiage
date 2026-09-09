import pytest
from src.graph import DataCenterGraph

@pytest.fixture
def graph():
    return DataCenterGraph()

def test_graph_loads_nodes_and_edges(graph):
    assert len(graph.nodes) >= 25
    assert len(graph.edges) >= 15
    assert "pdu-rack08-a" in graph.nodes
    assert "cdu-rack04" in graph.nodes
    assert "hgx-node01" in graph.nodes
    assert "tor-rack12-01" in graph.nodes

def test_find_node_by_exact_uri(graph):
    uri = "/redfish/v1/PowerEquipment/RackPDUs/dc1-row01-rack08-pduA/Branches/Branch2"
    node = graph.find_node_by_uri(uri)
    assert node is not None
    assert node.id == "pdu-rack08-a-br2"
    assert node.plane == "Power"

def test_find_node_by_subresource_uri(graph):
    # Alert reports /PowerSubsystem/PowerSupplies/PSU1 on node01
    alert_uri = "/redfish/v1/Chassis/dc1-row01-rack08-node01/PowerSubsystem/PowerSupplies/PSU1"
    node = graph.find_node_by_uri(alert_uri)
    assert node is not None
    assert node.id == "rack08-node01"
    assert node.rack == "Rack-08"

def test_find_upstream_root_power(graph):
    # Node 01 upstream power ancestors
    ancestors = graph.find_upstream_root("rack08-node01")
    ancestor_ids = {a.id for a in ancestors}
    assert "pdu-rack08-a-br2" in ancestor_ids
    assert "pdu-rack08-a" in ancestor_ids

def test_find_upstream_root_cooling(graph):
    # GPU 3 upstream cooling ancestor
    ancestors = graph.find_upstream_root("hgx-node01-gpu3")
    ancestor_ids = {a.id for a in ancestors}
    assert "cdu-rack04" in ancestor_ids

def test_find_impacted_assets_pdu_breaker(graph):
    # Blast radius of Branch Circuit 2 on PDU-A
    impacted = graph.find_impacted_assets("pdu-rack08-a-br2")
    impacted_ids = {n.id for n in impacted}
    assert "rack08-node01" in impacted_ids
    assert "rack08-node02" in impacted_ids
    assert "rack08-node03" in impacted_ids
    assert "rack08-node04" in impacted_ids

def test_find_impacted_assets_cdu(graph):
    # Blast radius of Rack-04 CDU
    impacted = graph.find_impacted_assets("cdu-rack04")
    impacted_ids = {n.id for n in impacted}
    assert "hgx-node01" in impacted_ids
    assert "hgx-node01-gpu3" in impacted_ids
    assert "hgx-node02" in impacted_ids

def test_find_path_between_nodes(graph):
    # Path from PDU branch to compute node
    path = graph.find_path("pdu-rack08-a-br2", "rack08-node01")
    assert path is not None
    assert len(path) == 2
    assert path[0]["node"].id == "pdu-rack08-a-br2"
    assert path[1]["node"].id == "rack08-node01"

    # Path from CDU to GPU
    cooling_path = graph.find_path("cdu-rack04", "hgx-node01-gpu3")
    assert cooling_path is not None
    assert cooling_path[0]["node"].id == "cdu-rack04"
    assert cooling_path[-1]["node"].id == "hgx-node01-gpu3"

def test_evaluate_redundancy_single_feed_loss(graph):
    # Loss of Feed-A PDU Branch 2
    failed_nodes = {"pdu-rack08-a-br2"}
    health = graph.evaluate_redundancy("rack08-node01", failed_nodes)
    assert health["status"] == "Degraded"
    assert health["redundancy_lost"] is True
    assert "A" in health["failed_feeds"]
    assert "B" in health["active_feeds"]

def test_evaluate_redundancy_dual_feed_loss(graph):
    # Loss of both Feed-A and Feed-B
    failed_nodes = {"pdu-rack08-a-br2", "pdu-rack08-b-br2"}
    health = graph.evaluate_redundancy("rack08-node01", failed_nodes)
    assert health["status"] == "Outage"
    assert health["redundancy_lost"] is True
    assert len(health["active_feeds"]) == 0
    assert set(health["failed_feeds"]) == {"A", "B"}

def test_register_dynamic_node(graph):
    new_node_data = {
        "id": "new-server-99",
        "type": "Server",
        "name": "ComputeServer-99",
        "rack": "Rack-08",
        "redfish_uri": "/redfish/v1/Systems/dc1-row01-rack08-node99"
    }
    node = graph.register_dynamic_node(new_node_data, parent_id="rack-08")
    assert node.id == "new-server-99"
    assert graph.get_node("new-server-99") is not None
    assert graph.find_node_by_uri("/redfish/v1/Systems/dc1-row01-rack08-node99") is not None
