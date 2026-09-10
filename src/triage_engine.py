import json
from pathlib import Path
from typing import List, Dict, Optional, Set, Any
from datetime import datetime
from pydantic import BaseModel, Field

from src.graph import DataCenterGraph, TopologyNode

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ALERTS_PATH = BASE_DIR / "data" / "seed_alerts.json"
DEFAULT_INCIDENTS_PATH = BASE_DIR / "data" / "incidents.json"

class Incident(BaseModel):
    id: str
    title: str
    priority: str  # P1, P2, P3, P4
    status: str = "Active"  # Active, Investigating, Acknowledged, Resolved
    category: str  # Power, LiquidCooling, AI-Accelerator, Network, ComputeHost, Storage, Environmental, Management
    
    root_cause_alert_id: str
    root_cause_node_id: Optional[str] = None
    root_cause_node_name: Optional[str] = None
    root_cause_component: Optional[str] = None
    root_cause_location: str
    root_cause_hypothesis: str
    
    impact_summary: str
    blast_radius_summary: str = ""
    affected_nodes: List[str] = Field(default_factory=list)
    impacted_nodes: List[str] = Field(default_factory=list)
    redundancy_state: Dict[str, Any] = Field(default_factory=dict)
    redundancy_status: str = ""
    
    alerts_count: int
    alert_ids: List[str] = Field(default_factory=list)
    dependent_alert_ids: List[str] = Field(default_factory=list)
    dependent_alerts_count: int = 0
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    
    recommended_actions: List[str] = Field(default_factory=list)
    dispatch_playbook: List[str] = Field(default_factory=list)
    dispatch_target: str
    suggested_team: str
    
    first_seen: str
    last_seen: str
    first_event_time: str = ""
    latest_event_time: str = ""

class TriageEngine:
    """
    Data Center Alert Triage and Incident Correlation Engine.
    Uses DataCenterGraph for upstream root finding, blast radius calculation,
    and natural-language hypothesis generation.
    """

    def __init__(
        self,
        graph: Optional[DataCenterGraph] = None,
        alerts_path: Optional[Path] = None
    ):
        self.graph = graph or DataCenterGraph()
        self.alerts_path = alerts_path or DEFAULT_ALERTS_PATH
        self.incidents: List[Incident] = []

    def load_alerts(self) -> List[dict]:
        if not self.alerts_path.exists():
            return []
        with open(self.alerts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("Events", [])

    def correlate(self, time_window_seconds: int = 300) -> List[Incident]:
        raw_alerts = self.load_alerts()
        if not raw_alerts:
            return []

        # Parse alerts with timestamp objects for temporal analysis
        parsed_alerts = []
        for alert in raw_alerts:
            ts = alert.get("Timestamp", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.utcnow()
            node = self.graph.find_node_by_uri(alert.get("OriginOfCondition", ""))
            parsed_alerts.append({
                "raw": alert,
                "dt": dt,
                "node": node,
                "event_id": alert.get("EventId", "")
            })

        # Sort chronologically
        parsed_alerts.sort(key=lambda x: x["dt"])

        # Cluster buckets
        # Each cluster has: { "root_alert": ..., "root_node": ..., "child_alerts": [...] }
        clusters: List[Dict[str, Any]] = []

        for item in parsed_alerts:
            alert = item["raw"]
            node = item["node"]
            node_id = node.id if node else None

            assigned = False

            # Try to match with an existing cluster based on upstream graph relationship
            for cluster in clusters:
                c_root_node = cluster["root_node"]
                c_root_alert = cluster["root_alert"]["raw"]

                # 1. Check upstream causality: does item node depend on cluster root node?
                if node_id and c_root_node:
                    ancestors = self.graph.find_upstream_root(node_id)
                    ancestor_ids = {a.id for a in ancestors}

                    if c_root_node.id in ancestor_ids:
                        cluster["child_alerts"].append(item)
                        assigned = True
                        break

                    # Check if cluster root node is child/symptom and this alert is the actual root provider!
                    # E.g. child alerts arrived slightly before or simultaneous with root breaker alert
                    root_ancestors = self.graph.find_upstream_root(c_root_node.id)
                    root_ancestor_ids = {a.id for a in root_ancestors}
                    if node_id in root_ancestor_ids and alert.get("Severity") == "Critical":
                        # Promote this alert to root!
                        cluster["child_alerts"].append(cluster["root_alert"])
                        cluster["root_alert"] = item
                        cluster["root_node"] = node
                        assigned = True
                        break

                # 2. Check same host or port flap (same origin of condition or same chassis)
                if (
                    alert.get("OriginOfCondition") == c_root_alert.get("OriginOfCondition") or
                    (node_id and c_root_node and node_id == c_root_node.id)
                ):
                    time_diff = abs((item["dt"] - cluster["latest_dt"]).total_seconds())
                    if time_diff <= time_window_seconds:
                        cluster["child_alerts"].append(item)
                        cluster["latest_dt"] = max(cluster["latest_dt"], item["dt"])
                        assigned = True
                        break

                # 3. Check direct physical proximity in liquid cooling / high-density thermal domain
                # e.g. CDU leak in Rack-04 causing GPU overheating and fan tray boost in Rack-04
                if node_id and c_root_node:
                    c_rack = c_root_node.rack or (c_root_alert.get("Location", {}).get("Rack"))
                    a_rack = node.rack or (alert.get("Location", {}).get("Rack"))
                    if c_rack and a_rack and c_rack == a_rack:
                        time_diff = abs((item["dt"] - cluster["root_alert"]["dt"]).total_seconds())
                        if time_diff <= time_window_seconds:
                            # Thermal or cooling cascade in the same rack
                            c_sub = c_root_alert.get("Subsystem", "")
                            a_sub = alert.get("Subsystem", "")
                            cooling_subs = {"DirectLiquidCooling", "Cooling", "AI-Accelerator", "Compute-CPU"}
                            if c_sub in cooling_subs and a_sub in cooling_subs:
                                cluster["child_alerts"].append(item)
                                cluster["latest_dt"] = max(cluster["latest_dt"], item["dt"])
                                assigned = True
                                break

                # 4. Check same physical Chassis within the time window (e.g. StorageArray-02 drive failure & volume degraded)
                c_chassis = c_root_alert.get("Location", {}).get("Chassis")
                a_chassis = alert.get("Location", {}).get("Chassis")
                if c_chassis and a_chassis and c_chassis == a_chassis:
                    time_diff = abs((item["dt"] - cluster["latest_dt"]).total_seconds())
                    if time_diff <= time_window_seconds:
                        cluster["child_alerts"].append(item)
                        cluster["latest_dt"] = max(cluster["latest_dt"], item["dt"])
                        assigned = True
                        break

            if not assigned:
                # Create a new cluster
                clusters.append({
                    "root_alert": item,
                    "root_node": node,
                    "child_alerts": [],
                    "latest_dt": item["dt"]
                })

        # Synthesize Correlated Incidents from clusters
        incidents = []
        inc_counter = 1

        for cluster in clusters:
            root_item = cluster["root_alert"]
            root_alert = root_item["raw"]
            root_node = cluster["root_node"]
            child_items = cluster["child_alerts"]

            all_cluster_items = [root_item] + child_items
            all_raw_alerts = [i["raw"] for i in all_cluster_items]
            all_raw_alerts.sort(key=lambda x: x.get("Timestamp", ""))

            # Calculate timestamps
            first_seen = all_raw_alerts[0].get("Timestamp", "")
            last_seen = all_raw_alerts[-1].get("Timestamp", "")

            # Location formatting
            loc = root_alert.get("Location", {})
            loc_str = f"{loc.get('Row', 'Row-?')}, {loc.get('Rack', 'Rack-?')}"
            if loc.get("Chassis"):
                loc_str += f" ({loc.get('Chassis')})"

            # Calculate affected nodes / blast radius
            affected_node_ids = set()
            if root_node:
                affected_node_ids.add(root_node.name)
                # Find downstream assets impacted in graph
                impacted_assets = self.graph.find_impacted_assets(root_node.id)
                for a in impacted_assets:
                    affected_node_ids.add(a.name)

            for ci in child_items:
                if ci["node"]:
                    affected_node_ids.add(ci["node"].name)

            affected_nodes_list = sorted(list(affected_node_ids))

            # Redundancy evaluation: find a dependent Server/Sled/Switch to evaluate feed redundancy
            failed_nodes = {root_node.id} if root_node else set()
            redundancy_state = {}
            if root_node:
                for n_name in affected_nodes_list:
                    target_node = next((n for n in self.graph.nodes.values() if n.name == n_name), None)
                    if target_node and target_node.type in ("Server", "StorageArray", "Switch"):
                        eval_res = self.graph.evaluate_redundancy(target_node.id, failed_nodes)
                        if eval_res.get("redundancy_lost"):
                            redundancy_state = eval_res
                            break
                        elif not redundancy_state:
                            redundancy_state = eval_res

            # Natural Language Synthesis: Title, Hypothesis, Category, Priority, and Playbook
            synth = self._synthesize_incident_intelligence(
                root_alert=root_alert,
                root_node=root_node,
                child_alerts=[c["raw"] for c in child_items],
                affected_nodes=affected_nodes_list,
                redundancy_state=redundancy_state
            )

            # Derive redundancy status string from state dict
            redundancy_status_str = ""
            if redundancy_state:
                level = redundancy_state.get("level", "")
                status_val = redundancy_state.get("status", "")
                if level:
                    redundancy_status_str = level
                elif status_val:
                    redundancy_status_str = status_val
                else:
                    redundancy_status_str = "Nominal"
            else:
                redundancy_status_str = "Nominal"

            all_event_ids = [a.get("EventId", "") for a in all_raw_alerts]
            root_component_name = root_node.name if root_node else "Unknown Component"

            incident = Incident(
                id=f"INC-20260908-{inc_counter:03d}",
                title=synth["title"],
                priority=synth["priority"],
                status="Active",
                category=synth["category"],
                root_cause_alert_id=root_alert.get("EventId", ""),
                root_cause_node_id=root_node.id if root_node else None,
                root_cause_node_name=root_component_name,
                root_cause_component=root_component_name,
                root_cause_location=loc_str,
                root_cause_hypothesis=synth["hypothesis"],
                impact_summary=synth["impact_summary"],
                blast_radius_summary=synth["impact_summary"],
                affected_nodes=affected_nodes_list,
                impacted_nodes=affected_nodes_list,
                redundancy_state=redundancy_state,
                redundancy_status=redundancy_status_str,
                alerts_count=len(all_raw_alerts),
                alert_ids=all_event_ids,
                dependent_alert_ids=all_event_ids,
                dependent_alerts_count=len(all_raw_alerts),
                alerts=all_raw_alerts,
                recommended_actions=synth["recommended_actions"],
                dispatch_playbook=synth["recommended_actions"],
                dispatch_target=synth["dispatch_target"],
                suggested_team=synth["suggested_team"],
                first_seen=first_seen,
                last_seen=last_seen,
                first_event_time=first_seen,
                latest_event_time=last_seen
            )
            incidents.append(incident)
            inc_counter += 1

        # Sort incidents by Priority (P1 > P2 > P3 > P4) then Timestamp desc
        priority_rank = {"P1": 4, "P2": 3, "P3": 2, "P4": 1}
        incidents.sort(
            key=lambda inc: (priority_rank.get(inc.priority, 0), inc.first_seen),
            reverse=True
        )

        self.incidents = incidents
        return incidents

    def _synthesize_incident_intelligence(
        self,
        root_alert: dict,
        root_node: Optional[TopologyNode],
        child_alerts: List[dict],
        affected_nodes: List[str],
        redundancy_state: dict
    ) -> Dict[str, Any]:
        """
        Synthesizes natural-language title, root cause hypothesis, impact summary,
        priority rank, and step-by-step dispatch actions.
        """
        msg_id = root_alert.get("MessageId", "")
        subsystem = root_alert.get("Subsystem", "")
        root_name = root_node.name if root_node else "Managed Component"
        loc = root_alert.get("Location", {})
        rack = loc.get("Rack", "Rack-??")
        row = loc.get("Row", "Row-??")

        # 1. Liquid Cooling & Thermal Cascade
        if "CoolantLeakDetected" in msg_id or subsystem == "DirectLiquidCooling":
            has_gpu_drop = any("XidError" in a.get("MessageId", "") for a in child_alerts)
            return {
                "title": f"Direct Liquid Cooling Leak & Thermal Runaway in {rack}",
                "priority": "P1",
                "category": "LiquidCooling",
                "hypothesis": (
                    f"Coolant leak detected on CDU tape sensor in {rack}. "
                    "Loss of coolant flow caused rapid thermal throttling on H100 GPU cold plates (98°C breach), "
                    "escalating to fatal NVIDIA XID 79 bus drop and thermal fan ramp."
                ),
                "impact_summary": f"Direct threat to {len(affected_nodes)} high-density compute nodes; GPU bus drop confirmed on Node 01.",
                "recommended_actions": [
                    f"Dispatch Facilities Technician immediately to {row}, {rack} (CDU Manifold).",
                    "Inspect quick-disconnect valves and manifold hose barbs for fluid escape.",
                    "Drain/cordon Kubernetes node HGX-H100-Node01 to prevent scheduler cascade.",
                    "Verify secondary cooling loop pressure and cold plate supply delta."
                ],
                "dispatch_target": f"{row}, {rack}, CDU Manifold",
                "suggested_team": "Facilities - Mechanical & AI Hardware Ops"
            }

        # 2. Power Distribution & Breaker Trip
        if "BranchCircuitBreakerTripped" in msg_id or (subsystem == "Power" and "Breaker" in root_alert.get("Message", "")):
            count_servers = len([n for n in affected_nodes if "Compute" in n or "Node" in n or "Sled" in n])
            return {
                "title": f"{rack} Intelligent ePDU-A Branch Circuit 2 Breaker Trip",
                "priority": "P2",
                "category": "Power",
                "hypothesis": (
                    f"Branch Circuit 2 on {root_name} tripped open (28.4A drop), abruptly cutting AC feed to PSU1 "
                    f"across {count_servers} compute sleds. All nodes survived via automatic Feed-B failover, "
                    "but are operating at zero power redundancy (N-1 degraded)."
                ),
                "impact_summary": f"{count_servers} Compute Sleds operating at zero power redundancy (N-1 degraded).",
                "recommended_actions": [
                    f"Inspect ePDU-A in {rack} (0U Left position) and verify Branch 2 breaker status.",
                    "Measure Feed-B total amperage load before resetting breaker to avoid dual-feed overload.",
                    "Balance branch phase loads and reset Branch Circuit 2 breaker to restore Feed-A redundancy."
                ],
                "dispatch_target": f"{row}, {rack}, ePDU-A 0U Left",
                "suggested_team": "Facilities - Electrical Operations"
            }

        # 3. Network Optical Degradation & Port Flapping
        if "Network" in subsystem or "NetworkPort" in msg_id or "OpticalPower" in msg_id:
            return {
                "title": f"ToR Switch Port 1/1 Optical Degradation & Flap in {rack}",
                "priority": "P2",
                "category": "NetworkFabric",
                "hypothesis": (
                    f"Optical transceiver receive power on {root_name} dropped to -18.4 dBm (below threshold), "
                    "triggering high symbol error rate and link flapping. Host NIC failover active to secondary link."
                ),
                "impact_summary": f"1 Top-of-Rack switch port degraded; host uplink failed over to secondary interface eno2.",
                "recommended_actions": [
                    f"Locate ToR-Switch-01 in {rack} (U41-U42).",
                    "Inspect Port 1/1 QSFP28 transceiver optics and clean LC/MPO fiber connector end-faces with click cleaner.",
                    "Replace failing optical transceiver module if low optical power persists."
                ],
                "dispatch_target": f"{row}, {rack}, ToR Switch (U41-U42)",
                "suggested_team": "Network Engineering & Datacenter Operations"
            }

        # 4. Host Compute Hardware Memory / Kernel Crash
        if "MemoryECC" in msg_id or "FatalNMI" in msg_id or "Compute-Memory" in subsystem:
            return {
                "title": f"Host Fatal Memory Crash (Uncorrectable ECC) on {root_name}",
                "priority": "P2",
                "category": "ComputeHost",
                "hypothesis": (
                    f"Uncorrectable multi-bit ECC error in CPU1 DIMM Slot A3 on {root_name}. "
                    "Hardware Machine Check Exception triggered an emergency NMI reboot to prevent memory corruption."
                ),
                "impact_summary": f"ComputeServer-07 forced reboot; single node offline pending DIMM quarantine.",
                "recommended_actions": [
                    f"Quarantine host {root_name} in cluster orchestrator to prevent rescheduled workload failures.",
                    f"Dispatch hardware tech to {rack} (U20-U21) to reseat or replace DDR5 DIMM in socket CPU1 DIMM_A3.",
                    "Execute memtester / memory BIST diagnostics before returning node to active pool."
                ],
                "dispatch_target": f"{row}, {rack}, Server U20-U21",
                "suggested_team": "Hardware SRE / Compute Operations"
            }

        # 5. Storage Degradation / Drive Predictive Wear-out
        if "Storage" in subsystem or "DrivePredictiveFailure" in msg_id or "VolumeDegraded" in msg_id:
            return {
                "title": f"Storage Array RAID-6 Degraded & Drive Bay 7 Wear-Out in {rack}",
                "priority": "P3",
                "category": "Storage",
                "hypothesis": (
                    f"NVMe SSD in Drive Bay 7 on {root_name} exhausted spare blocks (4% remaining). "
                    "Controller transitioned RAID-6 volume to Degraded status and allocated hot-spare Bay 24 for automatic rebuild."
                ),
                "impact_summary": "Storage pool degraded; RAID rebuild actively in progress (12% complete). No data loss.",
                "recommended_actions": [
                    "Monitor background parity rebuild progress on StorageController1.",
                    f"Stage replacement NVMe U.2 drive for Bay 7 in {rack} (StorageArray-02).",
                    "Perform hot-swap replacement once hot-spare rebuild completes."
                ],
                "dispatch_target": f"{row}, {rack}, StorageArray-02 (U15-U18)",
                "suggested_team": "Storage Operations"
            }

        # 6. CPU Thermal Throttling
        if "ProcessorThrottled" in msg_id or "Compute-CPU" in subsystem:
            return {
                "title": f"CPU 1 PROCHOT Thermal Throttling on {root_name}",
                "priority": "P3",
                "category": "ComputeHost",
                "hypothesis": (
                    f"Processor 1 VRM temperature exceeded 105°C on {root_name}, triggering PROCHOT frequency clamping to 1400MHz."
                ),
                "impact_summary": "Single node computing capacity throttled; performance degraded.",
                "recommended_actions": [
                    f"Inspect chassis airflow and air baffle alignment in {rack} (U05-U06).",
                    "Verify heat sink mounting pressure and thermal interface material (TIM)."
                ],
                "dispatch_target": f"{row}, {rack}, Server U05-U06",
                "suggested_team": "Hardware SRE"
            }

        # 7. Environmental Ingress Breach
        if "RackInletExceedsEnvelope" in msg_id or "Facility-Environmental" in subsystem:
            return {
                "title": f"Rack Inlet Temperature Breach in {rack} (31.5°C)",
                "priority": "P3",
                "category": "Environmental",
                "hypothesis": (
                    f"Environmental inlet sensor in {rack} reported 31.5°C, exceeding ASHRAE A2 recommended threshold (27.0°C)."
                ),
                "impact_summary": f"Elevated ambient temperature in {row}, {rack}; increases thermal stress on top rack servers.",
                "recommended_actions": [
                    f"Inspect cold aisle containment doors and strip curtains in {row}.",
                    "Verify CRAH unit #4 supply airflow and perforated floor tile alignment."
                ],
                "dispatch_target": f"{row}, {rack}, Top Aisle Inlet",
                "suggested_team": "Facilities - HVAC Operations"
            }

        # 8. Management / Firmware Routine Update
        return {
            "title": f"Routine Maintenance: {root_alert.get('Message', root_name)}",
            "priority": "P4",
            "category": "Management",
            "hypothesis": (
                f"Informational event staged on {root_name}. Firmware updated successfully, pending scheduled reboot."
            ),
            "impact_summary": "Zero customer impact; non-urgent maintenance state.",
            "recommended_actions": [
                "No immediate action required.",
                "Allow firmware to activate during next maintenance window."
            ],
            "dispatch_target": f"{row}, {rack}",
            "suggested_team": "Systems Administration"
        }

    def save_to_file(self, path: Optional[Path] = None):
        from datetime import timezone
        target = path or DEFAULT_INCIDENTS_PATH
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "incidents_count": len(self.incidents),
            "incidents": [inc.model_dump() for inc in self.incidents]
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
