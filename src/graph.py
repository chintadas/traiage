import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TOPOLOGY_PATH = BASE_DIR / "data" / "topology.json"

class TopologyNode(BaseModel):
    id: str
    type: str
    name: str
    plane: str = "Physical"
    rack: Optional[str] = None
    row: Optional[str] = None
    parent: Optional[str] = None
    feed: Optional[str] = None
    redfish_uri: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TopologyEdge(BaseModel):
    source: str
    target: str
    relation: str  # POWERED_BY, COOLED_BY, CONNECTED_TO, PART_OF, LOCATED_IN
    feed: Optional[str] = None
    psu: Optional[str] = None
    redundancy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DataCenterGraph:
    """
    Multi-plane Topological Dependency Graph for data center root-cause
    correlation, blast radius calculation, and redundancy assessment.
    """

    def __init__(self, topology_data: Optional[dict] = None, file_path: Optional[Path] = None):
        self.nodes: Dict[str, TopologyNode] = {}
        self.edges: List[TopologyEdge] = []
        self.adjacency: Dict[str, List[TopologyEdge]] = {}          # Outgoing edges: source -> [Edge]
        self.reverse_adjacency: Dict[str, List[TopologyEdge]] = {}  # Incoming edges: target -> [Edge]
        self.uri_index: Dict[str, str] = {}                        # redfish_uri -> node_id
        self.children: Dict[str, List[str]] = {}                    # parent_id -> [child_id]

        if topology_data:
            self.load_from_dict(topology_data)
        else:
            path = file_path or DEFAULT_TOPOLOGY_PATH
            self.load_from_file(path)

    def load_from_file(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Topology file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data)

    def load_from_dict(self, data: dict):
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()
        self.reverse_adjacency.clear()
        self.uri_index.clear()
        self.children.clear()

        # Load Nodes
        for raw_node in data.get("nodes", []):
            node = TopologyNode(**raw_node)
            self.nodes[node.id] = node
            self.adjacency[node.id] = []
            self.reverse_adjacency[node.id] = []

            if node.redfish_uri:
                # Normalize URI without trailing slash
                norm_uri = node.redfish_uri.rstrip("/")
                self.uri_index[norm_uri] = node.id

            if node.parent:
                self.children.setdefault(node.parent, []).append(node.id)

        # Load Edges
        for raw_edge in data.get("edges", []):
            edge = TopologyEdge(**raw_edge)
            self.edges.append(edge)
            self.adjacency.setdefault(edge.source, []).append(edge)
            self.reverse_adjacency.setdefault(edge.target, []).append(edge)

    def get_node(self, node_id: str) -> Optional[TopologyNode]:
        return self.nodes.get(node_id)

    def find_node_by_uri(self, redfish_uri: str) -> Optional[TopologyNode]:
        """
        Lookup node by Redfish URI. Handles exact match and sub-resource matching
        (e.g., matching a component's sensor URI to its parent component).
        """
        if not redfish_uri:
            return None

        cleaned = redfish_uri.strip().rstrip("/")
        
        # 1. Exact match
        if cleaned in self.uri_index:
            return self.nodes[self.uri_index[cleaned]]

        # 2. Longest prefix / sub-resource match
        # e.g., /redfish/v1/Chassis/dc1-row01-rack08-node01/PowerSubsystem/PowerSupplies/PSU1
        # matches node with URI /redfish/v1/Chassis/dc1-row01-rack08-node01
        best_match_id = None
        longest_prefix_len = 0

        for indexed_uri, node_id in self.uri_index.items():
            if cleaned.startswith(indexed_uri) and len(indexed_uri) > longest_prefix_len:
                best_match_id = node_id
                longest_prefix_len = len(indexed_uri)

        if best_match_id:
            return self.nodes[best_match_id]

        return None

    def find_upstream_root(
        self,
        node_id: str,
        relation_types: Optional[List[str]] = None,
        max_depth: int = 10
    ) -> List[TopologyNode]:
        """
        Traverse upstream dependency edges (POWERED_BY, COOLED_BY, CONNECTED_TO, PART_OF)
        to identify the root provider(s) of power, cooling, or connectivity.
        Returns list of upstream ancestor nodes ordered from nearest to topmost.
        """
        if node_id not in self.nodes:
            return []

        visited: Set[str] = set()
        ancestors: List[TopologyNode] = []
        queue = [(node_id, 0)]

        allowed_relations = set(relation_types) if relation_types else {
            "POWERED_BY", "COOLED_BY", "CONNECTED_TO", "PART_OF"
        }

        while queue:
            curr_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Check outgoing dependency edges (source is dependent, target is provider)
            for edge in self.adjacency.get(curr_id, []):
                if edge.relation in allowed_relations and edge.target not in visited:
                    visited.add(edge.target)
                    target_node = self.nodes.get(edge.target)
                    if target_node:
                        ancestors.append(target_node)
                        queue.append((edge.target, depth + 1))

            # Also check explicit parent link
            curr_node = self.nodes.get(curr_id)
            if curr_node and curr_node.parent and curr_node.parent not in visited:
                parent_node = self.nodes.get(curr_node.parent)
                if parent_node:
                    visited.add(curr_node.parent)
                    ancestors.append(parent_node)
                    queue.append((curr_node.parent, depth + 1))

        return ancestors

    def find_impacted_assets(
        self,
        node_id: str,
        relation_types: Optional[List[str]] = None,
        max_depth: int = 10
    ) -> List[TopologyNode]:
        """
        Downstream blast radius traversal: given a failed component (e.g. PDU branch, CDU, switch),
        traverse reverse dependency edges to find all dependent compute, storage, or network nodes.
        """
        if node_id not in self.nodes:
            return []

        visited: Set[str] = set()
        impacted: List[TopologyNode] = []
        queue = [(node_id, 0)]

        allowed_relations = set(relation_types) if relation_types else {
            "POWERED_BY", "COOLED_BY", "CONNECTED_TO", "PART_OF"
        }

        while queue:
            curr_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Follow reverse adjacency (target is provider, source is dependent)
            for edge in self.reverse_adjacency.get(curr_id, []):
                if edge.relation in allowed_relations and edge.source not in visited:
                    visited.add(edge.source)
                    source_node = self.nodes.get(edge.source)
                    if source_node:
                        impacted.append(source_node)
                        queue.append((edge.source, depth + 1))

            # Also include children (e.g., components inside a failing chassis)
            for child_id in self.children.get(curr_id, []):
                if child_id not in visited:
                    visited.add(child_id)
                    child_node = self.nodes.get(child_id)
                    if child_node:
                        impacted.append(child_node)
                        queue.append((child_id, depth + 1))

        return impacted

    def find_path(self, start_node_id: str, end_node_id: str) -> Optional[List[dict]]:
        """
        BFS path tracing between two nodes in the multi-plane graph.
        Returns a list of steps describing the path and relationship traversed.
        """
        if start_node_id not in self.nodes or end_node_id not in self.nodes:
            return None

        if start_node_id == end_node_id:
            return [{"node": self.nodes[start_node_id], "relation": "SELF"}]

        visited = {start_node_id}
        queue = [[{"node": self.nodes[start_node_id], "relation": "START"}]]

        while queue:
            path = queue.pop(0)
            last_node_id = path[-1]["node"].id

            if last_node_id == end_node_id:
                return path

            # Check forward edges
            for edge in self.adjacency.get(last_node_id, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    next_node = self.nodes.get(edge.target)
                    if next_node:
                        queue.append(path + [{"node": next_node, "relation": edge.relation, "edge": edge}])

            # Check reverse edges
            for edge in self.reverse_adjacency.get(last_node_id, []):
                if edge.source not in visited:
                    visited.add(edge.source)
                    next_node = self.nodes.get(edge.source)
                    if next_node:
                        queue.append(path + [{"node": next_node, "relation": f"REV_{edge.relation}", "edge": edge}])

            # Check parent/child
            curr_node = self.nodes.get(last_node_id)
            if curr_node and curr_node.parent and curr_node.parent not in visited:
                visited.add(curr_node.parent)
                parent_node = self.nodes.get(curr_node.parent)
                if parent_node:
                    queue.append(path + [{"node": parent_node, "relation": "PARENT"}])

            for child_id in self.children.get(last_node_id, []):
                if child_id not in visited:
                    visited.add(child_id)
                    child_node = self.nodes.get(child_id)
                    if child_node:
                        queue.append(path + [{"node": child_node, "relation": "CHILD"}])

        return None

    def evaluate_redundancy(self, node_id: str, failed_nodes: Set[str]) -> dict:
        """
        Evaluate remaining redundancy margin for a node given a set of failed upstream nodes.
        Particularly critical for dual-corded servers (Feed-A / Feed-B).
        """
        node = self.nodes.get(node_id)
        if not node:
            return {"status": "Unknown", "redundancy": "Unknown"}

        # Inspect power feed redundancy
        power_edges = [e for e in self.adjacency.get(node_id, []) if e.relation == "POWERED_BY"]

        if not power_edges:
            # Check if parent has power edges
            if node.parent:
                power_edges = [e for e in self.adjacency.get(node.parent, []) if e.relation == "POWERED_BY"]

        if power_edges:
            total_feeds = len(power_edges)
            active_feeds = []
            failed_feeds = []

            for edge in power_edges:
                feed_label = edge.feed or edge.target
                # If target or any ancestor of target is in failed_nodes
                target_ancestors = {edge.target} | {a.id for a in self.find_upstream_root(edge.target)}
                if target_ancestors.intersection(failed_nodes):
                    failed_feeds.append(feed_label)
                else:
                    active_feeds.append(feed_label)

            if len(failed_feeds) == 0:
                return {
                    "plane": "Power",
                    "status": "Healthy",
                    "level": f"N+{total_feeds - 1}" if total_feeds > 1 else "N",
                    "redundancy_lost": False,
                    "active_feeds": active_feeds,
                    "failed_feeds": failed_feeds
                }
            elif len(active_feeds) > 0:
                return {
                    "plane": "Power",
                    "status": "Degraded",
                    "level": "N-1 (Single-Feed Redundancy Loss)",
                    "redundancy_lost": True,
                    "active_feeds": active_feeds,
                    "failed_feeds": failed_feeds,
                    "warning": "Node operating without power redundancy. Loss of remaining feed causes immediate drop."
                }
            else:
                return {
                    "plane": "Power",
                    "status": "Outage",
                    "level": "N-0 (Total Power Loss)",
                    "redundancy_lost": True,
                    "active_feeds": [],
                    "failed_feeds": failed_feeds,
                    "warning": "Node has zero active power feeds."
                }

        # Cooling redundancy
        cooling_edges = [e for e in self.adjacency.get(node_id, []) if e.relation == "COOLED_BY"]
        if cooling_edges:
            cooling_failed = any(
                ({e.target} | {a.id for a in self.find_upstream_root(e.target)}).intersection(failed_nodes)
                for e in cooling_edges
            )
            if cooling_failed:
                return {
                    "plane": "Cooling",
                    "status": "Critical",
                    "level": "N-0 (Cooling Failure)",
                    "redundancy_lost": True,
                    "warning": "Active cooling source failed. Imminent thermal emergency."
                }

        return {"status": "Nominal", "redundancy_lost": False}

    def register_dynamic_node(self, node_data: dict, parent_id: Optional[str] = None) -> TopologyNode:
        """
        Just-In-Time (JIT) node registration for dynamic topology discovery.
        Adds node if not already present, updates URI index and parent-child relations.
        """
        node = TopologyNode(**node_data)
        if parent_id and not node.parent:
            node.parent = parent_id

        self.nodes[node.id] = node
        self.adjacency.setdefault(node.id, [])
        self.reverse_adjacency.setdefault(node.id, [])

        if node.redfish_uri:
            self.uri_index[node.redfish_uri.rstrip("/")] = node.id

        if node.parent:
            self.children.setdefault(node.parent, []).append(node.id)

        return node
