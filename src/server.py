import json
import os
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.models import RedfishAlert, AlertStats

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "seed_alerts.json"
SYNTHETIC_DATA_PATH = BASE_DIR / "data" / "synthetic_1000_alerts.json"
SYNTHETIC_10000_DATA_PATH = BASE_DIR / "data" / "synthetic_10000_alerts.json"
PUBLIC_DIR = BASE_DIR / "public"

DATASETS = {
    "seed_20": {
        "id": "seed_20",
        "name": "Seed Dataset (20 Alerts)",
        "path": DATA_PATH,
        "description": "Baseline curated telemetry covering 8 core data center incidents"
    },
    "synthetic_1000": {
        "id": "synthetic_1000",
        "name": "Synthetic Dataset (1,000 Alerts)",
        "path": SYNTHETIC_DATA_PATH,
        "description": "High-density cascaded failure storms (cooling leak, breaker trip, ToR flap, ECC crash, NVMe rebuild) + background noise"
    },
    "synthetic_10000": {
        "id": "synthetic_10000",
        "name": "Synthetic Dataset (10,000 Alerts / 24h)",
        "path": SYNTHETIC_10000_DATA_PATH,
        "description": "High-density multi-domain cascaded failure storms spread over a 24-hour telemetry window plus background operational noise"
    }
}

active_dataset_id = "seed_20"

def get_active_dataset_path() -> Path:
    entry = DATASETS.get(active_dataset_id, DATASETS["seed_20"])
    return entry["path"]

app = FastAPI(
    title="Data Center Alert Triage API",
    description="Telemetry ingestion and triage API for data center Redfish alerts",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_static(request, call_next):
    """Make browsers revalidate frontend assets so UI edits appear on a plain refresh."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response

def load_seed_alerts() -> List[dict]:
    p = get_active_dataset_path()
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("Events", [])

@app.get("/api/alerts")
def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: Critical, Warning, OK"),
    subsystem: Optional[str] = Query(None, description="Filter by subsystem"),
    rack: Optional[str] = Query(None, description="Filter by rack"),
    search: Optional[str] = Query(None, description="Global text search query"),
    sort_by: Optional[str] = Query("Timestamp", description="Field to sort by: Timestamp, Severity, Rack"),
    order: Optional[str] = Query("desc", description="Sort order: asc or desc")
):
    raw_events = load_seed_alerts()
    results = raw_events

    # Severity filter
    if severity and severity.lower() != "all":
        results = [e for e in results if e.get("Severity", "").lower() == severity.lower()]

    # Subsystem filter
    if subsystem and subsystem.lower() != "all":
        results = [e for e in results if e.get("Subsystem", "").lower() == subsystem.lower()]

    # Rack filter
    if rack and rack.lower() != "all":
        results = [
            e for e in results 
            if e.get("Location", {}).get("Rack", "").lower() == rack.lower()
        ]

    # Global text search
    if search:
        s = search.lower().strip()
        filtered = []
        for e in results:
            text_corpus = (
                f"{e.get('EventId', '')} "
                f"{e.get('MessageId', '')} "
                f"{e.get('Message', '')} "
                f"{e.get('OriginOfCondition', '')} "
                f"{e.get('Resolution', '')} "
                f"{e.get('Subsystem', '')} "
                f"{e.get('Location', {}).get('Rack', '')} "
                f"{e.get('Location', {}).get('Chassis', '')}"
            ).lower()
            if s in text_corpus:
                filtered.append(e)
        results = filtered

    # Sorting
    severity_rank = {"critical": 3, "warning": 2, "ok": 1}
    if sort_by == "Severity":
        results = sorted(
            results, 
            key=lambda x: severity_rank.get(x.get("Severity", "").lower(), 0), 
            reverse=(order == "desc")
        )
    elif sort_by == "Rack":
        results = sorted(
            results,
            key=lambda x: x.get("Location", {}).get("Rack", ""),
            reverse=(order == "desc")
        )
    else:  # default Timestamp
        results = sorted(
            results,
            key=lambda x: x.get("Timestamp", ""),
            reverse=(order == "desc")
        )

    return {
        "count": len(results),
        "total": len(raw_events),
        "alerts": results
    }

@app.get("/api/alerts/{event_id}")
def get_alert_by_id(event_id: str):
    raw_events = load_seed_alerts()
    for e in raw_events:
        if e.get("EventId") == event_id:
            return e
    raise HTTPException(status_code=404, detail=f"Alert '{event_id}' not found")

@app.get("/api/stats", response_model=AlertStats)
def get_stats():
    raw_events = load_seed_alerts()
    critical = sum(1 for e in raw_events if e.get("Severity") == "Critical")
    warning = sum(1 for e in raw_events if e.get("Severity") == "Warning")
    ok = sum(1 for e in raw_events if e.get("Severity") == "OK")
    
    racks = sorted(list({e.get("Location", {}).get("Rack", "") for e in raw_events if e.get("Location", {}).get("Rack")}))
    subsystems = sorted(list({e.get("Subsystem", "") for e in raw_events if e.get("Subsystem")}))

    return AlertStats(
        total=len(raw_events),
        critical=critical,
        warning=warning,
        ok=ok,
        racks_affected=len(racks),
        subsystems_affected=len(subsystems),
        subsystems=subsystems,
        racks=racks
    )

from src.triage_engine import TriageEngine, Incident
from pydantic import BaseModel

class IncidentStatusUpdate(BaseModel):
    status: str

class DatasetSwitchRequest(BaseModel):
    dataset: str

# Shared in-memory engine instance
triage_engine = TriageEngine(alerts_path=get_active_dataset_path())

@app.get("/api/datasets")
def get_datasets():
    results = []
    for k, v in DATASETS.items():
        count = 0
        if v["path"].exists():
            try:
                with open(v["path"], "r", encoding="utf-8") as f:
                    count = len(json.load(f).get("Events", []))
            except Exception:
                count = 0
        results.append({
            "id": v["id"],
            "name": v["name"],
            "count": count,
            "description": v["description"],
            "is_active": (v["id"] == active_dataset_id)
        })
    return {
        "active": active_dataset_id,
        "datasets": results
    }

@app.post("/api/datasets/active")
def set_active_dataset(payload: DatasetSwitchRequest):
    global active_dataset_id, triage_engine
    if payload.dataset not in DATASETS:
        raise HTTPException(status_code=400, detail=f"Unknown dataset '{payload.dataset}'")
    
    active_dataset_id = payload.dataset
    target_path = get_active_dataset_path()
    triage_engine = TriageEngine(alerts_path=target_path)
    triage_engine.correlate()

    raw_alerts = load_seed_alerts()
    return {
        "status": "success",
        "active": active_dataset_id,
        "name": DATASETS[active_dataset_id]["name"],
        "alerts_count": len(raw_alerts),
        "incidents_count": len(triage_engine.incidents)
    }

@app.get("/api/incidents")
def get_incidents(
    priority: Optional[str] = Query(None, description="Filter by priority: P1, P2, P3, P4"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status: Active, Acknowledged, Resolved"),
    search: Optional[str] = Query(None, description="Search in title, hypothesis, or location")
):
    if not triage_engine.incidents:
        triage_engine.correlate()
    
    results = triage_engine.incidents

    # Priority filter
    if priority and priority.lower() != "all":
        results = [inc for inc in results if inc.priority.lower() == priority.lower()]

    # Category filter
    if category and category.lower() != "all":
        results = [inc for inc in results if inc.category.lower() == category.lower()]

    # Status filter
    if status and status.lower() != "all":
        results = [inc for inc in results if inc.status.lower() == status.lower()]

    # Search filter
    if search:
        s = search.lower().strip()
        filtered = []
        for inc in results:
            corpus = f"{inc.id} {inc.title} {inc.root_cause_hypothesis} {inc.root_cause_location} {inc.category} {inc.dispatch_target}".lower()
            if s in corpus:
                filtered.append(inc)
        results = filtered

    return {
        "count": len(results),
        "total": len(triage_engine.incidents),
        "incidents": [inc.model_dump() for inc in results]
    }

@app.get("/api/incidents/{incident_id}")
def get_incident_by_id(incident_id: str):
    if not triage_engine.incidents:
        triage_engine.correlate()
    for inc in triage_engine.incidents:
        if inc.id.lower() == incident_id.lower():
            return inc.model_dump()
    raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

@app.post("/api/incidents/{incident_id}/status")
def update_incident_status(incident_id: str, payload: IncidentStatusUpdate):
    if not triage_engine.incidents:
        triage_engine.correlate()
    for inc in triage_engine.incidents:
        if inc.id.lower() == incident_id.lower():
            inc.status = payload.status
            return inc.model_dump()
    raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

if PUBLIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="127.0.0.1", port=8088, reload=True)
