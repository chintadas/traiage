#!/usr/bin/env python3
"""
Synthetic Redfish Telemetry Generator for TRAIAGE
Generates realistic DMTF Redfish alerts covering cascading failures,
correlated incident storms, and background data center noise over configurable
alert counts and time horizons (e.g. 1,000 or 10,000 alerts over 24 hours).
"""

import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

def generate_dataset(total_count: int = 10000, duration_hours: int = 24, output_file: Path = None):
    if output_file is None:
        output_file = DATA_DIR / f"synthetic_{total_count}_alerts.json"

    base_time = datetime(2026, 9, 8, 0, 0, 0, tzinfo=timezone.utc)
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
            "EventId": f"EVT-20260908-{evt_num:05d}",
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

    racks = ["Rack-01", "Rack-02", "Rack-04", "Rack-05", "Rack-08", "Rack-10", "Rack-12", "Rack-15"]
    rows = ["Row-01", "Row-02", "Row-03", "Row-04"]

    # Ratio of cascade storm events vs background telemetry
    # For 10,000 alerts: ~35% cascade storm events (~3,500), ~65% background noise (~6,500)
    storm_target = int(total_count * 0.35)
    
    # We will generate 10 distinct cascade incident storms spread across the 24h window
    storm_start_hours = [1.25, 3.5, 6.0, 8.75, 11.2, 13.5, 15.8, 18.25, 20.5, 22.1]
    alerts_per_storm = storm_target // len(storm_start_hours)

    for storm_idx, start_hour in enumerate(storm_start_hours):
        s_base = base_time + timedelta(hours=start_hour)
        storm_type = storm_idx % 6

        if storm_type == 0:
            # Direct Liquid Cooling Leak & GPU Thermal Runaway Cascade (Rack-04)
            events.append(make_event(
                s_base, "Critical", "Thermal.1.0.CoolantLeakDetected",
                f"Liquid cooling leak detection loop #{storm_idx + 1} resistance dropped below threshold at CDU manifold.",
                [str(storm_idx + 1), "CDU manifold"],
                "/redfish/v1/Chassis/dc1-row02-rack04/ThermalSubsystem/LeakDetection/Tape2",
                "Row-02", "Rack-04", "CDU-Rack04", "U01-U04", "DirectLiquidCooling",
                "Dispatch facilities technician immediately. Inspect quick-disconnect valves and manifold joints in Rack-04."
            ))
            events.append(make_event(
                s_base + timedelta(seconds=12), "Warning", "Sensor.1.0.CoolantPressureLow",
                "CDU secondary supply pressure dropped to 0.78 bar. Flow rate declining.",
                ["0.78 bar"],
                "/redfish/v1/Chassis/dc1-row02-rack04/ThermalSubsystem/Sensors/CDU_Pressure",
                "Row-02", "Rack-04", "CDU-Rack04", "U01-U04", "DirectLiquidCooling",
                "Verify pump variable frequency drive status and check expansion reservoir level."
            ))
            for i in range(alerts_per_storm - 2):
                sec = 20 + i * 3
                node_num = (i % 3) + 1
                gpu_id = i % 8
                temp = 94 + (i % 7)
                sev = "Critical" if temp >= 98 else "Warning"
                msg_id = "Oem.Nvidia.GpuJunctionThermalThresholdExceeded" if i % 4 != 0 else "Oem.Nvidia.XidError"
                msg = (f"GPU {gpu_id} (SXM5 H100) HBM3 temperature reached {temp}C."
                       if "Thermal" in msg_id else
                       f"GPU {gpu_id} reported fatal XID 79: GPU fell off the bus due to thermal trip.")
                events.append(make_event(
                    s_base + timedelta(seconds=sec), sev, msg_id, msg,
                    [str(gpu_id), f"{temp}C"],
                    f"/redfish/v1/Systems/dc1-row02-rack04-node0{node_num}/Processors/GPU{gpu_id}/ThermalMetrics",
                    "Row-02", "Rack-04", f"HGX-H100-Node0{node_num}", f"U{12 + node_num * 6}", "AI-Accelerator",
                    "Throttle AI workload and inspect cold plate supply delta."
                ))

        elif storm_type == 1:
            # Intelligent ePDU Branch Circuit Breaker Trip Cascade (Rack-08)
            events.append(make_event(
                s_base, "Critical", "Power.1.0.BranchCircuitBreakerTripped",
                f"Intelligent ePDU-A Branch Circuit 2 breaker tripped open. RMS current dropped to 0.0A instantaneously.",
                ["Branch Circuit 2", "0.0A"],
                "/redfish/v1/Chassis/dc1-row01-rack08/PowerSubsystem/Outlets/Branch2",
                "Row-01", "Rack-08", "ePDU-A-Left", "0U-Left", "Power",
                "Inspect Rack-08 ePDU-A branch 2 for short circuit before resetting breaker."
            ))
            for i in range(alerts_per_storm - 1):
                sec = 2 + i * 2
                sled_num = (i % 14) + 1
                sub_ev = i % 3
                if sub_ev == 0:
                    mid = "Power.1.0.PowerSupplyLostACInput"
                    msg = f"Power Supply 1 (PSU1) AC input lost on ComputeServer-{sled_num:02d}. Failover to Feed-B active."
                    sev = "Warning"
                elif sub_ev == 1:
                    mid = "Power.1.0.ChassisPowerRedundancyLost"
                    msg = f"ComputeServer-{sled_num:02d} power redundancy transitioned to NonRedundant (1+0)."
                    sev = "Warning"
                else:
                    mid = "Sensor.1.0.CurrentDrawSurge"
                    msg = f"Power Supply 2 (PSU2) on ComputeServer-{sled_num:02d} current draw surged to 9.2A on Feed-B."
                    sev = "Warning"
                events.append(make_event(
                    s_base + timedelta(seconds=sec), sev, mid, msg,
                    [f"ComputeServer-{sled_num:02d}"],
                    f"/redfish/v1/Chassis/dc1-row01-rack08-node{sled_num:02d}/PowerSubsystem/PowerSupplies/PSU1",
                    "Row-01", "Rack-08", f"ComputeServer-{sled_num:02d}", f"U{sled_num * 2:02d}", "Power",
                    "Restore Feed-A AC input to re-establish N+1 power redundancy."
                ))

        elif storm_type == 2:
            # Optical Transceiver Flap Storm (Rack-12)
            events.append(make_event(
                s_base, "Warning", "NetworkPort.1.0.OpticalPowerBelowThreshold",
                "Port 1/1 QSFP28 transceiver optical RX power dropped to -18.9 dBm (lower alarm threshold -14.0 dBm).",
                ["1/1", "-18.9 dBm"],
                "/redfish/v1/NetworkAdapters/dc1-row03-rack12-sw01/NetworkPorts/1_1/Optical",
                "Row-03", "Rack-12", "ToR-Switch-01", "U41-U42", "Network",
                "Inspect and clean LC optical connector; check fiber bend radius in cable tray."
            ))
            for i in range(alerts_per_storm - 1):
                sec = 5 + i * 3
                state = "Down" if i % 2 == 0 else "Up"
                sev = "Critical" if state == "Down" else "OK"
                port_idx = (i % 4) + 1
                events.append(make_event(
                    s_base + timedelta(seconds=sec), sev, f"NetworkPort.1.0.LinkStatus{state}",
                    f"Port 1/{port_idx} operational link state changed to {state}. 100GbE carrier lost/restored.",
                    [f"1/{port_idx}", state],
                    f"/redfish/v1/NetworkAdapters/dc1-row03-rack12-sw01/NetworkPorts/1_{port_idx}",
                    "Row-03", "Rack-12", "ToR-Switch-01", "U41-U42", "Network",
                    "Replace QSFP28 optical transceiver if flapping persists."
                ))

        elif storm_type == 3:
            # Host Memory Multi-Bit ECC Storm (Rack-02)
            events.append(make_event(
                s_base, "Critical", "Memory.1.0.UncorrectableECCError",
                "Uncorrectable multi-bit ECC error detected in CPU1 DIMM Slot A3 at physical address 0x7FFA80210000.",
                ["CPU1_DIMM_A3", "0x7FFA80210000"],
                "/redfish/v1/Systems/dc1-row02-rack02-node07/Memory/CPU1_DIMM_A3",
                "Row-02", "Rack-02", "ComputeServer-07", "U20-U21", "ComputeHost",
                "Replace defective DDR5 DIMM in CPU1 DIMM Slot A3."
            ))
            for i in range(alerts_per_storm - 1):
                sec = 1 + i * 2
                dimm_slot = f"CPU1_DIMM_A{i % 4 + 1}"
                events.append(make_event(
                    s_base + timedelta(seconds=sec), "Warning", "Memory.1.0.CorrectableECCThresholdExceeded",
                    f"DIMM Socket {dimm_slot} correctable ECC rate exceeded threshold: {300 + i * 15} errors/min.",
                    [dimm_slot, str(300 + i * 15)],
                    f"/redfish/v1/Systems/dc1-row02-rack02-node07/Memory/{dimm_slot}",
                    "Row-02", "Rack-02", "ComputeServer-07", "U20-U21", "ComputeHost",
                    "Monitor memory channel error rates."
                ))

        elif storm_type == 4:
            # Storage Array NVMe Drive Wear-Out & RAID Parity Rebuild (Rack-05)
            events.append(make_event(
                s_base, "Critical", "Storage.1.0.VolumeDegraded",
                "Storage Pool 'Vol-Tier0-Array2' RAID-6 array state transitioned from Optimal to Degraded.",
                ["Vol-Tier0-Array2", "RAID-6", "Degraded"],
                "/redfish/v1/Systems/dc1-row03-rack05-storage02/Storage/1/Volumes/Vol0",
                "Row-03", "Rack-05", "StorageArray-02", "U15-U18", "Storage",
                "Complete hot-spare drive parity rebuild."
            ))
            for i in range(alerts_per_storm - 1):
                sec = 3 + i * 4
                progress = min(100, int((i / (alerts_per_storm - 1)) * 100))
                events.append(make_event(
                    s_base + timedelta(seconds=sec), "Warning", "Storage.1.0.RebuildProgress",
                    f"Hot-spare Bay 24 parity rebuild in progress: {progress}% completed. IOPS throughput throttled.",
                    ["Bay 24", f"{progress}%"],
                    "/redfish/v1/Systems/dc1-row03-rack05-storage02/Storage/1",
                    "Row-03", "Rack-05", "StorageArray-02", "U15-U18", "Storage",
                    "Monitor parity rebuild completion."
                ))

        else:
            # Environmental Rack Inlet & CPU PROCHOT Cascades (Rack-01)
            events.append(make_event(
                s_base, "Warning", "Environmental.1.0.RackInletExceedsEnvelope",
                "Rack-01 environmental inlet sensor reported 32.1C (ASHRAE A2 recommended threshold 27.0C).",
                ["Rack-01", "32.1C", "27.0C"],
                "/redfish/v1/Chassis/dc1-row01-rack01/ThermalSubsystem/Sensors/InletTemp1",
                "Row-01", "Rack-01", "RackFrame-01", "Top-Inlet", "Environmental",
                "Inspect cold aisle containment doors and verify CRAH unit #4 supply airflow."
            ))
            for i in range(alerts_per_storm - 1):
                sec = 4 + i * 3
                core_id = i % 32
                events.append(make_event(
                    s_base + timedelta(seconds=sec), "Warning", "Processor.1.0.CorePerformanceDegraded",
                    f"Core {core_id} frequency capped at 1.40GHz due to thermal throttling event on ComputeServer-12.",
                    [str(core_id), "1.40GHz"],
                    f"/redfish/v1/Systems/dc1-row04-rack01-node12/Processors/CPU1/Cores/{core_id}",
                    "Row-04", "Rack-01", "ComputeServer-12", "U05-U06", "ComputeHost",
                    "Monitor CPU workload thermal delta."
                ))

    # =========================================================================
    # BACKGROUND TELEMETRY NOISE (distributed evenly across the 24-hour horizon)
    # Staged firmware updates, normal link recoveries, sensor audits, logins,
    # NTP syncs, energy telemetry
    # =========================================================================
    remaining = total_count - len(events)
    total_seconds = duration_hours * 3600

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
         ["14.82 kWh", "1.12"], "Power", "Nominal telemetry log."),
        ("OK", "Time.1.0.NTPSynchronizationAchieved",
         "Chassis real-time clock synchronized with stratum 1 NTP reference server 10.0.0.12 (jitter 0.12ms).",
         ["10.0.0.12", "0.12ms"], "Management", "Time source nominal."),
        ("OK", "Thermal.1.0.FanTachometerNormal",
         "Fan tray tachometer reading stabilized at 4,800 RPM (nominal operating zone).",
         ["4800 RPM"], "Cooling", "Nominal cooling telemetry.")
    ]

    for i in range(remaining):
        # Evenly spread over 24 hours with small sub-second jitter
        sec_offset = int((i / remaining) * total_seconds)
        noise_dt = base_time + timedelta(seconds=sec_offset)
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

    # Sort all events strictly by Timestamp
    events.sort(key=lambda x: x["Timestamp"])

    # Re-index EventId sequentially from 1 to total_count with zero padding
    pad = 5 if total_count >= 10000 else 4
    for idx, e in enumerate(events, start=1):
        e["EventId"] = f"EVT-20260908-{idx:0{pad}d}"

    dataset = {
        "$schema": "http://redfish.dmtf.org/schemas/v1/Event.v1_7_0.json",
        "Id": f"dc1-telemetry-synthetic-{total_count}-batch",
        "Name": f"Data Center High-Density Synthetic Redfish Alert Batch ({total_count:,} Events)",
        "Description": f"{total_count:,} realistic DMTF Redfish alerts covering cascading multi-domain failures across a {duration_hours}-hour period plus background noise",
        "TotalCount": len(events),
        "TimeRange": {
            "Start": events[0]["Timestamp"],
            "End": events[-1]["Timestamp"],
            "DurationHours": duration_hours
        },
        "GeneratedAt": datetime.now(timezone.utc).isoformat(),
        "Events": events
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    print(f"Successfully generated {len(events):,} synthetic Redfish alerts to {output_file}")
    print(f"Time range: {events[0]['Timestamp']} to {events[-1]['Timestamp']} ({duration_hours} hours)")

    crit = sum(1 for e in events if e["Severity"] == "Critical")
    warn = sum(1 for e in events if e["Severity"] == "Warning")
    ok = sum(1 for e in events if e["Severity"] == "OK")
    print(f"Severities: Critical={crit:,}, Warning={warn:,}, OK={ok:,}")
    return output_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic Redfish telemetry dataset")
    parser.add_argument("--count", type=int, default=10000, help="Number of alerts to generate (default: 10000)")
    parser.add_argument("--hours", type=int, default=24, help="Duration in hours to spread timestamps over (default: 24)")
    parser.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else None
    generate_dataset(total_count=args.count, duration_hours=args.hours, output_file=out_path)
