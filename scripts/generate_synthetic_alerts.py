#!/usr/bin/env python3
"""
Synthetic Redfish Telemetry Generator for TRAIAGE
Generates 1,000 realistic DMTF Redfish alerts covering cascading failures,
correlated incident storms, and background data center noise.
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "synthetic_1000_alerts.json"

def generate_1000_alerts():
    base_time = datetime(2026, 9, 8, 6, 0, 0, tzinfo=timezone.utc)
    events = []
    evt_num = 1

    def make_event(
        dt: datetime,
        severity: str,
        message_id: str,
        message: str,
        message_args: list,
        origin_uri: str,
        row: str,
        rack: str,
        chassis: str,
        slot: str,
        subsystem: str,
        resolution: str
    ):
        nonlocal evt_num
        event = {
            "EventId": f"EVT-20260908-{evt_num:04d}",
            "Timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Severity": severity,
            "MessageId": message_id,
            "Message": message,
            "MessageArgs": message_args,
            "OriginOfCondition": origin_uri,
            "Location": {
                "DataCenter": "DC-West-01",
                "Room": "DataHall-A",
                "Row": row,
                "Rack": rack,
                "Chassis": chassis,
                "Slot": slot
            },
            "Subsystem": subsystem,
            "Resolution": resolution
        }
        evt_num += 1
        return event

    # =========================================================================
    # STORM 1: Direct Liquid Cooling Leak & Thermal Runaway in Rack-04 (120 alerts)
    # Starts at 06:15:00
    # =========================================================================
    t1 = base_time + timedelta(minutes=15)
    # Root: CDU Leak detection
    events.append(make_event(
        t1, "Critical", "Thermal.1.0.CoolantLeakDetected",
        "Liquid cooling leak detection loop #2 resistance dropped below threshold (liquid detected) at CDU manifold.",
        ["2", "CDU manifold"],
        "/redfish/v1/Chassis/dc1-row02-rack04/ThermalSubsystem/LeakDetection/Tape2",
        "Row-02", "Rack-04", "CDU-Rack04", "U01-U04", "DirectLiquidCooling",
        "Dispatch facilities technician immediately. Inspect quick-disconnect valves and manifold joints in Rack-04."
    ))

    # Cascade 1: Secondary supply pressure drop
    events.append(make_event(
        t1 + timedelta(seconds=12), "Warning", "Sensor.1.0.CoolantPressureLow",
        "CDU secondary supply pressure dropped to 0.82 bar (nominal 1.60 bar). Flow rate declining.",
        ["0.82 bar", "1.60 bar"],
        "/redfish/v1/Chassis/dc1-row02-rack04/ThermalSubsystem/Sensors/CDU_Pressure",
        "Row-02", "Rack-04", "CDU-Rack04", "U01-U04", "DirectLiquidCooling",
        "Verify pump variable frequency drive status and check expansion reservoir level."
    ))

    # Cascade 2: HGX-H100 Nodes 01, 02, 03 GPU temperatures spike and throttle
    nodes_rack04 = [("HGX-H100-Node01", "dc1-row02-rack04-node01", "U12-U17"),
                    ("HGX-H100-Node02", "dc1-row02-rack04-node02", "U18-U23"),
                    ("HGX-H100-Node03", "dc1-row02-rack04-node03", "U24-U29")]

    for offset, (chassis, uri_part, slot) in enumerate(nodes_rack04):
        node_t = t1 + timedelta(seconds=25 + offset * 18)
        for gpu_idx in range(8):
            g_time = node_t + timedelta(seconds=gpu_idx * 3)
            temp = 92 + gpu_idx + offset
            events.append(make_event(
                g_time, "Critical", "Oem.Nvidia.GpuJunctionThermalThresholdExceeded",
                f"GPU {gpu_idx} (SXM5 H100) HBM3 temperature reached {temp}C, exceeding critical threshold of 95C.",
                [str(gpu_idx), "SXM5 H100", f"{temp}C", "95C"],
                f"/redfish/v1/Systems/{uri_part}/Processors/GPU{gpu_idx}/ThermalMetrics",
                "Row-02", "Rack-04", chassis, slot, "AI-Accelerator",
                "Throttle or pause AI workload; inspect coolant supply cold plate."
            ))
            if gpu_idx in (2, 3, 5):
                events.append(make_event(
                    g_time + timedelta(seconds=8), "Critical", "Oem.Nvidia.XidError",
                    f"GPU {gpu_idx} reported fatal XID 79: GPU has fallen off the PCIe bus due to thermal trip.",
                    [str(gpu_idx), "79", "GPU has fallen off the bus"],
                    f"/redfish/v1/Systems/{uri_part}/LogServices/EventLog/Entries/XID79_GPU{gpu_idx}",
                    "Row-02", "Rack-04", chassis, slot, "AI-Accelerator",
                    "Isolate node in Kubernetes cluster and schedule cold plate hardware service."
                ))

        # Fan tray boost
        events.append(make_event(
            node_t + timedelta(seconds=40), "Warning", "Thermal.1.0.FanBoostEngaged",
            f"Fan Tray in {chassis} boosted to 100% PWM emergency acoustic maximum in response to coolant loop failure.",
            [chassis, "100%"],
            f"/redfish/v1/Chassis/{uri_part}/Thermal/Fans",
            "Row-02", "Rack-04", chassis, slot, "Cooling",
            "Acoustic threshold exceeded. Hearing protection required in Row-02."
        ))

    # Fill additional coolant loop & telemetry warnings
    for i in range(50):
        c_time = t1 + timedelta(seconds=70 + i * 4)
        events.append(make_event(
            c_time, "Warning", "Thermal.1.0.CoolantTempDifferentialHigh",
            f"CDU return temperature delta exceeded 14.2C across manifold segment #{i % 6 + 1}.",
            [str(i % 6 + 1), "14.2C"],
            f"/redfish/v1/Chassis/dc1-row02-rack04/ThermalSubsystem/Sensors/CDU_Delta_{i}",
            "Row-02", "Rack-04", "CDU-Rack04", "U01-U04", "DirectLiquidCooling",
            "Check secondary cooling loop balance."
        ))

    # =========================================================================
    # STORM 2: Rack-08 Intelligent ePDU-A Branch Circuit Breaker Trip (150 alerts)
    # Starts at 07:20:00
    # =========================================================================
    t2 = base_time + timedelta(hours=1, minutes=20)
    # Root: ePDU Breaker Trip
    events.append(make_event(
        t2, "Critical", "Power.1.0.BranchCircuitBreakerTripped",
        "Intelligent ePDU-A Branch Circuit 2 breaker tripped open. RMS current dropped from 28.4A to 0.0A instantaneously.",
        ["Branch Circuit 2", "28.4A", "0.0A"],
        "/redfish/v1/Chassis/dc1-row01-rack08/PowerSubsystem/Outlets/Branch2",
        "Row-01", "Rack-08", "ePDU-A-Left", "0U-Left", "Power",
        "Inspect Rack-08 ePDU-A branch 2 for short circuit before resetting breaker."
    ))

    # Cascade: PSU1 AC input lost across 14 compute sleds in Rack-08
    for s_idx in range(1, 15):
        sled_time = t2 + timedelta(seconds=2 + s_idx)
        sled_name = f"ComputeServer-{s_idx:02d}"
        sled_uri = f"dc1-row01-rack08-node{s_idx:02d}"
        u_slot = f"U{s_idx * 2:02d}-U{s_idx * 2 + 1:02d}"
        events.append(make_event(
            sled_time, "Warning", "Power.1.0.PowerSupplyLostACInput",
            f"Power Supply 1 (PSU1) AC input lost on {sled_name}. Automatic failover to PSU2 (Feed-B) active.",
            ["PSU1", "Feed-B"],
            f"/redfish/v1/Chassis/{sled_uri}/PowerSubsystem/PowerSupplies/PSU1",
            "Row-01", "Rack-08", sled_name, u_slot, "Power",
            "Check Feed-A upstream breaker status; sled running with N-1 power redundancy."
        ))
        events.append(make_event(
            sled_time + timedelta(seconds=1), "Warning", "Power.1.0.ChassisPowerRedundancyLost",
            f"{sled_name} redundancy mode transitioned from FullyRedundant (2+0) to NonRedundant (1+0).",
            ["FullyRedundant", "NonRedundant"],
            f"/redfish/v1/Chassis/{sled_uri}/PowerSubsystem",
            "Row-01", "Rack-08", sled_name, u_slot, "Power",
            "Restore Feed-A AC input immediately to re-establish N+1 power redundancy."
        ))
        # Feed-B current surge
        events.append(make_event(
            sled_time + timedelta(seconds=3), "Warning", "Sensor.1.0.CurrentDrawSurge",
            f"Power Supply 2 (PSU2) on {sled_name} current draw surged to 8.9A on Feed-B.",
            ["PSU2", "8.9A"],
            f"/redfish/v1/Chassis/{sled_uri}/PowerSubsystem/PowerSupplies/PSU2/CurrentSensor",
            "Row-01", "Rack-08", sled_name, u_slot, "Power",
            "Monitor Feed-B total ampacity to avoid secondary overload."
        ))

    # Additional power phase telemetry alerts
    for p_idx in range(60):
        pt = t2 + timedelta(seconds=20 + p_idx * 2)
        events.append(make_event(
            pt, "Warning", "Power.1.0.PhaseUnbalanceWarning",
            f"ePDU-A Phase L1/L2 load imbalance reached 34% following Branch 2 trip.",
            ["Phase L1/L2", "34%"],
            f"/redfish/v1/Chassis/dc1-row01-rack08/PowerSubsystem/Phases/Phase_{p_idx % 3}",
            "Row-01", "Rack-08", "ePDU-A-Left", "0U-Left", "Power",
            "Rebalance branch circuit phases across Rack-08."
        ))

    # =========================================================================
    # STORM 3: Optical Degradation & Link Flap on Rack-12 ToR-Switch (110 alerts)
    # Starts at 08:30:00
    # =========================================================================
    t3 = base_time + timedelta(hours=2, minutes=30)
    # Root: Transceiver RX power breach
    events.append(make_event(
        t3, "Warning", "NetworkPort.1.0.OpticalPowerBelowThreshold",
        "Port 1/1 QSFP28 transceiver optical RX power dropped to -18.4 dBm (lower alarm threshold -14.0 dBm).",
        ["1/1", "QSFP28", "-18.4 dBm", "-14.0 dBm"],
        "/redfish/v1/NetworkAdapters/dc1-row03-rack12-sw01/NetworkPorts/1_1/Optical",
        "Row-03", "Rack-12", "ToR-Switch-01", "U41-U42", "Network",
        "Inspect and clean LC optical connector; check fiber bend radius in cable tray."
    ))

    # Flapping link events
    for flap_idx in range(25):
        f_time = t3 + timedelta(seconds=10 + flap_idx * 6)
        state = "Down" if flap_idx % 2 == 0 else "Up"
        sev = "Critical" if state == "Down" else "OK"
        events.append(make_event(
            f_time, sev, f"NetworkPort.1.0.LinkStatus{state}",
            f"Port 1/1 operational link state changed to {state}. 100GbE link carrier lost/restored.",
            ["1/1", state, "100GbE"],
            "/redfish/v1/NetworkAdapters/dc1-row03-rack12-sw01/NetworkPorts/1_1",
            "Row-03", "Rack-12", "ToR-Switch-01", "U41-U42", "Network",
            "Module experiencing physical layer signal loss. Replace QSFP28 optical transceiver."
        ))

    # Dependent host NIC failovers
    for h in range(1, 10):
        h_time = t3 + timedelta(seconds=30 + h * 4)
        events.append(make_event(
            h_time, "Warning", "NetworkInterface.1.0.BondMemberDown",
            f"ComputeServer-{h:02d} bond0 interface detected link loss on primary member eno1; failed over to secondary eno2.",
            ["bond0", "eno1", "eno2"],
            f"/redfish/v1/Systems/dc1-row03-rack12-node{h:02d}/NetworkInterfaces/bond0",
            "Row-03", "Rack-12", f"ComputeServer-{h:02d}", f"U{h * 3:02d}", "Network",
            "Verify uplink path to ToR-Switch-01."
        ))

    for b in range(50):
        bt = t3 + timedelta(seconds=80 + b * 2)
        events.append(make_event(
            bt, "Warning", "Network.1.0.FcsErrorRateHigh",
            f"Port 1/{b % 8 + 1} FCS CRC error rate exceeded 120 errors/sec.",
            [f"1/{b % 8 + 1}", "120 errors/sec"],
            f"/redfish/v1/NetworkAdapters/dc1-row03-rack12-sw01/NetworkPorts/1_{b % 8 + 1}",
            "Row-03", "Rack-12", "ToR-Switch-01", "U41-U42", "Network",
            "Check fiber optic patch lead for particulate contamination."
        ))

    # =========================================================================
    # STORM 4: Host Fatal Memory Crash (Uncorrectable ECC) on Server-07 (80 alerts)
    # Starts at 09:45:00
    # =========================================================================
    t4 = base_time + timedelta(hours=3, minutes=45)
    # Correctable error bursts
    for c_err in range(15):
        ct = t4 + timedelta(seconds=c_err * 2)
        events.append(make_event(
            ct, "Warning", "Memory.1.0.CorrectableECCThresholdExceeded",
            f"DIMM Socket CPU1_DIMM_A3 correctable ECC rate exceeded threshold: {250 + c_err * 30} errors/min.",
            ["CPU1_DIMM_A3", f"{250 + c_err * 30}"],
            "/redfish/v1/Systems/dc1-row02-rack02-node07/Memory/CPU1_DIMM_A3",
            "Row-02", "Rack-02", "ComputeServer-07", "U20-U21", "ComputeHost",
            "Schedule proactive DIMM replacement during next maintenance window."
        ))

    # Root: Uncorrectable ECC crash
    t4_crash = t4 + timedelta(seconds=35)
    events.append(make_event(
        t4_crash, "Critical", "Memory.1.0.UncorrectableECCError",
        "Uncorrectable multi-bit ECC error detected in CPU1 DIMM Slot A3 at physical address 0x7FFA80210000.",
        ["CPU1_DIMM_A3", "0x7FFA80210000"],
        "/redfish/v1/Systems/dc1-row02-rack02-node07/Memory/CPU1_DIMM_A3",
        "Row-02", "Rack-02", "ComputeServer-07", "U20-U21", "ComputeHost",
        "Replace defective DDR5 DIMM in CPU1 DIMM Slot A3."
    ))

    # Machine check exception & emergency NMI reboot
    events.append(make_event(
        t4_crash + timedelta(seconds=2), "Critical", "Host.1.0.MachineCheckException",
        "Fatal hardware Machine Check Exception (MCE) on core 14. Emergency NMI reboot initiated.",
        ["core 14", "NMI reboot"],
        "/redfish/v1/Systems/dc1-row02-rack02-node07/LogServices/EventLog/Entries/MCE01",
        "Row-02", "Rack-02", "ComputeServer-07", "U20-U21", "ComputeHost",
        "Check system event log and quarantine host from cluster."
    ))

    for post_idx in range(60):
        pt = t4_crash + timedelta(seconds=10 + post_idx * 3)
        events.append(make_event(
            pt, "Warning", "System.1.0.POSTMemoryCheckWarning",
            f"BIOS POST memory training test report: rank {post_idx % 4} marginalized on channel A.",
            [f"rank {post_idx % 4}", "channel A"],
            "/redfish/v1/Systems/dc1-row02-rack02-node07/Memory/ChannelA",
            "Row-02", "Rack-02", "ComputeServer-07", "U20-U21", "ComputeHost",
            "Run extended memory BIST diagnostics."
        ))

    # =========================================================================
    # STORM 5: Storage Array NVMe Drive Failure & RAID-6 Degradation (100 alerts)
    # Starts at 11:10:00
    # =========================================================================
    t5 = base_time + timedelta(hours=5, minutes=10)
    events.append(make_event(
        t5, "Warning", "Drive.1.0.DrivePredictiveFailure",
        "NVMe U.2 SSD in Bay 7 SMART status reported available spare block threshold breach (4% remaining).",
        ["Bay 7", "4%"],
        "/redfish/v1/Chassis/dc1-row03-rack05-storage02/Drives/DriveBay7",
        "Row-03", "Rack-05", "StorageArray-02", "U15-U18", "Storage",
        "Stage replacement 15.36TB NVMe drive. Initiate proactive copy."
    ))

    events.append(make_event(
        t5 + timedelta(seconds=15), "Critical", "Storage.1.0.VolumeDegraded",
        "Storage Pool 'Vol-Tier0-Array2' RAID-6 array state transitioned from Optimal to Degraded.",
        ["Vol-Tier0-Array2", "RAID-6", "Degraded"],
        "/redfish/v1/Systems/dc1-row03-rack05-storage02/Storage/1/Volumes/Vol0",
        "Row-03", "Rack-05", "StorageArray-02", "U15-U18", "Storage",
        "Array parity protection at N-1. Complete drive replacement to rebuild parity."
    ))

    for rb in range(98):
        rt = t5 + timedelta(seconds=30 + rb * 5)
        events.append(make_event(
            rt, "Warning", "Storage.1.0.RebuildProgress",
            f"Hot-spare Bay 24 parity rebuild in progress: {rb + 1}% completed. IOPS throughput throttled.",
            ["Bay 24", f"{rb + 1}%"],
            "/redfish/v1/Systems/dc1-row03-rack05-storage02/Storage/1",
            "Row-03", "Rack-05", "StorageArray-02", "U15-U18", "Storage",
            "Monitor parity rebuild completion."
        ))

    # =========================================================================
    # STORM 6: Rack Inlet Environmental Thermal Breach (80 alerts)
    # Starts at 12:45:00
    # =========================================================================
    t6 = base_time + timedelta(hours=6, minutes=45)
    events.append(make_event(
        t6, "Warning", "Environmental.1.0.RackInletExceedsEnvelope",
        "Rack-01 environmental inlet sensor reported 31.5C (ASHRAE A2 recommended threshold 27.0C).",
        ["Rack-01", "31.5C", "27.0C"],
        "/redfish/v1/Chassis/dc1-row01-rack01/ThermalSubsystem/Sensors/InletTemp1",
        "Row-01", "Rack-01", "RackFrame-01", "Top-Inlet", "Environmental",
        "Inspect cold aisle containment doors and verify CRAH unit #4 supply airflow."
    ))

    for s_temp in range(79):
        st = t6 + timedelta(seconds=10 + s_temp * 4)
        c_temp = 28.5 + (s_temp % 5) * 0.8
        events.append(make_event(
            st, "Warning", "Sensor.1.0.TemperatureThresholdExceeded",
            f"Server intake temperature sensor #{s_temp % 6 + 1} reached {c_temp:.1f}C.",
            [f"#{s_temp % 6 + 1}", f"{c_temp:.1f}C"],
            f"/redfish/v1/Chassis/dc1-row01-rack01/Sensors/Intake_{s_temp % 6 + 1}",
            "Row-01", "Rack-01", "RackFrame-01", "U10-U30", "Environmental",
            "Verify perforated floor tile alignment."
        ))

    # =========================================================================
    # STORM 7: CPU 1 PROCHOT Thermal Throttling Cascade in Rack-01 (80 alerts)
    # Starts at 14:15:00
    # =========================================================================
    t7 = base_time + timedelta(hours=8, minutes=15)
    events.append(make_event(
        t7, "Warning", "Processor.1.0.ProcessorThrottled",
        "CPU 1 VRM temperature exceeded 105C on ComputeServer-12. PROCHOT frequency clamping engaged (1400MHz).",
        ["CPU 1", "105C", "1400MHz"],
        "/redfish/v1/Systems/dc1-row04-rack01-node12/Processors/CPU1/Thermal",
        "Row-04", "Rack-01", "ComputeServer-12", "U05-U06", "ComputeHost",
        "Inspect chassis airflow and air baffle alignment in Rack-01."
    ))

    for th in range(79):
        th_t = t7 + timedelta(seconds=5 + th * 4)
        events.append(make_event(
            th_t, "Warning", "Processor.1.0.CorePerformanceDegraded",
            f"Core {th % 32} frequency capped at 1.40GHz due to thermal throttling event on ComputeServer-12.",
            [str(th % 32), "1.40GHz"],
            f"/redfish/v1/Systems/dc1-row04-rack01-node12/Processors/CPU1/Cores/{th % 32}",
            "Row-04", "Rack-01", "ComputeServer-12", "U05-U06", "ComputeHost",
            "Monitor CPU workload thermal delta."
        ))

    # =========================================================================
    # STORM 8: Secondary Power Domain ePDU-B Transient Voltage SAG (90 alerts)
    # Starts at 15:30:00
    # =========================================================================
    t8 = base_time + timedelta(hours=9, minutes=30)
    events.append(make_event(
        t8, "Warning", "Power.1.0.VoltageBelowThreshold",
        "Intelligent ePDU-B input voltage dropped to 198V AC (nominal 208V AC +/- 5%).",
        ["ePDU-B", "198V AC", "208V AC"],
        "/redfish/v1/Chassis/dc1-row01-rack08/PowerSubsystem/Outlets/FeedB_Main",
        "Row-01", "Rack-08", "ePDU-B-Right", "0U-Right", "Power",
        "Check utility transformer tap and UPS-B secondary bypass feed."
    ))

    for v in range(89):
        vt = t8 + timedelta(seconds=2 + v * 3)
        events.append(make_event(
            vt, "Warning", "Power.1.0.InputVoltageSagWarning",
            f"PSU2 on Sled #{v % 14 + 1} recorded transient voltage sag of 199V for 42ms.",
            [f"Sled #{v % 14 + 1}", "199V", "42ms"],
            f"/redfish/v1/Chassis/dc1-row01-rack08-node{v % 14 + 1:02d}/PowerSubsystem/PowerSupplies/PSU2",
            "Row-01", "Rack-08", f"ComputeServer-{v % 14 + 1:02d}", "U02-U30", "Power",
            "Power supply holdup capacitor maintained bus regulation. Informational."
        ))

    # =========================================================================
    # BACKGROUND TELEMETRY NOISE (remaining alerts to reach exactly 1,000)
    # Staged firmware updates, normal link recoveries, sensor audits, logins
    # =========================================================================
    remaining = 1000 - len(events)
    noise_start = base_time
    noise_window = 12 * 3600  # 12 hours

    noise_templates = [
        ("OK", "Update.1.0.FirmwareUpdateStaged",
         "BMC firmware image version 3.4.1 staged successfully. Activation pending next scheduled maintenance reboot.",
         ["3.4.1"], "Management", "Allow firmware to activate during next maintenance window."),
        ("OK", "NetworkPort.1.0.LinkStatusUp",
         "Management interface eth0 negotiated 1000BASE-T Full Duplex link state.",
         ["eth0", "1000BASE-T"], "Network", "Informational event."),
        ("OK", "Security.1.0.OperatorSessionStarted",
         "Authenticated Redfish operator session established via client IP 10.128.4.52.",
         ["10.128.4.52"], "Management", "Audit log recorded."),
        ("OK", "Sensor.1.0.CalibrationComplete",
         "Chassis ambient temperature thermistor auto-calibration completed with zero offset adjustment.",
         ["thermistor"], "Environmental", "Nominal calibration status."),
        ("OK", "Power.1.0.EnergyReportLogged",
         "Hourly rack energy accumulation: 14.82 kWh recorded. Efficiency PUE index 1.12.",
         ["14.82 kWh", "1.12"], "Power", "Nominal telemetry log.")
    ]

    racks = ["Rack-01", "Rack-02", "Rack-04", "Rack-05", "Rack-08", "Rack-10", "Rack-12", "Rack-15"]
    rows = ["Row-01", "Row-02", "Row-03", "Row-04"]

    for i in range(remaining):
        sec_offset = int((i / remaining) * noise_window) + (i % 7)
        noise_dt = noise_start + timedelta(seconds=sec_offset)
        template = noise_templates[i % len(noise_templates)]
        rack = racks[i % len(racks)]
        row = rows[i % len(rows)]
        chassis = f"ComputeServer-{i % 16 + 1:02d}"

        events.append(make_event(
            noise_dt,
            template[0],
            template[1],
            f"[{chassis}] {template[2]}",
            template[3],
            f"/redfish/v1/Systems/dc1-{row.lower()}-{rack.lower()}-node{i % 16 + 1:02d}",
            row, rack, chassis, f"U{i % 38 + 1:02d}",
            template[4],
            template[5]
        ))

    # Sort all events chronologically
    events.sort(key=lambda x: x["Timestamp"])

    # Re-index event IDs sequentially EVT-20260908-0001 through EVT-20260908-1000
    for idx, e in enumerate(events, start=1):
        e["EventId"] = f"EVT-20260908-{idx:04d}"

    dataset = {
        "$schema": "http://redfish.dmtf.org/schemas/v1/Event.v1_7_0.json",
        "Id": "dc1-telemetry-synthetic-1000-batch",
        "Name": "Data Center High-Density Synthetic Redfish Alert Batch (1,000 Events)",
        "Description": "1,000 realistic DMTF Redfish alerts covering cascading multi-domain failures (cooling loop leak, breaker trip, optical flapping, ECC storms, storage wear) plus background noise",
        "TotalCount": len(events),
        "GeneratedAt": datetime.now(timezone.utc).isoformat(),
        "Events": events
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    print(f"Successfully generated {len(events)} synthetic Redfish alerts to {OUTPUT_FILE}")
    print(f"Time range: {events[0]['Timestamp']} to {events[-1]['Timestamp']}")

    # Print summary stats
    crit = sum(1 for e in events if e["Severity"] == "Critical")
    warn = sum(1 for e in events if e["Severity"] == "Warning")
    ok = sum(1 for e in events if e["Severity"] == "OK")
    print(f"Severities: Critical={crit}, Warning={warn}, OK={ok}")

if __name__ == "__main__":
    generate_1000_alerts()
