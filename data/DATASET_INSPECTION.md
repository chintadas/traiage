# Data Center Raw Redfish Alerts: Seed Dataset Guide

This dataset (`data/seed_alerts.json`) contains **20 realistic raw telemetry alerts** adhering to the DMTF Redfish Event standard (`Event.v1_7_0.json`). 

It is engineered with deliberate **correlations, cascades, and root causes** across different data center domains to test and demonstrate the Triage Agent's grouping and prioritization capabilities.

---

## 1. Summary of the 20 Raw Alerts

| ID | Timestamp | Severity | Subsystem | Location | Summary / Event |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EVT-0001** | 06:15:22 | `Critical` | DirectLiquidCooling | Row-02, Rack-04 (CDU) | Liquid leak detection tape #2 triggered at CDU manifold |
| **EVT-0002** | 06:15:45 | `Critical` | AI-Accelerator | Row-02, Rack-04, Node-01 | GPU 3 (H100) HBM3 temperature reached 98°C (emergency threshold) |
| **EVT-0003** | 06:16:02 | `Critical` | AI-Accelerator | Row-02, Rack-04, Node-01 | Fatal NVIDIA XID 79: GPU 3 fallen off the bus |
| **EVT-0004** | 06:16:30 | `Warning` | Cooling | Row-02, Rack-04, Node-02 | Fan Tray 2 boosted to 100% (18,500 RPM) due to thermal delta |
| **EVT-0005** | 06:20:10 | `Critical` | Power | Row-01, Rack-08 (ePDU-A) | Intelligent PDU-A Branch Circuit 2 breaker tripped open (28.4A to 0A) |
| **EVT-0006** | 06:20:12 | `Warning` | Power | Row-01, Rack-08, Node-01 | Power Supply 1 AC input lost (0V). Operating on PSU2 redundancy |
| **EVT-0007** | 06:20:13 | `Warning` | Power | Row-01, Rack-08, Node-02 | Power Supply 1 AC input lost (0V). Operating on PSU2 redundancy |
| **EVT-0008** | 06:20:13 | `Warning` | Power | Row-01, Rack-08, Node-03 | Power Supply 1 AC input lost (0V). Operating on PSU2 redundancy |
| **EVT-0009** | 06:20:14 | `Warning` | Power | Row-01, Rack-08, Node-04 | Power Supply 1 AC input lost (0V). Operating on PSU2 redundancy |
| **EVT-0010** | 06:28:05 | `Warning` | Network | Row-03, Rack-12 (ToR-01) | Optical transceiver Rx power low (-18.4 dBm) on Port 1/1 |
| **EVT-0011** | 06:28:40 | `Warning` | Network | Row-03, Rack-12 (ToR-01) | Port 1/1 physical link down (symbol error rate spike) |
| **EVT-0012** | 06:28:46 | `OK` | Network | Row-03, Rack-12 (ToR-01) | Port 1/1 link restored to Up (100GbE autonegotiation) |
| **EVT-0013** | 06:28:42 | `Warning` | Network | Row-03, Rack-12, Node-05 | Host uplink adapter `eno1` carrier lost; failed over to `eno2` |
| **EVT-0014** | 06:33:10 | `Critical` | Compute-Memory | Row-02, Rack-02, Node-07 | Uncorrectable Multi-bit ECC error on CPU1 DIMM Slot A3 |
| **EVT-0015** | 06:33:14 | `Critical` | Compute-Host | Row-02, Rack-02, Node-07 | System Fatal NMI reboot triggered by Machine Check Exception |
| **EVT-0016** | 06:37:00 | `Warning` | Compute-CPU | Row-04, Rack-01, Node-12 | CPU1 PROCHOT asserted (clamped to 1.4GHz, VRM temp > 105°C) |
| **EVT-0017** | 06:40:19 | `Warning` | Storage | Row-03, Rack-05, Storage-02 | NVMe SSD in Bay 7 SMART warning: Available spare blocks degraded to 4% |
| **EVT-0018** | 06:40:22 | `Warning` | Storage | Row-03, Rack-05, Storage-02 | RAID-6 volume 'Pool01-Data' degraded; hot spare Bay 24 allocated for rebuild |
| **EVT-0019** | 06:44:00 | `Warning` | Facility-Environmental | Row-01, Rack-01 (Inlet) | Rack inlet temperature (31.5°C) exceeds ASHRAE A2 limit (27.0°C) |
| **EVT-0020** | 06:50:00 | `OK` | Management-BMC | Row-04, Rack-10, Node-03 | BMC firmware 3.4.1 staged successfully; pending maintenance reboot |

---

## 2. Realistic Incident Clusters (What the Triage Agent will correlate)

1. **Incident #1 (P1 - Critical): Liquid Cooling Leak & GPU Thermal Runaway Cascade**
   - *Underlying Alerts*: EVT-0001, EVT-0002, EVT-0003, EVT-0004
   - *Correlation Vector*: Location (`Row-02 / Rack-04`) + Time window (within 70s) + Subsystem cascade (CDU leak -> H100 GPU overheating -> XID 79 bus drop -> adjacent fan ramp).
   - *Agent Triage Hypothesis*: Coolant loss or valve closure at Rack-04 CDU manifold caused rapid thermal failure on Node 01 GPU 3.

2. **Incident #2 (P2 - Major): Feed-A PDU Branch Circuit Breaker Trip**
   - *Underlying Alerts*: EVT-0005, EVT-0006, EVT-0007, EVT-0008, EVT-0009
   - *Correlation Vector*: Common upstream power provider (`Rack-08 ePDU-A Branch 2`) + Identical timestamp (within 4 seconds).
   - *Agent Triage Hypothesis*: 4 compute sleds lost A-feed redundancy simultaneously due to Branch 2 trip. Servers still running on Feed B, but operating at **zero redundancy**.

3. **Incident #3 (P2 - Major): ToR Switch Port Flapping & Optical Transceiver Degradation**
   - *Underlying Alerts*: EVT-0010, EVT-0011, EVT-0012, EVT-0013
   - *Correlation Vector*: Port 1/1 optical telemetry + Link state transitions + Downstream host interface failover.
   - *Agent Triage Hypothesis*: Dirty or failing optical transceiver on Port 1/1 causing intermittent link drop and host NIC failover. Flap suppression applied.

4. **Incident #4 (P2 - Major): Host Hardware Crash: Uncorrectable Multi-bit ECC**
   - *Underlying Alerts*: EVT-0014, EVT-0015
   - *Correlation Vector*: Same host (`Row-02, Rack-02, Node-07`) + Causality (Memory UCE -> Fatal NMI reboot).
   - *Agent Triage Hypothesis*: Defective DIMM module triggered kernel crash and reboot. Node should be quarantined/drained.

5. **Incident #5 (P3 - Minor): Storage Pool Degraded & NVMe Wearout**
   - *Underlying Alerts*: EVT-0017, EVT-0018
   - *Correlation Vector*: Storage enclosure `StorageArray-02` + SMART spare depletion triggering RAID rebuild.
   - *Agent Triage Hypothesis*: Drive Bay 7 spare exhaustion triggered automatic failover to hot-spare Bay 24. No data loss, rebuild in progress.

6. **Isolated Alerts**:
   - **EVT-0016 (P3)**: Node-12 CPU VRM thermal throttling.
   - **EVT-0019 (P3)**: Cold aisle containment / CRAH airflow issue causing inlet temp breach.
   - **EVT-0020 (P4)**: Routine BMC firmware update pending reboot (Informational).

---

## 3. Redfish Schema Compliance

Each event record conforms to the DMTF Redfish standard:
- `EventId`: Unique event identifier
- `Timestamp`: ISO 8601 UTC timestamp
- `Severity`: `Critical`, `Warning`, or `OK`
- `MessageId`: Registry-based identifier (e.g. `Thermal.1.0.CoolantLeakDetected`)
- `OriginOfCondition`: Redfish URI pointing to the specific managed resource
- `Location`: Hierarchical data center physical placement
- `Resolution`: Recommended operator/automated remediation action
