import json
from datetime import datetime
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_alerts.json"

def test_seed_dataset_exists_and_valid_json():
    assert DATA_PATH.exists(), f"Dataset file not found at {DATA_PATH}"
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "Events" in data
    assert isinstance(data["Events"], list)
    assert len(data["Events"]) == 20

def test_alert_records_schema_compliance():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_severities = {"Critical", "Warning", "OK"}
    event_ids = set()

    for event in data["Events"]:
        # Required fields
        for field in ["EventId", "Timestamp", "Severity", "MessageId", "Message", "OriginOfCondition", "Location", "Subsystem"]:
            assert field in event, f"Missing required field '{field}' in event: {event.get('EventId')}"
            assert event[field], f"Field '{field}' should not be empty in event: {event.get('EventId')}"

        # Unique EventId
        eid = event["EventId"]
        assert eid not in event_ids, f"Duplicate EventId found: {eid}"
        event_ids.add(eid)

        # Valid severity
        assert event["Severity"] in valid_severities, f"Invalid severity '{event['Severity']}' in {eid}"

        # Valid ISO 8601 Timestamp
        ts = event["Timestamp"]
        assert ts.endswith("Z"), f"Timestamp should be UTC ending in Z: {ts}"
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError as err:
            assert False, f"Invalid ISO 8601 timestamp in {eid}: {err}"

        # Valid Location hierarchy
        loc = event["Location"]
        assert isinstance(loc, dict)
        assert "DataCenter" in loc and loc["DataCenter"]
        assert "Rack" in loc and loc["Rack"]

        # Valid OriginOfCondition Redfish URI format
        assert event["OriginOfCondition"].startswith("/redfish/v1/"), (
            f"OriginOfCondition should be a Redfish URI starting with /redfish/v1/: {event['OriginOfCondition']}"
        )
